"""OpenAI LLM Provider adapter using standard HTTP requests."""

import json
from typing import Any
import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.services.ai.base import (
    BaseLLMProvider,
    ExtractedEntities,
    FunctionCallRequest,
    LLMMessage,
    LLMResponse,
)
from app.services.ai.language_detector import detect_language

logger = get_logger(__name__)


class OpenAILLMProvider(BaseLLMProvider):
    """Production provider integrating OpenAI Chat Completions API with Function Calling."""

    def __init__(self, api_key: str | None = None, model: str = "gpt-4o-mini"):
        raw_key = api_key or settings.OPENAI_API_KEY or ""
        if isinstance(raw_key, str):
            raw_key = raw_key.strip().strip('"').strip("'")
            if raw_key.startswith("Bearer "):
                raw_key = raw_key[7:].strip()
        self.api_key = raw_key or None
        self.model = model or settings.AI_MODEL or "gpt-4o-mini"
        self.endpoint = "https://api.openai.com/v1/chat/completions"

    def generate_response(
        self,
        messages: list[LLMMessage],
        system_prompt: str,
        active_services: list[dict[str, Any]],
        available_tools: list[dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> LLMResponse:
        """Call OpenAI API with chat history, system prompt, and tools."""
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not configured on the server.")

        # Prepare messages payload
        payload_messages = [{"role": "system", "content": system_prompt}]
        for m in messages:
            item: dict[str, Any] = {"role": m.role, "content": m.content}
            if m.tool_call_id:
                item["tool_call_id"] = m.tool_call_id
            if m.name:
                item["name"] = m.name
            payload_messages.append(item)

        body: dict[str, Any] = {
            "model": self.model,
            "messages": payload_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if available_tools:
            body["tools"] = available_tools
            body["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=10.0) as client:
            resp = client.post(self.endpoint, headers=headers, json=body)
            if resp.status_code != 200:
                logger.error("OpenAI API returned %s: %s", resp.status_code, resp.text)
                raise RuntimeError(f"OpenAI API error ({resp.status_code}): {resp.text}")

            result = resp.json()

        choice = result["choices"][0]["message"]
        content = choice.get("content") or ""
        tool_calls_raw = choice.get("tool_calls") or []

        parsed_tool_calls: list[FunctionCallRequest] = []
        for tc in tool_calls_raw:
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except Exception:
                args = {}
            parsed_tool_calls.append(
                FunctionCallRequest(
                    id=tc.get("id", "call_1"),
                    function_name=fn.get("name", ""),
                    arguments=args,
                )
            )

        last_user_text = next((m.content for m in reversed(messages) if m.role == "user"), "")
        detected_lang = detect_language(last_user_text or content)

        return LLMResponse(
            text=content,
            intent="function_call" if parsed_tool_calls else "conversation",
            detected_language=detected_lang,
            tool_calls=parsed_tool_calls,
            raw_metadata=result,
        )

    async def agenerate_response(
        self,
        messages: list[LLMMessage],
        system_prompt: str,
        active_services: list[dict[str, Any]],
        available_tools: list[dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> LLMResponse:
        """Call OpenAI API asynchronously with chat history, system prompt, and tools."""
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not configured on the server.")

        payload_messages = [{"role": "system", "content": system_prompt}]
        for m in messages:
            item: dict[str, Any] = {"role": m.role, "content": m.content}
            if m.tool_call_id:
                item["tool_call_id"] = m.tool_call_id
            if m.name:
                item["name"] = m.name
            payload_messages.append(item)

        body: dict[str, Any] = {
            "model": self.model,
            "messages": payload_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if available_tools:
            body["tools"] = available_tools
            body["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(self.endpoint, headers=headers, json=body)
            if resp.status_code != 200:
                logger.error("OpenAI API returned %s: %s", resp.status_code, resp.text)
                raise RuntimeError(f"OpenAI API error ({resp.status_code}): {resp.text}")

            result = resp.json()

        choice = result["choices"][0]["message"]
        content = choice.get("content") or ""
        tool_calls_raw = choice.get("tool_calls") or []

        parsed_tool_calls: list[FunctionCallRequest] = []
        for tc in tool_calls_raw:
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except Exception:
                args = {}
            parsed_tool_calls.append(
                FunctionCallRequest(
                    id=tc.get("id", "call_1"),
                    function_name=fn.get("name", ""),
                    arguments=args,
                )
            )

        last_user_text = next((m.content for m in reversed(messages) if m.role == "user"), "")
        detected_lang = detect_language(last_user_text or content)

        return LLMResponse(
            text=content,
            intent="function_call" if parsed_tool_calls else "conversation",
            detected_language=detected_lang,
            tool_calls=parsed_tool_calls,
            raw_metadata=result,
        )
