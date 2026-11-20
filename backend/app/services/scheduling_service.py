"""Appointment availability, slot calculation, and scheduling conflict resolution engine."""

from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo
from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.appointment import Appointment
from app.models.assistant import AssistantConfig, Service
from app.models.availability import (
    AvailabilitySetting,
    BusinessBreak,
    BusinessHoliday,
    SpecialDateOverride,
)
from app.models.business import Business
from app.models.business_hours import BusinessHour
from app.models.customer import Customer
from app.models.staff_schedule import StaffSchedule
from app.models.user import User
from app.schemas.appointment import (
    AvailabilityResponse,
    BusinessHourItem,
    BusinessHoursResponse,
    TimeSlot,
)
from app.services.telephony.phone_utils import normalize_indian_mobile_number

logger = get_logger(__name__)

# Active statuses that reserve schedule capacity
ACTIVE_APPOINTMENT_STATUSES = ("upcoming", "scheduled", "confirmed", "rescheduled", "in_progress")

# Day names lookup
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


COMMON_TIMEZONES = {
    "Asia/Kolkata": timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata"),
    "UTC": timezone.utc,
    "America/New_York": timezone(timedelta(hours=-5), name="America/New_York"),
    "America/Chicago": timezone(timedelta(hours=-6), name="America/Chicago"),
    "America/Denver": timezone(timedelta(hours=-7), name="America/Denver"),
    "America/Los_Angeles": timezone(timedelta(hours=-8), name="America/Los_Angeles"),
    "Europe/London": timezone(timedelta(hours=0), name="Europe/London"),
    "Asia/Dubai": timezone(timedelta(hours=4), name="Asia/Dubai"),
    "Asia/Singapore": timezone(timedelta(hours=8), name="Asia/Singapore"),
}


def get_business_timezone(business: Business) -> timezone | ZoneInfo:
    """Resolve and return ZoneInfo or timezone fallback for the given Business tenant."""
    tz_str = business.timezone or "Asia/Kolkata"
    try:
        return ZoneInfo(tz_str)
    except Exception as exc:
        if tz_str in COMMON_TIMEZONES:
            return COMMON_TIMEZONES[tz_str]
        logger.warning("Invalid timezone '%s' for business %s: %s; falling back to UTC", tz_str, business.id, exc)
        return timezone.utc


def get_or_create_availability_settings(db: Session, business_id: str) -> AvailabilitySetting:
    """Retrieve or initialize default manual availability settings for a business."""
    setting = db.scalar(
        select(AvailabilitySetting).where(AvailabilitySetting.business_id == business_id)
    )
    if not setting:
        setting = AvailabilitySetting(
            business_id=business_id,
            default_duration_minutes=30,
            buffer_time_minutes=0,  # 0 by default for backwards compatibility; configurable via UI
            min_advance_hours=0,
            max_advance_days=60,
            same_day_booking=True,
            slot_interval_minutes=30,
        )
        db.add(setting)
        db.flush()
    return setting


