"""Exhaustive Regression Test Suite for Real Plivo Telephony Call Issues.

Addresses and verifies:
1. Deepgram STT phonetic misrecognition: 'Mediatrix head checkup.' matches 'Pediatric Health Checkup'.
2. Unreliable / echo transcription ('880.', '', '...') handling without corrupting conversation state.
3. Assistant audio playback protection against false barge-in and acoustic echo.
4. Multilingual service matching (English, Indian English, Tamil, Tanglish, Telugu, Teluglish).
5. Multi-turn conversation context retention and verbal confirmation.
6. Actual database Appointment creation committed and linked to the Call record.
"""

from datetime import datetime, timezone
import json
import struct
import time
from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.appointment import Appointment
from app.models.assistant import Service
from app.models.business import Business
from app.models.business_hours import BusinessHour
from app.models.call import Call
from app.models.conversation_session import ConversationSession
from app.models.customer import Customer
from app.services.streaming.audio_codec import mulaw_to_base64, pcm16_to_mulaw
from app.services.streaming.session_manager import AudioStreamSession, stream_manager
from app.services.streaming.stream_orchestrator import StreamOrchestrator
from app.services.voice_assistant_service import (
    is_unreliable_or_noise_transcript,
    match_service_from_catalog,
    process_conversational_turn,
)


@pytest.fixture
def real_plivo_clinic(db_session: Session) -> Business:
    """Fixture providing active clinic with the exact services from the production database."""
    biz_id = f"plivo_clinic_{uuid.uuid4().hex[:8]}"
    biz = Business(
        id=biz_id,
        name="Vattara City Clinic & Diagnostics",
        vertical="clinic",
        email="reception@vattaracityclinic.com",
        phone="+917904743468",
        timezone="Asia/Kolkata",
        is_active=True,
    )
    db_session.add(biz)
    db_session.flush()

    # 7-day operating hours: 08:00 - 20:00
    for dow in range(7):
        bh = BusinessHour(
            business_id=biz.id,
            day_of_week=dow,
            open_time="08:00",
            close_time="20:00",
            is_closed=False,
        )
        db_session.add(bh)

    # Active catalog services matching production database
    s1 = Service(
        id=f"srv_gp_{uuid.uuid4().hex[:6]}",
        business_id=biz.id,
        name="General Physician Consultation",
        duration_minutes=30,
        price=500.0,
        is_active=True,
    )
    s2 = Service(
        id=f"srv_cardio_{uuid.uuid4().hex[:6]}",
        business_id=biz.id,
        name="Cardiology Consultation & ECG",
        duration_minutes=45,
        price=1200.0,
        is_active=True,
    )
    s3 = Service(
        id=f"srv_ped_{uuid.uuid4().hex[:6]}",
        business_id=biz.id,
        name="Pediatric Health Checkup",
        duration_minutes=30,
        price=700.0,
        is_active=True,
    )
    s4 = Service(
        id=f"srv_diag_{uuid.uuid4().hex[:6]}",
        business_id=biz.id,
        name="Full Body Blood Diagnostics",
        duration_minutes=15,
        price=1500.0,
        is_active=True,
    )
    s5 = Service(
        id=f"srv_dent_{uuid.uuid4().hex[:6]}",
        business_id=biz.id,
        name="Dental Cleaning & Polish",
        duration_minutes=40,
        price=800.0,
        is_active=True,
    )
    db_session.add_all([s1, s2, s3, s4, s5])
    db_session.commit()
    return biz


# ------------------------------------------------------------------------------
# 1. Problem 2 Verification: "Mediatrix head checkup." matches Pediatric Health Checkup
# ------------------------------------------------------------------------------

def test_mediatrix_head_checkup_matches_pediatric_service(db_session: Session, real_plivo_clinic: Business):
    """Verify that 'Mediatrix head checkup.' (the exact Deepgram output) matches 'Pediatric Health Checkup'."""
    services = db_session.query(Service).filter(Service.business_id == real_plivo_clinic.id).all()
    
    # Exact phrase from the real Plivo call log
    utterance = "Mediatrix head checkup."
    matched = match_service_from_catalog(utterance, services)
    
    assert matched is not None
    assert matched.name == "Pediatric Health Checkup"


