"""Production Speech-To-Text (STT) adapters supporting Tamil, English, and Tanglish.

Integrates:
- BaseStreamingSTT interface.
- SarvamStreamingSTT targeting Sarvam Saaras v4 real-time WebSocket and REST API.
- DeepgramStreamingSTT targeting Deepgram Nova-3.
- WhisperStreamingSTT targeting OpenAI Whisper for high-accuracy fallback.
- MockStreamingSTT for zero-cost, high-speed, deterministic automated testing.
"""

from abc import ABC, abstractmethod
import asyncio
import json
import re
from typing import Any
import urllib.parse
import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.services.streaming.audio_codec import generate_wav_container, mulaw_to_pcm16, resample_pcm16

logger = get_logger(__name__)


class BaseStreamingSTT(ABC):
    """Abstract interface for real-time speech-to-text recognition."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @abstractmethod
    def process_audio_chunk(
        self,
        pcm16_bytes: bytes,
        language: str = "en-IN",
        sample_rate: int = 8000,
    ) -> tuple[str, bool]:
        """Process incoming audio frame. Returns (transcription_text, is_final)."""
        pass

    @abstractmethod
    def flush(self, language: str = "en-IN") -> str:
        """Force finalize and transcribe any remaining buffered audio in the utterance."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset internal audio buffers for the next turn."""
        pass


class MockStreamingSTT(BaseStreamingSTT):
    """Deterministic, zero-latency Mock STT provider for unit and regression testing."""

    def __init__(self, predefined_transcripts: list[str] | None = None):
        self._buffer = bytearray()
        self._transcripts = predefined_transcripts or []
        self._call_count = 0

    @property
    def provider_name(self) -> str:
        return "mock"

    def process_audio_chunk(
        self,
        pcm16_bytes: bytes,
        language: str = "en-IN",
        sample_rate: int = 8000,
    ) -> tuple[str, bool]:
        if not pcm16_bytes:
            return "", False

        self._buffer.extend(pcm16_bytes)

        # Emit an interim transcript once buffer exceeds 8000 bytes (0.5 sec)
        if len(self._buffer) >= 8000 and self._transcripts:
            text = self._transcripts[self._call_count % len(self._transcripts)]
            return text, False

        return "", False

    def flush(self, language: str = "en-IN") -> str:
        if not self._buffer:
            return ""

        text = ""
        if self._transcripts:
            text = self._transcripts[self._call_count % len(self._transcripts)]
            self._call_count += 1
        else:
            logger.warning("MockStreamingSTT flush called without predefined transcripts. Returning empty text.")

        self.reset()
        return text

    def reset(self) -> None:
        self._buffer.clear()


