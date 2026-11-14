"""Provider-independent abstractions for AI language models, STT, and TTS."""

from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel, Field


class LLMMessage(BaseModel):
    """Single turn message in the conversational history."""

    role: str  # "system", "user", "assistant", "tool"
    content: str
    tool_call_id: str | None = None
    name: str | None = None


class ExtractedEntities(BaseModel):
    """Key booking and customer entities extracted from conversation."""

    customer_name: str | None = None
    customer_phone: str | None = None
    service_id: str | None = None
    service_name: str | None = None
    appointment_datetime_iso: str | None = None
    appointment_id: str | None = None
    reschedule_reason: str | None = None
    cancel_reason: str | None = None
    target_date_iso: str | None = None
    doctor_or_staff_name: str | None = None


class FunctionCallRequest(BaseModel):
    """Tool/Function invocation requested by the LLM."""

    id: str
    function_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class FunctionCallResult(BaseModel):
    """Result of an executed tool/function call."""

    call_id: str
    function_name: str
    success: bool
    result: Any = None
    error: str | None = None


class LLMResponse(BaseModel):
    """Standardized response from any LLM provider."""

    text: str
    intent: str = "unknown"
    detected_language: str = "en-IN"  # "en-IN", "ta-IN", or "ta-Latn" (Tanglish)
    extracted_entities: ExtractedEntities = Field(default_factory=ExtractedEntities)
    tool_calls: list[FunctionCallRequest] = Field(default_factory=list)
    should_hangup: bool = False
    confidence: float = 1.0
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class BaseLLMProvider(ABC):
    """Abstract base class for provider-independent LLM engines."""

    @abstractmethod
    def generate_response(
        self,
        messages: list[LLMMessage],
        system_prompt: str,
        active_services: list[dict[str, Any]],
        available_tools: list[dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> LLMResponse:
        """Generate conversational response and extract entities/tool calls synchronously."""
        pass


class BaseSTTProvider(ABC):
    """Abstract base class for Speech-To-Text engines."""

    @abstractmethod
    def transcribe(
        self,
        audio_bytes: bytes,
        language: str = "en-IN",
        sample_rate: int = 8000,
    ) -> str:
        """Transcribe speech audio into text."""
        pass


class BaseTTSProvider(ABC):
    """Abstract base class for Text-To-Speech engines."""

    @abstractmethod
    def synthesize(
        self,
        text: str,
        voice: str = "alloy",
        language: str = "en-IN",
    ) -> bytes:
        """Synthesize text into speech audio bytes."""
        pass
