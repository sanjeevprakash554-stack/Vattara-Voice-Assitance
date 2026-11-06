"""SQLAlchemy model for BusinessWorkingHours entity."""

from datetime import time
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, ForeignKey, Integer, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.business import Business


class BusinessWorkingHours(Base, TimestampMixin):
    """Weekly operating schedule and timings for a business organization."""

    __tablename__ = "business_working_hours"
    __table_args__ = (
        UniqueConstraint("business_id", "day_of_week", name="uq_business_day_of_week"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Day index: 0 = Monday, 1 = Tuesday, 2 = Wednesday, 3 = Thursday, 4 = Friday, 5 = Saturday, 6 = Sunday
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    opening_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    closing_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationship to parent Business
    business: Mapped["Business"] = relationship("Business", back_populates="working_hours")

    @property
    def day_name(self) -> str:
        """Return human-readable English day name."""
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        if 0 <= self.day_of_week <= 6:
            return days[self.day_of_week]
        return "Unknown"

    def __repr__(self) -> str:
        status = "Closed" if self.is_closed else f"{self.opening_time}-{self.closing_time}"
        return f"<BusinessWorkingHours(business_id={self.business_id}, day={self.day_name}, {status})>"
