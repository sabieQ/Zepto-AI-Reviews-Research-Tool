from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.constants import BLOCKED_IMPORT_STATUSES, DatasetStatus
from app.models import CollectorRun, Dataset
from app.services.collectors.app_store import fetch_app_store_reviews
from app.services.collectors.play import iter_play_review_batches
from app.services.collectors.runner import CollectorError, get_or_create_master_dataset
from app.services.import_service import ingest_conversation_rows
from app.services.indexing import IndexingError, index_dataset
from app.services.logging_service import write_log

DEFAULT_BULK_TARGET = 100_000
# Play strategies to maximize unique reviews before platform stops
PLAY_SORTS = ("newest", "most_relevant", "rating")
INGEST_CHUNK = 400
# Per sort/country fetch ceiling (platform usually stops earlier)
PLAY_ASK_CAP = 120_000


def run_bulk_backfill(
    db: Session,
    *,
    dataset_id: UUID | None = None,
    target: int = DEFAULT_BULK_TARGET,
    country: str | None = None,
    lang: str | None = None,
    include_app_store: bool = True,
    auto_index: bool = False,
    play_countries: list[str] | None = None,
    on_progress: Any | None = None,
) -> CollectorRun:
    """One-shot Play-first backfill aiming for `target` unique conversations in the dataset.

    Stop condition uses dataset conversation_count (so restarts continue toward the goal).
    Ingests in chunks (does not hold 100k rows in memory). App Store is best-effort.
    Defaults auto_index=False — indexing tens of thousands is a separate expensive step.
    """
    settings = get_settings()
    target = max(1, min(int(target), 200_000))
    country_code = (country or settings.collector_country).strip().lower() or "in"
    lang_code = (lang or settings.collector_lang).strip().lower() or "en"
    countries = play_countries or [country_code, "us"]
    ordered: list[str] = []
    for c in countries:
        c = c.strip().lower()
        if c and c not in ordered:
            ordered.append(c)
    countries = ordered

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

    sources = ["google_play"] + (["app_store"] if include_app_store else [])
    run = CollectorRun(
        id=uuid.uuid4(),
        dataset_id=dataset.id,
        status="running",
        sources=sources,
        inserted=0,
        skipped=0,
        context={
            "mode": "bulk",
            "target": target,
            "country": country_code,
            "lang": lang_code,
            "play_countries": countries,
            "auto_index": auto_index,
            "by_source": {},
            "checkpoints": [],
        },
    )
    db.add(run)
    dataset.status = DatasetStatus.PROCESSING
    dataset.error_message = None
    db.commit()
    db.refresh(run)

    write_log(
        db,
        level="info",
        event="collector_bulk_start",
        message="Bulk backfill started",
        context={"run_id": str(run.id), "target": target, "dataset_id": str(dataset.id)},
    )
    db.commit()

    total_inserted = 0
    total_skipped = 0
    play_fetched = 0
    warnings: list[str] = []
    by_source: dict[str, Any] = {}
    checkpoints: list[dict[str, Any]] = []

    def _conversation_count() -> int:
        ds = db.get(Dataset, dataset.id)
        return int(ds.conversation_count) if ds else 0

    def _target_met() -> bool:
        return _conversation_count() >= target

    def _checkpoint(note: str) -> None:
        entry = {
            "at": datetime.now(timezone.utc).isoformat(),
            "note": note,
            "inserted": total_inserted,
            "skipped": total_skipped,
            "play_fetched": play_fetched,
            "conversation_count": _conversation_count(),
        }
        checkpoints.append(entry)
        run.inserted = total_inserted
        run.skipped = total_skipped
        run.context = {
            **(run.context or {}),
            "by_source": by_source,
            "warnings": warnings,
            "checkpoints": checkpoints[-50:],
            "play_fetched": play_fetched,
            "conversation_count": entry["conversation_count"],
        }
        db.commit()
        if on_progress:
            on_progress(entry)

    try:
        buffer: list[dict[str, Any]] = []

        def flush_buffer() -> None:
            nonlocal total_inserted, total_skipped, buffer
            if not buffer:
                return
            # Re-load dataset to avoid detached state after commits
            ds = db.get(Dataset, dataset.id)
            assert ds is not None
            ins, skip, _trunc = ingest_conversation_rows(
                db, dataset=ds, rows=buffer, allow_empty_insert=True
            )
            total_inserted += ins
            total_skipped += skip
            buffer = []
            db.commit()

        # --- Play: multi-sort x multi-country until dataset reaches target ---
        for ctry in countries:
            if _target_met():
                break
            for sort_name in PLAY_SORTS:
                if _target_met():
                    break
                remaining = max(0, target - _conversation_count())
                # Ask for more than remaining to account for duplicates across sorts
                ask = min(remaining + 5_000, PLAY_ASK_CAP)
                try:
                    for batch in iter_play_review_batches(
                        app_id=settings.collector_play_app_id,
                        country=ctry,
                        lang=lang_code,
                        limit=ask,
                        sort_name=sort_name,
                        batch_size=100,
                        sleep_s=0.45,
                    ):
                        play_fetched += len(batch)
                        buffer.extend(batch)
                        if len(buffer) >= INGEST_CHUNK:
                            flush_buffer()
                            _checkpoint(f"play {ctry}/{sort_name}")
                        if _target_met():
                            break
                except Exception as exc:  # noqa: BLE001
                    warnings.append(f"play {ctry}/{sort_name}: {exc}")
                flush_buffer()
                _checkpoint(f"play done {ctry}/{sort_name}")

        by_source["google_play"] = {
            "fetched": play_fetched,
            "ok": play_fetched > 0,
            "inserted_estimate": total_inserted,
        }

        # --- App Store best-effort (small; does not drive target) ---
        if include_app_store and not _target_met():
            ios_rows, ios_warn = fetch_app_store_reviews(
                app_id=settings.collector_ios_app_id,
                country=country_code,
                limit=500,
            )
            if ios_warn:
                warnings.append(f"app_store: {ios_warn}")
            by_source["app_store"] = {
                "fetched": len(ios_rows),
                "ok": bool(ios_rows),
                "error": ios_warn,
            }
            if ios_rows:
                buffer.extend(ios_rows)
                flush_buffer()
                _checkpoint("app_store")
        elif include_app_store:
            by_source["app_store"] = {"fetched": 0, "ok": False, "skipped": "target already met"}

        flush_buffer()

        ds = db.get(Dataset, dataset.id)
        assert ds is not None
        index_info: dict[str, Any] = {"ran": False}
        if total_inserted == 0 and total_skipped == 0 and play_fetched == 0:
            run.status = "failed"
            run.error_message = "; ".join(warnings) or "Bulk backfill fetched 0 reviews"
            ds.status = DatasetStatus.FAILED
            ds.error_message = run.error_message
        else:
            run.status = "completed"
            final_count = _conversation_count()
            if final_count < target:
                warnings.append(
                    f"Reached platform ceiling before target "
                    f"(dataset={final_count}, this_run_inserted={total_inserted}, "
                    f"target={target})"
                )
            run.error_message = "; ".join(warnings) if warnings else None
            if auto_index and ds.conversation_count > 0:
                ds.status = DatasetStatus.IMPORTED
                db.commit()
                db.refresh(ds)
                try:
                    index_dataset(db, ds)
                    index_info = {"ran": True, "status": "ready"}
                except IndexingError as exc:
                    warnings.append(f"index: {exc.message}")
                    index_info = {"ran": True, "status": "failed", "error": exc.message}
                except Exception as exc:  # noqa: BLE001
                    warnings.append(f"index: {exc}")
                    index_info = {"ran": True, "status": "failed", "error": str(exc)}
            else:
                ds.status = DatasetStatus.IMPORTED
                ds.error_message = None
                if not auto_index:
                    warnings.append(
                        "auto_index=false — run Index on the dataset when ready "
                        "(large corpora take time/AI quota)"
                    )

        run.inserted = total_inserted
        run.skipped = total_skipped
        run.context = {
            "mode": "bulk",
            "target": target,
            "country": country_code,
            "lang": lang_code,
            "play_countries": countries,
            "auto_index": auto_index,
            "by_source": by_source,
            "warnings": warnings,
            "checkpoints": checkpoints[-50:],
            "play_fetched": play_fetched,
            "index": index_info,
            "conversation_count": _conversation_count(),
            "target_met": _target_met(),
        }
        run.completed_at = datetime.now(timezone.utc)
        write_log(
            db,
            level="info" if run.status == "completed" else "error",
            event="collector_bulk_complete",
            message=f"Bulk backfill {run.status}",
            context={
                "run_id": str(run.id),
                "inserted": total_inserted,
                "skipped": total_skipped,
                "play_fetched": play_fetched,
                "target": target,
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
            r.inserted = total_inserted
            r.skipped = total_skipped
            r.completed_at = datetime.now(timezone.utc)
            r.context = {
                **(r.context or {}),
                "by_source": by_source,
                "warnings": warnings,
                "play_fetched": play_fetched,
            }
        if ds and ds.status == DatasetStatus.PROCESSING:
            ds.status = DatasetStatus.FAILED if total_inserted == 0 else DatasetStatus.IMPORTED
            ds.error_message = f"Bulk backfill interrupted: {exc}"
        write_log(
            db,
            level="error",
            event="collector_bulk_failed",
            message=str(exc),
            context={"run_id": str(run.id)},
        )
        db.commit()
        if r:
            db.refresh(r)
            return r
        raise
