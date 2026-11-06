"""SQLAlchemy model for Reminders."""

import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Text
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
        String(30), default="sms", nullable=False
    )  # sms, voice, email, whatsapp
    scheduled_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(30), default="pending", nullable=False, index=True
    )  # pending, sent, failed, cancelled
    message: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    business = relationship("Business", back_populates="reminders")
    appointment = relationship("Appointment", back_populates="reminders")
    customer = relationship("Customer", back_populates="reminders")

