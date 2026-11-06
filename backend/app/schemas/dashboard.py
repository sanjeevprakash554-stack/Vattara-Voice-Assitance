"""Pydantic schemas for Dashboard and Reports Analytics."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class DashboardStats(BaseModel):
    """Aggregate statistics for business dashboard."""

    total_incoming_calls: int = 0
    total_outgoing_calls: int = 0
    total_appointments: int = 0
    total_customers: int = 0
    successful_calls: int = 0
    missed_calls: int = 0
    active_assistant: bool = True
    upcoming_appointments_count: int = 0


class ActivityItem(BaseModel):
    """Activity feed event item."""

    id: str
    type: str  # call, appointment, reminder, customer
    title: str
    description: str
    status: str | None = None
    timestamp: datetime


class CallTrendPoint(BaseModel):
    """Data point for call volume trend chart."""

    date: str
    incoming: int = 0
    outgoing: int = 0
    missed: int = 0


class AppointmentStatusDistribution(BaseModel):
    """Data point for appointment breakdown chart."""

    status: str
    count: int


class CallDurationReport(BaseModel):
    """Call duration metric distribution."""

    range_label: str
    count: int


class AnalyticsOverview(BaseModel):
    """Comprehensive analytics response."""

    stats: DashboardStats
    call_trends: list[CallTrendPoint]
    appointment_breakdown: list[AppointmentStatusDistribution]
    duration_distribution: list[CallDurationReport]

