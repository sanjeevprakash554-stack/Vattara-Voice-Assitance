"""Comprehensive test suite for Tamil-English bilingual conversational support in Vattara Voice Assistance.

Covers all 10 required validation criteria:
1. Tamil-only conversation.
2. English-only conversation.
3. Tamil-to-English language switching mid-call.
4. English-to-Tamil language switching mid-call.
5. Tamil-English mixed sentences (Tanglish) and loanword protection.
6. English appointment booking flow.
7. Tamil appointment booking flow.
8. English availability inquiry.
9. Tamil availability inquiry.
10. Language-appropriate TTS routing and non-silent melodic fallback.
"""

from datetime import datetime, timezone
import json
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.assistant import Service
from app.models.business import Business
from app.models.customer import Customer
from app.services.ai.language_detector import detect_language
from app.services.streaming.stt_provider import DeepgramStreamingSTT
from app.services.streaming.tts_provider import ElevenLabsStreamingTTS, MockStreamingTTS
from app.services.voice_assistant_service import (
    detect_intent,
    get_or_create_conversation_session,
    process_conversational_turn,
)


@pytest.fixture
def demo_clinic(db_session: Session) -> Business:
    """Retrieve demo clinic tenant."""
    biz = db_session.scalar(select(Business).where(Business.id == "demo-biz-vattara-health"))
    if not biz:
        biz = Business(
            id="demo-biz-vattara-health",
            name="Vattara City Clinic & Diagnostics",
            phone="+918031794113",
            address="123 Anna Salai, Chennai, TN",
            is_active=True,
        )
        db_session.add(biz)
        db_session.commit()
        db_session.refresh(biz)
    return biz


# ==============================================================================
# 1. Deepgram STT Configuration & Language Hints
# ==============================================================================

def test_deepgram_nova3_multilingual_streaming_configuration():
    """Verify Deepgram Nova-3 is configured with model=nova-3, language=multi and both language hints."""
    stt = DeepgramStreamingSTT(
        api_key="test_key",
        model="nova-3",
        multilingual=True,
        language_hints=["ta", "en"],
    )
    assert stt.model == "nova-3"
    assert stt.resolve_language("multi") == "multi"
    assert stt.language_hints == ["ta", "en"]

    # Verify WebSocket URL generation contains both language hints
    ws_url = stt.build_websocket_url(language="multi", sample_rate=8000, encoding="linear16")
    assert "model=nova-3" in ws_url
    assert "language=multi" in ws_url
    assert "language_hint=ta" in ws_url
    assert "language_hint=en" in ws_url
    assert "sample_rate=8000" in ws_url

    # Verify REST request payload contains both language hints
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "results": {
            "channels": [
                {
                    "alternatives": [{"transcript": "Hello doctor", "confidence": 0.98}],
                    "detected_language": "en",
                    "languages": ["en", "ta"],
                    "language_confidence": 0.95,
                }
            ]
        }
    }

    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        stt.process_audio_chunk(bytes([10] * 3200))
        transcript = stt.flush(language="multi")
        assert transcript == "Hello doctor"
        assert stt.last_detected_language == "en"
        assert stt.last_detected_languages == ["en", "ta"]

        _, kwargs = mock_post.call_args
        params = kwargs["params"]
        assert params["model"] == "nova-3"
        assert params["language"] == "multi"
        assert params["language_hint"] == ["ta", "en"]


# ==============================================================================
# 2. Dynamic Language Detection & Code-Switching
# ==============================================================================

def test_dynamic_language_detection_and_loanword_protection():
    """Verify script detection, Deepgram metadata synergy, and loanword protection."""
    # Tamil speech -> ta-IN
    assert detect_language("வணக்கம்") == "ta-IN"
    assert detect_language("எனக்கு டாக்டர் அப்பாயின்ட்மென்ட் வேண்டும்") == "ta-IN"

    # English speech -> en-IN
    assert detect_language("Hello, I want to book an appointment.") == "en-IN"
    assert detect_language("What are your clinic working hours?") == "en-IN"

    # Deepgram metadata synergy
    assert detect_language("I need to see a physician", current_lang="ta-IN", deepgram_detected_lang="en") == "en-IN"

    # Medical loanwords and person names must NOT trigger language switch by themselves
    assert detect_language("Cardiology", current_lang="ta-IN") == "ta-IN"
    assert detect_language("Pediatric", current_lang="ta-IN") == "ta-IN"
    assert detect_language("Steve", current_lang="ta-IN") == "ta-IN"
    assert detect_language("General Physician", current_lang="ta-IN") == "ta-IN"
    assert detect_language("Tomorrow 10 AM", current_lang="ta-IN") == "ta-IN"


