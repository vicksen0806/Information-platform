import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, HttpUrl, field_validator


SourceType = Literal["webpage", "rss", "sitemap"]


class SourceCreate(BaseModel):
    name: str
    url: str
    source_type: SourceType = "webpage"
    crawl_interval_hours: int = 24

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError("Name cannot be empty")
        return v.strip()


class SourceUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    source_type: SourceType | None = None
    is_active: bool | None = None
    crawl_interval_hours: int | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class SourceResponse(BaseModel):
    id: uuid.UUID
    name: str
    url: str
    source_type: str
    is_active: bool
    crawl_interval_hours: int
    last_crawled_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SourceTestResult(BaseModel):
    success: bool
    http_status: int | None = None
    content_preview: str | None = None
    error: str | None = None