def get_day_operating_hours(
    db: Session,
    business_id: str,
    day_of_week: int,
    target_date: date | None = None,
) -> dict[str, Any]:
    """Retrieve opening hours for a business on a specific day of the week, with holiday and special date override priority."""
    # 1. Holiday Check (Highest Priority: Full Day Closure)
    if target_date is not None:
        target_str = target_date.isoformat()
        holiday = db.scalar(
            select(BusinessHoliday).where(
                BusinessHoliday.business_id == business_id,
                BusinessHoliday.holiday_date == target_str,
            )
        )
        if holiday:
            return {
                "open": "00:00",
                "close": "00:00",
                "is_closed": True,
                "is_holiday": True,
                "holiday_name": holiday.name,
                "holiday_description": holiday.description or "",
            }

        # 2. Special Date Override Check (Takes precedence over normal weekly schedule)
        override = db.scalar(
            select(SpecialDateOverride).where(
                SpecialDateOverride.business_id == business_id,
                SpecialDateOverride.override_date == target_str,
            )
        )
        if override:
            return {
                "open": override.open_time or "09:00",
                "close": override.close_time or "18:00",
                "is_closed": override.is_closed,
                "is_special_date": True,
                "special_date_description": override.description or "",
            }

    # 3. Check structured business_hours table
    bh = db.scalar(
        select(BusinessHour).where(
            BusinessHour.business_id == business_id,
            BusinessHour.day_of_week == day_of_week,
        )
    )
    if bh:
        return {
            "open": bh.open_time,
            "close": bh.close_time,
            "is_closed": bh.is_closed,
        }

    # 4. Check assistant_configs working_hours JSON fallback
    cfg = db.scalar(
        select(AssistantConfig).where(AssistantConfig.business_id == business_id)
    )
    if cfg and cfg.working_hours:
        import json
        try:
            parsed = json.loads(cfg.working_hours)
            day_key = DAY_NAMES[day_of_week].lower()
            if day_key in parsed:
                day_cfg = parsed[day_key]
                return {
                    "open": day_cfg.get("open", "09:00"),
                    "close": day_cfg.get("close", "18:00"),
                    "is_closed": not day_cfg.get("enabled", True),
                }
        except Exception as e:
            logger.warning("Failed to parse working_hours JSON for business %s: %s", business_id, e)

    # 5. Default fallback: Mon-Sat 09:00 - 18:00; Sun closed
    if day_of_week == 6:
        return {"open": "10:00", "close": "14:00", "is_closed": True}
    return {"open": "09:00", "close": "18:00", "is_closed": False}


def get_all_operating_hours(db: Session, business_id: str) -> list[BusinessHourItem]:
    """Retrieve full 7-day operating hours schedule for a business."""
    items: list[BusinessHourItem] = []
    for dow in range(7):
        hours = get_day_operating_hours(db, business_id, dow)
        items.append(
            BusinessHourItem(
                day_of_week=dow,
                day_name=DAY_NAMES[dow],
                open_time=str(hours["open"]),
                close_time=str(hours["close"]),
                is_closed=bool(hours["is_closed"]),
            )
        )
    return items


