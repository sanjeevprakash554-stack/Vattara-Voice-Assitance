"""Comprehensive Test Suite for Natural AI Receptionist Conversation System (22 Scenarios).

Covers:
1. Complete appointment booking.
2. Multiple details in one sentence.
3. Date and time supplied separately.
4. Date and time supplied in reverse order.
5. Changing an already selected appointment time.
6. Unavailable slot handling.
7. Alternative slot selection.
8. Booking verbal confirmation.
9. Rescheduling.
10. Cancellation.
11. Existing appointment enquiry.
12. General business enquiries (hours, address, services).
13. English conversation.
14. Tamil conversation.
15. Telugu conversation.
16. Tanglish conversation.
17. Teluglish conversation.
18. Caller interruption (barge-in).
19. Unclear speech recovery.
20. Duplicate turn prevention.
21. Database failure recovery.
22. Call closing and termination.
"""

import asyncio
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import json
import struct
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.appointment import Appointment
from app.models.assistant import AssistantConfig, Service
from app.models.business import Business
from app.models.business_hours import BusinessHour
from app.models.call import Call
from app.models.conversation_session import ConversationSession
from app.models.customer import Customer
from app.services.scheduling_service import (
    calculate_available_slots,
    find_alternative_slots,
)
from app.services.streaming.audio_codec import pcm16_to_mulaw, mulaw_to_base64
from app.services.streaming.session_manager import AudioStreamSession, stream_manager
from app.services.streaming.stream_orchestrator import StreamOrchestrator
from app.services.voice_assistant_service import (
    detect_intent,
    extract_caller_name,
    extract_date_and_time_parts,
    extract_datetime_from_speech,
    format_confirmation_date,
    format_confirmation_time,
    match_service_from_catalog,
    process_conversational_turn,
)


@pytest.fixture
def receptionist_env(db_session: Session) -> dict:
    """Fixture providing an active business tenant with services and operating hours."""
    biz = Business(
        id="demo-receptionist-biz",
        name="Vattara City Medical Center",
        vertical="clinic",
        email="reception@vattaramedical.com",
        phone="+914428280000",
        address="124 Anna Salai, Thousand Lights, Chennai, Tamil Nadu 600006",
        timezone="Asia/Kolkata",
        is_active=True,
    )
    db_session.add(biz)
    db_session.flush()

    cfg = AssistantConfig(
        business_id=biz.id,
        assistant_name="Vattara Health Assistant",
        language="en-IN",
        working_hours="Monday to Saturday: 9:00 AM to 6:00 PM, Sunday: Closed",
    )
    db_session.add(cfg)

    # Mon-Sun open 9:00-18:00
    for dow in range(7):
        bh = BusinessHour(
            business_id=biz.id,
            day_of_week=dow,
            open_time="09:00",
            close_time="18:00",
            is_closed=False,
        )
        db_session.add(bh)

    # Active services
    s_general = Service(
        id="srv-receptionist-general",
        business_id=biz.id,
        name="General Physician Consultation",
        duration_minutes=30,
        price=500.0,
        is_active=True,
    )
    s_cardio = Service(
        id="srv-receptionist-cardio",
        business_id=biz.id,
        name="Cardiology Consultation & ECG",
        duration_minutes=45,
        price=1200.0,
        is_active=True,
    )
    s_dental = Service(
        id="srv-receptionist-dental",
        business_id=biz.id,
        name="Dental Care and Cleaning",
        duration_minutes=30,
        price=800.0,
        is_active=True,
    )
    db_session.add_all([s_general, s_cardio, s_dental])
    db_session.commit()

    return {
        "business": biz,
        "general": s_general,
        "cardio": s_cardio,
        "dental": s_dental,
    }


def _make_session(db_session: Session, biz_id: str, call_sid: str, phone: str = "+919876543210", language: str = "en-IN") -> ConversationSession:
    sess = ConversationSession(
        call_sid=call_sid,
        business_id=biz_id,
        caller_phone=phone,
        step="greeting",
        language=language,
        detected_language=language,
        dialog_history=json.dumps([]),
        metadata_json=json.dumps({"require_confirmation": True}),
        retry_count=0,
        is_completed=False,
    )
    db_session.add(sess)
    db_session.commit()
    db_session.refresh(sess)
    return sess


