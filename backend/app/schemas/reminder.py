"""Pydantic schemas for Reminders and Reminder Settings."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.customer import CustomerResponse


class ReminderBase(BaseModel):
    """Base schema for Reminders."""

    customer_id: str
    appointment_id: str | None = None
    reminder_type: str = Field(default="voice", description="voice, call, sms, whatsapp, email")
    scheduled_time: datetime
    status: str = Field(default="pending", description="pending, calling, completed, sent, failed, cancelled, retrying")
    message: str = Field(..., min_length=2)
    interval_tag: str | None = None


class ReminderCreate(ReminderBase):
    """Payload to create a reminder."""

    pass


class ReminderUpdate(BaseModel):
    """Payload to update a reminder."""

    reminder_type: str | None = None
    scheduled_time: datetime | None = None
    status: str | None = None
    message: str | None = None
    retry_count: int | None = None
    next_retry_at: datetime | None = None
    customer_response: str | None = None
    error_message: str | None = None


class ReminderResponse(ReminderBase):
    """Response schema for a reminder."""

    id: str
    business_id: str
    call_sid: str | None = None
    retry_count: int = 0
    max_retries: int = 3
    next_retry_at: datetime | None = None
    customer_response: str | None = None
    error_message: str | None = None
    sent_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    customer: CustomerResponse | None = None

    model_config = ConfigDict(from_attributes=True)


class ReminderSettingBase(BaseModel):
    """Base schema for tenant reminder settings."""

    reminder_intervals_hours: str = Field(default="24,2", description="Comma-separated hours before appointment (e.g. '24,2')")
    calling_start_time: str = Field(default="09:00", description="Local time start for calling window (HH:MM)")
    calling_end_time: str = Field(default="20:00", description="Local time end for calling window (HH:MM)")
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay_minutes: int = Field(default=15, ge=5, le=1440)
    is_enabled: bool = True
    default_channel: str = Field(default="voice", description="voice, sms, whatsapp")


class ReminderSettingUpdate(BaseModel):
    """Payload to update business reminder settings."""

    reminder_intervals_hours: str | None = None
    calling_start_time: str | None = None
    calling_end_time: str | None = None
    max_retries: int | None = None
    retry_delay_minutes: int | None = None
    is_enabled: bool | None = None
    default_channel: str | None = None


class ReminderSettingResponse(ReminderSettingBase):
    """Response schema for tenant reminder settings."""

    id: str
    business_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProcessDueRemindersResponse(BaseModel):
    """Summary result of processing due reminders."""

    processed_count: int
    called_count: int
    retried_count: int
    deferred_count: int
    failed_count: int
    details: list[dict] = Field(default_factory=list)
