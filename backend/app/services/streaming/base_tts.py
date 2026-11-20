"""Base classes and mock implementations for telephony Text-To-Speech (TTS).

Provides:
- BaseStreamingTTS: Abstract base class for streaming telephony speech synthesis.
- MockStreamingTTS: Deterministic 8000 Hz G.711 mu-law audio generator for unit tests.
"""

from abc import ABC, abstractmethod
import math
import struct

from app.services.streaming.audio_codec import chunk_audio, pcm16_to_mulaw


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
        return chunk_audio(mulaw_data, chunk_size=chunk_size, pad_silence=True)

    async def asynthesize_to_mulaw(
        self,
        text: str,
        language: str = "en-IN",
        voice: str | None = None,
    ) -> bytes:
        """Asynchronously synthesize text into G.711 mu-law bytes."""
        return self.synthesize_to_mulaw(text, language=language, voice=voice)

    async def asynthesize_stream_chunks(
        self,
        text: str,
        language: str = "en-IN",
        voice: str | None = None,
        chunk_size: int = 160,
    ) -> list[bytes]:
        """Asynchronously synthesize text and divide into standard 20ms telephony frames."""
        mulaw_data = await self.asynthesize_to_mulaw(text, language=language, voice=voice)
        return chunk_audio(mulaw_data, chunk_size=chunk_size, pad_silence=True)


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
        """Generate structured melodic telephony notification earcon in 8000 Hz ITU-T G.711 mu-law.

        Uses a pleasant harmonic ascending chime (C5=523Hz -> E5=659Hz -> G5=784Hz) with
        smooth envelope shaping. This ensures fallback telephony audio is never silence and never
        an unintelligible monotone buzz.
        """
        sample_rate = 8000
        notes = [
            (523.25, 0.08),  # C5
            (659.25, 0.08),  # E5
            (783.99, 0.14),  # G5
        ]
        samples: list[int] = []
        for freq, duration in notes:
            note_samples = int(sample_rate * duration)
            for i in range(note_samples):
                t = i / note_samples
                env = math.sin(math.pi * t) ** 0.5
                val = 14000 * env * (
                    0.85 * math.sin(2 * math.pi * freq * (i / sample_rate))
                    + 0.15 * math.sin(4 * math.pi * freq * (i / sample_rate))
                )
                samples.append(int(val))

        pcm16_raw = struct.pack(f"<{len(samples)}h", *samples)
        return pcm16_to_mulaw(pcm16_raw)
