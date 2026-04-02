import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, model_validator


SourceType = Literal["webpage", "rss", "search"]


class SourceCreate(BaseModel):
    name: str
    url: str | None = None
    search_query: str | None = None
    source_type: SourceType = "webpage"
    crawl_interval_hours: int = 24

    @model_validator(mode="after")
    def validate_source(self):
        if self.source_type == "search":
            if not self.search_query or not self.search_query.strip():
                raise ValueError("search_query is required for search type")
        else:
            if not self.url:
                raise ValueError("url is required")
            if not self.url.startswith(("http://", "https://")):
                raise ValueError("URL must start with http:// or https://")
        name = self.name.strip() if self.name else ""
        if not name:
            raise ValueError("Name cannot be empty")
        self.name = name
        return self


class SourceUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    is_active: bool | None = None
    crawl_interval_hours: int | None = None

    @model_validator(mode="after")
    def validate_url(self):
        if self.url is not None and not self.url.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return self


class SourceResponse(BaseModel):
    id: uuid.UUID
    name: str
    url: str
    search_query: str | None
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