# ------------------------------------------------------------------------------
# 1. Complete appointment booking
# ------------------------------------------------------------------------------
def test_scenario_1_complete_appointment_booking(db_session: Session, receptionist_env: dict):
    biz = receptionist_env["business"]
    session = _make_session(db_session, biz.id, "call-scen-1")

    # Turn 1: Caller states service
    prompt1, cont1 = process_conversational_turn(db_session, session, "I want to book an appointment for General Physician", biz, require_confirmation=True)
    assert cont1 is True
    assert session.step == "awaiting_datetime"
    assert session.service_id == receptionist_env["general"].id

    # Turn 2: Caller states date and time
    prompt2, cont2 = process_conversational_turn(db_session, session, "Tomorrow at 10 AM", biz, require_confirmation=True)
    assert cont2 is True
    assert session.step == "awaiting_name"
    assert session.appointment_datetime_iso is not None

    # Turn 3: Caller gives name
    prompt3, cont3 = process_conversational_turn(db_session, session, "My name is John Doe", biz, require_confirmation=True)
    assert cont3 is True
    assert session.step == "awaiting_confirmation"
    assert "John Doe" in prompt3
    assert "confirm" in prompt3.lower()

    # Turn 4: Caller confirms verbally
    prompt4, cont4 = process_conversational_turn(db_session, session, "Yes, please confirm", biz, require_confirmation=True)
    assert cont4 is False
    assert session.step == "completed"
    assert session.is_completed is True
    assert session.booking_id is not None
    assert "confirmed" in prompt4.lower()

    # Verify DB Appointment
    appt = db_session.get(Appointment, session.booking_id)
    assert appt is not None
    assert appt.status == "upcoming"
    assert appt.customer.name == "John Doe"


# ------------------------------------------------------------------------------
# 2. Multiple details in one sentence
# ------------------------------------------------------------------------------
def test_scenario_2_multiple_details_in_one_sentence(db_session: Session, receptionist_env: dict):
    biz = receptionist_env["business"]
    session = _make_session(db_session, biz.id, "call-scen-2")

    # Single comprehensive turn
    prompt1, cont1 = process_conversational_turn(
        db_session,
        session,
        "I want a cardiology appointment tomorrow at 11 AM, my name is Arvind Swamy",
        biz,
        require_confirmation=True,
    )
    assert cont1 is True
    assert session.step == "awaiting_confirmation"
    assert session.service_id == receptionist_env["cardio"].id
    assert session.customer_name == "Arvind Swamy"
    assert "Arvind Swamy" in prompt1
    assert "confirm" in prompt1.lower()

    # Verbal confirmation
    prompt2, cont2 = process_conversational_turn(db_session, session, "Yes confirm it", biz, require_confirmation=True)
    assert cont2 is False
    assert session.step == "completed"
    assert session.is_completed is True
    assert session.booking_id is not None


# ------------------------------------------------------------------------------
# 3. Date and time supplied separately (Date then Time)
# ------------------------------------------------------------------------------
def test_scenario_3_date_and_time_supplied_separately(db_session: Session, receptionist_env: dict):
    biz = receptionist_env["business"]
    session = _make_session(db_session, biz.id, "call-scen-3")

    # Turn 1: Service
    process_conversational_turn(db_session, session, "Book Dental", biz, require_confirmation=True)
    assert session.step == "awaiting_datetime"

    # Turn 2: Date only ("Tomorrow")
    prompt2, cont2 = process_conversational_turn(db_session, session, "Tomorrow", biz, require_confirmation=True)
    assert cont2 is True
    assert session.step == "awaiting_datetime"
    assert "what time" in prompt2.lower()

    # Turn 3: Time only ("10 AM")
    prompt3, cont3 = process_conversational_turn(db_session, session, "10:00 AM", biz, require_confirmation=True)
    assert cont3 is True
    assert session.step == "awaiting_name"
    assert session.appointment_datetime_iso is not None

    # Turn 4: Name
    process_conversational_turn(db_session, session, "Sarah Connor", biz, require_confirmation=True)
    assert session.step == "awaiting_confirmation"

    # Turn 5: Confirm
    _, cont5 = process_conversational_turn(db_session, session, "Yes", biz, require_confirmation=True)
    assert cont5 is False
    assert session.is_completed is True


