"""AI Conversational Voice Engine package exports."""

from app.services.ai.base import (
    BaseLLMProvider,
    BaseSTTProvider,
    BaseTTSProvider,
    ExtractedEntities,
    FunctionCallRequest,
    FunctionCallResult,
    LLMMessage,
    LLMResponse,
)
from app.services.ai.factory import get_llm_provider
from app.services.ai.language_detector import (
    detect_language,
    get_display_language_name,
    is_tamil_script,
)
from app.services.ai.mock_provider import MockLLMProvider
from app.services.ai.openai_provider import OpenAILLMProvider
from app.services.ai.gemini_provider import GeminiLLMProvider
from app.services.ai.prompts import build_system_prompt
from app.services.ai.tools import AI_TOOLS_SPEC, execute_tool_call
from app.services.ai.voice_io import (
    DeepgramSTTAdapter,
    ElevenLabsTTSAdapter,
    TwilioSTTAdapter,
    TwilioTTSAdapter,
)

__all__ = [
    "BaseLLMProvider",
    "BaseSTTProvider",
    "BaseTTSProvider",
    "ExtractedEntities",
    "FunctionCallRequest",
    "FunctionCallResult",
    "LLMMessage",
    "LLMResponse",
    "get_llm_provider",
    "detect_language",
    "get_display_language_name",
    "is_tamil_script",
    "MockLLMProvider",
    "OpenAILLMProvider",
    "GeminiLLMProvider",
    "build_system_prompt",
    "AI_TOOLS_SPEC",
    "execute_tool_call",
    "TwilioSTTAdapter",
    "TwilioTTSAdapter",
    "DeepgramSTTAdapter",
    "ElevenLabsTTSAdapter",
]
