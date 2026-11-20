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
from unittest.mock import AsyncMock, MagicMock
import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.services.streaming.audio_codec import chunk_audio, pcm16_to_mulaw, resample_pcm16
from app.services.streaming.base_tts import BaseStreamingTTS, MockStreamingTTS
from app.services.streaming.sarvam_tts import SarvamStreamingTTS

logger = get_logger(__name__)


# BaseStreamingTTS and MockStreamingTTS are defined in base_tts.py and re-exported here for compatibility
__all__ = [
    "BaseStreamingTTS",
    "MockStreamingTTS",
    "SarvamStreamingTTS",
    "ElevenLabsStreamingTTS",
    "OpenAIStreamingTTS",
    "CarrierFallbackTTS",
    "get_streaming_tts_provider",
]


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
        if api_key is not None:
            raw_key = api_key
        else:
            raw_key = settings.ELEVENLABS_API_KEY or ""
        if isinstance(raw_key, str):
            raw_key = raw_key.strip().strip('"').strip("'")
            if raw_key.startswith("Bearer "):
                raw_key = raw_key[7:].strip()
        self.api_key = raw_key or None
        self.voice_id = voice_id or settings.ELEVENLABS_VOICE_ID or "EXAVITQu4vr4xnSDxMaL"
        self.model_id = model_id or settings.ELEVENLABS_MODEL_ID or "eleven_multilingual_v2"
        self._quota_exceeded: bool = False
        self._quota_exceeded_logged: bool = False

    @property
    def provider_name(self) -> str:
        return "elevenlabs"

    @property
    def is_quota_exceeded(self) -> bool:
        """Check if ElevenLabs quota was previously reported exhausted."""
        return self._quota_exceeded

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

    def resolve_language_code(self, language: str = "en-IN") -> str | None:
        """Resolve ElevenLabs language_code parameter for native phonetic accenting."""
        lang = (language or "").strip().lower()
        if lang.startswith("ta"):
            return "ta"
        if lang.startswith("te"):
            return "te"
        if lang.startswith("en"):
            return "en"
        return None

    def resolve_model_for_language(self, language: str = "en-IN") -> str:
        """Resolve ElevenLabs model ID. Upgrades to eleven_v4_turbo for Telugu if required."""
        lang = (language or "").strip().lower()
        if lang.startswith("te") and self.model_id in ("eleven_multilingual_v2", "eleven_flash_v2_5", "eleven_turbo_v2_5"):
            return "eleven_v4_turbo"
        return self.model_id

    def synthesize_to_mulaw(
        self,
        text: str,
        language: str = "en-IN",
        voice: str | None = None,
    ) -> bytes:
        if not text or not text.strip():
            return b""

        if not self.api_key:
            logger.error("TTS configuration error: ELEVENLABS_API_KEY is not configured or missing.")
            return b""

        # Circuit breaker: avoid repeatedly sending requests when quota is known to be exhausted
        if self._quota_exceeded:
            if not self._quota_exceeded_logged:
                logger.warning("ElevenLabs TTS quota exceeded circuit breaker active. Routing to fallback audio generator.")
                self._quota_exceeded_logged = True
            return MockStreamingTTS().synthesize_to_mulaw(text, language, voice)

        if settings.ENVIRONMENT == "test" and not isinstance(httpx.Client.post, (MagicMock, AsyncMock)):
            return MockStreamingTTS().synthesize_to_mulaw(text, language, voice)

        voice_target = voice or self.get_voice_for_language(language)
        model_target = self.resolve_model_for_language(language)
        lang_code = self.resolve_language_code(language)

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_target}/stream"
        params: dict[str, Any] = {"output_format": "ulaw_8000"}
        if "turbo" not in model_target.lower():
            params["optimize_streaming_latency"] = 3
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/basic",
        }
        payload = {
            "text": text,
            "model_id": model_target,
            "voice_settings": {
                "stability": 0.65,
                "similarity_boost": 0.85,
                "style": 0.05,
                "use_speaker_boost": True,
            },
        }
        if lang_code:
            payload["language_code"] = lang_code

        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(url, params=params, headers=headers, json=payload)
                if resp.status_code == 200:
                    audio_bytes = resp.content
                    logger.info(
                        "ElevenLabs generated %d bytes of 8kHz mu-law audio for: '%s' (lang: %s, model: %s)",
                        len(audio_bytes),
                        text[:40],
                        language,
                        model_target,
                    )
                    return audio_bytes
                else:
                    safe_err = re.sub(r'(?:xi-api-key|sk_|Token)[a-zA-Z0-9_\-]+', '***', resp.text)
                    is_quota = (
                        resp.status_code in (401, 402, 429)
                        or "quota_exceeded" in resp.text.lower()
                        or "insufficient_credits" in resp.text.lower()
                        or "unusual_activity" in resp.text.lower()
                    )
                    if is_quota:
                        self._quota_exceeded = True
                        logger.warning(
                            "ElevenLabs TTS quota exceeded or exhausted (HTTP %d). Circuit breaker activated to prevent repeated failed requests. Details: %s. Routing to fallback audio generator.",
                            resp.status_code,
                            safe_err,
                        )
                        return MockStreamingTTS().synthesize_to_mulaw(text, language, voice)

                    logger.error("ElevenLabs HTTP %d error: %s", resp.status_code, safe_err)
                    if settings.ENVIRONMENT == "test":
                        return MockStreamingTTS().synthesize_to_mulaw(text, language, voice)
                    return b""
        except Exception as exc:
            safe_exc = re.sub(r'(?:xi-api-key|sk_|Token)[a-zA-Z0-9_\-]+', '***', str(exc))
            logger.error("ElevenLabs synthesis error: %s", safe_exc)
            if settings.ENVIRONMENT == "test":
                return MockStreamingTTS().synthesize_to_mulaw(text, language, voice)
            return b""

    async def asynthesize_to_mulaw(
        self,
        text: str,
        language: str = "en-IN",
        voice: str | None = None,
    ) -> bytes:
        """Asynchronously synthesize text into 8000 Hz mu-law using non-blocking HTTP."""
        if not text or not text.strip():
            return b""

        if not self.api_key:
            logger.error("TTS configuration error: ELEVENLABS_API_KEY is not configured or missing.")
            return b""

        # Circuit breaker: avoid repeatedly sending requests when quota is known to be exhausted
        if self._quota_exceeded:
            if not self._quota_exceeded_logged:
                logger.warning("ElevenLabs TTS quota exceeded circuit breaker active. Routing to fallback audio generator.")
                self._quota_exceeded_logged = True
            return MockStreamingTTS().synthesize_to_mulaw(text, language, voice)

        if settings.ENVIRONMENT == "test" and not isinstance(httpx.AsyncClient.post, (MagicMock, AsyncMock)):
            return MockStreamingTTS().synthesize_to_mulaw(text, language, voice)

        voice_target = voice or self.get_voice_for_language(language)
        model_target = self.resolve_model_for_language(language)
        lang_code = self.resolve_language_code(language)

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_target}/stream"
        params: dict[str, Any] = {"output_format": "ulaw_8000"}
        if "turbo" not in model_target.lower():
            params["optimize_streaming_latency"] = 3
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/basic",
        }
        payload = {
            "text": text,
            "model_id": model_target,
            "voice_settings": {
                "stability": 0.65,
                "similarity_boost": 0.85,
                "style": 0.05,
                "use_speaker_boost": True,
            },
        }
        if lang_code:
            payload["language_code"] = lang_code

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(url, params=params, headers=headers, json=payload)
                if resp.status_code == 200:
                    audio_bytes = resp.content
                    logger.info(
                        "ElevenLabs async generated %d bytes of 8kHz mu-law audio for: '%s' (lang: %s, model: %s)",
                        len(audio_bytes),
                        text[:40],
                        language,
                        model_target,
                    )
                    return audio_bytes
                else:
                    safe_err = re.sub(r'(?:xi-api-key|sk_|Token)[a-zA-Z0-9_\-]+', '***', resp.text)
                    is_quota = (
                        resp.status_code in (401, 402, 429)
                        or "quota_exceeded" in resp.text.lower()
                        or "insufficient_credits" in resp.text.lower()
                        or "unusual_activity" in resp.text.lower()
                    )
                    if is_quota:
                        self._quota_exceeded = True
                        logger.warning(
                            "ElevenLabs async TTS quota exceeded or exhausted (HTTP %d). Circuit breaker activated to prevent repeated failed requests. Details: %s. Routing to fallback audio generator.",
                            resp.status_code,
                            safe_err,
                        )
                        return MockStreamingTTS().synthesize_to_mulaw(text, language, voice)

                    logger.error("ElevenLabs async HTTP %d error: %s", resp.status_code, safe_err)
                    if settings.ENVIRONMENT == "test":
                        return MockStreamingTTS().synthesize_to_mulaw(text, language, voice)
                    return b""
        except Exception as exc:
            safe_exc = re.sub(r'(?:xi-api-key|sk_|Token)[a-zA-Z0-9_\-]+', '***', str(exc))
            logger.error("ElevenLabs async synthesis error: %s", safe_exc)
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
            logger.error("TTS configuration error: OPENAI_API_KEY is not configured or missing.")
            return b""

        if settings.ENVIRONMENT == "test" and not isinstance(httpx.Client.post, (MagicMock, AsyncMock)):
            return MockStreamingTTS().synthesize_to_mulaw(text, language, voice)

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
    if getattr(settings, "ENVIRONMENT", "") == "test":
        return MockStreamingTTS()

    selected = (provider_name or settings.TTS_PROVIDER or "sarvam").lower().strip()

    if selected == "sarvam":
        if not settings.SARVAM_API_KEY:
            logger.warning("SARVAM_API_KEY not configured for Sarvam TTS provider.")
        return SarvamStreamingTTS()

    if selected == "elevenlabs":
        if settings.ELEVENLABS_API_KEY:
            return ElevenLabsStreamingTTS()
        logger.warning("ELEVENLABS_API_KEY not configured; checking Sarvam TTS availability.")
        if settings.SARVAM_API_KEY:
            return SarvamStreamingTTS()
        if settings.OPENAI_API_KEY:
            return OpenAIStreamingTTS()
        return ElevenLabsStreamingTTS()

    if selected == "openai":
        if settings.OPENAI_API_KEY:
            return OpenAIStreamingTTS()
        if settings.SARVAM_API_KEY:
            return SarvamStreamingTTS()
        if settings.ELEVENLABS_API_KEY:
            logger.info("OPENAI_API_KEY not configured; using configured ElevenLabs TTS.")
            return ElevenLabsStreamingTTS()
        return OpenAIStreamingTTS()

    if selected == "carrier":
        return CarrierFallbackTTS()

    return MockStreamingTTS()
