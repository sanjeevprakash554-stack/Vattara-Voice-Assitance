"""Google Gemini LLM Provider adapter using REST API with tools."""

import json
from typing import Any
import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.services.ai.base import (
    BaseLLMProvider,
    FunctionCallRequest,
    LLMMessage,
    LLMResponse,
)
from app.services.ai.language_detector import detect_language

logger = get_logger(__name__)


class GeminiLLMProvider(BaseLLMProvider):
    """Production provider integrating Google Gemini generateContent API with Function Calling."""

    def __init__(self, api_key: str | None = None, model: str = "gemini-1.5-flash"):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or "gemini-1.5-flash"

    def generate_response(
        self,
        messages: list[LLMMessage],
        system_prompt: str,
        active_services: list[dict[str, Any]],
        available_tools: list[dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> LLMResponse:
        """Call Gemini REST API with contents and function declarations."""
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured on the server.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

        # Convert messages to Gemini contents format
        contents = []
        for m in messages:
            role = "user" if m.role == "user" else "model"
            contents.append({"role": role, "parts": [{"text": m.content}]})

        body: dict[str, Any] = {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        # Convert tool spec to Gemini function declarations format if needed
        if available_tools:
            function_declarations = [
                t["function"] for t in available_tools if "function" in t
            ]
            body["tools"] = [{"functionDeclarations": function_declarations}]

        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=body)
            if resp.status_code != 200:
                logger.error("Gemini API returned %s: %s", resp.status_code, resp.text)
                raise RuntimeError(f"Gemini API error ({resp.status_code}): {resp.text}")

            result = resp.json()

        candidates = result.get("candidates", [])
        if not candidates:
            return LLMResponse(text="I apologize, but I could not process your request.", intent="unknown")

        candidate = candidates[0]
        content_parts = candidate.get("content", {}).get("parts", [])

        spoken_text = ""
        tool_calls: list[FunctionCallRequest] = []

        for p in content_parts:
            if "text" in p:
                spoken_text += p["text"]
            elif "functionCall" in p:
                fc = p["functionCall"]
                tool_calls.append(
                    FunctionCallRequest(
                        id=f"gemini_call_{len(tool_calls)+1}",
                        function_name=fc.get("name", ""),
                        arguments=fc.get("args", {}),
                    )
                )

        last_user_text = next((m.content for m in reversed(messages) if m.role == "user"), "")
        detected_lang = detect_language(last_user_text or spoken_text)

        return LLMResponse(
            text=spoken_text,
            intent="function_call" if tool_calls else "conversation",
            detected_language=detected_lang,
            tool_calls=tool_calls,
            raw_metadata=result,
        )
