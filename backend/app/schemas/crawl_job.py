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

    model_config = {"from_attributes": True}


class CrawlResultResponse(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    source_name: str | None = None
    http_status: int | None
    content_preview: str | None = None
    error_message: str | None
    crawled_at: datetime

    model_config = {"from_attributes": True}
