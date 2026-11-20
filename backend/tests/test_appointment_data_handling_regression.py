"""Regression test suite for appointment data handling in Vattara Voice Assistance.

Verifies:
1. Speech transcription and natural-language date/time extraction for "Tomorrow at 10:00 AM IST".
2. UTC-to-IST conversion and verbal speech formatting (10:00 AM IST, NOT 04:30 AM).
3. Prevention of double timezone conversion.
4. Customer name extraction and persistence ("Steve" instead of "Walk-in Customer").
5. Service selection persistence ("Pediatric Health Checkup" instead of "General Appointment").
6. Complete confirmed booking through 5-turn voice conversation with database persistence.
7. Correct dashboard REST API serialization and response values.
"""

from datetime import date, datetime, timedelta, timezone
import json
from unittest.mock import MagicMock
import uuid
from zoneinfo import ZoneInfo
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.api.routes.appointments import create_appointment, get_appointment, list_appointments
from app.models.appointment import Appointment
from app.models.assistant import Service
from app.models.business import Business
from app.models.business_hours import BusinessHour
from app.models.call import Call
from app.models.conversation_session import ConversationSession
from app.models.customer import Customer
from app.models.user import User
from app.schemas.appointment import AppointmentCreate, AppointmentResponse
from app.services.appointment_service import book_appointment_core
from app.services.voice_assistant_service import (
    extract_caller_name,
    extract_date_and_time_parts,
    format_confirmation_date,
    format_confirmation_time,
    match_service_from_catalog,
    process_conversational_turn,
)


@pytest.fixture
def ist_clinic(db_session: Session) -> Business:
    """Fixture providing an active clinic in Asia/Kolkata timezone with production services."""
    biz_id = "demo-biz-vattara-health"
    biz = db_session.get(Business, biz_id)
    if not biz:
        biz = Business(
            id=biz_id,
            name="Vattara City Clinic & Diagnostics",
            vertical="clinic",
            email="reception@vattaraclinic.com",
            phone="+914428289000",
            timezone="Asia/Kolkata",
            is_active=True,
        )
        db_session.add(biz)
        db_session.flush()

    # Ensure operating hours exist
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
        else:
            bh.is_closed = False

    # Ensure Pediatric Health Checkup exists
    ped_service = db_session.get(Service, "demo-service-3")
    if not ped_service:
        ped_service = Service(
            id="demo-service-3",
            business_id=biz.id,
            name="Pediatric Health Checkup",
            duration_minutes=30,
            price=700.0,
            is_active=True,
        )
        db_session.add(ped_service)

    db_session.commit()
    return biz


# ==============================================================================
# Task 1: Natural-Language Date/Time Extraction & UTC Conversion
# ==============================================================================

def test_natural_language_date_time_extraction_tomorrow_10am_ist():
    """Verify 'Tomorrow at 10 AM' in Asia/Kolkata extracts to tomorrow 10:00 IST -> UTC 04:30."""
    # Reference: Monday Nov 16, 2026, 05:30:00 UTC (= 11:00 AM IST)
    fixed_now_utc = datetime(2026, 11, 16, 5, 30, 0, tzinfo=timezone.utc)
    target_date, time_parts = extract_date_and_time_parts("Tomorrow at 10 AM", reference_dt=fixed_now_utc)

    assert target_date == date(2026, 11, 17), "Target date should be Nov 17, 2026"
    assert time_parts == (10, 0), "Target time should be 10:00"

    # Convert local business time to UTC
    biz_tz = ZoneInfo("Asia/Kolkata")
    local_dt = datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        time_parts[0],
        time_parts[1],
        tzinfo=biz_tz,
    )
    utc_dt = local_dt.astimezone(timezone.utc)

    # 10:00 AM IST is 04:30 AM UTC
    assert utc_dt.year == 2026
    assert utc_dt.month == 11
    assert utc_dt.day == 17
    assert utc_dt.hour == 4
    assert utc_dt.minute == 30
    assert utc_dt.tzinfo == timezone.utc


# ==============================================================================
# Task 2: UTC-to-IST Conversion & Speech Formatting
# ==============================================================================

