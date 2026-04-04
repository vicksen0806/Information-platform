import uuid
from datetime import datetime
from pydantic import BaseModel


class CrawlJobResponse(BaseModel):
    id: uuid.UUID
    status: str
    triggered_by: str
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    created_at: datetime
    has_digest: bool = False
    digest_id: str | None = None
    new_content_found: bool = False
    digest_error: str | None = None

    model_config = {"from_attributes": True}


class CrawlResultResponse(BaseModel):
    id: uuid.UUID
    keyword_text: str | None = None
    http_status: int | None
    content_preview: str | None = None
    article_count: int = 0
    error_message: str | None
    crawled_at: datetime

    model_config = {"from_attributes": True}
