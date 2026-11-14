"""Availability Management API routes for Vattara Voice Assistance.

Provides full REST endpoints for managing:
- Weekly operating hours
- Daily break times
- Appointment rules and buffer settings
- Holidays
- Special date overrides
"""

import json
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db_session
from app.core.logging import get_logger
from app.models.assistant import AssistantConfig
from app.models.availability import (
    AvailabilitySetting,
    BusinessBreak,
    BusinessHoliday,
    SpecialDateOverride,
)
from app.models.business import Business
from app.models.business_hours import BusinessHour
from app.models.user import User
from app.schemas.availability import (
    AppointmentSettingsSchema,
    BreakItem,
    FullAvailabilityConfigResponse,
    FullAvailabilityUpdateRequest,
    HolidayItem,
    SpecialDateItem,
    WeeklyScheduleItem,
    WeeklyScheduleUpdateRequest,
)
from app.services.scheduling_service import (
    DAY_NAMES,
    get_all_operating_hours,
    get_or_create_availability_settings,
)

logger = get_logger(__name__)
router = APIRouter()


def _get_business_timezone_str(db: Session, business_id: str) -> str:
    biz = db.get(Business, business_id)
    return (biz.timezone if biz and biz.timezone else "Asia/Kolkata")


def _build_full_availability_response(db: Session, business_id: str) -> FullAvailabilityConfigResponse:
    tz_str = _get_business_timezone_str(db, business_id)

    # 1. Weekly schedule
    hours_items = get_all_operating_hours(db, business_id)
    weekly_schedule = [
        WeeklyScheduleItem(
            day_of_week=h.day_of_week,
            day_name=h.day_name,
            open_time=h.open_time,
            close_time=h.close_time,
            is_closed=h.is_closed,
        )
        for h in hours_items
    ]

    # 2. Breaks
    breaks_db = db.scalars(
        select(BusinessBreak)
        .where(BusinessBreak.business_id == business_id)
        .order_by(BusinessBreak.day_of_week.asc(), BusinessBreak.start_time.asc())
    ).all()
    breaks = [
        BreakItem(
            id=b.id,
            day_of_week=b.day_of_week,
            start_time=b.start_time,
            end_time=b.end_time,
            description=b.description or "",
            is_active=b.is_active,
        )
        for b in breaks_db
    ]

    # 3. Settings
    setting_db = get_or_create_availability_settings(db, business_id)
    settings = AppointmentSettingsSchema(
        default_duration_minutes=setting_db.default_duration_minutes,
        buffer_time_minutes=setting_db.buffer_time_minutes,
        min_advance_hours=setting_db.min_advance_hours,
        max_advance_days=setting_db.max_advance_days,
        same_day_booking=setting_db.same_day_booking,
        slot_interval_minutes=setting_db.slot_interval_minutes,
    )

    # 4. Holidays
    holidays_db = db.scalars(
        select(BusinessHoliday)
        .where(BusinessHoliday.business_id == business_id)
        .order_by(BusinessHoliday.holiday_date.asc())
    ).all()
    holidays = [
        HolidayItem(
            id=h.id,
            holiday_date=h.holiday_date,
            name=h.name,
            description=h.description,
        )
        for h in holidays_db
    ]

    # 5. Special Dates
    specials_db = db.scalars(
        select(SpecialDateOverride)
        .where(SpecialDateOverride.business_id == business_id)
        .order_by(SpecialDateOverride.override_date.asc())
    ).all()
    special_dates = [
        SpecialDateItem(
            id=s.id,
            override_date=s.override_date,
            is_closed=s.is_closed,
            open_time=s.open_time,
            close_time=s.close_time,
            description=s.description,
        )
        for s in specials_db
    ]

    return FullAvailabilityConfigResponse(
        business_id=business_id,
        timezone=tz_str,
        weekly_schedule=weekly_schedule,
        breaks=breaks,
        settings=settings,
        holidays=holidays,
        special_dates=special_dates,
    )


