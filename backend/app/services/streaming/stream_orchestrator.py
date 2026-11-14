"""Real-Time Voice Streaming Orchestrator.

Orchestrates:
- Twilio Media Streams protocol events (connected, start, media, mark, stop).
- Voice Activity Detection (VAD) and speech frame classification.
- Immediate caller interruption (barge-in) and audio queue clearing.
- Speech-to-Text streaming and endpoint detection.
- Multilingual LLM turn processing and Phase 2 appointment function calling.
- Text-to-Speech audio chunk generation and playback streaming.
"""

import asyncio
from datetime import datetime, timezone
import json
import time
from typing import Any
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models.business import Business
from app.models.call import Call
from app.models.conversation_session import ConversationSession
from app.models.customer import Customer
from app.services.streaming.audio_codec import (
    base64_to_mulaw,
    compute_rms_energy,
    is_speech_active,
    mulaw_to_pcm16,
)
from app.services.streaming.session_manager import AudioStreamSession, stream_manager
from app.services.streaming.stt_provider import BaseStreamingSTT, get_streaming_stt_provider
from app.services.streaming.tts_provider import BaseStreamingTTS, get_streaming_tts_provider
from app.services.dashboard_events import dashboard_event_manager
from app.services.voice_assistant_service import (
    get_or_create_conversation_session,
    process_conversational_turn,
)

logger = get_logger(__name__)


