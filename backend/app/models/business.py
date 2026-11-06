"""SQLAlchemy model for Business entity."""

from typing import TYPE_CHECKING
from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.call_history import CallHistory
    from app.models.customer import Customer
    from app.models.reminder import Reminder
    from app.models.user import User


class Business(Base, TimestampMixin):
    """Business organization registered on the multi-business SaaS platform."""

    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    business_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    business_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    phone_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Relationships
    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="business",
        cascade="all, delete-orphan",
    )
    customers: Mapped[list["Customer"]] = relationship(
        "Customer",
        back_populates="business",
        cascade="all, delete-orphan",
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment",
        back_populates="business",
        cascade="all, delete-orphan",
    )
    call_histories: Mapped[list["CallHistory"]] = relationship(
        "CallHistory",
        back_populates="business",
        cascade="all, delete-orphan",
    )
    reminders: Mapped[list["Reminder"]] = relationship(
        "Reminder",
        back_populates="business",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Business(id={self.id}, name='{self.business_name}', type='{self.business_type}')>"
