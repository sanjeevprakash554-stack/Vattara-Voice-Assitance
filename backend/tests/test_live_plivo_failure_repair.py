import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import settings
from app.services.ai.gemini_provider import GeminiLLMProvider
from app.services.streaming.sarvam_tts import (
    SarvamRestFallbackTTS,
    SarvamStreamingTTS,
)
from app.services.streaming.session_manager import (
    AudioStreamSession,
    StreamConnectionManager,
)


def test_fallback_tts_reporting_and_sarvam_rest():
    """Verify stream reports fallback_tts=sarvam_rest in non-test environment and uses Sarvam REST."""
    tts = SarvamStreamingTTS(api_key="mock_key_123")
    with patch.object(tts, "_is_mock_test_mode", return_value=False):
        fallback = tts.get_fallback_provider()
        assert isinstance(fallback, SarvamRestFallbackTTS)
        assert fallback.provider_name == "sarvam_rest"

    # In mock test mode, fallback is MockStreamingTTS for zero-cost offline tests
    with patch.object(tts, "_is_mock_test_mode", return_value=True):
        fallback_test = tts.get_fallback_provider()
        assert fallback_test.provider_name == "mock"


def test_turn_in_progress_preserved_by_reset_turn_buffer():
    """Verify session.reset_turn_buffer does NOT prematurely drop turn_in_progress to False."""
    session = AudioStreamSession(
        stream_sid="MZ_test_001",
        call_sid="CA_test_001",
        business_id="b1",
        caller_phone="+919876543210",
    )
    session.turn_in_progress = True
    session.inbound_pcm16_buffer.extend(b"\x00\x00" * 100)
    session.consecutive_speech_frames = 10
    session.consecutive_silence_frames = 5
    session.is_caller_speaking = True

    # Reset buffer for upcoming turn
    session.reset_turn_buffer()

    # Buffers and speech counters reset
    assert len(session.inbound_pcm16_buffer) == 0
    assert session.consecutive_speech_frames == 0
    assert session.consecutive_silence_frames == 0
    assert session.is_caller_speaking is False
    # CRITICAL: turn_in_progress remains True until turn lifecycle completes
    assert session.turn_in_progress is True


def test_stream_manager_unregister_sets_websocket_closed_reason():
    """Verify unregister sets playback_cancellation_reason='websocket_closed' before cancelling task."""
    mgr = StreamConnectionManager()
    session = AudioStreamSession(
        stream_sid="MZ_test_002",
        call_sid="CA_test_002",
        business_id="b1",
        caller_phone="+919876543210",
    )
    ws = MagicMock()
    mgr._connections["MZ_test_002"] = ws
    mgr._sessions["MZ_test_002"] = session
    mgr._call_map[session.call_sid] = "MZ_test_002"

    mock_playback = MagicMock()
    mock_playback.done.return_value = False
    session.current_playback_task = mock_playback

    # Run unregister coroutine
    coro = mgr.unregister("MZ_test_002")
    try:
        coro.send(None)
    except StopIteration as e:
        returned_session = e.value

    assert returned_session is session
    assert session.playback_cancellation_reason == "websocket_closed"
    mock_playback.cancel.assert_called_once()


def test_gemini_timeouts_extended_for_tamil_support():
    """Verify GeminiProvider timeout configuration gives sufficient budget for Tamil generation."""
    provider = GeminiLLMProvider(api_key="mock_key_gemini")
    assert provider.api_key == "mock_key_gemini"

    # Inspect generate_response code / timeouts via dummy request setup
    # In generate_response, overall_timeout is 7.0s and read timeout is min(4.5, remaining)
    from unittest.mock import MagicMock
    mock_client = MagicMock()
    mock_client.post.return_value = MagicMock(status_code=200, json=lambda: {
        "candidates": [{"content": {"parts": [{"text": "வணக்கம்"}]}}]
    })
    provider._sync_client = mock_client

    from app.services.ai.base import LLMMessage
    resp = provider.generate_response(
        messages=[LLMMessage(role="user", content="வணக்கம்")],
        system_prompt="receptionist",
        active_services=[],
        available_tools=[],
    )
    assert resp.text == "வணக்கம்"
    # Check timeout passed to httpx client
    call_kwargs = mock_client.post.call_args.kwargs
    req_timeout = call_kwargs["timeout"]
    assert req_timeout.read >= 4.0
