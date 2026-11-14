"""SQLAlchemy model for Business Operating Hours."""

import uuid
from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin


class BusinessHour(Base, TimestampMixin):
    """Weekly operating hours configuration for a Business tenant."""

    __tablename__ = "business_hours"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    day_of_week: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True
    )  # 0 = Monday, 6 = Sunday (ISO 8601 / Python weekday)
    open_time: Mapped[str] = mapped_column(
        String(8), nullable=False, default="09:00"
    )  # Format: "HH:MM" in 24hr format
    close_time: Mapped[str] = mapped_column(
        String(8), nullable=False, default="18:00"
    )  # Format: "HH:MM" in 24hr format
    is_closed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Relationship
    business = relationship("Business")
