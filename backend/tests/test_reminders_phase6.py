"""Automated Tests for Phase 6: Automated Appointment Reminder & Outbound AI Calling.

Covers:
1. Reminder Settings: Default values and tenant updates.
2. Automatic reminder generation on appointment booking (24h & 2h default intervals).
3. Reminder synchronization on appointment rescheduling.
4. Reminder cancellation on appointment cancellation.
5. Timezone-aware calling window enforcement (deferring calls during quiet hours).
6. Outbound reminder execution with customer response classification (confirm, cancel, reschedule, callback, wrong number).
7. Multilingual intent classification in English, Tamil script, and Tanglish.
8. Telephony failure handling and retry backoff management (busy/no-answer, max retries).
9. Crash recovery for stale 'calling' status tasks.
10. Multi-tenant isolation for reminders and reminder settings.
11. Multilingual message generation for English, Tamil, and Tanglish.
"""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.appointment import Appointment
from app.models.assistant import Service
from app.models.business import Business
from app.models.customer import Customer
from app.models.reminder import Reminder, ReminderSetting
from app.services.reminder_service import (
    get_or_create_reminder_settings,
    is_within_calling_window,
    generate_reminder_message,
    schedule_appointment_reminders,
    reschedule_appointment_reminders,
    cancel_appointment_reminders,
)
from app.services.reminder_worker import (
    classify_reminder_response,
    process_due_reminders,
    recover_stale_calling_reminders,
)


def get_future_datetime(days_ahead: int = 7, hour_utc: int = 5, minute_utc: int = 30) -> datetime:
    """Return future weekday datetime in UTC guaranteed to fall within business hours (11:00 AM IST)."""
    target_date = date.today() + timedelta(days=days_ahead)
    while target_date.weekday() > 4:  # Ensure Monday (0) - Friday (4)
        target_date += timedelta(days=1)
    return datetime(target_date.year, target_date.month, target_date.day, hour_utc, minute_utc, 0, tzinfo=timezone.utc)


