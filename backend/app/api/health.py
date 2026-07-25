from fastapi import APIRouter

from app.core.database import check_database
from app.core.responses import error_response, success_response

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> object:
    ok, detail = check_database()
    payload = {
        "status": "ok" if ok else "degraded",
        "database": detail,
        "service": "zepto-research-api",
    }
    if not ok:
        return error_response(
            message="Database unreachable",
            errors=[payload],
            status_code=503,
        )
    return success_response(data=payload, message="Healthy")