def calculate_available_slots(
    db: Session,
    business_id: str,
    target_date: date,
    service_id: str | None = None,
    staff_id: str | None = None,
) -> AvailabilityResponse:
    """Calculate available, booked, and past time slots for a business on target_date."""
    business = db.get(Business, business_id)
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found.")

    biz_tz = get_business_timezone(business)
    dow = target_date.weekday()

    # Load Appointment Settings (duration, buffer, advance limits, same-day)
    settings = get_or_create_availability_settings(db, business_id)

    # 1. Resolve Service duration
    duration_minutes = settings.default_duration_minutes or 30
    service_name: str | None = None
    if service_id:
        srv = db.scalar(
            select(Service).where(Service.id == service_id, Service.business_id == business_id)
        )
        if srv:
            duration_minutes = max(10, srv.duration_minutes)
            service_name = srv.name
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Service '{service_id}' not found.")

    # 2. Resolve Operating Hours (Passing target_date checks holidays and special date overrides)
    hours = get_day_operating_hours(db, business_id, dow, target_date=target_date)
    is_closed = bool(hours["is_closed"])
    open_time_str = str(hours["open"])
    close_time_str = str(hours["close"])

    # Current local time for past slot detection
    now_local = datetime.now(biz_tz)

    # Check same-day booking constraint
    if not settings.same_day_booking and target_date == now_local.date():
        is_closed = True
        hours["is_closed"] = True
        hours["reason"] = "Same-day booking is disabled"

    # Check max advance booking constraint
    if target_date > now_local.date() + timedelta(days=settings.max_advance_days):
        is_closed = True
        hours["is_closed"] = True
        hours["reason"] = f"Booking not permitted beyond {settings.max_advance_days} days"

    # 3. Staff Specific Schedule Override (if staff_id provided)
    staff_name: str | None = None
    break_start_dt: datetime | None = None
    break_end_dt: datetime | None = None

    if staff_id:
        staff_user = db.scalar(
            select(User).where(User.id == staff_id, User.business_id == business_id)
        )
        if not staff_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found.")
        staff_name = staff_user.full_name

        staff_sched = db.scalar(
            select(StaffSchedule).where(
                StaffSchedule.business_id == business_id,
                StaffSchedule.user_id == staff_id,
                StaffSchedule.day_of_week == dow,
                StaffSchedule.is_active.is_(True),
            )
        )
        if staff_sched:
            open_time_str = staff_sched.start_time
            close_time_str = staff_sched.end_time
            if staff_sched.break_start and staff_sched.break_end:
                b_s_h, b_s_m = map(int, staff_sched.break_start.split(":"))
                b_e_h, b_e_m = map(int, staff_sched.break_end.split(":"))
                break_start_dt = datetime.combine(target_date, time(b_s_h, b_s_m), tzinfo=biz_tz)
                break_end_dt = datetime.combine(target_date, time(b_e_h, b_e_m), tzinfo=biz_tz)
        else:
            # Check if staff members have any schedule in business; if staff has schedules on other days but not today -> off
            has_any_sched = db.scalar(
                select(StaffSchedule).where(
                    StaffSchedule.business_id == business_id,
                    StaffSchedule.user_id == staff_id,
                    StaffSchedule.is_active.is_(True),
                ).limit(1)
            )
            if has_any_sched:
                is_closed = True

    if is_closed:
        return AvailabilityResponse(
            date=target_date.isoformat(),
            business_id=business_id,
            timezone=str(biz_tz),
            is_open=False,
            operating_hours=hours,
            service_id=service_id,
            service_name=service_name,
            duration_minutes=duration_minutes,
            staff_id=staff_id,
            staff_name=staff_name,
            slots=[],
            available_slots_count=0,
            total_slots_count=0,
        )

    # 4. Parse Day Boundaries in local timezone
    o_h, o_m = map(int, open_time_str.split(":"))
    c_h, c_m = map(int, close_time_str.split(":"))
    day_start = datetime.combine(target_date, time(o_h, o_m), tzinfo=biz_tz)
    day_close = datetime.combine(target_date, time(c_h, c_m), tzinfo=biz_tz)

    # 5. Fetch Business Breaks for this Day or All Days (-1)
    business_breaks = db.scalars(
        select(BusinessBreak).where(
            BusinessBreak.business_id == business_id,
            BusinessBreak.is_active.is_(True),
            or_(BusinessBreak.day_of_week == dow, BusinessBreak.day_of_week == -1),
        )
    ).all()
    break_windows = []
    for bb in business_breaks:
        try:
            bs_h, bs_m = map(int, bb.start_time.split(":"))
            be_h, be_m = map(int, bb.end_time.split(":"))
            b_s = datetime.combine(target_date, time(bs_h, bs_m), tzinfo=biz_tz)
            b_e = datetime.combine(target_date, time(be_h, be_m), tzinfo=biz_tz)
            break_windows.append((b_s, b_e, bb.description))
        except Exception:
            continue

    # 6. Fetch Active Appointments for this Day
    day_start_utc = day_start.astimezone(timezone.utc)
    day_end_utc = day_close.astimezone(timezone.utc)

    stmt = (
        select(Appointment)
        .where(
            Appointment.business_id == business_id,
            Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
            Appointment.appointment_time >= day_start_utc - timedelta(hours=3),
            Appointment.appointment_time <= day_end_utc + timedelta(hours=3),
        )
    )
    if staff_id:
        stmt = stmt.where(or_(Appointment.staff_id == staff_id, Appointment.staff_id.is_(None)))

    existing_appts = db.scalars(stmt).all()

    # 7. Generate Discrete Slots
    step_minutes = settings.slot_interval_minutes if settings.slot_interval_minutes > 0 else max(15, min(duration_minutes, 30))
    buffer_mins = settings.buffer_time_minutes if settings.buffer_time_minutes > 0 else 0
    min_advance = settings.min_advance_hours if settings.min_advance_hours > 0 else 0

    slots: list[TimeSlot] = []
    current_slot_start = day_start

    while current_slot_start + timedelta(minutes=duration_minutes) <= day_close:
        current_slot_end = current_slot_start + timedelta(minutes=duration_minutes)
        slot_start_utc = current_slot_start.astimezone(timezone.utc)
        slot_end_utc = current_slot_end.astimezone(timezone.utc)

        is_avail = True
        unavailable_reason: str | None = None

        # Check A: Past Time & Advance Notice
        earliest_allowed = now_local + timedelta(hours=min_advance)
        if current_slot_start < earliest_allowed:
            is_avail = False
            unavailable_reason = "Past time" if current_slot_start < now_local else f"Requires {min_advance}h advance notice"

        # Check B: Business Breaks
        elif break_windows:
            for b_s, b_e, b_desc in break_windows:
                if current_slot_start < b_e and current_slot_end > b_s:
                    is_avail = False
                    unavailable_reason = f"Break ({b_desc})"
                    break

        # Check C: Staff Break
        if is_avail and break_start_dt and break_end_dt:
            if current_slot_start < break_end_dt and current_slot_end > break_start_dt:
                is_avail = False
                unavailable_reason = "Staff break"

        # Check D: Overlapping Active Appointments (with buffer time)
        if is_avail:
            for appt in existing_appts:
                # Resolve appointment end time
                appt_start = appt.appointment_time
                if appt_start.tzinfo is None:
                    appt_start = appt_start.replace(tzinfo=timezone.utc)

                appt_end = appt.end_time
                if appt_end is None:
                    appt_dur = appt.service.duration_minutes if appt.service else 30
                    appt_end = appt_start + timedelta(minutes=appt_dur)
                elif appt_end.tzinfo is None:
                    appt_end = appt_end.replace(tzinfo=timezone.utc)

                eff_appt_start = appt_start - timedelta(minutes=buffer_mins)
                eff_appt_end = appt_end + timedelta(minutes=buffer_mins)

                # Overlap test: slot_start < eff_appt_end and slot_end > eff_appt_start
                if slot_start_utc < eff_appt_end and slot_end_utc > eff_appt_start:
                    is_avail = False
                    unavailable_reason = "Already booked"
                    break

        slots.append(
            TimeSlot(
                time=current_slot_start.strftime("%H:%M"),
                start_time=current_slot_start,
                end_time=current_slot_end,
                duration_minutes=duration_minutes,
                available=is_avail,
                reason=unavailable_reason,
            )
        )

        current_slot_start += timedelta(minutes=step_minutes)

    available_count = sum(1 for s in slots if s.available)

    return AvailabilityResponse(
        date=target_date.isoformat(),
        business_id=business_id,
        timezone=str(biz_tz),
        is_open=True,
        operating_hours=hours,
        service_id=service_id,
        service_name=service_name,
        duration_minutes=duration_minutes,
        staff_id=staff_id,
        staff_name=staff_name,
        slots=slots,
        available_slots_count=available_count,
        total_slots_count=len(slots),
    )


