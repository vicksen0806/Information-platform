import uuid
from datetime import datetime
from pydantic import BaseModel


class DigestResponse(BaseModel):
    id: uuid.UUID
    crawl_job_id: uuid.UUID
    title: str | None
    summary_md: str | None
    keywords_used: list[str] | None
    sources_count: int
    tokens_used: int
    llm_model: str | None
    is_read: bool
    share_token: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DigestUpdate(BaseModel):
    is_read: bool | None = None


class DigestListItem(BaseModel):
    id: uuid.UUID
    title: str | None
    keywords_used: list[str] | None
    sources_count: int
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UsageMonthly(BaseModel):
    month: str  # "2026-04"
    tokens: int
    digests: int


class UsageResponse(BaseModel):
    total_tokens: int
    total_digests: int
    this_month_tokens: int
    this_month_digests: int
    monthly: list[UsageMonthly]
