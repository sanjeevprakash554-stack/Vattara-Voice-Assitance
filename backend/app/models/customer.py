"""SQLAlchemy model for Customer entity."""

from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.business import Business
    from app.models.call_history import CallHistory


class Customer(Base, TimestampMixin):
    """Client, patient, or guest associated with a business tenant."""

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # Relationships
    business: Mapped["Business"] = relationship("Business", back_populates="customers")
    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment",
        back_populates="customer",
        cascade="all, delete-orphan",
    )
    call_histories: Mapped[list["CallHistory"]] = relationship(
        "CallHistory",
        back_populates="customer",
    )

    def __repr__(self) -> str:
        return f"<Customer(id={self.id}, name='{self.customer_name}', phone='{self.phone_number}')>"