# ------------------------------------------------------------------------------
# 4. Date and time supplied in reverse order (Time then Date)
# ------------------------------------------------------------------------------
def test_scenario_4_date_and_time_supplied_in_reverse_order(db_session: Session, receptionist_env: dict):
    biz = receptionist_env["business"]
    session = _make_session(db_session, biz.id, "call-scen-4")

    # Turn 1: Service and Time ("General Physician at 2 PM")
    prompt1, cont1 = process_conversational_turn(db_session, session, "I want General Physician at 2 PM", biz, require_confirmation=True)
    assert cont1 is True
    assert session.step == "awaiting_datetime"
    assert "which date" in prompt1.lower()

    # Turn 2: Date ("Day after tomorrow")
    prompt2, cont2 = process_conversational_turn(db_session, session, "Day after tomorrow", biz, require_confirmation=True)
    assert cont2 is True
    assert session.step == "awaiting_name"
    assert session.appointment_datetime_iso is not None

    # Turn 3: Name
    process_conversational_turn(db_session, session, "Ravi Kumar", biz, require_confirmation=True)
    assert session.step == "awaiting_confirmation"


# ------------------------------------------------------------------------------
# 5. Changing an already selected appointment time (Correction)
# ------------------------------------------------------------------------------
def test_scenario_5_changing_already_selected_time(db_session: Session, receptionist_env: dict):
    biz = receptionist_env["business"]
    session = _make_session(db_session, biz.id, "call-scen-5")

    # Initial setup to awaiting_confirmation
    process_conversational_turn(db_session, session, "Cardiology tomorrow at 10 AM, name is Priya Sharma", biz, require_confirmation=True)
    assert session.step == "awaiting_confirmation"
    orig_dt = session.appointment_datetime_iso

    # Caller changes time: "Actually 11 AM"
    prompt_corr, cont_corr = process_conversational_turn(db_session, session, "Actually make it 11 AM", biz, require_confirmation=True)
    assert cont_corr is True
    assert session.step == "awaiting_confirmation"
    assert session.appointment_datetime_iso != orig_dt
    assert "11:00 AM" in prompt_corr
    assert "confirm" in prompt_corr.lower()

    # Caller confirms the new time
    _, cont_done = process_conversational_turn(db_session, session, "Yes please confirm", biz, require_confirmation=True)
    assert cont_done is False
    assert session.is_completed is True
    appt = db_session.get(Appointment, session.booking_id)
    assert appt.appointment_time.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Asia/Kolkata")).hour == 11


# ------------------------------------------------------------------------------
# 6. Unavailable slot handling (Closed hour or conflict -> alternative suggestions)
# ------------------------------------------------------------------------------
def test_scenario_6_unavailable_slot_handling(db_session: Session, receptionist_env: dict):
    biz = receptionist_env["business"]
    session = _make_session(db_session, biz.id, "call-scen-6")

    # Select service
    process_conversational_turn(db_session, session, "General Physician", biz, require_confirmation=True)

    # Request an evening 8 PM slot (Clinic closes at 6:00 PM, so 8 PM is unavailable)
    prompt, cont = process_conversational_turn(db_session, session, "Tomorrow at 8 PM", biz, require_confirmation=True)
    assert cont is True
    assert session.step == "awaiting_datetime"
    # Alternative suggestions should be returned
    assert ("not available" in prompt.lower() or "available slots" in prompt.lower())


