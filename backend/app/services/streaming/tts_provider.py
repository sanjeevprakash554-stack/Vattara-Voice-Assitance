"""Production Text-To-Speech (TTS) streaming adapters supporting Tamil, English, and Tanglish.

Integrates:
- BaseStreamingTTS interface.
- MockStreamingTTS for fast, deterministic unit and regression testing.
- ElevenLabsStreamingTTS targeting ElevenLabs Multilingual v2 with native ulaw_8000 output.
- OpenAIStreamingTTS targeting OpenAI TTS-1 with 24kHz -> 8kHz transcoding.
- CarrierFallbackTTS for falling back to carrier TwiML <Say>.
"""

from abc import ABC, abstractmethod
import math
import re
import struct
from typing import Any
import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.services.streaming.audio_codec import chunk_audio, pcm16_to_mulaw, resample_pcm16

logger = get_logger(__name__)


class BaseStreamingTTS(ABC):
    """Abstract interface for real-time telephony voice synthesis."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @abstractmethod
    def synthesize_to_mulaw(
        self,
        text: str,
        language: str = "en-IN",
        voice: str | None = None,
    ) -> bytes:
        """Synthesize text into raw 8000 Hz, 8-bit mono ITU-T G.711 mu-law bytes."""
        pass

    def synthesize_stream_chunks(
        self,
        text: str,
        language: str = "en-IN",
        voice: str | None = None,
        chunk_size: int = 160,
    ) -> list[bytes]:
        """Synthesize text and divide into standard 20ms telephony frames (160 bytes)."""
        mulaw_data = self.synthesize_to_mulaw(text, language=language, voice=voice)
        return chunk_audio(mulaw_data, chunk_size=chunk_size)


class MockStreamingTTS(BaseStreamingTTS):
    """Deterministic, zero-latency Mock TTS generator producing valid G.711 mu-law frames."""

    @property
    def provider_name(self) -> str:
        return "mock"

    def synthesize_to_mulaw(
        self,
        text: str,
        language: str = "en-IN",
        voice: str | None = None,
    ) -> bytes:
        """Generate synthetic 400Hz audible tone in 8000 Hz mu-law for 200ms."""
        duration_sec = 0.2
        num_samples = int(8000 * duration_sec)
        samples = []
        for i in range(num_samples):
            # 400 Hz tone at 50% amplitude
            val = int(16000 * math.sin(2 * math.pi * 400 * (i / 8000.0)))
            samples.append(val)

        pcm16_raw = struct.pack(f"<{len(samples)}h", *samples)
        return pcm16_to_mulaw(pcm16_raw)


class ElevenLabsStreamingTTS(BaseStreamingTTS):
    """ElevenLabs Multilingual v2 low-latency streaming TTS adapter.
    
    Supports:
    - English ('en-IN', 'en-US').
    - Tamil ('ta-IN', 'ta-Latn') with native pronunciation.
    - Telugu ('te-IN', 'te-Latn') with native pronunciation.
    - Direct native ulaw_8000 delivery from ElevenLabs CDN.
    """

    def __init__(
        self,
        api_key: str | None = None,
        voice_id: str | None = None,
        model_id: str | None = None,
    ):
        raw_key = api_key or settings.ELEVENLABS_API_KEY or ""
        if isinstance(raw_key, str):
            raw_key = raw_key.strip().strip('"').strip("'")
            if raw_key.startswith("Bearer "):
                raw_key = raw_key[7:].strip()
        self.api_key = raw_key or None
        self.voice_id = voice_id or settings.ELEVENLABS_VOICE_ID or "EXAVITQu4vr4xnSDxMaL"
        self.model_id = model_id or settings.ELEVENLABS_MODEL_ID or "eleven_multilingual_v2"

    @property
    def provider_name(self) -> str:
        return "elevenlabs"

    def get_voice_for_language(self, language: str = "en-IN") -> str:
        """Resolve optimal ElevenLabs voice ID based on caller language preference."""
        lang = (language or "").strip().lower()
        if lang.startswith("ta"):
            return getattr(settings, "ELEVENLABS_VOICE_ID_TA", None) or self.voice_id
        if lang.startswith("te"):
            return getattr(settings, "ELEVENLABS_VOICE_ID_TE", None) or self.voice_id
        if lang.startswith("en"):
            return getattr(settings, "ELEVENLABS_VOICE_ID_EN", None) or self.voice_id
        return self.voice_id

    def synthesize_to_mulaw(
        self,
        text: str,
        language: str = "en-IN",
        voice: str | None = None,
    ) -> bytes:
        if not text or not text.strip():
            return b""

        if not self.api_key:
            if settings.ENVIRONMENT == "test":
                return MockStreamingTTS().synthesize_to_mulaw(text, language, voice)
            logger.error("TTS configuration error: ELEVENLABS_API_KEY is not configured or missing.")
            return b""

        voice_target = voice or self.get_voice_for_language(language)
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_target}/stream"
        params = {"output_format": "ulaw_8000"}
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/basic",
        }
        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "optimize_streaming_latency": 3,
            },
        }

        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(url, params=params, headers=headers, json=payload)
                if resp.status_code == 200:
                    audio_bytes = resp.content
                    logger.info(
                        "ElevenLabs generated %d bytes of 8kHz mu-law audio for: '%s'",
                        len(audio_bytes),
                        text[:40],
                    )
                    return audio_bytes
                else:
                    safe_err = re.sub(r'sk_[a-zA-Z0-9_\-]+', 'sk_***', resp.text)
                    logger.error("ElevenLabs HTTP %d error: %s", resp.status_code, safe_err)
                    if settings.ENVIRONMENT == "test":
                        return MockStreamingTTS().synthesize_to_mulaw(text, language, voice)
                    return b""
        except Exception as exc:
            safe_exc = re.sub(r'sk_[a-zA-Z0-9_\-]+', 'sk_***', str(exc))
            logger.error("ElevenLabs synthesis error: %s", safe_exc)
            if settings.ENVIRONMENT == "test":
                return MockStreamingTTS().synthesize_to_mulaw(text, language, voice)
            return b""

    def synthesize_to_mp3(
        self,
        text: str,
        voice: str | None = None,
        language: str = "en-IN",
    ) -> bytes:
        """Synthesize text directly into MP3 format (44.1kHz 128kbps) using ElevenLabs API."""
        if not text or not text.strip():
            return b""

        if not self.api_key:
            logger.error("TTS configuration error: ELEVENLABS_API_KEY is not configured or missing.")
            return b""

        voice_target = voice or self.get_voice_for_language(language)
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_target}/stream"
        params = {"output_format": "mp3_44100_128"}
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "optimize_streaming_latency": 3,
            },
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(url, params=params, headers=headers, json=payload)
                if resp.status_code == 200:
                    audio_bytes = resp.content
                    logger.info(
                        "ElevenLabs generated %d bytes of MP3 audio for: '%s'",
                        len(audio_bytes),
                        text[:40],
                    )
                    return audio_bytes
                else:
                    safe_err = re.sub(r'sk_[a-zA-Z0-9_\-]+', 'sk_***', resp.text)
                    logger.error("ElevenLabs MP3 HTTP %d error: %s", resp.status_code, safe_err)
                    return b""
        except Exception as exc:
            safe_exc = re.sub(r'sk_[a-zA-Z0-9_\-]+', 'sk_***', str(exc))
            logger.error("ElevenLabs MP3 synthesis error: %s", safe_exc)
            return b""


class OpenAIStreamingTTS(BaseStreamingTTS):
    """OpenAI TTS-1 voice synthesis adapter with real-time 24kHz PCM -> 8kHz mu-law downsampling."""

    def __init__(self, api_key: str | None = None, model: str = "tts-1"):
        raw_key = api_key or settings.OPENAI_API_KEY or ""
        if isinstance(raw_key, str):
            raw_key = raw_key.strip().strip('"').strip("'")
            if raw_key.startswith("Bearer "):
                raw_key = raw_key[7:].strip()
        self.api_key = raw_key or None
        self.model = model

    @property
    def provider_name(self) -> str:
        return "openai"

    def synthesize_to_mulaw(
        self,
        text: str,
        language: str = "en-IN",
        voice: str | None = None,
    ) -> bytes:
        if not text or not text.strip():
            return b""

        if not self.api_key:
            if settings.ENVIRONMENT == "test":
                return MockStreamingTTS().synthesize_to_mulaw(text, language, voice)
            logger.error("TTS configuration error: OPENAI_API_KEY is not configured or missing.")
            return b""

        url = "https://api.openai.com/v1/audio/speech"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": text,
            "voice": voice or "alloy",
            "response_format": "pcm",  # 24,000 Hz, 16-bit mono raw PCM
        }

        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    pcm24k = resp.content
                    # Downsample 24kHz -> 8kHz
                    pcm8k = resample_pcm16(pcm24k, orig_sr=24000, target_sr=8000)
                    # Compand to G.711 mu-law
                    return pcm16_to_mulaw(pcm8k)
                else:
                    safe_err = re.sub(r'sk-[a-zA-Z0-9_\-]+', 'sk-***', resp.text)
                    logger.error("OpenAI TTS HTTP %d error: %s", resp.status_code, safe_err)
                    if settings.ENVIRONMENT == "test":
                        return MockStreamingTTS().synthesize_to_mulaw(text, language, voice)
                    return b""
        except Exception as exc:
            safe_exc = re.sub(r'sk-[a-zA-Z0-9_\-]+', 'sk-***', str(exc))
            logger.error("OpenAI TTS request error: %s", safe_exc)
            if settings.ENVIRONMENT == "test":
                return MockStreamingTTS().synthesize_to_mulaw(text, language, voice)
            return b""


class CarrierFallbackTTS(BaseStreamingTTS):
    """Carrier TTS fallback when audio streaming is bypassed."""

    @property
    def provider_name(self) -> str:
        return "carrier"

    def synthesize_to_mulaw(
        self,
        text: str,
        language: str = "en-IN",
        voice: str | None = None,
    ) -> bytes:
        return b""


def get_streaming_tts_provider(provider_name: str | None = None) -> BaseStreamingTTS:
    """Instantiate streaming TTS provider based on configuration or explicit name."""
    selected = (provider_name or settings.TTS_PROVIDER or "openai").lower().strip()

    if selected == "elevenlabs":
        if settings.ELEVENLABS_API_KEY:
            return ElevenLabsStreamingTTS()
        logger.warning("ELEVENLABS_API_KEY not configured; checking OpenAI TTS availability.")
        if settings.OPENAI_API_KEY:
            return OpenAIStreamingTTS()
        return ElevenLabsStreamingTTS()
    if selected == "openai":
        if settings.OPENAI_API_KEY:
            return OpenAIStreamingTTS()
        if settings.ELEVENLABS_API_KEY:
            logger.info("OPENAI_API_KEY not configured; using configured ElevenLabs TTS.")
            return ElevenLabsStreamingTTS()
        return OpenAIStreamingTTS()
    if selected == "carrier":
        return CarrierFallbackTTS()
    return MockStreamingTTS()
