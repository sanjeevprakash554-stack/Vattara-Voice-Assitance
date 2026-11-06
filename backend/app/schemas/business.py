"""Pydantic schemas for Business entities and admin views."""

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
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BusinessStatusUpdateRequest(BaseModel):
    """Payload to activate or deactivate a business."""

    is_active: bool = Field(..., description="Active status for the business organization")


class BusinessDetailResponse(BusinessResponse):
    """Detailed business information including staff members for Super Admin audit."""

    users_count: int = 0
    customers_count: int = 0
    appointments_count: int = 0
    call_histories_count: int = 0
