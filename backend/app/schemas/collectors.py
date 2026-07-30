from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.constants import MAX_COLLECTOR_PER_STORE

CollectorSource = Literal["google_play", "app_store"]


class CollectorRunRequest(BaseModel):
    dataset_id: UUID | None = None
    sources: list[CollectorSource] | None = None
    limit: int | None = Field(default=None, ge=1, le=MAX_COLLECTOR_PER_STORE)
    country: str | None = Field(default=None, min_length=2, max_length=8)
    lang: str | None = Field(default=None, min_length=2, max_length=8)
    auto_index: bool = False


class CollectorBulkRequest(BaseModel):
    dataset_id: UUID | None = None
    target: int = Field(default=100_000, ge=100, le=200_000)
    country: str | None = Field(default=None, min_length=2, max_length=8)
    lang: str | None = Field(default=None, min_length=2, max_length=8)
    include_app_store: bool = True
    auto_index: bool = False
    play_countries: list[str] | None = None


class CollectorRunOut(BaseModel):
    id: UUID
    dataset_id: UUID
    status: str
    sources: Any
    inserted: int
    skipped: int
    error_message: str | None
    context: Any
    created_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}
