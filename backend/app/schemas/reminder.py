"""Pydantic schemas for Reminders."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.customer import CustomerResponse


class ReminderBase(BaseModel):
    """Base schema for Reminders."""

    customer_id: str
    appointment_id: str | None = None
    reminder_type: str = Field(default="sms", description="sms, voice, email, whatsapp")
    scheduled_time: datetime
    status: str = Field(default="pending", description="pending, sent, failed, cancelled")
    message: str = Field(..., min_length=2)


class ReminderCreate(ReminderBase):
    """Payload to create a reminder."""

    pass


class ReminderUpdate(BaseModel):
    """Payload to update a reminder."""

    reminder_type: str | None = None
    scheduled_time: datetime | None = None
    status: str | None = None
    message: str | None = None


class ReminderResponse(ReminderBase):
    """Response schema for a reminder."""

    id: str
    business_id: str
    sent_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    customer: CustomerResponse | None = None

    model_config = ConfigDict(from_attributes=True)

