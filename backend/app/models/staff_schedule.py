"""SQLAlchemy model for Staff/Doctor Availability Schedules."""

import uuid
from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin


class StaffSchedule(Base, TimestampMixin):
    """Doctor or Staff member working hours and break schedules."""

    __tablename__ = "staff_schedules"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    staff_name: Mapped[str] = mapped_column(
        String(200), nullable=False
    )
    day_of_week: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True
    )  # 0 = Monday, 6 = Sunday
    start_time: Mapped[str] = mapped_column(
        String(8), nullable=False, default="09:00"
    )
    end_time: Mapped[str] = mapped_column(
        String(8), nullable=False, default="17:00"
    )
    break_start: Mapped[str | None] = mapped_column(
        String(8), nullable=True
    )
    break_end: Mapped[str | None] = mapped_column(
        String(8), nullable=True
    )
    slot_duration_minutes: Mapped[int] = mapped_column(
        Integer, default=30, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    # Relationships
    business = relationship("Business")
    user = relationship("User")
