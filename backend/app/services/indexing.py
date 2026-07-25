from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.constants import DatasetStatus, MAX_TOP_K
from app.models import Conversation, ConversationChunk, Dataset
from app.services.ai_provider import AIProviderError, embed, embedding_uses_remote_api
from app.services.chunking import chunk_text
from app.services.logging_service import write_log
from app.services.settings_service import clear_reindex_required_flag, get_effective_settings


class IndexingError(Exception):
    def __init__(self, message: str, *, status_code: int = 400, errors: list[Any] | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.errors = errors or []


def ensure_vector_index(db: Session) -> None:
    """Create ANN index if missing (safe after embeddings exist)."""
    try:
        db.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_conversation_chunks_embedding_hnsw
                ON conversation_chunks
                USING hnsw (embedding vector_cosine_ops)
                """
            )
        )
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
        try:
            db.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS ix_conversation_chunks_embedding_ivfflat
                    ON conversation_chunks
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100)
                    """
                )
            )
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
            write_log(
                db,
                level="warn",
                event="vector_index_skipped",
                message="Could not create vector ANN index; sequential scan will be used",
                context={},
            )
            db.commit()


def index_dataset(
    db: Session,
    dataset: Dataset,
    *,
    conversation_limit: int | None = None,
    progress_every: int = 500,
) -> Dataset:
    if dataset.conversation_count <= 0:
        raise IndexingError(
            "No conversations to index",
            errors=[{"field": "dataset", "issue": "empty"}],
        )

    if dataset.status == DatasetStatus.INDEXING:
        raise IndexingError(
            "Indexing already in progress",
            status_code=409,
            errors=[{"field": "status", "issue": "indexing"}],
        )

    if dataset.status not in {
        DatasetStatus.IMPORTED,
        DatasetStatus.READY,
        DatasetStatus.FAILED,
    }:
        raise IndexingError(
            f"Dataset status '{dataset.status}' cannot be indexed. Import conversations first.",
            errors=[{"field": "status", "issue": "invalid"}],
        )

    settings = get_settings()
    if embedding_uses_remote_api() and not settings.ai_api_key.strip():
        dataset.status = DatasetStatus.FAILED
        dataset.error_message = (
            "AI_API_KEY is missing. Add your OpenRouter API key to backend/.env "
            "(https://openrouter.ai/keys), then click Index — or set "
            "EMBEDDING_PROVIDER=local for free on-device embeddings."
        )
        write_log(
            db,
            level="error",
            event="index_failed",
            message=dataset.error_message,
            context={"dataset_id": str(dataset.id)},
        )
        db.commit()
        raise IndexingError(dataset.error_message, status_code=400)

    dataset.status = DatasetStatus.INDEXING
    dataset.error_message = None
    write_log(
        db,
        level="info",
        event="index_start",
        message="Indexing started",
        context={
            "dataset_id": str(dataset.id),
            "conversation_limit": conversation_limit,
            "embedding_provider": settings.embedding_provider,
        },
    )
    db.commit()

    try:
        db.execute(delete(ConversationChunk).where(ConversationChunk.dataset_id == dataset.id))
        db.flush()

        q = (
            select(Conversation)
            .where(Conversation.dataset_id == dataset.id)
            .order_by(Conversation.created_at.desc())
        )
        if conversation_limit is not None and conversation_limit > 0:
            q = q.limit(int(conversation_limit))
        conversations = list(db.scalars(q).all())
        if not conversations:
            raise IndexingError("No conversations to index")

        effective = get_effective_settings(db)
        embed_dims = int(
            effective.get("embedding_dimensions") or get_settings().embedding_dimensions
        )
        embed_model = str(effective.get("embedding_model") or "")
        embed_provider = str(effective.get("ai_provider") or "")
        batch_size = 64 if not embedding_uses_remote_api() else 32

        total_chunks = 0
        pending_rows: list[tuple[Conversation, int, str]] = []

        def flush_pending() -> None:
            nonlocal total_chunks, pending_rows
            if not pending_rows:
                return
            texts = [p[2] for p in pending_rows]
            vectors = embed(
                texts,
                model=embed_model,
                dimensions=embed_dims,
                provider=embed_provider,
                batch_size=batch_size,
            )
            if len(vectors) != len(pending_rows):
                raise IndexingError("Embedding provider returned incomplete results")
            for (conv, idx, piece), vector in zip(pending_rows, vectors, strict=True):
                db.add(
                    ConversationChunk(
                        id=uuid.uuid4(),
                        conversation_id=conv.id,
                        dataset_id=dataset.id,
                        chunk_index=idx,
                        content=piece,
                        token_count=len(piece.split()),
                        embedding=vector,
                    )
                )
            total_chunks += len(pending_rows)
            pending_rows = []
            db.flush()

        for i, conv in enumerate(conversations, start=1):
            pieces = chunk_text(conv.content)
            for idx, piece in enumerate(pieces):
                pending_rows.append((conv, idx, piece))
            if len(pending_rows) >= 400:
                flush_pending()
            if progress_every and i % progress_every == 0:
                write_log(
                    db,
                    level="info",
                    event="index_progress",
                    message=f"Indexed {i}/{len(conversations)} conversations",
                    context={
                        "dataset_id": str(dataset.id),
                        "conversations_done": i,
                        "conversations_total": len(conversations),
                        "chunks": total_chunks,
                    },
                )
                db.commit()

        flush_pending()
        if total_chunks <= 0:
            raise IndexingError("No chunkable content found")

        dataset.status = DatasetStatus.READY
        dataset.error_message = None
        write_log(
            db,
            level="info",
            event="index_complete",
            message="Indexing completed",
            context={
                "dataset_id": str(dataset.id),
                "chunks": total_chunks,
                "conversations_indexed": len(conversations),
                "conversation_limit": conversation_limit,
            },
        )
        db.commit()
        db.refresh(dataset)
        clear_reindex_required_flag(db)
        ensure_vector_index(db)
        return dataset

    except IndexingError as exc:
        db.rollback()
        ds = db.get(Dataset, dataset.id)
        if ds:
            ds.status = DatasetStatus.FAILED
            ds.error_message = exc.message
            write_log(
                db,
                level="error",
                event="index_failed",
                message=exc.message,
                context={"dataset_id": str(dataset.id), "errors": exc.errors},
            )
            db.commit()
        raise
    except AIProviderError as exc:
        db.rollback()
        ds = db.get(Dataset, dataset.id)
        if ds:
            ds.status = DatasetStatus.FAILED
            ds.error_message = exc.message
            write_log(
                db,
                level="error",
                event="index_failed",
                message=exc.message,
                context={"dataset_id": str(dataset.id)},
            )
            db.commit()
        raise IndexingError(exc.message, status_code=exc.status_code or 400) from exc
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        ds = db.get(Dataset, dataset.id)
        if ds:
            ds.status = DatasetStatus.FAILED
            ds.error_message = "Indexing failed due to an internal error"
            write_log(
                db,
                level="error",
                event="index_failed",
                message=str(exc),
                context={"dataset_id": str(dataset.id)},
            )
            db.commit()
        raise


