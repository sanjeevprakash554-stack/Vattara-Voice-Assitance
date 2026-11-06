"""Pydantic schemas for Business Working Hours management."""

from datetime import datetime, time
from pydantic import BaseModel, ConfigDict, Field, model_validator


class WorkingHoursItem(BaseModel):
    """Single day schedule item (0=Monday, 6=Sunday)."""

    day_of_week: int = Field(..., ge=0, le=6, description="Day of week: 0=Monday through 6=Sunday")
    opening_time: time | None = Field(default=None, description="Opening time (e.g. 09:00:00)")
    closing_time: time | None = Field(default=None, description="Closing time (e.g. 17:00:00)")
    is_closed: bool = Field(default=False, description="True if business is closed on this day")

    @model_validator(mode="after")
    def validate_timings(self) -> "WorkingHoursItem":
        if not self.is_closed:
            if self.opening_time is None or self.closing_time is None:
                raise ValueError(
                    f"Day {self.day_of_week} is open but missing opening_time or closing_time."
                )
            if self.opening_time >= self.closing_time:
                raise ValueError(
                    f"Day {self.day_of_week}: opening_time ({self.opening_time}) must be earlier than closing_time ({self.closing_time})."
                )
        return self


class WorkingHoursResponse(BaseModel):
    """Working hours response representation."""

    id: int
    business_id: int
    day_of_week: int
    day_name: str
    opening_time: time | None = None
    closing_time: time | None = None
    is_closed: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkingHoursUpdateRequest(BaseModel):
    """Payload to create or update weekly working hours."""

    hours: list[WorkingHoursItem] = Field(
        ...,
        min_length=1,
        max_length=7,
        description="Weekly schedule items",
    )

    @model_validator(mode="after")
    def validate_no_duplicate_days(self) -> "WorkingHoursUpdateRequest":
        days = [h.day_of_week for h in self.hours]
        if len(days) != len(set(days)):
            raise ValueError("Duplicate day_of_week entries are not allowed.")
        return self
