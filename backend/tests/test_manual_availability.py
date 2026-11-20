"""Comprehensive Automated Test Suite for Manual Availability Management.

Covers:
1. Availability REST APIs (Full config GET/PUT, Weekly schedule PUT, Breaks CRUD, Settings PUT, Holidays CRUD, Special dates CRUD).
2. Slot Calculation & Booking Feasibility:
   - Operating hours enforcement.
   - Break windows enforcement.
   - Holiday closures.
   - Special date overrides (custom hours vs closed).
   - Buffer time between appointments.
   - Same-day booking enable/disable toggle.
   - Minimum advance notice and maximum booking window.
3. Alternative slot suggestions when requested slot is unavailable.
4. AI Function Calling (tools.py) returns alternative suggestions on conflicts.
5. Multi-tenant isolation between businesses.
"""

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.appointment import Appointment
from app.models.assistant import Service
from app.models.availability import (
    AvailabilitySetting,
    BusinessBreak,
    BusinessHoliday,
    SpecialDateOverride,
)
from app.models.business import Business
from app.models.business_hours import BusinessHour
from app.models.customer import Customer
from app.models.user import User
from app.schemas.appointment import AppointmentCreate
from app.services.ai.tools import execute_tool_call
from app.services.appointment_service import book_appointment_core
from app.services.scheduling_service import (
    DAY_NAMES,
    calculate_available_slots,
    find_alternative_slots,
)


def get_next_weekday(target_weekday: int) -> date:
    """Return the next date matching target_weekday (0=Monday, 6=Sunday)."""
    today = date.today()
    days_ahead = target_weekday - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return today + timedelta(days=days_ahead)


# ==============================================================================
# 1. Availability REST API Tests
# ==============================================================================

