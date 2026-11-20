"""Provider-independent Speech-To-Text (STT) and Text-To-Speech (TTS) interfaces."""

from app.core.logging import get_logger
from app.services.ai.base import BaseSTTProvider, BaseTTSProvider

logger = get_logger(__name__)


class DeepgramSTTAdapter(BaseSTTProvider):
    """Deepgram STT adapter prepared for real-time WebSocket streaming."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key

    def transcribe(
        self,
        audio_bytes: bytes,
        language: str = "en-IN",
        sample_rate: int = 8000,
    ) -> str:
        logger.info("Deepgram STT interface ready for audio streaming (%d bytes)", len(audio_bytes))
        return ""


class SarvamTTSAdapter(BaseTTSProvider):
    """Sarvam AI Bulbul v4 Flash TTS adapter for Indian multilingual voice synthesis."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key

    def synthesize(
        self,
        text: str,
        voice: str = "ratan",
        language: str = "en-IN",
    ) -> bytes:
        logger.info("Sarvam TTS interface ready for voice synthesis: %s (lang: %s)", text[:40], language)
        return b""


class ElevenLabsTTSAdapter(BaseTTSProvider):
    """ElevenLabs TTS adapter prepared for ultra-realistic neural voice synthesis."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key

    def synthesize(
        self,
        text: str,
        voice: str = "alloy",
        language: str = "en-IN",
    ) -> bytes:
        logger.info("ElevenLabs TTS interface ready for voice synthesis: %s", text[:40])
        return b""