def to_utc(dt: datetime) -> datetime:
    """Convert offset-naive SQLite datetime to UTC aware."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ==============================================================================
# 1. Reminder Settings Tests
# ==============================================================================

def test_get_and_update_reminder_settings(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Verify retrieval and updating of tenant reminder configuration."""
    # 1. Retrieve default settings
    res = client.get("/api/v1/reminders/settings", headers=auth_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["business_id"] == "demo-biz-vattara-health"
    assert data["reminder_intervals_hours"] == "24,2"
    assert data["calling_start_time"] == "09:00"
    assert data["calling_end_time"] == "20:00"
    assert data["max_retries"] == 3
    assert data["retry_delay_minutes"] == 15
    assert data["is_enabled"] is True

    # 2. Update settings
    update_payload = {
        "reminder_intervals_hours": "48,24,1",
        "calling_start_time": "10:00",
        "calling_end_time": "19:00",
        "max_retries": 4,
        "retry_delay_minutes": 20,
        "is_enabled": True,
        "default_channel": "voice",
    }
    put_res = client.put("/api/v1/reminders/settings", json=update_payload, headers=auth_headers)
    assert put_res.status_code == status.HTTP_200_OK
    updated = put_res.json()
    assert updated["reminder_intervals_hours"] == "48,24,1"
    assert updated["calling_start_time"] == "10:00"
    assert updated["calling_end_time"] == "19:00"
    assert updated["max_retries"] == 4
    assert updated["retry_delay_minutes"] == 20


# ==============================================================================
# 2. Automatic Reminder Scheduling on Booking
# ==============================================================================

def test_auto_reminder_generation_on_booking(
    client: TestClient, auth_headers: dict[str, str], db_session: Session
) -> None:
    """Booking an appointment automatically generates 24h and 2h reminders."""
    appt_time = get_future_datetime(days_ahead=7)
    booking_payload = {
        "customer_name": "Senthil Nathan",
        "customer_phone": "+919876543210",
        "appointment_time": appt_time.isoformat(),
        "source": "phone",
    }
    res = client.post("/api/v1/appointments", json=booking_payload, headers=auth_headers)
    assert res.status_code == status.HTTP_201_CREATED
    appt_id = res.json()["id"]

    # Verify reminders created in DB
    reminders = db_session.execute(
        select(Reminder).where(Reminder.appointment_id == appt_id).order_by(Reminder.scheduled_time.asc())
    ).scalars().all()

    assert len(reminders) == 2
    tags = [r.interval_tag for r in reminders]
    assert "24h" in tags
    assert "2h" in tags

    r24 = next(r for r in reminders if r.interval_tag == "24h")
    assert r24.status in ["scheduled", "pending"]
    assert r24.customer.phone == "+919876543210"
    assert abs((appt_time - to_utc(r24.scheduled_time)).total_seconds() - 86400) < 60

    r2 = next(r for r in reminders if r.interval_tag == "2h")
    assert r2.status in ["scheduled", "pending"]
    assert abs((appt_time - to_utc(r2.scheduled_time)).total_seconds() - 7200) < 60


# ==============================================================================
# 3. Reminder Rescheduling and Cancellation Synchronization
# ==============================================================================

def test_reminder_rescheduling_sync(
    client: TestClient, auth_headers: dict[str, str], db_session: Session
) -> None:
    """Rescheduling an appointment updates the scheduled_time of all active reminders."""
    initial_time = get_future_datetime(days_ahead=7)
    res = client.post(
        "/api/v1/appointments",
        json={
            "customer_name": "Priya Sundaram",
            "customer_phone": "+919840123456",
            "appointment_time": initial_time.isoformat(),
            "source": "phone",
        },
        headers=auth_headers,
    )
    assert res.status_code == status.HTTP_201_CREATED
    appt_id = res.json()["id"]

    # Reschedule to 9 days ahead
    new_time = get_future_datetime(days_ahead=9)
    reschedule_res = client.post(
        f"/api/v1/appointments/{appt_id}/reschedule",
        json={"new_appointment_time": new_time.isoformat(), "reason": "Patient requested alternate day"},
        headers=auth_headers,
    )
    assert reschedule_res.status_code == status.HTTP_200_OK

    # Check updated reminder scheduled times
    reminders = db_session.execute(
        select(Reminder).where(Reminder.appointment_id == appt_id)
    ).scalars().all()
    assert len(reminders) == 2

    r24 = next(r for r in reminders if r.interval_tag == "24h")
    assert abs((new_time - to_utc(r24.scheduled_time)).total_seconds() - 86400) < 60

    r2 = next(r for r in reminders if r.interval_tag == "2h")
    assert abs((new_time - to_utc(r2.scheduled_time)).total_seconds() - 7200) < 60


def test_reminder_cancellation_sync(
    client: TestClient, auth_headers: dict[str, str], db_session: Session
) -> None:
    """Cancelling an appointment cancels all associated pending reminders."""
    appt_time = get_future_datetime(days_ahead=8)
    res = client.post(
        "/api/v1/appointments",
        json={
            "customer_name": "Arun Kumar",
            "customer_phone": "+919840999888",
            "appointment_time": appt_time.isoformat(),
            "source": "phone",
        },
        headers=auth_headers,
    )
    assert res.status_code == status.HTTP_201_CREATED
    appt_id = res.json()["id"]

    # Cancel the appointment
    cancel_res = client.post(
        f"/api/v1/appointments/{appt_id}/cancel?reason=Client+Travelling",
        headers=auth_headers,
    )
    assert cancel_res.status_code == status.HTTP_200_OK

    reminders = db_session.execute(
        select(Reminder).where(Reminder.appointment_id == appt_id)
    ).scalars().all()
    assert len(reminders) == 2
    for r in reminders:
        assert r.status == "cancelled"


# ==============================================================================
# 4. Calling Window & Timezone Quiet Hours Enforcement
# ==============================================================================

def test_is_within_calling_window() -> None:
    """Verify calling window calculations respect business timezone."""
    biz = Business(id="test-biz-window", name="Test Window Clinic", phone="+919888877777", email="win@test.com", timezone="Asia/Kolkata")
    setting = ReminderSetting(calling_start_time="09:00", calling_end_time="20:00")

    # 08:30 IST is 03:00 UTC (before 09:00 start)
    dt_early_utc = datetime(2026, 11, 15, 3, 0, tzinfo=timezone.utc)
    assert is_within_calling_window(biz, setting, dt_early_utc) is False

    # 14:00 IST is 08:30 UTC (within 09:00-20:00)
    dt_midday_utc = datetime(2026, 11, 15, 8, 30, tzinfo=timezone.utc)
    assert is_within_calling_window(biz, setting, dt_midday_utc) is True

    # 20:30 IST is 15:00 UTC (after 20:00 end)
    dt_late_utc = datetime(2026, 11, 15, 15, 0, tzinfo=timezone.utc)
    assert is_within_calling_window(biz, setting, dt_late_utc) is False


# ==============================================================================
# 5. Multilingual Intent Classification
# ==============================================================================

def test_classify_reminder_response_multilingual() -> None:
    """Verify classification of customer spoken responses in English, Tamil, and Tanglish."""
    # English
    assert classify_reminder_response("Yes, I will definitely attend.") == "confirm"
    assert classify_reminder_response("Please cancel my visit.") == "cancel"
    assert classify_reminder_response("I need to reschedule for next week.") == "reschedule"
    assert classify_reminder_response("Can you please call me back later?") == "callback"
    assert classify_reminder_response("Sorry, wrong number, not me.") == "wrong_number"

    # Tamil script
    assert classify_reminder_response("ஆமாம், நான் நாளை வருகிறேன்.") == "confirm"
    assert classify_reminder_response("எனது முன்பதிவை ரத்து செய்யுங்கள்.") == "cancel"
    assert classify_reminder_response("நேரத்தை மாற்ற விரும்புகிறேன்.") == "reschedule"
    assert classify_reminder_response("பிறகு என்னை அழைக்கவும்.") == "callback"
    assert classify_reminder_response("தவறான எண்.") == "wrong_number"

    # Tanglish (Tamil in Latin script)
    assert classify_reminder_response("Aama naan kandippa varuven, confirm pannunga.") == "confirm"
    assert classify_reminder_response("Cancel pannidunga, ennala vara mudiyadhu.") == "cancel"
    assert classify_reminder_response("Naalaikku postpone panna mudiyuma?") == "reschedule"
    assert classify_reminder_response("Apram call pannunga, busy-ah irukken.") == "callback"
    assert classify_reminder_response("Thappana number bro.") == "wrong_number"


def test_classify_response_api_endpoint(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Test POST /api/v1/reminders/classify-response endpoint."""
    res = client.post(
        "/api/v1/reminders/classify-response",
        json={"transcript": "Aama confirm pannidunga", "language": "ta"},
        headers=auth_headers,
    )
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["intent"] == "confirm"


# ==============================================================================
# 6. Due Reminder Processing & Action Execution
# ==============================================================================

def test_process_due_reminders_confirm_action(
    client: TestClient, auth_headers: dict[str, str], db_session: Session
) -> None:
    """Processing a due reminder with customer 'confirm' marks appointment confirmed."""
    appt_time = get_future_datetime(days_ahead=7)
    booking_res = client.post(
        "/api/v1/appointments",
        json={
            "customer_name": "Karthik Raja",
            "customer_phone": "+919777788888",
            "appointment_time": appt_time.isoformat(),
            "source": "phone",
        },
        headers=auth_headers,
    )
    assert booking_res.status_code == status.HTTP_201_CREATED
    appt_id = booking_res.json()["id"]

    # Make one reminder due immediately by setting scheduled_time in the past
    r24 = db_session.execute(
        select(Reminder).where(Reminder.appointment_id == appt_id, Reminder.interval_tag == "24h")
    ).scalar_one()
    r24.scheduled_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    db_session.commit()

    # Trigger process-due with mocked customer confirmation
    process_res = client.post(
        "/api/v1/reminders/process-due?force_calling_window=true&mock_response=Yes+I+confirm+my+appointment",
        headers=auth_headers,
    )
    assert process_res.status_code == status.HTTP_200_OK
    p_data = process_res.json()
    assert p_data["processed_count"] >= 1
    assert p_data["called_count"] >= 1

    # Check DB state
    db_session.refresh(r24)
    assert r24.status in ["sent", "completed"]
    assert r24.customer_response == "confirm"

    # Appointment should now be confirmed
    appt = db_session.get(Appointment, appt_id)
    assert appt.status == "confirmed"


def test_process_due_reminders_cancel_action(
    client: TestClient, auth_headers: dict[str, str], db_session: Session
) -> None:
    """Processing a due reminder with customer 'cancel' cancels the appointment."""
    appt_time = get_future_datetime(days_ahead=8)
    booking_res = client.post(
        "/api/v1/appointments",
        json={
            "customer_name": "Deepa Murugan",
            "customer_phone": "+919666655555",
            "appointment_time": appt_time.isoformat(),
            "source": "phone",
        },
        headers=auth_headers,
    )
    assert booking_res.status_code == status.HTTP_201_CREATED
    appt_id = booking_res.json()["id"]

    r24 = db_session.execute(
        select(Reminder).where(Reminder.appointment_id == appt_id, Reminder.interval_tag == "24h")
    ).scalar_one()
    r24.scheduled_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    db_session.commit()

    # Trigger process-due with mocked customer cancellation
    process_res = client.post(
        "/api/v1/reminders/process-due?force_calling_window=true&mock_response=Please+cancel+my+booking",
        headers=auth_headers,
    )
    assert process_res.status_code == status.HTTP_200_OK

    db_session.refresh(r24)
    assert r24.customer_response == "cancel"

    appt = db_session.get(Appointment, appt_id)
    assert appt.status == "cancelled"


# ==============================================================================
# 7. Telephony Failure & Retry Backoff Management
# ==============================================================================

def test_telephony_failure_retry_management(db_session: Session) -> None:
    """When telephony returns busy or failed, retry_count increments and next_retry_at is scheduled."""
    customer = db_session.get(Customer, "cust-test-retry")
    if not customer:
        customer = Customer(
            id="cust-test-retry",
            business_id="demo-biz-vattara-health",
            name="Test Retry Customer",
            phone="+919876500000",
        )
        db_session.add(customer)
        db_session.commit()

    due_rem = Reminder(
        business_id="demo-biz-vattara-health",
        customer_id=customer.id,
        reminder_type="voice",
        scheduled_time=datetime.now(timezone.utc) - timedelta(minutes=5),
        status="scheduled",
        message="Test reminder",
        retry_count=0,
        max_retries=2,
    )
    db_session.add(due_rem)
    db_session.commit()
    db_session.refresh(due_rem)

    # 1. First failure (busy): retry_count becomes 1 (< 2), status -> retrying
    summary1 = process_due_reminders(db_session, force_calling_window=True, mock_customer_response="busy")
    assert summary1["retried_count"] >= 1

    db_session.refresh(due_rem)
    assert due_rem.retry_count == 1
    assert due_rem.status == "retrying"
    assert due_rem.next_retry_at is not None

    # 2. Advance time and set retry_count = 2 (reaching max_retries = 2)
    due_rem.next_retry_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    due_rem.retry_count = 2
    setting = get_or_create_reminder_settings(db_session, "demo-biz-vattara-health")
    setting.max_retries = 2
    db_session.commit()

    summary2 = process_due_reminders(db_session, force_calling_window=True, mock_customer_response="busy")
    assert summary2["failed_count"] >= 1

    db_session.refresh(due_rem)
    assert due_rem.status == "failed"


# ==============================================================================
# 8. Worker Crash Recovery for Stale 'calling' Tasks
# ==============================================================================

def test_recover_stale_calling_reminders(db_session: Session) -> None:
    """Reminders stuck in 'calling' state due to an unhandled worker crash are reset."""
    customer = db_session.get(Customer, "cust-stuck")
    if not customer:
        customer = Customer(
            id="cust-stuck",
            business_id="demo-biz-vattara-health",
            name="Stuck Customer",
            phone="+919876500001",
        )
        db_session.add(customer)
        db_session.commit()

    stuck_rem = Reminder(
        business_id="demo-biz-vattara-health",
        customer_id=customer.id,
        reminder_type="voice",
        scheduled_time=datetime.now(timezone.utc) - timedelta(minutes=30),
        status="calling",
        message="Stuck reminder",
        retry_count=0,
        max_retries=3,
        updated_at=datetime.now(timezone.utc) - timedelta(minutes=25),
    )
    db_session.add(stuck_rem)
    db_session.commit()
    db_session.refresh(stuck_rem)

    recovered_count = recover_stale_calling_reminders(db_session, timeout_minutes=15)
    assert recovered_count >= 1

    db_session.refresh(stuck_rem)
    assert stuck_rem.status == "scheduled"
    assert stuck_rem.retry_count == 1
    assert "Recovered from stuck calling state" in (stuck_rem.error_message or "")


# ==============================================================================
# 9. Multi-Tenant Isolation for Reminders
# ==============================================================================

def test_reminder_tenant_isolation(client: TestClient, auth_headers: dict[str, str], db_session: Session) -> None:
    """Tenant A cannot read, modify, or process Tenant B's reminders."""
    biz_b = db_session.get(Business, "biz-tenant-beta")
    if not biz_b:
        biz_b = Business(
            id="biz-tenant-beta",
            name="Beta Multispeciality Clinic",
            phone="+919111122222",
            email="beta-tenant@vattara.com",
            timezone="Asia/Kolkata",
        )
        db_session.add(biz_b)

    cust_b = db_session.get(Customer, "cust-b")
    if not cust_b:
        cust_b = Customer(
            id="cust-b",
            business_id="biz-tenant-beta",
            name="Beta Customer",
            phone="+919111133333",
        )
        db_session.add(cust_b)

    rem_b = db_session.get(Reminder, "rem-tenant-beta-1")
    if not rem_b:
        rem_b = Reminder(
            id="rem-tenant-beta-1",
            business_id="biz-tenant-beta",
            customer_id="cust-b",
            reminder_type="voice",
            scheduled_time=datetime.now(timezone.utc) + timedelta(hours=5),
            status="scheduled",
            message="Private appointment reminder for Beta Clinic",
        )
        db_session.add(rem_b)
    db_session.commit()

    # 1. Tenant A (via auth_headers) lists reminders: must not include Tenant B's reminder
    list_res = client.get("/api/v1/reminders", headers=auth_headers)
    assert list_res.status_code == status.HTTP_200_OK
    rem_ids = [r["id"] for r in list_res.json()]
    assert "rem-tenant-beta-1" not in rem_ids

    # 2. Tenant A tries to access Tenant B's reminder directly: 404
    get_res = client.get("/api/v1/reminders/rem-tenant-beta-1", headers=auth_headers)
    assert get_res.status_code == status.HTTP_404_NOT_FOUND

    # 3. Tenant A tries to delete Tenant B's reminder: 404
    del_res = client.delete("/api/v1/reminders/rem-tenant-beta-1", headers=auth_headers)
    assert del_res.status_code == status.HTTP_404_NOT_FOUND


# ==============================================================================
# 10. Multilingual Reminder Message Generation
# ==============================================================================

def test_multilingual_reminder_message_generation() -> None:
    """Verify reminder message composition in English, Tamil, and Tanglish."""
    appt_dt = datetime(2026, 11, 20, 15, 30, tzinfo=ZoneInfo("Asia/Kolkata"))

    # English
    en_msg = generate_reminder_message(
        customer_name="Ramesh",
        business_name="Vattara Clinic",
        service_name="Consultation",
        appointment_time_local=appt_dt,
        language="en-IN",
    )
    assert "Hello Ramesh" in en_msg
    assert "Vattara Clinic" in en_msg
    assert "Consultation" in en_msg
    assert "Would you like to confirm this appointment?" in en_msg

    # Tamil script
    ta_msg = generate_reminder_message(
        customer_name="ரமேஷ்",
        business_name="வட்டார மருத்துவமனை",
        service_name="ஆலோசனை",
        appointment_time_local=appt_dt,
        language="ta-IN",
    )
    assert "வணக்கம்" in ta_msg
    assert "வட்டார மருத்துவமனை" in ta_msg
    assert "முன்பதிவை உறுதிப்படுத்த" in ta_msg

    # Tanglish
    tanglish_msg = generate_reminder_message(
        customer_name="Ramesh",
        business_name="Vattara Clinic",
        service_name="Consultation",
        appointment_time_local=appt_dt,
        language="ta-Latn",
    )
    assert "Vanakkam Ramesh" in tanglish_msg
    assert "Vattara Clinic" in tanglish_msg
    assert "Confirm panna virumbureengala?" in tanglish_msg
