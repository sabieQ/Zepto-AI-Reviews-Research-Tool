from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.responses import error_response, success_response
from app.schemas.datasets import DatasetCreate, DatasetDetailOut, DatasetOut
from app.services import import_service

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("")
def get_datasets(db: Session = Depends(get_db)):
    items = import_service.list_datasets(db)
    data = [DatasetOut.model_validate(item).model_dump(mode="json") for item in items]
    return success_response(data=data, message="Datasets retrieved")


@router.post("")
def post_dataset(payload: DatasetCreate, db: Session = Depends(get_db)):
    dataset = import_service.create_dataset(db, payload)
    return success_response(
        data=DatasetOut.model_validate(dataset).model_dump(mode="json"),
        message="Dataset created",
        status_code=201,
    )


@router.get("/{dataset_id}")
def get_dataset(dataset_id: UUID, db: Session = Depends(get_db)):
    dataset = import_service.get_dataset(db, dataset_id)
    if not dataset:
        return error_response(message="Dataset not found", status_code=404)
    conversations = import_service.list_conversations(db, dataset_id)
    detail = DatasetDetailOut(
        **DatasetOut.model_validate(dataset).model_dump(),
        conversations=conversations,
    )
    return success_response(data=detail.model_dump(mode="json"), message="Dataset retrieved")


@router.delete("/{dataset_id}")
def remove_dataset(dataset_id: UUID, db: Session = Depends(get_db)):
    dataset = import_service.get_dataset(db, dataset_id)
    if not dataset:
        return error_response(message="Dataset not found", status_code=404)
    import_service.delete_dataset(db, dataset)
    return success_response(data={"id": str(dataset_id)}, message="Dataset deleted")
