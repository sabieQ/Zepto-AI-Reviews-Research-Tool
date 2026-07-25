import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import LogEntry

logger = logging.getLogger("zepto")


def write_log(
    db: Session,
    *,
    level: str,
    event: str,
    message: str,
    context: dict[str, Any] | None = None,
) -> None:
    safe_context = context or {}
    entry = LogEntry(
        id=uuid.uuid4(),
        level=level,
        event=event,
        message=message,
        context=safe_context,
    )
    db.add(entry)
    log_fn = logger.error if level == "error" else logger.warning if level == "warn" else logger.info
    log_fn("%s | %s | %s", event, message, safe_context)
