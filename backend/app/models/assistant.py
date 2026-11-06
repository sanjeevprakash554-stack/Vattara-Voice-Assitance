"""SQLAlchemy models for AI Assistant Configuration, Services, and FAQs."""

import uuid
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin


class AssistantConfig(Base, TimestampMixin):
    """AI Voice Assistant configuration for a Business."""

    __tablename__ = "assistant_configs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    business_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    assistant_name: Mapped[str] = mapped_column(String(100), default="Vattara AI", nullable=False)
    language: Mapped[str] = mapped_column(String(20), default="en-US", nullable=False)
    voice: Mapped[str] = mapped_column(String(50), default="alloy", nullable=False)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    working_hours: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default='{"monday":{"open":"09:00","close":"18:00","enabled":true},"tuesday":{"open":"09:00","close":"18:00","enabled":true},"wednesday":{"open":"09:00","close":"18:00","enabled":true},"thursday":{"open":"09:00","close":"18:00","enabled":true},"friday":{"open":"09:00","close":"18:00","enabled":true},"saturday":{"open":"10:00","close":"16:00","enabled":true},"sunday":{"open":"10:00","close":"14:00","enabled":false}}',
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationship
    business = relationship("Business", back_populates="assistant_config")


class Service(Base, TimestampMixin):
    """Services provided by the Business."""

    __tablename__ = "services"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    business = relationship("Business", back_populates="services")
    appointments = relationship("Appointment", back_populates="service")


class FAQ(Base, TimestampMixin):
    """Frequently Asked Questions and Knowledge Base entries for AI receptionist."""

    __tablename__ = "faqs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(100), default="General", nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[Text] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationship
    business = relationship("Business", back_populates="faqs")

