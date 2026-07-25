from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.constants import (
    BLOCKED_IMPORT_STATUSES,
    DatasetStatus,
    MASTER_DATASET_SOURCE,
    MAX_COLLECTOR_PER_STORE,
)
from app.models import CollectorRun, Dataset
from app.services.collectors.app_store import fetch_app_store_reviews
from app.services.collectors.play import fetch_play_reviews
from app.services.import_service import ingest_conversation_rows
from app.services.indexing import IndexingError, index_dataset
from app.services.logging_service import write_log

ALLOWED_COLLECTOR_SOURCES = ("google_play", "app_store")


class CollectorError(Exception):
    def __init__(self, message: str, *, status_code: int = 400, errors: list[Any] | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.errors = errors or []


def get_or_create_master_dataset(db: Session, name: str | None = None) -> Dataset:
    settings = get_settings()
    master_name = (name or settings.collector_master_dataset_name).strip()
    existing = db.scalar(select(Dataset).where(Dataset.name == master_name).limit(1))
    if existing:
        return existing
    dataset = Dataset(
        id=uuid.uuid4(),
        name=master_name,
        source=MASTER_DATASET_SOURCE,
        description="Auto-collected public store reviews (Phase 7b)",
        status=DatasetStatus.PENDING,
        conversation_count=0,
    )
    db.add(dataset)
    write_log(
        db,
        level="info",
        event="collector_master_dataset_create",
        message="Created master corpus dataset",
        context={"dataset_id": str(dataset.id), "name": master_name},
    )
    db.commit()
    db.refresh(dataset)
    return dataset


def list_collector_runs(db: Session, *, limit: int = 20) -> list[CollectorRun]:
    limit = max(1, min(limit, 100))
    return list(
        db.scalars(
            select(CollectorRun).order_by(CollectorRun.created_at.desc()).limit(limit)
        ).all()
    )


def run_collectors(
    db: Session,
    *,
    dataset_id: UUID | None = None,
    sources: list[str] | None = None,
    limit: int | None = None,
    country: str | None = None,
    lang: str | None = None,
    auto_index: bool = True,
) -> CollectorRun:
    settings = get_settings()
    resolved_sources = sources or list(ALLOWED_COLLECTOR_SOURCES)
    for src in resolved_sources:
        if src not in ALLOWED_COLLECTOR_SOURCES:
            raise CollectorError(
                f"Unsupported collector source: {src}",
                status_code=422,
                errors=[{"field": "sources", "value": src}],
            )
    if not resolved_sources:
        raise CollectorError("At least one source is required", status_code=422)

    per_store = limit if limit is not None else settings.collector_max_per_store
    per_store = max(1, min(int(per_store), MAX_COLLECTOR_PER_STORE))
    country_code = (country or settings.collector_country).strip().lower() or "in"
    lang_code = (lang or settings.collector_lang).strip().lower() or "en"

    if dataset_id is not None:
        dataset = db.get(Dataset, dataset_id)
        if not dataset:
            raise CollectorError("Dataset not found", status_code=404)
    else:
        dataset = get_or_create_master_dataset(db)

    if dataset.status in BLOCKED_IMPORT_STATUSES:
        raise CollectorError(
            "Dataset is busy (import/index in progress). Try again shortly.",
            status_code=409,
            errors=[{"field": "status", "value": dataset.status}],
        )

    run = CollectorRun(
        id=uuid.uuid4(),
        dataset_id=dataset.id,
        status="running",
        sources=list(resolved_sources),
        inserted=0,
        skipped=0,
        context={
            "country": country_code,
            "lang": lang_code,
            "limit_per_store": per_store,
            "auto_index": auto_index,
            "by_source": {},
        },
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    write_log(
        db,
        level="info",
        event="collector_start",
        message="Collector run started",
        context={"run_id": str(run.id), "dataset_id": str(dataset.id), "sources": resolved_sources},
    )
    db.commit()

    all_rows: list[dict[str, Any]] = []
    by_source: dict[str, Any] = {}
    warnings: list[str] = []

    try:
        if "google_play" in resolved_sources:
            try:
                play_rows = fetch_play_reviews(
                    app_id=settings.collector_play_app_id,
                    country=country_code,
                    lang=lang_code,
                    limit=per_store,
                )
                by_source["google_play"] = {"fetched": len(play_rows), "ok": True}
                all_rows.extend(play_rows)
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)
                warnings.append(f"google_play: {msg}")
                by_source["google_play"] = {"fetched": 0, "ok": False, "error": msg}

        if "app_store" in resolved_sources:
            ios_rows, ios_warn = fetch_app_store_reviews(
                app_id=settings.collector_ios_app_id,
                country=country_code,
                limit=per_store,
            )
            if ios_warn:
                warnings.append(f"app_store: {ios_warn}")
            by_source["app_store"] = {
                "fetched": len(ios_rows),
                "ok": bool(ios_rows),
                "error": ios_warn,
            }
            all_rows.extend(ios_rows)

        if not all_rows:
            run.status = "failed"
            run.error_message = "; ".join(warnings) or "No reviews fetched from any source"
            run.context = {**(run.context or {}), "by_source": by_source, "warnings": warnings}
            run.completed_at = datetime.now(timezone.utc)
            write_log(
                db,
                level="error",
                event="collector_failed",
                message=run.error_message,
                context={"run_id": str(run.id), "by_source": by_source},
            )
            db.commit()
            db.refresh(run)
            return run

        dataset.status = DatasetStatus.PROCESSING
        dataset.error_message = None
        db.commit()

        inserted, skipped, truncated = ingest_conversation_rows(
            db,
            dataset=dataset,
            rows=all_rows,
            allow_empty_insert=True,
        )

        run.inserted = inserted
        run.skipped = skipped
        index_info: dict[str, Any] = {"ran": False}

        if inserted == 0 and skipped > 0:
            # All duplicates — keep prior ready status if possible
            if dataset.status == DatasetStatus.PROCESSING:
                dataset.status = (
                    DatasetStatus.READY
                    if dataset.conversation_count > 0
                    else DatasetStatus.IMPORTED
                )
            dataset.error_message = None
        elif auto_index and (inserted > 0 or dataset.conversation_count > 0):
            dataset.status = DatasetStatus.IMPORTED
            db.commit()
            db.refresh(dataset)
            try:
                index_dataset(db, dataset)
                index_info = {"ran": True, "status": "ready"}
            except IndexingError as exc:
                warnings.append(f"index: {exc.message}")
                index_info = {"ran": True, "status": "failed", "error": exc.message}
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"index: {exc}")
                index_info = {"ran": True, "status": "failed", "error": str(exc)}
        else:
            dataset.status = DatasetStatus.IMPORTED
            dataset.error_message = None

        run.status = "completed"
        run.error_message = "; ".join(warnings) if warnings else None
        run.context = {
            "country": country_code,
            "lang": lang_code,
            "limit_per_store": per_store,
            "auto_index": auto_index,
            "by_source": by_source,
            "warnings": warnings,
            "truncated_rows": truncated,
            "index": index_info,
            "fetched_total": len(all_rows),
        }
        run.completed_at = datetime.now(timezone.utc)
        write_log(
            db,
            level="info",
            event="collector_complete",
            message="Collector run completed",
            context={
                "run_id": str(run.id),
                "inserted": inserted,
                "skipped": skipped,
                "by_source": by_source,
            },
        )
        db.commit()
        db.refresh(run)
        return run

    except Exception as exc:  # noqa: BLE001
        db.rollback()
        r = db.get(CollectorRun, run.id)
        ds = db.get(Dataset, dataset.id)
        if r:
            r.status = "failed"
            r.error_message = str(exc)
            r.completed_at = datetime.now(timezone.utc)
            r.context = {**(r.context or {}), "by_source": by_source, "warnings": warnings}
        if ds and ds.status == DatasetStatus.PROCESSING:
            ds.status = DatasetStatus.FAILED
            ds.error_message = f"Collector failed: {exc}"
        write_log(
            db,
            level="error",
            event="collector_failed",
            message=str(exc),
            context={"run_id": str(run.id)},
        )
        db.commit()
        if r:
            db.refresh(r)
            return r
        raise
