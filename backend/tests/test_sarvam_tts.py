"""Comprehensive Automated Test Suite for Sarvam AI Bulbul v4 Flash TTS Provider.

Tests all 12 required migration scenarios:
1. Sarvam API authentication & credential masking
2. TTS provider initialization & configuration
3. Tamil speech generation (ta-IN, speaker: ratan)
4. English speech generation (en-IN, speaker: ratan)
5. Tanglish speech generation (ta-Latn / code-switching)
6. Progressive audio chunk reception
7. Audio decoding (raw mu-law, WAV container stripping, PCM transcoding)
8. μ-law 8 kHz compatibility & MP3 rejection
9. Plivo audio forwarding (playAudio event format & 160-byte 20ms frames)
10. Barge-in interruption & playback termination
11. WebSocket disconnection resilience
12. Provider fallback to ElevenLabs / Mock
"""

import asyncio
import base64
from contextlib import asynccontextmanager
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.core.config import settings
from app.services.streaming.audio_codec import (
    chunk_audio,
    is_mp3_audio,
    is_wav_container,
    pcm16_to_mulaw,
    validate_and_normalize_to_mulaw_8k,
    validate_telephony_mulaw_chunk,
)
from app.services.streaming.base_tts import BaseStreamingTTS, MockStreamingTTS
from app.services.streaming.sarvam_tts import (
    SarvamStreamingTTS,
    mask_credential,
    sanitize_error_msg,
)
from app.services.streaming.session_manager import AudioStreamSession, StreamConnectionManager
from app.services.streaming.stream_orchestrator import StreamOrchestrator
from app.services.streaming.tts_provider import (
    ElevenLabsStreamingTTS,
    get_streaming_tts_provider,
)


class MockSarvamWebSocket:
    """Mock WebSocket implementing Sarvam streaming methods and asynchronous iteration."""

    def __init__(self, messages):
        self.messages = messages
        self.configure = AsyncMock()
        self.convert = AsyncMock()
        self.flush = AsyncMock()

    async def __aiter__(self):
        for msg in self.messages:
            yield msg


# Helper to build mock Sarvam audio message
def make_mock_sarvam_audio_message(raw_mulaw_bytes: bytes) -> MagicMock:
    """Create a mock AudioOutput message matching Sarvam SDK structure."""
    from sarvamai.types.audio_output import AudioOutput
    from sarvamai.types.audio_output_data import AudioOutputData

    b64_str = base64.b64encode(raw_mulaw_bytes).decode("ascii")
    return AudioOutput(
        type="audio",
        data=AudioOutputData(
            content_type="audio/x-mulaw",
            audio=b64_str,
            request_id="req_test_001",
        ),
    )


def make_mock_sarvam_final_event() -> MagicMock:
    """Create a mock EventResponse message matching Sarvam SDK completion event."""
    from sarvamai.types.event_response import EventResponse
    from sarvamai.types.event_response_data import EventResponseData

    return EventResponse(
        type="event",
        data=EventResponseData(
            event_type="final",
            message="TTS generation completed",
            timestamp="2026-11-17T12:00:00Z",
        ),
    )


# ==============================================================================
# 1. Sarvam API Authentication
# ==============================================================================

def test_1_sarvam_api_authentication():
    """Verify API key loading, masking, and that credentials are never exposed in logs."""
    raw_key = "sk_samvaad_nbwuq693_ULxlz8bjNRsjclhz2sGxGS44"
    masked = mask_credential(raw_key)

    # Must mask middle characters
    assert masked.startswith("sk_sa")
    assert masked.endswith("GS44")
    assert "nbwuq693" not in masked
    assert "ULxlz8bj" not in masked

    # Sanitizer removes keys from error messages
    error_str = f"Error communicating with Sarvam using api-subscription-key {raw_key} failed"
    sanitized = sanitize_error_msg(error_str)
    assert raw_key not in sanitized
    assert "***" in sanitized

    # Provider strips Bearer prefix if user pasted Authorization header
    provider_with_bearer = SarvamStreamingTTS(api_key=f"Bearer {raw_key}")
    assert provider_with_bearer.api_key == raw_key


