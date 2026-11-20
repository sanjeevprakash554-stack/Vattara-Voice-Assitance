"""Regression tests for Priority 1: Phone Number Integrity.

Validates the full 8-step phone-number lifecycle:
1. Plivo inbound caller ID normalization.
2. ConversationSession caller_phone storage.
3. Deepgram transcription noise sanitization and spoken extraction.
4. Customer lookup and creation.
5. Appointment booking tool arguments validation.
6. Database persistence.
7. Duplicate appointment validation across phone representations.
8. Reminder recipient phone integrity.
"""

from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.assistant import Service
from app.models.business import Business
from app.models.business_hours import BusinessHour
from app.models.call import Call
from app.models.conversation_session import ConversationSession
from app.models.customer import Customer
from app.models.reminder import Reminder
from app.schemas.appointment import AppointmentCreate
from app.services.appointment_service import book_appointment_core
from app.services.scheduling_service import validate_booking_feasibility
from app.services.telephony.phone_utils import (
    clean_phone_digits,
    extract_phone_number,
    normalize_indian_mobile_number,
    sanitize_transcription_noise,
)
from app.services.voice_assistant_service import get_or_create_conversation_session


# ---------------------------------------------------------------------------
# Unit Tests for Normalization & Noise Sanitization
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "input_phone, expected",
    [
        ("+917904743468", "+917904743468"),
        ("917904743468", "+917904743468"),
        ("07904743468", "+917904743468"),
        ("7904743468", "+917904743468"),
        ("+91 79047 43468", "+917904743468"),
        ("+91-79047-43468", "+917904743468"),
        ("(+91) 7904743468", "+917904743468"),
        ("9840123456", "+919840123456"),
        ("6380123456", "+916380123456"),
        ("8901234567", "+918901234567"),
    ],
)
def test_normalize_valid_indian_mobile_numbers(input_phone: str, expected: str):
    """Ensure all valid variations of Indian 10-digit mobile numbers normalize to +91XXXXXXXXXX."""
    result = normalize_indian_mobile_number(input_phone)
    assert result == expected


@pytest.mark.parametrize(
    "invalid_input",
    [
        # The exact corrupted 11-digit number from Deepgram transcription artifact:
        "70904743468",
        # Truncated or short numbers (must NEVER be padded or accepted):
        "790474346",
        "12345",
        "987654321",
        "",
        # Overlong numbers (must NEVER be silently truncated):
        "9179047434689",
        "+91790474346899",
        # Invalid first digit for Indian mobile (valid mobile starts with 6, 7, 8, 9):
        "+915904743468",
        "1904743468",
        "2904743468",
        # Landline with std code (should not be treated as mobile):
        "04428289000",
    ],
)
def test_normalize_invalid_numbers_returns_none(invalid_input: str):
    """Ensure invalid-length or invalid-start numbers are rejected and NEVER silently truncated."""
    result = normalize_indian_mobile_number(invalid_input)
    assert result is None, f"Expected {invalid_input} to be rejected, but got {result}"


def test_sanitize_deepgram_time_artifact_noise():
    """Verify Deepgram smart_format artifact '09:04' inside digits is sanitized."""
    # When user said "7 9 0 4 7 4 3 4 6 8", Deepgram output "7 09:04 743468"
    noisy_transcript = "My phone number is 7 09:04 743468 please call me"
    sanitized = sanitize_transcription_noise(noisy_transcript)
    assert "09:04" not in sanitized
    extracted = extract_phone_number(noisy_transcript)
    assert extracted == "+917904743468"


def test_extract_phone_number_various_noisy_utterances():
    """Verify extraction across Tamil and English noisy transcriptions."""
    utterance_tamil = "என்னோட phone number 7 09:04 743468"
    assert extract_phone_number(utterance_tamil) == "+917904743468"

    utterance_clean = "Call me at +91 98401 23456 tomorrow"
    assert extract_phone_number(utterance_clean) == "+919840123456"

    utterance_local = "Mobile is 8939123456"
    assert extract_phone_number(utterance_local) == "+918939123456"


