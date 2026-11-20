"""Master Automated Test Suite for Natural, Consistent, Low-Latency AI Voice Receptionist.

Covers:
A. Voice consistency (Tamil speaker, English speaker, Telugu speaker, persistent across turns).
B. Language detection & explicit switching (Telugu, Tamil, English, Tanglish, short words immunity).
C. Conversational context & recovery handling ('Hello?', 'Are you there?', 'Can you hear me?', 'Wait').
D. Silence management state machine (prompts at thresholds, caller resuming, no premature termination).
E. Telephony audio synchronization (text language matches TTS language, no Telugu with English voice).
F. Barge-in & low-latency cancellation.
G. Fallback to ElevenLabs and Mock TTS without voice corruption.
"""

import asyncio
from datetime import datetime, timezone
import json
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.core.config import settings
from app.models.business import Business
from app.models.call import Call
from app.models.conversation_session import ConversationSession
from app.services.ai.language_detector import detect_language
from app.services.streaming.audio_codec import chunk_audio
from app.services.streaming.session_manager import AudioStreamSession, stream_manager
from app.services.streaming.stream_orchestrator import StreamOrchestrator
from app.services.streaming.voice_registry import (
    detect_script_language_from_text,
    get_voice_for_language,
    resolve_canonical_language,
    synchronize_voice_and_language,
)
from app.services.voice_assistant_service import process_conversational_turn


# ---------------------------------------------------------------------------
# Section A: Voice Consistency & Identity
# ---------------------------------------------------------------------------

def test_a1_consistent_speaker_mapping_per_language():
    """Verify one consistent assistant voice per configured language for Sarvam AI."""
    # Tamil
    spk_ta1 = get_voice_for_language("ta-IN", provider="sarvam")
    spk_ta2 = get_voice_for_language("ta-IN", provider="sarvam")
    spk_tanglish = get_voice_for_language("ta-Latn", provider="sarvam")
    assert spk_ta1 == "gokul_ta_narration"
    assert spk_ta1 == spk_ta2 == spk_tanglish

    # English
    spk_en1 = get_voice_for_language("en-IN", provider="sarvam")
    spk_en2 = get_voice_for_language("en-IN", provider="sarvam")
    assert spk_en1 == "ishita_en_customer"
    assert spk_en1 == spk_en2

    # Telugu
    spk_te1 = get_voice_for_language("te-IN", provider="sarvam")
    spk_te2 = get_voice_for_language("te-IN", provider="sarvam")
    spk_teluglish = get_voice_for_language("te-Latn", provider="sarvam")
    assert spk_te1 == "kavitha_te_conversation"
    assert spk_te1 == spk_te2 == spk_teluglish


def test_a2_elevenlabs_fallback_voice_consistency():
    """Verify ElevenLabs fallback maintains consistent voice identifiers per language."""
    v_ta = get_voice_for_language("ta-IN", provider="elevenlabs")
    v_en = get_voice_for_language("en-IN", provider="elevenlabs")
    v_te = get_voice_for_language("te-IN", provider="elevenlabs")
    assert v_ta and len(v_ta) > 5
    assert v_en and len(v_en) > 5
    assert v_te and len(v_te) > 5


def test_a3_session_voice_identity_persistence():
    """Verify AudioStreamSession stores and reuses selected speaker throughout the call."""
    session = AudioStreamSession(
        stream_sid="stream_test_voice_1",
        call_sid="call_test_voice_1",
        business_id="biz_1",
        caller_phone="+919876543210",
        language="ta-IN",
        provider="plivo",
        tts_provider="sarvam",
    )
    assert session.active_tts_language == "ta-IN"
    assert session.active_tts_speaker == "gokul_ta_narration"

    # Turn 1 in Tamil: voice remains gokul_ta_narration
    resp_l, tts_l, spk = session.update_voice_state("வணக்கம்! உங்களுக்கு எப்படி உதவலாம்?")
    assert resp_l == "ta-IN"
    assert tts_l == "ta-IN"
    assert spk == "gokul_ta_narration"
    assert session.active_tts_speaker == "gokul_ta_narration"

    # Turn 2 in Tamil: voice remains gokul_ta_narration
    resp_l2, tts_l2, spk2 = session.update_voice_state("நாளை காலை 10 மணிக்கு அப்பாயின்ட்மென்ட் உள்ளது.")
    assert resp_l2 == "ta-IN"
    assert spk2 == "gokul_ta_narration"


