"""Pydantic schemas for Business entities, profile management, and admin views."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class BusinessResponse(BaseModel):
    """Public safe representation of a registered Business."""

    id: int
    business_name: str
    business_type: str
    email: EmailStr
    phone_number: str | None = None
    address: str | None = None
    website: str | None = None
    description: str | None = None
    logo_url: str | None = None
    timezone: str = "UTC"
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BusinessProfileResponse(BusinessResponse):
    """Business profile response for tenant authenticated sessions."""
    pass


class BusinessProfileUpdateRequest(BaseModel):
    """Payload for updating business profile information."""

    business_name: str | None = Field(default=None, min_length=2, max_length=255)
    business_type: str | None = Field(default=None, min_length=2, max_length=100)
    email: EmailStr | None = None
    phone_number: str | None = Field(default=None, max_length=50)
    address: str | None = None
    website: str | None = Field(default=None, max_length=255)
    description: str | None = None
    logo_url: str | None = Field(default=None, max_length=1024)
    timezone: str | None = Field(default=None, max_length=50)


class BusinessStatusUpdateRequest(BaseModel):
    """Payload to activate or deactivate a business."""

    is_active: bool = Field(..., description="Active status for the business organization")


class BusinessDetailResponse(BusinessResponse):
    """Detailed business information including staff members for Super Admin audit."""

    users_count: int = 0
    customers_count: int = 0
    appointments_count: int = 0
    call_histories_count: int = 0
