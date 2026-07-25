from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.responses import error_response, success_response
from app.schemas.collectors import CollectorBulkRequest, CollectorRunOut, CollectorRunRequest
from app.services.collectors import (
    CollectorError,
    list_collector_runs,
    run_bulk_backfill,
    run_collectors,
)
from app.services.import_service import get_dataset

router = APIRouter(prefix="/collectors", tags=["collectors"])


def _enrich(run, db: Session) -> dict:
    body = CollectorRunOut.model_validate(run).model_dump(mode="json")
    dataset = get_dataset(db, run.dataset_id)
    body["dataset"] = (
        {
            "id": str(dataset.id),
            "name": dataset.name,
            "status": dataset.status,
            "conversation_count": dataset.conversation_count,
        }
        if dataset
        else None
    )
    return body


@router.post("/run")
def post_collectors_run(payload: CollectorRunRequest, db: Session = Depends(get_db)):
    """Small incremental refresh (default ≤100 reviews per store)."""
    try:
        run = run_collectors(
            db,
            dataset_id=payload.dataset_id,
            sources=list(payload.sources) if payload.sources else None,
            limit=payload.limit,
            country=payload.country,
            lang=payload.lang,
            auto_index=payload.auto_index,
        )
    except CollectorError as exc:
        return error_response(
            message=exc.message,
            errors=exc.errors,
            status_code=exc.status_code,
        )

    body = _enrich(run, db)
    if run.status == "failed":
        return error_response(
            message=run.error_message or "Collector run failed",
            errors=[{"code": "collector_failed", "run": body}],
            status_code=400,
        )
    return success_response(data=body, message="Collector run completed")


@router.post("/bulk")
def post_collectors_bulk(payload: CollectorBulkRequest, db: Session = Depends(get_db)):
    """One-shot Play-first backfill (can take a long time — prefer CLI for 100k)."""
    try:
        run = run_bulk_backfill(
            db,
            dataset_id=payload.dataset_id,
            target=payload.target,
            country=payload.country,
            lang=payload.lang,
            include_app_store=payload.include_app_store,
            auto_index=payload.auto_index,
            play_countries=payload.play_countries,
        )
    except CollectorError as exc:
        return error_response(
            message=exc.message,
            errors=exc.errors,
            status_code=exc.status_code,
        )

    body = _enrich(run, db)
    if run.status == "failed":
        return error_response(
            message=run.error_message or "Bulk backfill failed",
            errors=[{"code": "collector_bulk_failed", "run": body}],
            status_code=400,
        )
    return success_response(data=body, message="Bulk backfill completed")


@router.get("/runs")
def get_collector_runs(limit: int = 20, db: Session = Depends(get_db)):
    items = list_collector_runs(db, limit=limit)
    data = [CollectorRunOut.model_validate(i).model_dump(mode="json") for i in items]
    return success_response(data=data, message="Collector runs retrieved")
