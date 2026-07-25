from __future__ import annotations

import re
from typing import Any

from app.models import Report


class ExportError(Exception):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if v is not None and str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def sanitize_filename(title: str | None, report_id: str) -> str:
    base = (title or "report").strip() or "report"
    base = re.sub(r"[^\w\s\-]+", "", base, flags=re.UNICODE)
    base = re.sub(r"\s+", "-", base).strip("-")[:80] or "report"
    return f"{base}-{report_id[:8]}"


def report_to_markdown(report: Report) -> str:
    lines: list[str] = [
        f"# {report.title or 'Research report'}",
        "",
        f"**Status:** {report.status}",
        f"**Question:** {report.question_text}",
        f"**Confidence:** {report.confidence or 'n/a'}",
    ]
    if report.confidence_rationale:
        lines.append(f"**Confidence rationale:** {report.confidence_rationale}")
    if report.model_provider or report.model_name:
        lines.append(
            f"**Model:** {report.model_provider or 'n/a'} / {report.model_name or 'n/a'}"
        )
    lines.append("")

    if report.status == "failed":
        lines.extend(
            [
                "## Error",
                "",
                report.error_message or "Research failed",
                "",
            ]
        )
        return "\n".join(lines).strip() + "\n"

    lines.extend(["## Executive summary", "", report.executive_summary or "_None_", ""])

    for heading, key in (
        ("Key findings", report.key_findings),
        ("Root causes", report.root_causes),
        ("Themes", report.themes),
        ("Opportunities", report.opportunities),
    ):
        items = _as_list(key)
        lines.append(f"## {heading}")
        lines.append("")
        if items:
            lines.extend([f"- {item}" for item in items])
        else:
            lines.append("_None_")
        lines.append("")

    lines.extend(["## Evidence", ""])
    evidence = report.evidence if isinstance(report.evidence, list) else []
    if not evidence:
        lines.append("_No evidence citations_")
    else:
        for i, item in enumerate(evidence, start=1):
            if not isinstance(item, dict):
                continue
            quote = str(item.get("quote") or "").strip()
            cid = item.get("conversation_id")
            source = item.get("source")
            url = item.get("url")
            lines.append(f"### Evidence {i}")
            lines.append("")
            lines.append(f"> {quote}" if quote else "> _(empty quote)_")
            lines.append("")
            meta = [f"conversation_id: `{cid}`"]
            if source:
                meta.append(f"source: {source}")
            if url:
                meta.append(f"url: {url}")
            lines.append(" · ".join(meta))
            lines.append("")

    return "\n".join(lines).strip() + "\n"


def export_report(report: Report, *, format: str) -> tuple[bytes, str, str]:
    """Return (content_bytes, media_type, filename)."""
    fmt = (format or "md").strip().lower()
    if report.status != "completed":
        raise ExportError(
            f"Only completed reports can be exported (status={report.status})",
            status_code=400,
        )

    stem = sanitize_filename(report.title, str(report.id))

    if fmt in {"md", "markdown"}:
        text = report_to_markdown(report)
        return text.encode("utf-8"), "text/markdown; charset=utf-8", f"{stem}.md"

    if fmt == "pdf":
        raise ExportError("PDF export is not available in MVP", status_code=501)

    if fmt == "docx":
        raise ExportError("DOCX export is not available in MVP", status_code=501)

    raise ExportError(
        f"Unsupported export format '{format}'. Use md (pdf/docx not available).",
        status_code=400,
    )
