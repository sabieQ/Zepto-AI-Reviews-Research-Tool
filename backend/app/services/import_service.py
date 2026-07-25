from __future__ import annotations

import csv
import io
import json
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.constants import (
    BLOCKED_IMPORT_STATUSES,
    CONVERSATION_PREVIEW_LIMIT,
    DatasetStatus,
    MAX_CONTENT_CHARS,
    MAX_IMPORT_ROWS,
    MAX_UPLOAD_BYTES,
)
from app.models import Conversation, Dataset
from app.schemas.datasets import DatasetCreate
from app.services.cleaning import (
    clean_content,
    content_hash,
    optional_str,
    parse_posted_at,
    parse_rating,
    parse_url,
)
from app.services.logging_service import write_log


class ImportError(Exception):
    def __init__(self, message: str, *, status_code: int = 400, errors: list[Any] | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.errors = errors or []


def list_datasets(db: Session) -> list[Dataset]:
    return list(db.scalars(select(Dataset).order_by(Dataset.created_at.desc())).all())


def get_dataset(db: Session, dataset_id: UUID) -> Dataset | None:
    return db.get(Dataset, dataset_id)


def create_dataset(db: Session, payload: DatasetCreate) -> Dataset:
    dataset = Dataset(
        name=payload.name,
        source=payload.source,
        description=payload.description,
        status=DatasetStatus.PENDING,
        conversation_count=0,
    )
    db.add(dataset)
    db.flush()
    write_log(
        db,
        level="info",
        event="dataset_create",
        message="Dataset created",
        context={"dataset_id": str(dataset.id), "name": dataset.name, "source": dataset.source},
    )
    db.commit()
    db.refresh(dataset)
    return dataset


def delete_dataset(db: Session, dataset: Dataset) -> None:
    dataset_id = str(dataset.id)
    db.delete(dataset)
    write_log(
        db,
        level="info",
        event="dataset_delete",
        message="Dataset deleted",
        context={"dataset_id": dataset_id},
    )
    db.commit()


def list_conversations(
    db: Session, dataset_id: UUID, limit: int = CONVERSATION_PREVIEW_LIMIT
) -> list[Conversation]:
    stmt = (
        select(Conversation)
        .where(Conversation.dataset_id == dataset_id)
        .order_by(Conversation.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def recompute_conversation_count(db: Session, dataset_id: UUID) -> int:
    count = db.scalar(
        select(func.count()).select_from(Conversation).where(Conversation.dataset_id == dataset_id)
    )
    return int(count or 0)


def _decode_upload(raw: bytes) -> str:
    if not raw:
        raise ImportError("Empty file", errors=[{"field": "file", "issue": "empty"}])
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ImportError(
            f"File exceeds maximum size of {MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
            status_code=413,
            errors=[{"field": "file", "issue": "too_large", "max_bytes": MAX_UPLOAD_BYTES}],
        )
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8")
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        raise ImportError(
            "Unsupported encoding (UTF-16). Please upload UTF-8 CSV or JSON.",
            errors=[{"field": "file", "issue": "unsupported_encoding"}],
        )
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ImportError(
            "Unable to decode file as UTF-8",
            errors=[{"field": "file", "issue": "decode_error"}],
        ) from exc


def _normalize_headers(headers: list[str]) -> list[str]:
    return [h.strip().lstrip("\ufeff").lower() for h in headers]


def _parse_csv(text: str) -> list[dict[str, Any]]:
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise ImportError(
            "CSV has no header row",
            errors=[{"field": "file", "issue": "missing_headers"}],
        )
    normalized = _normalize_headers(list(reader.fieldnames))
    if "content" not in normalized:
        raise ImportError(
            "CSV missing required column: content",
            errors=[{"field": "content", "issue": "required", "headers": normalized}],
        )
    rows: list[dict[str, Any]] = []
    try:
        for raw_row in reader:
            row = {
                (_normalize_headers([k])[0] if k is not None else ""): v
                for k, v in raw_row.items()
            }
            rows.append(row)
    except csv.Error as exc:
        raise ImportError(
            f"Malformed CSV: {exc}",
            errors=[{"field": "file", "issue": "malformed_csv"}],
        ) from exc
    return rows


def _parse_json(text: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ImportError(
            f"Malformed JSON: {exc.msg}",
            errors=[{"field": "file", "issue": "malformed_json"}],
        ) from exc
    if not isinstance(payload, list):
        raise ImportError(
            "JSON must be an array of objects",
            errors=[{"field": "file", "issue": "expected_array"}],
        )
    rows: list[dict[str, Any]] = []
    for idx, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ImportError(
                "JSON array must contain only objects",
                errors=[{"field": "file", "issue": "non_object_item", "index": idx}],
            )
        rows.append({str(k).strip().lower(): v for k, v in item.items()})
    if rows and not any("content" in r for r in rows):
        raise ImportError(
            "JSON objects missing required field: content",
            errors=[{"field": "content", "issue": "required"}],
        )
    return rows


def parse_upload(filename: str | None, raw: bytes) -> list[dict[str, Any]]:
    name = (filename or "").lower()
    text = _decode_upload(raw)

    if name.endswith(".exe") or name.endswith(".bin") or name.endswith(".zip"):
        raise ImportError(
            "Unsupported file type. Upload CSV or JSON.",
            errors=[{"field": "file", "issue": "unsupported_type"}],
        )

    if name.endswith(".json"):
        return _parse_json(text)

    stripped = text.lstrip()
    if stripped.startswith("["):
        return _parse_json(text)
    if stripped.startswith("{"):
        return _parse_json(text)

    if name.endswith(".csv") or name.endswith(".txt") or not name:
        return _parse_csv(text)

    raise ImportError(
        "Unsupported file type. Upload CSV or JSON.",
        errors=[{"field": "file", "issue": "unsupported_type"}],
    )


def ingest_conversation_rows(
    db: Session,
    *,
    dataset: Dataset,
    rows: list[dict[str, Any]],
    allow_empty_insert: bool = False,
) -> tuple[int, int, int]:
    """Insert cleaned/deduped conversation rows. Returns (inserted, skipped, truncated).

    Does not change dataset status — callers own status transitions.
    """
    existing_ext = set(
        db.scalars(
            select(Conversation.external_id).where(
                Conversation.dataset_id == dataset.id,
                Conversation.external_id.is_not(None),
            )
        ).all()
    )
    existing_hashes = {
        content_hash(c)
        for c in db.scalars(
            select(Conversation.content).where(Conversation.dataset_id == dataset.id)
        ).all()
    }

    seen_ext_in_batch: set[str] = set()
    seen_hash_in_batch: set[str] = set()
    to_insert: list[Conversation] = []
    skipped = 0
    truncated_rows = 0

    for row in rows:
        raw_content = row.get("content")
        raw_str = None if raw_content is None else str(raw_content)
        cleaned = clean_content(raw_str)
        if cleaned is None:
            skipped += 1
            continue
        if raw_str is not None and len(raw_str) > MAX_CONTENT_CHARS:
            truncated_rows += 1

        external_id = optional_str(row.get("external_id"), max_len=200)
        digest = content_hash(cleaned)

        if external_id:
            if external_id in existing_ext or external_id in seen_ext_in_batch:
                skipped += 1
                continue
            seen_ext_in_batch.add(external_id)
        else:
            if digest in existing_hashes or digest in seen_hash_in_batch:
                skipped += 1
                continue
            seen_hash_in_batch.add(digest)

        meta = row.get("metadata")
        if not isinstance(meta, dict):
            meta = {}

        to_insert.append(
            Conversation(
                dataset_id=dataset.id,
                external_id=external_id,
                source=optional_str(row.get("source"), max_len=64) or dataset.source,
                author=optional_str(row.get("author"), max_len=200),
                content=cleaned,
                raw_content=raw_str[: MAX_CONTENT_CHARS * 2] if raw_str is not None else None,
                rating=parse_rating(row.get("rating")),
                posted_at=parse_posted_at(row.get("posted_at")),
                url=parse_url(row.get("url")),
                metadata_=meta,
            )
        )

    if not to_insert and not allow_empty_insert:
        raise ImportError(
            "No valid rows found after cleaning (all empty or duplicates)",
            errors=[{"field": "file", "issue": "no_valid_rows", "skipped": skipped}],
        )

    for conv in to_insert:
        db.add(conv)
    if to_insert:
        db.flush()
        for conv in to_insert:
            if conv.external_id:
                existing_ext.add(conv.external_id)
            existing_hashes.add(content_hash(conv.content))

    dataset.conversation_count = recompute_conversation_count(db, dataset.id)
    return len(to_insert), skipped, truncated_rows


def import_conversations(
    db: Session,
    *,
    dataset: Dataset,
    filename: str | None,
    raw: bytes,
) -> tuple[Dataset, int, int, int]:
    if dataset.status in BLOCKED_IMPORT_STATUSES:
        raise ImportError(
            "Import already in progress for this dataset",
            status_code=409,
            errors=[{"field": "status", "issue": "processing"}],
        )

    # Validate/parse before mutating status (keeps pending datasets clean on bad files)
    rows = parse_upload(filename, raw)
    if len(rows) > MAX_IMPORT_ROWS:
        raise ImportError(
            f"Row count exceeds maximum of {MAX_IMPORT_ROWS}",
            errors=[{"field": "file", "issue": "too_many_rows", "max_rows": MAX_IMPORT_ROWS}],
        )
    if not rows:
        raise ImportError(
            "No valid rows found in file",
            errors=[{"field": "file", "issue": "no_rows"}],
        )

    write_log(
        db,
        level="info",
        event="import_start",
        message="Import started",
        context={"dataset_id": str(dataset.id), "filename": filename, "row_count": len(rows)},
    )

    previous_status = dataset.status
    dataset.status = DatasetStatus.PROCESSING
    dataset.error_message = None
    db.commit()

    try:
        inserted, skipped, truncated_rows = ingest_conversation_rows(
            db, dataset=dataset, rows=rows, allow_empty_insert=False
        )

        dataset.status = DatasetStatus.IMPORTED
        dataset.error_message = None
        write_log(
            db,
            level="info",
            event="import_complete",
            message="Import completed",
            context={
                "dataset_id": str(dataset.id),
                "inserted": inserted,
                "skipped": skipped,
                "truncated_rows": truncated_rows,
            },
        )
        db.commit()
        db.refresh(dataset)
        return dataset, inserted, skipped, truncated_rows

    except ImportError as exc:
        db.rollback()
        ds = get_dataset(db, dataset.id)
        if ds:
            # Restore previous status on validation-style failures after processing began
            if previous_status == DatasetStatus.PENDING and ds.conversation_count == 0:
                ds.status = DatasetStatus.PENDING
            else:
                ds.status = DatasetStatus.FAILED
            ds.error_message = exc.message
            write_log(
                db,
                level="error",
                event="import_failed",
                message=exc.message,
                context={"dataset_id": str(dataset.id), "errors": exc.errors},
            )
            db.commit()
        raise
    except IntegrityError as exc:
        db.rollback()
        ds = get_dataset(db, dataset.id)
        if ds:
            ds.status = DatasetStatus.FAILED
            ds.error_message = "Import conflict (duplicate external_id)"
            write_log(
                db,
                level="error",
                event="import_failed",
                message=ds.error_message,
                context={"dataset_id": str(dataset.id)},
            )
            db.commit()
        raise ImportError(
            "Import conflict (duplicate external_id)",
            status_code=409,
            errors=[{"field": "external_id", "issue": "conflict"}],
        ) from exc
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        ds = get_dataset(db, dataset.id)
        if ds:
            ds.status = DatasetStatus.FAILED
            ds.error_message = "Import failed due to an internal error"
            write_log(
                db,
                level="error",
                event="import_failed",
                message=str(exc),
                context={"dataset_id": str(dataset.id)},
            )
            db.commit()
        raise
