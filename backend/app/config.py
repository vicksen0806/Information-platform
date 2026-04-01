from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/infoplatform"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    SECRET_KEY: str = "change-this-in-production"
    ENCRYPTION_KEY: str = "change-this-32-byte-key-in-prod!"

    # JWT
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    # Celery Beat — 每日爬取时间（UTC）
    DAILY_CRAWL_HOUR: int = 1
    DAILY_CRAWL_MINUTE: int = 0

    # 初始管理员
    FIRST_ADMIN_EMAIL: str = "admin@example.com"
    FIRST_ADMIN_PASSWORD: str = "changeme123"

    # 环境
    ENV: str = "development"

    # LLM 提供商 base_url 映射
    LLM_PROVIDER_BASE_URLS: dict = {
        "openai":   "https://api.openai.com/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "qwen":     "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "zhipu":    "https://open.bigmodel.cn/api/paas/v4",
        "moonshot": "https://api.moonshot.cn/v1",
    }

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