# ---------------------------------------------------------------------------
# Section B: Language Detection & Explicit Switching
# ---------------------------------------------------------------------------

def test_b1_explicit_language_switch_telugu():
    """Verify explicit requests for Telugu switch language to te-IN immediately."""
    assert detect_language("Can you speak in Telugu?") == "te-IN"
    assert detect_language("Can you speak Telugu?") == "te-IN"
    assert detect_language("Speak in Telugu please") == "te-IN"
    assert detect_language("Telugu lo matladandi") == "te-IN"
    assert detect_language("Switch to Telugu") == "te-IN"
    assert detect_language("తెలుగులో మాట్లాడండి") == "te-IN"


def test_b2_explicit_language_switch_tamil():
    """Verify explicit requests for Tamil switch language to ta-IN immediately."""
    assert detect_language("Can you speak in Tamil?") == "ta-IN"
    assert detect_language("Speak Tamil please") == "ta-IN"
    assert detect_language("Tamil-la pesunga") == "ta-IN"
    assert detect_language("Switch to Tamil") == "ta-IN"
    assert detect_language("தமிழில் பேசவும்") == "ta-IN"


def test_b3_explicit_language_switch_english():
    """Verify explicit requests for English switch language to en-IN immediately."""
    assert detect_language("Can you speak in English?", current_lang="ta-IN") == "en-IN"
    assert detect_language("Switch to English", current_lang="te-IN") == "en-IN"
    assert detect_language("English please", current_lang="ta-IN") == "en-IN"


def test_b4_short_words_never_change_language():
    """Verify short words ('Hello', 'Okay', 'Yes', 'No') do NOT switch language away from established preference."""
    # Tamil session
    assert detect_language("Hello", current_lang="ta-IN") == "ta-IN"
    assert detect_language("Hello?", current_lang="ta-IN") == "ta-IN"
    assert detect_language("Okay", current_lang="ta-IN") == "ta-IN"
    assert detect_language("Yes", current_lang="ta-IN") == "ta-IN"
    assert detect_language("Are you there?", current_lang="ta-IN") == "ta-IN"
    assert detect_language("Can you hear me?", current_lang="ta-IN") == "ta-IN"

    # Telugu session
    assert detect_language("Hello", current_lang="te-IN") == "te-IN"
    assert detect_language("Hello?", current_lang="te-IN") == "te-IN"
    assert detect_language("Okay", current_lang="te-IN") == "te-IN"
    assert detect_language("Are you there?", current_lang="te-IN") == "te-IN"


def test_b5_telugu_text_never_sent_with_english_voice():
    """Verify Telugu response text is never sent with an English TTS language or speaker."""
    session = AudioStreamSession(
        stream_sid="stream_test_sync_1",
        call_sid="call_test_sync_1",
        business_id="biz_1",
        caller_phone="+919876543210",
        language="en-IN",  # Session was in English
        provider="plivo",
        tts_provider="sarvam",
    )
    # Caller asks for Telugu, AI generates Telugu response
    telugu_reply = "అవును, నేను తెలుగులో మాట్లాడగలను. మీకు ఎలా సహాయపడగలను?"
    resp_l, tts_l, spk = session.update_voice_state(telugu_reply)

    assert resp_l == "te-IN"
    assert tts_l == "te-IN"
    assert spk == "kavitha_te_conversation"
    assert spk != "ishita_en_customer"  # NEVER English speaker


def test_b6_tamil_text_never_sent_with_english_voice():
    """Verify Tamil response text is never sent with an English TTS language or speaker."""
    session = AudioStreamSession(
        stream_sid="stream_test_sync_2",
        call_sid="call_test_sync_2",
        business_id="biz_1",
        caller_phone="+919876543210",
        language="en-IN",
        provider="plivo",
        tts_provider="sarvam",
    )
    tamil_reply = "வணக்கம்! எங்கள் மருத்துவமனைக்கு வரவேற்கிறோம்."
    resp_l, tts_l, spk = session.update_voice_state(tamil_reply)

    assert resp_l == "ta-IN"
    assert tts_l == "ta-IN"
    assert spk == "gokul_ta_narration"