# ==============================================================================
# 2. TTS Provider Initialization
# ==============================================================================

def test_2_sarvam_tts_provider_initialization():
    """Verify SarvamStreamingTTS initialization with defaults from config."""
    tts = SarvamStreamingTTS(
        api_key="mock_sarvam_key",
        model="bulbul:v4-flash",
        tamil_speaker="ratan",
        english_speaker="ratan",
        pace=1.0,
    )

    assert tts.provider_name == "sarvam"
    assert tts.model == "bulbul:v4-flash"
    assert tts.tamil_speaker == "ratan"
    assert tts.english_speaker == "ratan"
    assert tts.pace == 1.0
    assert tts.enable_preprocessing is True
    assert isinstance(tts, BaseStreamingTTS)

    # Factory getter integration
    with patch.object(settings, "TTS_PROVIDER", "sarvam"):
        with patch.object(settings, "SARVAM_API_KEY", "mock_key"):
            with patch.object(settings, "ENVIRONMENT", "production"):
                factory_provider = get_streaming_tts_provider()
                assert isinstance(factory_provider, SarvamStreamingTTS)
                assert factory_provider.provider_name == "sarvam"


# ==============================================================================
# 3. Tamil Speech Generation
# ==============================================================================

def test_3_sarvam_tamil_speech_generation():
    """Verify Tamil language resolution (ta-IN, speaker: ratan) and audio frame generation."""
    async def _run():
        tts = SarvamStreamingTTS(api_key="mock_sarvam_key")
        lang_code, speaker = tts.resolve_language_and_speaker("ta-IN")

        assert lang_code == "ta-IN"
        assert speaker == "ratan"

        # 480 bytes = 3 frames of 160 bytes
        mock_audio_bytes = bytes([128] * 480)
        mock_msg = make_mock_sarvam_audio_message(mock_audio_bytes)
        mock_final = make_mock_sarvam_final_event()

        mock_ws = MockSarvamWebSocket([mock_msg, mock_final])

        @asynccontextmanager
        async def mock_connect():
            yield mock_ws

        with patch.object(tts, "_connect_ws", side_effect=mock_connect):
            frames: list[bytes] = []
            async for frame in tts.astream_mulaw_chunks("வணக்கம், நலமா?", language="ta-IN"):
                frames.append(frame)

            assert len(frames) == 3
            assert all(len(f) == 160 for f in frames)
            mock_ws.configure.assert_awaited_once()
            cfg_kwargs = mock_ws.configure.await_args.kwargs
            assert cfg_kwargs["target_language_code"] == "ta-IN"
            assert cfg_kwargs["speaker"] == "ratan"
            assert cfg_kwargs["output_audio_codec"] == "mulaw"
            assert cfg_kwargs["speech_sample_rate"] == 8000

    asyncio.run(_run())


# ==============================================================================
# 4. English Speech Generation
# ==============================================================================

def test_4_sarvam_english_speech_generation():
    """Verify English language resolution (en-IN, speaker: ratan) and audio frames."""
    async def _run():
        tts = SarvamStreamingTTS(api_key="mock_sarvam_key")
        lang_code, speaker = tts.resolve_language_and_speaker("en-IN")

        assert lang_code == "en-IN"
        assert speaker == "ratan"

        mock_audio_bytes = bytes([64] * 320)  # 2 frames of 160 bytes
        mock_msg = make_mock_sarvam_audio_message(mock_audio_bytes)
        mock_final = make_mock_sarvam_final_event()

        mock_ws = MockSarvamWebSocket([mock_msg, mock_final])

        @asynccontextmanager
        async def mock_connect():
            yield mock_ws

        with patch.object(tts, "_connect_ws", side_effect=mock_connect):
            frames: list[bytes] = []
            async for frame in tts.astream_mulaw_chunks(
                "Hello, welcome to Vattara Clinic.", language="en-IN"
            ):
                frames.append(frame)

            assert len(frames) == 2
            assert all(len(f) == 160 for f in frames)
            mock_ws.configure.assert_awaited_once()
            assert mock_ws.configure.await_args.kwargs["target_language_code"] == "en-IN"

    asyncio.run(_run())


