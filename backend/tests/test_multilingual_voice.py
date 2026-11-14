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
from app.services.ai.language_detector import (
    detect_language,
    get_display_language_name,
    is_tamil_script,
    is_telugu_script,
)
from app.services.ai.prompts import build_system_prompt
from app.services.streaming.stt_provider import DeepgramStreamingSTT, WhisperStreamingSTT
from app.services.streaming.stream_orchestrator import StreamOrchestrator
from app.services.streaming.tts_provider import ElevenLabsStreamingTTS
from app.services.voice_assistant_service import (
    detect_intent,
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
        assert kwargs["json"]["model_id"] == "eleven_multilingual_v2"
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
    db_session.add(cfg)
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
    assert session.language == "te-IN"
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
    assert session.language == "te-IN"
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
