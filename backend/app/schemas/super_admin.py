"""Pydantic schemas for Platform-Level Super Administrator management."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class PlatformStats(BaseModel):
    total_businesses: int
    active_businesses: int
    inactive_businesses: int
    total_users: int
    total_calls: int
    total_appointments: int
    active_subscriptions: int
    trial_subscriptions: int
    plans_breakdown: dict[str, int]
    total_minutes_consumed: int


class TenantOverview(BaseModel):
    id: str
    name: str
    vertical: str
    phone: str
    email: str
    timezone: str
    is_active: bool
    user_count: int
    call_count: int
    appointment_count: int
    plan_name: str = "starter"
    subscription_status: str = "active"
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UpdateTenantSubscription(BaseModel):
    plan_name: str | None = None
    status: str | None = None
    monthly_call_minutes_limit: int | None = None
