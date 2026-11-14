"""Audio Stream Session and WebSocket Connection Manager for real-time telephony streaming.

Manages:
- Per-call stream state, buffers, turn-taking, and VAD counters.
- Caller interruption (barge-in) state and token invalidation.
- Active WebSocket connections mapped to Twilio streamSid and callSid.
- Thread-safe outbound audio framing, marks, and clear event dispatches.
"""

import asyncio
from datetime import datetime, timezone
import json
import time
from typing import Any
from fastapi import WebSocket

from app.core.logging import get_logger
from app.services.streaming.audio_codec import mulaw_to_base64

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
        provider: str = "twilio",
    ):
        self.stream_sid = stream_sid
        self.call_sid = call_sid
        self.business_id = business_id
        self.caller_phone = caller_phone
        self.destination_phone = destination_phone
        self.customer_name = customer_name
        self.language = language
        self.provider = provider.lower()  # "twilio" or "plivo"

        # VAD & Speech State
        self.inbound_pcm16_buffer = bytearray()
        self.consecutive_speech_frames = 0
        self.consecutive_silence_frames = 0
        self.is_caller_speaking = False
        self.is_assistant_speaking = False
        self.turn_in_progress = False

        # Barge-in cancellation token & grace tracking
        self.playback_generation = 0
        self.interrupted = False
        self.assistant_speaking_started_at: float | None = None
        self.last_speech_timestamp = time.time()
        self.started_at = datetime.now(timezone.utc)

    def trigger_barge_in(self) -> int:
        """Handle caller interruption: invalidate assistant playback queue."""
        self.playback_generation += 1
        self.is_assistant_speaking = False
        self.assistant_speaking_started_at = None
        self.interrupted = True
        logger.info(
            "Barge-in triggered on Stream %s (Gen: %d). Halting assistant audio playback.",
            self.stream_sid,
            self.playback_generation,
        )
        return self.playback_generation

    def reset_turn_buffer(self) -> None:
        """Reset caller speech buffer and turn counters for next conversational turn."""
        self.inbound_pcm16_buffer.clear()
        self.consecutive_speech_frames = 0
        self.consecutive_silence_frames = 0
        self.is_caller_speaking = False
        self.turn_in_progress = False


class StreamConnectionManager:
    """Thread-safe manager for active telephony WebSocket connections and streams."""

    def __init__(self):
        self._connections: dict[str, WebSocket] = {}
        self._sessions: dict[str, AudioStreamSession] = {}
        self._call_map: dict[str, str] = {}  # call_sid -> stream_sid
        self._lock = asyncio.Lock()

    async def register(
        self,
        stream_sid: str,
        websocket: WebSocket,
        session: AudioStreamSession,
    ) -> None:
        """Register active WebSocket and streaming session."""
        async with self._lock:
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
        async with self._lock:
            ws = self._connections.pop(stream_sid, None)
            session = self._sessions.pop(stream_sid, None)
            if session:
                self._call_map.pop(session.call_sid, None)
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
