"""Pydantic schemas for Appointments and Scheduling Engine."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.customer import CustomerResponse
from app.schemas.assistant import ServiceResponse


class AppointmentBase(BaseModel):
    """Base schema for appointment attributes."""

    customer_id: str | None = None
    service_id: str | None = None
    staff_id: str | None = None
    appointment_time: datetime
    end_time: datetime | None = None
    status: str = Field(
        default="upcoming",
        description="upcoming, completed, cancelled, rescheduled",
    )
    notes: str | None = None
    reschedule_reason: str | None = None
    cancel_reason: str | None = None
    source: str = Field(default="ai_call", description="ai_call, manual, web")


class AppointmentCreate(AppointmentBase):
    """Payload to book an appointment."""

    customer_name: str | None = None
    customer_phone: str | None = None


class ExotelAppointmentRequest(AppointmentCreate):
    """Payload for Exotel Voice Agent appointment gateway with optional integration key."""

    integration_key: str | None = Field(
        default=None,
        description="Secure integration secret key for Exotel server-to-server authentication",
    )


class AppointmentUpdate(BaseModel):
    """Payload to update an appointment."""

    appointment_time: datetime | None = None
    end_time: datetime | None = None
    status: str | None = None
    service_id: str | None = None
    staff_id: str | None = None
    notes: str | None = None
    reschedule_reason: str | None = None
    cancel_reason: str | None = None


class RescheduleRequest(BaseModel):
    """Payload to reschedule an appointment."""

    new_appointment_time: datetime = Field(
        ..., description="New target datetime for the rescheduled appointment."
    )
    reason: str | None = Field(
        default=None, description="Reason for rescheduling the appointment."
    )


class CancelAppointmentRequest(BaseModel):
    """Payload to cancel an appointment."""

    reason: str | None = Field(
        default=None, description="Reason for cancellation."
    )


class AppointmentResponse(AppointmentBase):
    """Response schema for an appointment."""

    id: str
    business_id: str
    created_at: datetime
    updated_at: datetime
    customer: CustomerResponse | None = None
    service: ServiceResponse | None = None

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# Availability & Slot Calculation Schemas
# ==============================================================================

class TimeSlot(BaseModel):
    """Calculated appointment slot."""

    time: str = Field(..., description="Local 24-hr time 'HH:MM'")
    start_time: datetime = Field(..., description="Timezone-aware start datetime ISO")
    end_time: datetime = Field(..., description="Timezone-aware end datetime ISO")
    duration_minutes: int
    available: bool
    reason: str | None = Field(
        default=None, description="Reason if slot is unavailable (e.g. 'Already booked', 'Past time')"
    )


class AvailabilityResponse(BaseModel):
    """Available slots calculation response."""

    date: str = Field(..., description="Target date 'YYYY-MM-DD'")
    business_id: str
    timezone: str
    is_open: bool
    operating_hours: dict[str, Any] = Field(
        default_factory=dict, description="Open, close and enabled status for target date"
    )
    service_id: str | None = None
    service_name: str | None = None
    duration_minutes: int
    staff_id: str | None = None
    staff_name: str | None = None
    slots: list[TimeSlot] = Field(default_factory=list)
    available_slots_count: int = 0
    total_slots_count: int = 0


# ==============================================================================
# Operating Hours & Staff Schemas
# ==============================================================================

class BusinessHourItem(BaseModel):
    """Operating hours for a specific day of the week."""

    day_of_week: int = Field(..., ge=0, le=6, description="0=Monday, ..., 6=Sunday")
    day_name: str = Field(..., description="Monday, Tuesday, etc.")
    open_time: str = Field(default="09:00", description="'HH:MM' 24-hr format")
    close_time: str = Field(default="18:00", description="'HH:MM' 24-hr format")
    is_closed: bool = Field(default=False)


class BusinessHoursResponse(BaseModel):
    """Complete weekly operating schedule."""

    business_id: str
    timezone: str
    schedule: list[BusinessHourItem]


class BusinessHoursUpdateRequest(BaseModel):
    """Weekly operating schedule update payload."""

    schedule: list[BusinessHourItem]


class StaffScheduleItem(BaseModel):
    """Staff working schedule."""

    id: str | None = None
    user_id: str | None = None
    staff_name: str
    day_of_week: int = Field(..., ge=0, le=6)
    start_time: str = "09:00"
    end_time: str = "17:00"
    break_start: str | None = None
    break_end: str | None = None
    slot_duration_minutes: int = 30
    is_active: bool = True


class StaffMemberResponse(BaseModel):
    """Staff/Doctor summary for appointment assignment."""

    id: str
    name: str
    email: str | None = None
    role: str
    is_active: bool
