"""SQLAlchemy model for Call history and transcripts."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin


class Call(Base, TimestampMixin):
    """Voice Call record (Inbound or Outbound)."""

    __tablename__ = "calls"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    caller_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    caller_phone: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    call_type: Mapped[str] = mapped_column(
        String(20), default="incoming", nullable=False
    )  # incoming, outgoing
    status: Mapped[str] = mapped_column(
        String(30), default="completed", nullable=False
    )  # completed, missed, failed, in_progress
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    recording_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    initiated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    business = relationship("Business", back_populates="calls")
    customer = relationship("Customer", back_populates="calls")

