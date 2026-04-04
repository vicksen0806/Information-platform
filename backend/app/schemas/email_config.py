from pydantic import BaseModel, EmailStr


class EmailConfigCreate(BaseModel):
    smtp_host: str
    smtp_port: int = 465
    smtp_user: str
    smtp_password: str | None = None  # empty = keep existing
    smtp_from: str
    smtp_to: str  # comma-separated recipients
    is_active: bool = True


class EmailConfigResponse(BaseModel):
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_from: str
    smtp_to: str
    is_active: bool

    model_config = {"from_attributes": True}


class EmailTestResult(BaseModel):
    success: bool
    message: str
