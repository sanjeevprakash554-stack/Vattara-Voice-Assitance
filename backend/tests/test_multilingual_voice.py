"""Comprehensive test suite for English, Tamil, and Telugu Multilingual Voice Support.

Validates:
1. Deepgram Nova-3 STT Integration (model='nova-3', language='multi', 'ta', 'te', 'en-IN').
2. Whisper STT Telugu, Tamil, and English language parameter mapping.
3. Automatic Language Detection (Telugu script, Tamil script, Teluglish, Tanglish, English).
4. Code-mixing / mixed speech preservation (loanwords like 'doctor', 'appointment' not falsely switching language).
5. Intent classification across English, Tamil, and Telugu.
6. Spoken date and time parsing across English, Tamil, and Telugu.
7. Spoken caller name extraction across English, Tamil, and Telugu.
8. ElevenLabs Multilingual v2 voice resolution and 8kHz mu-law audio synthesis.
9. End-to-end multi-turn appointment booking in Telugu.
10. End-to-end multi-turn appointment booking in Tamil.
11. End-to-end multi-turn appointment booking in English (regression).
12. Stream orchestrator localized greeting generation.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.assistant import AssistantConfig, Service
from app.models.business import Business
from app.models.conversation_session import ConversationSession
from app.services.ai.base import BaseLLMProvider, LLMMessage, LLMResponse
from app.services.ai.factory import get_llm_provider
from app.services.ai.language_detector import (
    detect_language,
    get_display_language_name,
    is_tamil_script,
    is_telugu_script,
)
from app.services.ai.mock_provider import MockLLMProvider
from app.services.ai.prompts import build_system_prompt
from app.services.ai.tools import execute_tool_call
from app.services.streaming.stt_provider import DeepgramStreamingSTT, WhisperStreamingSTT
from app.services.streaming.stream_orchestrator import StreamOrchestrator
from app.services.streaming.tts_provider import (
    ElevenLabsStreamingTTS,
    MockStreamingTTS,
    get_streaming_tts_provider,
)
from app.services.voice_assistant_service import (
    detect_intent,
    execute_llm_conversational_turn,
    extract_caller_name,
    extract_datetime_from_speech,
    format_confirmation_date,
    match_service_from_catalog,
    process_conversational_turn,
)


# ==============================================================================
# 1. Deepgram Nova-3 Speech-To-Text Tests
# ==============================================================================


def test_deepgram_nova3_default_configuration():
    """Verify Deepgram STT defaults to nova-3 model with multilingual capability."""
    stt = DeepgramStreamingSTT(api_key="mock_key")
    assert stt.model == "nova-3"
    assert stt.multilingual is True
    assert stt.provider_name == "deepgram"


def test_deepgram_nova3_language_resolution():
    """Verify language code resolution to Deepgram Nova-3 parameters."""
    stt = DeepgramStreamingSTT(api_key="mock_key", model="nova-3", multilingual=True)

    # Multilingual code-switching mode
    assert stt.resolve_language("multi") == "multi"
    assert stt.resolve_language("multilingual") == "multi"
    assert stt.resolve_language("auto") == "multi"

    # Specific language mapping
    assert stt.resolve_language("ta") == "ta"
    assert stt.resolve_language("ta-IN") == "ta"
    assert stt.resolve_language("ta-Latn") == "ta"
    assert stt.resolve_language("te") == "te"
    assert stt.resolve_language("te-IN") == "te"
    assert stt.resolve_language("te-Latn") == "te"
    assert stt.resolve_language("en-IN") == "en-IN"
    assert stt.resolve_language("en-US") == "en-IN"


def test_deepgram_nova3_multilingual_flush_request():
    """Verify Deepgram Nova-3 REST request sends model=nova-3 and language=multi."""
    stt = DeepgramStreamingSTT(api_key="test_deepgram_key", model="nova-3", multilingual=True)
    stt.process_audio_chunk(bytes([100] * 3200))

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "results": {
            "channels": [
                {
                    "alternatives": [
                        {"transcript": "నమస్కారం డాక్టర్ అపాయింట్‌మెంట్ కావాలి"}
                    ]
                }
            ]
        }
    }

    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        result = stt.flush(language="multi")
        assert result == "నమస్కారం డాక్టర్ అపాయింట్‌మెంట్ కావాలి"

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs["params"]["model"] == "nova-3"
        assert kwargs["params"]["language"] == "multi"
        assert kwargs["headers"]["Authorization"] == "Token test_deepgram_key"


def test_deepgram_nova3_telugu_and_tamil_speech_requests():
    """Verify Deepgram Nova-3 specifically passes 'te' for Telugu and 'ta' for Tamil."""
    stt = DeepgramStreamingSTT(api_key="test_key")

    mock_resp_te = MagicMock()
    mock_resp_te.status_code = 200
    mock_resp_te.json.return_value = {
        "results": {"channels": [{"alternatives": [{"transcript": "నాకు డాక్టర్ కావాలి"}]}]}
    }

    stt.process_audio_chunk(bytes([50] * 3200))
    with patch("httpx.Client.post", return_value=mock_resp_te) as mock_post:
        res = stt.flush(language="te-IN")
        assert res == "నాకు డాక్టర్ కావాలి"
        assert mock_post.call_args[1]["params"]["language"] == "te"
        assert mock_post.call_args[1]["params"]["model"] == "nova-3"


def test_deepgram_nova3_tamil_and_tanglish_medical_keyterms():
    """Verify Deepgram request includes Tamil script, Tanglish, and English medical keyterms."""
    stt = DeepgramStreamingSTT(api_key="test_key")
    stt.process_audio_chunk(bytes([50] * 3200))

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "results": {
            "channels": [
                {
                    "alternatives": [
                        {"transcript": "வணக்கம் எனக்கு பீடியாட்ரிக் செக்கப் முன்பதிவு செய்ய வேண்டும்"}
                    ],
                    "detected_language": "ta",
                }
            ]
        }
    }

    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        transcript = stt.flush(language="ta-IN")
        assert transcript == "வணக்கம் எனக்கு பீடியாட்ரிக் செக்கப் முன்பதிவு செய்ய வேண்டும்"
        assert stt.last_detected_language == "ta"

        # Check request parameters
        call_params = mock_post.call_args[1]["params"]
        assert call_params["model"] == "nova-3"
        assert call_params["language"] == "ta"
        keyterms = call_params["keyterm"]
        assert "மருத்துவர்" in keyterms
        assert "முன்பதிவு" in keyterms
        assert "பீடியாட்ரிக் செக்கப்" in keyterms
        assert "maruthuvar" in keyterms
        assert "pediatric" in keyterms

    # Test reset clears last_detected_language
    stt.reset()
    assert stt.last_detected_language is None


def test_whisper_stt_telugu_mapping():
    """Verify WhisperStreamingSTT maps Telugu language code properly."""
    stt = WhisperStreamingSTT(api_key="test_openai_key")
    stt.process_audio_chunk(bytes([40] * 3200))

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"text": "నాకు కార్డియాలజీ అపాయింట్‌మెంట్ కావాలి"}

    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        res = stt.flush(language="te-IN")
        assert res == "నాకు కార్డియాలజీ అపాయింట్‌మెంట్ కావాలి"
        data_arg = mock_post.call_args[1]["data"]
        assert data_arg["language"] == "te"


# ==============================================================================
# 2. Automatic Language Detection Tests
# ==============================================================================


def test_telugu_and_tamil_script_detection():
    """Verify Unicode script classification for Tamil and Telugu."""
    assert is_telugu_script("నమస్కారం డాక్టర్ గారు") is True
    assert is_telugu_script("Hello doctor") is False
    assert is_telugu_script("வணக்கம்") is False

    assert is_tamil_script("வணக்கம் டாக்டர்") is True
    assert is_tamil_script("నమస్కారం") is False
    assert is_tamil_script("Hello doctor") is False


def test_automatic_language_selection_native_scripts():
    """Verify language detector identifies Telugu, Tamil, and English in native script."""
    assert detect_language("నమస్కారం! నాకు అపాయింట్‌మెంట్ కావాలి") == "te-IN"
    assert detect_language("வணக்கம்! எனக்கு அப்பாயின்ட்மென்ட் வேண்டும்") == "ta-IN"
    assert detect_language("Hello, I would like to schedule a doctor visit.") == "en-IN"


def test_teluglish_phonetic_detection():
    """Verify colloquial Telugu written in Latin script (Teluglish) is recognized."""
    samples = [
        "Namaskaram! Repu appointment slot undha?",
        "Naaku doctor consultation repu 10 am ki kavali",
        "Eppudu slots unnaya please cheppandi",
        "Appointment time marchandi",
        "Mee peru enti doctoru",
    ]
    for s in samples:
        detected = detect_language(s)
        assert detected == "te-Latn", f"Failed for Teluglish phrase: '{s}'"


def test_tanglish_phonetic_detection():
    """Verify colloquial Tamil written in Latin script (Tanglish) is recognized."""
    samples = [
        "Vanakkam! Naalaiki doctor-ah parkanum",
        "Enakku general physician consultation venum",
        "Slot iruka kaalaila 10 maniki?",
        "Romba nandri, appointment confirm pannunga",
    ]
    for s in samples:
        detected = detect_language(s)
        assert detected == "ta-Latn", f"Failed for Tanglish phrase: '{s}'"


def test_code_mixing_technical_words_preservation():
    """Verify borrowed English medical/appointment words do NOT trigger unwarranted language switch."""
    # Caller speaks Teluglish with loanwords: 'doctor', 'appointment', 'booking'
    assert detect_language("Doctor appointment repu morning 10 am ki book cheyali") == "te-Latn"
    assert detect_language("Cardiology slots unnaya check cheyandi please") == "te-Latn"

    # Caller speaks Tanglish with loanwords
    assert detect_language("Cardiology doctor appointment naalaiki book pannanum") == "ta-Latn"

    # Persistence: once in Telugu, minor confirmation like 'Yes' or 'Okay doctor' preserves preferred language
    assert detect_language("Okay doctor", current_lang="te-Latn") == "te-Latn"
    assert detect_language("Yes 10 am is good", current_lang="te-Latn") == "te-Latn"
    assert detect_language("Okay doctor", current_lang="ta-Latn") == "ta-Latn"

    # Explicit switch to English should switch language
    assert detect_language("Please speak in English from now on", current_lang="te-Latn") == "en-IN"


def test_display_language_names():
    """Verify localized display labels for all language variants."""
    assert "Telugu" in get_display_language_name("te-IN")
    assert "Teluglish" in get_display_language_name("te-Latn")
    assert "Tamil" in get_display_language_name("ta-IN")
    assert "Tanglish" in get_display_language_name("ta-Latn")
    assert "English" in get_display_language_name("en-IN")


# ==============================================================================
# 3. Intent & Entity Extraction Tests Across English, Tamil, and Telugu
# ==============================================================================


def test_intent_detection_across_all_languages():
    """Verify intent classification accurately handles English, Tamil, and Telugu."""
    # Booking Intent
    assert detect_intent("I want to book an appointment") == "booking"
    assert detect_intent("அப்பாயின்ட்மென்ட் முன்பதிவு செய்ய வேண்டும்") == "booking"
    assert detect_intent("டாக்டரை பார்க்க வேண்டும்") == "booking"
    assert detect_intent("నాకు అపాయింట్‌మెంట్ కావాలి") == "booking"
    assert detect_intent("డాక్టర్ దర్శనం బుక్ చేయాలి") == "booking"
    assert detect_intent("doctor appointment book cheyali") == "booking"

    # Check Availability Intent
    assert detect_intent("Are slots available tomorrow?") == "check_availability"
    assert detect_intent("நாளைக்கு நேரம் இருக்கிறதா?") == "check_availability"
    assert detect_intent("స్లాట్లు ఉన్నాయా?") == "check_availability"
    assert detect_intent("repu slots unnaya") == "check_availability"

    # Reschedule Intent
    assert detect_intent("I need to reschedule my consultation") == "reschedule_appointment"
    assert detect_intent("நேரத்தை மாற்ற வேண்டும்") == "reschedule_appointment"
    assert detect_intent("సమయం మార్చండి") == "reschedule_appointment"
    assert detect_intent("appointment time marchandi") == "reschedule_appointment"

    # Cancel Intent
    assert detect_intent("Cancel my appointment") == "cancel_appointment"
    assert detect_intent("முன்பதிவை ரத்து செய்") == "cancel_appointment"
    assert detect_intent("అపాయింట్‌మెంట్ రద్దు చేయండి") == "cancel_appointment"
    assert detect_intent("appointment cancel cheyandi") == "cancel_appointment"

    # Exit Intent
    assert detect_intent("Goodbye") == "cancellation"
    assert detect_intent("வேண்டாம் நன்றி") == "cancellation"
    assert detect_intent("వద్దు చాలు") == "cancellation"
    assert detect_intent("vaddu chalamma") == "cancellation"

    # Confirmation
    assert detect_intent("Yes please") == "confirmation"
    assert detect_intent("ஆம் சரி") == "confirmation"
    assert detect_intent("అవును సరే") == "confirmation"
    assert detect_intent("avunu thappakunda") == "confirmation"

    # Greeting
    assert detect_intent("Hello") == "greeting"
    assert detect_intent("வணக்கம்") == "greeting"
    assert detect_intent("నమస్కారం") == "greeting"
    assert detect_intent("namaskaramandi") == "greeting"


def test_extract_datetime_across_all_languages():
    """Verify spoken relative date and time parsing across English, Tamil, and Telugu."""
    fixed_now = datetime(2026, 11, 16, 9, 0, 0, tzinfo=timezone.utc)  # Monday

    # English: Tomorrow 10 AM -> Tuesday 10:00
    dt_en, _ = extract_datetime_from_speech("Tomorrow at 10 AM", fixed_now)
    assert dt_en is not None
    assert dt_en.date() == fixed_now.date() + timedelta(days=1)
    assert dt_en.hour == 10

    # Tamil: நாளை காலை 10 மணிக்கு
    dt_ta, _ = extract_datetime_from_speech("நாளை 10 மணிக்கு", fixed_now)
    assert dt_ta is not None
    assert dt_ta.date() == fixed_now.date() + timedelta(days=1)
    assert dt_ta.hour == 10

    # Tanglish: naalaiki 10 maniki
    dt_tngl, _ = extract_datetime_from_speech("naalaiki 10 maniki", fixed_now)
    assert dt_tngl is not None
    assert dt_tngl.date() == fixed_now.date() + timedelta(days=1)
    assert dt_tngl.hour == 10

    # Telugu: రేపు 10 గంటలకు
    dt_te, _ = extract_datetime_from_speech("రేపు 10 గంటలకు", fixed_now)
    assert dt_te is not None
    assert dt_te.date() == fixed_now.date() + timedelta(days=1)
    assert dt_te.hour == 10

    # Teluglish: repu 10 gantalu
    dt_telg, _ = extract_datetime_from_speech("repu 10 gantalu", fixed_now)
    assert dt_telg is not None
    assert dt_telg.date() == fixed_now.date() + timedelta(days=1)
    assert dt_telg.hour == 10

    # Evening conversion in Telugu: సాయంత్రం 4 గంటలకు -> 16:00
    dt_eve, _ = extract_datetime_from_speech("రేపు సాయంత్రం 4 గంటలకు", fixed_now)
    assert dt_eve is not None
    assert dt_eve.hour == 16


def test_extract_caller_name_across_languages():
    """Verify spoken caller name extraction across English, Tamil, and Telugu."""
    assert extract_caller_name("My name is John Doe") == "John Doe"
    assert extract_caller_name("என் பெயர் கார்த்திக்") == "கார்த்திக்"
    assert extract_caller_name("en peyar Ramesh") == "Ramesh"
    assert extract_caller_name("నా పేరు సురేష్") == "సురేష్"
    assert extract_caller_name("naa peru Venkatesh") == "Venkatesh"
    assert extract_caller_name("na peru Suresh Kumar") == "Suresh Kumar"


def test_format_confirmation_date_across_languages():
    """Verify month formatting across English, Tamil, and Telugu."""
    sample_dt = datetime(2026, 5, 20, 10, 30)
    assert "May 20, 2026" in format_confirmation_date(sample_dt, "en-IN")
    assert "மே" in format_confirmation_date(sample_dt, "ta-IN")
    assert "మే" in format_confirmation_date(sample_dt, "te-IN")


# ==============================================================================
# 4. ElevenLabs Multilingual v2 Voice Selection Tests
# ==============================================================================


def test_elevenlabs_multilingual_voice_selection():
    """Verify ElevenLabs voice resolution respects language preferences."""
    tts = ElevenLabsStreamingTTS(api_key="mock_key", voice_id="default_voice_123")

    # With default settings, language voice falls back to default voice ID
    assert tts.get_voice_for_language("en-IN") == "default_voice_123"
    assert tts.get_voice_for_language("ta-IN") == "default_voice_123"
    assert tts.get_voice_for_language("te-IN") == "default_voice_123"

    # When dedicated language voices are configured
    with patch.object(settings, "ELEVENLABS_VOICE_ID_TA", "tamil_voice_id"), \
         patch.object(settings, "ELEVENLABS_VOICE_ID_TE", "telugu_voice_id"), \
         patch.object(settings, "ELEVENLABS_VOICE_ID_EN", "english_voice_id"):
        assert tts.get_voice_for_language("ta-IN") == "tamil_voice_id"
        assert tts.get_voice_for_language("ta-Latn") == "tamil_voice_id"
        assert tts.get_voice_for_language("te-IN") == "telugu_voice_id"
        assert tts.get_voice_for_language("te-Latn") == "telugu_voice_id"
        assert tts.get_voice_for_language("en-IN") == "english_voice_id"


def test_elevenlabs_synthesize_telugu_mulaw_stream():
    """Verify ElevenLabs synthesizes Telugu text into standard 8kHz mu-law audio frames."""
    tts = ElevenLabsStreamingTTS(api_key="mock_key")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = bytes([128] * 480)  # 3 frames of 160 bytes (20ms each)

    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        chunks = tts.synthesize_stream_chunks(
            text="నమస్కారం! మీ అపాయింట్‌మెంట్ ధృవీకరించబడింది.",
            language="te-IN",
            chunk_size=160,
        )
        assert len(chunks) == 3
        assert len(chunks[0]) == 160

        _, kwargs = mock_post.call_args
        assert kwargs["params"]["output_format"] == "ulaw_8000"
        # ElevenLabs dynamically routes Telugu to eleven_v4_turbo since eleven_multilingual_v2 does not support te
        assert kwargs["json"]["model_id"] == "eleven_v4_turbo"
        assert kwargs["json"]["language_code"] == "te"
        assert kwargs["json"]["text"] == "నమస్కారం! మీ అపాయింట్‌మెంట్ ధృవీకరించబడింది."


# ==============================================================================
# 5. Stream Orchestrator Localized Greeting Tests
# ==============================================================================


def test_stream_orchestrator_greetings():
    """Verify initial greeting text generation for English, Tamil, and Telugu."""
    mock_biz = MagicMock()
    mock_biz.name = "Apollo Clinic"

    en_greet = StreamOrchestrator._build_greeting_text(mock_biz, "en-IN")
    assert "Thank you for calling Apollo Clinic" in en_greet

    ta_greet = StreamOrchestrator._build_greeting_text(mock_biz, "ta-IN")
    assert "வணக்கம்!" in ta_greet and "Apollo Clinic" in ta_greet

    tngl_greet = StreamOrchestrator._build_greeting_text(mock_biz, "ta-Latn")
    assert "Vanakkam!" in tngl_greet and "Apollo Clinic" in tngl_greet

    te_greet = StreamOrchestrator._build_greeting_text(mock_biz, "te-IN")
    assert "నమస్కారం!" in te_greet and "Apollo Clinic" in te_greet

    telg_greet = StreamOrchestrator._build_greeting_text(mock_biz, "te-Latn")
    assert "Namaskaram!" in telg_greet and "Apollo Clinic" in telg_greet

    # Phase 5 Bilingual Greeting (without premature language assumption)
    bilingual_greet = StreamOrchestrator._build_greeting_text(mock_biz, "bilingual")
    assert "வணக்கம்!" in bilingual_greet and "Welcome to Apollo Clinic" in bilingual_greet and "How can I help you today?" in bilingual_greet

    auto_greet = StreamOrchestrator._build_greeting_text(mock_biz, "auto")
    assert "வணக்கம்!" in auto_greet and "Welcome to Apollo Clinic" in auto_greet

    # Default fallback with no business name should avoid hardcoding 'Vattara'
    fallback_greet = StreamOrchestrator._build_greeting_text(None, "bilingual")
    assert "our clinic" in fallback_greet and "Vattara" not in fallback_greet


# ==============================================================================
# 6. End-to-End Conversational Booking Tests in Telugu, Tamil, and English
# ==============================================================================


@pytest.fixture
def mock_multilingual_db(db_session: Session) -> tuple[Business, Service]:
    """Create test business with cardiology service and assistant config."""
    biz = Business(
        id="test-biz-multi-123",
        name="Vattara Health Care",
        email="clinic@vattara.com",
        phone="+919876543210",
        is_active=True,
    )
    db_session.add(biz)

    service = Service(
        id="srv-cardio-999",
        business_id=biz.id,
        name="Cardiology Consultation",
        duration_minutes=30,
        price=750.0,
        is_active=True,
    )
    db_session.add(service)

    cfg = AssistantConfig(
        business_id=biz.id,
        language="en-IN",
        stt_provider="mock",
        tts_provider="mock",
    )
    from app.models.business_hours import BusinessHour
    for dow in range(7):
        db_session.add(BusinessHour(business_id=biz.id, day_of_week=dow, open_time="08:00", close_time="20:00", is_closed=False))
    db_session.commit()
    db_session.refresh(biz)
    db_session.refresh(service)
    return biz, service


def test_conversational_telugu_booking_flow(db_session: Session, mock_multilingual_db: tuple[Business, Service]):
    """Verify multi-turn appointment booking entirely in Telugu (తెలుగు)."""
    biz, service = mock_multilingual_db
    call_sid = "CS_telugu_test_001"

    session = ConversationSession(
        call_sid=call_sid,
        business_id=biz.id,
        caller_phone="+919111122222",
        step="greeting",
        language="en-IN",
        retry_count=0,
        is_completed=False,
    )
    db_session.add(session)
    db_session.commit()

    # Turn 1: Caller speaks in Telugu requesting cardiology
    reply_1, cont_1 = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="నమస్కారం, నాకు గుండె జబ్బు డాక్టర్ కావాలి",
        business=biz,
    )
    assert cont_1 is True
    assert session.language in ("te-Latn", "te-IN")
    assert session.service_id == service.id
    # Assistant asks for date and time in Telugu
    assert "సంప్రదింపులకు" in reply_1 or "ఏ రోజు మరియు సమయం" in reply_1

    # Turn 2: Caller provides date and time: "రేపు 10 గంటలకు"
    reply_2, cont_2 = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="రేపు 10 గంటలకు అనుకూలంగా ఉంటుంది",
        business=biz,
    )
    assert cont_2 is True
    assert session.appointment_datetime_iso is not None
    # Assistant asks for caller name in Telugu
    assert "మీ పూర్తి పేరు" in reply_2

    # Turn 3: Caller gives name: "నా పేరు వెంకటేష్"
    reply_3, cont_3 = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="నా పేరు వెంకటేష్",
        business=biz,
    )
    # Turn 3 completes the booking!
    assert cont_3 is False
    assert session.is_completed is True
    assert session.customer_name == "వెంకటేష్"
    assert "విజయవంతంగా నిర్ధారించబడ్డాయి" in reply_3 or "ధన్యవాదాలు" in reply_3


def test_conversational_teluglish_booking_flow(db_session: Session, mock_multilingual_db: tuple[Business, Service]):
    """Verify multi-turn booking in Teluglish (Telugu written phonetically in Latin script)."""
    biz, service = mock_multilingual_db
    call_sid = "CS_teluglish_test_002"

    session = ConversationSession(
        call_sid=call_sid,
        business_id=biz.id,
        caller_phone="+919222233333",
        step="greeting",
        language="en-IN",
        retry_count=0,
        is_completed=False,
    )
    db_session.add(session)
    db_session.commit()

    # Turn 1: Teluglish service request
    reply_1, cont_1 = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="Namaskaram, naaku cardiology doctor consultation kavali",
        business=biz,
    )
    assert cont_1 is True
    assert session.language in ("te-Latn", "te-IN")
    assert session.service_id == service.id

    # Turn 2: Teluglish date & time
    reply_2, cont_2 = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="repu morning 10 am ki book cheyandi",
        business=biz,
    )
    assert cont_2 is True
    assert session.appointment_datetime_iso is not None
    assert "full name" in reply_2.lower()

    # Turn 3: Teluglish name
    reply_3, cont_3 = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="naa peru Rajesh Kumar",
        business=biz,
    )
    assert cont_3 is False
    assert session.is_completed is True
    assert session.customer_name == "Rajesh Kumar"
    assert "confirmed" in reply_3.lower() or "dhanyavadalu" in reply_3.lower()


def test_conversational_tamil_booking_flow(db_session: Session, mock_multilingual_db: tuple[Business, Service]):
    """Verify multi-turn appointment booking in Tamil (தமிழ்)."""
    biz, service = mock_multilingual_db
    call_sid = "CS_tamil_test_003"

    session = ConversationSession(
        call_sid=call_sid,
        business_id=biz.id,
        caller_phone="+919333344444",
        step="greeting",
        language="en-IN",
        retry_count=0,
        is_completed=False,
    )
    db_session.add(session)
    db_session.commit()

    # Turn 1: Tamil service request
    reply_1, cont_1 = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="வணக்கம், எனக்கு இதய சிகிச்சை மருத்துவ ஆலோசனை வேண்டும்",
        business=biz,
    )
    assert cont_1 is True
    assert session.language == "ta-IN"
    assert session.service_id == service.id

    # Turn 2: Tamil date & time
    reply_2, cont_2 = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="நாளை காலை 10 மணிக்கு வேண்டும்",
        business=biz,
    )
    assert cont_2 is True
    assert "பெயரை" in reply_2

    # Turn 3: Tamil name
    reply_3, cont_3 = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="என் பெயர் கார்த்திக்",
        business=biz,
    )
    assert cont_3 is False
    assert session.is_completed is True
    assert session.customer_name == "கார்த்திக்"
    assert "வெற்றிகரமாக பதிவு செய்யப்பட்டது" in reply_3


def test_conversational_english_booking_regression(db_session: Session, mock_multilingual_db: tuple[Business, Service]):
    """Verify existing English appointment booking flow remains 100% working without regressions."""
    biz, service = mock_multilingual_db
    call_sid = "CS_english_test_004"

    session = ConversationSession(
        call_sid=call_sid,
        business_id=biz.id,
        caller_phone="+919444455555",
        step="greeting",
        language="en-IN",
        retry_count=0,
        is_completed=False,
    )
    db_session.add(session)
    db_session.commit()

    # Turn 1: English single turn with all entities
    reply, cont = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="Hello, my name is David Warner. I want to book a cardiology appointment tomorrow at 10 AM.",
        business=biz,
    )
    assert cont is False
    assert session.is_completed is True
    assert session.customer_name == "David Warner"
    assert session.service_id == service.id
    assert "confirmed" in reply.lower()
    assert "David Warner" in reply


def test_system_prompt_builder_includes_multilingual_instructions():
    """Verify generated system prompt incorporates English, Tamil, and Telugu receptionist guidelines."""
    prompt = build_system_prompt(
        assistant_name="Vattara AI",
        business_name="City Hospital",
        current_datetime_str="2026-11-16 10:00:00",
        timezone_str="Asia/Kolkata",
        services=[{"id": "s1", "name": "General Care", "duration_minutes": 20, "price": 500}],
        operating_hours=[{"day": "Monday", "open": "09:00", "close": "18:00", "closed": False}],
    )
    assert "English" in prompt
    assert "Tamil (தமிழ்)" in prompt
    assert "Telugu (తెలుగు)" in prompt
    assert "Teluglish" in prompt
    assert "Tanglish" in prompt
    assert "City Hospital" in prompt


# ==============================================================================
# 3. Phase 2: Intelligent Language Detection & Conversation Continuity Tests
# ==============================================================================


def test_phase2_tamil_and_tanglish_distinction_and_persistence():
    """Verify ta-Latn, ta-IN, te-Latn, and te-IN are preserved without collapsing."""
    # Tamil Unicode vs Tanglish
    assert detect_language("வணக்கம் டாக்டர், எனக்கு அப்பாயின்ட்மென்ட் வேண்டும்") == "ta-IN"
    assert detect_language("Vanakkam doctor, enakku appointment venum") == "ta-Latn"

    # Telugu Unicode vs Teluglish
    assert detect_language("నమస్కారం డాక్టర్, నాకు అపాయింట్‌మెంట్ కావాలి") == "te-IN"
    assert detect_language("Namaskaram doctor, naaku appointment kavali") == "te-Latn"

    # English
    assert detect_language("Hello doctor, I would like to book an appointment") == "en-IN"


def test_phase2_user_specified_code_switching_examples():
    """Verify exact user-specified code-switching and medical inquiry utterances."""
    # 1. "Doctor appointment eppo kidaikum?"
    assert detect_language("Doctor appointment eppo kidaikum?") == "ta-Latn"

    # 2. "Enakku tomorrow morning slot venum."
    assert detect_language("Enakku tomorrow morning slot venum.") == "ta-Latn"

    # 3. "Naalaikku 10 mani ku book pannunga."
    assert detect_language("Naalaikku 10 mani ku book pannunga.") == "ta-Latn"

    # 4. "Doctor consultation fees evlo?"
    assert detect_language("Doctor consultation fees evlo?") == "ta-Latn"

    # 5. "எனக்கு tomorrow appointment வேண்டும்."
    assert detect_language("எனக்கு tomorrow appointment வேண்டும்.") == "ta-IN"
    assert detect_language("எனக்கு tomorrow appointment வேண்டும்.", current_lang="ta-Latn") == "ta-Latn"


def test_phase2_medical_loanwords_do_not_switch_language():
    """Verify common borrowed English medical terms do NOT cause a false switch to English."""
    # In Tanglish: medical loanwords and short replies must stay in ta-Latn
    assert detect_language("Pediatric consultation charges", current_lang="ta-Latn") == "ta-Latn"
    assert detect_language("Tomorrow 10 AM slot", current_lang="ta-Latn") == "ta-Latn"
    assert detect_language("Steve", current_lang="ta-Latn") == "ta-Latn"
    assert detect_language("Yes please confirm", current_lang="ta-Latn") == "ta-Latn"

    # In Tamil script: English words mixed in must stay in ta-IN
    assert detect_language("Tomorrow 10 AM", current_lang="ta-IN") == "ta-IN"
    assert detect_language("Cardiology checkup", current_lang="ta-IN") == "ta-IN"
    assert detect_language("Steve", current_lang="ta-IN") == "ta-IN"


def test_phase2_dynamic_language_switching_mid_call():
    """Verify caller can switch to English and back to Tanglish/Tamil naturally."""
    # 1. Starts in Tanglish
    lang = detect_language("Vanakkam doctor, naalaiki appointment slot iruka?")
    assert lang == "ta-Latn"

    # 2. Continues with loanwords (stays Tanglish)
    lang = detect_language("Cardiology doctor", current_lang=lang)
    assert lang == "ta-Latn"

    # 3. Caller switches explicitly to English
    lang = detect_language("Can we switch to English please?", current_lang=lang)
    assert lang == "en-IN"

    # 4. Caller asks in English
    lang = detect_language("What are your clinic timings tomorrow?", current_lang=lang)
    assert lang == "en-IN"

    # 5. Caller switches back to Tanglish
    lang = detect_language("Seri, naalaiki 10 maniki confirm pannunga", current_lang=lang)
    assert lang == "ta-Latn"

    # 6. Caller concludes in Tanglish
    lang = detect_language("Romba nandri doctor", current_lang=lang)
    assert lang == "ta-Latn"


def test_phase2_conversational_tanglish_booking_end_to_end(
    db_session: Session,
    mock_multilingual_db: tuple[Business, Service],
):
    """Verify multi-turn Tanglish booking preserves ta-Latn and generates Tanglish prompts."""
    biz, service = mock_multilingual_db
    call_sid = "CS_phase2_tanglish_test"

    session = ConversationSession(
        call_sid=call_sid,
        business_id=biz.id,
        caller_phone="+919555566666",
        step="greeting",
        language="en-IN",
        retry_count=0,
        is_completed=False,
    )
    db_session.add(session)
    db_session.commit()

    # Turn 1: Caller requests service in Tanglish
    reply_1, cont_1 = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="Vanakkam, enakku cardiology doctor consultation venum",
        business=biz,
    )
    assert cont_1 is True
    # CRITICAL: Must be ta-Latn, NOT collapsed to ta-IN
    assert session.language == "ta-Latn"
    assert session.detected_language == "ta-Latn"
    assert session.service_id == service.id
    # Assistant asks for date/time in Tanglish
    assert "date and time" in reply_1.lower() or "convenient" in reply_1.lower()

    # Turn 2: Caller provides date & time in Tanglish with loanwords
    reply_2, cont_2 = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="naalaiki kaalai 10 maniki slot venum",
        business=biz,
    )
    assert cont_2 is True
    assert session.language == "ta-Latn"
    assert session.appointment_datetime_iso is not None
    # Assistant asks for customer name in Tanglish
    assert "full name" in reply_2.lower()

    # Turn 3: Caller gives name in Tanglish -> completes booking in Tanglish
    reply_3, cont_3 = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="en peyar Steve",
        business=biz,
    )
    assert cont_3 is False
    assert session.is_completed is True
    assert session.language == "ta-Latn"
    assert session.customer_name == "Steve"
    # Final confirmation spoken in Tanglish (not collapsed to Tamil script)
    assert "nandri" in reply_3.lower() or "vanakkam" in reply_3.lower()
    assert "steve" in reply_3.lower()


# ==============================================================================
# 4. Phase 3: Dynamic LLM Integration & Natural Conversational Intelligence Tests
# ==============================================================================


def test_phase3_llm_provider_instantiation_and_async():
    """Verify get_llm_provider and asynchronous agenerate_response interface."""
    import inspect

    # 1. Mock Provider
    mock_llm = get_llm_provider("mock")
    assert isinstance(mock_llm, MockLLMProvider)

    # 2. Verify agenerate_response is an async coroutine method on BaseLLMProvider
    assert inspect.iscoroutinefunction(mock_llm.agenerate_response)

    # 3. Verify generate_response produces valid LLMResponse
    messages = [LLMMessage(role="user", content="Hello, is the clinic open today?")]
    system_prompt = "You are an AI receptionist."
    resp = mock_llm.generate_response(
        messages=messages,
        system_prompt=system_prompt,
        active_services=[],
        available_tools=[],
    )
    assert isinstance(resp, LLMResponse)
    assert resp.text != ""


def test_phase3_dynamic_system_prompt_builder():
    """Verify dynamic system prompt constructs rich tenant context with doctors and state."""
    services = [
        {"id": "srv-1", "name": "Cardiology Consultation", "duration_minutes": 30, "price": 800, "description": "Heart checkup"},
        {"id": "srv-2", "name": "Pediatric Checkup", "duration_minutes": 20, "price": 500, "description": "Child wellness"},
    ]
    hours = [
        {"day": "Monday", "open": "09:00", "close": "18:00", "closed": False},
        {"day": "Sunday", "open": "10:00", "close": "14:00", "closed": True},
    ]
    doctors = [
        {"name": "Dr. Ramesh (Cardiologist)", "available_days": [{"day": "Monday", "start": "09:00", "end": "13:00"}]},
    ]
    state = {
        "service_name": "Cardiology Consultation",
        "appointment_datetime_iso": "2026-11-18T10:00:00+05:30",
        "customer_name": "Steve",
        "language": "ta-Latn",
        "step": "awaiting_confirmation",
    }

    prompt = build_system_prompt(
        assistant_name="Vattara AI",
        business_name="City Heart Center",
        current_datetime_str="2026-11-17 10:00:00 IST",
        timezone_str="Asia/Kolkata",
        services=services,
        operating_hours=hours,
        business_profile="City Heart Center - Specialized Cardiac Hospital. Phone: +914428280000",
        doctor_schedules=doctors,
        session_state=state,
    )

    # Assert all rich context elements are present
    assert "City Heart Center" in prompt
    assert "Dr. Ramesh (Cardiologist)" in prompt
    assert "Cardiology Consultation" in prompt
    assert "₹800" in prompt
    assert "Steve" in prompt
    assert "ta-Latn" in prompt
    assert "check_available_slots" in prompt
    assert "book_appointment" in prompt
    assert "get_doctors" in prompt
    assert "get_business_info" in prompt


def test_phase3_tool_execution_all_eight_tools(
    db_session: Session,
    mock_multilingual_db: tuple[Business, Service],
):
    """Verify function calling dispatcher executes all 8 tools cleanly."""
    biz, service = mock_multilingual_db

    # 1. get_services_and_hours
    res_srv = execute_tool_call(db_session, biz.id, "get_services_and_hours", {})
    assert "services" in res_srv
    assert "operating_schedule" in res_srv

    # 2. get_doctors
    res_doc = execute_tool_call(db_session, biz.id, "get_doctors", {})
    assert "doctors" in res_doc
    assert len(res_doc["doctors"]) > 0

    # 3. get_business_info
    res_biz = execute_tool_call(db_session, biz.id, "get_business_info", {})
    assert res_biz["name"] == biz.name
    assert res_biz["phone"] == biz.phone

    # 4. transfer_to_human
    res_trans = execute_tool_call(db_session, biz.id, "transfer_to_human", {"reason": "Caller requested desk"})
    assert res_trans["success"] is True
    assert res_trans["action"] == "transfer"

    # 5. check_available_slots
    target_d = (datetime.now(timezone.utc) + timedelta(days=2)).date().isoformat()
    res_slots = execute_tool_call(db_session, biz.id, "check_available_slots", {"date": target_d, "service_id": service.id})
    assert "date" in res_slots

    # 6. book_appointment
    target_dt = (datetime.now(timezone.utc) + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0)
    res_book = execute_tool_call(
        db_session,
        biz.id,
        "book_appointment",
        {
            "customer_name": "John Doe",
            "customer_phone": "+919888877777",
            "service_id": service.id,
            "appointment_time": target_dt.isoformat(),
        },
    )
    assert res_book["success"] is True
    appt_id = res_book["appointment_id"]

    # 7. reschedule_appointment
    new_dt = (datetime.now(timezone.utc) + timedelta(days=3)).replace(hour=11, minute=0, second=0, microsecond=0)
    res_resched = execute_tool_call(
        db_session,
        biz.id,
        "reschedule_appointment",
        {
            "customer_phone": "+919888877777",
            "new_appointment_time": new_dt.isoformat(),
            "appointment_id": appt_id,
        },
    )
    assert res_resched["success"] is True

    # 8. cancel_appointment
    res_cancel = execute_tool_call(
        db_session,
        biz.id,
        "cancel_appointment",
        {
            "customer_phone": "+919888877777",
            "appointment_id": appt_id,
        },
    )
    assert res_cancel["success"] is True


def test_phase3_dynamic_llm_conversational_turn_tanglish(
    db_session: Session,
    mock_multilingual_db: tuple[Business, Service],
):
    """Verify execute_llm_conversational_turn autonomously processes multi-turn turns in Tanglish."""
    biz, service = mock_multilingual_db
    call_sid = "CS_phase3_llm_tanglish"

    session = ConversationSession(
        call_sid=call_sid,
        business_id=biz.id,
        caller_phone="+919444433333",
        step="greeting",
        language="ta-Latn",
        retry_count=0,
        is_completed=False,
    )
    db_session.add(session)
    db_session.commit()

    llm = MockLLMProvider()

    # Turn 1: Caller asks for service in Tanglish
    reply_1, cont_1 = execute_llm_conversational_turn(
        db=db_session,
        session=session,
        speech_clean="Doctor appointment eppo kidaikum?",
        business=biz,
        llm_provider=llm,
    )
    assert cont_1 is True
    assert session.language == "ta-Latn"
    assert len(reply_1) > 0

    # Turn 2: Caller asks for clinic info
    reply_2, cont_2 = execute_llm_conversational_turn(
        db=db_session,
        session=session,
        speech_clean="Clinic address engirukku?",
        business=biz,
        llm_provider=llm,
    )
    assert cont_2 is True
    assert "address" in reply_2.lower() or biz.name.lower() in reply_2.lower()


def test_phase3_llm_error_graceful_fallback_without_call_drop(
    db_session: Session,
    mock_multilingual_db: tuple[Business, Service],
):
    """Verify when LLM provider throws an exception (401/429/timeout), the turn safely falls back without failing."""
    biz, service = mock_multilingual_db
    call_sid = "CS_phase3_fallback_test"

    session = ConversationSession(
        call_sid=call_sid,
        business_id=biz.id,
        caller_phone="+919111122222",
        step="greeting",
        language="ta-Latn",
        retry_count=0,
        is_completed=False,
    )
    db_session.add(session)
    db_session.commit()

    class FailingLLMProvider(BaseLLMProvider):
        def generate_response(self, *args, **kwargs):
            raise RuntimeError("OpenAI API error 429: Insufficient quota / rate limited")

    failing_llm = FailingLLMProvider()

    # Call process_conversational_turn with failing LLM
    # MUST NOT raise unhandled exception; MUST fall back cleanly to deterministic response
    spoken_reply, should_gather = process_conversational_turn(
        db=db_session,
        session=session,
        speech_text="Cardiology consultation fees evlo?",
        business=biz,
        llm_provider=failing_llm,
    )

    assert should_gather is True
    assert len(spoken_reply) > 0
    # Deterministic pricing fallback responded safely!
    assert "₹" in spoken_reply or "fee" in spoken_reply.lower() or "500" in spoken_reply


def test_phase3_dynamic_llm_conversational_turn_tamil_script(
    db_session: Session,
    mock_multilingual_db: tuple[Business, Service],
):
    """Verify execute_llm_conversational_turn autonomously processes multi-turn booking in native Tamil script."""
    biz, service = mock_multilingual_db
    call_sid = "CS_phase3_llm_tamil_script"

    session = ConversationSession(
        call_sid=call_sid,
        business_id=biz.id,
        caller_phone="+919777788888",
        step="greeting",
        language="ta-IN",
        retry_count=0,
        is_completed=False,
    )
    db_session.add(session)
    db_session.commit()

    llm = MockLLMProvider()

    # Turn 1: Caller requests service in Tamil script
    reply_1, cont_1 = execute_llm_conversational_turn(
        db=db_session,
        session=session,
        speech_clean="வணக்கம் எனக்கு கார்டியாலஜி அப்பாயின்ட்மென்ட் வேண்டும்",
        business=biz,
        llm_provider=llm,
    )
    assert cont_1 is True
    assert session.language == "ta-IN"
    assert "நாள் மற்றும் நேரம்" in reply_1 or "முன்பதிவுக்கு" in reply_1

    # Turn 2: Caller provides date & time in Tamil script
    reply_2, cont_2 = execute_llm_conversational_turn(
        db=db_session,
        session=session,
        speech_clean="நாளை காலை 10 மணிக்கு வேண்டும்",
        business=biz,
        llm_provider=llm,
    )
    assert cont_2 is True
    assert session.language == "ta-IN"
    assert "முழுப் பெயரை" in reply_2

    # Turn 3: Caller gives name -> book_appointment tool executes autonomously
    reply_3, cont_3 = execute_llm_conversational_turn(
        db=db_session,
        session=session,
        speech_clean="என் பெயர் கார்த்திக்",
        business=biz,
        llm_provider=llm,
    )
    assert cont_3 is False
    assert session.is_completed is True
    assert session.booking_id is not None
    assert "நன்றி" in reply_3
    assert "வெற்றிகரமாக" in reply_3 or "வணக்கம்" in reply_3


# ==============================================================================
# 9. Phase 4 - Natural Multilingual Text-to-Speech Implementation Tests
# ==============================================================================


def test_phase4_tts_language_code_resolution():
    """Verify ElevenLabs language_code parameter resolution for Tamil, Tanglish, Telugu, and English."""
    tts = ElevenLabsStreamingTTS(api_key="mock_key")

    assert tts.resolve_language_code("ta-IN") == "ta"
    # Tanglish must pass 'ta' so Latin script is spoken with native Tamil phonetic phonology
    assert tts.resolve_language_code("ta-Latn") == "ta"
    assert tts.resolve_language_code("te-IN") == "te"
    assert tts.resolve_language_code("te-Latn") == "te"
    assert tts.resolve_language_code("en-IN") == "en"
    assert tts.resolve_language_code("en-US") == "en"
    assert tts.resolve_language_code("unknown") is None
    assert tts.resolve_language_code("") is None


def test_phase4_tts_model_resolution_and_upgrade():
    """Verify dynamic model upgrade to eleven_v4_turbo for Telugu (since multilingual_v2 rejects 'te')."""
    tts = ElevenLabsStreamingTTS(api_key="mock_key", model_id="eleven_multilingual_v2")

    # Tamil and English preserve eleven_multilingual_v2
    assert tts.resolve_model_for_language("ta-IN") == "eleven_multilingual_v2"
    assert tts.resolve_model_for_language("ta-Latn") == "eleven_multilingual_v2"
    assert tts.resolve_model_for_language("en-IN") == "eleven_multilingual_v2"

    # Telugu dynamically routes to eleven_v4_turbo to prevent HTTP 400 error
    assert tts.resolve_model_for_language("te-IN") == "eleven_v4_turbo"
    assert tts.resolve_model_for_language("te-Latn") == "eleven_v4_turbo"


def test_phase4_tts_voice_selection_and_environment_overrides():
    """Verify default receptionist voice ID consistency and language-specific overrides."""
    tts = ElevenLabsStreamingTTS(api_key="mock_key", voice_id="EXAVITQu4vr4xnSDxMaL")

    # Default voice (Sarah) used across all languages to ensure voice consistency
    assert tts.get_voice_for_language("ta-IN") == "EXAVITQu4vr4xnSDxMaL"
    assert tts.get_voice_for_language("ta-Latn") == "EXAVITQu4vr4xnSDxMaL"
    assert tts.get_voice_for_language("te-IN") == "EXAVITQu4vr4xnSDxMaL"
    assert tts.get_voice_for_language("en-IN") == "EXAVITQu4vr4xnSDxMaL"

    # With explicit environment overrides
    with patch.object(settings, "ELEVENLABS_VOICE_ID_TA", "custom_tamil_voice_id", create=True):
        with patch.object(settings, "ELEVENLABS_VOICE_ID_TE", "custom_telugu_voice_id", create=True):
            assert tts.get_voice_for_language("ta-IN") == "custom_tamil_voice_id"
            assert tts.get_voice_for_language("ta-Latn") == "custom_tamil_voice_id"
            assert tts.get_voice_for_language("te-IN") == "custom_telugu_voice_id"
            assert tts.get_voice_for_language("en-IN") == "EXAVITQu4vr4xnSDxMaL"


def test_phase4_tts_synthesis_mulaw_and_frame_chunking():
    """Verify ElevenLabs produces ITU-T G.711 8kHz mu-law audio divided into 20ms 160-byte frames."""
    tts = ElevenLabsStreamingTTS(api_key="mock_key", voice_id="EXAVITQu4vr4xnSDxMaL")

    # 800 bytes of mu-law = 5 frames of 160 bytes = 100ms
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = bytes([128] * 800)

    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        chunks = tts.synthesize_stream_chunks(
            text="வணக்கம்! உங்கள் அப்பாயின்ட்மென்ட் முன்பதிவு செய்யப்பட்டுள்ளது.",
            language="ta-IN",
            chunk_size=160,
        )

        assert len(chunks) == 5
        assert all(len(c) == 160 for c in chunks)

        call_url, kwargs = mock_post.call_args[0][0], mock_post.call_args[1]
        assert "EXAVITQu4vr4xnSDxMaL/stream" in call_url
        assert kwargs["params"]["output_format"] == "ulaw_8000"
        assert kwargs["params"]["optimize_streaming_latency"] == 3
        assert kwargs["json"]["language_code"] == "ta"
        assert kwargs["json"]["model_id"] == "eleven_multilingual_v2"
        assert kwargs["json"]["voice_settings"]["use_speaker_boost"] is True


def test_phase4_tts_tanglish_synthesis_payload():
    """Verify Tanglish requests pass language_code='ta' for authentic phonetic delivery."""
    tts = ElevenLabsStreamingTTS(api_key="mock_key", voice_id="EXAVITQu4vr4xnSDxMaL")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = bytes([128] * 320)  # 2 frames

    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        chunks = tts.synthesize_stream_chunks(
            text="Doctor appointment eppo kidaikum?",
            language="ta-Latn",
            chunk_size=160,
        )

        assert len(chunks) == 2
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["language_code"] == "ta"
        assert kwargs["json"]["model_id"] == "eleven_multilingual_v2"
        assert kwargs["params"]["output_format"] == "ulaw_8000"


def test_phase4_tts_error_and_fallback_resilience():
    """Verify graceful handling when ElevenLabs encounters API errors or missing credentials."""
    # Case 1: Missing API key
    tts_no_key = ElevenLabsStreamingTTS(api_key="")
    assert tts_no_key.synthesize_to_mulaw("Hello") == b""

    # Case 2: Empty text
    tts = ElevenLabsStreamingTTS(api_key="valid_key")
    assert tts.synthesize_to_mulaw("") == b""
    assert tts.synthesize_to_mulaw("   ") == b""

    # Case 3: API error in production environment returns empty bytes (zero call drops)
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"

    with patch.object(settings, "ENVIRONMENT", "production"):
        with patch("httpx.Client.post", return_value=mock_resp):
            result = tts.synthesize_to_mulaw("Test speech", language="en-IN")
            assert result == b""

    # Case 4: Factory provider selection
    provider = get_streaming_tts_provider("mock")
    assert isinstance(provider, MockStreamingTTS)
    assert provider.provider_name == "mock"




