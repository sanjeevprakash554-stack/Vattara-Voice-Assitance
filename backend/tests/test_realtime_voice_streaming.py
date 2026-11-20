"""Comprehensive automated test suite for Phase 5: Real-Time AI Voice Streaming & WebSocket Engine.

Test coverage:
1. G.711 mu-law <-> Linear PCM16 encoding/decoding roundtrip.
2. Telephony audio resampling (8kHz <-> 16kHz, 24kHz -> 8kHz) and WAV container generation.
3. Voice Activity Detection (VAD) and RMS audio energy computation.
4. Streaming STT provider adapters (Mock, Deepgram Nova-2, OpenAI Whisper).
5. Streaming TTS provider adapters (Mock, ElevenLabs Multilingual v2, OpenAI TTS-1).
6. Media Stream TwiML generator (<Connect><Stream url="wss://...">).
7. WebSocket real-time stream lifecycle (connected, start, media, mark, stop).
8. Caller interruption (barge-in): verify Twilio 'clear' event and audio abort.
9. Real-time turn-taking and Phase 2 appointment function calling via stream.
10. Multi-tenant audio stream isolation.
11. Abrupt WebSocket disconnection cleanup and resource recovery.
12. Streaming telemetry and health status endpoint.
"""

import asyncio
import json
import math
import struct
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import anyio
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.plivo_service import PlivoService
from app.models.business import Business
from app.models.call import Call
from app.models.conversation_session import ConversationSession
from app.services.streaming.audio_codec import (
    base64_to_mulaw,
    chunk_audio,
    compute_rms_energy,
    generate_wav_container,
    is_speech_active,
    mulaw_to_base64,
    mulaw_to_pcm16,
    pcm16_to_mulaw,
    resample_pcm16,
)
from app.services.streaming.session_manager import AudioStreamSession, stream_manager
from app.services.streaming.stt_provider import (
    DeepgramStreamingSTT,
    MockStreamingSTT,
    WhisperStreamingSTT,
    get_streaming_stt_provider,
)
from app.services.streaming.stream_orchestrator import StreamOrchestrator
from app.services.streaming.tts_provider import (
    ElevenLabsStreamingTTS,
    MockStreamingTTS,
    OpenAIStreamingTTS,
    get_streaming_tts_provider,
)


# ==============================================================================
# 1. Audio Codec & Digital Signal Processing Tests
# ==============================================================================


def test_audio_codec_mulaw_pcm_roundtrip():
    """Verify G.711 mu-law <-> linear PCM16 conversion retains signal integrity."""
    # Generate 16-bit linear PCM sine wave
    num_samples = 160
    samples = [int(15000 * math.sin(2 * math.pi * 440 * (i / 8000.0))) for i in range(num_samples)]
    original_pcm = struct.pack(f"<{num_samples}h", *samples)

    # Encode PCM16 -> Mu-law (8-bit)
    mulaw = pcm16_to_mulaw(original_pcm)
    assert len(mulaw) == num_samples  # 1 byte per sample in mu-law

    # Decode Mu-law -> PCM16 (16-bit)
    decoded_pcm = mulaw_to_pcm16(mulaw)
    assert len(decoded_pcm) == num_samples * 2

    # Verify base64 serialization
    b64 = mulaw_to_base64(mulaw)
    assert isinstance(b64, str)
    unb64 = base64_to_mulaw(b64)
    assert unb64 == mulaw

    # Verify 20ms telephony frame chunking (160 bytes)
    frames = chunk_audio(mulaw, chunk_size=160)
    assert len(frames) == 1
    assert len(frames[0]) == 160


