"""SQLAlchemy model for Reminder entity."""

from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.business import Business


class Reminder(Base, TimestampMixin):
    """Notification reminder scheduled for an upcoming appointment."""

    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    appointment_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reminder_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    reminder_type: Mapped[str] = mapped_column(String(50), nullable=False, default="sms", index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", index=True)

    # Relationships
    business: Mapped["Business"] = relationship("Business", back_populates="reminders")
    appointment: Mapped["Appointment"] = relationship("Appointment", back_populates="reminders")

    def __repr__(self) -> str:
        return (
            f"<Reminder(id={self.id}, appointment_id={self.appointment_id}, "
            f"type='{self.reminder_type}', status='{self.status}')>"
        )