# ------------------------------------------------------------------------------
# 7. Alternative slot selection
# ------------------------------------------------------------------------------
def test_scenario_7_alternative_slot_selection(db_session: Session, receptionist_env: dict):
    biz = receptionist_env["business"]
    session = _make_session(db_session, biz.id, "call-scen-7")

    # Service selected
    process_conversational_turn(db_session, session, "Dental cleaning", biz, require_confirmation=True)

    # 8 PM requested -> returns alternative slots within 09:00 - 18:00
    process_conversational_turn(db_session, session, "Tomorrow at 8 PM", biz, require_confirmation=True)

    # Caller picks alternative: "Tomorrow at 10 AM"
    prompt, cont = process_conversational_turn(db_session, session, "Tomorrow at 10 AM", biz, require_confirmation=True)
    assert cont is True
    assert session.step == "awaiting_name"
    assert session.appointment_datetime_iso is not None


# ------------------------------------------------------------------------------
# 8. Booking verbal confirmation (Refusal & Acceptance)
# ------------------------------------------------------------------------------
def test_scenario_8_booking_verbal_confirmation_denial_and_acceptance(db_session: Session, receptionist_env: dict):
    biz = receptionist_env["business"]

    # 8a: Denial
    s_deny = _make_session(db_session, biz.id, "call-scen-8a")
    process_conversational_turn(db_session, s_deny, "Cardiology tomorrow at 10 AM, name Mohan", biz, require_confirmation=True)
    assert s_deny.step == "awaiting_confirmation"

    prompt_deny, cont_deny = process_conversational_turn(db_session, s_deny, "No, don't confirm", biz, require_confirmation=True)
    assert cont_deny is True
    assert s_deny.step == "greeting"
    assert s_deny.booking_id is None
    assert "will not confirm" in prompt_deny.lower()

    # 8b: Acceptance
    s_acc = _make_session(db_session, biz.id, "call-scen-8b")
    process_conversational_turn(db_session, s_acc, "Cardiology tomorrow at 10 AM, name Mohan", biz, require_confirmation=True)
    prompt_acc, cont_acc = process_conversational_turn(db_session, s_acc, "Yes, please confirm the booking", biz, require_confirmation=True)
    assert cont_acc is False
    assert s_acc.step == "completed"
    assert s_acc.booking_id is not None


# ------------------------------------------------------------------------------
# 9. Rescheduling
# ------------------------------------------------------------------------------
def test_scenario_9_rescheduling(db_session: Session, receptionist_env: dict):
    biz = receptionist_env["business"]
    caller = "+919876543299"

    # Seed existing upcoming appointment
    cust = Customer(business_id=biz.id, name="Test Patient", phone=caller)
    db_session.add(cust)
    db_session.flush()

    orig_time = datetime.now(timezone.utc) + timedelta(days=1, hours=2)
    appt = Appointment(
        business_id=biz.id,
        customer_id=cust.id,
        service_id=receptionist_env["general"].id,
        appointment_time=orig_time,
        status="upcoming",
    )
    db_session.add(appt)
    db_session.commit()

    session = _make_session(db_session, biz.id, "call-scen-9", phone=caller)

    # Caller requests reschedule with new time
    new_time_str = "day after tomorrow at 3 PM"
    prompt, cont = process_conversational_turn(db_session, session, f"Reschedule my appointment to {new_time_str}", biz, require_confirmation=True)
    assert cont is False
    assert session.is_completed is True
    assert "rescheduled" in prompt.lower() or "மாற்றப்பட்டது" in prompt or "మార్చబడింది" in prompt

    db_session.refresh(appt)
    assert appt.status == "rescheduled" or appt.appointment_time != orig_time


