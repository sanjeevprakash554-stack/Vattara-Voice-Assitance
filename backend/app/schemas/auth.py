"""Pydantic schemas for Authentication, Registration, and User Profile."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class BusinessResponse(BaseModel):
    """Schema for Business details in responses."""

    id: str
    name: str
    vertical: str
    phone: str
    email: str
    timezone: str
    address: str | None = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    """Schema for User details in responses."""

    id: str
    business_id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserProfileResponse(BaseModel):
    """Schema combining User profile and Business tenant metadata."""

    user: UserResponse
    business: BusinessResponse


class Token(BaseModel):
    """Authentication bearer token response."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    business: BusinessResponse


class LoginRequest(BaseModel):
    """User login credential payload."""

    email: str
    password: str


class RegisterBusinessRequest(BaseModel):
    """Registration request for creating a new Business and admin user."""

    business_name: str = Field(..., min_length=2, max_length=150)
    vertical: str = Field(
        ...,
        description="clinic, hospital, hotel, salon, service_centre, real_estate, other",
    )
    business_phone: str = Field(..., min_length=7, max_length=25)
    business_email: str
    address: str | None = None
    timezone: str = "Asia/Kolkata"

    admin_name: str = Field(..., min_length=2, max_length=100)
    admin_email: str
    admin_password: str = Field(..., min_length=6, max_length=128)


class ForgotPasswordRequest(BaseModel):
    """Request to initiate password reset."""

    email: str


class ResetPasswordRequest(BaseModel):
    """Payload to reset forgotten password."""

    email: str
    new_password: str = Field(..., min_length=6, max_length=128)
    reset_code: str = Field(default="123456")


class UpdateProfileRequest(BaseModel):
    """Payload to update user/business profile information."""

    full_name: str | None = None
    business_name: str | None = None
    phone: str | None = None
    address: str | None = None
    current_password: str | None = None
    new_password: str | None = None