def validate_booking_feasibility(
    db: Session,
    business_id: str,
    appointment_time: datetime,
    service_id: str | None = None,
    staff_id: str | None = None,
    customer_id: str | None = None,
    customer_phone: str | None = None,
    exclude_appointment_id: str | None = None,
    enforce_operating_hours: bool = True,
    enforce_past_check: bool = True,
) -> tuple[datetime, datetime, int]:
    """Validate appointment feasibility, conflict avoidance, operating hours, and service duration."""
    business = db.get(Business, business_id)
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found.")

    biz_tz = get_business_timezone(business)

    # Load Appointment Settings (duration, buffer, advance limits, same-day)
    settings = get_or_create_availability_settings(db, business_id)

    # 1. Ensure timezone-aware datetime
    if appointment_time.tzinfo is None:
        appointment_time = appointment_time.replace(tzinfo=biz_tz)

    appointment_time_utc = appointment_time.astimezone(timezone.utc)
    local_appt = appointment_time.astimezone(biz_tz)

    # 2. Priority 2: Strictly validate appointment is not in the past
    if enforce_past_check:
        now_utc = datetime.now(timezone.utc)
        if appointment_time_utc < now_utc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot book appointments in the past.",
            )

    # 3. Validate service duration
    duration_minutes = settings.default_duration_minutes or 30
    if service_id:
        srv = db.scalar(
            select(Service).where(Service.id == service_id, Service.business_id == business_id)
        )
        if not srv:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Service ID '{service_id}' not found for this business.",
            )
        duration_minutes = max(10, srv.duration_minutes)

    end_time_utc = appointment_time_utc + timedelta(minutes=duration_minutes)
    local_end = local_appt + timedelta(minutes=duration_minutes)

    # 4. Validate Business Operating Hours, Holidays, Special Dates & Advance Rules
    if enforce_operating_hours:
        dow = local_appt.weekday()

        # Check Holiday Closure
        holiday = db.scalar(
            select(BusinessHoliday).where(
                BusinessHoliday.business_id == business_id,
                BusinessHoliday.holiday_date == local_appt.date().isoformat(),
            )
        )
        if holiday:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Business is closed for holiday: {holiday.name} on {local_appt.date().isoformat()}.",
            )

        # Check Special Date Override Closure
        override = db.scalar(
            select(SpecialDateOverride).where(
                SpecialDateOverride.business_id == business_id,
                SpecialDateOverride.override_date == local_appt.date().isoformat(),
            )
        )
        if override and override.is_closed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Business is closed on {local_appt.date().isoformat()} ({override.description or 'Special closure'}).",
            )

        # Check same-day booking constraint
        if not settings.same_day_booking and local_appt.date() == datetime.now(biz_tz).date():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Same-day appointments are not permitted by business settings.",
            )

        # Check minimum advance notice
        if enforce_past_check and settings.min_advance_hours > 0:
            min_allowed = datetime.now(biz_tz) + timedelta(hours=settings.min_advance_hours)
            if local_appt < min_allowed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Appointments require at least {settings.min_advance_hours} hours advance notice.",
                )

        # Check maximum advance booking
        max_allowed = datetime.now(biz_tz).date() + timedelta(days=settings.max_advance_days)
        if local_appt.date() > max_allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot book appointments more than {settings.max_advance_days} days in advance.",
            )

        # Operating hours check (with special date override support)
        hours = get_day_operating_hours(db, business_id, dow, target_date=local_appt.date())
        if hours["is_closed"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Business is closed on {DAY_NAMES[dow]}s.",
            )

        o_h, o_m = map(int, str(hours["open"]).split(":"))
        c_h, c_m = map(int, str(hours["close"]).split(":"))
        day_open = datetime.combine(local_appt.date(), time(o_h, o_m), tzinfo=biz_tz)
        day_close = datetime.combine(local_appt.date(), time(c_h, c_m), tzinfo=biz_tz)

        if local_appt < day_open or local_end > day_close:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Appointment time ({local_appt.strftime('%H:%M')} - {local_end.strftime('%H:%M')}) "
                    f"falls outside operating hours ({hours['open']} - {hours['close']}) on {DAY_NAMES[dow]}."
                ),
            )

        # Validate Business Breaks
        biz_breaks = db.scalars(
            select(BusinessBreak).where(
                BusinessBreak.business_id == business_id,
                BusinessBreak.is_active.is_(True),
                or_(BusinessBreak.day_of_week == dow, BusinessBreak.day_of_week == -1),
            )
        ).all()
        for bb in biz_breaks:
            b_s_h, b_s_m = map(int, bb.start_time.split(":"))
            b_e_h, b_e_m = map(int, bb.end_time.split(":"))
            b_start = datetime.combine(local_appt.date(), time(b_s_h, b_s_m), tzinfo=biz_tz)
            b_end = datetime.combine(local_appt.date(), time(b_e_h, b_e_m), tzinfo=biz_tz)
            if local_appt < b_end and local_end > b_start:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Requested appointment time ({local_appt.strftime('%H:%M')} - {local_end.strftime('%H:%M')}) conflicts with scheduled {bb.description} ({bb.start_time} - {bb.end_time}).",
                )

        # 5. Validate Staff Schedule & Breaks (if staff specified)
        if staff_id:
            sched = db.scalar(
                select(StaffSchedule).where(
                    StaffSchedule.business_id == business_id,
                    StaffSchedule.user_id == staff_id,
                    StaffSchedule.day_of_week == dow,
                    StaffSchedule.is_active.is_(True),
                )
            )
            if sched:
                s_o_h, s_o_m = map(int, sched.start_time.split(":"))
                s_c_h, s_c_m = map(int, sched.end_time.split(":"))
                staff_open = datetime.combine(local_appt.date(), time(s_o_h, s_o_m), tzinfo=biz_tz)
                staff_close = datetime.combine(local_appt.date(), time(s_c_h, s_c_m), tzinfo=biz_tz)
                if local_appt < staff_open or local_end > staff_close:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Requested time is outside {sched.staff_name}'s shift ({sched.start_time} - {sched.end_time}).",
                    )
                if sched.break_start and sched.break_end:
                    b_s_h, b_s_m = map(int, sched.break_start.split(":"))
                    b_e_h, b_e_m = map(int, sched.break_end.split(":"))
                    break_start = datetime.combine(local_appt.date(), time(b_s_h, b_s_m), tzinfo=biz_tz)
                    break_end = datetime.combine(local_appt.date(), time(b_e_h, b_e_m), tzinfo=biz_tz)
                    if local_appt < break_end and local_end > break_start:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Requested time conflicts with {sched.staff_name}'s break ({sched.break_start} - {sched.break_end}).",
                        )

    # 6. Prevent Duplicate Appointments (Same customer at the exact time)
    if customer_id or customer_phone:
        dup_stmt = (
            select(Appointment)
            .join(Customer, Appointment.customer_id == Customer.id)
            .where(
                Appointment.business_id == business_id,
                Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
                Appointment.appointment_time == appointment_time_utc,
            )
        )
        norm_p = normalize_indian_mobile_number(customer_phone) if customer_phone else None
        raw_p = customer_phone.strip() if customer_phone else None
        phone_variants = set()
        if norm_p:
            phone_variants.add(norm_p)
            phone_variants.add(norm_p.replace("+91", "91"))
            phone_variants.add(norm_p.replace("+91", ""))
        if raw_p:
            phone_variants.add(raw_p)

        match_conds = []
        if customer_id and customer_id != "new":
            match_conds.append(Appointment.customer_id == customer_id)
        if phone_variants:
            match_conds.append(Customer.phone.in_(list(phone_variants)))

        if match_conds:
            dup_stmt = dup_stmt.where(or_(*match_conds))

        if exclude_appointment_id:
            dup_stmt = dup_stmt.where(Appointment.id != exclude_appointment_id)

        existing_dup = db.scalar(dup_stmt)
        if existing_dup:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Customer already has an appointment booked at this exact time.",
            )

    # 7. Prevent Overlapping Appointments (with buffer time protection)
    buffer_mins = settings.buffer_time_minutes if settings.buffer_time_minutes > 0 else 0
    overlap_stmt = (
        select(Appointment)
        .where(
            Appointment.business_id == business_id,
            Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
            Appointment.appointment_time >= appointment_time_utc - timedelta(hours=4),
            Appointment.appointment_time <= end_time_utc + timedelta(hours=4),
        )
    )
    if exclude_appointment_id:
        overlap_stmt = overlap_stmt.where(Appointment.id != exclude_appointment_id)
    if staff_id:
        overlap_stmt = overlap_stmt.where(or_(Appointment.staff_id == staff_id, Appointment.staff_id.is_(None)))

    potential_overlaps = db.scalars(overlap_stmt).all()
    for existing in potential_overlaps:
        e_start = existing.appointment_time
        if e_start.tzinfo is None:
            e_start = e_start.replace(tzinfo=timezone.utc)

        e_end = existing.end_time
        if e_end is None:
            e_dur = existing.service.duration_minutes if existing.service else 30
            e_end = e_start + timedelta(minutes=e_dur)
        elif e_end.tzinfo is None:
            e_end = e_end.replace(tzinfo=timezone.utc)

        eff_start = e_start - timedelta(minutes=buffer_mins)
        eff_end = e_end + timedelta(minutes=buffer_mins)

        # Overlap interval formula with buffer: start_A < eff_end and end_A > eff_start
        if appointment_time_utc < eff_end and end_time_utc > eff_start:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The selected time slot overlaps with an existing booking or buffer period.",
            )

    return appointment_time_utc, end_time_utc, duration_minutes