def test_utc_to_ist_conversion_and_speech_formatting():
    """Verify UTC 04:30 is formatted as 10:00 AM IST for verbal confirmation."""
    biz_tz = ZoneInfo("Asia/Kolkata")
    utc_dt = datetime(2026, 11, 17, 4, 30, 0, tzinfo=timezone.utc)

    # Convert to local timezone
    local_dt = utc_dt.astimezone(biz_tz)
    assert local_dt.hour == 10
    assert local_dt.minute == 0

    # Verbal confirmation time must say 10:00 AM, NOT 4:30 AM
    time_str = format_confirmation_time(utc_dt, language="en-IN", biz_tz=biz_tz)
    assert time_str == "10:00 AM"

    # Even if datetime is naive (as loaded from SQLite), it must be treated as UTC
    naive_utc_dt = datetime(2026, 11, 17, 4, 30, 0)
    time_str_naive = format_confirmation_time(naive_utc_dt, language="en-IN", biz_tz=biz_tz)
    assert time_str_naive == "10:00 AM"

    date_str = format_confirmation_date(utc_dt, language="en-IN", biz_tz=biz_tz)
    assert "November 17, 2026" in date_str


# ==============================================================================
# Task 3: Prevention of Double Timezone Conversion
# ==============================================================================

def test_prevention_of_double_timezone_conversion(db_session: Session, ist_clinic: Business):
    """Verify that timezone-aware UTC datetime is not converted twice."""
    biz_tz = ZoneInfo("Asia/Kolkata")
    utc_time = datetime(2026, 11, 17, 4, 30, 0, tzinfo=timezone.utc)

    # 1. Localize to IST
    ist_time = utc_time.astimezone(biz_tz)
    assert ist_time.hour == 10
    assert ist_time.minute == 0

    # 2. Re-converting or passing to format_confirmation_time with biz_tz must NOT shift it again
    formatted = format_confirmation_time(ist_time, language="en-IN", biz_tz=biz_tz)
    assert formatted == "10:00 AM", f"Expected 10:00 AM, but got {formatted} (double converted!)"

    # 3. Create appointment in DB with UTC time
    cust = Customer(
        id=f"cust_{uuid.uuid4().hex[:8]}",
        business_id=ist_clinic.id,
        name="Steve",
        phone="+919840112233",
    )
    db_session.add(cust)
    db_session.flush()

    appt = Appointment(
        id=f"appt_{uuid.uuid4().hex[:8]}",
        business_id=ist_clinic.id,
        customer_id=cust.id,
        service_id="demo-service-3",
        appointment_time=utc_time.replace(tzinfo=None),  # SQLite naive UTC
        end_time=(utc_time + timedelta(minutes=30)).replace(tzinfo=None),
        status="upcoming",
        source="voice_ai",
    )
    db_session.add(appt)
    db_session.commit()
    db_session.refresh(appt)

    # 4. Serialize with AppointmentResponse
    resp = AppointmentResponse.model_validate(appt)
    serialized = resp.model_dump(mode="json")

    # Timezone offset MUST be present and be UTC (+00:00 or Z)
    raw_iso = serialized["appointment_time"]
    assert raw_iso.endswith("+00:00") or raw_iso.endswith("Z"), f"Expected UTC offset in {raw_iso}"

    # Parsing the ISO string with timezone awareness
    parsed = datetime.fromisoformat(raw_iso)
    in_ist = parsed.astimezone(biz_tz)
    assert in_ist.hour == 10
    assert in_ist.minute == 0


# ==============================================================================
# Task 4: Customer Name Extraction & Persistence
# ==============================================================================

def test_customer_name_extraction_and_persistence(db_session: Session, ist_clinic: Business):
    """Verify 'Steve' is extracted and persists in Customer record, preventing 'Walk-in Customer'."""
    # 1. Extraction checks
    assert extract_caller_name("My name is Steve") == "Steve"
    assert extract_caller_name("Steve", is_awaiting_name=True) == "Steve"
    assert extract_caller_name("The patient is Steve") == "Steve"
    assert extract_caller_name("Book for Steve") == "Steve"

    # 2. Existing customer with auto-generated/old name is updated when caller provides 'Steve'
    caller_phone = "+919840998877"
    existing_cust = Customer(
        id=f"cust_{uuid.uuid4().hex[:8]}",
        business_id=ist_clinic.id,
        name="Caller +919840998877",
        phone=caller_phone,
    )
    db_session.add(existing_cust)
    db_session.commit()

    # Book with customer_name="Steve"
    payload = AppointmentCreate(
        customer_name="Steve",
        customer_phone=caller_phone,
        service_id="demo-service-3",
        appointment_time=datetime(2026, 11, 17, 4, 30, tzinfo=timezone.utc),
    )
    appt = book_appointment_core(
        db=db_session,
        business_id=ist_clinic.id,
        payload=payload,
        validate_conflicts=False,
    )

    db_session.refresh(existing_cust)
    assert existing_cust.name == "Steve", "Existing customer record was not updated with confirmed name 'Steve'!"
    assert appt.customer.name == "Steve"

    # Response schema must output customer_name == "Steve"
    resp = AppointmentResponse.model_validate(appt)
    assert resp.customer_name == "Steve"
    assert resp.customer_name != "Walk-in Customer"