# ---------------------------------------------------------------------------
# Section C: Conversation Context & Dedicated Recovery
# ---------------------------------------------------------------------------

def test_c1_recovery_handling_hello_again():
    """Verify that saying 'Hello?' mid-conversation recovers naturally without restarting the call."""
    mock_db = MagicMock()
    mock_biz = MagicMock(spec=Business)
    mock_biz.id = "biz_1"
    mock_biz.name = "Vattara Health"
    mock_biz.assistant_config = None

    session = ConversationSession(
        call_sid="call_rec_1",
        business_id="biz_1",
        caller_phone="+919876543210",
        step="awaiting_datetime",
        service_id="srv_cardio",
        service_name="Cardiology Consultation",
        language="en-IN",
        dialog_history=json.dumps([
            {"role": "caller", "text": "I need a cardiology checkup"},
            {"role": "assistant", "text": "Sure, which date would you prefer?"},
        ]),
        retry_count=0,
        is_completed=False,
    )

    prompt, should_gather = process_conversational_turn(
        db=mock_db,
        session=session,
        speech_text="Hello?",
        business=mock_biz,
    )

    assert should_gather is True
    assert "right here" in prompt.lower() or "listening" in prompt.lower()
    # Must NOT restart initial welcome
    assert "welcome to" not in prompt.lower()
    assert session.is_completed is False


def test_c2_recovery_handling_can_you_hear_me():
    """Verify 'Can you hear me?' confirms presence and does not break context."""
    mock_db = MagicMock()
    mock_biz = MagicMock(spec=Business)
    mock_biz.id = "biz_1"
    mock_biz.name = "Vattara Health"
    mock_biz.assistant_config = None

    session = ConversationSession(
        call_sid="call_rec_2",
        business_id="biz_1",
        caller_phone="+919876543210",
        step="awaiting_name",
        language="ta-IN",
        dialog_history=json.dumps([
            {"role": "caller", "text": "டாக்டர் அப்பாயின்ட்மென்ட் வேண்டும்"},
            {"role": "assistant", "text": "உங்கள் பெயரை கூறவும்."},
        ]),
        retry_count=0,
        is_completed=False,
    )

    prompt, should_gather = process_conversational_turn(
        db=mock_db,
        session=session,
        speech_text="Can you hear me?",
        business=mock_biz,
    )

    assert should_gather is True
    # Tamil presence confirmation
    assert "லைனில்" in prompt or "கேட்கிறது" in prompt or "தொடருங்கள்" in prompt
    assert session.language == "ta-IN"  # Language maintained!


def test_c3_recovery_handling_hold_request():
    """Verify 'One minute' or 'Wait' triggers a patient waiting response."""
    mock_db = MagicMock()
    mock_biz = MagicMock(spec=Business)
    mock_biz.id = "biz_1"
    mock_biz.name = "Vattara Health"
    mock_biz.assistant_config = None

    session = ConversationSession(
        call_sid="call_rec_3",
        business_id="biz_1",
        caller_phone="+919876543210",
        step="awaiting_datetime",
        language="en-IN",
        dialog_history=json.dumps([]),
        retry_count=0,
        is_completed=False,
    )

    prompt, should_gather = process_conversational_turn(
        db=mock_db,
        session=session,
        speech_text="One minute please, let me check my calendar",
        business=mock_biz,
    )

    assert should_gather is True
    assert "take your time" in prompt.lower() or "right here" in prompt.lower()


# ---------------------------------------------------------------------------
# Section D: Silence Management State Machine
# ---------------------------------------------------------------------------