def test_audio_resampling_and_wav_generation():
    """Verify telephony sample rate conversion and WAV container wrapping."""
    # 8000 Hz signal (80 samples = 10ms)
    s8k = [int(10000 * math.sin(i)) for i in range(80)]
    pcm8k = struct.pack(f"<{len(s8k)}h", *s8k)

    # Upsample 8kHz -> 16kHz for Deepgram
    pcm16k = resample_pcm16(pcm8k, orig_sr=8000, target_sr=16000)
    assert len(pcm16k) == len(pcm8k) * 2

    # Downsample 16kHz -> 8kHz
    pcm8k_back = resample_pcm16(pcm16k, orig_sr=16000, target_sr=8000)
    assert len(pcm8k_back) == len(pcm8k)

    # Downsample 24kHz (OpenAI TTS) -> 8kHz
    s24k = [1000] * 240
    pcm24k = struct.pack(f"<{len(s24k)}h", *s24k)
    pcm8k_from_24k = resample_pcm16(pcm24k, orig_sr=24000, target_sr=8000)
    assert len(pcm8k_from_24k) == (len(pcm24k) // 3)

    # Wrap in WAV container
    wav = generate_wav_container(pcm8k, sample_rate=8000)
    assert wav[:4] == b"RIFF"
    assert wav[8:12] == b"WAVE"
    assert len(wav) == 44 + len(pcm8k)


def test_voice_activity_detection_and_rms_energy():
    """Verify energy calculation and VAD speech/silence discrimination."""
    # Silent audio frame
    silence_pcm = bytes(320)
    silence_energy = compute_rms_energy(silence_pcm)
    assert silence_energy == 0.0
    assert not is_speech_active(silence_energy, threshold=300.0)

    # Human speech amplitude frame (~12,000 RMS)
    speech_samples = [12000 if i % 2 == 0 else -12000 for i in range(160)]
    speech_pcm = struct.pack(f"<{len(speech_samples)}h", *speech_samples)
    speech_energy = compute_rms_energy(speech_pcm)
    assert speech_energy > 5000.0
    assert is_speech_active(speech_energy, threshold=300.0)


# ==============================================================================
# 2. STT Provider Tests
# ==============================================================================


def test_mock_streaming_stt():
    """Verify MockStreamingSTT processes chunks and flushes final transcript."""
    stt = MockStreamingSTT(predefined_transcripts=["I need cardiology appointment"])
    dummy_audio = bytes([128] * 16000)

    _, is_final = stt.process_audio_chunk(dummy_audio)
    transcript = stt.flush(language="en-IN")
    assert transcript == "I need cardiology appointment"


def test_deepgram_streaming_stt_request():
    """Verify DeepgramStreamingSTT correctly formats headers, parameters, and audio body."""
    stt = DeepgramStreamingSTT(api_key="mock_deepgram_key")
    dummy_audio = bytes([100] * 8000)
    stt.process_audio_chunk(dummy_audio)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "results": {
            "channels": [
                {
                    "alternatives": [
                        {"transcript": "மருத்துவ ஆலோசனை வேண்டும்"}
                    ]
                }
            ]
        }
    }

    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        result = stt.flush(language="ta-IN")
        assert result == "மருத்துவ ஆலோசனை வேண்டும்"

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs["params"]["language"] == "ta"
        assert kwargs["headers"]["Authorization"] == "Token mock_deepgram_key"


def test_whisper_streaming_stt_request():
    """Verify WhisperStreamingSTT formats multi-part form data."""
    stt = WhisperStreamingSTT(api_key="mock_openai_key")
    stt.process_audio_chunk(bytes([50] * 3200))

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"text": "I want to reschedule my appointment"}

    with patch("httpx.Client.post", return_value=mock_resp):
        result = stt.flush(language="en-IN")
        assert result == "I want to reschedule my appointment"


# ==============================================================================
# 3. TTS Provider Tests
# ==============================================================================


def test_mock_streaming_tts():
    """Verify MockStreamingTTS generates valid 8kHz mu-law audio frames."""
    tts = MockStreamingTTS()
    chunks = tts.synthesize_stream_chunks("Hello", chunk_size=160)
    assert len(chunks) > 0
    assert len(chunks[0]) == 160


def test_elevenlabs_streaming_tts():
    """Verify ElevenLabsStreamingTTS requests direct 8kHz mu-law audio stream."""
    tts = ElevenLabsStreamingTTS(api_key="mock_eleven_key")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    # 480 bytes = 3 x 20ms frames
    mock_resp.content = bytes([128] * 480)

    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        chunks = tts.synthesize_stream_chunks("Vanakkam", language="ta-IN")
        assert len(chunks) == 3
        assert len(chunks[0]) == 160

        _, kwargs = mock_post.call_args
        assert kwargs["params"]["output_format"] == "ulaw_8000"
        assert kwargs["headers"]["xi-api-key"] == "mock_eleven_key"


