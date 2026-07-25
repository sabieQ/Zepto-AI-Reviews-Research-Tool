from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.responses import error_response, success_response
from app.schemas.datasets import DatasetOut
from app.schemas.indexing import IndexResultOut, SearchRequest
from app.services import import_service
from app.services.indexing import IndexingError, index_dataset, retrieve_similar

router = APIRouter(tags=["indexing"])


@router.post("/datasets/{dataset_id}/reindex")
def reindex_dataset(dataset_id: UUID, db: Session = Depends(get_db)):
    dataset = import_service.get_dataset(db, dataset_id)
    if not dataset:
        return error_response(message="Dataset not found", status_code=404)
    try:
        dataset = index_dataset(db, dataset)
    except IndexingError as exc:
        return error_response(
            message=exc.message,
            errors=exc.errors,
            status_code=exc.status_code,
        )
    result = IndexResultOut(
        dataset_id=dataset.id,
        status=dataset.status,
        conversation_count=dataset.conversation_count,
        message="Dataset indexed and ready for research",
    )
    return success_response(
        data={
            **result.model_dump(mode="json"),
            "dataset": DatasetOut.model_validate(dataset).model_dump(mode="json"),
        },
        message=result.message,
    )


@router.post("/search")
def search_chunks(payload: SearchRequest, db: Session = Depends(get_db)):
    try:
        results = retrieve_similar(
            db,
            dataset_id=payload.dataset_id,
            query=payload.query,
            top_k=payload.top_k,
        )
    except IndexingError as exc:
        return error_response(
            message=exc.message,
            errors=exc.errors,
            status_code=exc.status_code,
        )
    return success_response(
        data={"results": results, "count": len(results)},
        message="Search completed",
    )
