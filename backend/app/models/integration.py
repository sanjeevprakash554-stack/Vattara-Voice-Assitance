"""SQLAlchemy model for Business Tenant Telephony and External Integrations."""

import uuid
from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin


class BusinessIntegration(Base, TimestampMixin):
    """Telephony provider configurations and status per business tenant."""

    __tablename__ = "business_integrations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    primary_provider: Mapped[str] = mapped_column(
        String(50), default="twilio", nullable=False
    )  # twilio, plivo, smartflo, exotel

    # Plivo Configuration (Primary Indian Telephony Provider)
    plivo_auth_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    plivo_phone_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_plivo_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Twilio Configuration
    twilio_account_sid: Mapped[str | None] = mapped_column(String(100), nullable=True)
    twilio_phone_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_twilio_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Tata Smartflo Configuration
    smartflo_caller_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    smartflo_api_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_smartflo_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Exotel Configuration
    exotel_sid: Mapped[str | None] = mapped_column(String(100), nullable=True)
    exotel_caller_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_exotel_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Webhook Status
    inbound_webhook_url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    business = relationship("Business", back_populates="integrations")