def retrieve_similar(
    db: Session,
    *,
    dataset_id: UUID,
    query: str,
    top_k: int = 12,
) -> list[dict[str, Any]]:
    dataset = db.get(Dataset, dataset_id)
    if not dataset:
        raise IndexingError("Dataset not found", status_code=404)
    if dataset.status != DatasetStatus.READY:
        raise IndexingError(
            "Dataset is not ready for search. Index it first.",
            status_code=400,
            errors=[{"field": "status", "value": dataset.status}],
        )

    cleaned = (query or "").strip()
    if not cleaned:
        raise IndexingError(
            "Query must not be empty",
            errors=[{"field": "query", "issue": "required"}],
        )

    if top_k < 1 or top_k > MAX_TOP_K:
        raise IndexingError(
            f"top_k must be between 1 and {MAX_TOP_K}",
            errors=[{"field": "top_k", "issue": "range"}],
        )

    effective = get_effective_settings(db)
    query_vec = embed(
        [cleaned],
        model=str(effective.get("embedding_model") or ""),
        dimensions=int(effective.get("embedding_dimensions") or get_settings().embedding_dimensions),
        provider=str(effective.get("ai_provider") or ""),
    )[0]

    distance = ConversationChunk.embedding.cosine_distance(query_vec)
    stmt = (
        select(ConversationChunk, Conversation, distance.label("distance"))
        .join(Conversation, Conversation.id == ConversationChunk.conversation_id)
        .where(ConversationChunk.dataset_id == dataset_id)
        .where(ConversationChunk.embedding.is_not(None))
        .order_by(distance)
        .limit(top_k)
    )
    rows = db.execute(stmt).all()
    results: list[dict[str, Any]] = []
    for chunk, conv, dist in rows:
        results.append(
            {
                "chunk_id": str(chunk.id),
                "conversation_id": str(conv.id),
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "author": conv.author,
                "source": conv.source,
                "url": conv.url,
                "distance": float(dist) if dist is not None else None,
            }
        )
    return results