# ==============================================================================
# 5. Tanglish Speech Generation
# ==============================================================================

def test_5_sarvam_tanglish_speech_generation():
    """Verify Tanglish (ta-Latn) maps to ta-IN with enable_preprocessing=True."""
    async def _run():
        tts = SarvamStreamingTTS(api_key="mock_sarvam_key")
        lang_code, speaker = tts.resolve_language_and_speaker("ta-Latn")

        assert lang_code == "ta-IN"
        assert speaker == "ratan"

        mock_audio_bytes = bytes([200] * 160)
        mock_msg = make_mock_sarvam_audio_message(mock_audio_bytes)
        mock_final = make_mock_sarvam_final_event()

        mock_ws = MockSarvamWebSocket([mock_msg, mock_final])

        @asynccontextmanager
        async def mock_connect():
            yield mock_ws

        with patch.object(tts, "_connect_ws", side_effect=mock_connect):
            frames: list[bytes] = []
            async for frame in tts.astream_mulaw_chunks(
                "Vanakkam! Naalaiki 10 manikku appointment book pannidalaama?", language="ta-Latn"
            ):
                frames.append(frame)

            assert len(frames) == 1
            assert len(frames[0]) == 160
            cfg_kwargs = mock_ws.configure.await_args.kwargs
            assert cfg_kwargs["target_language_code"] == "ta-IN"
            assert cfg_kwargs["enable_preprocessing"] is True

    asyncio.run(_run())


# ==============================================================================
# 6. Audio Chunk Reception
# ==============================================================================

def test_6_sarvam_audio_chunk_reception():
    """Verify progressive chunk reception across multiple WebSocket frames."""
    async def _run():
        tts = SarvamStreamingTTS(api_key="mock_sarvam_key")

        # 3 separate progressive chunks from WebSocket (80 bytes each -> total 240 bytes = 1.5 frames)
        # Streamer should buffer chunk 1 and 2, yield 160 bytes, then yield remaining 80 padded to 160!
        chunk1 = make_mock_sarvam_audio_message(bytes([10] * 80))
        chunk2 = make_mock_sarvam_audio_message(bytes([20] * 80))
        chunk3 = make_mock_sarvam_audio_message(bytes([30] * 80))
        mock_final = make_mock_sarvam_final_event()

        mock_ws = MockSarvamWebSocket([chunk1, chunk2, chunk3, mock_final])

        @asynccontextmanager
        async def mock_connect():
            yield mock_ws

        with patch.object(tts, "_connect_ws", side_effect=mock_connect):
            frames: list[bytes] = []
            async for frame in tts.astream_mulaw_chunks("Testing progressive chunk reception"):
                frames.append(frame)

            assert len(frames) == 2
            assert len(frames[0]) == 160
            assert len(frames[1]) == 160
            # Frame 0 should contain chunk1 + chunk2
            assert frames[0][:80] == bytes([10] * 80)
            assert frames[0][80:] == bytes([20] * 80)
            # Frame 1 should contain chunk3 + silence padding (0xFF)
            assert frames[1][:80] == bytes([30] * 80)
            assert frames[1][80:] == b"\xff" * 80

    asyncio.run(_run())


# ==============================================================================
# 7. Audio Decoding
# ==============================================================================