# ------------------------------------------------------------------------------
# 1. Full Availability (GET & PUT)
# ------------------------------------------------------------------------------
@router.get("", response_model=FullAvailabilityConfigResponse)
def get_availability(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> FullAvailabilityConfigResponse:
    """Retrieve complete availability configuration for the current tenant."""
    return _build_full_availability_response(db, current_user.business_id)


@router.put("", response_model=FullAvailabilityConfigResponse)
def update_full_availability(
    payload: FullAvailabilityUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> FullAvailabilityConfigResponse:
    """Batch-update the entire availability configuration in a single transaction."""
    business_id = current_user.business_id

    # 1. Weekly Schedule
    if payload.weekly_schedule is not None:
        hours_map = {}
        for item in payload.weekly_schedule:
            bh = db.scalar(
                select(BusinessHour).where(
                    BusinessHour.business_id == business_id,
                    BusinessHour.day_of_week == item.day_of_week,
                )
            )
            if not bh:
                bh = BusinessHour(
                    business_id=business_id,
                    day_of_week=item.day_of_week,
                    open_time=item.open_time,
                    close_time=item.close_time,
                    is_closed=item.is_closed,
                )
                db.add(bh)
            else:
                bh.open_time = item.open_time
                bh.close_time = item.close_time
                bh.is_closed = item.is_closed

            day_key = DAY_NAMES[item.day_of_week].lower()
            hours_map[day_key] = {
                "open": item.open_time,
                "close": item.close_time,
                "enabled": not item.is_closed,
            }

        # Sync to AssistantConfig.working_hours JSON
        cfg = db.scalar(select(AssistantConfig).where(AssistantConfig.business_id == business_id))
        if cfg:
            cfg.working_hours = json.dumps(hours_map)

    # 2. Settings
    if payload.settings is not None:
        settings_db = get_or_create_availability_settings(db, business_id)
        settings_db.default_duration_minutes = payload.settings.default_duration_minutes
        settings_db.buffer_time_minutes = payload.settings.buffer_time_minutes
        settings_db.min_advance_hours = payload.settings.min_advance_hours
        settings_db.max_advance_days = payload.settings.max_advance_days
        settings_db.same_day_booking = payload.settings.same_day_booking
        settings_db.slot_interval_minutes = payload.settings.slot_interval_minutes

    db.commit()
    return _build_full_availability_response(db, business_id)


# ------------------------------------------------------------------------------
# 2. Weekly Schedule
# ------------------------------------------------------------------------------
@router.put("/weekly-schedule", response_model=list[WeeklyScheduleItem])
def update_weekly_schedule(
    payload: WeeklyScheduleUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[WeeklyScheduleItem]:
    """Update weekly working schedule for all 7 days."""
    business_id = current_user.business_id
    hours_map = {}

    for item in payload.schedule:
        bh = db.scalar(
            select(BusinessHour).where(
                BusinessHour.business_id == business_id,
                BusinessHour.day_of_week == item.day_of_week,
            )
        )
        if not bh:
            bh = BusinessHour(
                business_id=business_id,
                day_of_week=item.day_of_week,
                open_time=item.open_time,
                close_time=item.close_time,
                is_closed=item.is_closed,
            )
            db.add(bh)
        else:
            bh.open_time = item.open_time
            bh.close_time = item.close_time
            bh.is_closed = item.is_closed

        day_key = DAY_NAMES[item.day_of_week].lower()
        hours_map[day_key] = {
            "open": item.open_time,
            "close": item.close_time,
            "enabled": not item.is_closed,
        }

    # Sync to AssistantConfig.working_hours JSON
    cfg = db.scalar(select(AssistantConfig).where(AssistantConfig.business_id == business_id))
    if cfg:
        cfg.working_hours = json.dumps(hours_map)

    db.commit()

    fresh = get_all_operating_hours(db, business_id)
    return [
        WeeklyScheduleItem(
            day_of_week=h.day_of_week,
            day_name=h.day_name,
            open_time=h.open_time,
            close_time=h.close_time,
            is_closed=h.is_closed,
        )
        for h in fresh
    ]


# ------------------------------------------------------------------------------
# 3. Breaks Management
# ------------------------------------------------------------------------------
@router.post("/breaks", response_model=BreakItem, status_code=status.HTTP_201_CREATED)
def add_break(
    payload: BreakItem,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> BreakItem:
    """Add a new scheduled break."""
    if payload.start_time >= payload.end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Break start time must be before end time.",
        )

    new_break = BusinessBreak(
        business_id=current_user.business_id,
        day_of_week=payload.day_of_week,
        start_time=payload.start_time,
        end_time=payload.end_time,
        description=payload.description or "Break",
        is_active=payload.is_active,
    )
    db.add(new_break)
    db.commit()
    db.refresh(new_break)

    return BreakItem(
        id=new_break.id,
        day_of_week=new_break.day_of_week,
        start_time=new_break.start_time,
        end_time=new_break.end_time,
        description=new_break.description or "",
        is_active=new_break.is_active,
    )


@router.delete("/breaks/{break_id}")
def delete_break(
    break_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> dict[str, Any]:
    """Delete a break by ID."""
    brk = db.scalar(
        select(BusinessBreak).where(
            BusinessBreak.id == break_id,
            BusinessBreak.business_id == current_user.business_id,
        )
    )
    if not brk:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Break not found.")

    db.delete(brk)
    db.commit()
    return {"success": True, "message": "Break deleted successfully."}


# ------------------------------------------------------------------------------
# 4. Settings Management
# ------------------------------------------------------------------------------
@router.put("/settings", response_model=AppointmentSettingsSchema)
def update_settings(
    payload: AppointmentSettingsSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> AppointmentSettingsSchema:
    """Update appointment rules, buffer time, advance limits, and interval."""
    settings_db = get_or_create_availability_settings(db, current_user.business_id)
    settings_db.default_duration_minutes = payload.default_duration_minutes
    settings_db.buffer_time_minutes = payload.buffer_time_minutes
    settings_db.min_advance_hours = payload.min_advance_hours
    settings_db.max_advance_days = payload.max_advance_days
    settings_db.same_day_booking = payload.same_day_booking
    settings_db.slot_interval_minutes = payload.slot_interval_minutes

    db.commit()
    db.refresh(settings_db)

    return AppointmentSettingsSchema(
        default_duration_minutes=settings_db.default_duration_minutes,
        buffer_time_minutes=settings_db.buffer_time_minutes,
        min_advance_hours=settings_db.min_advance_hours,
        max_advance_days=settings_db.max_advance_days,
        same_day_booking=settings_db.same_day_booking,
        slot_interval_minutes=settings_db.slot_interval_minutes,
    )


# ------------------------------------------------------------------------------
# 5. Holidays Management
# ------------------------------------------------------------------------------
@router.post("/holidays", response_model=HolidayItem, status_code=status.HTTP_201_CREATED)
def add_holiday(
    payload: HolidayItem,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> HolidayItem:
    """Add or update a holiday closure."""
    try:
        date.fromisoformat(payload.holiday_date)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid holiday_date format. Expected YYYY-MM-DD.",
        )

    # Check for existing holiday on same date
    existing = db.scalar(
        select(BusinessHoliday).where(
            BusinessHoliday.business_id == current_user.business_id,
            BusinessHoliday.holiday_date == payload.holiday_date,
        )
    )
    if existing:
        existing.name = payload.name
        existing.description = payload.description
        holiday = existing
    else:
        holiday = BusinessHoliday(
            business_id=current_user.business_id,
            holiday_date=payload.holiday_date,
            name=payload.name,
            description=payload.description,
        )
        db.add(holiday)

    db.commit()
    db.refresh(holiday)

    return HolidayItem(
        id=holiday.id,
        holiday_date=holiday.holiday_date,
        name=holiday.name,
        description=holiday.description,
    )


@router.delete("/holidays/{holiday_id}")
def delete_holiday(
    holiday_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> dict[str, Any]:
    """Delete a holiday closure by ID."""
    holiday = db.scalar(
        select(BusinessHoliday).where(
            BusinessHoliday.id == holiday_id,
            BusinessHoliday.business_id == current_user.business_id,
        )
    )
    if not holiday:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holiday not found.")

    db.delete(holiday)
    db.commit()
    return {"success": True, "message": "Holiday deleted successfully."}


# ------------------------------------------------------------------------------
# 6. Special Date Overrides Management
# ------------------------------------------------------------------------------
@router.post("/special-dates", response_model=SpecialDateItem, status_code=status.HTTP_201_CREATED)
def add_special_date(
    payload: SpecialDateItem,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> SpecialDateItem:
    """Add or update a date-specific hours override or full-day closure."""
    try:
        date.fromisoformat(payload.override_date)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid override_date format. Expected YYYY-MM-DD.",
        )

    if not payload.is_closed and (payload.open_time and payload.close_time):
        if payload.open_time >= payload.close_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Open time must be before close time.",
            )

    existing = db.scalar(
        select(SpecialDateOverride).where(
            SpecialDateOverride.business_id == current_user.business_id,
            SpecialDateOverride.override_date == payload.override_date,
        )
    )
    if existing:
        existing.is_closed = payload.is_closed
        existing.open_time = payload.open_time
        existing.close_time = payload.close_time
        existing.description = payload.description
        override = existing
    else:
        override = SpecialDateOverride(
            business_id=current_user.business_id,
            override_date=payload.override_date,
            is_closed=payload.is_closed,
            open_time=payload.open_time,
            close_time=payload.close_time,
            description=payload.description,
        )
        db.add(override)

    db.commit()
    db.refresh(override)

    return SpecialDateItem(
        id=override.id,
        override_date=override.override_date,
        is_closed=override.is_closed,
        open_time=override.open_time,
        close_time=override.close_time,
        description=override.description,
    )


@router.delete("/special-dates/{special_date_id}")
def delete_special_date(
    special_date_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> dict[str, Any]:
    """Delete a special date override by ID."""
    override = db.scalar(
        select(SpecialDateOverride).where(
            SpecialDateOverride.id == special_date_id,
            SpecialDateOverride.business_id == current_user.business_id,
        )
    )
    if not override:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Special date override not found.",
        )

    db.delete(override)
    db.commit()
    return {"success": True, "message": "Special date override deleted successfully."}