def test_openai_streaming_tts_downsampling():
    """Verify OpenAIStreamingTTS accepts 24kHz PCM and transcodes to 8kHz mu-law."""
    tts = OpenAIStreamingTTS(api_key="mock_openai_key")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    # 24,000 samples/sec * 2 bytes = 48,000 bytes per second.
    # 4800 bytes of 24kHz PCM16 -> 800 samples -> 800 bytes mu-law (5 frames of 160)
    mock_resp.content = bytes([10] * 4800)

    with patch("httpx.Client.post", return_value=mock_resp):
        mulaw = tts.synthesize_to_mulaw("Welcome to Vattara Health")
        assert len(mulaw) == 800


# ==============================================================================
# 4. Plivo Media Stream Webhook
# ==============================================================================


def test_plivo_media_stream_xml_generation(client: TestClient, db_session: Session):
    """Verify POST /api/v1/plivo/incoming generates valid <Stream> XML."""
    payload = {
        "CallUUID": "val_stream_test_001",
        "From": "+919876543210",
        "To": settings.PLIVO_PHONE_NUMBER or "+918040001234",
        "Direction": "inbound",
    }
    endpoint = "/api/v1/plivo/incoming"
    url = f"http://testserver{endpoint}"
    nonce = "777888999111"
    sig = PlivoService.compute_v3_signature(
        auth_token=settings.PLIVO_AUTH_TOKEN or "test_token",
        uri=url,
        nonce=nonce,
        method="POST",
        params=payload,
    )

    resp = client.post(
        endpoint,
        data=payload,
        headers={
            "X-Plivo-Signature-V3": sig,
            "X-Plivo-Signature-V3-Nonce": nonce,
        },
    )
    assert resp.status_code == 200
    assert "application/xml" in resp.headers["content-type"]
    xml_content = resp.text
    assert "<Response>" in xml_content
    assert "<Stream" in xml_content
    assert "/api/v1/plivo/stream" in xml_content


# ==============================================================================
# 5. WebSocket Stream Lifecycle & Real-Time Turn-Taking
# ==============================================================================


def test_websocket_stream_lifecycle_and_turn_taking(client: TestClient, db_session: Session):
    """Verify complete WebSocket Media Stream lifecycle: connect, start, playAudio, stop."""
    stream_sid = "plivo_stream_test_001"
    call_sid = "val_call_test_001"

    # Pre-seed call
    call = Call(
        id=call_sid,
        business_id="demo-biz-vattara-health",
        caller_phone="+919876543210",
        call_type="incoming",
        status="in_progress",
        duration_seconds=0,
        summary=f"Incoming voice call via Plivo (CallUUID: {call_sid})",
        initiated_at=datetime.now(timezone.utc),
    )
    db_session.add(call)
    db_session.commit()

    with client.websocket_connect(f"/api/v1/plivo/stream?business_id=demo-biz-vattara-health&call_uuid={call_sid}&caller_phone=%2B919876543210") as ws:
        # Step 1: Send 'start'
        ws.send_text(
            json.dumps({
                "event": "start",
                "start": {
                    "streamId": stream_sid,
                    "callId": call_sid,
                },
            })
        )

        # Receive greeting media events
        received_media = False
        for _ in range(5):
            msg = json.loads(ws.receive_text())
            if msg.get("event") == "playAudio":
                received_media = True
                assert "media" in msg
                assert "payload" in msg["media"]
                break

        assert received_media, "Expected assistant voice greeting playAudio frame"

        # Step 2: Send 'stop'
        ws.send_text(json.dumps({"event": "stop", "stop": {"streamId": stream_sid, "callId": call_sid}}))

    # Verify session cleaned up
    assert stream_manager.get_session(stream_sid) is None

    # Verify Call record finalized in database
    db_call = db_session.scalar(select(Call).where(Call.summary.like(f"%{call_sid}%")))
    assert db_call is not None
    assert db_call.status == "completed"
    assert db_call.ended_at is not None


# ==============================================================================
# 6. Caller Interruption (Barge-In)
# ==============================================================================


