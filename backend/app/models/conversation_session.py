"""SQLAlchemy model for persistent multi-turn voice conversation state."""

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base, TimestampMixin


class ConversationSession(Base, TimestampMixin):
    """Persistent voice conversation state tracking for Twilio voice calls."""

    __tablename__ = "conversation_sessions"

    call_sid: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    caller_phone: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    customer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    service_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("services.id", ondelete="SET NULL"), nullable=True
    )
    service_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    appointment_datetime_iso: Mapped[str | None] = mapped_column(String(50), nullable=True)
    step: Mapped[str] = mapped_column(String(50), default="greeting", nullable=False)
    language: Mapped[str] = mapped_column(String(20), default="en-IN", nullable=False)
    detected_language: Mapped[str | None] = mapped_column(String(30), nullable=True)
    intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    booking_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    dialog_history: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_speech_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
