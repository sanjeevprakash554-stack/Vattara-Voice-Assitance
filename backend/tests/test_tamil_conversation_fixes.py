"""Tests for Tamil conversation failure fixes (Nov 16, 2026).

Verifies:
1. Deepgram STT language resolution defaults to Tamil ('ta') for Tamil demo and handles English/Telugu.
2. The 4 exact Tamil test utterances:
   - 'வணக்கம்'
   - 'எனக்கு டாக்டர் அப்பாயின்ட்மென்ட் வேண்டும்'
   - 'நாளைக்கு டாக்டர் இருக்கிறாரா?'
   - 'கிளினிக் எத்தனை மணிக்கு திறக்கும்?'
3. Correct language classification (ta-IN for Tamil Unicode script).
4. Correct intent classification.
5. Natural Tamil receptionist responses (no English fallback).
6. Correct TTS language code resolution.
7. Graceful ElevenLabs quota_exceeded circuit breaker and fallback audio generation without silence.
8. Support for Tanglish and mid-call explicit language switching to English.
"""

import json
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.assistant import AssistantConfig, Service
from app.models.business import Business
from app.models.conversation_session import ConversationSession
from app.services.ai.language_detector import (
    detect_language,
    get_display_language_name,
    is_tamil_script,
)
from app.services.ai.natural_receptionist import classify_natural_receptionist_intent
from app.services.streaming.stt_provider import DeepgramStreamingSTT
from app.services.streaming.tts_provider import ElevenLabsStreamingTTS, MockStreamingTTS
from app.services.voice_assistant_service import (
    detect_intent,
    get_or_create_conversation_session,
    process_conversational_turn,
)


@pytest.fixture
def test_clinic_db(db_session: Session) -> dict[str, str]:
    """Ensure active business and services exist for Tamil test verification."""
    biz = db_session.get(Business, "demo-biz-vattara-health")
    if not biz:
        biz = Business(
            id="demo-biz-vattara-health",
            name="Vattara City Clinic & Diagnostics",
            phone="+914428289000",
            email="contact@vattaraclinic.com",
            is_active=True,
        )
        db_session.add(biz)
        db_session.flush()

    cfg = db_session.get(AssistantConfig, "demo-assistant-config")
    if not cfg:
        cfg = AssistantConfig(
            id="demo-assistant-config",
            business_id=biz.id,
            assistant_name="Vattara Voice AI",
            language="ta-IN",
            ai_provider="mock",
            stt_provider="deepgram",
            tts_provider="elevenlabs",
            working_hours='{"monday": {"open": "08:30", "close": "20:00", "enabled": true}}',
            is_active=True,
        )
        db_session.add(cfg)
    else:
        cfg.language = "ta-IN"

    # Services
    srv = db_session.scalar(
        select(Service).where(Service.business_id == biz.id, Service.name == "General Physician Consultation")
    )
    if not srv:
        srv = Service(
            id="srv-gen-physician",
            business_id=biz.id,
            name="General Physician Consultation",
            price=500.0,
            duration_minutes=30,
            is_active=True,
        )
        db_session.add(srv)

    db_session.commit()
    return {"biz_id": biz.id}


# ==============================================================================
# Task A: Deepgram STT Tests
# ==============================================================================

def test_deepgram_stt_language_resolution_tamil_first():
    """Verify Deepgram STT resolves to 'ta' for Tamil demo instead of 'multi'."""
    stt = DeepgramStreamingSTT(api_key="test_key", model="nova-3", multilingual=True)

    # When Tamil or Tamil-script or Tanglish is passed:
    assert stt.resolve_language("ta") == "ta"
    assert stt.resolve_language("ta-IN") == "ta"
    assert stt.resolve_language("ta-Latn") == "ta"

    # Multilingual code-switching mode when explicitly requested:
    assert stt.resolve_language("multi") == "multi"

    # When caller speaks English or Telugu, deliberate language is preserved:
    assert stt.resolve_language("en-IN") == "en-IN"
    assert stt.resolve_language("en-US") == "en-IN"
    assert stt.resolve_language("te-IN") == "te"
    assert stt.resolve_language("te-Latn") == "te"


