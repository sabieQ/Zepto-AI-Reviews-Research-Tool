from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Report
from app.services.logging_service import write_log

# Reports left in pending/running longer than this are marked failed (crash recovery)
STALE_RESEARCH_MINUTES = 30


def fail_stale_reports(db: Session, *, older_than_minutes: int = STALE_RESEARCH_MINUTES) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)
    rows = list(
        db.scalars(
            select(Report).where(
                Report.status.in_(("pending", "running")),
                Report.created_at < cutoff,
            )
        ).all()
    )
    for report in rows:
        report.status = "failed"
        report.error_message = (
            report.error_message
            or "Research timed out or was interrupted; marked failed on recovery"
        )
        report.completed_at = datetime.now(timezone.utc)
    if rows:
        write_log(
            db,
            level="warn",
            event="research_stale_recovery",
            message=f"Marked {len(rows)} stale research report(s) as failed",
            context={"count": len(rows), "cutoff_minutes": older_than_minutes},
        )
        db.commit()
    return len(rows)