def find_alternative_slots(
    db: Session,
    business_id: str,
    target_date: date,
    preferred_time_str: str | None = None,
    service_id: str | None = None,
    staff_id: str | None = None,
    max_suggestions: int = 4,
    days_ahead: int = 7,
    limit_per_day: int | None = None,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """Scan availability for nearest open slots on target_date and subsequent working days."""
    suggestions: list[dict[str, Any]] = []
    curr_date = target_date
    days_checked = 0
    max_days = max(1, min(days_ahead, 14))

    while len(suggestions) < max_suggestions and days_checked < max_days:
        try:
            avail = calculate_available_slots(
                db=db,
                business_id=business_id,
                target_date=curr_date,
                service_id=service_id,
                staff_id=staff_id,
            )
            if avail.is_open:
                day_added = 0
                for slot in avail.slots:
                    if slot.available:
                        suggestions.append({
                            "date": curr_date.isoformat(),
                            "time": slot.time,
                            "datetime": slot.start_time.isoformat(),
                            "day_name": DAY_NAMES[curr_date.weekday()],
                        })
                        day_added += 1
                        if limit_per_day and day_added >= limit_per_day:
                            break
                        if len(suggestions) >= max_suggestions:
                            break
        except Exception as exc:
            logger.warning("Error calculating slots for alternative search on %s: %s", curr_date, exc)
        curr_date += timedelta(days=1)
        days_checked += 1

    return suggestions


def reschedule_appointment_core(
    db: Session,
    business_id: str,
    appointment_id: str,
    new_appointment_time: datetime,
    reason: str | None = None,
) -> Appointment:
    """Core logic to validate and reschedule an existing appointment to a new slot."""
    appt = db.scalar(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.business_id == business_id,
        )
    )
    if not appt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found.",
        )

    if appt.status in ("cancelled", "completed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reschedule an appointment that is already {appt.status}.",
        )

    # Validate feasibility of new slot excluding current appointment
    new_start_utc, new_end_utc, _ = validate_booking_feasibility(
        db=db,
        business_id=business_id,
        appointment_time=new_appointment_time,
        service_id=appt.service_id,
        staff_id=appt.staff_id,
        customer_id=appt.customer_id,
        exclude_appointment_id=appointment_id,
        enforce_operating_hours=True,
        enforce_past_check=True,
    )

    appt.appointment_time = new_start_utc
    appt.end_time = new_end_utc
    appt.status = "rescheduled"
    if reason:
        appt.reschedule_reason = reason
        appt.notes = f"{appt.notes or ''} [Rescheduled: {reason}]".strip()

    db.commit()
    db.refresh(appt)
    logger.info("Rescheduled appointment %s to %s for business %s", appt.id, new_start_utc, business_id)

    # Phase 6: Sync reminder schedules after rescheduling
    try:
        from app.services.reminder_service import reschedule_appointment_reminders
        reschedule_appointment_reminders(db, appt)
    except Exception as exc:
        logger.warning("Rescheduling reminders sync skipped: %s", exc)

    return appt


def cancel_appointment_core(
    db: Session,
    business_id: str,
    appointment_id: str,
    reason: str | None = None,
) -> Appointment:
    """Cancel an appointment and free its slot."""
    appt = db.scalar(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.business_id == business_id,
        )
    )
    if not appt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found.",
        )

    appt.status = "cancelled"
    if reason:
        appt.cancel_reason = reason
        appt.notes = f"{appt.notes or ''} [Cancelled: {reason}]".strip()

    db.commit()
    db.refresh(appt)
    logger.info("Cancelled appointment %s for business %s", appt.id, business_id)

    # Phase 6: Cancel pending reminders for this appointment
    try:
        from app.services.reminder_service import cancel_appointment_reminders
        cancel_appointment_reminders(db, appt.id)
    except Exception as exc:
        logger.warning("Cancelling reminders sync skipped: %s", exc)

    return appt
