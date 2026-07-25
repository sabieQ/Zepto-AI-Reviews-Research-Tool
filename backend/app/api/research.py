from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.responses import error_response, success_response
from app.schemas.research import ReportOut, ResearchQuestionOut, ResearchRequest
from app.services import research as research_service
from app.services.export import ExportError, export_report
from app.services.research import ResearchError

router = APIRouter(tags=["research"])


@router.get("/research-questions")
def get_research_questions(db: Session = Depends(get_db)):
    items = research_service.list_research_questions(db)
    data = [ResearchQuestionOut.model_validate(i).model_dump(mode="json") for i in items]
    return success_response(data=data, message="Research question presets retrieved")


@router.post("/research")
def post_research(payload: ResearchRequest, db: Session = Depends(get_db)):
    try:
        report = research_service.run_research(
            db,
            dataset_id=payload.dataset_id,
            question=payload.question,
            research_question_id=payload.research_question_id,
            top_k=payload.top_k,
        )
    except ResearchError as exc:
        return error_response(
            message=exc.message,
            errors=exc.errors,
            status_code=exc.status_code,
        )

    body = ReportOut.model_validate(report).model_dump(mode="json")
    if report.status == "failed":
        return error_response(
            message=report.error_message or "Research failed",
            errors=[{"code": "research_failed", "report": body}],
            status_code=400,
        )
    return success_response(data=body, message="Research completed")


@router.get("/reports")
def get_reports(dataset_id: UUID | None = None, db: Session = Depends(get_db)):
    items = research_service.list_reports(db, dataset_id=dataset_id)
    data = [ReportOut.model_validate(i).model_dump(mode="json") for i in items]
    return success_response(data=data, message="Reports retrieved")


@router.get("/reports/{report_id}")
def get_report(report_id: UUID, db: Session = Depends(get_db)):
    report = research_service.get_report(db, report_id)
    if not report:
        return error_response(message="Report not found", status_code=404)
    return success_response(
        data=ReportOut.model_validate(report).model_dump(mode="json"),
        message="Report retrieved",
    )


@router.get("/reports/{report_id}/export")
def export_report_endpoint(
    report_id: UUID,
    format: str = "md",
    db: Session = Depends(get_db),
):
    report = research_service.get_report(db, report_id)
    if not report:
        return error_response(message="Report not found", status_code=404)
    try:
        content, media_type, filename = export_report(report, format=format)
    except ExportError as exc:
        return error_response(message=exc.message, status_code=exc.status_code)
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.delete("/reports/{report_id}")
def remove_report(report_id: UUID, db: Session = Depends(get_db)):
    report = research_service.get_report(db, report_id)
    if not report:
        return error_response(message="Report not found", status_code=404)
    research_service.delete_report(db, report)
    return success_response(data={"id": str(report_id)}, message="Report deleted")