def test_deepgram_stt_logging_captures_detected_and_transcript():
    """Verify Deepgram STT flush logs both requested and detected languages."""
    stt = DeepgramStreamingSTT(api_key="test_mock_key")
    stt.process_audio_chunk(b"\x00" * 3200)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "results": {
            "channels": [
                {
                    "alternatives": [{"transcript": "வணக்கம்"}],
                    "detected_language": "ta",
                }
            ]
        }
    }

    with patch("httpx.Client.post", return_value=mock_resp), patch("app.services.streaming.stt_provider.logger") as mock_logger:
        res = stt.flush(language="ta-IN")
        assert res == "வணக்கம்"
        assert stt.last_detected_language == "ta"
        mock_logger.info.assert_called()
        call_msg = mock_logger.info.call_args[0][0]
        assert "req_lang" in call_msg or "Deepgram transcribed" in call_msg


# ==============================================================================
# Task B & C: The 4 Exact Tamil Utterances Verification
# ==============================================================================

def test_utterance_1_vanakkam(db_session: Session, test_clinic_db: dict[str, str]):
    """1. வணக்கம் -> Lang: ta-IN, Intent: greeting, Natural Tamil Greeting Response."""
    biz = db_session.get(Business, test_clinic_db["biz_id"])
    session = get_or_create_conversation_session(
        db=db_session,
        call_sid="CS_test_utt_1",
        business_id=biz.id,
        caller_phone="+919876543210",
    )

    utterance = "வணக்கம்"
    detected_lang = detect_language(utterance, current_lang=session.language)
    assert detected_lang == "ta-IN"

    intent, _ = classify_natural_receptionist_intent(utterance)
    assert intent == "greeting"

    resp, cont = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text=utterance,
        business=biz,
    )

    assert cont is True
    assert session.language == "ta-IN"
    assert "வணக்கம்" in resp
    assert "நல்வரவு" in resp or "உதவ" in resp
    # Ensure no English text returned
    assert "Which medical service" not in resp


def test_utterance_2_booking_request(db_session: Session, test_clinic_db: dict[str, str]):
    """2. எனக்கு டாக்டர் அப்பாயின்ட்மென்ட் வேண்டும் -> Lang: ta-IN, Intent: booking, Tamil Slot filling."""
    biz = db_session.get(Business, test_clinic_db["biz_id"])
    session = get_or_create_conversation_session(
        db=db_session,
        call_sid="CS_test_utt_2",
        business_id=biz.id,
        caller_phone="+919876543210",
    )

    utterance = "எனக்கு டாக்டர் அப்பாயின்ட்மென்ட் வேண்டும்"
    detected_lang = detect_language(utterance, current_lang=session.language)
    assert detected_lang == "ta-IN"

    intent, _ = classify_natural_receptionist_intent(utterance)
    assert intent == "booking"

    resp, cont = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text=utterance,
        business=biz,
    )

    assert cont is True
    assert session.language == "ta-IN"
    assert "மருத்துவ ஆலோசனை" in resp or "சேவை" in resp
    assert "பதிவு செய்ய" in resp
    assert "Which medical service" not in resp


def test_utterance_3_doctor_availability(db_session: Session, test_clinic_db: dict[str, str]):
    """3. நாளைக்கு டாக்டர் இருக்கிறாரா? -> Lang: ta-IN, Intent: check_availability, Tamil Slot Response."""
    biz = db_session.get(Business, test_clinic_db["biz_id"])
    session = get_or_create_conversation_session(
        db=db_session,
        call_sid="CS_test_utt_3",
        business_id=biz.id,
        caller_phone="+919876543210",
    )

    utterance = "நாளைக்கு டாக்டர் இருக்கிறாரா?"
    detected_lang = detect_language(utterance, current_lang=session.language)
    assert detected_lang == "ta-IN"

    intent, _ = classify_natural_receptionist_intent(utterance)
    assert intent == "check_availability"

    resp, cont = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text=utterance,
        business=biz,
    )

    assert cont is True
    assert session.language == "ta-IN"
    # Should inform caller of availability/timings in Tamil
    assert ("மருத்துவர்" in resp or "நேரங்கள்" in resp or "ஆலோசனைகள்" in resp)
    assert "Which medical service" not in resp