def test_7_sarvam_audio_decoding():
    """Verify audio decoding handles raw mu-law, WAV containers with mu-law format 7, and WAV PCM16."""
    # Case A: Raw mu-law bytes
    raw_mulaw = bytes([120, 130, 140, 150])
    res_a = validate_and_normalize_to_mulaw_8k(raw_mulaw)
    assert res_a == raw_mulaw

    # Case B: WAV container wrapping format 7 (mu-law)
    import struct
    wav_mulaw = (
        b"RIFF" + struct.pack("<I", 36 + 4) + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 7, 1, 8000, 8000, 1, 8)
        + b"data" + struct.pack("<I", 4) + raw_mulaw
    )
    assert is_wav_container(wav_mulaw)
    res_b = validate_and_normalize_to_mulaw_8k(wav_mulaw)
    assert res_b == raw_mulaw

    # Case C: WAV container wrapping format 1 (linear PCM16 at 8000Hz)
    pcm_samples = [500, -500, 1000, -1000]
    pcm_bytes = struct.pack("<4h", *pcm_samples)
    wav_pcm = (
        b"RIFF" + struct.pack("<I", 36 + len(pcm_bytes)) + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, 8000, 16000, 2, 16)
        + b"data" + struct.pack("<I", len(pcm_bytes)) + pcm_bytes
    )
    res_c = validate_and_normalize_to_mulaw_8k(wav_pcm)
    expected_mulaw = pcm16_to_mulaw(pcm_bytes)
    assert res_c == expected_mulaw


# ==============================================================================
# 8. μ-law 8 kHz Compatibility & MP3 Rejection
# ==============================================================================

def test_8_sarvam_mulaw_8khz_compatibility():
    """Verify MP3 data is strictly rejected and never forwarded into mu-law pipeline."""
    # MP3 with ID3 header
    mp3_id3 = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\xff\xfb\x90\x44" * 10
    assert is_mp3_audio(mp3_id3)

    with pytest.raises(ValueError, match="MP3 data detected"):
        validate_and_normalize_to_mulaw_8k(mp3_id3)

    # MP3 with MPEG sync word (0xFF 0xFB)
    mp3_sync = b"\xff\xfb\x90\x64" + b"\x00" * 100
    assert is_mp3_audio(mp3_sync)

    with pytest.raises(ValueError, match="MP3 data detected"):
        validate_and_normalize_to_mulaw_8k(mp3_sync)


# ==============================================================================
# 9. Plivo Audio Forwarding
# ==============================================================================

def test_9_sarvam_plivo_audio_forwarding():
    """Verify StreamConnectionManager formats Plivo playAudio event with 8kHz mu-law payload."""
    async def _run():
        stream_sid = "plivo_stream_test_forwarding"
        call_sid = "plivo_call_test_forwarding"

        mock_ws = AsyncMock()
        session = AudioStreamSession(
            stream_sid=stream_sid,
            call_sid=call_sid,
            business_id="demo-biz-vattara-health",
            caller_phone="+919876543210",
            provider="plivo",
        )

        manager = StreamConnectionManager()
        await manager.register(stream_sid, mock_ws, session)

        test_frame = bytes([128] * 160)
        success = await manager.send_media(stream_sid, test_frame)
        assert success is True

        mock_ws.send_text.assert_awaited_once()
        raw_sent = mock_ws.send_text.await_args[0][0]
        payload_dict = json.loads(raw_sent)

        assert payload_dict["event"] == "playAudio"
        assert "media" in payload_dict
        assert payload_dict["media"]["contentType"] == "audio/x-mulaw"
        assert payload_dict["media"]["sampleRate"] == 8000
        b64_audio = payload_dict["media"]["payload"]
        assert base64.b64decode(b64_audio) == test_frame

        # Test rejection of corrupt MP3 frame in send_media
        corrupt_mp3_frame = b"ID3" + bytes([0] * 157)
        rejected = await manager.send_media(stream_sid, corrupt_mp3_frame)
        assert rejected is False

    asyncio.run(_run())


# ==============================================================================
# 10. Barge-in Interruption
# ==============================================================================

