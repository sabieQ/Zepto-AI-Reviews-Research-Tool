from uuid import UUID

from pydantic import BaseModel, Field

from app.core.constants import DEFAULT_TOP_K, MAX_TOP_K


class SearchRequest(BaseModel):
    dataset_id: UUID
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=MAX_TOP_K)


class IndexResultOut(BaseModel):
    dataset_id: UUID
    status: str
    conversation_count: int
    message: str
