import uuid
from datetime import date, datetime
from pydantic import BaseModel


class DigestKeywordCard(BaseModel):
    keyword: str
    summary_md: str
    crawl_date: datetime | None = None


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
    feedback: str | None = None  # 'positive' | 'negative' | None
    is_starred: bool = False
    importance_score: float | None = None
    keyword_cards: list[DigestKeywordCard] = []

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
    feedback: str | None = None  # 'positive' | 'negative' | None
    is_starred: bool = False
    importance_score: float | None = None

    model_config = {"from_attributes": True}


class KeywordHistorySummary(BaseModel):
    keyword: str
    latest_crawled_at: datetime | None = None
    total_days: int = 0


class KeywordHistoryEntry(BaseModel):
    keyword: str
    crawl_date: date
    crawled_at: datetime
    summary_md: str
    article_count: int = 0
    digest_id: uuid.UUID | None = None
    title: str | None = None


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
