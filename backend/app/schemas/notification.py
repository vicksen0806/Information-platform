import uuid
from datetime import datetime
from pydantic import BaseModel, model_validator


def _mask_url(url: str) -> str:
    """Show only the first 40 chars and mask the rest (token area)."""
    if len(url) <= 40:
        return url
    return url[:40] + "****"


class NotificationConfigResponse(BaseModel):
    webhook_type: str
    webhook_url: str       # full URL stored internally
    webhook_url_masked: str = ""
    is_active: bool

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def set_masked(self):
        self.webhook_url_masked = _mask_url(self.webhook_url)
        return self


class NotificationConfigUpsert(BaseModel):
    webhook_type: str  # feishu | wecom | generic
    webhook_url: str
    is_active: bool = True


class NotificationTestResult(BaseModel):
    success: bool
    message: str


class NotificationRouteCreate(BaseModel):
    group_name: str | None = None
    webhook_type: str
    webhook_url: str
    is_active: bool = True


class NotificationRouteResponse(BaseModel):
    id: uuid.UUID
    group_name: str | None
    webhook_type: str
    webhook_url: str
    webhook_url_masked: str = ""
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def set_masked(self):
        self.webhook_url_masked = _mask_url(self.webhook_url)
        return self