def test_phonetic_and_fuzzy_catalog_service_matching(db_session: Session, real_plivo_clinic: Business):
    """Verify fuzzy and phonetic variations match against the actual clinic service catalog."""
    services = db_session.query(Service).filter(Service.business_id == real_plivo_clinic.id).all()

    test_cases = [
        ("pediatrix head checkup", "Pediatric Health Checkup"),
        ("padiatric health checkup", "Pediatric Health Checkup"),
        ("child health checkup", "Pediatric Health Checkup"),
        ("head checkup for child", "Pediatric Health Checkup"),
        ("general physician checkup", "General Physician Consultation"),
        ("family doctor consultation", "General Physician Consultation"),
        ("cardiac consultation and ecg", "Cardiology Consultation & ECG"),
        ("heart ecg test", "Cardiology Consultation & ECG"),
        ("teeth polish and cleaning", "Dental Cleaning & Polish"),
        ("dentist scaling and cleaning", "Dental Cleaning & Polish"),
        ("full body blood test", "Full Body Blood Diagnostics"),
        ("complete blood diagnostics", "Full Body Blood Diagnostics"),
    ]

    for speech, expected_name in test_cases:
        matched = match_service_from_catalog(speech, services)
        assert matched is not None, f"Failed to match speech: '{speech}'"
        assert matched.name == expected_name, f"Expected '{expected_name}', got '{matched.name}' for speech '{speech}'"


# ------------------------------------------------------------------------------
# 2. Problem 3 Verification: "880." and empty strings handled as unreliable transcripts
# ------------------------------------------------------------------------------

def test_unreliable_and_noise_transcription_detection():
    """Verify detection of line noise, acoustic echo, and DTMF artifacts without corrupting conversation."""
    # When waiting for service or greeting, stray numbers are noise
    assert is_unreliable_or_noise_transcript("880.", current_step="awaiting_service") is True
    assert is_unreliable_or_noise_transcript("880", current_step="awaiting_service") is True
    assert is_unreliable_or_noise_transcript("123", current_step="greeting") is True
    assert is_unreliable_or_noise_transcript("", current_step="awaiting_service") is True
    assert is_unreliable_or_noise_transcript("   ", current_step="awaiting_service") is True
    assert is_unreliable_or_noise_transcript(".", current_step="awaiting_service") is True
    assert is_unreliable_or_noise_transcript("...", current_step="awaiting_service") is True
    assert is_unreliable_or_noise_transcript("Thank you.", current_step="awaiting_service") is True

    # Real words must NOT be flagged as noise
    assert is_unreliable_or_noise_transcript("Mediatrix head checkup.", current_step="awaiting_service") is False
    assert is_unreliable_or_noise_transcript("Want to book a appointment.", current_step="greeting") is False
    assert is_unreliable_or_noise_transcript("Tomorrow at 10 AM", current_step="awaiting_datetime") is False

    # In awaiting_datetime, numbers like "10" or "9" could be a time and are NOT rejected
    assert is_unreliable_or_noise_transcript("10", current_step="awaiting_datetime") is False


def test_echo_880_does_not_advance_or_corrupt_conversation_state(db_session: Session, real_plivo_clinic: Business):
    """Verify that an echo transcription of '880.' does not advance or fail the session in awaiting_service."""
    call_sid = f"plivo_test_echo_{uuid.uuid4().hex[:8]}"
    session = ConversationSession(
        call_sid=call_sid,
        business_id=real_plivo_clinic.id,
        caller_phone="+917904743468",
        step="awaiting_service",
        intent="booking",
        language="en-IN",
        detected_language="en-IN",
        dialog_history=json.dumps([]),
        metadata_json=json.dumps({"require_confirmation": True}),
        retry_count=0,
        is_completed=False,
    )
    db_session.add(session)
    db_session.commit()

    # Echo artifact arrives
    resp, should_gather = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="880.",
        business=real_plivo_clinic,
    )

    # State must remain cleanly in awaiting_service without marking call completed or setting wrong intent
    assert should_gather is True
    assert session.step == "awaiting_service"
    assert session.intent == "booking"
    assert session.is_completed is False
    assert session.service_id is None
    # Response should helpfully guide caller with catalog offerings
    assert "Which medical service would you like to book" in resp


# ------------------------------------------------------------------------------
# 3. Problem 5 Verification: Playback protection against false barge-in & echo
# ------------------------------------------------------------------------------

