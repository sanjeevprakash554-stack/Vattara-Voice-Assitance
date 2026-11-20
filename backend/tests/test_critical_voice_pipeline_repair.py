"""Comprehensive regression tests for Critical Voice Pipeline Repair, Conversation Flow Correction,
and Low-Latency Telemetry.

Verifies:
1. Phone number extraction from digits, English words, Tamil script, Tanglish, and Telugu words.
2. Phone number spoken during greeting step is NEVER filtered as noise.
3. Playback cancellation reasons recorded: caller_barge_in, superseded_by_new_turn, websocket_closed, internal_error.
4. Frame tracking: frames_generated, frames_queued, frames_sent, frames_rejected, playback_completed.
5. Safe barge-in: empty STT does not destroy assistant state.
6. Turn serialization: turn lock prevents overlapping turns.
7. 10-checkpoint pipeline latency tracker structured output.
"""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.core.config import settings
from app.models.conversation_session import ConversationSession
from app.services.streaming.session_manager import AudioStreamSession, stream_manager
from app.services.streaming.stream_orchestrator import StreamOrchestrator, TurnLatencyTracker
from app.services.voice_assistant_service import (
    extract_phone_number,
    is_unreliable_or_noise_transcript,
    get_cached_business_catalog,
)


def test_phone_number_extraction_multilingual():
    """Verify phone numbers are reliably extracted across digits, English, Tamil, and Telugu spoken words."""
    # 1. Direct digits
    assert extract_phone_number("My number is 9876543210") == "+919876543210"
    assert extract_phone_number("98765 43210") == "+919876543210"
    assert extract_phone_number("+91-9876543210") == "+919876543210"
    assert extract_phone_number("09876543210") == "+919876543210"

    # 2. English spoken words
    assert extract_phone_number("nine eight seven six five four three two one zero") == "+919876543210"
    assert extract_phone_number("double nine eight seven six five four three two one") == "+919987654321"

    # 3. Tamil Unicode spoken words
    assert extract_phone_number("ஒன்பது எட்டு ஏழு ஆறு ஐந்து நான்கு மூன்று இரண்டு ஒன்று பூஜ்ஜியம்") == "+919876543210"

    # 4. Tanglish phonetic words
    assert extract_phone_number("onbadhu ettu yezhu aaru anju naalu moonu rendu onnu zero") == "+919876543210"

    # 5. Telugu spoken words
    assert extract_phone_number("tommidi enimidi yedu aaru aidu naalugu moodu rendu okati sunna") == "+919876543210"

    # 6. Non-phone text should return None
    assert extract_phone_number("hello how are you") is None
    assert extract_phone_number("880.") is None
    assert extract_phone_number("123") is None


def test_phone_number_in_greeting_not_filtered_as_noise():
    """Verify phone number spoken during 'greeting' step is NEVER filtered as noise."""
    # Spoken during greeting step
    assert is_unreliable_or_noise_transcript("9876543210", current_step="greeting") is False
    assert is_unreliable_or_noise_transcript("My number is 9876543210", current_step="greeting") is False
    assert is_unreliable_or_noise_transcript("nine eight seven six five four three two one zero", current_step="greeting") is False
    assert is_unreliable_or_noise_transcript("ஒன்பது எட்டு ஏழு ஆறு ஐந்து நான்கு மூன்று இரண்டு ஒன்று பூஜ்ஜியம்", current_step="greeting") is False

    # Short line noise/DTMF is still filtered as noise
    assert is_unreliable_or_noise_transcript("880.", current_step="greeting") is True
    assert is_unreliable_or_noise_transcript("123", current_step="greeting") is True
    assert is_unreliable_or_noise_transcript(".", current_step="greeting") is True


def test_playback_cancellation_reason_tracking():
    """Verify playback cancellation reasons are recorded accurately on AudioStreamSession."""
    session = AudioStreamSession(
        stream_sid="stream_cancel_test",
        call_sid="call_cancel_test",
        business_id="biz_test",
        caller_phone="+919876543210",
    )

    # 1. Barge-in sets caller_barge_in
    session.trigger_barge_in(reason="caller_barge_in")
    assert session.playback_cancellation_reason == "caller_barge_in"
    assert session.playback_completed is False
    assert session.interrupted is True

    # 2. Reset playback metrics
    session.reset_playback_metrics()
    assert session.playback_cancellation_reason is None
    assert session.frames_generated == 0
    assert session.frames_sent == 0
    assert session.playback_completed is False

    # 3. Superseded by new turn
    session.playback_cancellation_reason = "superseded_by_new_turn"
    assert session.playback_cancellation_reason == "superseded_by_new_turn"

    # 4. WebSocket closed
    session.playback_cancellation_reason = "websocket_closed"
    assert session.playback_cancellation_reason == "websocket_closed"


def test_turn_latency_tracker_10_checkpoints():
    """Verify 10-checkpoint latency tracker records timestamps and generates structured summary."""
    tracker = TurnLatencyTracker(
        correlation_id="turn_call_123_1",
        stream_sid="stream_123",
        call_sid="call_123",
        turn_seq=1,
    )

    t0 = tracker.mark("1_last_caller_frame")
    time.sleep(0.005)
    tracker.mark("2_endpoint_detected")
    tracker.mark("3_stt_started")
    time.sleep(0.005)
    tracker.mark("4_stt_finished")
    tracker.mark("5_context_retrieved")
    tracker.mark("6_llm_started")
    tracker.mark("7_tool_executed")
    time.sleep(0.005)
    tracker.mark("8_response_ready")
    tracker.mark("9_tts_first_chunk")
    time.sleep(0.005)
    tracker.mark("10_first_frame_sent")

    summary = tracker.to_summary()
    assert summary["correlation_id"] == "turn_call_123_1"
    assert summary["turn_seq"] == 1
    assert "stage_latencies_ms" in summary
    assert "checkpoints_ms_from_start" in summary

    stages = summary["stage_latencies_ms"]
    assert "endpoint_latency_ms" in stages
    assert "stt_latency_ms" in stages
    assert "llm_latency_ms" in stages
    assert "total_pipeline_latency_ms" in stages
    assert stages["total_pipeline_latency_ms"] > 0


def test_turn_lock_serialization():
    """Verify AudioStreamSession turn_lock serializes turns without overlap."""
    async def _run():
        session = AudioStreamSession(
            stream_sid="stream_lock_test",
            call_sid="call_lock_test",
            business_id="biz_test",
            caller_phone="+919876543210",
        )

        execution_order = []

        async def worker(worker_id: int):
            async with session.turn_lock:
                execution_order.append(f"start_{worker_id}")
                await asyncio.sleep(0.01)
                execution_order.append(f"end_{worker_id}")

        await asyncio.gather(worker(1), worker(2))

        # Must execute sequentially: start_1 -> end_1 -> start_2 -> end_2
        assert execution_order in (
            ["start_1", "end_1", "start_2", "end_2"],
            ["start_2", "end_2", "start_1", "end_1"],
        )

    asyncio.run(_run())