def test_bilingual_mid_call_language_switching(db_session: Session, demo_clinic: Business):
    """Verify caller can switch from Tamil to English and English to Tamil during active call."""
    call_sid = "test-call-switch-bilingual-001"
    session = get_or_create_conversation_session(
        db=db_session,
        call_sid=call_sid,
        business_id=demo_clinic.id,
        caller_phone="+919840199001",
        default_language="ta-IN",
    )

    # Turn 1: Caller speaks Tamil
    reply1, _ = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="வணக்கம், எனக்கு மருத்துவ ஆலோசனை வேண்டும்",
        business=demo_clinic,
    )
    assert session.language == "ta-IN"
    assert "மருத்துவ ஆலோசனை" in reply1

    # Turn 2: Caller switches mid-call to English
    reply2, _ = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="What are your clinic working hours?",
        business=demo_clinic,
    )
    assert session.language == "en-IN"
    assert "Our clinic working hours are" in reply2

    # Turn 3: Caller switches mid-call back to Tamil
    reply3, _ = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="நாளைக்கு டாக்டர் இருக்கிறாரா?",
        business=demo_clinic,
    )
    assert session.language == "ta-IN"
    assert "மருத்துவர்கள் ஆலோசனைகள் வழங்குகிறார்கள்" in reply3


def test_bilingual_mixed_tanglish_sentences(db_session: Session, demo_clinic: Business):
    """Verify mixed sentences (Tanglish) are recognized and answered naturally."""
    call_sid = "test-call-tanglish-002"
    session = get_or_create_conversation_session(
        db=db_session,
        call_sid=call_sid,
        business_id=demo_clinic.id,
        caller_phone="+919840199002",
        default_language="en-IN",
    )

    # Tanglish input with Latin script
    reply, _ = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="naalaiki appointment kidaikuma?",
        business=demo_clinic,
    )
    assert session.language == "ta-Latn"
    assert "available-ah" in reply or "doctors" in reply


# ==============================================================================
# 3. Complete English Appointment Booking Flow
# ==============================================================================

def test_bilingual_english_only_appointment_booking(db_session: Session, demo_clinic: Business):
    """Verify complete 5-turn English booking flow from greeting to database appointment."""
    call_sid = "test-call-english-booking-003"
    session = get_or_create_conversation_session(
        db=db_session,
        call_sid=call_sid,
        business_id=demo_clinic.id,
        caller_phone="+919840199003",
        default_language="en-IN",
    )

    dialogue = [
        "Hello, I want to book an appointment.",
        "General Physician Consultation",
        "Tomorrow at 10:30 AM",
        "Steve Rogers",
        "Yes, I confirm the appointment.",
    ]

    for turn_idx, text in enumerate(dialogue, 1):
        reply, cont = process_conversational_turn(
            db=db_session,
            session=session,
            speech_text=text,
            business=demo_clinic,
        )
        assert session.language == "en-IN"
        if turn_idx == 1:
            assert "medical service" in reply.lower()
        elif turn_idx == 2:
            assert "date" in reply.lower() or "time" in reply.lower()
        elif turn_idx == 3:
            assert "name" in reply.lower()
        elif turn_idx == 4:
            assert "confirm" in reply.lower()
        elif turn_idx == 5:
            assert "confirmed" in reply.lower() or "thank you" in reply.lower()
            assert not cont

    # Verify appointment in DB
    appt = db_session.scalar(
        select(Appointment).where(Appointment.notes.like(f"%{call_sid}%"))
    )
    assert appt is not None
    assert appt.status == "upcoming"

    cust = db_session.get(Customer, appt.customer_id)
    assert cust is not None
    assert "Steve" in cust.name


# ==============================================================================
# 4. Complete Tamil Appointment Booking Flow
# ==============================================================================

def test_bilingual_tamil_only_appointment_booking(db_session: Session, demo_clinic: Business):
    """Verify complete 5-turn Tamil booking flow from greeting to database appointment."""
    call_sid = "test-call-tamil-booking-004"
    session = get_or_create_conversation_session(
        db=db_session,
        call_sid=call_sid,
        business_id=demo_clinic.id,
        caller_phone="+919840199004",
        default_language="ta-IN",
    )

    dialogue = [
        "எனக்கு டாக்டர் அப்பாயின்ட்மென்ட் வேண்டும்",
        "பொது மருத்துவம்",
        "நாளை காலை 10:30 மணிக்கு",
        "செல்வம்",
        "ஆம் உறுதி செய்கிறேன்",
    ]

    for turn_idx, text in enumerate(dialogue, 1):
        reply, cont = process_conversational_turn(
            db=db_session,
            session=session,
            speech_text=text,
            business=demo_clinic,
        )
        assert session.language == "ta-IN"
        if turn_idx == 5:
            assert "வெற்றிகரமாக பதிவு செய்யப்பட்டது" in reply
            assert not cont

    # Verify appointment in DB
    appt = db_session.scalar(
        select(Appointment).where(Appointment.notes.like(f"%{call_sid}%"))
    )
    assert appt is not None
    assert appt.status == "upcoming"

    cust = db_session.get(Customer, appt.customer_id)
    assert cust is not None
    assert cust.name == "செல்வம்"


# ==============================================================================
# 5. Availability Inquiries Across English and Tamil
# ==============================================================================

def test_bilingual_english_availability_inquiry(db_session: Session, demo_clinic: Business):
    """Verify English doctor availability enquiry."""
    call_sid = "test-call-avail-en-005"
    session = get_or_create_conversation_session(
        db=db_session,
        call_sid=call_sid,
        business_id=demo_clinic.id,
        caller_phone="+919840199005",
        default_language="en-IN",
    )

    reply, _ = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="Is the doctor available tomorrow?",
        business=demo_clinic,
    )
    assert session.language == "en-IN"
    assert "doctors are available" in reply or "slots" in reply


