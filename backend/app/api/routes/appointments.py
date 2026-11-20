"""Appointment Management and Scheduling routes."""

import re
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db_session
from app.models.appointment import Appointment
from app.models.business import Business
from app.models.business_hours import BusinessHour
from app.models.call import Call
from app.models.staff_schedule import StaffSchedule
from app.models.user import User
from app.schemas.appointment import (
    AppointmentCallDetail,
    AppointmentCreate,
    AppointmentResponse,
    AppointmentUpdate,
    AvailabilityResponse,
    BusinessHourItem,
    BusinessHoursResponse,
    BusinessHoursUpdateRequest,
    CancelAppointmentRequest,
    RescheduleRequest,
    StaffMemberResponse,
    StaffScheduleItem,
)
from app.services.appointment_service import book_appointment_core
from app.services.dashboard_events import dashboard_event_manager
from app.services.scheduling_service import (
    calculate_available_slots,
    cancel_appointment_core,
    get_all_operating_hours,
    get_business_timezone,
    reschedule_appointment_core,
)

router = APIRouter()


# ==============================================================================
# 1. Availability & Slot Calculation
# ==============================================================================

@router.get("/availability/slots", response_model=AvailabilityResponse)
def get_appointment_slots(
    target_date_str: str = Query(..., alias="date", description="Target date in 'YYYY-MM-DD' format"),
    service_id: str | None = Query(None, description="Service ID to calculate custom duration"),
    staff_id: str | None = Query(None, description="Doctor/Staff ID to filter assigned availability"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> AvailabilityResponse:
    """Calculate discrete available time slots for the business on a specific date."""
    try:
        target_date = date.fromisoformat(target_date_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Expected 'YYYY-MM-DD'.",
        )

    return calculate_available_slots(
        db=db,
        business_id=current_user.business_id,
        target_date=target_date,
        service_id=service_id,
        staff_id=staff_id,
    )


# ==============================================================================
# 2. Operating Hours Management
# ==============================================================================

@router.get("/operating-hours", response_model=BusinessHoursResponse)
def get_business_operating_hours(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> BusinessHoursResponse:
    """Retrieve full weekly operating schedule for the current business."""
    business = db.get(Business, current_user.business_id)
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found.")

    schedule = get_all_operating_hours(db, current_user.business_id)
    return BusinessHoursResponse(
        business_id=current_user.business_id,
        timezone=business.timezone,
        schedule=schedule,
    )


@router.put("/operating-hours", response_model=BusinessHoursResponse)
def update_business_operating_hours(
    payload: BusinessHoursUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> BusinessHoursResponse:
    """Update weekly operating schedule for the current business."""
    business = db.get(Business, current_user.business_id)
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found.")

    for item in payload.schedule:
        bh = db.scalar(
            select(BusinessHour).where(
                BusinessHour.business_id == current_user.business_id,
                BusinessHour.day_of_week == item.day_of_week,
            )
        )
        if not bh:
            bh = BusinessHour(
                business_id=current_user.business_id,
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

    db.commit()
    return BusinessHoursResponse(
        business_id=current_user.business_id,
        timezone=business.timezone,
        schedule=get_all_operating_hours(db, current_user.business_id),
    )


# ==============================================================================
# 3. Staff & Schedules
# ==============================================================================

@router.get("/staff", response_model=list[StaffMemberResponse])
def list_business_staff(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[StaffMemberResponse]:
    """List staff members and doctors available for appointments."""
    users = db.scalars(
        select(User).where(
            User.business_id == current_user.business_id,
            User.is_active.is_(True),
        ).order_by(User.full_name.asc())
    ).all()

    return [
        StaffMemberResponse(
            id=u.id,
            name=u.full_name,
            email=u.email,
            role=u.role,
            is_active=u.is_active,
        )
        for u in users
    ]


@router.get("/staff-schedules", response_model=list[StaffScheduleItem])
def list_staff_schedules(
    staff_id: str | None = Query(None, description="Optional filter by staff user_id"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[StaffScheduleItem]:
    """Retrieve staff availability shifts and breaks."""
    stmt = (
        select(StaffSchedule)
        .where(
            StaffSchedule.business_id == current_user.business_id,
            StaffSchedule.is_active.is_(True),
        )
        .order_by(StaffSchedule.day_of_week.asc())
    )
    if staff_id:
        stmt = stmt.where(StaffSchedule.user_id == staff_id)

    schedules = db.scalars(stmt).all()
    return [
        StaffScheduleItem(
            id=s.id,
            user_id=s.user_id,
            staff_name=s.staff_name,
            day_of_week=s.day_of_week,
            start_time=s.start_time,
            end_time=s.end_time,
            break_start=s.break_start,
            break_end=s.break_end,
            slot_duration_minutes=s.slot_duration_minutes,
            is_active=s.is_active,
        )
        for s in schedules
    ]


@router.post("/staff-schedules", response_model=StaffScheduleItem, status_code=status.HTTP_201_CREATED)
def create_staff_schedule(
    payload: StaffScheduleItem,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> StaffScheduleItem:
    """Add a new staff working shift or availability schedule."""
    schedule = StaffSchedule(
        business_id=current_user.business_id,
        user_id=payload.user_id,
        staff_name=payload.staff_name,
        day_of_week=payload.day_of_week,
        start_time=payload.start_time,
        end_time=payload.end_time,
        break_start=payload.break_start,
        break_end=payload.break_end,
        slot_duration_minutes=payload.slot_duration_minutes,
        is_active=payload.is_active,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return StaffScheduleItem(
        id=schedule.id,
        user_id=schedule.user_id,
        staff_name=schedule.staff_name,
        day_of_week=schedule.day_of_week,
        start_time=schedule.start_time,
        end_time=schedule.end_time,
        break_start=schedule.break_start,
        break_end=schedule.break_end,
        slot_duration_minutes=schedule.slot_duration_minutes,
        is_active=schedule.is_active,
    )


# ==============================================================================
# 4. Standard Appointment CRUD & Action Endpoints
# ==============================================================================

@router.get("", response_model=list[AppointmentResponse])
def list_appointments(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[AppointmentResponse]:
    """List appointments for the business with optional status filter and linked telephony calls."""
    stmt = (
        select(Appointment)
        .where(Appointment.business_id == current_user.business_id)
        .order_by(Appointment.appointment_time.desc())
    )

    if status_filter:
        stmt = stmt.where(Appointment.status == status_filter)

    stmt = stmt.offset(offset).limit(limit)
    appointments = db.scalars(stmt).all()

    # Pre-fetch recent calls for this business to attach call information
    recent_calls = db.scalars(
        select(Call)
        .where(Call.business_id == current_user.business_id)
        .order_by(Call.created_at.desc())
        .limit(100)
    ).all()
    calls_by_id = {c.id: c for c in recent_calls}

    results: list[AppointmentResponse] = []
    for a in appointments:
        resp = AppointmentResponse.model_validate(a)
        matched_call = None
        if a.notes:
            sid_match = re.search(r"CallSid:\s*([a-f0-9\-]+)", a.notes)
            if sid_match and sid_match.group(1) in calls_by_id:
                matched_call = calls_by_id[sid_match.group(1)]
        if not matched_call:
            for c in recent_calls:
                if a.id in (c.summary or ""):
                    matched_call = c
                    break
        if matched_call:
            resp.call = AppointmentCallDetail.model_validate(matched_call)
        results.append(resp)

    return results


@router.get("/{appointment_id}", response_model=AppointmentResponse)
def get_appointment(
    appointment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> AppointmentResponse:
    """Get single appointment details including associated voice call information."""
    appt = db.scalar(
        select(Appointment).where(
            Appointment.id == appointment_id, Appointment.business_id == current_user.business_id
        )
    )
    if not appt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")

    resp = AppointmentResponse.model_validate(appt)

    # Search for associated Call record
    call_rec = None
    if appt.notes:
        sid_match = re.search(r"CallSid:\s*([a-f0-9\-]+)", appt.notes)
        if sid_match:
            call_rec = db.get(Call, sid_match.group(1))
    if not call_rec:
        call_rec = db.scalar(
            select(Call).where(
                Call.business_id == current_user.business_id,
                Call.summary.like(f"%{appt.id}%"),
            )
        )
    if call_rec:
        resp.call = AppointmentCallDetail.model_validate(call_rec)

    return resp


@router.post("", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
def create_appointment(
    payload: AppointmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> AppointmentResponse:
    """Create a new appointment with conflict detection, operating hours, and service duration validation."""
    biz = db.get(Business, current_user.business_id)
    biz_tz = get_business_timezone(biz) if biz else timezone.utc

    appt_time = payload.appointment_time
    if appt_time.tzinfo is None:
        appt_time = appt_time.replace(tzinfo=biz_tz)
    payload.appointment_time = appt_time

    appt = book_appointment_core(
        db=db,
        business_id=current_user.business_id,
        payload=payload,
        validate_conflicts=True,
        enforce_operating_hours=True,
        enforce_past_check=True,
    )
    dashboard_event_manager.dispatch(
        business_id=current_user.business_id,
        event_type="APPOINTMENT_CREATED",
        data={
            "appointment_id": appt.id,
            "customer_id": appt.customer_id,
            "customer_name": appt.customer.name if appt.customer else None,
            "service_id": appt.service_id,
            "service_name": appt.service.name if appt.service else None,
            "appointment_time": appt.appointment_time.isoformat(),
            "status": appt.status,
            "source": appt.source,
        },
    )
    return AppointmentResponse.model_validate(appt)


@router.put("/{appointment_id}", response_model=AppointmentResponse)
def update_appointment(
    appointment_id: str,
    payload: AppointmentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> AppointmentResponse:
    """Update or reschedule an appointment."""
    if payload.appointment_time is not None:
        rescheduled_appt = reschedule_appointment_core(
            db=db,
            business_id=current_user.business_id,
            appointment_id=appointment_id,
            new_appointment_time=payload.appointment_time,
            reason=payload.reschedule_reason or payload.notes,
        )
        dashboard_event_manager.dispatch(
            business_id=current_user.business_id,
            event_type="APPOINTMENT_UPDATED",
            data={
                "appointment_id": rescheduled_appt.id,
                "status": rescheduled_appt.status,
                "appointment_time": rescheduled_appt.appointment_time.isoformat(),
                "reason": rescheduled_appt.reschedule_reason,
            },
        )
        return AppointmentResponse.model_validate(rescheduled_appt)

    appt = db.scalar(
        select(Appointment).where(
            Appointment.id == appointment_id, Appointment.business_id == current_user.business_id
        )
    )
    if not appt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")

    if payload.end_time is not None:
        appt.end_time = payload.end_time
    if payload.status is not None:
        appt.status = payload.status
    if payload.service_id is not None:
        appt.service_id = payload.service_id
    if payload.staff_id is not None:
        appt.staff_id = payload.staff_id
    if payload.notes is not None:
        appt.notes = payload.notes

    db.commit()
    db.refresh(appt)

    dashboard_event_manager.dispatch(
        business_id=current_user.business_id,
        event_type="APPOINTMENT_UPDATED",
        data={
            "appointment_id": appt.id,
            "status": appt.status,
            "appointment_time": appt.appointment_time.isoformat(),
            "notes": appt.notes,
        },
    )
    return AppointmentResponse.model_validate(appt)


@router.post("/{appointment_id}/reschedule", response_model=AppointmentResponse)
def reschedule_appointment(
    appointment_id: str,
    payload: RescheduleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> AppointmentResponse:
    """Dedicated endpoint to reschedule an appointment with full slot conflict validation."""
    appt = reschedule_appointment_core(
        db=db,
        business_id=current_user.business_id,
        appointment_id=appointment_id,
        new_appointment_time=payload.new_appointment_time,
        reason=payload.reason,
    )
    dashboard_event_manager.dispatch(
        business_id=current_user.business_id,
        event_type="APPOINTMENT_UPDATED",
        data={
            "appointment_id": appt.id,
            "status": appt.status,
            "appointment_time": appt.appointment_time.isoformat(),
            "reason": appt.reschedule_reason,
        },
    )
    return AppointmentResponse.model_validate(appt)


@router.post("/{appointment_id}/cancel", response_model=AppointmentResponse)
def cancel_appointment(
    appointment_id: str,
    reason: str | None = Query(None),
    payload: CancelAppointmentRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> AppointmentResponse:
    """Cancel an appointment and free its time slot."""
    cancel_reason = (payload.reason if payload and payload.reason else reason) or "Client requested cancellation"
    appt = cancel_appointment_core(
        db=db,
        business_id=current_user.business_id,
        appointment_id=appointment_id,
        reason=cancel_reason,
    )
    dashboard_event_manager.dispatch(
        business_id=current_user.business_id,
        event_type="APPOINTMENT_UPDATED",
        data={
            "appointment_id": appt.id,
            "status": appt.status,
            "reason": cancel_reason,
        },
    )
    return AppointmentResponse.model_validate(appt)


@router.post("/{appointment_id}/complete", response_model=AppointmentResponse)
def complete_appointment(
    appointment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> AppointmentResponse:
    """Mark an appointment as completed."""
    appt = db.scalar(
        select(Appointment).where(
            Appointment.id == appointment_id, Appointment.business_id == current_user.business_id
        )
    )
    if not appt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")

    appt.status = "completed"
    db.commit()
    db.refresh(appt)

    dashboard_event_manager.dispatch(
        business_id=current_user.business_id,
        event_type="APPOINTMENT_UPDATED",
        data={
            "appointment_id": appt.id,
            "status": appt.status,
        },
    )
    return AppointmentResponse.model_validate(appt)
