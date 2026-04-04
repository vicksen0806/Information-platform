import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class NotificationRoute(Base):
    """Per-group webhook routing: send a specific group's content to a dedicated webhook."""
    __tablename__ = "notification_routes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    group_name: Mapped[str | None] = mapped_column(String(100), nullable=True)  # None = ungrouped keywords
    webhook_url: Mapped[str] = mapped_column(Text, nullable=False)
    webhook_type: Mapped[str] = mapped_column(String(30), nullable=False, default="generic")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="notification_routes")
