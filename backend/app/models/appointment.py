"""SQLAlchemy model for Appointment entity."""

from datetime import date, time
from typing import TYPE_CHECKING
from sqlalchemy import Date, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.business import Business
    from app.models.customer import Customer
    from app.models.reminder import Reminder


class Appointment(Base, TimestampMixin):
    """Scheduled appointment, consultation, reservation, or service session."""

    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    appointment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    appointment_time: Mapped[time] = mapped_column(Time, nullable=False)
    service_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="scheduled", index=True)

    # Relationships
    business: Mapped["Business"] = relationship("Business", back_populates="appointments")
    customer: Mapped["Customer"] = relationship("Customer", back_populates="appointments")
    reminders: Mapped[list["Reminder"]] = relationship(
        "Reminder",
        back_populates="appointment",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Appointment(id={self.id}, service='{self.service_name}', "
            f"date={self.appointment_date}, status='{self.status}')>"
        )
