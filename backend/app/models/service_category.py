"""SQLAlchemy model for ServiceCategory entity."""

from typing import TYPE_CHECKING
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.business import Business
    from app.models.business_service import BusinessService


class ServiceCategory(Base, TimestampMixin):
    """Categorical grouping of services offered by a business organization."""

    __tablename__ = "service_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Relationships
    business: Mapped["Business"] = relationship("Business", back_populates="service_categories")
    services: Mapped[list["BusinessService"]] = relationship(
        "BusinessService",
        back_populates="category",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<ServiceCategory(id={self.id}, name='{self.category_name}', active={self.is_active})>"
