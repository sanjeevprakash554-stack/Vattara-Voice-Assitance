"""Automated Tests for Phase 2: Appointment Availability and Scheduling Engine.

Covers:
1. Business operating hours (retrieval, update, open/closed days).
2. Staff / Doctor availability schedules (shifts, break intervals).
3. Available slot calculation (open slots, booked slots, past slots).
4. Prevention of duplicate appointments for the same customer.
5. Prevention of overlapping bookings.
6. Service duration validation and closing boundary enforcement.
7. Appointment rescheduling and cancellation (slot freeing).
8. Timezone-aware scheduling.
9. Multi-tenant scheduling isolation.
"""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.models.appointment import Appointment
from app.models.assistant import Service
from app.models.business import Business
from app.models.business_hours import BusinessHour
from app.models.customer import Customer
from app.models.staff_schedule import StaffSchedule
from app.models.user import User


# Helper to get upcoming weekday (e.g. next Tuesday = 1, next Thursday = 3, next Sunday = 6)
def get_next_weekday(target_weekday: int) -> date:
    """Return the next date matching target_weekday (0=Monday, 6=Sunday)."""
    today = date.today()
    days_ahead = target_weekday - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return today + timedelta(days=days_ahead)


# ==============================================================================
# 1. Operating Hours Tests
# ==============================================================================