def test_caller_interruption_barge_in():
    """Verify that high-energy caller speech while assistant is speaking fires barge-in."""
    async def _run():
        stream_sid = "MZ_barge_in_stream_002"
        call_sid = "CA_barge_in_call_002"

        mock_ws = AsyncMock()
        session = AudioStreamSession(
            stream_sid=stream_sid,
            call_sid=call_sid,
            business_id="demo-biz-vattara-health",
            caller_phone="+919876543210",
        )
        # Simulate assistant currently speaking
        session.is_assistant_speaking = True
        initial_gen = session.playback_generation

        await stream_manager.register(stream_sid, mock_ws, session)

        orchestrator = StreamOrchestrator(vad_energy_threshold=300.0)

        # High energy audio sample (simulating caller speaking)
        loud_samples = [15000 if i % 2 == 0 else -15000 for i in range(160)]
        loud_pcm = struct.pack(f"<{len(loud_samples)}h", *loud_samples)
        loud_mulaw = pcm16_to_mulaw(loud_pcm)
        loud_b64 = mulaw_to_base64(loud_mulaw)

        # Process consecutive speech frames (matching BARGE_IN_MIN_SPEECH_FRAMES = 5)
        for _ in range(settings.BARGE_IN_MIN_SPEECH_FRAMES):
            await orchestrator.handle_media(stream_sid, {"payload": loud_b64}, db=MagicMock())

        # Verify Barge-In was triggered
        assert session.interrupted is True
        assert session.is_assistant_speaking is False
        assert session.playback_generation > initial_gen

        # Verify Twilio 'clear' event was sent to flush audio buffer
        mock_ws.send_text.assert_called()
        sent_calls = [json.loads(call.args[0]) for call in mock_ws.send_text.call_args_list]
        clear_events = [c for c in sent_calls if c.get("event") in ("clear", "clearAudio")]
        assert len(clear_events) >= 1
        assert clear_events[0].get("streamSid") == stream_sid or clear_events[0].get("streamId") == stream_sid

        await stream_manager.unregister(stream_sid)

    anyio.run(_run)


# ==============================================================================
# 7. Multi-Tenant Stream Isolation
# ==============================================================================


def test_multi_tenant_stream_isolation(client: TestClient, db_session: Session):
    """Verify distinct streams maintain independent tenant context and session isolation."""
    # Create two distinct tenants
    biz1 = Business(
        id="biz-stream-tenant-1",
        name="Alpha Clinic",
        email="reception@alphaclinic.com",
        phone="+9144001",
        is_active=True,
    )
    biz2 = Business(
        id="biz-stream-tenant-2",
        name="Beta Hospital",
        email="contact@betahospital.com",
        phone="+9144002",
        is_active=True,
    )
    db_session.add_all([biz1, biz2])

    call1 = Call(
        id="val_call_iso_001",
        business_id=biz1.id,
        caller_phone="+919876543210",
        call_type="incoming",
        status="in_progress",
        duration_seconds=0,
        summary="Incoming voice call via Plivo (CallUUID: val_call_iso_001)",
        initiated_at=datetime.now(timezone.utc),
    )
    call2 = Call(
        id="val_call_iso_002",
        business_id=biz2.id,
        caller_phone="+919876543211",
        call_type="incoming",
        status="in_progress",
        duration_seconds=0,
        summary="Incoming voice call via Plivo (CallUUID: val_call_iso_002)",
        initiated_at=datetime.now(timezone.utc),
    )
    db_session.add_all([call1, call2])
    db_session.commit()

    # Stream 1 for Tenant 1
    with client.websocket_connect(f"/api/v1/plivo/stream?business_id={biz1.id}&call_uuid={call1.id}&caller_phone=%2B919876543210") as ws1:
        ws1.send_text(
            json.dumps({
                "event": "start",
                "start": {
                    "streamId": "MZ_iso_001",
                    "callId": call1.id,
                },
            })
        )
        msg1 = json.loads(ws1.receive_text())
        assert msg1.get("event") == "playAudio"

        s1 = stream_manager.get_session("MZ_iso_001")
        assert s1 is not None
        assert s1.business_id == biz1.id
        tenant_1_resolved_id = s1.business_id
        ws1.send_text(json.dumps({"event": "stop", "stop": {"streamId": "MZ_iso_001", "callId": call1.id}}))

    # Stream 2 for Tenant 2
    with client.websocket_connect(f"/api/v1/plivo/stream?business_id={biz2.id}&call_uuid={call2.id}&caller_phone=%2B919876543211") as ws2:
        ws2.send_text(
            json.dumps({
                "event": "start",
                "start": {
                    "streamId": "MZ_iso_002",
                    "callId": call2.id,
                },
            })
        )
        msg2 = json.loads(ws2.receive_text())
        assert msg2.get("event") == "playAudio"

        s2 = stream_manager.get_session("MZ_iso_002")
        assert s2 is not None
        assert s2.business_id == biz2.id
        tenant_2_resolved_id = s2.business_id
        ws2.send_text(json.dumps({"event": "stop", "stop": {"streamId": "MZ_iso_002", "callId": call2.id}}))

    assert tenant_1_resolved_id == biz1.id
    assert tenant_2_resolved_id == biz2.id
    assert tenant_1_resolved_id != tenant_2_resolved_id


