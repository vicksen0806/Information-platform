from typing import Literal
from pydantic import BaseModel

LlmProvider = Literal["openai", "deepseek", "qwen", "zhipu", "moonshot"]


class LlmConfigCreate(BaseModel):
    provider: LlmProvider
    api_key: str
    model_name: str
    base_url: str | None = None


class LlmConfigResponse(BaseModel):
    provider: str
    api_key_masked: str
    model_name: str
    base_url: str | None

    model_config = {"from_attributes": True}


class LlmTestResult(BaseModel):
    success: bool
    message: str