# ------------------------------------------------------------------------------
# 10. Cancellation
# ------------------------------------------------------------------------------
def test_scenario_10_cancellation(db_session: Session, receptionist_env: dict):
    biz = receptionist_env["business"]
    caller = "+919876543288"

    # Seed existing upcoming appointment
    cust = Customer(business_id=biz.id, name="Cancel Patient", phone=caller)
    db_session.add(cust)
    db_session.flush()

    appt = Appointment(
        business_id=biz.id,
        customer_id=cust.id,
        service_id=receptionist_env["cardio"].id,
        appointment_time=datetime.now(timezone.utc) + timedelta(days=2),
        status="upcoming",
    )
    db_session.add(appt)
    db_session.commit()

    session = _make_session(db_session, biz.id, "call-scen-10", phone=caller)

    prompt, cont = process_conversational_turn(db_session, session, "Cancel my appointment please", biz, require_confirmation=True)
    assert cont is False
    assert session.is_completed is True
    assert "cancelled" in prompt.lower() or "ரத்து" in prompt or "రద్దు" in prompt

    db_session.refresh(appt)
    assert appt.status == "cancelled"


# ------------------------------------------------------------------------------
# 11. Existing appointment enquiry
# ------------------------------------------------------------------------------
def test_scenario_11_existing_appointment_enquiry(db_session: Session, receptionist_env: dict):
    biz = receptionist_env["business"]
    caller = "+919876543277"

    # Seed existing appointment
    cust = Customer(business_id=biz.id, name="Enquiry Patient", phone=caller)
    db_session.add(cust)
    db_session.flush()

    target_dt = datetime.now(timezone.utc) + timedelta(days=2, hours=3)
    appt = Appointment(
        business_id=biz.id,
        customer_id=cust.id,
        service_id=receptionist_env["cardio"].id,
        appointment_time=target_dt,
        status="upcoming",
    )
    db_session.add(appt)
    db_session.commit()

    session = _make_session(db_session, biz.id, "call-scen-11", phone=caller)

    # Inquire about existing booking
    prompt, cont = process_conversational_turn(db_session, session, "Do I have an upcoming appointment?", biz, require_confirmation=True)
    assert cont is True
    assert "Cardiology" in prompt or "cardio" in prompt.lower()
    assert "appointment" in prompt.lower()


# ------------------------------------------------------------------------------
# 12. General business enquiries (Hours, Address, Services)
# ------------------------------------------------------------------------------
def test_scenario_12_general_business_enquiries(db_session: Session, receptionist_env: dict):
    biz = receptionist_env["business"]
    session = _make_session(db_session, biz.id, "call-scen-12")

    # Address query
    p_addr, _ = process_conversational_turn(db_session, session, "Where is your clinic located?", biz, require_confirmation=True)
    assert "Anna Salai" in p_addr or biz.name in p_addr

    # Timings query
    p_hrs, _ = process_conversational_turn(db_session, session, "What are your working hours?", biz, require_confirmation=True)
    assert "Monday" in p_hrs or "9:00 AM" in p_hrs

    # Services query
    p_srv, _ = process_conversational_turn(db_session, session, "What services do you offer?", biz, require_confirmation=True)
    assert "General Physician" in p_srv or "Cardiology" in p_srv


# ------------------------------------------------------------------------------
# 13. English conversation
# ------------------------------------------------------------------------------
def test_scenario_13_english_conversation(db_session: Session, receptionist_env: dict):
    biz = receptionist_env["business"]
    session = _make_session(db_session, biz.id, "call-scen-13", language="en-IN")

    p1, _ = process_conversational_turn(db_session, session, "Hello, I want to book an appointment for dental cleaning tomorrow at 2 PM. My name is Alice Smith.", biz, require_confirmation=True)
    assert session.language == "en-IN"
    assert "Alice Smith" in p1

    p2, cont2 = process_conversational_turn(db_session, session, "Yes, confirm it please", biz, require_confirmation=True)
    assert cont2 is False
    assert session.is_completed is True
    assert "confirmed" in p2.lower()