def test_get_and_update_operating_hours(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Verify retrieval and updating of weekly business operating hours."""
    # 1. Retrieve 7-day schedule
    res = client.get("/api/v1/appointments/operating-hours", headers=auth_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["business_id"] == "demo-biz-vattara-health"
    assert len(data["schedule"]) == 7

    # 2. Update operating hours: Mark Wednesday (dow=2) closed and extend Thursday
    new_schedule = [
        {"day_of_week": 0, "day_name": "Monday", "open_time": "08:30", "close_time": "20:00", "is_closed": False},
        {"day_of_week": 1, "day_name": "Tuesday", "open_time": "08:30", "close_time": "20:00", "is_closed": False},
        {"day_of_week": 2, "day_name": "Wednesday", "open_time": "09:00", "close_time": "17:00", "is_closed": True},
        {"day_of_week": 3, "day_name": "Thursday", "open_time": "08:00", "close_time": "21:00", "is_closed": False},
        {"day_of_week": 4, "day_name": "Friday", "open_time": "08:30", "close_time": "20:00", "is_closed": False},
        {"day_of_week": 5, "day_name": "Saturday", "open_time": "09:00", "close_time": "18:00", "is_closed": False},
        {"day_of_week": 6, "day_name": "Sunday", "open_time": "10:00", "close_time": "14:00", "is_closed": True},
    ]
    put_res = client.put(
        "/api/v1/appointments/operating-hours",
        json={"schedule": new_schedule},
        headers=auth_headers,
    )
    assert put_res.status_code == status.HTTP_200_OK
    updated_data = put_res.json()
    wed = next(d for d in updated_data["schedule"] if d["day_of_week"] == 2)
    assert wed["is_closed"] is True

    thu = next(d for d in updated_data["schedule"] if d["day_of_week"] == 3)
    assert thu["open_time"] == "08:00"
    assert thu["close_time"] == "21:00"


# ==============================================================================
# 2. Staff Schedule & Provider Availability Tests
# ==============================================================================

def test_staff_schedule_management(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Verify staff listing and creating provider availability shifts."""
    # 1. List staff members
    staff_res = client.get("/api/v1/appointments/staff", headers=auth_headers)
    assert staff_res.status_code == status.HTTP_200_OK
    staff_list = staff_res.json()
    assert len(staff_list) >= 1
    admin_staff_id = staff_list[0]["id"]

    # 2. Create staff schedule for Tuesday (dow=1) with shift 09:00 - 15:00 and break 12:00 - 13:00
    sched_payload = {
        "user_id": admin_staff_id,
        "staff_name": "Dr. Rajesh Kumar",
        "day_of_week": 1,
        "start_time": "09:00",
        "end_time": "15:00",
        "break_start": "12:00",
        "break_end": "13:00",
        "slot_duration_minutes": 30,
        "is_active": True,
    }
    create_res = client.post(
        "/api/v1/appointments/staff-schedules",
        json=sched_payload,
        headers=auth_headers,
    )
    assert create_res.status_code == status.HTTP_201_CREATED
    sched = create_res.json()
    assert sched["start_time"] == "09:00"
    assert sched["break_start"] == "12:00"

    # 3. List staff schedules
    list_res = client.get(
        f"/api/v1/appointments/staff-schedules?staff_id={admin_staff_id}",
        headers=auth_headers,
    )
    assert list_res.status_code == status.HTTP_200_OK
    schedules = list_res.json()
    assert any(s["day_of_week"] == 1 and s["break_start"] == "12:00" for s in schedules)


# ==============================================================================
# 3. Slot Calculation Tests
# ==============================================================================

def test_calculate_slots_open_vs_closed_day(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Verify slots calculation on open business day vs closed day."""
    next_mon = get_next_weekday(0).isoformat()
    next_sun = get_next_weekday(6).isoformat()

    # Open Day (Monday)
    res_mon = client.get(f"/api/v1/appointments/availability/slots?date={next_mon}", headers=auth_headers)
    assert res_mon.status_code == status.HTTP_200_OK
    mon_data = res_mon.json()
    assert mon_data["is_open"] is True
    assert mon_data["available_slots_count"] > 0
    assert len(mon_data["slots"]) > 0

    # Ensure slots have proper format and duration
    first_slot = mon_data["slots"][0]
    assert "time" in first_slot
    assert "start_time" in first_slot
    assert "end_time" in first_slot
    assert first_slot["duration_minutes"] == 30

    # Closed Day (Sunday)
    res_sun = client.get(f"/api/v1/appointments/availability/slots?date={next_sun}", headers=auth_headers)
    assert res_sun.status_code == status.HTTP_200_OK
    sun_data = res_sun.json()
    assert sun_data["is_open"] is False
    assert sun_data["available_slots_count"] == 0
    assert len(sun_data["slots"]) == 0


def test_service_duration_adjusts_slots_and_boundaries(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
) -> None:
    """Verify slot calculation respects custom service duration."""
    next_tue = get_next_weekday(1).isoformat()

    # Query cardiology service (duration = 45 mins)
    srv = db_session.scalar(select(Service).where(Service.name.like("%Cardiology%")))
    assert srv is not None
    assert srv.duration_minutes == 45

    res = client.get(
        f"/api/v1/appointments/availability/slots?date={next_tue}&service_id={srv.id}",
        headers=auth_headers,
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["duration_minutes"] == 45
    assert data["service_id"] == srv.id
    for s in data["slots"]:
        assert s["duration_minutes"] == 45


# ==============================================================================
# 4. Conflict Avoidance: Duplicates & Overlaps
# ==============================================================================

def test_prevent_duplicate_appointments(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Ensure booking duplicate appointments for the same customer at the exact same time is rejected with 409."""
    next_tue = get_next_weekday(1)
    target_dt = datetime(next_tue.year, next_tue.month, next_tue.day, 5, 30, tzinfo=timezone.utc)
    # 05:30 UTC = 11:00 AM IST (well inside operating hours)

    payload = {
        "customer_phone": "+91 99999 77771",
        "customer_name": "Duplicate Test Client",
        "appointment_time": target_dt.isoformat(),
        "notes": "First booking",
        "source": "dashboard",
    }

    # 1. First booking succeeds
    res1 = client.post("/api/v1/appointments", json=payload, headers=auth_headers)
    assert res1.status_code == status.HTTP_201_CREATED

    # 2. Second booking with same customer and same time must fail with 409
    res2 = client.post("/api/v1/appointments", json=payload, headers=auth_headers)
    assert res2.status_code == status.HTTP_409_CONFLICT
    assert "exact time" in res2.json()["detail"].lower() or "duplicate" in res2.json()["detail"].lower()


def test_prevent_overlapping_appointments(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Ensure booking an overlapping slot is rejected with 409 Conflict."""
    next_tue = get_next_weekday(1)
    target_dt = datetime(next_tue.year, next_tue.month, next_tue.day, 6, 0, tzinfo=timezone.utc)
    # 06:00 UTC = 11:30 AM IST

    # 1. Book from 11:30 to 12:00 (30 mins)
    res1 = client.post(
        "/api/v1/appointments",
        json={
            "customer_phone": "+91 99999 77772",
            "customer_name": "Client A",
            "appointment_time": target_dt.isoformat(),
            "notes": "Booking 1",
        },
        headers=auth_headers,
    )
    assert res1.status_code == status.HTTP_201_CREATED

    # 2. Attempt booking at 11:45 (overlaps with 11:30 - 12:00)
    overlap_dt = target_dt + timedelta(minutes=15)
    res2 = client.post(
        "/api/v1/appointments",
        json={
            "customer_phone": "+91 99999 77773",
            "customer_name": "Client B",
            "appointment_time": overlap_dt.isoformat(),
            "notes": "Overlapping booking",
        },
        headers=auth_headers,
    )
    assert res2.status_code == status.HTTP_409_CONFLICT
    assert "overlap" in res2.json()["detail"].lower()

    # 3. Booking at 12:00 (immediately adjacent, no overlap) succeeds
    adjacent_dt = target_dt + timedelta(minutes=30)
    res3 = client.post(
        "/api/v1/appointments",
        json={
            "customer_phone": "+91 99999 77774",
            "customer_name": "Client C",
            "appointment_time": adjacent_dt.isoformat(),
            "notes": "Adjacent booking",
        },
        headers=auth_headers,
    )
    assert res3.status_code == status.HTTP_201_CREATED


# ==============================================================================
# 5. Operating Hours Boundary & Service Duration Validation
# ==============================================================================

def test_operating_hours_boundary_rejection(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Ensure appointments scheduled outside business operating hours are rejected."""
    # Clinic operating hours on weekdays: 08:30 - 20:00 IST
    next_mon = get_next_weekday(0)

    # 01:00 UTC = 06:30 IST (before 08:30 open)
    before_open = datetime(next_mon.year, next_mon.month, next_mon.day, 1, 0, tzinfo=timezone.utc)
    res_early = client.post(
        "/api/v1/appointments",
        json={
            "customer_phone": "+91 99999 77775",
            "appointment_time": before_open.isoformat(),
            "notes": "Early bird attempt",
        },
        headers=auth_headers,
    )
    assert res_early.status_code == status.HTTP_400_BAD_REQUEST
    assert "outside operating hours" in res_early.json()["detail"].lower()

    # 15:00 UTC = 20:30 IST (after 20:00 close)
    after_close = datetime(next_mon.year, next_mon.month, next_mon.day, 15, 0, tzinfo=timezone.utc)
    res_late = client.post(
        "/api/v1/appointments",
        json={
            "customer_phone": "+91 99999 77775",
            "appointment_time": after_close.isoformat(),
            "notes": "Night attempt",
        },
        headers=auth_headers,
    )
    assert res_late.status_code == status.HTTP_400_BAD_REQUEST
    assert "outside operating hours" in res_late.json()["detail"].lower()


# ==============================================================================
# 6. Rescheduling & Cancellation Flows
# ==============================================================================

def test_reschedule_appointment_flow(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Verify rescheduling an appointment frees the old slot and validates new slot conflicts."""
    future_date = date.today() + timedelta(days=14)
    # Ensure it's a weekday (if weekend, shift to Monday)
    if future_date.weekday() >= 5:
        future_date += timedelta(days=(7 - future_date.weekday()))

    # Initial slot: 10:00 AM IST (04:30 UTC)
    t1 = datetime(future_date.year, future_date.month, future_date.day, 4, 30, tzinfo=timezone.utc)
    # New slot: 02:00 PM IST (08:30 UTC)
    t2 = datetime(future_date.year, future_date.month, future_date.day, 8, 30, tzinfo=timezone.utc)

    # 1. Create appointment
    create_res = client.post(
        "/api/v1/appointments",
        json={
            "customer_phone": "+91 99999 77776",
            "customer_name": "Reschedule Client",
            "appointment_time": t1.isoformat(),
            "notes": "Initial time",
        },
        headers=auth_headers,
    )
    assert create_res.status_code == status.HTTP_201_CREATED
    appt_id = create_res.json()["id"]

    # 2. Reschedule to t2
    resched_res = client.post(
        f"/api/v1/appointments/{appt_id}/reschedule",
        json={"new_appointment_time": t2.isoformat(), "reason": "Patient requested afternoon"},
        headers=auth_headers,
    )
    assert resched_res.status_code == status.HTTP_200_OK
    updated = resched_res.json()
    assert updated["status"] == "rescheduled"
    assert updated["reschedule_reason"] == "Patient requested afternoon"

    # 3. Verify old slot t1 is now freed and can be booked by another client
    free_slot_booking = client.post(
        "/api/v1/appointments",
        json={
            "customer_phone": "+91 99999 77777",
            "customer_name": "New Client On Freed Slot",
            "appointment_time": t1.isoformat(),
        },
        headers=auth_headers,
    )
    assert free_slot_booking.status_code == status.HTTP_201_CREATED


def test_cancel_appointment_frees_slot(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Verify cancelling an appointment frees the slot immediately."""
    next_fri = get_next_weekday(4)
    # Slot at 11:00 AM IST (05:30 UTC)
    t_slot = datetime(next_fri.year, next_fri.month, next_fri.day, 5, 30, tzinfo=timezone.utc)

    # 1. Book appointment
    res1 = client.post(
        "/api/v1/appointments",
        json={
            "customer_phone": "+91 99999 77778",
            "customer_name": "Cancellation Client",
            "appointment_time": t_slot.isoformat(),
        },
        headers=auth_headers,
    )
    assert res1.status_code == status.HTTP_201_CREATED
    appt_id = res1.json()["id"]

    # 2. Verify slot is occupied in slot calculation
    date_str = next_fri.isoformat()
    slots_res1 = client.get(f"/api/v1/appointments/availability/slots?date={date_str}", headers=auth_headers)
    occupied_slot = next((s for s in slots_res1.json()["slots"] if s["time"] == "11:00"), None)
    if occupied_slot:
        assert occupied_slot["available"] is False

    # 3. Cancel the appointment
    cancel_res = client.post(
        f"/api/v1/appointments/{appt_id}/cancel",
        json={"reason": "Patient had emergency travel"},
        headers=auth_headers,
    )
    assert cancel_res.status_code == status.HTTP_200_OK
    assert cancel_res.json()["status"] == "cancelled"

    # 4. Verify slot is now available again in slot calculation
    slots_res2 = client.get(f"/api/v1/appointments/availability/slots?date={date_str}", headers=auth_headers)
    freed_slot = next((s for s in slots_res2.json()["slots"] if s["time"] == "11:00"), None)
    if freed_slot:
        assert freed_slot["available"] is True


# ==============================================================================
# 7. Timezone-Aware Scheduling Tests
# ==============================================================================

def test_timezone_aware_scheduling(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Verify slots and bookings properly account for business local timezone offset."""
    next_tue = get_next_weekday(1)
    res = client.get(f"/api/v1/appointments/availability/slots?date={next_tue.isoformat()}", headers=auth_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["timezone"] == "Asia/Kolkata"

    # Verify returned start_time strings contain +05:30 offset
    first_slot = data["slots"][0]
    assert "+05:30" in first_slot["start_time"]


# ==============================================================================
# 8. Multi-Tenant Scheduling Isolation Tests
# ==============================================================================

@pytest.fixture
def tenant_b_scheduling(db_session: Session) -> dict[str, str]:
    """Create isolated second tenant (Business B) for scheduling tests."""
    biz_b = Business(
        id="tenant-b-sched-biz",
        name="Wellness Spa",
        vertical="spa",
        phone="+91 44 9999 8888",
        email="info@wellnessspa.com",
        timezone="Asia/Kolkata",
        address="Beach Road, Chennai",
        is_active=True,
    )
    db_session.add(biz_b)

    user_b = User(
        id="user-tenant-b-spa-admin",
        business_id=biz_b.id,
        email="admin@wellnessspa.com",
        full_name="Spa Admin",
        hashed_password=get_password_hash("Spa@123"),
        role="admin",
        is_active=True,
    )
    db_session.add(user_b)
    db_session.commit()

    token_b = create_access_token(
        subject=user_b.id,
        extra_claims={"business_id": biz_b.id, "role": "admin"},
    )
    return {"Authorization": f"Bearer {token_b}", "business_id": biz_b.id}


def test_multi_tenant_scheduling_isolation(
    client: TestClient,
    auth_headers: dict[str, str],
    tenant_b_scheduling: dict[str, str],
) -> None:
    """Verify Tenant B bookings do not block Tenant A, and Tenant B cannot access Tenant A's slots/reschedule."""
    next_wed = get_next_weekday(2)
    t_slot = datetime(next_wed.year, next_wed.month, next_wed.day, 5, 30, tzinfo=timezone.utc)
    headers_b = {"Authorization": tenant_b_scheduling["Authorization"]}

    # 1. Tenant A books 11:00 AM IST
    res_a = client.post(
        "/api/v1/appointments",
        json={
            "customer_phone": "+91 98401 22222",
            "appointment_time": t_slot.isoformat(),
        },
        headers=auth_headers,
    )
    assert res_a.status_code == status.HTTP_201_CREATED
    appt_a_id = res_a.json()["id"]

    # 2. Tenant B books SAME EXACT time slot (11:00 AM IST) - must SUCCEED because different tenant!
    res_b = client.post(
        "/api/v1/appointments",
        json={
            "customer_phone": "+91 99999 33333",
            "appointment_time": t_slot.isoformat(),
        },
        headers=headers_b,
    )
    assert res_b.status_code == status.HTTP_201_CREATED

    # 3. Tenant B tries to reschedule Tenant A's appointment - must return 404
    t_new = t_slot + timedelta(hours=2)
    res_hack = client.post(
        f"/api/v1/appointments/{appt_a_id}/reschedule",
        json={"new_appointment_time": t_new.isoformat()},
        headers=headers_b,
    )
    assert res_hack.status_code == status.HTTP_404_NOT_FOUND

    # 4. Tenant B tries to cancel Tenant A's appointment - must return 404
    res_cancel_hack = client.post(
        f"/api/v1/appointments/{appt_a_id}/cancel",
        headers=headers_b,
    )
    assert res_cancel_hack.status_code == status.HTTP_404_NOT_FOUND
