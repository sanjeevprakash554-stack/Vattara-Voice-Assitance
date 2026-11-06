"""Pydantic schemas for Customer management and interaction history."""

from datetime import date, datetime, time
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CustomerCreateRequest(BaseModel):
    """Payload to create a new customer record."""

    customer_name: str = Field(..., min_length=1, max_length=255, description="Full customer name")
    phone_number: str = Field(..., min_length=5, max_length=50, description="Phone number used for caller matching")
    email: EmailStr | None = Field(default=None, description="Optional email address")
    address: str | None = Field(default=None, description="Physical address")
    notes: str | None = Field(default=None, description="Free-form customer background notes")


class CustomerUpdateRequest(BaseModel):
    """Payload to update an existing customer."""

    customer_name: str | None = Field(default=None, min_length=1, max_length=255)
    phone_number: str | None = Field(default=None, min_length=5, max_length=50)
    email: EmailStr | None = None
    address: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class CustomerResponse(BaseModel):
    """Public safe representation of a Customer entity."""

    id: int
    business_id: int
    customer_name: str
    phone_number: str
    email: str | None = None
    address: str | None = None
    notes: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomerAppointmentHistoryItem(BaseModel):
    """Historical appointment record summary for a customer."""

    id: int
    service_name: str
    appointment_date: date
    appointment_time: time
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomerCallHistoryItem(BaseModel):
    """Historical telephony / voice receptionist interaction record for a customer."""

    id: int
    phone_number: str
    call_type: str
    call_status: str
    call_duration: int
    recording_url: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomerHistoryResponse(BaseModel):
    """Comprehensive historical dossier for a customer."""

    customer: CustomerResponse
    appointments: list[CustomerAppointmentHistoryItem]
    call_history: list[CustomerCallHistoryItem]
    total_calls: int
    total_appointments: int
    last_interaction_date: datetime | None = None