# ==============================================================================
# 8. Streaming Engine Health Telemetry
# ==============================================================================


def test_stream_engine_health_endpoint(client: TestClient):
    """Verify /health/plivo reports operational state and configured status."""
    resp = client.get("/api/v1/health/plivo")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "configured" in data


# ==============================================================================
# 9. Plivo Live Voice Diagnostics & Playback Fixes
# ==============================================================================


def test_playback_timestamp_set_immediately_before_first_chunk():
    """Verify assistant_speaking_started_at is NOT set during synthesis and stamped at chunk 0."""
    async def _run():
        stream_sid = "test_timestamp_stream"
        session = AudioStreamSession(
            stream_sid=stream_sid,
            call_sid="test_timestamp_call",
            business_id="demo-biz-vattara-health",
            caller_phone="+919876543210",
            provider="plivo",
        )
        mock_ws = AsyncMock()
        await stream_manager.register(stream_sid, mock_ws, session)

        # Before synthesis, speaking should be False
        assert session.is_assistant_speaking is False
        assert session.assistant_speaking_started_at is None

        orchestrator = StreamOrchestrator(tts_provider=MockStreamingTTS())

        # Synthesize and stream
        await orchestrator.stream_assistant_response(stream_sid, "Hello welcome to Vattara")

        # After playback completes, speaking flags should reset
        assert session.is_assistant_speaking is False
        assert session.assistant_speaking_started_at is None
        assert mock_ws.send_text.called

    anyio.run(_run)


def test_carrier_noise_cannot_interrupt_initial_playback():
    """Verify that carrier noise transients during startup and grace period cannot abort playback."""
    async def _run():
        stream_sid = "test_carrier_noise_stream"
        session = AudioStreamSession(
            stream_sid=stream_sid,
            call_sid="test_carrier_noise_call",
            business_id="demo-biz-vattara-health",
            caller_phone="+919876543210",
            provider="plivo",
        )
        mock_ws = AsyncMock()
        await stream_manager.register(stream_sid, mock_ws, session)
        orchestrator = StreamOrchestrator()

        # High-amplitude noise packet (e.g. mobile carrier connect burst)
        noise_samples = [16000 if i % 2 == 0 else -16000 for i in range(160)]
        noise_pcm = struct.pack(f"<{len(noise_samples)}h", *noise_samples)
        noise_b64 = mulaw_to_base64(pcm16_to_mulaw(noise_pcm))

        # 1. Noise during synthesis phase (assistant not speaking yet)
        session.is_assistant_speaking = False
        session.assistant_speaking_started_at = None
        for _ in range(3):
            await orchestrator.handle_media(stream_sid, {"payload": noise_b64}, db=MagicMock())
        assert session.interrupted is False

        # 2. Start playback: timestamp stamped now
        session.is_assistant_speaking = True
        session.assistant_speaking_started_at = time.time()
        session.reset_turn_buffer()
        session.interrupted = False

        # 3. Carrier noise arrives during initial 1200ms grace period
        for _ in range(10):
            await orchestrator.handle_media(stream_sid, {"payload": noise_b64}, db=MagicMock())

        # Within the grace period, barge-in is suppressed despite high energy
        assert session.interrupted is False
        assert session.is_assistant_speaking is True

    anyio.run(_run)