def test_d1_inactivity_prompt_generation():
    """Verify localized silence check-in prompts for English, Tamil, and Telugu."""
    # Stage 1 prompts
    p1_en = StreamOrchestrator._build_inactivity_prompt("en-IN", stage=1)
    p1_ta = StreamOrchestrator._build_inactivity_prompt("ta-IN", stage=1)
    p1_te = StreamOrchestrator._build_inactivity_prompt("te-IN", stage=1)
    assert "still there" in p1_en.lower()
    assert "லைனில் இருக்கிறீர்களா" in p1_ta
    assert "లైన్‌లో ఉన్నారా" in p1_te

    # Stage 2 prompts
    p2_en = StreamOrchestrator._build_inactivity_prompt("en-IN", stage=2)
    p2_ta = StreamOrchestrator._build_inactivity_prompt("ta-IN", stage=2)
    p2_te = StreamOrchestrator._build_inactivity_prompt("te-IN", stage=2)
    assert len(p2_en) > 10
    assert len(p2_ta) > 10
    assert len(p2_te) > 10

    # Stage 3 final prompts
    p3_en = StreamOrchestrator._build_inactivity_prompt("en-IN", stage=3)
    p3_ta = StreamOrchestrator._build_inactivity_prompt("ta-IN", stage=3)
    p3_te = StreamOrchestrator._build_inactivity_prompt("te-IN", stage=3)
    assert "goodbye" in p3_en.lower() or "thank you" in p3_en.lower()
    assert "வணக்கம்" in p3_ta
    assert "నమస్కారం" in p3_te


def test_d2_inactivity_watchdog_resets_on_caller_speech():
    """Verify that caller speech immediately resets inactivity prompt counters."""
    async def _run():
        session = AudioStreamSession(
            stream_sid="stream_inact_1",
            call_sid="call_inact_1",
            business_id="biz_1",
            caller_phone="+919876543210",
            language="en-IN",
            provider="plivo",
        )
        session.inactivity_prompts_sent = 2
        session.last_speech_or_playback_at = time.time() - 20.0

        # Simulate caller speaking (speech detected or barge-in triggered)
        session.trigger_barge_in()
        assert session.inactivity_prompts_sent == 0
        assert time.time() - session.last_speech_or_playback_at < 1.0

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Section E: Telephony Audio Framing & Protocol
# ---------------------------------------------------------------------------

def test_e1_plivo_play_audio_formatting():
    """Verify outbound audio frames adhere strictly to Plivo JSON playAudio protocol."""
    async def _run():
        mock_ws = AsyncMock()
        session = AudioStreamSession(
            stream_sid="plivo_stream_test_1",
            call_sid="plivo_call_test_1",
            business_id="biz_1",
            caller_phone="+919876543210",
            provider="plivo",
        )
        await stream_manager.register("plivo_stream_test_1", mock_ws, session)

        # 160 bytes of valid mu-law audio
        test_frame = bytes([128] * 160)
        sent = await stream_manager.send_media("plivo_stream_test_1", test_frame)
        assert sent is True
        assert mock_ws.send_text.called

        call_args = mock_ws.send_text.call_args[0][0]
        event = json.loads(call_args)
        assert event["event"] == "playAudio"
        assert event["media"]["contentType"] == "audio/x-mulaw"
        assert event["media"]["sampleRate"] == 8000
        assert len(event["media"]["payload"]) > 0

        await stream_manager.unregister("plivo_stream_test_1")

    asyncio.run(_run())


def test_e2_barge_in_clears_telephony_audio():
    """Verify caller barge-in issues clearAudio event to Plivo WebSocket."""
    async def _run():
        mock_ws = AsyncMock()
        session = AudioStreamSession(
            stream_sid="plivo_stream_test_2",
            call_sid="plivo_call_test_2",
            business_id="biz_1",
            caller_phone="+919876543210",
            provider="plivo",
        )
        await stream_manager.register("plivo_stream_test_2", mock_ws, session)

        session.is_assistant_speaking = True
        session.trigger_barge_in()
        await stream_manager.send_clear("plivo_stream_test_2")

        assert mock_ws.send_text.called
        clear_msg = json.loads(mock_ws.send_text.call_args[0][0])
        assert clear_msg["event"] == "clearAudio"
        assert clear_msg["streamId"] == "plivo_stream_test_2"

        await stream_manager.unregister("plivo_stream_test_2")

    asyncio.run(_run())