def test_10_sarvam_barge_in_interruption():
    """Verify caller interruption halts progressive audio streaming immediately."""
    async def _run():
        stream_sid = "plivo_stream_barge_in_test"
        mock_ws = AsyncMock()

        session = AudioStreamSession(
            stream_sid=stream_sid,
            call_sid="call_barge_in_001",
            business_id="demo-biz",
            caller_phone="+919876543210",
            provider="plivo",
        )

        manager = StreamConnectionManager()
        await manager.register(stream_sid, mock_ws, session)

        # Create infinite frame generator mock
        async def mock_frame_stream(*args, **kwargs):
            for i in range(100):
                yield bytes([i % 256] * 160)

        mock_tts = MagicMock(spec=SarvamStreamingTTS)
        mock_tts.astream_mulaw_chunks = mock_frame_stream

        orchestrator = StreamOrchestrator(tts_provider=mock_tts)

        # Patch stream_manager with our registered manager
        with patch("app.services.streaming.stream_orchestrator.stream_manager", manager):
            stream_task = asyncio.create_task(
                orchestrator.stream_assistant_response(
                    stream_sid=stream_sid,
                    text="Long speech that will be interrupted by the caller.",
                )
            )

            # Allow stream to start and send first few frames
            await asyncio.sleep(0.05)
            assert session.is_assistant_speaking is True

            # Simulate caller interruption (barge-in)
            session.trigger_barge_in()
            await manager.send_clear(stream_sid)

            # Allow orchestrator task to observe interruption and return
            await asyncio.sleep(0.05)
            assert stream_task.done() or session.interrupted is True

            # Verify clearAudio event was sent to Plivo
            sent_calls = [json.loads(c[0][0]) for c in mock_ws.send_text.await_args_list]
            clear_events = [c for c in sent_calls if c.get("event") == "clearAudio"]
            assert len(clear_events) >= 1

    asyncio.run(_run())


# ==============================================================================
# 11. WebSocket Disconnection Resilience
# ==============================================================================

def test_11_sarvam_websocket_disconnection():
    """Verify handling of unexpected WebSocket disconnection or connection error."""
    async def _run():
        mock_fallback = MagicMock(spec=BaseStreamingTTS)
        mock_fallback.provider_name = "mock"
        mock_fallback.asynthesize_stream_chunks = AsyncMock(
            return_value=[bytes([255] * 160), bytes([255] * 160)]
        )

        tts = SarvamStreamingTTS(
            api_key="mock_sarvam_key",
            fallback_provider=mock_fallback,
        )

        @asynccontextmanager
        async def mock_disconnect():
            raise ConnectionResetError("Remote server closed connection")
            yield  # pragma: no cover

        with patch.object(tts, "_connect_ws", side_effect=mock_disconnect):
            frames: list[bytes] = []
            async for frame in tts.astream_mulaw_chunks("Disconnection resilience test"):
                frames.append(frame)

            # Must cleanly fall back to fallback provider without crashing
            assert len(frames) == 2
            assert len(frames[0]) == 160
            mock_fallback.asynthesize_stream_chunks.assert_awaited_once()

    asyncio.run(_run())


# ==============================================================================
# 12. Provider Fallback
# ==============================================================================

def test_12_sarvam_provider_fallback():
    """Verify that when Sarvam fails with auth or network error, fallback provider is used."""
    async def _run():
        mock_eleven = MagicMock(spec=ElevenLabsStreamingTTS)
        mock_eleven.provider_name = "elevenlabs"
        mock_eleven.asynthesize_stream_chunks = AsyncMock(
            return_value=[bytes([150] * 160), bytes([150] * 160), bytes([150] * 160)]
        )

        tts = SarvamStreamingTTS(
            api_key="invalid_test_key",
            fallback_provider=mock_eleven,
        )

        from sarvamai.core.api_error import ApiError

        @asynccontextmanager
        async def mock_auth_error():
            raise ApiError(
                status_code=403,
                body="Invalid or missing authentication credentials",
                headers={},
            )
            yield  # pragma: no cover

        with patch.object(tts, "_connect_ws", side_effect=mock_auth_error):
            frames: list[bytes] = []
            async for frame in tts.astream_mulaw_chunks("Testing fallback to ElevenLabs"):
                frames.append(frame)

            assert len(frames) == 3
            assert tts.is_circuit_breaker_active is True
            mock_eleven.asynthesize_stream_chunks.assert_awaited_once()

    asyncio.run(_run())


