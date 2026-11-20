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
from collections import deque
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
from app.database.connection import SessionLocal
from app.services.streaming.audio_codec import (
    AdaptiveNoiseFloorTracker,
    WebRtcVoiceDetector,
    base64_to_mulaw,
    chunk_audio,
    classify_telephony_frame,
    compute_rms_energy,
    is_audio_noise_only,
    is_speech_active,
    mulaw_to_base64,
    mulaw_to_pcm16,
    pcm16_to_mulaw,
    suppress_telephony_noise,
    trim_silence_and_noise,
)
from app.services.streaming.session_manager import AudioStreamSession, stream_manager
from app.services.streaming.stt_provider import (
    BaseStreamingSTT,
    SarvamRealtimeSTTStream,
    get_streaming_stt_provider,
)
from app.services.streaming.tts_provider import BaseStreamingTTS, MockStreamingTTS, get_streaming_tts_provider
from app.services.streaming.voice_registry import get_voice_for_language, synchronize_voice_and_language
from app.services.dashboard_events import dashboard_event_manager
from app.services.voice_assistant_service import (
    get_or_create_conversation_session,
    is_unreliable_or_noise_transcript,
    process_conversational_turn,
)

logger = get_logger(__name__)


class TurnLatencyTracker:
    """Tracks latency across 10 distinct checkpoints in the real-time telephony voice pipeline."""

    def __init__(self, correlation_id: str, stream_sid: str, call_sid: str, turn_seq: int):
        self.correlation_id = correlation_id
        self.stream_sid = stream_sid
        self.call_sid = call_sid
        self.turn_seq = turn_seq
        self.checkpoints: dict[str, float] = {}
        self.meta: dict[str, Any] = {}

    def mark(self, name: str) -> float:
        now = time.perf_counter()
        self.checkpoints[name] = now
        return now

    def to_summary(self) -> dict[str, Any]:
        c = self.checkpoints
        t0 = c.get("1_last_caller_frame") or c.get("2_endpoint_detected") or 0.0

        diffs = {}
        for name, ts in c.items():
            diffs[f"{name}_ms"] = round((ts - t0) * 1000, 2) if t0 else 0.0

        stage_latencies = {}
        if "2_endpoint_detected" in c and "1_last_caller_frame" in c:
            stage_latencies["endpoint_latency_ms"] = round((c["2_endpoint_detected"] - c["1_last_caller_frame"]) * 1000, 2)
        if "4_stt_finished" in c and "3_stt_started" in c:
            stage_latencies["stt_latency_ms"] = round((c["4_stt_finished"] - c["3_stt_started"]) * 1000, 2)
        if "6_llm_started" in c and "5_context_retrieved" in c:
            stage_latencies["context_retrieval_ms"] = round((c["6_llm_started"] - c["5_context_retrieved"]) * 1000, 2)
        if "8_response_ready" in c and "6_llm_started" in c:
            stage_latencies["llm_latency_ms"] = round((c["8_response_ready"] - c["6_llm_started"]) * 1000, 2)
        if "7_tool_executed" in c and "6_llm_started" in c:
            stage_latencies["tool_latency_ms"] = round((c["7_tool_executed"] - c["6_llm_started"]) * 1000, 2)
        if "9_tts_first_chunk" in c and "8_response_ready" in c:
            stage_latencies["tts_time_to_first_chunk_ms"] = round((c["9_tts_first_chunk"] - c["8_response_ready"]) * 1000, 2)
        if "10_first_frame_sent" in c and "1_last_caller_frame" in c:
            stage_latencies["total_pipeline_latency_ms"] = round((c["10_first_frame_sent"] - c["1_last_caller_frame"]) * 1000, 2)

        return {
            "correlation_id": self.correlation_id,
            "stream_sid": self.stream_sid,
            "call_sid": self.call_sid,
            "turn_seq": self.turn_seq,
            "stage_latencies_ms": stage_latencies,
            "checkpoints_ms_from_start": diffs,
            "meta": self.meta,
        }


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
        self.vad_detector = WebRtcVoiceDetector(mode=getattr(settings, "VAD_MODE", 2))

    async def handle_start(
        self,
        stream_sid: str,
        start_payload: dict[str, Any],
        websocket: Any,
        db: Session,
        provider: str = "plivo",
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
            tts_candidate = cfg.tts_provider
            # Ensure Sarvam AI is selected as primary TTS when configured in environment
            if (
                getattr(settings, "TTS_PROVIDER", "sarvam").lower() == "sarvam"
                and getattr(settings, "SARVAM_API_KEY", None)
            ):
                if not tts_candidate or tts_candidate.lower() in ("sarvam", "elevenlabs"):
                    tts_candidate = "sarvam"
            if tts_candidate:
                self.tts = get_streaming_tts_provider(tts_candidate)
            if cfg.stt_provider:
                self.stt = get_streaming_stt_provider(cfg.stt_provider)

        # Initialize or retrieve persistent ConversationSession
        conv_session = get_or_create_conversation_session(
            db=db,
            call_sid=call_sid,
            business_id=biz_id,
            caller_phone=caller_phone,
        )

        # Resolve initial greeting language: do not prematurely assume caller language before speech evidence
        greeting_mode = getattr(settings, "DEFAULT_GREETING_MODE", "bilingual")
        if conv_session.detected_language:
            greeting_lang = conv_session.detected_language
        elif conv_session.language and conv_session.language != "en-IN":
            greeting_lang = conv_session.language
        else:
            greeting_lang = greeting_mode

        stream_session = AudioStreamSession(
            stream_sid=stream_sid,
            call_sid=call_sid,
            business_id=biz_id,
            caller_phone=caller_phone,
            destination_phone=dest_phone,
            customer_name=conv_session.customer_name,
            language=conv_session.detected_language or conv_session.language or "en-IN",
            provider=provider,
            tts_provider=self.tts.provider_name,
        )

        await stream_manager.register(stream_sid, websocket, stream_session)

        fallback_name = "none"
        if hasattr(self.tts, "get_fallback_provider"):
            try:
                fallback_name = self.tts.get_fallback_provider().provider_name
            except Exception:
                fallback_name = "none"

        logger.info(
            "Telephony stream %s registered: provider=%s, tenant=%s, primary_tts=%s, fallback_tts=%s, stt=%s, greeting_lang=%s",
            stream_sid,
            provider,
            biz_id,
            self.tts.provider_name,
            fallback_name,
            getattr(self.stt, "provider_name", "default"),
            greeting_lang,
        )

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

        # Send initial intelligent Multilingual Greeting
        greeting_text = self._build_greeting_text(business, greeting_lang)
        stream_session.update_voice_state(greeting_text)
        dashboard_event_manager.dispatch(
            business_id=biz_id,
            event_type="AI_RESPONSE_GENERATED",
            data={
                "call_id": call_sid,
                "speaker": "assistant",
                "text": greeting_text,
                "language": stream_session.active_response_language,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        asyncio.create_task(
            self.stream_assistant_response(
                stream_sid=stream_sid,
                text=greeting_text,
                language=stream_session.active_tts_language,
                voice=stream_session.active_tts_speaker,
            )
        )

        # Launch background silence and inactivity watchdog
        stream_session.inactivity_watchdog_task = asyncio.create_task(
            self._run_inactivity_watchdog(stream_sid, db)
        )

        # Launch real-time Sarvam STT WebSocket stream if configured
        if getattr(self.stt, "provider_name", "") == "sarvam":
            self._start_sarvam_stt_task(stream_sid, stream_session)

        return stream_session

    def _start_sarvam_stt_task(self, stream_sid: str, session: AudioStreamSession) -> None:
        """Initialize and maintain real-time Sarvam Saaras v4 STT streaming WebSocket connection."""
        async def _sarvam_stt_worker():
            stt_stream = SarvamRealtimeSTTStream(
                api_key=getattr(self.stt, "api_key", None),
                model=getattr(self.stt, "model", "saaras:v4"),
                language_code="auto",
                encoding="mulaw",
                sample_rate=8000,
            )
            connected = await stt_stream.connect()
            if not connected:
                return

            session.sarvam_stt_stream = stt_stream

            async def _on_speech_start(data):
                if session.is_assistant_speaking and settings.ENABLE_BARGE_IN:
                    is_in_grace = False
                    if session.assistant_speaking_started_at is not None:
                        elapsed_ms = (time.time() - session.assistant_speaking_started_at) * 1000.0
                        if elapsed_ms < settings.BARGE_IN_GRACE_PERIOD_MS:
                            is_in_grace = True
                    has_local_speech = (
                        session.consecutive_speech_frames >= 4
                        and getattr(session, "last_energy", 0.0) >= 700.0
                    )
                    if not is_in_grace and has_local_speech:
                        logger.info(
                            "Barge-in triggered via genuine Sarvam vad.speech_start on stream %s (frames=%d, energy=%.1f)",
                            stream_sid,
                            session.consecutive_speech_frames,
                            getattr(session, "last_energy", 0.0),
                        )
                        session.trigger_barge_in(reason="sarvam_speech_start")
                        await stream_manager.send_clear(stream_sid)
                    elif not is_in_grace:
                        logger.debug(
                            "Sarvam vad.speech_start ignored during assistant speech on stream %s due to low local energy (frames=%d, energy=%.1f)",
                            stream_sid,
                            session.consecutive_speech_frames,
                            getattr(session, "last_energy", 0.0),
                        )

            def _on_partial(text: str, lang: str | None):
                session.latest_partial_transcript = text
                if lang:
                    session.stt_detected_language = lang
                if hasattr(self.stt, "set_partial_transcript"):
                    self.stt.set_partial_transcript(text, lang)

            def _on_speech_end(data):
                logger.debug("Sarvam STT vad.speech_end on stream %s", stream_sid)

            def _on_final(text: str, lang: str | None, conf: float | None):
                session.latest_final_transcript = text
                session.latest_final_confidence = conf
                if lang:
                    session.stt_detected_language = lang
                if hasattr(self.stt, "set_final_transcript"):
                    self.stt.set_final_transcript(text, lang, conf)

            await stt_stream.receive_loop(
                on_speech_start=_on_speech_start,
                on_partial=_on_partial,
                on_speech_end=_on_speech_end,
                on_final=_on_final,
            )

        session.sarvam_stt_task = asyncio.create_task(_sarvam_stt_worker())

    async def handle_media(
        self,
        stream_sid: str,
        media_payload: dict[str, Any],
        db: Session,
    ) -> None:
        """Process incoming 20ms audio frame from caller, perform VAD and turn detection."""
        session = stream_manager.get_session(stream_sid)
        if not session:
            return

        session.last_frame_perf = time.perf_counter()

        b64_chunk = media_payload.get("payload", "")
        if not b64_chunk:
            return

        now_ts = time.time()

        # 1. Decode base64 -> 8000Hz 8-bit mu-law -> 16-bit linear PCM
        mulaw_bytes = base64_to_mulaw(b64_chunk)
        raw_pcm16 = mulaw_to_pcm16(mulaw_bytes)

        # High-pass filter to remove sub-250Hz rumble, DC offset, mains hum, and handling thumps
        pcm16_bytes = session.highpass_filter.process(raw_pcm16) if hasattr(session, "highpass_filter") else raw_pcm16

        # 2. Multi-stage Composite Speech Classifier (WebRTC VAD + Adaptive SNR + ZCR + Periodicity + Crest factor + Echo suppression)
        echo_settling_sec = getattr(settings, "ECHO_SETTLING_WINDOW_MS", 500) / 1000.0
        is_in_playback_echo_tail = (
            getattr(session, "assistant_speaking_ended_at", None) is not None
            and (now_ts - session.assistant_speaking_ended_at) < echo_settling_sec
        )

        has_speech, energy, vad_metrics = classify_telephony_frame(
            pcm16_bytes=pcm16_bytes,
            noise_tracker=session.noise_tracker,
            vad_detector=self.vad_detector,
            is_assistant_speaking=session.is_assistant_speaking,
            is_echo_tail=is_in_playback_echo_tail,
            base_threshold=self.vad_threshold,
            barge_in_threshold=settings.BARGE_IN_ENERGY_THRESHOLD,
            max_zcr=getattr(settings, "VAD_MAX_ZCR", 0.42),
        )
        session.last_energy = energy

        # Real-time soft noise suppression: attenuates non-speech frames by ~26dB to prevent STT hallucinations on fans/AC
        clean_pcm = suppress_telephony_noise(pcm16_bytes, session.noise_tracker.noise_floor, is_speech=has_speech)
        clean_mulaw = pcm16_to_mulaw(clean_pcm)
        clean_b64 = mulaw_to_base64(clean_mulaw)

        # Forward audio to Sarvam STT real-time WebSocket if connected
        # When assistant is speaking, only forward if caller speech has been confirmed to prevent echo feedback into STT
        if session.sarvam_stt_stream and session.sarvam_stt_stream.is_connected:
            if not session.is_assistant_speaking or has_speech:
                asyncio.create_task(session.sarvam_stt_stream.send_audio(clean_b64))

        # Track recent VAD classifications in rolling window (30 frames = 600ms)
        if not hasattr(session, "recent_vad_frames") or session.recent_vad_frames is None:
            session.recent_vad_frames = deque(maxlen=30)
        session.recent_vad_frames.append(1 if has_speech else 0)

        onset_frames_needed = getattr(settings, "VAD_SPEECH_ONSET_FRAMES", 5)
        max_speech_buffer_bytes = getattr(settings, "MAX_SPEECH_BUFFER_BYTES", 96000)

        if has_speech:
            session.consecutive_speech_frames += 1
            session.consecutive_silence_frames = 0
            session.last_speech_or_playback_at = now_ts
            session.inactivity_prompts_sent = 0

            # BARGE-IN DETECTION: Caller interrupted assistant during speech playback
            if (
                session.is_assistant_speaking
                and settings.ENABLE_BARGE_IN
            ):
                # Suppress barge-in during initial grace period (blocks acoustic echo & playback onset reflection)
                is_in_grace_period = False
                if session.assistant_speaking_started_at is not None:
                    elapsed_ms = (now_ts - session.assistant_speaking_started_at) * 1000.0
                    if elapsed_ms < settings.BARGE_IN_GRACE_PERIOD_MS:
                        is_in_grace_period = True

                if (
                    not is_in_grace_period
                    and session.consecutive_speech_frames >= settings.BARGE_IN_MIN_SPEECH_FRAMES
                ):
                    session.trigger_barge_in(reason="caller_barge_in")
                    await stream_manager.send_clear(stream_sid)
                    # Discard older assistant playback echo and preserve only caller's interruption speech
                    bytes_to_keep = settings.BARGE_IN_MIN_SPEECH_FRAMES * len(clean_pcm)
                    mulaw_bytes_to_keep = settings.BARGE_IN_MIN_SPEECH_FRAMES * len(clean_mulaw)
                    session.inbound_pcm16_buffer = (
                        bytearray(session.inbound_pcm16_buffer[-bytes_to_keep:])
                        if len(session.inbound_pcm16_buffer) > bytes_to_keep
                        else bytearray(session.inbound_pcm16_buffer)
                    )
                    session.inbound_mulaw_buffer = (
                        bytearray(session.inbound_mulaw_buffer[-mulaw_bytes_to_keep:])
                        if len(session.inbound_mulaw_buffer) > mulaw_bytes_to_keep
                        else bytearray(session.inbound_mulaw_buffer)
                    )
            else:
                # Buffer incoming speech when assistant is NOT speaking
                session.inbound_pcm16_buffer.extend(clean_pcm)
                session.inbound_mulaw_buffer.extend(clean_mulaw)

            if not session.is_caller_speaking and session.consecutive_speech_frames >= onset_frames_needed:
                session.is_caller_speaking = True
                logger.debug(
                    "Speech start detected on stream %s (Energy: %.1f, NoiseFloor: %.1f, SNR: %.1f, ZCR: %.3f)",
                    stream_sid,
                    energy,
                    vad_metrics["noise_floor"],
                    vad_metrics["snr"],
                    vad_metrics["zcr"],
                )

            # Prevent unlimited buffer accumulation even during continuous speech or loud noise bursts (> 6.0s)
            if session.is_caller_speaking and len(session.inbound_pcm16_buffer) >= max_speech_buffer_bytes:
                if session.turn_in_progress or session.turn_lock.locked():
                    logger.debug("Turn already in progress on stream %s. Deferring endpoint.", stream_sid)
                    return
                logger.info(
                    "Endpoint detected on stream %s due to max speech buffer limit reached (%d bytes / %.1fs). Processing turn.",
                    stream_sid,
                    len(session.inbound_pcm16_buffer),
                    len(session.inbound_pcm16_buffer) / 16000.0,
                )
                session.is_caller_speaking = False
                session.turn_in_progress = True
                asyncio.create_task(self._process_completed_turn(stream_sid, db, last_frame_perf=session.last_frame_perf))
                return

        else:
            session.consecutive_silence_frames += 1
            if session.is_caller_speaking:
                session.inbound_pcm16_buffer.extend(clean_pcm)
                session.inbound_mulaw_buffer.extend(clean_mulaw)

                # DYNAMIC ADAPTIVE END-OF-SPEECH DETECTION (target: 400ms-600ms)
                effective_silence_target = self.silence_timeout_ms
                if len(session.inbound_pcm16_buffer) < 24000:
                    effective_silence_target = min(400, self.silence_timeout_ms)

                silence_ms = session.consecutive_silence_frames * 20
                is_consecutive_silence = silence_ms >= effective_silence_target

                # Safe rolling/windowed silence check: tolerates isolated noise clicks/spikes during silence
                is_windowed_silence = False
                if len(session.recent_vad_frames) >= 18:
                    recent_window = list(session.recent_vad_frames)[-20:]
                    silence_count = recent_window.count(0)
                    silence_ratio = silence_count / len(recent_window)
                    # >= 85% silence in the last 360-400ms window, with at least 80ms (4 frames) of current silence
                    if silence_ratio >= 0.85 and session.consecutive_silence_frames >= 4:
                        is_windowed_silence = True

                is_buffer_limit_reached = len(session.inbound_pcm16_buffer) >= max_speech_buffer_bytes

                if is_consecutive_silence or is_windowed_silence or is_buffer_limit_reached:
                    if session.turn_in_progress or session.turn_lock.locked():
                        logger.debug("Turn already in progress on stream %s. Deferring endpoint.", stream_sid)
                        return

                    reason = "consecutive silence" if is_consecutive_silence else (
                        "windowed silence" if is_windowed_silence else "max speech buffer limit"
                    )
                    logger.info(
                        "Endpoint detected on stream %s (%s, silence: %dms, buffer: %d bytes / %.1fs). Processing turn.",
                        stream_sid,
                        reason,
                        silence_ms,
                        len(session.inbound_pcm16_buffer),
                        len(session.inbound_pcm16_buffer) / 16000.0,
                    )
                    session.is_caller_speaking = False
                    session.turn_in_progress = True

                    # Process caller's speech turn asynchronously
                    asyncio.create_task(self._process_completed_turn(stream_sid, db, last_frame_perf=session.last_frame_perf))
            else:
                # Discard old pre-speech noise clicks while caller is idle, keeping recent pre-roll buffer (300ms / 15 frames)
                max_preroll_bytes = max(15, onset_frames_needed + 5) * len(clean_pcm)
                max_preroll_mulaw = max(15, onset_frames_needed + 5) * len(clean_mulaw)
                if len(session.inbound_pcm16_buffer) > max_preroll_bytes:
                    session.inbound_pcm16_buffer = bytearray(session.inbound_pcm16_buffer[-max_preroll_bytes:])
                if len(session.inbound_mulaw_buffer) > max_preroll_mulaw:
                    session.inbound_mulaw_buffer = bytearray(session.inbound_mulaw_buffer[-max_preroll_mulaw:])

    async def _process_completed_turn(
        self,
        stream_sid: str,
        db: Session | None = None,
        last_frame_perf: float | None = None,
    ) -> None:
        """Transcribe speech, query AI conversational engine, and stream response."""
        session = stream_manager.get_session(stream_sid)
        if not session:
            return

        turn_lock_held = False
        try:
            if session.turn_lock.locked():
                logger.warning("Turn lock already held on stream %s. Ignoring overlapping endpoint.", stream_sid)
                return

            async with session.turn_lock:
                turn_lock_held = True
                session.turn_seq += 1
                correlation_id = f"turn_{session.call_sid}_{session.turn_seq}"
                tracker = TurnLatencyTracker(
                    correlation_id=correlation_id,
                    stream_sid=stream_sid,
                    call_sid=session.call_sid,
                    turn_seq=session.turn_seq,
                )
                tracker.checkpoints["1_last_caller_frame"] = last_frame_perf or time.perf_counter()
                tracker.mark("2_endpoint_detected")

                # Clean up audio buffer: trim leading/trailing noise and silence frames
                raw_pcm_data = bytes(session.inbound_pcm16_buffer)
                raw_mulaw_data = bytes(session.inbound_mulaw_buffer)
                streaming_final_transcript = session.latest_final_transcript
                streaming_confidence = session.latest_final_confidence
                stt_detected_lang = session.stt_detected_language
                session.reset_turn_buffer()

                pcm_data = trim_silence_and_noise(raw_pcm_data, vad_detector=self.vad_detector)

                # Audio quality & noise-only rejection: check if buffer is purely environmental noise or transient click
                if is_audio_noise_only(pcm_data, noise_floor=session.noise_tracker.noise_floor):
                    if not (streaming_final_transcript and len(streaming_final_transcript.split()) >= 3):
                        logger.debug(
                            "Discarded noise-only audio turn on stream %s (Turn %s, len=%d bytes, noise_floor=%.1f)",
                            stream_sid,
                            correlation_id,
                            len(pcm_data),
                            session.noise_tracker.noise_floor,
                        )
                        return

                if len(pcm_data) < 3200 and not streaming_final_transcript:  # Ignore clicks/background noise < 200ms
                    return

                # 1. Feed to STT
                tracker.mark("3_stt_started")
                if streaming_final_transcript and streaming_final_transcript.strip():
                    transcript = streaming_final_transcript.strip()
                else:
                    configured_stt_lang = (
                        getattr(settings, "SARVAM_STT_LANGUAGE", None)
                        or getattr(settings, "DEEPGRAM_LANGUAGE", "auto")
                    )
                    if session.language and (session.language.startswith("ta") or session.language.startswith("te")):
                        stt_lang = self.stt.resolve_language(session.language)
                    elif configured_stt_lang not in ("auto", "bilingual", "unknown"):
                        stt_lang = configured_stt_lang
                    else:
                        stt_lang = "auto" if getattr(self.stt, "provider_name", "") == "sarvam" else "multi"

                    if hasattr(self.stt, "process_mulaw_chunk") and raw_mulaw_data:
                        self.stt.process_mulaw_chunk(raw_mulaw_data, language=stt_lang)
                    else:
                        self.stt.process_audio_chunk(pcm_data, language=stt_lang)

                    transcript = self.stt.flush(language=stt_lang)

                tracker.mark("4_stt_finished")
                stt_detected_lang = stt_detected_lang or getattr(self.stt, "last_detected_language", None)

                # Prevent empty results from cancelling valid assistant playback
                if not transcript or not transcript.strip():
                    logger.debug("Empty transcription on stream %s (Turn %s). Ignoring turn and preserving playback.", stream_sid, correlation_id)
                    return

                # Speech confidence check: reject low-confidence (<0.30) short transcripts from noisy speech
                stt_conf = streaming_confidence or getattr(self.stt, "last_language_confidence", None)
                if stt_conf is not None and stt_conf < 0.30 and len(transcript.split()) <= 2:
                    logger.warning(
                        "Rejected low-confidence (%.2f) short transcript '%s' on stream %s",
                        stt_conf,
                        transcript,
                        stream_sid,
                    )
                    return

                # Valid caller speech confirmed! Now confirm barge-in if pending or assistant is speaking
                if session.is_barge_in_pending or session.is_assistant_speaking:
                    session.trigger_barge_in(reason="caller_barge_in")
                    await stream_manager.send_clear(stream_sid)
                    session.is_barge_in_pending = False

                logger.info("Transcribed caller speech on stream %s (Turn %s): '%s'", stream_sid, correlation_id, transcript)
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

                # 2. Query Conversational Voice Engine with thread-safe scoped DB session
                tracker.mark("5_context_retrieved")
                with SessionLocal() as scoped_db:
                    conv_session = get_or_create_conversation_session(
                        db=scoped_db,
                        call_sid=session.call_sid,
                        business_id=session.business_id,
                        caller_phone=session.caller_phone,
                    )

                    # Check for unreliable noise/echo artifacts
                    if is_unreliable_or_noise_transcript(transcript, conv_session.step):
                        logger.warning(
                            "Filtered unreliable/noise transcription on stream %s (Turn %s): '%s' (step=%s). Preserving state.",
                            stream_sid,
                            correlation_id,
                            transcript,
                            conv_session.step,
                        )
                        return

                    business = scoped_db.get(Business, session.business_id)
                    if not business:
                        business = scoped_db.scalar(select(Business).where(Business.is_active.is_(True)).limit(1))

                    tracker.mark("6_llm_started")
                    response_text, should_gather = await asyncio.to_thread(
                        process_conversational_turn,
                        db=scoped_db,
                        session=conv_session,
                        speech_text=transcript,
                        business=business,
                        require_confirmation=None,
                        llm_provider=None,
                        deepgram_detected_lang=stt_detected_lang,
                        stt_detected_lang=stt_detected_lang,
                    )
                    tracker.mark("8_response_ready")
                    if conv_session.step in ("completed", "cancelled", "transferred"):
                        tracker.mark("7_tool_executed")

                    turn_detected_lang = conv_session.detected_language or conv_session.language

                if turn_detected_lang:
                    session.language = turn_detected_lang

                resp_lang, tts_lang, active_speaker = session.update_voice_state(response_text)
                logger.info(
                    "Synchronized turn on stream %s (Turn %s): response_lang=%s, tts_lang=%s, speaker=%s (provider=%s)",
                    stream_sid,
                    correlation_id,
                    resp_lang,
                    tts_lang,
                    active_speaker,
                    self.tts.provider_name,
                )

                dashboard_event_manager.dispatch(
                    business_id=session.business_id,
                    event_type="AI_RESPONSE_GENERATED",
                    data={
                        "call_id": session.call_sid,
                        "speaker": "assistant",
                        "text": response_text,
                        "language": session.active_response_language,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

                # 3. Stream AI response playback with consistent voice identity & correlation latency tracker
                await self.stream_assistant_response(
                    stream_sid=stream_sid,
                    text=response_text,
                    language=session.active_tts_language,
                    voice=session.active_tts_speaker,
                    latency_tracker=tracker,
                )

                # 4. Telemetry logging of complete 10-point latency report
                logger.info("PIPELINE_LATENCY_REPORT: %s", json.dumps(tracker.to_summary()))

        except Exception as exc:
            logger.error("Error processing completed turn on stream %s: %s", stream_sid, exc, exc_info=True)
        finally:
            if session and turn_lock_held:
                session.turn_in_progress = False
                session.is_barge_in_pending = False

    async def stream_assistant_response(
        self,
        stream_sid: str,
        text: str,
        language: str = "en-IN",
        voice: str | None = None,
        latency_tracker: TurnLatencyTracker | None = None,
    ) -> None:
        """Synthesize response and stream 20ms mu-law audio frames over WebSocket with drift-free pacing."""
        session = stream_manager.get_session(stream_sid)
        if not session or not text.strip():
            return

        speaker_to_use = voice or (session.active_tts_speaker if session else None)

        # Cancel any active playback task on this session before acquiring the playback lock
        current_task = asyncio.current_task()
        if (
            session.current_playback_task
            and session.current_playback_task is not current_task
            and not session.current_playback_task.done()
        ):
            session.playback_cancellation_reason = "superseded_by_new_turn"
            session.current_playback_task.cancel()

        async with session.playback_lock:
            session.current_playback_task = current_task
            session.turn_in_progress = True
            session.reset_playback_metrics()

            tts_start_time = time.time()
            logger.info(
                "Streaming assistant voice response to %s: '%s' (Lang: %s, Speaker: %s, Provider: %s, Format: 8kHz mu-law)",
                stream_sid,
                text[:50],
                language,
                speaker_to_use,
                self.tts.provider_name,
            )

            try:
                current_gen = session.playback_generation
                frame_duration = 0.020  # 20ms per 160-byte frame
                frame_idx = 0
                total_bytes = 0
                start_perf: float | None = None
                pre_buffer_target = 3

                # Progressive streaming for real-time WebSocket TTS providers (Sarvam Bulbul v4 Flash)
                if hasattr(self.tts, "astream_mulaw_chunks"):
                    async for frame in self.tts.astream_mulaw_chunks(
                        text=text,
                        language=language,
                        voice=speaker_to_use,
                        chunk_size=settings.STREAM_CHUNK_SIZE_BYTES,
                    ):
                        session.frames_generated += 1
                        session.frames_queued += 1

                        if session.playback_generation != current_gen or session.interrupted:
                            logger.info(
                                "Aborted progressive playback transmission on stream %s due to caller barge-in (delivery_status=interrupted_by_caller).",
                                stream_sid,
                            )
                            return

                        # Safe barge-in hold: if caller started speaking, hold frames until STT confirms
                        while session.is_barge_in_pending and not session.interrupted and session.playback_generation == current_gen:
                            await asyncio.sleep(0.02)

                        if session.playback_generation != current_gen or session.interrupted:
                            return

                        if start_perf is None:
                            if latency_tracker:
                                latency_tracker.mark("9_tts_first_chunk")
                            session.is_assistant_speaking = True
                            session.assistant_speaking_started_at = time.time()
                            session.reset_turn_buffer()
                            session.interrupted = False
                            start_perf = time.perf_counter()
                            logger.info(
                                "First audio chunk arrived on stream %s from %s (time_to_first_audio=%.3fs, chunk_bytes=%d, codec=audio/x-mulaw, sample_rate=8000Hz)",
                                stream_sid,
                                self.tts.provider_name,
                                time.time() - tts_start_time,
                                len(frame),
                            )

                        if frame_idx < pre_buffer_target:
                            sent = await stream_manager.send_media(stream_sid, frame)
                            if not sent:
                                session.frames_rejected += 1
                                session.playback_cancellation_reason = "websocket_closed"
                                logger.warning("Stream %s failed to send pre-buffer frame %d (delivery_status=failed)", stream_sid, frame_idx)
                                return
                            session.frames_sent += 1
                            if latency_tracker and "10_first_frame_sent" not in latency_tracker.checkpoints:
                                latency_tracker.mark("10_first_frame_sent")
                            frame_idx += 1
                            total_bytes += len(frame)
                            continue

                        # Monotonic target presentation timestamp pacing
                        target_time = start_perf + (frame_idx * frame_duration)
                        sleep_sec = target_time - time.perf_counter()
                        if sleep_sec > 0.003:
                            await asyncio.sleep(sleep_sec)

                        if session.playback_generation != current_gen or session.interrupted:
                            logger.info(
                                "Aborted progressive playback transmission on stream %s due to caller barge-in (delivery_status=interrupted_by_caller).",
                                stream_sid,
                            )
                            return

                        sent = await stream_manager.send_media(stream_sid, frame)
                        if not sent:
                            session.frames_rejected += 1
                            session.playback_cancellation_reason = "websocket_closed"
                            logger.warning("Stream %s failed to send progressive frame %d (delivery_status=failed)", stream_sid, frame_idx)
                            break
                        session.frames_sent += 1
                        if latency_tracker and "10_first_frame_sent" not in latency_tracker.checkpoints:
                            latency_tracker.mark("10_first_frame_sent")
                        frame_idx += 1
                        total_bytes += len(frame)

                else:
                    # Batch synthesis for legacy/fallback TTS providers
                    if hasattr(self.tts, "asynthesize_stream_chunks"):
                        chunks = await self.tts.asynthesize_stream_chunks(
                            text=text,
                            language=language,
                            voice=speaker_to_use,
                            chunk_size=settings.STREAM_CHUNK_SIZE_BYTES,
                        )
                    else:
                        chunks = await asyncio.to_thread(
                            self.tts.synthesize_stream_chunks,
                            text=text,
                            language=language,
                            voice=speaker_to_use,
                            chunk_size=settings.STREAM_CHUNK_SIZE_BYTES,
                        )

                    if not chunks:
                        logger.error(
                            "No audio chunks synthesized by primary TTS for: '%s' (Lang: %s). Refusing to silently substitute mock audio in production.",
                            text[:50],
                            language,
                        )
                        if getattr(settings, "ENVIRONMENT", "") == "test":
                            fallback_mulaw = MockStreamingTTS().synthesize_to_mulaw(text, language=language)
                            chunks = chunk_audio(fallback_mulaw, chunk_size=settings.STREAM_CHUNK_SIZE_BYTES, pad_silence=True)
                        else:
                            return

                    if not chunks:
                        return

                    session = stream_manager.get_session(stream_sid)
                    if not session:
                        return

                    session.frames_generated += len(chunks)
                    session.frames_queued += len(chunks)
                    if latency_tracker:
                        latency_tracker.mark("9_tts_first_chunk")

                    session.is_assistant_speaking = True
                    session.assistant_speaking_started_at = time.time()
                    session.reset_turn_buffer()
                    session.interrupted = False

                    total_chunks = len(chunks)
                    start_perf = time.perf_counter()

                    logger.info(
                        "Synthesized batch audio for stream %s: chunks=%d, bytes=%d, provider=%s, codec=audio/x-mulaw, sample_rate=8000Hz",
                        stream_sid,
                        total_chunks,
                        sum(len(c) for c in chunks),
                        self.tts.provider_name,
                    )

                    pre_buffer_count = min(pre_buffer_target, total_chunks)
                    for i in range(pre_buffer_count):
                        if session.playback_generation != current_gen or session.interrupted:
                            logger.info(
                                "Aborted playback transmission on stream %s during pre-buffer (delivery_status=interrupted_by_caller).",
                                stream_sid,
                            )
                            return
                        sent = await stream_manager.send_media(stream_sid, chunks[i])
                        if not sent:
                            session.frames_rejected += 1
                            session.playback_cancellation_reason = "websocket_closed"
                            logger.warning("Stream %s failed to send batch pre-buffer frame %d (delivery_status=failed)", stream_sid, i)
                            return
                        session.frames_sent += 1
                        if latency_tracker and "10_first_frame_sent" not in latency_tracker.checkpoints:
                            latency_tracker.mark("10_first_frame_sent")
                        frame_idx += 1
                        total_bytes += len(chunks[i])

                    for idx in range(pre_buffer_count, total_chunks):
                        if session.playback_generation != current_gen or session.interrupted:
                            logger.info(
                                "Aborted playback transmission on stream %s due to caller barge-in (delivery_status=interrupted_by_caller).",
                                stream_sid,
                            )
                            return

                        # Safe barge-in hold
                        while session.is_barge_in_pending and not session.interrupted and session.playback_generation == current_gen:
                            await asyncio.sleep(0.02)

                        if session.playback_generation != current_gen or session.interrupted:
                            return

                        target_time = start_perf + (idx * frame_duration)
                        sleep_sec = target_time - time.perf_counter()
                        if sleep_sec > 0.003:
                            await asyncio.sleep(sleep_sec)

                        sent = await stream_manager.send_media(stream_sid, chunks[idx])
                        if not sent:
                            session.frames_rejected += 1
                            session.playback_cancellation_reason = "websocket_closed"
                            logger.warning("Stream %s failed to send batch frame %d (delivery_status=failed)", stream_sid, idx)
                            break
                        session.frames_sent += 1
                        frame_idx += 1
                        total_bytes += len(chunks[idx])

                if frame_idx > 0 and start_perf is not None:
                    elapsed = time.perf_counter() - start_perf
                    expected_sec = frame_idx * frame_duration
                    session.playback_completed = True
                    session.playback_cancellation_reason = None
                    logger.info(
                        "Completed audio playback on stream %s: chunks=%d, bytes=%d, actual_sec=%.3f, expected_sec=%.3f, provider=%s, delivery_status=success",
                        stream_sid,
                        frame_idx,
                        total_bytes,
                        elapsed,
                        expected_sec,
                        self.tts.provider_name,
                    )
                    mark_name = f"mark_{int(time.time() * 1000)}"
                    await stream_manager.send_mark(stream_sid, mark_name)

            except asyncio.CancelledError:
                if session and not session.playback_cancellation_reason:
                    session.playback_cancellation_reason = "internal_error"
                logger.info(
                    "Playback task for stream %s cancelled cleanly (reason=%s).",
                    stream_sid,
                    getattr(session, "playback_cancellation_reason", "unknown"),
                )
                raise
            finally:
                if session:
                    session.is_assistant_speaking = False
                    session.assistant_speaking_started_at = None
                    session.assistant_speaking_ended_at = time.time()
                    session.last_speech_or_playback_at = time.time()
                    session.reset_turn_buffer()
                    session.consecutive_speech_frames = 0
                    session.consecutive_silence_frames = 0
                    session.turn_in_progress = False
                    if session.current_playback_task is current_task:
                        session.current_playback_task = None

    def handle_mark(self, stream_sid: str, mark_payload: dict[str, Any]) -> None:
        """Handle Twilio 'mark' event signifying playback finished on carrier switch."""
        session = stream_manager.get_session(stream_sid)
        if session:
            session.is_assistant_speaking = False
            session.assistant_speaking_ended_at = time.time()

    async def handle_stop(
        self,
        stream_sid: str,
        stop_payload: dict[str, Any],
        db: Session,
    ) -> None:
        """Handle Twilio 'stop' event, unregister connection, and record call completion."""
        existing_session = stream_manager.get_session(stream_sid)
        if existing_session and not existing_session.playback_cancellation_reason:
            existing_session.playback_cancellation_reason = "websocket_closed"

        session = await stream_manager.unregister(stream_sid)
        if not session:
            return

        session.playback_cancellation_reason = "websocket_closed"
        if session.current_playback_task and not session.current_playback_task.done():
            session.current_playback_task.cancel()

        if session.inactivity_watchdog_task and not session.inactivity_watchdog_task.done():
            session.inactivity_watchdog_task.cancel()

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

    async def _run_inactivity_watchdog(self, stream_sid: str, db: Session) -> None:
        """Monitor caller silence and deliver staged, gentle check-ins before concluding."""
        logger.info("Inactivity watchdog started for stream %s", stream_sid)
        try:
            while True:
                await asyncio.sleep(1.0)
                session = stream_manager.get_session(stream_sid)
                if not session:
                    break

                # If turn or playback in progress, or caller speaking, keep timer fresh
                if (
                    session.is_caller_speaking
                    or session.is_assistant_speaking
                    or session.turn_in_progress
                    or session.is_handling_inactivity
                ):
                    continue

                now = time.time()
                silence_duration = now - session.last_speech_or_playback_at

                # Stage 1: Gentle check after first silence interval (default 6s)
                if silence_duration >= settings.CALLER_INACTIVITY_PROMPT_1_SEC and session.inactivity_prompts_sent == 0:
                    session.inactivity_prompts_sent = 1
                    session.is_handling_inactivity = True
                    prompt_1 = self._build_inactivity_prompt(session.active_response_language, stage=1)
                    logger.info("Delivering 1st silence prompt on stream %s (silence=%.1fs): '%s'", stream_sid, silence_duration, prompt_1)
                    await self.stream_assistant_response(
                        stream_sid=stream_sid,
                        text=prompt_1,
                        language=session.active_tts_language,
                        voice=session.active_tts_speaker,
                    )
                    session.last_speech_or_playback_at = time.time()
                    session.is_handling_inactivity = False

                # Stage 2: Second check after additional silence (default 14s total)
                elif silence_duration >= (settings.CALLER_INACTIVITY_PROMPT_2_SEC - settings.CALLER_INACTIVITY_PROMPT_1_SEC) and session.inactivity_prompts_sent == 1:
                    session.inactivity_prompts_sent = 2
                    session.is_handling_inactivity = True
                    prompt_2 = self._build_inactivity_prompt(session.active_response_language, stage=2)
                    logger.info("Delivering 2nd silence prompt on stream %s (silence=%.1fs): '%s'", stream_sid, silence_duration, prompt_2)
                    await self.stream_assistant_response(
                        stream_sid=stream_sid,
                        text=prompt_2,
                        language=session.active_tts_language,
                        voice=session.active_tts_speaker,
                    )
                    session.last_speech_or_playback_at = time.time()
                    session.is_handling_inactivity = False

                # Stage 3: Maximum silence exceeded (default 180s total) -> graceful conclusion
                elif silence_duration >= (settings.CALLER_MAX_INACTIVITY_SEC - settings.CALLER_INACTIVITY_PROMPT_2_SEC) and session.inactivity_prompts_sent >= 2:
                    prompt_final = self._build_inactivity_prompt(session.active_response_language, stage=3)
                    logger.info("Max silence reached on stream %s. Delivering graceful exit: '%s'", stream_sid, prompt_final)
                    await self.stream_assistant_response(
                        stream_sid=stream_sid,
                        text=prompt_final,
                        language=session.active_tts_language,
                        voice=session.active_tts_speaker,
                    )
                    await asyncio.sleep(1.5)
                    if session.websocket:
                        try:
                            await session.websocket.close(code=1000, reason="Inactivity timeout")
                        except Exception:
                            pass
                    break

        except asyncio.CancelledError:
            logger.debug("Inactivity watchdog cleanly cancelled for stream %s", stream_sid)
        except Exception as exc:
            logger.warning("Error in inactivity watchdog for stream %s: %s", stream_sid, exc)

    @staticmethod
    def _build_inactivity_prompt(language: str, stage: int = 1) -> str:
        """Construct localized gentle silence recovery prompts."""
        lang = (language or "en-IN").strip().lower()
        if lang.startswith("ta"):
            if stage == 1:
                return "வணக்கம், நீங்கள் லைனில் இருக்கிறீர்களா? நான் உதவ காத்திருக்கிறேன்."
            elif stage == 2:
                return "உங்கள் குரல் கேட்கவில்லை. நீங்கள் பேசும்போது தொடங்கலாம்."
            return "அழைப்பு முடிவடைகிறது. மீண்டும் அழைக்கவும். வணக்கம்."
        elif lang.startswith("te"):
            if stage == 1:
                return "హలో, మీరు లైన్‌లో ఉన్నారా? నేను మీకు సహాయం చేయడానికి ఇక్కడే ఉన్నాను."
            elif stage == 2:
                return "మీ స్వరం వినపడటం లేదు. మీరు మాట్లాడినప్పుడు నేను సహాయం చేస్తాను."
            return "కాల్ ముగుస్తోంది. దయచేసి మళ్ళీ కాల్ చేయండి. నమస్కారం."
        else:
            if stage == 1:
                return "Hello, are you still there? I'm here to help."
            elif stage == 2:
                return "I'm still having trouble hearing you. Please let me know how I can help."
            return "Thank you for calling Vattara Health. Goodbye."

    @staticmethod
    def _build_greeting_text(business: Business | None, language: str = "bilingual") -> str:
        biz_name = (business.name if business and business.name else "").strip() or "our clinic"
        lang = (language or "").strip().lower()

        if lang in ("bilingual", "multi", "auto"):
            tpl = getattr(
                settings,
                "GREETING_TEMPLATE_BILINGUAL",
                "வணக்கம்! Welcome to {business_name}. How can I help you today?",
            )
            return tpl.format(business_name=biz_name)
        elif lang.startswith("ta-in") or lang == "ta":
            tpl = getattr(
                settings,
                "GREETING_TEMPLATE_TAMIL",
                "வணக்கம்! {business_name}. உங்களுக்கு எப்படி உதவலாம்?",
            )
            return tpl.format(business_name=biz_name)
        elif lang.startswith("ta-latn"):
            tpl = getattr(
                settings,
                "GREETING_TEMPLATE_TANGLISH",
                "Vanakkam! {business_name}. Ungalukku eppadi udhavalam?",
            )
            return tpl.format(business_name=biz_name)
        elif lang.startswith("te-in") or lang == "te":
            tpl = getattr(
                settings,
                "GREETING_TEMPLATE_TELUGU",
                "నమస్కారం! {business_name} కు స్వాగతం. నేను మీకు ఎలా సహాయపడగలను?",
            )
            return tpl.format(business_name=biz_name)
        elif lang.startswith("te-latn"):
            tpl = getattr(
                settings,
                "GREETING_TEMPLATE_TELUGLISH",
                "Namaskaram! {business_name}-ku swagatham. Nenu meeku ela sahayapadagalanu?",
            )
            return tpl.format(business_name=biz_name)
        elif lang.startswith("en"):
            tpl = getattr(
                settings,
                "GREETING_TEMPLATE_ENGLISH",
                "Hello! Thank you for calling {business_name}. How may I help you?",
            )
            return tpl.format(business_name=biz_name)

        tpl = getattr(
            settings,
            "GREETING_TEMPLATE_BILINGUAL",
            "வணக்கம்! Welcome to {business_name}. How can I help you today?",
        )
        return tpl.format(business_name=biz_name)
