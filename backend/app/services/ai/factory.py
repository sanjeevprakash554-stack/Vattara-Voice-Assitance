"""Factory for instantiating provider-independent AI LLM, STT, and TTS engines."""

from app.core.config import settings
from app.core.logging import get_logger
from app.services.ai.base import BaseLLMProvider
from app.services.ai.gemini_provider import GeminiLLMProvider
from app.services.ai.mock_provider import MockLLMProvider
from app.services.ai.openai_provider import OpenAILLMProvider

logger = get_logger(__name__)


def get_llm_provider(
    provider_name: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> BaseLLMProvider:
    """Return the configured LLM provider instance.
    
    Supported values for provider_name:
    - 'mock' (for automated testing and offline environments)
    - 'openai' (uses OpenAI GPT-4o / GPT-4o-mini)
    - 'gemini' (uses Google Gemini 1.5/2.0)
    """
    selected = (provider_name or settings.AI_PROVIDER or "mock").lower().strip()
    is_production = settings.ENVIRONMENT.lower() == "production"

    if selected == "openai":
        key = api_key or settings.OPENAI_API_KEY
        if key:
            logger.info("Using OpenAILLMProvider with model '%s'", model or settings.AI_MODEL)
            return OpenAILLMProvider(api_key=key, model=model or settings.AI_MODEL)
        if is_production:
            raise ValueError("OPENAI_API_KEY is required and cannot be omitted in production environment.")
        logger.warning("OPENAI_API_KEY missing. Falling back to MockLLMProvider in development/test environment.")

    elif selected == "gemini":
        key = api_key or settings.GEMINI_API_KEY
        if key:
            chosen_model = model or settings.AI_MODEL or "gemini-3.1-flash-lite"
            logger.info("Using GeminiLLMProvider with model '%s'", chosen_model)
            return GeminiLLMProvider(api_key=key, model=chosen_model)
        if is_production:
            raise ValueError("GEMINI_API_KEY is required and cannot be omitted in production environment.")
        logger.warning("GEMINI_API_KEY missing. Falling back to MockLLMProvider in development/test environment.")

    elif is_production and selected == "mock":
        raise ValueError("MockLLMProvider cannot be used as primary provider in production environment.")

    # Default for test and offline dev environments
    return MockLLMProvider()
