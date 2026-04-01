import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator


class KeywordCreate(BaseModel):
    text: str

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
    is_active: bool


class KeywordResponse(BaseModel):
    id: uuid.UUID
    text: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
