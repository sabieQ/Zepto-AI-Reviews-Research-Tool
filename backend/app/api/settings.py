from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.responses import error_response, success_response
from app.schemas.research import SettingsUpdate
from app.services.settings_service import get_effective_settings, update_settings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def get_settings_endpoint(db: Session = Depends(get_db)):
    data = get_effective_settings(db)
    # Never expose secrets
    data.pop("ai_api_key", None)
    return success_response(data=data, message="Settings retrieved")


@router.put("")
def put_settings(payload: SettingsUpdate, db: Session = Depends(get_db)):
    try:
        data = update_settings(db, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        return error_response(message=str(exc), status_code=422)
    data.pop("ai_api_key", None)
    return success_response(data=data, message="Settings updated")