# ==============================================================================
# Task 5: Service Selection Persistence
# ==============================================================================

def test_service_selection_persistence(db_session: Session, ist_clinic: Business):
    """Verify 'Pediatric Health Checkup' is matched from catalog and persisted correctly."""
    services = db_session.query(Service).filter(Service.business_id == ist_clinic.id).all()

    # Exact match
    matched = match_service_from_catalog("Pediatric Health Checkup", services)
    assert matched is not None
    assert matched.id == "demo-service-3"
    assert matched.name == "Pediatric Health Checkup"

    # Phonetic misrecognition variant
    fuzzy_matched = match_service_from_catalog("Mediatrix head checkup.", services)
    assert fuzzy_matched is not None
    assert fuzzy_matched.id == "demo-service-3"

    # Booking persistence
    payload = AppointmentCreate(
        customer_name="Steve",
        customer_phone="+919840554433",
        service_id=matched.id,
        appointment_time=datetime(2026, 11, 17, 4, 30, tzinfo=timezone.utc),
    )
    appt = book_appointment_core(
        db=db_session,
        business_id=ist_clinic.id,
        payload=payload,
        validate_conflicts=False,
    )

    assert appt.service_id == "demo-service-3"
    assert appt.service.name == "Pediatric Health Checkup"

    resp = AppointmentResponse.model_validate(appt)
    assert resp.service_name == "Pediatric Health Checkup"
    assert resp.service_name != "General Appointment"


# ==============================================================================
# Task 6: Full 5-Turn Voice Conversational Booking Flow
# ==============================================================================

def test_full_voice_booking_flow_end_to_end(db_session: Session, ist_clinic: Business):
    """Simulate the exact 5-turn real phone call and verify DB persistence."""
    call_uuid = f"call_test_{uuid.uuid4().hex[:10]}"
    caller_phone = "+919840332211"

    # Initial call record created upon incoming ring
    call_rec = Call(
        id=call_uuid,
        business_id=ist_clinic.id,
        caller_name=f"Caller {caller_phone}",
        caller_phone=caller_phone,
        call_type="incoming",
        status="in_progress",
        duration_seconds=0,
        summary=f"Incoming call via Plivo (CallUUID: {call_uuid})",
        initiated_at=datetime.now(timezone.utc),
    )
    db_session.add(call_rec)
    db_session.commit()

    # Conversation session begins
    session = ConversationSession(
        call_sid=call_uuid,
        business_id=ist_clinic.id,
        caller_phone=caller_phone,
        customer_name=None,
        step="greeting",
        language="en-IN",
        detected_language="en-IN",
        dialog_history=json.dumps([]),
        metadata_json=json.dumps({"require_confirmation": True}),
        retry_count=0,
        is_completed=False,
    )
    db_session.add(session)
    db_session.commit()

    # Turn 1: "Want to book an appointment."
    resp1, cont1 = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="Want to book an appointment.",
        business=ist_clinic,
    )
    assert cont1 is True
    assert session.intent == "booking"
    assert session.step == "awaiting_service"

    # Turn 2: "Pediatric Health Checkup"
    resp2, cont2 = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="Pediatric Health Checkup",
        business=ist_clinic,
    )
    assert cont2 is True
    assert session.service_id == "demo-service-3"
    assert session.service_name == "Pediatric Health Checkup"
    assert session.step == "awaiting_datetime"

    # Turn 3: "Tomorrow at 10 AM"
    resp3, cont3 = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="Tomorrow at 10 AM.",
        business=ist_clinic,
    )
    assert cont3 is True
    assert session.appointment_datetime_iso is not None
    assert session.step == "awaiting_name"
    assert "full name" in resp3.lower()

    # Turn 4: "Steve"
    resp4, cont4 = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="My name is Steve.",
        business=ist_clinic,
    )
    assert cont4 is True
    assert session.customer_name == "Steve"
    assert session.step == "awaiting_confirmation"
    # Assistant verbally speaks back the appointment details
    assert "Steve" in resp4
    assert "Pediatric Health Checkup" in resp4
    assert "10:00 AM" in resp4, f"Assistant spoke wrong time in verbal confirmation: {resp4}"
    assert "4:30 AM" not in resp4, "Assistant spoke UTC time 4:30 AM instead of IST 10:00 AM!"

    # Turn 5: "Yes, please confirm."
    resp5, cont5 = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="Yes, please confirm.",
        business=ist_clinic,
    )
    assert cont5 is False
    assert session.step == "completed"
    assert session.is_completed is True
    assert session.booking_id is not None
    assert "confirmed" in resp5.lower()
    assert "Steve" in resp5
    assert "10:00 AM" in resp5

    # DATABASE VERIFICATION
    # 1. Appointment record
    appt = db_session.get(Appointment, session.booking_id)
    assert appt is not None
    assert appt.business_id == ist_clinic.id
    assert appt.service_id == "demo-service-3"
    assert appt.service.name == "Pediatric Health Checkup"
    assert appt.customer.name == "Steve"
    assert appt.customer.phone == caller_phone
    assert appt.status == "upcoming"

    # 2. Call record linked and updated
    db_session.refresh(call_rec)
    assert call_rec.status == "completed"
    assert call_rec.caller_name == "Steve"
    assert call_rec.customer_id == appt.customer_id
    assert session.booking_id in call_rec.summary
    assert "Steve" in call_rec.transcript
    assert "Pediatric Health Checkup" in call_rec.transcript
    assert "10:00 AM" in call_rec.transcript