def test_bilingual_tamil_availability_inquiry(db_session: Session, demo_clinic: Business):
    """Verify Tamil doctor availability enquiry."""
    call_sid = "test-call-avail-ta-006"
    session = get_or_create_conversation_session(
        db=db_session,
        call_sid=call_sid,
        business_id=demo_clinic.id,
        caller_phone="+919840199006",
        default_language="ta-IN",
    )

    reply, _ = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="நாளைக்கு டாக்டர் இருக்கிறாரா?",
        business=demo_clinic,
    )
    assert session.language == "ta-IN"
    assert "மருத்துவர்கள் ஆலோசனைகள் வழங்குகிறார்கள்" in reply


# ==============================================================================
# 6. TTS Language Routing & Fallback Melodic Earcon
# ==============================================================================

def test_bilingual_tts_routing_and_melodic_fallback():
    """Verify TTS language parameter resolution and melodic non-silent fallback."""
    tts = ElevenLabsStreamingTTS(api_key="mock_eleven_key")

    # Language code resolution
    assert tts.resolve_language_code("ta-IN") == "ta"
    assert tts.resolve_language_code("en-IN") == "en"
    assert tts.resolve_language_code("te-IN") == "te"

    # Model resolution
    assert tts.resolve_model_for_language("ta-IN") == "eleven_multilingual_v2"
    assert tts.resolve_model_for_language("en-IN") == "eleven_multilingual_v2"
    assert tts.resolve_model_for_language("te-IN") == "eleven_v4_turbo"

    # Melodic fallback verification: ensure valid 8kHz mu-law audio frames
    mock_tts = MockStreamingTTS()
    mulaw_data = mock_tts.synthesize_to_mulaw("Fallback speech", language="ta-IN")
    assert len(mulaw_data) > 0
    # Must divide evenly into standard 160-byte telephony frames (20ms each)
    assert len(mulaw_data) % 160 == 0

    chunks = mock_tts.synthesize_stream_chunks("Fallback test", language="en-IN", chunk_size=160)
    assert len(chunks) > 0
    assert len(chunks[0]) == 160


# ==============================================================================
# 7. Phase 3 Exact Dialogue Examples Verification
# ==============================================================================

def test_phase3_exact_user_prompt_examples(db_session: Session, demo_clinic: Business):
    """Verify the 4 exact examples specified in Phase 3 of the prompt."""
    # Example 1: Caller: "Hello, I want to book an appointment." -> English response
    sess1 = get_or_create_conversation_session(
        db=db_session,
        call_sid="test-p3-ex1",
        business_id=demo_clinic.id,
        caller_phone="+919840199101",
        default_language="ta-IN",
    )
    reply1, _ = process_conversational_turn(
        db=db_session,
        session=sess1,
        speech_text="Hello, I want to book an appointment.",
        business=demo_clinic,
    )
    assert sess1.language == "en-IN"
    assert "medical service" in reply1.lower()

    # Example 2: Caller: "எனக்கு டாக்டர் அப்பாயின்ட்மென்ட் வேண்டும்." -> Tamil script response
    sess2 = get_or_create_conversation_session(
        db=db_session,
        call_sid="test-p3-ex2",
        business_id=demo_clinic.id,
        caller_phone="+919840199102",
        default_language="en-IN",
    )
    reply2, _ = process_conversational_turn(
        db=db_session,
        session=sess2,
        speech_text="எனக்கு டாக்டர் அப்பாயின்ட்மென்ட் வேண்டும்.",
        business=demo_clinic,
    )
    assert sess2.language == "ta-IN"
    assert "மருத்துவ ஆலோசனை" in reply2

    # Example 3: Caller: "நாளைக்கு appointment கிடைக்குமா?" -> Natural Tamil-English mixed response
    sess3 = get_or_create_conversation_session(
        db=db_session,
        call_sid="test-p3-ex3",
        business_id=demo_clinic.id,
        caller_phone="+919840199103",
        default_language="ta-IN",
    )
    reply3, _ = process_conversational_turn(
        db=db_session,
        session=sess3,
        speech_text="நாளைக்கு appointment கிடைக்குமா?",
        business=demo_clinic,
    )
    assert sess3.language in ("ta-IN", "ta-Latn")
    assert "மருத்துவர்கள்" in reply3 or "doctors" in reply3 or "slots" in reply3

    # Example 4: Caller: "What are your clinic working hours?" -> English response
    sess4 = get_or_create_conversation_session(
        db=db_session,
        call_sid="test-p3-ex4",
        business_id=demo_clinic.id,
        caller_phone="+919840199104",
        default_language="ta-IN",
    )
    reply4, _ = process_conversational_turn(
        db=db_session,
        session=sess4,
        speech_text="What are your clinic working hours?",
        business=demo_clinic,
    )
    assert sess4.language == "en-IN"
    assert "working hours are" in reply4.lower()
