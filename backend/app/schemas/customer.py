"""Pydantic schemas for Customers."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class CustomerBase(BaseModel):
    """Base schema for Customer attributes."""

    name: str = Field(..., min_length=2, max_length=200)
    phone: str = Field(..., min_length=7, max_length=50)
    email: str | None = None
    notes: str | None = None


class CustomerCreate(CustomerBase):
    """Payload to create a new customer."""

    pass


class CustomerUpdate(BaseModel):
    """Payload to update an existing customer."""

    name: str | None = None
    phone: str | None = None
    email: str | None = None
    notes: str | None = None


class CustomerResponse(CustomerBase):
    """Response schema for a customer record."""

    id: str
    business_id: str
    total_calls: int = 0
    total_appointments: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomerDetailResponse(CustomerResponse):
    """Customer with recent call and appointment history."""

    calls: list[dict] = []
    appointments: list[dict] = []