# ==============================================================================
# Task 7: Correct Dashboard REST API Response
# ==============================================================================

def test_dashboard_api_response_correctness(db_session: Session, ist_clinic: Business):
    """Verify that the dashboard API returns top-level customer_name, service_name, and UTC ISO time."""
    admin_user = db_session.get(User, "demo-user-admin")
    if not admin_user:
        admin_user = User(
            id="demo-user-admin",
            business_id=ist_clinic.id,
            email="admin@vattara.com",
            full_name="Dr. Rajesh Kumar",
            role="admin",
            is_active=True,
        )
        db_session.add(admin_user)
        db_session.commit()

    # Appointment for a future date (2 days from now) at 10:00 AM IST = 04:30 AM UTC
    future_date = (datetime.now(timezone.utc) + timedelta(days=2)).date()
    future_time_utc = datetime(future_date.year, future_date.month, future_date.day, 4, 30, tzinfo=timezone.utc)
    payload = AppointmentCreate(
        customer_name="Steve",
        customer_phone="+919840123999",
        service_id="demo-service-3",
        appointment_time=future_time_utc,
        notes="Regression verification for Steve",
    )

    # 1. Create Appointment via create_appointment endpoint
    created_resp = create_appointment(payload=payload, current_user=admin_user, db=db_session)
    created_item = created_resp.model_dump(mode="json")

    assert created_item["customer_name"] == "Steve"
    assert created_item["service_name"] == "Pediatric Health Checkup"
    assert created_item["status"] == "upcoming"
    appt_id = created_item["id"]

    # 2. List Appointments endpoint: list_appointments
    items = list_appointments(status_filter=None, limit=50, offset=0, current_user=admin_user, db=db_session)
    serialized_items = [item.model_dump(mode="json") for item in items]
    assert isinstance(serialized_items, list)

    target_item = next((item for item in serialized_items if item["id"] == appt_id), None)
    assert target_item is not None, f"Appointment {appt_id} not found in API response!"

    # 3. Customer Name Check
    assert target_item["customer_name"] == "Steve"
    assert target_item["customer_name"] != "Walk-in Customer"

    # 4. Service Name Check
    assert target_item["service_name"] == "Pediatric Health Checkup"
    assert target_item["service_name"] != "General Appointment"

    # 5. Timezone Serialized Format Check
    raw_time_str = target_item["appointment_time"]
    assert raw_time_str.endswith("+00:00") or raw_time_str.endswith("Z"), f"Expected UTC offset in {raw_time_str}"

    # 6. Conversion to Asia/Kolkata gives 10:00 AM
    parsed_dt = datetime.fromisoformat(raw_time_str)
    ist_tz = ZoneInfo("Asia/Kolkata")
    ist_dt = parsed_dt.astimezone(ist_tz)
    assert ist_dt.hour == 10
    assert ist_dt.minute == 0
    assert ist_dt.strftime("%I:%M %p") == "10:00 AM"

    # 7. Single appointment endpoint: get_appointment
    single_resp = get_appointment(appointment_id=appt_id, current_user=admin_user, db=db_session)
    single_item = single_resp.model_dump(mode="json")
    assert single_item["customer_name"] == "Steve"
    assert single_item["service_name"] == "Pediatric Health Checkup"
    assert single_item["status"] == "upcoming"
