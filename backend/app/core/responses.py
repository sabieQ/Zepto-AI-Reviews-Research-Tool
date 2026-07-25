from typing import Any

from fastapi.responses import JSONResponse


def success_response(
    data: Any = None,
    message: str = "",
    status_code: int = 200,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "message": message,
            "data": data if data is not None else {},
        },
    )


def error_response(
    message: str,
    errors: list[Any] | None = None,
    status_code: int = 400,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "message": message,
            "errors": errors or [],
        },
    )
