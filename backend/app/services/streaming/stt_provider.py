"""Production Speech-To-Text (STT) adapters supporting Tamil, English, and Tanglish.

Integrates:
- BaseStreamingSTT interface.
- MockStreamingSTT for zero-cost, high-speed, deterministic automated testing.
- DeepgramStreamingSTT targeting Deepgram Nova-2 with low-latency streaming and interim/final events.
- WhisperStreamingSTT targeting OpenAI Whisper for high-accuracy fallback.
"""

from abc import ABC, abstractmethod
import re
from typing import Any
import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.services.streaming.audio_codec import generate_wav_container, resample_pcm16

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
    ):
        self.api_key = api_key or settings.DEEPGRAM_API_KEY
        self.model = model or getattr(settings, "DEEPGRAM_MODEL", "nova-3")
        self.multilingual = multilingual
        self._buffer = bytearray()
        self._last_interim = ""

    @property
    def provider_name(self) -> str:
        return "deepgram"

    def resolve_language(self, language: str = "en-IN") -> str:
        """Map application language code to Deepgram Nova-3 recognized language parameter."""
        lang = (language or "").strip().lower()
        if lang in ("multi", "multilingual", "auto"):
            return "multi"
        if lang.startswith("ta"):
            return "ta"
        if lang.startswith("te"):
            return "te"
        if lang.startswith("en"):
            return "en-IN"
        return "multi" if self.multilingual else "en-IN"

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

        # Map Vattara language codes to Deepgram Nova-3 language parameters
        deepgram_lang = self.resolve_language(language)

        # Resample to 16 kHz for maximum Deepgram Nova-3 accuracy
        pcm16k = resample_pcm16(raw_pcm, orig_sr=8000, target_sr=16000)
        wav_data = generate_wav_container(pcm16k, sample_rate=16000)

        url = "https://api.deepgram.com/v1/listen"
        params = {
            "model": self.model,
            "language": deepgram_lang,
            "smart_format": "true",
            "punctuate": "true",
            "encoding": "linear16",
            "sample_rate": "16000",
        }
        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "audio/wav",
        }

        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(url, params=params, headers=headers, content=wav_data)
                if resp.status_code == 200:
                    data = resp.json()
                    transcript = (
                        data.get("results", {})
                        .get("channels", [{}])[0]
                        .get("alternatives", [{}])[0]
                        .get("transcript", "")
                    )
                    logger.info("Deepgram transcribed [%s]: '%s'", deepgram_lang, transcript)
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


def get_streaming_stt_provider(provider_name: str | None = None) -> BaseStreamingSTT:
    """Instantiate streaming STT provider based on configuration or explicit name."""
    selected = (provider_name or settings.STT_PROVIDER or "whisper").lower().strip()

    if selected == "deepgram":
        if not settings.DEEPGRAM_API_KEY:
            logger.error(
                "STT Configuration Error: DEEPGRAM_API_KEY is not configured in backend/.env. "
                "Caller speech cannot be transcribed with Deepgram Nova-2 without a valid API key."
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
