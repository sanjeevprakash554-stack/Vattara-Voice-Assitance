"""SQLAlchemy models for SaaS Subscriptions, Plans, Usage Limits, and Invoices."""

import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin


class Subscription(Base, TimestampMixin):
    """SaaS Subscription record tracking tenant tier, billing cycle, and usage quotas."""

    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    plan_name: Mapped[str] = mapped_column(
        String(50), default="starter", nullable=False
    )  # starter, professional, enterprise
    billing_cycle: Mapped[str] = mapped_column(
        String(20), default="monthly", nullable=False
    )  # monthly, annual
    status: Mapped[str] = mapped_column(
        String(30), default="active", nullable=False, index=True
    )  # trial, active, past_due, cancelled, suspended
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Usage Quotas & Limits
    monthly_call_minutes_limit: Mapped[int] = mapped_column(Integer, default=500, nullable=False)
    used_call_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_assistants: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_staff: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

    # Relationships
    business = relationship("Business", back_populates="subscription")
    invoices = relationship("Invoice", back_populates="subscription", cascade="all, delete-orphan")


class Invoice(Base, TimestampMixin):
    """Billing statement / ledger invoice for business tenant subscription renewals."""

    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subscription_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="paid", nullable=False, index=True
    )  # paid, pending, failed
    billing_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pdf_url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    business = relationship("Business", back_populates="invoices")
    subscription = relationship("Subscription", back_populates="invoices")