class DeepgramStreamingSTT(BaseStreamingSTT):
    """Deepgram Nova-3 production streaming STT adapter.
    
    Supports:
    - English ('en-IN', 'en-US', 'en').
    - Tamil ('ta', 'ta-IN', 'ta-Latn').
    - Telugu ('te', 'te-IN', 'te-Latn').
    - Multilingual code-switching ('multi').
    - Low-latency streaming and interim/final recognition events.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        multilingual: bool = True,
        language_hints: list[str] | None = None,
    ):
        self.api_key = api_key or settings.DEEPGRAM_API_KEY
        self.model = model or getattr(settings, "DEEPGRAM_MODEL", "nova-3")
        self.multilingual = multilingual
        self.language_hints = (
            language_hints
            if language_hints is not None
            else getattr(settings, "deepgram_language_hints_list", ["ta", "en"])
        )
        self._buffer = bytearray()
        self._last_interim = ""
        self._last_detected_language: str | None = None
        self._last_detected_languages: list[str] = []
        self._last_language_confidence: float | None = None
        # Persistent HTTP client with keep-alive to eliminate per-turn SSL/TCP handshake latency
        self._client = httpx.Client(
            timeout=httpx.Timeout(15.0, connect=8.0),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20, keepalive_expiry=120.0),
        )

    @property
    def provider_name(self) -> str:
        return "deepgram"

    @property
    def last_detected_language(self) -> str | None:
        """Return the detected language reported by Deepgram on the most recent utterance."""
        return self._last_detected_language

    @property
    def last_detected_languages(self) -> list[str]:
        """Return the list of detected languages across channels/alternatives."""
        return self._last_detected_languages

    @property
    def last_language_confidence(self) -> float | None:
        """Return language detection confidence reported by Deepgram."""
        return self._last_language_confidence

    def resolve_language(self, language: str = "multi") -> str:
        """Map application language code to Deepgram Nova-3 recognized language parameter."""
        lang = (language or "").strip().lower()
        if not lang or lang in ("multi", "multilingual", "auto", "unknown", "bilingual"):
            return "multi"
        if lang.startswith("ta") or lang == "tanglish":
            return "ta"
        if lang.startswith("te") or lang == "teluglish":
            return "te"
        if lang.startswith("en"):
            return "en-IN"
        return "multi"

    def build_websocket_url(
        self,
        language: str = "multi",
        sample_rate: int = 8000,
        encoding: str = "linear16",
    ) -> str:
        """Construct real-time Deepgram Nova-3 streaming WebSocket URL with language hints."""
        lang = self.resolve_language(language)
        query_parts = [
            f"model={self.model}",
            f"language={lang}",
            f"encoding={encoding}",
            f"sample_rate={sample_rate}",
            "smart_format=true",
            "punctuate=true",
        ]
        if lang == "multi" and self.language_hints:
            for hint in self.language_hints:
                query_parts.append(f"language_hint={hint}")
        return f"wss://api.deepgram.com/v1/listen?{'&'.join(query_parts)}"

    def process_audio_chunk(
        self,
        pcm16_bytes: bytes,
        language: str = "en-IN",
        sample_rate: int = 8000,
    ) -> tuple[str, bool]:
        """Buffer incoming PCM-16 audio and detect endpointing."""
        if not pcm16_bytes:
            return "", False

        self._buffer.extend(pcm16_bytes)
        # Deepgram streaming accepts continuous chunks over WebSocket or buffered REST
        return "", False

    def flush(self, language: str = "en-IN") -> str:
        """Send complete buffered speech utterance to Deepgram REST endpoint."""
        if not self._buffer:
            return ""

        raw_pcm = bytes(self._buffer)
        self.reset()

        if not self.api_key:
            logger.error("STT configuration error: DEEPGRAM_API_KEY is not configured or missing.")
            return ""

        if len(raw_pcm) < 1600:
            return ""

        # Map Vattara language codes to Deepgram Nova-3 language parameters
        deepgram_lang = self.resolve_language(language)

        # Wrap native 8 kHz telephony PCM in standard WAV container (no interpolation distortion)
        wav_data = generate_wav_container(raw_pcm, sample_rate=8000)

        url = "https://api.deepgram.com/v1/listen"
        # Tailor keyterms to avoid cross-language acoustic bias and prevent query parameter bloat
        if deepgram_lang == "ta":
            medical_keyterms = [
                "appointment",
                "doctor",
                "consultation",
                "pediatric",
                "maruthuvar",
                "மருத்துவர்",
                "முன்பதிவு",
                "பீடியாட்ரிக் செக்கப்",
                "clinic",
                "checkup",
            ]
        elif deepgram_lang == "te":
            medical_keyterms = [
                "appointment",
                "doctor",
                "consultation",
                "pediatric",
                "vaidhyudu",
                "వైద్యుడు",
                "clinic",
                "checkup",
            ]
        else:
            medical_keyterms = [
                "appointment",
                "doctor",
                "consultation",
                "pediatric",
                "maruthuvar",
                "மருத்துவர்",
                "clinic",
                "checkup",
            ]
        params: dict[str, Any] = {
            "model": self.model,
            "language": deepgram_lang,
            "smart_format": "true",
            "punctuate": "true",
            "encoding": "linear16",
            "sample_rate": "8000",
            "keyterm": medical_keyterms,
        }
        if deepgram_lang == "multi" and self.language_hints:
            params["language_hint"] = self.language_hints

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "audio/wav",
        }

        try:
            resp = self._client.post(url, params=params, headers=headers, content=wav_data)
            if resp.status_code == 200:
                data = resp.json()
                channel = (
                    data.get("results", {})
                    .get("channels", [{}])[0]
                )
                alt = channel.get("alternatives", [{}])[0]
                transcript = alt.get("transcript", "")
                self._last_detected_language = channel.get("detected_language") or alt.get("detected_language")
                self._last_detected_languages = channel.get("languages", [])
                self._last_language_confidence = channel.get("language_confidence")
                logger.info(
                    "Deepgram transcribed [req_lang=%s, detected_lang=%s, hints=%s]: '%s'",
                    deepgram_lang,
                    self._last_detected_language or "unknown",
                    self.language_hints if deepgram_lang == "multi" else "none",
                    transcript,
                )
                return transcript
            elif resp.status_code in (401, 403):
                safe_err = re.sub(r'Token\s+[a-zA-Z0-9_\-]+', 'Token ***', resp.text)
                logger.error(
                    "Deepgram STT authentication failure (HTTP %d): Invalid or unauthorized DEEPGRAM_API_KEY. Details: %s",
                    resp.status_code,
                    safe_err,
                )
                return ""
            else:
                logger.error("Deepgram HTTP %d: %s", resp.status_code, resp.text)
                return ""
        except Exception as exc:
            logger.error("Deepgram request failed: %s", exc)
            return ""

    def reset(self) -> None:
        self._buffer.clear()
        self._last_interim = ""
        self._last_detected_language = None
        self._last_detected_languages = []
        self._last_language_confidence = None


class WhisperStreamingSTT(BaseStreamingSTT):
    """OpenAI Whisper STT adapter for high-accuracy batch and streaming transcription."""

    def __init__(self, api_key: str | None = None):
        raw_key = api_key or settings.OPENAI_API_KEY or ""
        if isinstance(raw_key, str):
            raw_key = raw_key.strip().strip('"').strip("'")
            if raw_key.startswith("Bearer "):
                raw_key = raw_key[7:].strip()
        self.api_key = raw_key or None
        self._buffer = bytearray()

    @property
    def provider_name(self) -> str:
        return "whisper"

    def process_audio_chunk(
        self,
        pcm16_bytes: bytes,
        language: str = "en-IN",
        sample_rate: int = 8000,
    ) -> tuple[str, bool]:
        if pcm16_bytes:
            self._buffer.extend(pcm16_bytes)
        return "", False

    def flush(self, language: str = "en-IN") -> str:
        if not self._buffer:
            return ""

        raw_pcm = bytes(self._buffer)
        self.reset()

        if not self.api_key:
            logger.error("STT configuration error: OPENAI_API_KEY is not configured or missing for Whisper STT.")
            return ""

        # Wrap in WAV format
        wav_data = generate_wav_container(raw_pcm, sample_rate=8000)
        if language.startswith("ta"):
            whisper_lang = "ta"
        elif language.startswith("te"):
            whisper_lang = "te"
        else:
            whisper_lang = "en"

        try:
            files = {"file": ("audio.wav", wav_data, "audio/wav")}
            data = {"model": "whisper-1", "language": whisper_lang}
            headers = {"Authorization": f"Bearer {self.api_key}"}

            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers=headers,
                    files=files,
                    data=data,
                )
                if resp.status_code == 200:
                    text = resp.json().get("text", "").strip()
                    logger.info("Whisper transcribed [%s]: '%s'", whisper_lang, text)
                    return text
                elif resp.status_code in (401, 403):
                    safe_err = re.sub(r'sk-[a-zA-Z0-9_\-]+', 'sk-***', resp.text)
                    logger.error(
                        "Whisper STT authentication failure (HTTP %d): Invalid or unauthorized OPENAI_API_KEY. Details: %s",
                        resp.status_code,
                        safe_err,
                    )
                    return ""
                else:
                    safe_err = re.sub(r'sk-[a-zA-Z0-9_\-]+', 'sk-***', resp.text)
                    logger.error("Whisper HTTP %d: %s", resp.status_code, safe_err)
                    return ""
        except Exception as exc:
            safe_exc = re.sub(r'sk-[a-zA-Z0-9_\-]+', 'sk-***', str(exc))
            logger.error("Whisper request failed: %s", safe_exc)
            return ""

    def reset(self) -> None:
        self._buffer.clear()


class SarvamRealtimeSTTStream:
    """Manages real-time bidirectional WebSocket streaming to Sarvam Saaras v4 STT."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        language_code: str | None = None,
        encoding: str | None = None,
        sample_rate: int | None = None,
        mode: str = "codemix",
        stream_type: str = "fast",
        endpointing: str = "vad",
    ):
        raw_key = api_key or settings.SARVAM_API_KEY or ""
        if isinstance(raw_key, str):
            raw_key = raw_key.strip().strip('"').strip("'")
            if raw_key.startswith("Bearer "):
                raw_key = raw_key[7:].strip()
        self.api_key = raw_key or None
        self.model = model or getattr(settings, "SARVAM_STT_MODEL", "saaras:v4")
        self.language_code = language_code or getattr(settings, "SARVAM_STT_LANGUAGE", "auto")
        self.encoding = encoding or getattr(settings, "SARVAM_STT_ENCODING", "mulaw")
        self.sample_rate = sample_rate or getattr(settings, "SARVAM_STT_SAMPLE_RATE", 8000)
        self.mode = mode
        self.stream_type = stream_type
        self.endpointing = endpointing

        self._ws: Any = None
        self._connected = False
        self._is_closing = False
        self._receive_task: asyncio.Task | None = None

    @property
    def is_connected(self) -> bool:
        return self._connected and self._ws is not None

    def build_websocket_url(self) -> str:
        """Construct real-time WebSocket URL for Sarvam Saaras v4 streaming."""
        params = {
            "model": self.model,
            "language_code": self.language_code,
            "encoding": self.encoding,
            "sample_rate": str(self.sample_rate),
            "mode": self.mode,
            "stream_type": self.stream_type,
            "endpointing": self.endpointing,
        }
        query_string = urllib.parse.urlencode(params)
        return f"wss://api.sarvam.ai/speech-to-text-realtime/ws?{query_string}"

    async def connect(self) -> bool:
        """Establish WebSocket connection to Sarvam Saaras v4."""
        if not self.api_key:
            logger.warning("Sarvam STT WebSocket disabled: SARVAM_API_KEY is not configured.")
            return False

        try:
            import inspect
            import websockets

            ws_url = self.build_websocket_url()
            headers = {"api-subscription-key": self.api_key}

            connect_kwargs: dict[str, Any] = {"open_timeout": 5.0}
            sig = inspect.signature(websockets.connect)
            if "additional_headers" in sig.parameters:
                connect_kwargs["additional_headers"] = headers
            else:
                connect_kwargs["extra_headers"] = headers

            self._ws = await websockets.connect(ws_url, **connect_kwargs)
            self._connected = True
            self._is_closing = False
            logger.info(
                "Sarvam Saaras v4 real-time STT WebSocket connected [model=%s, lang=%s, encoding=%s, rate=%d]",
                self.model,
                self.language_code,
                self.encoding,
                self.sample_rate,
            )
            return True
        except Exception as exc:
            safe_exc = re.sub(r'[a-zA-Z0-9_\-]{20,}', '***', str(exc))
            logger.warning(
                "Could not establish Sarvam STT WebSocket connection (%s). Will use REST fallback.",
                safe_exc,
            )
            self._connected = False
            self._ws = None
            return False

    async def send_audio(self, b64_audio_chunk: str) -> bool:
        """Send 20ms base64 audio chunk directly over WebSocket."""
        if not self._connected or not self._ws or self._is_closing:
            return False

        try:
            payload = json.dumps({"event": "audio_input", "audio": b64_audio_chunk})
            await self._ws.send(payload)
            return True
        except Exception as exc:
            logger.debug("Failed sending audio chunk to Sarvam STT WebSocket: %s", exc)
            self._connected = False
            return False

    async def receive_loop(
        self,
        on_speech_start: Any = None,
        on_partial: Any = None,
        on_speech_end: Any = None,
        on_final: Any = None,
    ) -> None:
        """Listen for server events and dispatch callbacks."""
        if not self._ws:
            return

        try:
            async for raw_message in self._ws:
                if self._is_closing:
                    break
                try:
                    if isinstance(raw_message, bytes):
                        raw_message = raw_message.decode("utf-8")
                    data = json.loads(raw_message)
                except Exception:
                    continue

                event = data.get("event")
                if event == "session.begin":
                    logger.debug("Sarvam STT session.begin received: req_id=%s", data.get("request_id"))
                elif event in ("vad.speech_start", "speech_start"):
                    logger.debug("Sarvam STT vad.speech_start event received")
                    if on_speech_start:
                        res = on_speech_start(data)
                        if asyncio.iscoroutine(res):
                            await res
                elif event == "transcript.partial":
                    text = (data.get("transcript") or data.get("text") or "").strip()
                    lang = data.get("language_code") or data.get("language")
                    if on_partial and text:
                        res = on_partial(text, lang)
                        if asyncio.iscoroutine(res):
                            await res
                elif event in ("vad.speech_end", "speech_end"):
                    logger.debug("Sarvam STT vad.speech_end event received")
                    if on_speech_end:
                        res = on_speech_end(data)
                        if asyncio.iscoroutine(res):
                            await res
                elif event == "transcript.final":
                    text = (data.get("transcript") or data.get("text") or "").strip()
                    lang = data.get("language_code") or data.get("language")
                    conf = data.get("language_probability") or data.get("language_confidence")
                    logger.info("Sarvam STT transcript.final received [lang=%s]: '%s'", lang, text)
                    if on_final and text:
                        res = on_final(text, lang, conf)
                        if asyncio.iscoroutine(res):
                            await res
                elif event == "error":
                    safe_err = re.sub(r'[a-zA-Z0-9_\-]{20,}', '***', data.get("message", ""))
                    logger.error("Sarvam STT WebSocket error event: %s", safe_err)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            if not self._is_closing:
                safe_exc = re.sub(r'[a-zA-Z0-9_\-]{20,}', '***', str(exc))
                logger.debug("Sarvam STT receive loop ended: %s", safe_exc)
        finally:
            self._connected = False

    async def close(self) -> None:
        """Close Sarvam STT WebSocket connection."""
        self._is_closing = True
        self._connected = False
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None


