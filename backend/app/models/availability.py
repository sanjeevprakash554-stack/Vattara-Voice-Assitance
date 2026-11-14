"""SQLAlchemy models for Manual Availability Management.

Covers:
1. BusinessBreak: Scheduled breaks (e.g. lunch, tea) per day or daily.
2. AvailabilitySetting: Business-level appointment booking rules & timing constraints.
3. BusinessHoliday: Fixed holiday dates with full day closure.
4. SpecialDateOverride: Date-specific overrides for custom working hours or special closures.
"""

import uuid
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin


class BusinessBreak(Base, TimestampMixin):
    """Business operating breaks (e.g. lunch hour, sanitization window)."""

    __tablename__ = "business_breaks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    day_of_week: Mapped[int] = mapped_column(
        Integer, nullable=False, default=-1, index=True
    )  # -1 = All operating days, 0 = Monday, ..., 6 = Sunday
    start_time: Mapped[str] = mapped_column(
        String(8), nullable=False, default="13:00"
    )  # "HH:MM" 24-hr format
    end_time: Mapped[str] = mapped_column(
        String(8), nullable=False, default="14:00"
    )  # "HH:MM" 24-hr format
    description: Mapped[str] = mapped_column(
        String(200), nullable=False, default="Lunch Break"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    business = relationship("Business")


class AvailabilitySetting(Base, TimestampMixin):
    """Business appointment scheduling constraints, buffer rules, and advance booking limits."""

    __tablename__ = "availability_settings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    default_duration_minutes: Mapped[int] = mapped_column(
        Integer, default=30, nullable=False
    )
    buffer_time_minutes: Mapped[int] = mapped_column(
        Integer, default=10, nullable=False
    )  # Minimum buffer gap between consecutive appointments
    min_advance_hours: Mapped[int] = mapped_column(
        Integer, default=2, nullable=False
    )  # Minimum hours notice required for booking
    max_advance_days: Mapped[int] = mapped_column(
        Integer, default=30, nullable=False
    )  # Maximum days ahead customers can book
    same_day_booking: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )  # Whether same-day booking is allowed
    slot_interval_minutes: Mapped[int] = mapped_column(
        Integer, default=30, nullable=False
    )  # Discrete step interval between selectable slots (15, 30, etc.)

    business = relationship("Business")


class BusinessHoliday(Base, TimestampMixin):
    """Business closure dates / public holidays where no appointments can be scheduled."""

    __tablename__ = "business_holidays"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    holiday_date: Mapped[str] = mapped_column(
        String(10), nullable=False, index=True
    )  # Format: "YYYY-MM-DD"
    name: Mapped[str] = mapped_column(
        String(200), nullable=False
    )  # e.g., "Republic Day", "Annual Maintenance"
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    business = relationship("Business")


class SpecialDateOverride(Base, TimestampMixin):
    """Overrides standard weekly operating hours for a specific date (special hours or closures)."""

    __tablename__ = "special_date_overrides"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    override_date: Mapped[str] = mapped_column(
        String(10), nullable=False, index=True
    )  # Format: "YYYY-MM-DD"
    is_closed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )  # True = full day closure, False = special open hours below
    open_time: Mapped[str | None] = mapped_column(
        String(8), nullable=True, default="09:00"
    )  # "HH:MM" 24-hr format
    close_time: Mapped[str | None] = mapped_column(
        String(8), nullable=True, default="13:00"
    )  # "HH:MM" 24-hr format
    description: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # e.g. "Festival Eve Half Day", "Extended Evening Session"

    business = relationship("Business")