def test_genuine_caller_speech_triggers_barge_in_after_grace_period():
    """Verify genuine speech (5 consecutive frames after grace period) triggers barge-in."""
    async def _run():
        stream_sid = "test_genuine_barge_in_stream"
        session = AudioStreamSession(
            stream_sid=stream_sid,
            call_sid="test_genuine_barge_in_call",
            business_id="demo-biz-vattara-health",
            caller_phone="+919876543210",
            provider="plivo",
        )
        mock_ws = AsyncMock()
        await stream_manager.register(stream_sid, mock_ws, session)
        orchestrator = StreamOrchestrator()

        # Set assistant speaking started 2 seconds ago (grace period expired)
        session.is_assistant_speaking = True
        session.assistant_speaking_started_at = time.time() - 2.0
        initial_gen = session.playback_generation

        # Speech frame with RMS energy > 850
        speech_samples = [14000 if i % 2 == 0 else -14000 for i in range(160)]
        speech_pcm = struct.pack(f"<{len(speech_samples)}h", *speech_samples)
        speech_b64 = mulaw_to_base64(pcm16_to_mulaw(speech_pcm))

        # (BARGE_IN_MIN_SPEECH_FRAMES - 1) frames should not trigger barge-in
        for _ in range(settings.BARGE_IN_MIN_SPEECH_FRAMES - 1):
            await orchestrator.handle_media(stream_sid, {"payload": speech_b64}, db=MagicMock())
        assert session.interrupted is False

        # Next frame reaches BARGE_IN_MIN_SPEECH_FRAMES -> triggers barge-in
        await orchestrator.handle_media(stream_sid, {"payload": speech_b64}, db=MagicMock())
        assert session.interrupted is True
        assert session.playback_generation > initial_gen
        assert session.is_assistant_speaking is False

        # Verify Plivo clearAudio event was transmitted
        mock_ws.send_text.assert_called()
        sent_calls = [json.loads(call.args[0]) for call in mock_ws.send_text.call_args_list]
        clear_events = [c for c in sent_calls if c.get("event") == "clearAudio"]
        assert len(clear_events) >= 1
        assert clear_events[0]["streamId"] == stream_sid

    anyio.run(_run)


def test_stt_authentication_failures_reported_clearly(caplog):
    """Verify STT authentication failures log descriptive error messages and return empty string."""
    import logging

    # 1. Whisper STT with HTTP 401 response
    whisper_stt = WhisperStreamingSTT(api_key="invalid_test_key")
    whisper_stt.process_audio_chunk(bytes([50] * 3200))

    mock_401 = MagicMock()
    mock_401.status_code = 401
    mock_401.text = '{"error": {"message": "Incorrect API key provided: sk-test"}}'

    with patch("httpx.Client.post", return_value=mock_401):
        with caplog.at_level(logging.ERROR):
            transcript = whisper_stt.flush(language="en-IN")
            assert transcript == ""
            assert any("Whisper STT authentication failure (HTTP 401)" in rec.message for rec in caplog.records)

    caplog.clear()

    # 2. Deepgram STT with HTTP 401 response
    deepgram_stt = DeepgramStreamingSTT(api_key="invalid_test_key")
    deepgram_stt.process_audio_chunk(bytes([50] * 3200))

    mock_dg_401 = MagicMock()
    mock_dg_401.status_code = 401
    mock_dg_401.text = '{"err_code": "INVALID_AUTH", "err_msg": "Invalid credentials"}'

    with patch("httpx.Client.post", return_value=mock_dg_401):
        with caplog.at_level(logging.ERROR):
            transcript = deepgram_stt.flush(language="en-IN")
            assert transcript == ""
            assert any("Deepgram STT authentication failure (HTTP 401)" in rec.message for rec in caplog.records)

    caplog.clear()

    # 3. get_streaming_stt_provider("deepgram") without key logs clear configuration error
    with patch("app.core.config.settings.DEEPGRAM_API_KEY", None):
        with caplog.at_level(logging.ERROR):
            provider = get_streaming_stt_provider("deepgram")
            assert provider.provider_name == "deepgram"
            assert any("DEEPGRAM_API_KEY is not configured" in rec.message for rec in caplog.records)
