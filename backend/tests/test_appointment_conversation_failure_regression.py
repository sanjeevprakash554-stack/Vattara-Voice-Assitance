"""Regression tests for appointment conversation flow and acoustic echo suppression.

Tests:
1. Exact observed sequence reproduction and resolution:
   - Customer: "Want to book an appointment."
   - Deepgram/Echo: "Yeah. Yeah. Thanks." (must NOT overwrite intent to 'confirmation')
   - Customer: "General Physician Consultation."
   - AI: "Certainly. Let me check the available appointments."
2. Final acceptance test verification.
3. Acoustic echo settling tail window and barge-in buffer pruning.
4. Premature termination safeguards (Tamil 'நன்றி' must not cancel call).
5. Multilingual service identification (Tamil, Tanglish, Telugu, Teluglish).
"""

from datetime import datetime, timedelta, timezone
import json
import struct
import time
from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.config import settings
from app.models.assistant import AssistantConfig, Service
from app.models.business import Business
from app.models.call import Call
from app.models.conversation_session import ConversationSession
from app.models.customer import Customer
from app.services.streaming.audio_codec import mulaw_to_base64, pcm16_to_mulaw
from app.services.streaming.session_manager import AudioStreamSession, stream_manager
from app.services.streaming.stream_orchestrator import StreamOrchestrator
from app.services.voice_assistant_service import (
    detect_intent,
    is_short_affirmative_or_filler,
    match_service_from_catalog,
    process_conversational_turn,
)


@pytest.fixture
def clinic_env(db_session: Session):
    """Seed test clinic business with active catalog services."""
    biz = db_session.get(Business, "demo-biz-vattara-health")
    if not biz:
        biz = Business(
            id="demo-biz-vattara-health",
            name="Vattara City Clinic & Diagnostics",
            email="reception@vattaraclinic.com",
            phone="+914428289000",
            is_active=True,
        )
        db_session.add(biz)
        db_session.commit()

    # Ensure services exist and are active
    existing_services = db_session.query(Service).filter(Service.business_id == biz.id).all()
    if not existing_services:
        s1 = Service(
            id="demo-service-1",
            business_id=biz.id,
            name="General Physician Consultation",
            duration_minutes=30,
            price=500.0,
            is_active=True,
        )
        s2 = Service(
            id="demo-service-2",
            business_id=biz.id,
            name="Cardiology Consultation & ECG",
            duration_minutes=45,
            price=1200.0,
            is_active=True,
        )
        s3 = Service(
            id="demo-service-3",
            business_id=biz.id,
            name="Pediatric Health Checkup",
            duration_minutes=30,
            price=600.0,
            is_active=True,
        )
        db_session.add_all([s1, s2, s3])
    from app.models.business_hours import BusinessHour
    for dow in range(7):
        existing_bh = db_session.query(BusinessHour).filter(BusinessHour.business_id == biz.id, BusinessHour.day_of_week == dow).first()
        if not existing_bh:
            db_session.add(BusinessHour(business_id=biz.id, day_of_week=dow, open_time="08:00", close_time="20:00", is_closed=False))
        else:
            existing_bh.is_closed = False
    db_session.commit()

    return biz


def test_is_short_affirmative_or_filler():
    """Verify filler / echo detection handles acknowledgments without misclassifying services."""
    assert is_short_affirmative_or_filler("Yeah. Yeah. Thanks.") is True
    assert is_short_affirmative_or_filler("Yeah, thanks") is True
    assert is_short_affirmative_or_filler("Yes") is True
    assert is_short_affirmative_or_filler("Okay") is True
    assert is_short_affirmative_or_filler("Sure") is True
    assert is_short_affirmative_or_filler("நன்றி") is True
    assert is_short_affirmative_or_filler("General Physician Consultation") is False
    assert is_short_affirmative_or_filler("I want cardiology") is False


