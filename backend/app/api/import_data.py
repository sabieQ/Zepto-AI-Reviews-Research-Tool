from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.responses import error_response, success_response
from app.schemas.datasets import DatasetOut, ImportResultOut
from app.services import import_service
from app.services.import_service import ImportError
from app.services.indexing import IndexingError, index_dataset

router = APIRouter(tags=["import"])


@router.post("/import")
async def import_file(
    dataset_id: UUID | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    auto_index: bool = Form(default=True),
    db: Session = Depends(get_db),
):
    if dataset_id is None:
        return error_response(
            message="dataset_id is required",
            errors=[{"field": "dataset_id", "issue": "required"}],
            status_code=422,
        )
    if file is None:
        return error_response(
            message="file is required",
            errors=[{"field": "file", "issue": "required"}],
            status_code=400,
        )

    dataset = import_service.get_dataset(db, dataset_id)
    if not dataset:
        return error_response(message="Dataset not found", status_code=404)

    raw = await file.read()
    try:
        dataset, inserted, skipped, truncated = import_service.import_conversations(
            db,
            dataset=dataset,
            filename=file.filename,
            raw=raw,
        )
    except ImportError as exc:
        return error_response(
            message=exc.message,
            errors=exc.errors,
            status_code=exc.status_code,
        )

    index_message = ""
    if auto_index and inserted > 0:
        # Refresh dataset instance after import commit
        dataset = import_service.get_dataset(db, dataset_id) or dataset
        try:
            dataset = index_dataset(db, dataset)
            index_message = " Indexed and marked ready."
        except IndexingError as exc:
            index_message = f" Import OK, but indexing failed: {exc.message}"
            dataset = import_service.get_dataset(db, dataset_id) or dataset

    message = f"Imported {inserted} conversations ({skipped} skipped).{index_message}"
    result = ImportResultOut(
        dataset=DatasetOut.model_validate(dataset),
        inserted=inserted,
        skipped=skipped,
        truncated_rows=truncated,
        message=message,
    )
    return success_response(data=result.model_dump(mode="json"), message=message)