class SarvamStreamingSTT(BaseStreamingSTT):
    """Sarvam Saaras v4 production streaming and REST STT adapter.

    Supports:
    - Real-time streaming WebSocket API using model `saaras:v4` (wss://api.sarvam.ai/speech-to-text-realtime/ws).
    - Automatic multilingual language detection with `language_code=auto`.
    - Tamil, English, and Tanglish conversations, including code-mixed transcription.
    - Native 8 kHz telephony mu-law audio ingestion without lossy transcoding.
    - Partial transcripts (transcript.partial), final transcripts (transcript.final), and genuine VAD events.
    - Resilient REST fallback to https://api.sarvam.ai/speech-to-text with medical keyterm biasing.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        language_code: str = "auto",
        sample_rate: int = 8000,
        encoding: str = "mulaw",
    ):
        raw_key = api_key or settings.SARVAM_API_KEY or ""
        if isinstance(raw_key, str):
            raw_key = raw_key.strip().strip('"').strip("'")
            if raw_key.startswith("Bearer "):
                raw_key = raw_key[7:].strip()
        self.api_key = raw_key or None
        self.model = model or getattr(settings, "SARVAM_STT_MODEL", "saaras:v4")
        self.language_code = language_code or getattr(settings, "SARVAM_STT_LANGUAGE", "auto")
        self.sample_rate = sample_rate or getattr(settings, "SARVAM_STT_SAMPLE_RATE", 8000)
        self.encoding = encoding or getattr(settings, "SARVAM_STT_ENCODING", "mulaw")

        self._pcm_buffer = bytearray()
        self._mulaw_buffer = bytearray()
        self._last_interim = ""
        self._last_final = ""
        self._last_detected_language: str | None = None
        self._last_language_confidence: float | None = None

        self._client = httpx.Client(
            timeout=httpx.Timeout(15.0, connect=8.0),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20, keepalive_expiry=120.0),
        )

    @property
    def provider_name(self) -> str:
        return "sarvam"

    @property
    def last_detected_language(self) -> str | None:
        """Return the detected language reported by Sarvam Saaras v4."""
        return self._last_detected_language

    @property
    def last_language_confidence(self) -> float | None:
        """Return language detection confidence reported by Sarvam."""
        return self._last_language_confidence

    def resolve_language(self, language: str = "auto") -> str:
        """Map application language code to Sarvam Saaras v4 recognized language parameter."""
        lang = (language or "").strip().lower()
        if not lang or lang in ("auto", "multi", "multilingual", "unknown", "bilingual"):
            return "auto"
        if lang.startswith("ta-latn") or lang == "tanglish":
            return "auto"
        if lang.startswith("ta"):
            return "ta-IN"
        if lang.startswith("te-latn") or lang == "teluglish":
            return "auto"
        if lang.startswith("te"):
            return "te-IN"
        if lang.startswith("en"):
            return "en-IN"
        return "auto"

    def set_final_transcript(
        self,
        transcript: str,
        language: str | None = None,
        confidence: float | None = None,
    ) -> None:
        """Record transcript received from streaming WebSocket."""
        self._last_final = transcript
        if language:
            self._last_detected_language = language
        if confidence is not None:
            self._last_language_confidence = confidence

    def set_partial_transcript(self, transcript: str, language: str | None = None) -> None:
        """Record interim transcript received from streaming WebSocket."""
        self._last_interim = transcript
        if language:
            self._last_detected_language = language

    def process_audio_chunk(
        self,
        pcm16_bytes: bytes,
        language: str = "auto",
        sample_rate: int = 8000,
    ) -> tuple[str, bool]:
        """Buffer incoming PCM-16 audio."""
        if pcm16_bytes:
            self._pcm_buffer.extend(pcm16_bytes)
        return self._last_interim, False

    def process_mulaw_chunk(
        self,
        mulaw_bytes: bytes,
        language: str = "auto",
    ) -> tuple[str, bool]:
        """Buffer incoming native 8 kHz mu-law audio directly without transcoding."""
        if mulaw_bytes:
            self._mulaw_buffer.extend(mulaw_bytes)
        return self._last_interim, False

    def flush(self, language: str = "auto") -> str:
        """Finalize turn: return streaming transcript or execute REST transcription fallback."""
        if self._last_final and self._last_final.strip():
            transcript = self._last_final.strip()
            self.reset()
            return transcript

        raw_pcm = bytes(self._pcm_buffer)
        raw_mulaw = bytes(self._mulaw_buffer)
        self.reset()

        if not raw_pcm and not raw_mulaw:
            return ""

        if not self.api_key:
            logger.error("STT configuration error: SARVAM_API_KEY is not configured or missing.")
            return ""

        if raw_pcm:
            wav_data = generate_wav_container(raw_pcm, sample_rate=8000)
        else:
            pcm_from_mulaw = mulaw_to_pcm16(raw_mulaw)
            wav_data = generate_wav_container(pcm_from_mulaw, sample_rate=8000)

        if len(wav_data) < 1600:
            return ""

        sarvam_lang = self.resolve_language(language)
        api_lang = "unknown" if sarvam_lang == "auto" else sarvam_lang

        medical_keyterms = [
            "appointment",
            "doctor",
            "consultation",
            "pediatric",
            "maruthuvar",
            "மருத்துவர்",
            "முன்பதிவு",
            "பீடியாட்ரிக் செக்கப்",
            "clinic",
            "checkup",
        ]

        url = "https://api.sarvam.ai/speech-to-text"
        headers = {
            "api-subscription-key": self.api_key,
        }
        files = {
            "file": ("audio.wav", wav_data, "audio/wav"),
        }
        data = {
            "model": self.model,
            "language_code": api_lang,
            "mode": "codemix",
            "keyterms": json.dumps(medical_keyterms),
        }

        try:
            resp = self._client.post(url, headers=headers, data=data, files=files)
            if resp.status_code == 200:
                result = resp.json()
                transcript = result.get("transcript", "").strip()
                self._last_detected_language = result.get("language_code")
                self._last_language_confidence = result.get("language_probability")
                logger.info(
                    "Sarvam Saaras v4 REST transcribed [req_lang=%s, detected_lang=%s]: '%s'",
                    api_lang,
                    self._last_detected_language or "unknown",
                    transcript,
                )
                return transcript
            elif resp.status_code in (401, 403):
                safe_err = re.sub(r'[a-zA-Z0-9_\-]{20,}', '***', resp.text)
                logger.error(
                    "Sarvam STT authentication failure (HTTP %d): Invalid or unauthorized SARVAM_API_KEY. Details: %s",
                    resp.status_code,
                    safe_err,
                )
                return ""
            else:
                logger.error("Sarvam STT REST HTTP %d: %s", resp.status_code, resp.text)
                return ""
        except Exception as exc:
            safe_exc = re.sub(r'[a-zA-Z0-9_\-]{20,}', '***', str(exc))
            logger.error("Sarvam STT request failed: %s", safe_exc)
            return ""

    def reset(self) -> None:
        self._pcm_buffer.clear()
        self._mulaw_buffer.clear()
        self._last_interim = ""
        self._last_final = ""
        self._last_detected_language = None
        self._last_language_confidence = None


def get_streaming_stt_provider(provider_name: str | None = None) -> BaseStreamingSTT:
    """Instantiate streaming STT provider based on configuration or explicit name."""
    selected = (provider_name or settings.STT_PROVIDER or "sarvam").lower().strip()

    if selected == "sarvam":
        if not settings.SARVAM_API_KEY:
            logger.error(
                "STT Configuration Error: SARVAM_API_KEY is not configured in backend/.env. "
                "Caller speech cannot be transcribed with Sarvam Saaras v4 without a valid API key."
            )
        return SarvamStreamingSTT()
    if selected == "deepgram":
        if not settings.DEEPGRAM_API_KEY:
            logger.error(
                "STT Configuration Error: DEEPGRAM_API_KEY is not configured in backend/.env. "
                "Caller speech cannot be transcribed with Deepgram Nova-3 without a valid API key."
            )
        return DeepgramStreamingSTT()
    if selected in ("whisper", "openai"):
        if not settings.OPENAI_API_KEY:
            logger.error(
                "STT Configuration Error: OPENAI_API_KEY is not configured in backend/.env. "
                "Caller speech cannot be transcribed with Whisper STT without a valid API key."
            )
        return WhisperStreamingSTT()
    if selected == "mock":
        return MockStreamingSTT()

    logger.warning("Unrecognized STT provider '%s'; returning MockStreamingSTT.", selected)
    return MockStreamingSTT()
