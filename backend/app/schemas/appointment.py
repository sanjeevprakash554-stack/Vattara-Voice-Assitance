"""Pydantic schemas for Appointments."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.customer import CustomerResponse
from app.schemas.assistant import ServiceResponse


class AppointmentBase(BaseModel):
    """Base schema for appointment attributes."""

    customer_id: str
    service_id: str | None = None
    appointment_time: datetime
    end_time: datetime | None = None
    status: str = Field(
        default="upcoming",
        description="upcoming, completed, cancelled, rescheduled",
    )
    notes: str | None = None
    source: str = Field(default="ai_call", description="ai_call, manual, web")


class AppointmentCreate(AppointmentBase):
    """Payload to book an appointment."""

    customer_name: str | None = None
    customer_phone: str | None = None


class AppointmentUpdate(BaseModel):
    """Payload to update/reschedule an appointment."""

    appointment_time: datetime | None = None
    end_time: datetime | None = None
    status: str | None = None
    service_id: str | None = None
    notes: str | None = None


class AppointmentResponse(AppointmentBase):
    """Response schema for an appointment."""

    id: str
    business_id: str
    created_at: datetime
    updated_at: datetime
    customer: CustomerResponse | None = None
    service: ServiceResponse | None = None

    model_config = ConfigDict(from_attributes=True)