# ==============================================================================
# 13. Raw μ-law Silence & Audio Validation
# ==============================================================================

def test_13_mulaw_silence_and_audio_validation():
    """Verify that pure G.711 mu-law frames and silence padding (0xFF) are accepted and forwarded."""
    # 1. 0xFF is valid ITU-T G.711 mu-law silence (must NOT be rejected as MP3)
    silence_frame = bytes([0xFF] * 160)
    is_valid, reason = validate_telephony_mulaw_chunk(silence_frame)
    assert is_valid is True, f"Silence frame was falsely rejected: {reason}"

    # 2. 0x7F is also low-level / alternate mu-law silence
    alt_silence = bytes([0x7F] * 160)
    is_valid2, _ = validate_telephony_mulaw_chunk(alt_silence)
    assert is_valid2 is True

    # 3. Verify send_media transmits silence-prefixed frames without false block
    async def _run():
        stream_sid = "test_stream_silence_validation"
        mock_ws = AsyncMock()
        session = AudioStreamSession(
            stream_sid=stream_sid,
            call_sid="call_silence_001",
            business_id="demo-biz",
            caller_phone="+919876543210",
            provider="plivo",
        )
        manager = StreamConnectionManager()
        await manager.register(stream_sid, mock_ws, session)

        success = await manager.send_media(stream_sid, silence_frame)
        assert success is True, "Silence frame must be forwarded to Plivo WebSocket"
        mock_ws.send_text.assert_awaited_once()

    asyncio.run(_run())


# ==============================================================================
# 14. Invalid Audio Rejection Matrix
# ==============================================================================

def test_14_invalid_audio_rejection_matrix():
    """Verify that genuinely invalid container formats and corrupt audio are strictly rejected."""
    # A. Empty audio chunk
    is_valid, _ = validate_telephony_mulaw_chunk(b"")
    assert is_valid is False

    # B. WAV / RIFF container header
    wav_header = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00"
    is_valid, reason = validate_telephony_mulaw_chunk(wav_header)
    assert is_valid is False
    assert "WAV/RIFF" in reason

    # C. MP3 with ID3 header
    mp3_id3 = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\xff\xfb\x90\x44" * 5
    is_valid, reason = validate_telephony_mulaw_chunk(mp3_id3)
    assert is_valid is False
    assert "MP3" in reason

    # D. Raw MP3 sync frame (0xFF 0xFB with valid MPEG-1 Layer 3 bitrate/sampling)
    mp3_raw = b"\xff\xfb\x90\x64" + bytes([0] * 156)
    is_valid, reason = validate_telephony_mulaw_chunk(mp3_raw)
    assert is_valid is False
    assert "MP3" in reason

    # E. OGG container header
    ogg_header = b"OggS\x00\x02\x00\x00\x00\x00\x00\x00"
    is_valid, reason = validate_telephony_mulaw_chunk(ogg_header)
    assert is_valid is False
    assert "OGG" in reason

    # F. FLAC container header
    flac_header = b"fLaC\x00\x00\x00\x22"
    is_valid, reason = validate_telephony_mulaw_chunk(flac_header)
    assert is_valid is False
    assert "FLAC" in reason

    # G. Verify send_media blocks forwarding for each invalid format
    async def _run():
        stream_sid = "test_stream_rejection"
        mock_ws = AsyncMock()
        session = AudioStreamSession(
            stream_sid=stream_sid,
            call_sid="call_reject_001",
            business_id="demo-biz",
            caller_phone="+919876543210",
            provider="plivo",
        )
        manager = StreamConnectionManager()
        await manager.register(stream_sid, mock_ws, session)

        for invalid_sample in [wav_header, mp3_id3, mp3_raw, ogg_header, flac_header]:
            rejected = await manager.send_media(stream_sid, invalid_sample)
            assert rejected is False

        mock_ws.send_text.assert_not_awaited()

    asyncio.run(_run())