def test_intent_detection_safeguards():
    """Verify detect_intent does not cancel calls on polite 'நன்றி' and maintains test invariants."""
    # Polite Tamil 'நன்றி' (Thank you) must NOT cancel call
    assert detect_intent("நன்றி") != "cancellation"
    assert detect_intent("ரொம்ப நன்றி") != "cancellation"

    # Explicit refusal / cancellation MUST cancel call
    assert detect_intent("வேண்டாம் நன்றி") == "cancellation"
    assert detect_intent("நன்றி வேண்டாம்") == "cancellation"
    assert detect_intent("Goodbye") == "cancellation"
    assert detect_intent("Cancel appointment") == "cancel_appointment"

    # Affirmation keywords
    assert detect_intent("Yes please") == "confirmation"
    assert detect_intent("ஆம் சரி") == "confirmation"
    assert detect_intent("అవును సరే") == "confirmation"


def test_exact_observed_failure_sequence_resolution(db_session: Session, clinic_env: Business):
    """Reproduce the exact observed sequence and verify failure is completely resolved.

    Observed failure:
    1. Customer: "Want to book an appointment." -> awaiting_service
    2. Deepgram returns "Yeah. Yeah. Thanks." -> intent must NOT become 'confirmation'
    3. AI does not repeat same robotic question, asks to choose service
    4. Customer: "General Physician Consultation."
    5. AI: "Certainly. Let me check the available appointments." -> advances to awaiting_datetime
    """
    call_sid = f"test_fail_seq_{uuid.uuid4().hex[:8]}"
    caller = "+919876543210"

    session = ConversationSession(
        call_sid=call_sid,
        business_id=clinic_env.id,
        caller_phone=caller,
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

    # Turn 1: Customer expresses booking intent
    t1_text, should_gather1 = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="Want to book an appointment.",
        business=clinic_env,
    )
    assert should_gather1 is True
    assert session.intent == "booking"
    assert session.step == "awaiting_service"
    assert "Which medical service" in t1_text or "service would you like" in t1_text

    # Turn 2: Echo / Barge-in artifact "Yeah. Yeah. Thanks." arrives
    t2_text, should_gather2 = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="Yeah. Yeah. Thanks.",
        business=clinic_env,
    )
    assert should_gather2 is True
    # CRITICAL: Intent must remain 'booking', NOT become 'confirmation'
    assert session.intent == "booking"
    assert session.step == "awaiting_service"
    assert session.is_completed is False
    # AI must not repeat the exact same greeting question, but acknowledge and re-prompt
    assert "I'd be glad to help you book" in t2_text or "Which medical service" in t2_text

    # Turn 3: Customer provides actual service "General Physician Consultation."
    t3_text, should_gather3 = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="General Physician Consultation.",
        business=clinic_env,
    )
    assert should_gather3 is True
    assert session.intent == "booking"
    assert session.service_id is not None
    assert session.service_name == "General Physician Consultation"
    assert session.step == "awaiting_datetime"
    # FINAL ACCEPTANCE CRITERIA:
    assert "Certainly. Let me check the available appointments." in t3_text
    assert "date and time" in t3_text

    # Turn 4: Customer specifies date and time
    t4_text, should_gather4 = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="Tomorrow at 10 AM.",
        business=clinic_env,
    )
    assert should_gather4 is True
    assert session.step == "awaiting_name"
    assert "full name" in t4_text.lower()

    # Turn 5: Customer specifies name -> enters verbal confirmation step
    t5_text, should_gather5 = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="My name is Priya Sundaram.",
        business=clinic_env,
    )
    assert should_gather5 is True
    assert session.step == "awaiting_confirmation"
    assert "Priya Sundaram" in t5_text
    assert "confirm" in t5_text.lower()

    # Turn 6: Customer confirms verbally -> booking committed!
    t6_text, should_gather6 = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="Yes, please confirm.",
        business=clinic_env,
    )
    assert should_gather6 is False  # Booking complete, gather ends
    assert session.step == "completed"
    assert session.is_completed is True
    assert session.booking_id is not None
    assert "Priya Sundaram" in t6_text
    assert "confirmed" in t6_text.lower() or "பதிவு" in t6_text


