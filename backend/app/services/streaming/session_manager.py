"""Audio Stream Session and WebSocket Connection Manager for real-time telephony streaming.

Manages:
- Per-call stream state, buffers, turn-taking, and VAD counters.
- Caller interruption (barge-in) state and token invalidation.
- Active WebSocket connections mapped to Twilio streamSid and callSid.
- Thread-safe outbound audio framing, marks, and clear event dispatches.
"""

import asyncio
from collections import deque
from datetime import datetime, timezone
import json
import time
from typing import Any
from fastapi import WebSocket

from app.core.logging import get_logger
from app.services.streaming.audio_codec import (
    AdaptiveNoiseFloorTracker,
    BiquadFilter,
    mulaw_to_base64,
    validate_telephony_mulaw_chunk,
)
from app.services.streaming.voice_registry import (
    get_voice_for_language,
    resolve_canonical_language,
    synchronize_voice_and_language,
)

logger = get_logger(__name__)


class AudioStreamSession:
    """Encapsulates active real-time conversational voice state for a single call stream."""

    def __init__(
        self,
        stream_sid: str,
        call_sid: str,
        business_id: str,
        caller_phone: str,
        destination_phone: str = "",
        customer_name: str | None = None,
        language: str = "en-IN",
        provider: str = "plivo",
        tts_provider: str = "sarvam",
    ):
        self.stream_sid = stream_sid
        self.call_sid = call_sid
        self.business_id = business_id
        self.caller_phone = caller_phone
        self.destination_phone = destination_phone
        self.customer_name = customer_name
        self.language = resolve_canonical_language(language)
        self.provider = provider.lower()  # "twilio" or "plivo"
        self.tts_provider = (tts_provider or "sarvam").lower()

        # Single source of truth for voice identity and language
        self.detected_language: str = self.language
        self.preferred_language: str = self.language
        self.active_response_language: str = self.language
        self.active_tts_language: str = self.language
        self.active_tts_speaker: str = get_voice_for_language(self.language, provider=self.tts_provider)

        # Inactivity & Silence Management
        self.inactivity_prompts_sent: int = 0
        self.last_speech_or_playback_at: float = time.time()
        self.inactivity_watchdog_task: asyncio.Task | None = None
        self.is_handling_inactivity: bool = False

        # VAD & Speech State
        self.noise_tracker = AdaptiveNoiseFloorTracker()
        self.highpass_filter = BiquadFilter()
        self.last_energy: float = 0.0
        self.inbound_pcm16_buffer = bytearray()
        self.inbound_mulaw_buffer = bytearray()
        self.latest_partial_transcript: str = ""
        self.latest_final_transcript: str = ""
        self.latest_final_confidence: float | None = None
        self.stt_detected_language: str | None = None
        self.sarvam_stt_stream: Any = None
        self.sarvam_stt_task: asyncio.Task | None = None
        self.consecutive_speech_frames = 0
        self.consecutive_silence_frames = 0
        self.recent_vad_frames: deque[int] = deque(maxlen=30)
        self.is_caller_speaking = False
        self.is_assistant_speaking = False
        self.turn_in_progress = False

        # Single playback concurrency lock and task reference
        self._playback_lock: asyncio.Lock | None = None
        self.current_playback_task: asyncio.Task | None = None

        # Playback lifecycle & frame tracking
        self.playback_cancellation_reason: str | None = None
        self.frames_generated: int = 0
        self.frames_queued: int = 0
        self.frames_sent: int = 0
        self.frames_rejected: int = 0
        self.playback_completed: bool = False

        # Turn serialization & sequence
        self._turn_lock: asyncio.Lock | None = None
        self.turn_seq: int = 0
        self.is_barge_in_pending: bool = False
        self.last_frame_perf: float = time.perf_counter()

        # Barge-in cancellation token & grace tracking
        self.playback_generation = 0
        self.interrupted = False
        self.assistant_speaking_started_at: float | None = None
        self.assistant_speaking_ended_at: float | None = None
        self.last_speech_timestamp = time.time()
        self.started_at = datetime.now(timezone.utc)

    def update_voice_state(self, response_text: str, custom_voice: str | None = None) -> tuple[str, str, str]:
        """Synchronize active response language, TTS language, and speaker persona with the response text."""
        resp_lang, tts_lang, speaker = synchronize_voice_and_language(
            response_text=response_text,
            session_language=self.language,
            provider=self.tts_provider,
            custom_voice=custom_voice,
        )
        self.active_response_language = resp_lang
        self.active_tts_language = tts_lang
        self.active_tts_speaker = speaker
        if self.language in ("ta-IN", "ta-Latn") and resp_lang in ("te-IN", "te-Latn"):
            logger.warning("Prevented session.language overwrite from Tamil to Telugu: resp_lang=%s", resp_lang)
        elif self.language in ("te-IN", "te-Latn") and resp_lang in ("ta-IN", "ta-Latn"):
            logger.warning("Prevented session.language overwrite from Telugu to Tamil: resp_lang=%s", resp_lang)
        else:
            self.language = resp_lang
        return resp_lang, tts_lang, speaker

    @property
    def playback_lock(self) -> asyncio.Lock:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if self._playback_lock is None or getattr(self._playback_lock, "_loop", None) not in (loop, None):
            self._playback_lock = asyncio.Lock()
        return self._playback_lock

    @property
    def turn_lock(self) -> asyncio.Lock:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if self._turn_lock is None or getattr(self._turn_lock, "_loop", None) not in (loop, None):
            self._turn_lock = asyncio.Lock()
        return self._turn_lock

    def reset_playback_metrics(self) -> None:
        """Reset frame metrics and state before a new playback turn begins."""
        self.playback_cancellation_reason = None
        self.frames_generated = 0
        self.frames_queued = 0
        self.frames_sent = 0
        self.frames_rejected = 0
        self.playback_completed = False
        self.interrupted = False

    def trigger_barge_in(self, reason: str = "caller_barge_in") -> int:
        """Handle caller interruption: invalidate assistant playback queue."""
        self.playback_generation += 1
        self.playback_cancellation_reason = reason
        self.playback_completed = False
        self.is_assistant_speaking = False
        self.assistant_speaking_started_at = None
        self.assistant_speaking_ended_at = time.time()
        self.interrupted = True
        self.turn_in_progress = False
        self.inactivity_prompts_sent = 0
        self.last_speech_or_playback_at = time.time()
        if self.current_playback_task and not self.current_playback_task.done():
            self.current_playback_task.cancel()
        logger.info(
            "Barge-in triggered on Stream %s (Gen: %d, reason: %s). Halting assistant audio playback.",
            self.stream_sid,
            self.playback_generation,
            reason,
        )
        return self.playback_generation

    def reset_turn_buffer(self) -> None:
        """Reset caller speech buffer and turn counters for next conversational turn."""
        self.inbound_pcm16_buffer.clear()
        self.inbound_mulaw_buffer.clear()
        self.latest_partial_transcript = ""
        self.latest_final_transcript = ""
        self.latest_final_confidence = None
        self.consecutive_speech_frames = 0
        self.consecutive_silence_frames = 0
        if hasattr(self, "recent_vad_frames") and self.recent_vad_frames is not None:
            self.recent_vad_frames.clear()
        self.is_caller_speaking = False
        self.last_speech_or_playback_at = time.time()


