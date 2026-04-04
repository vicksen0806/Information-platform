import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator


class KeywordCreate(BaseModel):
    text: str
    url: str | None = None
    source_type: str = "search"  # search | webpage | rss

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        v = v.strip()
        if len(v) == 0:
            raise ValueError("Keyword cannot be empty")
        if len(v) > 200:
            raise ValueError("Keyword cannot exceed 200 characters")
        return v


class KeywordUpdate(BaseModel):
    is_active: bool | None = None
    url: str | None = None
    source_type: str | None = None


class KeywordResponse(BaseModel):
    id: uuid.UUID
    text: str
    is_active: bool
    url: str | None
    source_type: str
    created_at: datetime

    model_config = {"from_attributes": True}
