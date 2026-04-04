import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    llm_config: Mapped["UserLlmConfig"] = relationship("UserLlmConfig", back_populates="user", uselist=False)
    schedule_config: Mapped["UserScheduleConfig"] = relationship("UserScheduleConfig", back_populates="user", uselist=False)
    notification_config: Mapped["UserNotificationConfig"] = relationship("UserNotificationConfig", back_populates="user", uselist=False)
    sources: Mapped[list["Source"]] = relationship("Source", back_populates="user", cascade="all, delete-orphan")
    keywords: Mapped[list["Keyword"]] = relationship("Keyword", back_populates="user", cascade="all, delete-orphan")
    crawl_jobs: Mapped[list["CrawlJob"]] = relationship("CrawlJob", back_populates="user", cascade="all, delete-orphan")
    digests: Mapped[list["Digest"]] = relationship("Digest", back_populates="user", cascade="all, delete-orphan")
