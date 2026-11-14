"""SQLAlchemy model for Reminders and Reminder Settings."""

import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin


class Reminder(Base, TimestampMixin):
    """Notification or reminder dispatched to customers."""

    __tablename__ = "reminders"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    appointment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("appointments.id", ondelete="CASCADE"), nullable=True, index=True
    )
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reminder_type: Mapped[str] = mapped_column(
        String(30), default="voice", nullable=False
    )  # voice, call, sms, whatsapp, email
    scheduled_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(30), default="pending", nullable=False, index=True
    )  # pending, calling, completed, sent, failed, cancelled, retrying
    message: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Phase 6 Enhancements
    call_sid: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    customer_response: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    interval_tag: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Relationships
    business = relationship("Business", back_populates="reminders")
    appointment = relationship("Appointment", back_populates="reminders")
    customer = relationship("Customer", back_populates="reminders")


class ReminderSetting(Base, TimestampMixin):
    """Business tenant configuration for automated appointment reminders."""

    __tablename__ = "reminder_settings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    reminder_intervals_hours: Mapped[str] = mapped_column(
        String(50), default="24,2", nullable=False
    )  # Comma-separated hours before appointment (e.g. "24,2")
    calling_start_time: Mapped[str] = mapped_column(
        String(10), default="09:00", nullable=False
    )  # Calling window start (HH:MM in business local time)
    calling_end_time: Mapped[str] = mapped_column(
        String(10), default="20:00", nullable=False
    )  # Calling window end (HH:MM in business local time)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    retry_delay_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    default_channel: Mapped[str] = mapped_column(String(20), default="voice", nullable=False)

    # Relationships
    business = relationship("Business", back_populates="reminder_setting")
