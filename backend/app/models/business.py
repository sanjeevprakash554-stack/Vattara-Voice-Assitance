"""SQLAlchemy model for Business (multi-tenant organization)."""

import uuid
from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin


class Business(Base, TimestampMixin):
    """Business entity representing a tenant organization."""

    __tablename__ = "businesses"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    vertical: Mapped[str] = mapped_column(
        String(50), nullable=False, default="clinic"
    )  # hospital, clinic, hotel, salon, service_centre, real_estate, other
    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Kolkata", nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    users = relationship("User", back_populates="business", cascade="all, delete-orphan")
    assistant_config = relationship(
        "AssistantConfig", back_populates="business", uselist=False, cascade="all, delete-orphan"
    )
    customers = relationship("Customer", back_populates="business", cascade="all, delete-orphan")
    calls = relationship("Call", back_populates="business", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="business", cascade="all, delete-orphan")
    reminders = relationship("Reminder", back_populates="business", cascade="all, delete-orphan")
    services = relationship("Service", back_populates="business", cascade="all, delete-orphan")
    faqs = relationship("FAQ", back_populates="business", cascade="all, delete-orphan")

