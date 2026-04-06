import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text, Float, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from app.database import Base


class Digest(Base):
    __tablename__ = "digests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    crawl_job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("crawl_jobs.id", ondelete="CASCADE"), unique=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    summary_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords_used: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    sources_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    llm_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    share_token: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    importance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # embedding vector(1536) is managed outside the ORM (via raw SQL) to avoid
    # breaking when pgvector extension is not installed.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    user: Mapped["User"] = relationship("User", back_populates="digests")
    crawl_job: Mapped["CrawlJob"] = relationship("CrawlJob", back_populates="digest")