class StreamConnectionManager:
    """Thread-safe manager for active telephony WebSocket connections and streams."""

    def __init__(self):
        self._connections: dict[str, WebSocket] = {}
        self._sessions: dict[str, AudioStreamSession] = {}
        self._call_map: dict[str, str] = {}  # call_sid -> stream_sid
        self._lock: asyncio.Lock | None = None

    def _get_lock(self) -> asyncio.Lock:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if self._lock is None or getattr(self._lock, "_loop", None) not in (loop, None):
            self._lock = asyncio.Lock()
        return self._lock

    async def register(
        self,
        stream_sid: str,
        websocket: WebSocket,
        session: AudioStreamSession,
    ) -> None:
        """Register active WebSocket and streaming session."""
        async with self._get_lock():
            self._connections[stream_sid] = websocket
            self._sessions[stream_sid] = session
            self._call_map[session.call_sid] = stream_sid
            logger.info(
                "Registered telephony stream | streamSid=%s | callSid=%s | business=%s",
                stream_sid,
                session.call_sid,
                session.business_id,
            )

    async def unregister(self, stream_sid: str) -> AudioStreamSession | None:
        """Clean up active stream connection and return the closed session."""
        async with self._get_lock():
            ws = self._connections.pop(stream_sid, None)
            session = self._sessions.pop(stream_sid, None)
            if session:
                self._call_map.pop(session.call_sid, None)
                if not session.playback_cancellation_reason:
                    session.playback_cancellation_reason = "websocket_closed"
                if session.inactivity_watchdog_task and not session.inactivity_watchdog_task.done():
                    session.inactivity_watchdog_task.cancel()
                if session.current_playback_task and not session.current_playback_task.done():
                    session.current_playback_task.cancel()
                if session.sarvam_stt_task and not session.sarvam_stt_task.done():
                    session.sarvam_stt_task.cancel()
                if session.sarvam_stt_stream:
                    try:
                        asyncio.create_task(session.sarvam_stt_stream.close())
                    except Exception:
                        pass
            logger.info("Unregistered telephony stream %s", stream_sid)
            return session

    def get_session(self, stream_sid: str) -> AudioStreamSession | None:
        """Look up session by streamSid."""
        return self._sessions.get(stream_sid)

    def get_session_by_call_sid(self, call_sid: str) -> AudioStreamSession | None:
        """Look up session by callSid."""
        stream_sid = self._call_map.get(call_sid)
        return self._sessions.get(stream_sid) if stream_sid else None

    async def send_media(self, stream_sid: str, mulaw_chunk: bytes) -> bool:
        """Transmit raw 8000 Hz mu-law audio frame to telephony WebSocket (Twilio or Plivo)."""
        ws = self._connections.get(stream_sid)
        if not ws:
            return False

        # Safeguard: prevent invalid non-mulaw frames (e.g. WAV/MP3 container headers) from reaching carrier
        is_valid, reason = validate_telephony_mulaw_chunk(mulaw_chunk)
        if not is_valid:
            logger.error(
                "Blocked forwarding non-mulaw audio data to telephony WebSocket: invalid audio frame header (%s, len=%d).",
                reason,
                len(mulaw_chunk),
            )
            return False

        b64_payload = mulaw_to_base64(mulaw_chunk)
        session = self._sessions.get(stream_sid)
        is_plivo = session is not None and session.provider == "plivo"

        if is_plivo:
            message = {
                "event": "playAudio",
                "media": {
                    "contentType": "audio/x-mulaw",
                    "sampleRate": 8000,
                    "payload": b64_payload,
                },
            }
        else:
            message = {
                "event": "media",
                "streamSid": stream_sid,
                "media": {"payload": b64_payload},
            }

        try:
            await ws.send_text(json.dumps(message))
            return True
        except Exception as exc:
            logger.warning("Failed to send media frame to stream %s: %s", stream_sid, exc)
            return False

    async def send_clear(self, stream_sid: str) -> bool:
        """Send clear event to immediately flush queued audio buffer (barge-in interrupt)."""
        ws = self._connections.get(stream_sid)
        if not ws:
            return False

        session = self._sessions.get(stream_sid)
        is_plivo = session is not None and session.provider == "plivo"

        if is_plivo:
            message = {"event": "clearAudio", "streamId": stream_sid}
        else:
            message = {"event": "clear", "streamSid": stream_sid}

        try:
            await ws.send_text(json.dumps(message))
            logger.debug("Sent clear event to %s stream %s", "Plivo" if is_plivo else "Twilio", stream_sid)
            return True
        except Exception as exc:
            logger.warning("Failed to send clear to stream %s: %s", stream_sid, exc)
            return False

    async def send_mark(self, stream_sid: str, mark_name: str) -> bool:
        """Send mark event to track completion of audio playback."""
        ws = self._connections.get(stream_sid)
        if not ws:
            return False

        session = self._sessions.get(stream_sid)
        is_plivo = session is not None and session.provider == "plivo"

        if is_plivo:
            # Plivo tracks stream playback server-side; we mark session directly
            if session:
                session.is_assistant_speaking = False
            return True

        message = {
            "event": "mark",
            "streamSid": stream_sid,
            "mark": {"name": mark_name},
        }
        try:
            await ws.send_text(json.dumps(message))
            return True
        except Exception as exc:
            logger.warning("Failed to send mark to stream %s: %s", stream_sid, exc)
            return False


# Global Stream Connection Manager Singleton
stream_manager = StreamConnectionManager()