# ------------------------------------------------------------------------------
# 14. Tamil conversation (Unicode Script)
# ------------------------------------------------------------------------------
def test_scenario_14_tamil_conversation(db_session: Session, receptionist_env: dict):
    biz = receptionist_env["business"]
    session = _make_session(db_session, biz.id, "call-scen-14", language="ta-IN")

    # Turn 1: Tamil input
    p1, cont1 = process_conversational_turn(
        db_session,
        session,
        "வணக்கம், எனக்கு பொது மருத்துவம் ஆலோசனை நாளை காலை 10 மணிக்கு வேண்டும். என் பெயர் முத்துக்குமார்.",
        biz,
        require_confirmation=True,
    )
    assert cont1 is True
    assert session.language == "ta-IN"
    assert session.step == "awaiting_confirmation"
    assert "முத்துக்குமார்" in p1

    # Turn 2: Tamil confirmation
    p2, cont2 = process_conversational_turn(db_session, session, "ஆம், உறுதி செய்யவும்", biz, require_confirmation=True)
    assert cont2 is False
    assert session.is_completed is True
    assert "பதிவு செய்யப்பட்டது" in p2 or "நன்றி" in p2


# ------------------------------------------------------------------------------
# 15. Telugu conversation (Unicode Script)
# ------------------------------------------------------------------------------
def test_scenario_15_telugu_conversation(db_session: Session, receptionist_env: dict):
    biz = receptionist_env["business"]
    session = _make_session(db_session, biz.id, "call-scen-15", language="te-IN")

    p1, cont1 = process_conversational_turn(
        db_session,
        session,
        "నమస్కారం, నాకు కార్డియాలజీ అపాయింట్‌మెంట్ రేపు ఉదయం 11 గంటలకు కావాలి. నా పేరు వెంకటేష్.",
        biz,
        require_confirmation=True,
    )
    assert cont1 is True
    assert session.language == "te-IN"
    assert session.step == "awaiting_confirmation"
    assert "వెంకటేష్" in p1

    p2, cont2 = process_conversational_turn(db_session, session, "అవును, నిర్ధారించండి", biz, require_confirmation=True)
    assert cont2 is False
    assert session.is_completed is True
    assert "నిర్ధారించబడ్డాయి" in p2 or "ధన్యవాదాలు" in p2


# ------------------------------------------------------------------------------
# 16. Tanglish conversation (Tamil in Latin Script)
# ------------------------------------------------------------------------------
def test_scenario_16_tanglish_conversation(db_session: Session, receptionist_env: dict):
    biz = receptionist_env["business"]
    session = _make_session(db_session, biz.id, "call-scen-16", language="ta-IN")

    p1, cont1 = process_conversational_turn(
        db_session,
        session,
        "Vanakkam, enakku cardiology appointment naalaiki kaalai 10 maniki venum. En peru Dinesh.",
        biz,
        require_confirmation=True,
    )
    assert cont1 is True
    assert session.step == "awaiting_confirmation"
    assert "Dinesh" in p1

    p2, cont2 = process_conversational_turn(db_session, session, "Aama, confirm pannunga", biz, require_confirmation=True)
    assert cont2 is False
    assert session.is_completed is True
    assert session.booking_id is not None


# ------------------------------------------------------------------------------
# 17. Teluglish conversation (Telugu in Latin Script)
# ------------------------------------------------------------------------------
def test_scenario_17_teluglish_conversation(db_session: Session, receptionist_env: dict):
    biz = receptionist_env["business"]
    session = _make_session(db_session, biz.id, "call-scen-17", language="te-IN")

    p1, cont1 = process_conversational_turn(
        db_session,
        session,
        "Namaskaram, nenu general medicine doctor ni chudali, repu podduna 10 am ki, na peru Suresh.",
        biz,
        require_confirmation=True,
    )
    assert cont1 is True
    assert session.step == "awaiting_confirmation"
    assert "Suresh" in p1

    p2, cont2 = process_conversational_turn(db_session, session, "Avunu confirm cheyandi", biz, require_confirmation=True)
    assert cont2 is False
    assert session.is_completed is True


# ------------------------------------------------------------------------------
# 18. Caller interruption (barge-in)
# ------------------------------------------------------------------------------
def test_scenario_18_caller_interruption_barge_in():
    stream_sid = "MZ_test_bargein_scenario_18"
    session = AudioStreamSession(
        stream_sid=stream_sid,
        call_sid="CA_bargein_18",
        business_id="demo-receptionist-biz",
        caller_phone="+919876543210",
        provider="plivo",
    )
    session.is_assistant_speaking = True
    session.turn_in_progress = True
    initial_gen = session.playback_generation

    mock_task = MagicMock()
    mock_task.done.return_value = False
    session.current_playback_task = mock_task

    # Trigger barge in
    gen = session.trigger_barge_in()
    assert session.interrupted is True
    assert session.is_assistant_speaking is False
    assert session.turn_in_progress is False
    assert gen > initial_gen
    mock_task.cancel.assert_called_once()


