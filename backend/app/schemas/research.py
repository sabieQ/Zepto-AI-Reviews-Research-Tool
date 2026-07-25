from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.constants import MAX_TOP_K
from app.services.research import MAX_QUESTION_LEN, MIN_QUESTION_LEN


class ResearchRequest(BaseModel):
    dataset_id: UUID
    question: str = Field(..., min_length=1, max_length=MAX_QUESTION_LEN)
    research_question_id: UUID | None = None
    top_k: int | None = Field(default=None, ge=1, le=MAX_TOP_K)

    @field_validator("question")
    @classmethod
    def question_trimmed(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("question must not be empty")
        if len(cleaned) < MIN_QUESTION_LEN:
            raise ValueError(f"question must be at least {MIN_QUESTION_LEN} characters")
        return cleaned


class ResearchQuestionOut(BaseModel):
    id: UUID
    slug: str
    category: str | None
    title: str
    description: str | None
    prompt_file: str | None
    is_active: bool
    sort_order: int

    model_config = {"from_attributes": True}


class ReportOut(BaseModel):
    id: UUID
    dataset_id: UUID
    research_question_id: UUID | None
    question_text: str
    title: str | None
    status: str
    executive_summary: str | None
    key_findings: Any
    root_causes: Any
    themes: Any
    opportunities: Any
    confidence: str | None
    confidence_rationale: str | None
    evidence: Any
    model_provider: str | None
    model_name: str | None
    error_message: str | None
    created_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class SettingsUpdate(BaseModel):
    ai_provider: str | None = None
    ai_model: str | None = None
    embedding_model: str | None = None
    embedding_dimensions: int | None = Field(default=None, ge=8, le=4096)
    top_k: int | None = Field(default=None, ge=1, le=MAX_TOP_K)
