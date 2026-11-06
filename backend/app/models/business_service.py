"""SQLAlchemy model for BusinessService entity."""

from typing import TYPE_CHECKING
from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.business import Business
    from app.models.service_category import ServiceCategory


class BusinessService(Base, TimestampMixin):
    """Specific commercial service, treatment, repair, or consultation offered by a business."""

    __tablename__ = "business_services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("service_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    service_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Relationships
    business: Mapped["Business"] = relationship("Business", back_populates="services")
    category: Mapped["ServiceCategory | None"] = relationship("ServiceCategory", back_populates="services")

    def __repr__(self) -> str:
        return (
            f"<BusinessService(id={self.id}, name='{self.service_name}', "
            f"price={self.price} {self.currency}, duration={self.duration_minutes}m, active={self.is_active})>"
        )
