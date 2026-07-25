import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import api_router
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.logging import configure_logging, log_event
from app.core.responses import error_response
from app.services.recovery import fail_stale_reports
from app.services.seed import seed_research_questions

logger = logging.getLogger("zepto")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    log_event(logger, "system_startup", "Zepto API starting", frontend_url=settings.frontend_url)

    db = SessionLocal()
    try:
        created = seed_research_questions(db)
        stale = fail_stale_reports(db)
        log_event(
            logger,
            "startup_seed",
            "Startup seed and recovery complete",
            presets_created=created,
            stale_reports_failed=stale,
        )
    except Exception as exc:  # noqa: BLE001 — startup must not crash the app hard on seed
        logger.exception("Startup seed/recovery failed: %s", exc)
    finally:
        db.close()

    yield
    log_event(logger, "system_shutdown", "Zepto API shutting down")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Zepto AI Product Research Assistant",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request: Request, exc: RequestValidationError):
        safe_errors: list[Any] = []
        for err in exc.errors():
            item = dict(err)
            ctx = item.get("ctx")
            if isinstance(ctx, dict):
                item["ctx"] = {
                    key: (str(value) if not isinstance(value, (str, int, float, bool, type(None))) else value)
                    for key, value in ctx.items()
                }
            safe_errors.append(item)
        return error_response(
            message="Validation failed",
            errors=safe_errors,
            status_code=422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_request: Request, exc: StarletteHTTPException):
        detail = exc.detail
        message = detail if isinstance(detail, str) else "Request failed"
        errors = detail if isinstance(detail, list) else ([detail] if detail is not None else [])
        return error_response(message=message, errors=errors, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception):
        logger.exception("Unhandled exception: %s", exc)
        return error_response(
            message="Internal server error",
            errors=[],
            status_code=500,
        )

    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