class StreamOrchestrator:
    """Coordinates real-time bi-directional voice audio streaming, VAD, STT, AI, and TTS."""

    def __init__(
        self,
        stt_provider: BaseStreamingSTT | None = None,
        tts_provider: BaseStreamingTTS | None = None,
        vad_energy_threshold: float | None = None,
        silence_timeout_ms: int | None = None,
    ):
        self.stt = stt_provider or get_streaming_stt_provider()
        self.tts = tts_provider or get_streaming_tts_provider()
        self.vad_threshold = vad_energy_threshold or settings.VAD_ENERGY_THRESHOLD
        self.silence_timeout_ms = silence_timeout_ms or settings.VAD_SILENCE_TIMEOUT_MS

    async def handle_start(
        self,
        stream_sid: str,
        start_payload: dict[str, Any],
        websocket: Any,
        db: Session,
        provider: str = "twilio",
    ) -> AudioStreamSession:
        """Handle stream 'start' event (Twilio or Plivo), initialize persistent session, and stream greeting."""
        call_sid = (
            start_payload.get("callSid")
            or start_payload.get("callId")
            or start_payload.get("call_uuid")
            or start_payload.get("CallUUID")
            or f"CS_{stream_sid[:16]}"
        )
        custom_params = start_payload.get("customParameters", {})

        # Resolve business tenant from custom parameters or default active business
        business_id = custom_params.get("business_id")
        business: Business | None = None
        if business_id:
            business = db.get(Business, business_id)
        if not business:
            business = db.scalar(select(Business).where(Business.is_active.is_(True)).limit(1))

        biz_id = business.id if business else "default-biz"
        caller_phone = custom_params.get("caller_phone") or custom_params.get("from") or "+919876543210"
        dest_phone = custom_params.get("to") or (business.phone if business else "")

        # Dynamically configure tenant STT and TTS providers if configured in AssistantConfig
        if business and business.assistant_config:
            cfg = business.assistant_config
            if cfg.tts_provider:
                self.tts = get_streaming_tts_provider(cfg.tts_provider)
            if cfg.stt_provider:
                self.stt = get_streaming_stt_provider(cfg.stt_provider)

        # Initialize or retrieve persistent ConversationSession
        conv_session = get_or_create_conversation_session(
            db=db,
            call_sid=call_sid,
            business_id=biz_id,
            caller_phone=caller_phone,
        )

        stream_session = AudioStreamSession(
            stream_sid=stream_sid,
            call_sid=call_sid,
            business_id=biz_id,
            caller_phone=caller_phone,
            destination_phone=dest_phone,
            customer_name=conv_session.customer_name,
            language=conv_session.language or "en-IN",
            provider=provider,
        )

        await stream_manager.register(stream_sid, websocket, stream_session)

        # Idempotently ensure Call record exists in database
        existing_call = db.scalar(
            select(Call).where(or_(Call.id == call_sid, Call.summary.like(f"%{call_sid}%")))
        )
        if not existing_call and business:
            now = datetime.now(timezone.utc)
            provider_title = provider.capitalize()
            new_call = Call(
                id=call_sid if len(call_sid) <= 36 else str(call_sid[:36]),
                business_id=business.id,
                caller_name=conv_session.customer_name,
                caller_phone=caller_phone,
                call_type="incoming",
                status="in_progress",
                duration_seconds=0,
                summary=f"Real-Time AI Voice Stream Call via {provider_title} (Id: {call_sid})",
                initiated_at=now,
            )
            db.add(new_call)
            db.commit()

        # Dispatch real-time CALL_STARTED event to dashboard
        dashboard_event_manager.dispatch(
            business_id=biz_id,
            event_type="CALL_STARTED",
            data={
                "call_id": call_sid,
                "caller_phone": caller_phone,
                "caller_name": conv_session.customer_name or f"Caller {caller_phone}",
                "status": "in_progress",
                "call_type": "incoming",
                "language": stream_session.language,
                "provider": provider,
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        # Send initial AI Greeting
        greeting_text = self._build_greeting_text(business, stream_session.language)
        dashboard_event_manager.dispatch(
            business_id=biz_id,
            event_type="AI_RESPONSE_GENERATED",
            data={
                "call_id": call_sid,
                "speaker": "assistant",
                "text": greeting_text,
                "language": stream_session.language,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        asyncio.create_task(
            self.stream_assistant_response(
                stream_sid=stream_sid,
                text=greeting_text,
                language=stream_session.language,
            )
        )

        return stream_session

    async def handle_media(
        self,
        stream_sid: str,
        media_payload: dict[str, Any],
        db: Session,
    ) -> None:
        """Process incoming 20ms audio frame from caller, perform VAD and turn detection."""
        session = stream_manager.get_session(stream_sid)
        if not session or session.turn_in_progress:
            return

        b64_chunk = media_payload.get("payload", "")
        if not b64_chunk:
            return

        # 1. Decode base64 -> 8000Hz 8-bit mu-law -> 16-bit linear PCM
        mulaw_bytes = base64_to_mulaw(b64_chunk)
        pcm16_bytes = mulaw_to_pcm16(mulaw_bytes)

        # 2. Compute RMS frame energy
        energy = compute_rms_energy(pcm16_bytes)
        # Use elevated energy threshold when assistant is speaking to suppress acoustic echo and line noise
        effective_threshold = (
            settings.BARGE_IN_ENERGY_THRESHOLD
            if session.is_assistant_speaking
            else self.vad_threshold
        )
        has_speech = is_speech_active(energy, threshold=effective_threshold)

        if has_speech:
            session.consecutive_speech_frames += 1
            session.consecutive_silence_frames = 0
            session.inbound_pcm16_buffer.extend(pcm16_bytes)

            # BARGE-IN DETECTION: Caller interrupted assistant during speech playback
            if (
                session.is_assistant_speaking
                and settings.ENABLE_BARGE_IN
            ):
                # Suppress barge-in during initial grace period (blocks acoustic echo & playback onset reflection)
                is_in_grace_period = False
                if session.assistant_speaking_started_at is not None:
                    elapsed_ms = (time.time() - session.assistant_speaking_started_at) * 1000.0
                    if elapsed_ms < settings.BARGE_IN_GRACE_PERIOD_MS:
                        is_in_grace_period = True

                if (
                    not is_in_grace_period
                    and session.consecutive_speech_frames >= settings.BARGE_IN_MIN_SPEECH_FRAMES
                ):
                    session.trigger_barge_in()
                    await stream_manager.send_clear(stream_sid)

            if not session.is_caller_speaking and session.consecutive_speech_frames >= 3:
                session.is_caller_speaking = True
                logger.debug("Speech start detected on stream %s (Energy: %.1f)", stream_sid, energy)

        else:
            session.consecutive_silence_frames += 1
            if session.is_caller_speaking:
                session.inbound_pcm16_buffer.extend(pcm16_bytes)

                # END-OF-SPEECH DETECTION: Silence exceeds threshold (e.g. 800ms = 40 frames)
                silence_ms = session.consecutive_silence_frames * 20
                if silence_ms >= self.silence_timeout_ms:
                    logger.info(
                        "Endpoint detected on stream %s after %dms silence. Processing turn.",
                        stream_sid,
                        silence_ms,
                    )
                    session.is_caller_speaking = False
                    session.turn_in_progress = True

                    # Process caller's speech turn asynchronously
                    asyncio.create_task(self._process_completed_turn(stream_sid, db))

    async def _process_completed_turn(self, stream_sid: str, db: Session) -> None:
        """Transcribe speech, query AI conversational engine, and stream response."""
        session = stream_manager.get_session(stream_sid)
        if not session:
            return

        pcm_data = bytes(session.inbound_pcm16_buffer)
        session.reset_turn_buffer()

        if len(pcm_data) < 3200:  # Ignore clicks/background noise < 200ms
            session.turn_in_progress = False
            return

        # 1. Feed to STT
        stt_lang = (
            "multi"
            if (getattr(self.stt, "provider_name", "") == "deepgram" and getattr(self.stt, "multilingual", False) and session.language in ("en-IN", "multi"))
            else session.language
        )
        self.stt.process_audio_chunk(pcm_data, language=stt_lang)
        transcript = self.stt.flush(language=stt_lang)

        if not transcript or not transcript.strip():
            logger.debug("Empty transcription on stream %s. Ignoring turn.", stream_sid)
            session.turn_in_progress = False
            return

        logger.info("Transcribed caller speech on stream %s: '%s'", stream_sid, transcript)
        dashboard_event_manager.dispatch(
            business_id=session.business_id,
            event_type="TRANSCRIPT_RECEIVED",
            data={
                "call_id": session.call_sid,
                "speaker": "caller",
                "text": transcript,
                "language": session.language,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        # 2. Query Conversational Voice Engine & Phase 2 Tools
        business = db.get(Business, session.business_id)
        if not business:
            business = db.scalar(select(Business).where(Business.is_active.is_(True)).limit(1))

        conv_session = get_or_create_conversation_session(
            db=db,
            call_sid=session.call_sid,
            business_id=session.business_id,
            caller_phone=session.caller_phone,
        )

        response_text, should_gather = process_conversational_turn(
            db=db,
            session=conv_session,
            speech_text=transcript,
            business=business,
        )

        session.language = conv_session.language or session.language
        session.turn_in_progress = False

        dashboard_event_manager.dispatch(
            business_id=session.business_id,
            event_type="AI_RESPONSE_GENERATED",
            data={
                "call_id": session.call_sid,
                "speaker": "assistant",
                "text": response_text,
                "language": session.language,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        # 3. Stream AI response playback
        await self.stream_assistant_response(
            stream_sid=stream_sid,
            text=response_text,
            language=session.language,
        )

    async def stream_assistant_response(
        self,
        stream_sid: str,
        text: str,
        language: str = "en-IN",
    ) -> None:
        """Synthesize response and stream 20ms mu-law audio frames over WebSocket."""
        session = stream_manager.get_session(stream_sid)
        if not session or not text.strip():
            return

        logger.info(
            "Streaming assistant voice response to %s: '%s' (Lang: %s)",
            stream_sid,
            text[:50],
            language,
        )

        try:
            # Generate 20ms mu-law frames via TTS off the asyncio event loop
            chunks = await asyncio.to_thread(
                self.tts.synthesize_stream_chunks,
                text=text,
                language=language,
                chunk_size=settings.STREAM_CHUNK_SIZE_BYTES,
            )

            if not chunks:
                logger.warning("No audio chunks synthesized for text: '%s'", text[:50])
                return

            # Re-verify stream session is still active after network synthesis
            session = stream_manager.get_session(stream_sid)
            if not session:
                return

            # Set speaking state and grace period timestamp immediately before first frame transmission
            current_gen = session.playback_generation
            session.is_assistant_speaking = True
            session.assistant_speaking_started_at = time.time()
            session.reset_turn_buffer()
            session.interrupted = False

            for chunk in chunks:
                # Check for barge-in interruption before sending each frame
                if session.playback_generation != current_gen or session.interrupted:
                    logger.info(
                        "Aborted playback transmission on stream %s due to caller barge-in.",
                        stream_sid,
                    )
                    return

                sent = await stream_manager.send_media(stream_sid, chunk)
                if not sent:
                    break

                # Pace delivery at real-time rate (20ms per frame)
                await asyncio.sleep(0.018)

            # Mark playback completion
            mark_name = f"mark_{int(time.time() * 1000)}"
            await stream_manager.send_mark(stream_sid, mark_name)
        finally:
            if session:
                session.is_assistant_speaking = False
                session.assistant_speaking_started_at = None

    def handle_mark(self, stream_sid: str, mark_payload: dict[str, Any]) -> None:
        """Handle Twilio 'mark' event signifying playback finished on carrier switch."""
        session = stream_manager.get_session(stream_sid)
        if session:
            session.is_assistant_speaking = False

    async def handle_stop(
        self,
        stream_sid: str,
        stop_payload: dict[str, Any],
        db: Session,
    ) -> None:
        """Handle Twilio 'stop' event, unregister connection, and record call completion."""
        session = await stream_manager.unregister(stream_sid)
        if not session:
            return

        now = datetime.now(timezone.utc)
        duration = max(0, int((now - session.started_at).total_seconds()))

        # Update Call record
        call_record = db.scalar(
            select(Call).where(
                or_(Call.id == session.call_sid, Call.summary.like(f"%{session.call_sid}%"))
            )
        )
        if call_record:
            call_record.status = "completed"
            call_record.duration_seconds = duration
            call_record.ended_at = now
            db.commit()
            logger.info(
                "Finalized call %s after %ds on stream %s",
                session.call_sid,
                duration,
                stream_sid,
            )

        # Dispatch CALL_COMPLETED event to dashboard
        dashboard_event_manager.dispatch(
            business_id=session.business_id,
            event_type="CALL_COMPLETED",
            data={
                "call_id": session.call_sid,
                "status": "completed",
                "duration_seconds": duration,
                "ended_at": now.isoformat(),
            },
        )

    @staticmethod
    def _build_greeting_text(business: Business | None, language: str) -> str:
        biz_name = business.name if business else "Vattara Health"
        if language.startswith("ta-IN"):
            return f"வணக்கம்! {biz_name} உங்களை வரவேற்கிறது. நான் உங்களுக்கு எவ்வாறு உதவ முடியும்?"
        elif language.startswith("ta-Latn"):
            return f"Vanakkam! {biz_name}-ku ungalai varaverkirom. Naan ungalukku eppadi udhava mudiyum?"
        elif language.startswith("te-IN"):
            return f"నమస్కారం! {biz_name} కు స్వాగతం. నేను మీకు ఎలా సహాయపడగలను?"
        elif language.startswith("te-Latn"):
            return f"Namaskaram! {biz_name}-ku swagatham. Nenu meeku ela sahayapadagalanu?"
        return f"Thank you for calling {biz_name}. How can I assist you with your appointment today?"
