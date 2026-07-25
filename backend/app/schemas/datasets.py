from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.constants import ALLOWED_SOURCES, MAX_DATASET_NAME_LENGTH


class DatasetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=MAX_DATASET_NAME_LENGTH)
    source: str
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name must not be empty")
        return cleaned

    @field_validator("source")
    @classmethod
    def source_allowed(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned not in ALLOWED_SOURCES:
            raise ValueError(f"source must be one of: {', '.join(ALLOWED_SOURCES)}")
        return cleaned

    @field_validator("description")
    @classmethod
    def description_trim(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ConversationOut(BaseModel):
    id: UUID
    external_id: str | None
    source: str | None
    author: str | None
    content: str
    rating: int | None
    posted_at: datetime | None
    url: str | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class DatasetOut(BaseModel):
    id: UUID
    name: str
    source: str
    description: str | None
    conversation_count: int
    status: str
    error_message: str | None
    created_at: datetime | None
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class DatasetDetailOut(DatasetOut):
    conversations: list[ConversationOut] = []


class ImportResultOut(BaseModel):
    dataset: DatasetOut
    inserted: int
    skipped: int
    truncated_rows: int = 0
    message: str


class LogCreate(BaseModel):
    level: Literal["info", "warn", "error"]
    event: str
    message: str
    context: dict[str, Any] = Field(default_factory=dict)
