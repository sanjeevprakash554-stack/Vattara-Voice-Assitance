"""Regression tests for Priority 2: Past Appointment Prevention.

Verifies:
1. Rejection of appointments in the past (e.g. 10:00 AM IST when now is 2:30 PM IST).
2. Timezone-aware UTC <-> IST conversion and business hours validation.
3. Future slot acceptance with correct start and end times.
4. Reminder scheduling relative to actual appointment time and prevention of premature completion.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from fastapi import HTTPException
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.assistant import Service
from app.models.business import Business
from app.models.business_hours import BusinessHour
from app.models.customer import Customer
from app.models.reminder import Reminder
from app.schemas.appointment import AppointmentCreate
from app.services.appointment_service import book_appointment_core
from app.services.reminder_service import schedule_appointment_reminders
from app.services.reminder_worker import process_due_reminders
from app.services.scheduling_service import validate_booking_feasibility


@pytest.fixture
def ist_clinic(db_session: Session) -> Business:
    """Fixture providing an active clinic in Asia/Kolkata timezone with production services."""
    biz = db_session.get(Business, "demo-biz-vattara-health")
    if not biz:
        biz = Business(
            id="demo-biz-vattara-health",
            name="Vattara City Clinic & Diagnostics",
            vertical="clinic",
            email="reception@vattaraclinic.com",
            phone="+914428289000",
            timezone="Asia/Kolkata",
            is_active=True,
        )
        db_session.add(biz)
        db_session.flush()

    for dow in range(7):
        bh = db_session.query(BusinessHour).filter(
            BusinessHour.business_id == biz.id,
            BusinessHour.day_of_week == dow,
        ).first()
        if not bh:
            db_session.add(
                BusinessHour(
                    business_id=biz.id,
                    day_of_week=dow,
                    open_time="08:00",
                    close_time="20:00",
                    is_closed=False,
                )
            )

    srv = db_session.get(Service, "demo-service-3")
    if not srv:
        srv = Service(
            id="demo-service-3",
            business_id=biz.id,
            name="Pediatric Health Checkup",
            duration_minutes=30,
            price=700.0,
            is_active=True,
        )
        db_session.add(srv)

    db_session.commit()
    return biz


def test_reject_past_appointment_earlier_today(db_session: Session, ist_clinic: Business):
    """Verify that an appointment earlier on the same day (e.g. 10:00 AM IST when now is ~2:30 PM IST) is rejected."""
    # Current time
    now_utc = datetime.now(timezone.utc)
    # A time strictly 2 hours in the past
    past_time = now_utc - timedelta(hours=2)

    # 1. Direct validation check
    with pytest.raises(HTTPException) as exc_info:
        validate_booking_feasibility(
            db=db_session,
            business_id=ist_clinic.id,
            appointment_time=past_time,
            service_id="demo-service-3",
            enforce_past_check=True,
        )
    assert exc_info.value.status_code == 400
    assert "Cannot book appointments in the past" in exc_info.value.detail

    # 2. End-to-end booking core check
    payload = AppointmentCreate(
        customer_name="Test Customer",
        customer_phone="+919840123456",
        service_id="demo-service-3",
        appointment_time=past_time,
        notes="Past test",
    )
    with pytest.raises(HTTPException) as exc_info2:
        book_appointment_core(
            db=db_session,
            business_id=ist_clinic.id,
            payload=payload,
            enforce_past_check=True,
        )
    assert exc_info2.value.status_code == 400
    assert "Cannot book appointments in the past" in exc_info2.value.detail


def test_reject_appointment_yesterday(db_session: Session, ist_clinic: Business):
    """Verify appointments on previous days are strictly rejected."""
    now_utc = datetime.now(timezone.utc)
    yesterday = now_utc - timedelta(days=1)

    payload = AppointmentCreate(
        customer_name="Test Customer",
        customer_phone="+919840123456",
        service_id="demo-service-3",
        appointment_time=yesterday,
        notes="Yesterday test",
    )
    with pytest.raises(HTTPException) as exc_info:
        book_appointment_core(
            db=db_session,
            business_id=ist_clinic.id,
            payload=payload,
            enforce_past_check=True,
        )
    assert exc_info.value.status_code == 400
    assert "Cannot book appointments in the past" in exc_info.value.detail


def test_reject_outside_business_hours(db_session: Session, ist_clinic: Business):
    """Verify appointments outside operating hours (08:00 - 20:00 IST) are rejected."""
    ist_tz = ZoneInfo("Asia/Kolkata")
    tomorrow = (datetime.now(ist_tz) + timedelta(days=1)).date()

    # 23:00 IST (11:00 PM) is outside 08:00 - 20:00
    night_slot_ist = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 23, 0, tzinfo=ist_tz)

    payload = AppointmentCreate(
        customer_name="Test Customer",
        customer_phone="+919840123456",
        service_id="demo-service-3",
        appointment_time=night_slot_ist,
        notes="Late night test",
    )
    with pytest.raises(HTTPException) as exc_info:
        book_appointment_core(
            db=db_session,
            business_id=ist_clinic.id,
            payload=payload,
            enforce_operating_hours=True,
            enforce_past_check=True,
        )
    assert exc_info.value.status_code == 400
    assert "operating hours" in exc_info.value.detail.lower()


def test_accept_valid_future_appointment_and_verify_duration(db_session: Session, ist_clinic: Business):
    """Verify that a valid future appointment is accepted with correct UTC/IST conversions and end time."""
    ist_tz = ZoneInfo("Asia/Kolkata")
    future_date = (datetime.now(ist_tz) + timedelta(days=2)).date()

    # 10:00 AM IST = 04:30 AM UTC
    slot_ist = datetime(future_date.year, future_date.month, future_date.day, 10, 0, tzinfo=ist_tz)
    expected_utc = slot_ist.astimezone(timezone.utc)
    expected_end_utc = expected_utc + timedelta(minutes=30)

    payload = AppointmentCreate(
        customer_name="Future Patient",
        customer_phone="+919840199887",
        service_id="demo-service-3",
        appointment_time=slot_ist,
        notes="Future appointment test",
    )
    appt = book_appointment_core(
        db=db_session,
        business_id=ist_clinic.id,
        payload=payload,
        enforce_operating_hours=True,
        enforce_past_check=True,
    )

    assert appt is not None
    appt_start_utc = appt.appointment_time if appt.appointment_time.tzinfo else appt.appointment_time.replace(tzinfo=timezone.utc)
    appt_end_utc = appt.end_time if appt.end_time.tzinfo else appt.end_time.replace(tzinfo=timezone.utc)
    assert appt_start_utc == expected_utc
    assert appt_end_utc == expected_end_utc
    assert (appt_end_utc - appt_start_utc) == timedelta(minutes=30)


def test_reminders_scheduled_relative_to_appointment_and_not_completed_prematurely(db_session: Session, ist_clinic: Business):
    """Verify that reminders are scheduled relative to the appointment time and cannot be marked completed prematurely."""
    ist_tz = ZoneInfo("Asia/Kolkata")
    future_date = (datetime.now(ist_tz) + timedelta(days=3)).date()
    slot_ist = datetime(future_date.year, future_date.month, future_date.day, 11, 0, tzinfo=ist_tz)
    slot_utc = slot_ist.astimezone(timezone.utc)

    payload = AppointmentCreate(
        customer_name="Reminder Patient",
        customer_phone="+919840199123",
        service_id="demo-service-3",
        appointment_time=slot_ist,
        notes="Reminder scheduling test",
    )
    appt = book_appointment_core(
        db=db_session,
        business_id=ist_clinic.id,
        payload=payload,
        enforce_past_check=True,
    )

    reminders = db_session.execute(
        select(Reminder).where(Reminder.appointment_id == appt.id)
    ).scalars().all()
    assert len(reminders) >= 1

    for r in reminders:
        r_time_utc = r.scheduled_time if r.scheduled_time.tzinfo else r.scheduled_time.replace(tzinfo=timezone.utc)
        # Scheduled time must be in the future and strictly earlier than the appointment time
        assert r_time_utc < slot_utc
        assert r_time_utc > datetime.now(timezone.utc)
        assert r.status == "pending"

    # Attempt to dispatch reminders now: since scheduled_time is in the future, process_due_reminders must NOT complete them
    res = process_due_reminders(db=db_session)
    assert res.get("processed_count", 0) == 0
    # None of these future reminders should have been dispatched or completed
    for r in reminders:
        db_session.refresh(r)
        assert r.status == "pending", "Future reminder must remain pending and NOT be dispatched prematurely"
