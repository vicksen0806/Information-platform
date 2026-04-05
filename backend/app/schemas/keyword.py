import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator


class KeywordCreate(BaseModel):
    text: str
    url: str | None = None
    source_type: str = "search"  # search | webpage | rss
    group_name: str | None = None
    crawl_interval_hours: int = 24
    requires_js: bool = False

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        v = v.strip()
        if len(v) == 0:
            raise ValueError("Keyword cannot be empty")
        if len(v) > 200:
            raise ValueError("Keyword cannot exceed 200 characters")
        return v

    @field_validator("crawl_interval_hours")
    @classmethod
    def validate_interval(cls, v: int) -> int:
        if v not in (1, 6, 12, 24, 72, 168):
            raise ValueError("crawl_interval_hours must be one of: 1, 6, 12, 24, 72, 168")
        return v


class KeywordUpdate(BaseModel):
    is_active: bool | None = None
    url: str | None = None
    source_type: str | None = None
    group_name: str | None = None
    crawl_interval_hours: int | None = None
    requires_js: bool | None = None


class KeywordResponse(BaseModel):
    id: uuid.UUID
    text: str
    is_active: bool
    url: str | None
    source_type: str
    group_name: str | None
    crawl_interval_hours: int
    last_crawled_at: datetime | None
    requires_js: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}