def test_barge_in_and_playback_echo_protection():
    """Verify elevated thresholds and echo settling window prevent false barge-in."""
    from app.services.streaming.audio_codec import compute_rms_energy, is_speech_active

    # 1. Verify fine-tuned telephony barge-in settings
    assert settings.BARGE_IN_ENERGY_THRESHOLD == 1200.0, "Elevated barge-in threshold must be 1200.0 to reject acoustic echo"
    assert settings.BARGE_IN_MIN_SPEECH_FRAMES == 10, "Minimum speech frames must be 10 (200ms) to reject transient echo bursts"
    assert settings.BARGE_IN_GRACE_PERIOD_MS == 2000, "Grace period must be 2000ms to protect playback onset"
    assert settings.ECHO_SETTLING_WINDOW_MS == 500, "Echo settling window must be 500ms to protect post-playback reflection"

    # 2. Typical acoustic echo / hybrid line noise (900 RMS: above idle 400, but below elevated threshold 1200)
    echo_samples = [900 if i % 2 == 0 else -900 for i in range(160)]
    echo_pcm = struct.pack(f"<{len(echo_samples)}h", *echo_samples)
    energy = compute_rms_energy(echo_pcm)
    assert 850.0 <= energy <= 950.0

    # During playback or echo tail: effective_threshold is 1200.0 -> is_speech_active must be FALSE
    assert is_speech_active(energy, threshold=settings.BARGE_IN_ENERGY_THRESHOLD) is False

    # 3. Intentional loud caller interruption (1800 RMS) -> is_speech_active must be TRUE
    speech_samples = [1800 if i % 2 == 0 else -1800 for i in range(160)]
    speech_pcm = struct.pack(f"<{len(speech_samples)}h", *speech_samples)
    speech_energy = compute_rms_energy(speech_pcm)
    assert speech_energy > 1500.0
    assert is_speech_active(speech_energy, threshold=settings.BARGE_IN_ENERGY_THRESHOLD) is True


# ------------------------------------------------------------------------------
# 4. Multilingual Service Matching (English, Tamil, Tanglish, Telugu, Teluglish)
# ------------------------------------------------------------------------------

def test_multilingual_service_matching_all_languages(db_session: Session, real_plivo_clinic: Business):
    """Verify service identification works seamlessly across all target languages and scripts."""
    services = db_session.query(Service).filter(Service.business_id == real_plivo_clinic.id).all()

    cases = [
        # Tamil Unicode Script
        ("குழந்தை மருத்துவம் பரிசோதனை வேண்டும்", "Pediatric Health Checkup"),
        ("பொது மருத்துவர் ஆலோசனை பார்க்க வேண்டும்", "General Physician Consultation"),
        ("பல் சுத்தம் செய்ய வேண்டும்", "Dental Cleaning & Polish"),
        ("இதய பரிசோதனை மற்றும் ஈசிஜி", "Cardiology Consultation & ECG"),
        ("இரத்த பரிசோதனை", "Full Body Blood Diagnostics"),

        # Tanglish (Tamil in Latin Script)
        ("Paappa health checkup pannanum please", "Pediatric Health Checkup"),
        ("Kuzhandhai maruthuvam consultation venum", "Pediatric Health Checkup"),
        ("General physician consultation parkanum", "General Physician Consultation"),
        ("Enakku teeth cleaning pannanum", "Dental Cleaning & Polish"),
        ("Cardiology checkup and ecg", "Cardiology Consultation & ECG"),

        # Telugu Unicode Script
        ("పిల్లల ఆరోగ్య పరీక్ష కావాలి", "Pediatric Health Checkup"),
        ("పిల్లల డాక్టర్ అపాయింట్‌మెంట్ కావాలి", "Pediatric Health Checkup"),
        ("సాధారణ వైద్యం డాక్టర్ సంప్రదింపులు", "General Physician Consultation"),
        ("పళ్ళు శుభ్రం చేయించుకోవాలి", "Dental Cleaning & Polish"),
        ("గుండె పరీక్ష ఈసీజీ కావాలి", "Cardiology Consultation & ECG"),

        # Teluglish (Telugu in Latin Script)
        ("Pillala health checkup kosam", "Pediatric Health Checkup"),
        ("Pillala doctor consultation kavali", "Pediatric Health Checkup"),
        ("Vaidhyudu consultation book cheyandi", "General Physician Consultation"),
        ("Pallu clean cheyali", "Dental Cleaning & Polish"),
        ("Gunde doctor appointment", "Cardiology Consultation & ECG"),
    ]

    for speech, expected_name in cases:
        matched = match_service_from_catalog(speech, services)
        assert matched is not None, f"Failed matching: '{speech}'"
        assert matched.name == expected_name, f"Expected '{expected_name}', got '{matched.name}' for: '{speech}'"


