"""SQLAlchemy model for Customers."""

import uuid
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin


class Customer(Base, TimestampMixin):
    """Customer entity associated with a Business."""

    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_appointments: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    business = relationship("Business", back_populates="customers")
    calls = relationship("Call", back_populates="customer", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="customer", cascade="all, delete-orphan")
    reminders = relationship("Reminder", back_populates="customer", cascade="all, delete-orphan")