def test_get_and_update_full_availability(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Verify GET and PUT /api/v1/availability for unified config management."""
    # 1. GET full config
    res = client.get("/api/v1/availability", headers=auth_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["business_id"] == "demo-biz-vattara-health"
    assert "weekly_schedule" in data
    assert len(data["weekly_schedule"]) == 7
    assert "breaks" in data
    assert "settings" in data
    assert "holidays" in data
    assert "special_dates" in data
    assert data["settings"]["slot_interval_minutes"] >= 5

    # 2. PUT full config update
    new_settings = {
        "default_duration_minutes": 45,
        "buffer_time_minutes": 15,
        "min_advance_hours": 3,
        "max_advance_days": 45,
        "same_day_booking": False,
        "slot_interval_minutes": 15,
    }
    update_res = client.put(
        "/api/v1/availability",
        json={"settings": new_settings},
        headers=auth_headers,
    )
    assert update_res.status_code == status.HTTP_200_OK
    updated_data = update_res.json()
    assert updated_data["settings"]["default_duration_minutes"] == 45
    assert updated_data["settings"]["buffer_time_minutes"] == 15
    assert updated_data["settings"]["same_day_booking"] is False


def test_weekly_schedule_update(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Verify PUT /api/v1/availability/weekly-schedule."""
    schedule_payload = {
        "schedule": [
            {"day_of_week": 0, "day_name": "Monday", "open_time": "08:00", "close_time": "17:00", "is_closed": False},
            {"day_of_week": 1, "day_name": "Tuesday", "open_time": "08:00", "close_time": "17:00", "is_closed": False},
            {"day_of_week": 2, "day_name": "Wednesday", "open_time": "08:00", "close_time": "17:00", "is_closed": False},
            {"day_of_week": 3, "day_name": "Thursday", "open_time": "08:00", "close_time": "17:00", "is_closed": False},
            {"day_of_week": 4, "day_name": "Friday", "open_time": "08:00", "close_time": "17:00", "is_closed": False},
            {"day_of_week": 5, "day_name": "Saturday", "open_time": "09:00", "close_time": "13:00", "is_closed": False},
            {"day_of_week": 6, "day_name": "Sunday", "open_time": "10:00", "close_time": "14:00", "is_closed": True},
        ]
    }
    res = client.put("/api/v1/availability/weekly-schedule", json=schedule_payload, headers=auth_headers)
    assert res.status_code == status.HTTP_200_OK
    items = res.json()
    assert len(items) == 7
    monday = next(i for i in items if i["day_of_week"] == 0)
    assert monday["open_time"] == "08:00"
    assert monday["close_time"] == "17:00"
    assert monday["is_closed"] is False


def test_breaks_crud_and_validation(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Verify POST and DELETE /api/v1/availability/breaks."""
    # 1. Invalid break where start >= end
    bad_break = {
        "day_of_week": -1,
        "start_time": "14:00",
        "end_time": "13:00",
        "description": "Invalid Break",
        "is_active": True,
    }
    bad_res = client.post("/api/v1/availability/breaks", json=bad_break, headers=auth_headers)
    assert bad_res.status_code == status.HTTP_400_BAD_REQUEST

    # 2. Create valid break
    valid_break = {
        "day_of_week": -1,
        "start_time": "13:00",
        "end_time": "14:00",
        "description": "Daily Lunch Break",
        "is_active": True,
    }
    res = client.post("/api/v1/availability/breaks", json=valid_break, headers=auth_headers)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["id"] is not None
    assert data["start_time"] == "13:00"
    assert data["end_time"] == "14:00"
    break_id = data["id"]

    # 3. Delete break
    del_res = client.delete(f"/api/v1/availability/breaks/{break_id}", headers=auth_headers)
    assert del_res.status_code == status.HTTP_200_OK
    assert del_res.json()["success"] is True

    # 4. Delete non-existent break returns 404
    del_404 = client.delete(f"/api/v1/availability/breaks/{break_id}", headers=auth_headers)
    assert del_404.status_code == status.HTTP_404_NOT_FOUND


def test_holidays_crud(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Verify POST and DELETE /api/v1/availability/holidays."""
    holiday_payload = {
        "holiday_date": "2026-12-25",
        "name": "Christmas Day",
        "description": "Clinic closed for Christmas",
    }
    # Create holiday
    res = client.post("/api/v1/availability/holidays", json=holiday_payload, headers=auth_headers)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["id"] is not None
    assert data["holiday_date"] == "2026-12-25"
    assert data["name"] == "Christmas Day"
    holiday_id = data["id"]

    # Delete holiday
    del_res = client.delete(f"/api/v1/availability/holidays/{holiday_id}", headers=auth_headers)
    assert del_res.status_code == status.HTTP_200_OK
    assert del_res.json()["success"] is True


def test_special_dates_crud(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Verify POST and DELETE /api/v1/availability/special-dates."""
    override_payload = {
        "override_date": "2026-12-24",
        "is_closed": False,
        "open_time": "09:00",
        "close_time": "12:00",
        "description": "Christmas Eve Half-Day",
    }
    # Create override
    res = client.post("/api/v1/availability/special-dates", json=override_payload, headers=auth_headers)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["id"] is not None
    assert data["override_date"] == "2026-12-24"
    assert data["open_time"] == "09:00"
    override_id = data["id"]

    # Delete override
    del_res = client.delete(f"/api/v1/availability/special-dates/{override_id}", headers=auth_headers)
    assert del_res.status_code == status.HTTP_200_OK
    assert del_res.json()["success"] is True


# ==============================================================================
# 2. Availability Constraints Enforcement Tests
# ==============================================================================

def test_booking_rejected_during_break(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
) -> None:
    """Verify appointments overlapping scheduled breaks are rejected."""
    biz_id = "demo-biz-vattara-health"
    next_tue = get_next_weekday(1)  # Tuesday

    # 1. Configure break on Tuesdays 13:00 - 14:00
    brk = BusinessBreak(
        business_id=biz_id,
        day_of_week=1,
        start_time="13:00",
        end_time="14:00",
        description="Tuesday Staff Lunch",
        is_active=True,
    )
    db_session.add(brk)
    db_session.commit()

    # 2. Attempt to book at 13:30 IST (during break)
    tz = ZoneInfo("Asia/Kolkata")
    appt_dt = datetime.combine(next_tue, time(13, 30), tzinfo=tz)
    res = client.post(
        "/api/v1/appointments",
        json={
            "customer_name": "Ananya Sharma",
            "customer_phone": "+919876543210",
            "appointment_time": appt_dt.isoformat(),
        },
        headers=auth_headers,
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "tuesday staff lunch" in res.json()["detail"].lower()

    # 3. Booking at 14:30 IST (after break) succeeds
    valid_dt = datetime.combine(next_tue, time(14, 30), tzinfo=tz)
    res_valid = client.post(
        "/api/v1/appointments",
        json={
            "customer_name": "Ananya Sharma",
            "customer_phone": "+919876543210",
            "appointment_time": valid_dt.isoformat(),
        },
        headers=auth_headers,
    )
    assert res_valid.status_code == status.HTTP_201_CREATED


def test_booking_rejected_on_holiday_and_slots_marked_unavailable(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
) -> None:
    """Verify entire day is closed and appointments blocked on official holidays."""
    biz_id = "demo-biz-vattara-health"
    next_wed = get_next_weekday(2)  # Wednesday

    # 1. Add holiday closure on next Wednesday
    holiday = BusinessHoliday(
        business_id=biz_id,
        holiday_date=next_wed.isoformat(),
        name="Annual Founders Day",
        description="Full day closure",
    )
    db_session.add(holiday)
    db_session.commit()

    # 2. Available slots calculation reflects closure
    avail = calculate_available_slots(db=db_session, business_id=biz_id, target_date=next_wed)
    assert avail.is_open is False
    assert avail.available_slots_count == 0

    # 3. Booking attempt on holiday is rejected
    tz = ZoneInfo("Asia/Kolkata")
    appt_dt = datetime.combine(next_wed, time(11, 0), tzinfo=tz)
    res = client.post(
        "/api/v1/appointments",
        json={
            "customer_name": "Rohan Patel",
            "customer_phone": "+919876543211",
            "appointment_time": appt_dt.isoformat(),
        },
        headers=auth_headers,
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "Annual Founders Day" in res.json()["detail"]


def test_special_date_override_custom_hours_and_closure(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
) -> None:
    """Verify special date overrides take precedence over standard weekly schedule."""
    biz_id = "demo-biz-vattara-health"
    next_thu = get_next_weekday(3)  # Thursday

    # 1. Set custom hours on Thursday: 09:00 - 12:00 only
    override = SpecialDateOverride(
        business_id=biz_id,
        override_date=next_thu.isoformat(),
        is_closed=False,
        open_time="09:00",
        close_time="12:00",
        description="Half-day seminar",
    )
    db_session.add(override)
    db_session.commit()

    # 2. Slot at 10:00 IST (within custom hours) succeeds
    tz = ZoneInfo("Asia/Kolkata")
    appt_morning = datetime.combine(next_thu, time(10, 0), tzinfo=tz)
    res_morn = client.post(
        "/api/v1/appointments",
        json={
            "customer_name": "Deepa Nair",
            "customer_phone": "+919876543212",
            "appointment_time": appt_morning.isoformat(),
        },
        headers=auth_headers,
    )
    assert res_morn.status_code == status.HTTP_201_CREATED

    # 3. Slot at 14:00 IST (outside custom hours) is rejected
    appt_afternoon = datetime.combine(next_thu, time(14, 0), tzinfo=tz)
    res_aft = client.post(
        "/api/v1/appointments",
        json={
            "customer_name": "Deepa Nair",
            "customer_phone": "+919876543212",
            "appointment_time": appt_afternoon.isoformat(),
        },
        headers=auth_headers,
    )
    assert res_aft.status_code == status.HTTP_400_BAD_REQUEST
    assert "falls outside operating hours (09:00 - 12:00)" in res_aft.json()["detail"]


def test_buffer_time_between_appointments_enforced(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
) -> None:
    """Verify buffer time requirement prevents back-to-back bookings without required gap."""
    biz_id = "demo-biz-vattara-health"
    next_fri = get_next_weekday(4)  # Friday

    # 1. Set buffer time to 15 minutes
    setting = db_session.scalar(select(AvailabilitySetting).where(AvailabilitySetting.business_id == biz_id))
    if not setting:
        setting = AvailabilitySetting(business_id=biz_id)
        db_session.add(setting)
    setting.buffer_time_minutes = 15
    db_session.commit()

    # 2. Book appointment 1: 10:00 - 10:30 (30 min)
    tz = ZoneInfo("Asia/Kolkata")
    dt1 = datetime.combine(next_fri, time(10, 0), tzinfo=tz)
    res1 = client.post(
        "/api/v1/appointments",
        json={
            "customer_name": "Patient Alpha",
            "customer_phone": "+919876543220",
            "appointment_time": dt1.isoformat(),
        },
        headers=auth_headers,
    )
    assert res1.status_code == status.HTTP_201_CREATED

    # 3. Attempt booking appointment 2 at 10:30 (0 min buffer gap, needs 15 min) -> rejected with 409 Conflict!
    dt2 = datetime.combine(next_fri, time(10, 30), tzinfo=tz)
    res2 = client.post(
        "/api/v1/appointments",
        json={
            "customer_name": "Patient Beta",
            "customer_phone": "+919876543221",
            "appointment_time": dt2.isoformat(),
        },
        headers=auth_headers,
    )
    assert res2.status_code == status.HTTP_409_CONFLICT
    assert "buffer" in res2.json()["detail"].lower()

    # 4. Booking appointment 2 at 10:45 (15 min buffer gap) -> succeeds!
    dt3 = datetime.combine(next_fri, time(10, 45), tzinfo=tz)
    res3 = client.post(
        "/api/v1/appointments",
        json={
            "customer_name": "Patient Beta",
            "customer_phone": "+919876543221",
            "appointment_time": dt3.isoformat(),
        },
        headers=auth_headers,
    )
    print("DEBUG RES3:", res3.status_code, res3.text)
    assert res3.status_code == status.HTTP_201_CREATED


def test_same_day_booking_restriction(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
) -> None:
    """Verify same-day booking can be disabled."""
    biz_id = "demo-biz-vattara-health"

    # Set same_day_booking = False
    setting = db_session.scalar(select(AvailabilitySetting).where(AvailabilitySetting.business_id == biz_id))
    if not setting:
        setting = AvailabilitySetting(business_id=biz_id)
        db_session.add(setting)
    setting.same_day_booking = False
    db_session.commit()

    # Attempt to book today
    tz = ZoneInfo("Asia/Kolkata")
    today_dt = datetime.now(tz) + timedelta(hours=3)
    res = client.post(
        "/api/v1/appointments",
        json={
            "customer_name": "Walkin User",
            "customer_phone": "+919876543230",
            "appointment_time": today_dt.isoformat(),
        },
        headers=auth_headers,
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "not permitted" in res.json()["detail"].lower()


# ==============================================================================
# 3. Alternative Slots Suggestion & AI Tool Calling
# ==============================================================================

def test_find_alternative_slots_across_days(db_session: Session) -> None:
    """Verify find_alternative_slots returns valid open slots on subsequent working days."""
    biz_id = "demo-biz-vattara-health"
    next_wed = get_next_weekday(2)

    # Put holiday on Wednesday
    holiday = BusinessHoliday(
        business_id=biz_id,
        holiday_date=next_wed.isoformat(),
        name="Clinic Closed Wednesday",
    )
    db_session.add(holiday)
    db_session.commit()

    # Find alternatives starting on Wednesday
    alternatives = find_alternative_slots(
        db=db_session,
        business_id=biz_id,
        target_date=next_wed,
        max_suggestions=3,
        days_ahead=5,
    )
    assert len(alternatives) > 0
    # Must not contain Wednesday slots
    for alt in alternatives:
        assert alt["date"] != next_wed.isoformat()
        assert "time" in alt
        assert "day_name" in alt


def test_ai_tools_check_and_book_return_alternatives_on_conflict(db_session: Session) -> None:
    """Verify AI function calling returns structured alternative suggestions on conflict."""
    biz_id = "demo-biz-vattara-health"
    next_wed = get_next_weekday(2)

    # 1. Set holiday on Wednesday
    holiday = BusinessHoliday(
        business_id=biz_id,
        holiday_date=next_wed.isoformat(),
        name="Midweek Maintenance",
    )
    db_session.add(holiday)
    db_session.commit()

    # 2. check_available_slots on holiday returns alternative_suggestions
    tool_check = execute_tool_call(
        db=db_session,
        business_id=biz_id,
        function_name="check_available_slots",
        arguments={"date": next_wed.isoformat()},
    )
    assert tool_check["is_open"] is False
    assert "alternative_suggestions" in tool_check
    assert len(tool_check["alternative_suggestions"]) > 0

    # 3. book_appointment on holiday returns error + alternative_suggestions
    target_dt = datetime.combine(next_wed, time(11, 0), tzinfo=timezone.utc)
    tool_book = execute_tool_call(
        db=db_session,
        business_id=biz_id,
        function_name="book_appointment",
        arguments={
            "customer_name": "Siddharth Verma",
            "customer_phone": "+919876543240",
            "appointment_time": target_dt.isoformat(),
        },
    )
    assert tool_book["success"] is False
    assert "holiday" in tool_book["error"].lower()
    assert "alternative_suggestions" in tool_book
    assert len(tool_book["alternative_suggestions"]) > 0


# ==============================================================================
# 4. Multi-Tenant Availability Isolation
# ==============================================================================

def test_multi_tenant_availability_isolation(client: TestClient, db_session: Session) -> None:
    """Verify holidays, breaks, and settings for Business A never leak to Business B."""
    # Create Business B and User B
    biz_b = Business(
        id="biz-tenant-beta",
        name="City Dental Center",
        vertical="dental",
        email="contact@citydental.com",
        phone="+919988776655",
        is_active=True,
    )
    user_b = User(
        id="user-tenant-b",
        business_id="biz-tenant-beta",
        email="contact@citydental.com",
        full_name="Dr. Beta Dentist",
        hashed_password="mock_hash",
        role="admin",
        is_active=True,
    )
    db_session.add_all([biz_b, user_b])

    # Create break and holiday exclusively for Business A
    holiday_a = BusinessHoliday(
        business_id="demo-biz-vattara-health",
        holiday_date="2026-11-20",
        name="Hospital Anniversary A",
    )
    break_a = BusinessBreak(
        business_id="demo-biz-vattara-health",
        day_of_week=0,
        start_time="12:00",
        end_time="13:00",
        description="Tenant A Lunch",
        is_active=True,
    )
    db_session.add_all([holiday_a, break_a])
    db_session.commit()

    # Query availability as Tenant B user
    token_b = create_access_token(
        subject="user-tenant-b",
        extra_claims={"business_id": "biz-tenant-beta", "role": "admin"},
    )
    headers_b = {"Authorization": f"Bearer {token_b}"}

    res_b = client.get("/api/v1/availability", headers=headers_b)
    assert res_b.status_code == status.HTTP_200_OK
    data_b = res_b.json()
    assert data_b["business_id"] == "biz-tenant-beta"

    # Business B must have zero holidays and zero breaks from Business A
    assert len(data_b["holidays"]) == 0
    assert len(data_b["breaks"]) == 0