# ------------------------------------------------------------------------------
# 19. Unclear speech recovery (3-stage retry limit)
# ------------------------------------------------------------------------------
def test_scenario_19_unclear_speech_recovery(db_session: Session, receptionist_env: dict):
    biz = receptionist_env["business"]
    session = _make_session(db_session, biz.id, "call-scen-19")

    # Retry 1: Polite repeat
    p1, c1 = process_conversational_turn(db_session, session, "", biz, require_confirmation=True)
    assert c1 is True
    assert session.retry_count == 1
    assert "repeat" in p1.lower() or "did not catch" in p1.lower()

    # Retry 2: Guided prompt
    p2, c2 = process_conversational_turn(db_session, session, "", biz, require_confirmation=True)
    assert c2 is True
    assert session.retry_count == 2
    assert "trouble hearing" in p2.lower() or "help" in p2.lower()

    # Retry 3: Disconnect gracefully
    p3, c3 = process_conversational_turn(db_session, session, "", biz, require_confirmation=True)
    assert c3 is False
    assert session.is_completed is True
    assert "goodbye" in p3.lower() or "call back" in p3.lower()


# ------------------------------------------------------------------------------
# 20. Duplicate turn prevention (Idempotency)
# ------------------------------------------------------------------------------
def test_scenario_20_duplicate_turn_prevention(db_session: Session, receptionist_env: dict):
    biz = receptionist_env["business"]
    session = _make_session(db_session, biz.id, "call-scen-20")

    # Complete booking
    process_conversational_turn(db_session, session, "Cardiology tomorrow at 10 AM, name Bruce Wayne", biz, require_confirmation=True)
    process_conversational_turn(db_session, session, "Yes confirm", biz, require_confirmation=True)
    assert session.is_completed is True
    first_booking = session.booking_id

    # Subsequent utterance after completion should not double-book
    p_dup, c_dup = process_conversational_turn(db_session, session, "Book another appointment", biz, require_confirmation=True)
    assert c_dup is False
    assert session.booking_id == first_booking
    assert "already been successfully confirmed" in p_dup.lower()


# ------------------------------------------------------------------------------
# 21. Database failure recovery
# ------------------------------------------------------------------------------
def test_scenario_21_database_failure_recovery(db_session: Session, receptionist_env: dict):
    biz = receptionist_env["business"]
    session = _make_session(db_session, biz.id, "call-scen-21")

    process_conversational_turn(db_session, session, "Cardiology tomorrow at 10 AM, name Clark Kent", biz, require_confirmation=True)
    assert session.step == "awaiting_confirmation"

    # Simulate DB error during booking execution
    with patch("app.services.voice_assistant_service.execute_tool_call", return_value={"success": False, "error": "Database lock timeout"}):
        p_err, c_err = process_conversational_turn(db_session, session, "Yes confirm", biz, require_confirmation=True)
        assert c_err is True
        assert session.step == "awaiting_datetime"
        assert "could not be booked" in p_err.lower() or "apologize" in p_err.lower()


# ------------------------------------------------------------------------------
# 22. Call closing and termination
# ------------------------------------------------------------------------------
def test_scenario_22_call_closing_and_termination(db_session: Session, receptionist_env: dict):
    biz = receptionist_env["business"]
    session = _make_session(db_session, biz.id, "call-scen-22")

    prompt, cont = process_conversational_turn(db_session, session, "Thank you, goodbye!", biz, require_confirmation=True)
    assert cont is False
    assert session.step == "cancelled"
    assert session.is_completed is True
    assert "goodbye" in prompt.lower() or "have a wonderful day" in prompt.lower()