def test_utterance_4_clinic_timings(db_session: Session, test_clinic_db: dict[str, str]):
    """4. கிளினிக் எத்தனை மணிக்கு திறக்கும்? -> Lang: ta-IN, Intent: business_inquiry_hours, Spoken Tamil Hours."""
    biz = db_session.get(Business, test_clinic_db["biz_id"])
    session = get_or_create_conversation_session(
        db=db_session,
        call_sid="CS_test_utt_4",
        business_id=biz.id,
        caller_phone="+919876543210",
    )

    utterance = "கிளினிக் எத்தனை மணிக்கு திறக்கும்?"
    detected_lang = detect_language(utterance, current_lang=session.language)
    assert detected_lang == "ta-IN"

    intent, _ = classify_natural_receptionist_intent(utterance)
    assert intent == "business_inquiry_hours"

    resp, cont = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text=utterance,
        business=biz,
    )

    assert cont is True
    assert session.language == "ta-IN"
    assert "வேலை நேரம்" in resp or "திறந்திருக்கும்" in resp or "மணி" in resp
    # Ensure raw JSON or "information not in my records" error is NOT present
    assert '{"monday"' not in resp
    assert "பதிவேட்டில் இல்லை" not in resp


# ==============================================================================
# Task D: ElevenLabs TTS & Quota Exceeded Circuit Breaker Tests
# ==============================================================================

def test_elevenlabs_quota_exceeded_handled_gracefully():
    """Verify ElevenLabs 429 quota_exceeded activates circuit breaker and returns audio."""
    tts = ElevenLabsStreamingTTS(api_key="test_xi_key")

    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.text = '{"detail": {"status": "quota_exceeded", "message": "Credits remaining 96 while 165 required"}}'

    with patch("httpx.Client.post", return_value=mock_resp):
        # 1. First call fails with 429 quota_exceeded
        audio = tts.synthesize_to_mulaw("வணக்கம்! Vattara City Clinic", language="ta-IN")
        # Gracefully generates fallback audio instead of empty silence
        assert len(audio) > 0
        assert tts.is_quota_exceeded is True

    # 2. Subsequent call should hit circuit breaker immediately without making HTTP request
    with patch("httpx.Client.post") as mock_post:
        audio2 = tts.synthesize_to_mulaw("அடுத்த கேள்வி", language="ta-IN")
        assert len(audio2) > 0
        # Verified: did not repeatedly spam ElevenLabs with exceeded quota
        mock_post.assert_not_called()


def test_elevenlabs_language_code_resolution():
    """Verify correct ElevenLabs language_code is passed for Tamil and Tanglish."""
    tts = ElevenLabsStreamingTTS(api_key="test_xi_key")
    assert tts.resolve_language_code("ta-IN") == "ta"
    assert tts.resolve_language_code("ta-Latn") == "ta"
    assert tts.resolve_language_code("te-IN") == "te"
    assert tts.resolve_language_code("en-IN") == "en"


# ==============================================================================
# Task B: Mid-Call Language Switching & Tanglish Tests
# ==============================================================================

def test_tanglish_recognition_and_continuity():
    """Verify Tanglish speech is detected as ta-Latn and preserved across turns."""
    t1 = "doctor appointment eppo kidaikum?"
    assert detect_language(t1, current_lang="ta-IN") == "ta-Latn"

    # Subsequent short reply preserves ta-Latn
    t2 = "tomorrow morning 10 am"
    assert detect_language(t2, current_lang="ta-Latn") == "ta-Latn"


def test_explicit_mid_call_switch_to_english():
    """Verify caller can explicitly switch from Tamil to English."""
    # Caller speaks Tamil
    assert detect_language("வணக்கம்", current_lang="ta-IN") == "ta-IN"

    # Caller explicitly switches
    switch_utt = "Can you please speak in English from now on?"
    assert detect_language(switch_utt, current_lang="ta-IN") == "en-IN"