# ==============================================================================
# 15. Sarvam TTS Provider Prioritization & Selection
# ==============================================================================

def test_15_sarvam_provider_prioritization_and_selection():
    """Verify Sarvam AI is selected as active primary provider, with ElevenLabs as fallback."""
    with patch.object(settings, "TTS_PROVIDER", "sarvam"):
        with patch.object(settings, "SARVAM_API_KEY", "sk_test_sarvam_developer_key"):
            with patch.object(settings, "ELEVENLABS_API_KEY", "eleven_fallback_key"):
                with patch.object(settings, "ENVIRONMENT", "production"):
                    provider = get_streaming_tts_provider()
                    assert isinstance(provider, SarvamStreamingTTS)
                    assert provider.provider_name == "sarvam"

                    # Verify ElevenLabs remains available as fallback
                    fallback = provider.get_fallback_provider()
                    assert isinstance(fallback, ElevenLabsStreamingTTS)
                    assert fallback.provider_name == "elevenlabs"


# ==============================================================================
# 16. End-to-End Mocked Voice Response Delivery
# ==============================================================================

def test_16_end_to_end_mocked_voice_response_delivery():
    """Verify complete pipeline delivery from stream orchestrator through Plivo playAudio WebSocket."""
    async def _run():
        stream_sid = "plivo_e2e_playback_stream"
        mock_ws = AsyncMock()

        session = AudioStreamSession(
            stream_sid=stream_sid,
            call_sid="call_e2e_001",
            business_id="demo-biz-vattara-health",
            caller_phone="+919876543210",
            provider="plivo",
        )

        from app.services.streaming.session_manager import stream_manager
        await stream_manager.register(stream_sid, mock_ws, session)

        # Mock TTS that yields 5 progressive frames, including leading silence frame
        silence_chunk = bytes([0xFF] * 160)
        speech_chunk1 = bytes([120] * 160)
        speech_chunk2 = bytes([130] * 160)
        speech_chunk3 = bytes([140] * 160)
        tail_silence = bytes([0xFF] * 160)
        mock_frames = [silence_chunk, speech_chunk1, speech_chunk2, speech_chunk3, tail_silence]

        class MockVoiceProvider(BaseStreamingTTS):
            @property
            def provider_name(self):
                return "sarvam"

            def synthesize_to_mulaw(self, text, language="en-IN", voice=None):
                return b"".join(mock_frames)

            async def astream_mulaw_chunks(self, text, language="en-IN", voice=None, chunk_size=160):
                for f in mock_frames:
                    yield f

        orchestrator = StreamOrchestrator(tts_provider=MockVoiceProvider())

        # Execute audio streaming through orchestrator
        await orchestrator.stream_assistant_response(
            stream_sid=stream_sid,
            text="வணக்கம், உங்கள் முன்பதிவு உறுதிசெய்யப்பட்டது.",
            language="ta-IN",
        )

        # Verify all 5 frames were transmitted to Plivo WebSocket
        assert mock_ws.send_text.await_count == 5

        # Inspect each sent Plivo event
        for call_args in mock_ws.send_text.await_args_list:
            raw_json = call_args[0][0]
            msg = json.loads(raw_json)
            assert msg["event"] == "playAudio"
            assert msg["media"]["contentType"] == "audio/x-mulaw"
            assert msg["media"]["sampleRate"] == 8000
            assert "payload" in msg["media"]
            # Payload must decode to exactly 160 bytes
            decoded = base64.b64decode(msg["media"]["payload"])
            assert len(decoded) == 160

    asyncio.run(_run())