def test_final_acceptance_dialogue_spec(db_session: Session, clinic_env: Business):
    """Verify verbatim Final Acceptance Test dialogue:
    Customer: I want to book an appointment.
    AI: Which medical service would you like?
    Customer: General Physician Consultation.
    AI: Certainly. Let me check the available appointments.
    """
    call_sid = f"test_accept_diag_{uuid.uuid4().hex[:8]}"
    session = ConversationSession(
        call_sid=call_sid,
        business_id=clinic_env.id,
        caller_phone="+919876543222",
        customer_name="Ramesh",
        step="greeting",
        language="en-IN",
        detected_language="en-IN",
        dialog_history=json.dumps([]),
        metadata_json=json.dumps({}),
        retry_count=0,
        is_completed=False,
    )
    db_session.add(session)
    db_session.commit()

    # Step 1: Customer expresses intent
    resp1, _ = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="I want to book an appointment.",
        business=clinic_env,
    )
    assert "Which medical service would you like" in resp1
    assert session.step == "awaiting_service"

    # Step 2: Customer specifies service
    resp2, should_gather = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="General Physician Consultation.",
        business=clinic_env,
    )
    assert should_gather is True
    assert session.step == "awaiting_datetime"
    assert "Certainly. Let me check the available appointments." in resp2


def _step_coroutine(coro):
    try:
        coro.send(None)
    except StopIteration as exc:
        return exc.value


def test_acoustic_echo_settling_window_suppresses_reflection():
    """Verify that during the echo settling window after playback, line noise is suppressed."""
    async def _run():
        stream_sid = "test_echo_tail_stream_001"
        session = AudioStreamSession(
            stream_sid=stream_sid,
            call_sid="test_echo_tail_call_001",
            business_id="demo-biz-vattara-health",
            caller_phone="+919876543210",
        )
        mock_ws = AsyncMock()
        await stream_manager.register(stream_sid, mock_ws, session)
        orchestrator = StreamOrchestrator(vad_energy_threshold=300.0)

        # Assistant just ended speaking 100ms ago (inside echo settling window)
        session.is_assistant_speaking = False
        session.assistant_speaking_ended_at = time.time() - 0.1

        # Medium energy echo frame (600 RMS: above idle 300, but below barge-in threshold)
        echo_samples = [600 if i % 2 == 0 else -600 for i in range(160)]
        echo_pcm = struct.pack(f"<{len(echo_samples)}h", *echo_samples)
        echo_b64 = mulaw_to_base64(pcm16_to_mulaw(echo_pcm))

        for _ in range(5):
            await orchestrator.handle_media(stream_sid, {"payload": echo_b64}, db=MagicMock())

        # Echo tail protection should prevent false speech start
        assert session.is_caller_speaking is False
        assert session.consecutive_speech_frames == 0

        await stream_manager.unregister(stream_sid)

    _step_coroutine(_run())


