"""Pydantic schemas for Manual Availability Management."""

from pydantic import BaseModel, ConfigDict, Field


class WeeklyScheduleItem(BaseModel):
    """Configuration for a single day of the week."""

    day_of_week: int = Field(..., ge=0, le=6, description="0=Monday, ..., 6=Sunday")
    day_name: str = Field(default="", description="Monday, Tuesday, etc.")
    open_time: str = Field(default="09:00", description="'HH:MM' 24-hr format")
    close_time: str = Field(default="18:00", description="'HH:MM' 24-hr format")
    is_closed: bool = Field(default=False)

    model_config = ConfigDict(from_attributes=True)


class WeeklyScheduleUpdateRequest(BaseModel):
    """Payload to update weekly working hours."""

    schedule: list[WeeklyScheduleItem]


class BreakItem(BaseModel):
    """Break window definition."""

    id: str | None = None
    day_of_week: int = Field(
        default=-1, ge=-1, le=6, description="-1 = All Days, 0 = Monday, ..., 6 = Sunday"
    )
    start_time: str = Field(default="13:00", description="'HH:MM' 24-hr format")
    end_time: str = Field(default="14:00", description="'HH:MM' 24-hr format")
    description: str = Field(default="Lunch Break", max_length=200)
    is_active: bool = Field(default=True)

    model_config = ConfigDict(from_attributes=True)


class AppointmentSettingsSchema(BaseModel):
    """Appointment rules, buffer time, and advance limits."""

    default_duration_minutes: int = Field(default=30, ge=5, le=480)
    buffer_time_minutes: int = Field(default=10, ge=0, le=120)
    min_advance_hours: int = Field(default=2, ge=0, le=720)
    max_advance_days: int = Field(default=30, ge=1, le=365)
    same_day_booking: bool = Field(default=True)
    slot_interval_minutes: int = Field(default=30, ge=5, le=120)

    model_config = ConfigDict(from_attributes=True)


class HolidayItem(BaseModel):
    """Holiday closure date."""

    id: str | None = None
    holiday_date: str = Field(..., description="'YYYY-MM-DD' format")
    name: str = Field(..., max_length=200, description="Name or title of holiday")
    description: str | None = Field(default=None)

    model_config = ConfigDict(from_attributes=True)


class SpecialDateItem(BaseModel):
    """Date-specific hours override or closure."""

    id: str | None = None
    override_date: str = Field(..., description="'YYYY-MM-DD' format")
    is_closed: bool = Field(default=False, description="True if full-day closure")
    open_time: str | None = Field(default="09:00", description="'HH:MM' 24-hr format")
    close_time: str | None = Field(default="13:00", description="'HH:MM' 24-hr format")
    description: str | None = Field(default=None, description="Reason or label for override")

    model_config = ConfigDict(from_attributes=True)


class FullAvailabilityConfigResponse(BaseModel):
    """Unified availability management payload for frontend synchronization."""

    business_id: str
    timezone: str
    weekly_schedule: list[WeeklyScheduleItem]
    breaks: list[BreakItem]
    settings: AppointmentSettingsSchema
    holidays: list[HolidayItem]
    special_dates: list[SpecialDateItem]

    model_config = ConfigDict(from_attributes=True)


class FullAvailabilityUpdateRequest(BaseModel):
    """Unified payload to save entire availability configuration in a single transaction."""

    weekly_schedule: list[WeeklyScheduleItem] | None = None
    breaks: list[BreakItem] | None = None
    settings: AppointmentSettingsSchema | None = None
    holidays: list[HolidayItem] | None = None
    special_dates: list[SpecialDateItem] | None = None
