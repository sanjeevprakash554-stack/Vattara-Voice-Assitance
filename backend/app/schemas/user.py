"""Pydantic schemas for User entities, staff management, and profile views."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.models.user import UserRole


class UserResponse(BaseModel):
    """Public safe representation of a User entity (no password hash)."""

    id: int
    business_id: int | None
    full_name: str
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserProfileResponse(UserResponse):
    """Extended user profile response including business metadata."""

    business_name: str | None = None
    business_type: str | None = None


class UserProfileUpdateRequest(BaseModel):
    """Payload for self user profile updates (role/business_id modification prohibited)."""

    full_name: str = Field(..., min_length=2, max_length=255, description="User's full display name")


class UserCreateRequest(BaseModel):
    """Payload for Business Admin creating a new staff member."""

    full_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr = Field(..., description="Unique staff email address")
    password: str = Field(..., min_length=8, description="Initial password meeting strength requirements")
    role: UserRole = Field(
        default=UserRole.STAFF,
        description="Role assigned to the staff member (STAFF or BUSINESS_ADMIN)",
    )


class UserUpdateRequest(BaseModel):
    """Payload for Business Admin updating permitted staff member fields."""

    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    role: UserRole | None = Field(default=None, description="Role update (cannot elevate to SUPER_ADMIN)")
    is_active: bool | None = Field(default=None, description="Account active status")
