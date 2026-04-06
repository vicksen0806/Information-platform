from typing import Literal, Annotated
from pydantic import BaseModel

LlmProvider = Literal["openai", "deepseek", "qwen", "zhipu", "moonshot", "volcengine"]


LlmSummaryStyle = Literal["concise", "detailed", "academic"]


class LlmConfigCreate(BaseModel):
    provider: LlmProvider
    api_key: str | None = None  # 留空时保留已有密钥
    model_name: str
    base_url: str | None = None
    prompt_template: str | None = None
    summary_style: LlmSummaryStyle = "concise"
    embedding_model: str | None = None  # e.g. "text-embedding-3-small", blank = disable


class LlmConfigResponse(BaseModel):
    provider: str
    api_key_masked: str
    model_name: str
    base_url: str | None
    prompt_template: str | None = None
    summary_style: str = "concise"
    embedding_model: str | None = None

    model_config = {"from_attributes": True}


class LlmTestResult(BaseModel):
    success: bool
    message: str
