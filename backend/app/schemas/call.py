"""Pydantic schemas for Calls."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class CallBase(BaseModel):
    """Base schema for Call records."""

    caller_name: str | None = None
    caller_phone: str = Field(..., min_length=7, max_length=50)
    call_type: str = Field(default="incoming", description="incoming or outgoing")
    status: str = Field(default="completed", description="completed, missed, failed, in_progress")
    duration_seconds: int = Field(default=0, ge=0)
    summary: str | None = None
    transcript: str | None = None
    recording_url: str | None = None


class CallCreate(CallBase):
    """Payload to log a new call."""

    customer_id: str | None = None
    initiated_at: datetime | None = None
    ended_at: datetime | None = None


class CallSimulateRequest(BaseModel):
    """Payload to simulate an AI incoming or outgoing call."""

    caller_name: str = "Test Caller"
    caller_phone: str = "+919876543210"
    call_type: str = "incoming"
    scenario: str = "Appointment Inquiry"
    duration_seconds: int = 145


class CallResponse(CallBase):
    """Response schema for a call log entry."""

    id: str
    business_id: str
    customer_id: str | None = None
    initiated_at: datetime
    ended_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