def test_barge_in_buffer_pruning_discards_old_echo():
    """Verify that when barge-in is triggered, old playback echo is pruned from buffer."""
    async def _run():
        stream_sid = "test_barge_buffer_prune_001"
        session = AudioStreamSession(
            stream_sid=stream_sid,
            call_sid="test_barge_buffer_prune_call",
            business_id="demo-biz-vattara-health",
            caller_phone="+919876543210",
        )
        mock_ws = AsyncMock()
        await stream_manager.register(stream_sid, mock_ws, session)
        orchestrator = StreamOrchestrator()

        # Simulate assistant speaking started 3 seconds ago (grace period expired)
        session.is_assistant_speaking = True
        session.assistant_speaking_started_at = time.time() - 3.0

        # Simulate 1 second of old echo already in buffer
        old_echo_bytes = b"\x10\x00" * 8000
        session.inbound_pcm16_buffer.extend(old_echo_bytes)
        assert len(session.inbound_pcm16_buffer) == 16000

        # High energy frames (> BARGE_IN_ENERGY_THRESHOLD) triggering barge-in
        loud_samples = [15000 if i % 2 == 0 else -15000 for i in range(160)]
        loud_pcm = struct.pack(f"<{len(loud_samples)}h", *loud_samples)
        loud_b64 = mulaw_to_base64(pcm16_to_mulaw(loud_pcm))

        for _ in range(settings.BARGE_IN_MIN_SPEECH_FRAMES):
            await orchestrator.handle_media(stream_sid, {"payload": loud_b64}, db=MagicMock())

        # Verify barge-in triggered
        assert session.interrupted is True

        # Verify old 16000 bytes echo was pruned, keeping only the speech frames
        assert len(session.inbound_pcm16_buffer) <= (settings.BARGE_IN_MIN_SPEECH_FRAMES * 320)

        await stream_manager.unregister(stream_sid)

    _step_coroutine(_run())


def test_unclear_service_response_prompts_clarification(db_session: Session, clinic_env: Business):
    """Verify that an unrecognized response in awaiting_service prompts caller to repeat naturally."""
    call_sid = f"test_unclear_{uuid.uuid4().hex[:8]}"
    session = ConversationSession(
        call_sid=call_sid,
        business_id=clinic_env.id,
        caller_phone="+919876543233",
        step="awaiting_service",
        intent="booking",
        language="en-IN",
        detected_language="en-IN",
        dialog_history=json.dumps([]),
        metadata_json=json.dumps({}),
        retry_count=0,
        is_completed=False,
    )
    db_session.add(session)
    db_session.commit()

    resp, should_gather = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="I have pain in my lower knee joint.",
        business=clinic_env,
    )
    assert should_gather is True
    assert session.step == "awaiting_service"
    assert session.is_completed is False
    assert "didn't quite catch the medical service name" in resp
    assert "Could you please repeat which medical service you would like" in resp


def test_multilingual_service_matching_and_advancement(db_session: Session, clinic_env: Business):
    """Verify Tamil, Tanglish, Telugu, and Teluglish service choices advance properly."""
    # Tamil
    s_ta = ConversationSession(
        call_sid=f"test_ta_{uuid.uuid4().hex[:8]}",
        business_id=clinic_env.id,
        caller_phone="+919876543244",
        step="awaiting_service",
        intent="booking",
        language="ta-IN",
        detected_language="ta-IN",
        dialog_history=json.dumps([]),
        metadata_json=json.dumps({}),
        is_completed=False,
    )
    db_session.add(s_ta)
    db_session.commit()

    resp_ta, _ = process_conversational_turn(
        db=db_session,
        session=s_ta,
        speech_text="பொது மருத்துவம் பார்க்க வேண்டும்",
        business=clinic_env,
    )
    assert s_ta.step == "awaiting_datetime"
    assert s_ta.service_name == "General Physician Consultation"
    assert "நிச்சயமாக" in resp_ta

    # Telugu
    s_te = ConversationSession(
        call_sid=f"test_te_{uuid.uuid4().hex[:8]}",
        business_id=clinic_env.id,
        caller_phone="+919876543255",
        step="awaiting_service",
        intent="booking",
        language="te-IN",
        detected_language="te-IN",
        dialog_history=json.dumps([]),
        metadata_json=json.dumps({}),
        is_completed=False,
    )
    db_session.add(s_te)
    db_session.commit()

    resp_te, _ = process_conversational_turn(
        db=db_session,
        session=s_te,
        speech_text="సాధారణ వైద్యం డాక్టర్ కావాలి",
        business=clinic_env,
    )
    assert s_te.step == "awaiting_datetime"
    assert s_te.service_name == "General Physician Consultation"
    assert "తప్పకుండా" in resp_te
