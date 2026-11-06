"""SQLAlchemy model for User entity with role definitions."""

from enum import Enum
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.business import Business


class UserRole(str, Enum):
    """User role enumeration for RBAC authorization."""

    SUPER_ADMIN = "SUPER_ADMIN"
    BUSINESS_ADMIN = "BUSINESS_ADMIN"
    STAFF = "STAFF"


class User(Base, TimestampMixin):
    """Platform user entity supporting multi-tenant administrators, staff, and super admins."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    business_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default=UserRole.STAFF.value, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Relationship to parent Business (nullable for platform-level Super Admins)
    business: Mapped["Business | None"] = relationship("Business", back_populates="users")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}', active={self.is_active})>"
