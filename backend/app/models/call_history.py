"""SQLAlchemy model for CallHistory entity."""

from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.business import Business
    from app.models.customer import Customer


class CallHistory(Base, TimestampMixin):
    """Telephony and AI receptionist call activity log."""

    __tablename__ = "call_histories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    phone_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    call_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    call_status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    call_duration: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recording_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Relationships
    business: Mapped["Business"] = relationship("Business", back_populates="call_histories")
    customer: Mapped["Customer | None"] = relationship("Customer", back_populates="call_histories")

    def __repr__(self) -> str:
        return (
            f"<CallHistory(id={self.id}, phone='{self.phone_number}', "
            f"type='{self.call_type}', status='{self.call_status}', duration={self.call_duration}s)>"
        )