# ------------------------------------------------------------------------------
# 5. Full Real Call Sequence: From "Mediatrix" to Confirmed Database Booking
# ------------------------------------------------------------------------------

def test_full_plivo_real_call_to_confirmed_database_booking(db_session: Session, real_plivo_clinic: Business):
    """Reproduce the real Plivo call flow and verify that the appointment is committed to DB and linked to Call."""
    call_uuid = f"plivo_real_{uuid.uuid4().hex[:12]}"
    caller_phone = f"+9198{uuid.uuid4().int % 1000000000:08d}"

    # Pre-create the initial incoming Call record as Plivo route does
    call_rec = Call(
        id=call_uuid,
        business_id=real_plivo_clinic.id,
        caller_name=f"Caller {caller_phone}",
        caller_phone=caller_phone,
        call_type="incoming",
        status="in_progress",
        duration_seconds=0,
        summary=f"Incoming voice call via Plivo (CallUUID: {call_uuid})",
        initiated_at=datetime.now(timezone.utc),
    )
    db_session.add(call_rec)
    db_session.commit()

    # Session begins
    session = ConversationSession(
        call_sid=call_uuid,
        business_id=real_plivo_clinic.id,
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

    # Turn 1: Caller states "Want to book a appointment."
    resp1, cont1 = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="Want to book a appointment.",
        business=real_plivo_clinic,
    )
    assert cont1 is True
    assert session.intent == "booking"
    assert session.step == "awaiting_service"
    assert "Which medical service" in resp1

    # Turn 2: Caller provides medical service (transcribed as "Mediatrix head checkup.")
    resp2, cont2 = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="Mediatrix head checkup.",
        business=real_plivo_clinic,
    )
    assert cont2 is True
    assert session.service_id is not None
    assert session.service_name == "Pediatric Health Checkup"
    assert session.step == "awaiting_datetime"
    assert "Pediatric Health Checkup" in resp2 or "available appointments" in resp2

    # Turn 3: Caller states date and time
    resp3, cont3 = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="Tomorrow at 10 AM.",
        business=real_plivo_clinic,
    )
    assert cont3 is True
    assert session.appointment_datetime_iso is not None
    assert session.step == "awaiting_name"
    assert "full name" in resp3.lower()

    # Turn 4: Caller states name
    resp4, cont4 = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="My name is Steve.",
        business=real_plivo_clinic,
    )
    assert cont4 is True
    assert session.customer_name == "Steve"
    assert session.step == "awaiting_confirmation"
    assert "Steve" in resp4
    assert "confirm" in resp4.lower()

    # Turn 5: Caller affirms verbal confirmation
    resp5, cont5 = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="Yes, please confirm.",
        business=real_plivo_clinic,
    )
    assert cont5 is False  # Call conversation complete
    assert session.step == "completed"
    assert session.is_completed is True
    assert session.booking_id is not None
    assert "confirmed" in resp5.lower()

    # VERIFY DATABASE PERSISTENCE:
    # 1. Appointment record exists in DB
    appt = db_session.get(Appointment, session.booking_id)
    assert appt is not None, "Appointment record was NOT committed to the database!"
    assert appt.business_id == real_plivo_clinic.id
    assert appt.service_id == session.service_id
    assert appt.status == "upcoming"
    assert appt.customer.name == "Steve"
    assert appt.customer.phone == caller_phone

    # 2. Call record is updated and linked
    db_session.refresh(call_rec)
    assert call_rec.status == "completed"
    assert call_rec.caller_name == "Steve"
    assert call_rec.customer_id == appt.customer_id, "Call record is NOT linked to the customer!"
    assert session.booking_id in call_rec.summary, "Call record summary does not contain Booking ID!"
    assert "Steve" in call_rec.transcript
    assert "Pediatric Health Checkup" in call_rec.transcript