# ---------------------------------------------------------------------------
# End-to-End Lifecycle Tests
# ---------------------------------------------------------------------------

@pytest.fixture
def setup_lifecycle_clinic(db_session: Session) -> Business:
    """Setup clinic with service and hours."""
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


def test_complete_8_step_phone_lifecycle(db_session: Session, setup_lifecycle_clinic: Business):
    """Trace and verify all 8 steps of phone number lifecycle without digit corruption."""
    biz = setup_lifecycle_clinic

    # Step 1: Plivo Inbound Caller ID
    plivo_raw_caller = "917904743468"  # Plivo standard without plus
    norm_caller = normalize_indian_mobile_number(plivo_raw_caller)
    assert norm_caller == "+917904743468"

    # Step 2: ConversationSession caller_phone storage
    session = get_or_create_conversation_session(
        db=db_session,
        call_sid="test-call-sid-12345",
        business_id=biz.id,
        caller_phone=plivo_raw_caller,
    )
    assert session.caller_phone == "+917904743468"

    # Step 3: Deepgram transcription and spoken-number extraction
    speech_text = "என்னோட பேர் is கியூ என்னோட phone number 7 09:04 743468"
    extracted_phone = extract_phone_number(speech_text)
    assert extracted_phone == "+917904743468"

    # Step 4: Customer lookup and creation
    customer = db_session.execute(
        select(Customer).where(Customer.phone == "+917904743468")
    ).scalar_one_or_none()
    if not customer:
        customer = Customer(
            business_id=biz.id,
            name="Q",
            phone=norm_caller,
        )
        db_session.add(customer)
        db_session.commit()
    assert customer.phone == "+917904743468"

    # Step 5 & 6: Appointment booking tool arguments and Database persistence
    # Future slot 2 days ahead at 10:00 AM IST (04:30 UTC)
    future_date = (datetime.now(timezone.utc) + timedelta(days=2)).date()
    future_utc = datetime(future_date.year, future_date.month, future_date.day, 4, 30, tzinfo=timezone.utc)

    # Even if LLM erroneously passes corrupted "70904743468", appointment service normalizes or rejects
    # Here we test book_appointment_core with customer_phone
    payload = AppointmentCreate(
        customer_name="Q",
        customer_phone="+917904743468",
        service_id="demo-service-3",
        appointment_time=future_utc,
        notes="Step 6 persistence test",
    )
    appt = book_appointment_core(
        db=db_session,
        business_id=biz.id,
        payload=payload,
    )
    assert appt is not None
    assert appt.id is not None

    # Verify customer associated with appointment has +917904743468
    appt_customer = db_session.get(Customer, appt.customer_id)
    assert appt_customer.phone == "+917904743468"

    # Step 7: Duplicate appointment validation across representations
    # Trying to book with "917904743468" or "7904743468" must be detected as duplicate and raise HTTP 409!
    with pytest.raises(HTTPException) as exc_info1:
        validate_booking_feasibility(
            db=db_session,
            business_id=biz.id,
            appointment_time=future_utc,
            customer_phone="917904743468",
        )
    assert exc_info1.value.status_code == 409

    with pytest.raises(HTTPException) as exc_info2:
        validate_booking_feasibility(
            db=db_session,
            business_id=biz.id,
            appointment_time=future_utc,
            customer_phone="7904743468",
        )
    assert exc_info2.value.status_code == 409

    # Step 8: Reminder recipient integrity
    reminders = db_session.execute(
        select(Reminder).where(Reminder.appointment_id == appt.id)
    ).scalars().all()
    assert len(reminders) >= 1, "At least one reminder must be scheduled"
    for reminder in reminders:
        assert reminder.customer.phone == "+917904743468"
        assert reminder.customer.phone != "70904743468"
