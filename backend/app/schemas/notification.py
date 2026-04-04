from pydantic import BaseModel


class NotificationConfigResponse(BaseModel):
    webhook_type: str
    webhook_url: str
    is_active: bool

    model_config = {"from_attributes": True}


class NotificationConfigUpsert(BaseModel):
    webhook_type: str  # feishu | wecom | generic
    webhook_url: str
    is_active: bool = True


class NotificationTestResult(BaseModel):
    success: bool
    message: str
