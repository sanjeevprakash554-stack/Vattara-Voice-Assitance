"""Google Gemini LLM Provider adapter using REST API with tools."""

import asyncio
import json
import random
import re
import time
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


class GeminiCircuitOpenError(RuntimeError):
    """Raised when Gemini Circuit Breaker is OPEN due to repeated 503/429 failures."""
    pass


class GeminiTimeoutError(RuntimeError):
    """Raised when Gemini LLM request exceeds the bounded overall turn timeout."""
    pass


class GeminiCircuitBreaker:
    """In-memory Circuit Breaker with metrics for Gemini REST API."""

    def __init__(self, failure_threshold: int = 3, recovery_timeout_sec: float = 15.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.consecutive_failures = 0
        self.last_failure_time = 0.0

        # Detailed operational metrics
        self.total_calls = 0
        self.total_503_errors = 0
        self.total_429_errors = 0
        self.total_retries = 0
        self.total_fallbacks = 0
        self.total_circuit_trips = 0

    def can_execute(self) -> bool:
        """Check if request is permitted through circuit breaker."""
        now = time.time()
        if self.state == "OPEN":
            if now - self.last_failure_time >= self.recovery_timeout_sec:
                self.state = "HALF_OPEN"
                logger.info("Gemini Circuit Breaker entered HALF_OPEN state; permitting probe request.")
                return True
            return False
        return True

    def record_success(self) -> None:
        """Record successful Gemini API response."""
        if self.state in ("OPEN", "HALF_OPEN"):
            logger.info("Gemini Circuit Breaker recovered to CLOSED state.")
        self.state = "CLOSED"
        self.consecutive_failures = 0

    def record_failure(self, status_code: int | None = None) -> None:
        """Record failed Gemini API response and update state."""
        self.consecutive_failures += 1
        self.last_failure_time = time.time()

        if status_code == 503:
            self.total_503_errors += 1
        elif status_code == 429:
            self.total_429_errors += 1

        if self.consecutive_failures >= self.failure_threshold:
            if self.state != "OPEN":
                self.total_circuit_trips += 1
                self.state = "OPEN"
                logger.warning(
                    "Gemini Circuit Breaker TRIPPED to OPEN after %d consecutive failures (cooling down for %.1fs).",
                    self.consecutive_failures,
                    self.recovery_timeout_sec,
                )

    def record_retry(self) -> None:
        self.total_retries += 1

    def record_fallback(self) -> None:
        self.total_fallbacks += 1

    def reset_metrics(self) -> None:
        self.total_calls = 0
        self.total_503_errors = 0
        self.total_429_errors = 0
        self.total_retries = 0
        self.total_fallbacks = 0
        self.total_circuit_trips = 0
        self.consecutive_failures = 0
        self.state = "CLOSED"

    def get_metrics(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "consecutive_failures": self.consecutive_failures,
            "total_calls": self.total_calls,
            "total_503_errors": self.total_503_errors,
            "total_429_errors": self.total_429_errors,
            "total_retries": self.total_retries,
            "total_fallbacks": self.total_fallbacks,
            "total_circuit_trips": self.total_circuit_trips,
        }


# Global singleton instance for operational tracking
gemini_circuit_breaker = GeminiCircuitBreaker()


def _mask_key(key: str | None) -> str:
    """Safely mask API key for logging purposes."""
    if not key or len(key) < 8:
        return "***"
    return f"{key[:6]}...{key[-4:]}"


def _format_gemini_contents(messages: list[LLMMessage | dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert standardized LLMMessages or dicts into alternating Gemini contents format."""
    raw_turns: list[dict[str, Any]] = []

    for m in messages:
        role = m.role if hasattr(m, "role") else m.get("role", "user")
        content = m.content if hasattr(m, "content") else m.get("content", "")
        raw_parts = getattr(m, "raw_parts", None) or (m.get("raw_parts") if isinstance(m, dict) else None)
        name = getattr(m, "name", None) or (m.get("name") if isinstance(m, dict) else None)

        if role == "user":
            raw_turns.append({"role": "user", "parts": [{"text": content}]})
        elif role in ("assistant", "model"):
            if raw_parts:
                raw_turns.append({"role": "model", "parts": raw_parts})
            else:
                raw_turns.append({"role": "model", "parts": [{"text": content or ""}]})
        elif role == "tool":
            try:
                resp_obj = json.loads(content) if isinstance(content, str) else content
            except Exception:
                resp_obj = {"output": content}
            raw_turns.append({
                "role": "function",
                "parts": [{
                    "functionResponse": {
                        "name": name or "tool",
                        "response": resp_obj,
                    }
                }],
            })

    # Gemini requires alternating roles; merge consecutive turns with the same role
    merged: list[dict[str, Any]] = []
    for turn in raw_turns:
        if merged and merged[-1]["role"] == turn["role"]:
            merged[-1]["parts"].extend(turn["parts"])
        else:
            merged.append(turn)

    # Gemini requires conversations to start with a 'user' turn
    if merged and merged[0]["role"] not in ("user", "model"):
        merged.insert(0, {"role": "user", "parts": [{"text": "Hello"}]})

    return merged


class GeminiLLMProvider(BaseLLMProvider):
    """Production provider integrating Google Gemini generateContent API with Function Calling."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        raw_key = api_key or settings.GEMINI_API_KEY or ""
        if isinstance(raw_key, str):
            raw_key = raw_key.strip().strip('"').strip("'")
            if raw_key.startswith("Bearer "):
                raw_key = raw_key[7:].strip()
        self.api_key = raw_key or None
        self.model = model or settings.AI_MODEL or "gemini-3.1-flash-lite"
        # Persistent HTTP connection pools to avoid per-turn TLS/TCP handshake overhead
        self._sync_client = httpx.Client(
            timeout=httpx.Timeout(15.0, connect=8.0),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20, keepalive_expiry=120.0),
        )
        self._async_client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=8.0),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20, keepalive_expiry=120.0),
        )

    def _build_request_body(
        self,
        messages: list[LLMMessage],
        system_prompt: str,
        available_tools: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Construct the Gemini generateContent REST payload."""
        contents = _format_gemini_contents(messages)

        body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        if system_prompt:
            body["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        if available_tools:
            function_declarations = [
                t["function"] for t in available_tools if "function" in t
            ]
            if function_declarations:
                body["tools"] = [{"functionDeclarations": function_declarations}]

        return body

    def _parse_candidate_response(
        self,
        result: dict[str, Any],
        messages: list[LLMMessage],
    ) -> LLMResponse:
        """Parse Gemini REST response into standardized LLMResponse."""
        candidates = result.get("candidates", [])
        if not candidates:
            return LLMResponse(
                text="I apologize, but I could not process your request at this moment.",
                intent="unknown",
            )

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
                        id=fc.get("id") or f"gemini_call_{len(tool_calls)+1}",
                        function_name=fc.get("name", ""),
                        arguments=fc.get("args", {}),
                    )
                )

        last_user_text = next(
            (
                (m.content if hasattr(m, "content") else m.get("content", ""))
                for m in reversed(messages)
                if (m.role if hasattr(m, "role") else m.get("role")) == "user"
            ),
            "",
        )
        import re
        if re.search(r"[\u0B80-\u0BFF]", spoken_text):
            detected_lang = "ta-IN"
        elif re.search(r"[\u0C00-\u0C7F]", spoken_text):
            user_lang = detect_language(last_user_text) if last_user_text else None
            if user_lang and user_lang.startswith("ta"):
                detected_lang = user_lang
            else:
                detected_lang = "te-IN"
        else:
            detected_lang = detect_language(spoken_text or last_user_text)

        return LLMResponse(
            text=spoken_text.strip(),
            intent="function_call" if tool_calls else "conversation",
            detected_language=detected_lang,
            tool_calls=tool_calls,
            raw_metadata=result,
        )

    def generate_response(
        self,
        messages: list[LLMMessage],
        system_prompt: str,
        active_services: list[dict[str, Any]],
        available_tools: list[dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> LLMResponse:
        """Call Gemini REST API synchronously with strict bounded timeout and circuit breaker."""
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured on the server.")

        start_time = time.perf_counter()
        overall_timeout = 7.0  # Bounded hard cap (eliminates 30-40s hangs while allowing genuine responses)
        max_retries = 1        # Strict max retries: at most 1 retry (2 total attempts)

        # 1. Circuit Breaker Check
        if not gemini_circuit_breaker.can_execute():
            gemini_circuit_breaker.record_fallback()
            logger.warning("Gemini Circuit Breaker is OPEN. Fast-failing to conversational fallback.")
            raise GeminiCircuitOpenError("Gemini circuit breaker is OPEN due to repeated upstream 503/rate-limit failures.")

        gemini_circuit_breaker.total_calls += 1

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        body = self._build_request_body(
            messages=messages,
            system_prompt=system_prompt,
            available_tools=available_tools,
            temperature=temperature,
            max_tokens=min(max_tokens, 180),
        )

        last_error: Exception | None = None
        client = self._sync_client

        for attempt in range(max_retries + 1):
            elapsed = time.perf_counter() - start_time
            remaining = overall_timeout - elapsed
            if remaining <= 0.4:
                logger.warning(
                    "Gemini request budget exhausted (%.2fs elapsed, %.2fs remaining). Failing fast.",
                    elapsed,
                    remaining,
                )
                gemini_circuit_breaker.record_failure(503)
                gemini_circuit_breaker.record_fallback()
                raise GeminiTimeoutError(f"Gemini LLM request exceeded bounded deadline of {overall_timeout}s")

            # Bounded per-request timeout: allows sufficient time for complex Tamil token generation
            req_timeout = httpx.Timeout(
                connect=min(2.0, remaining),
                read=min(4.5, remaining),
                write=2.0,
                pool=2.0,
            )

            try:
                resp = client.post(url, json=body, timeout=req_timeout)
                if resp.status_code == 200:
                    gemini_circuit_breaker.record_success()
                    return self._parse_candidate_response(resp.json(), messages)

                # Transient server / rate limit error: 503 or 429
                if resp.status_code in (429, 503):
                    gemini_circuit_breaker.record_failure(resp.status_code)
                    if attempt < max_retries:
                        elapsed = time.perf_counter() - start_time
                        remaining = overall_timeout - elapsed
                        # Jittered exponential backoff: 0.15s - 0.40s
                        jitter = random.uniform(0.05, 0.15)
                        backoff = min(0.15 * (1.5 ** attempt) + jitter, 0.40)
                        if remaining > (backoff + 0.8):
                            gemini_circuit_breaker.record_retry()
                            logger.warning(
                                "Gemini API returned %s (attempt %d/%d). Bounded backoff %.2fs with jitter...",
                                resp.status_code,
                                attempt + 1,
                                max_retries + 1,
                                backoff,
                            )
                            time.sleep(backoff)
                            continue
                        else:
                            logger.warning(
                                "Insufficient time budget for retry after %s (%.2fs remaining). Fast-failing.",
                                resp.status_code,
                                remaining,
                            )
                            gemini_circuit_breaker.record_fallback()
                            raise RuntimeError(f"Gemini API returned {resp.status_code} and time budget exhausted")

                # Non-retryable error
                gemini_circuit_breaker.record_failure(resp.status_code)
                gemini_circuit_breaker.record_fallback()
                logger.error(
                    "Gemini API returned %s: %s (key: %s)",
                    resp.status_code,
                    resp.text,
                    _mask_key(self.api_key),
                )
                raise RuntimeError(f"Gemini API error ({resp.status_code}): {resp.text}")

            except (httpx.TimeoutException, httpx.NetworkError) as net_err:
                last_error = net_err
                gemini_circuit_breaker.record_failure()
                if attempt < max_retries:
                    elapsed = time.perf_counter() - start_time
                    remaining = overall_timeout - elapsed
                    jitter = random.uniform(0.05, 0.15)
                    backoff = min(0.15 + jitter, 0.35)
                    if remaining > (backoff + 0.8):
                        gemini_circuit_breaker.record_retry()
                        logger.warning(
                            "Gemini API network timeout/error (attempt %d/%d). Quick retry in %.2fs...",
                            attempt + 1,
                            max_retries + 1,
                            backoff,
                        )
                        time.sleep(backoff)
                        continue
                logger.error("Gemini API connection failed after retries: %s", net_err)
                break

        gemini_circuit_breaker.record_fallback()
        if last_error:
            raise RuntimeError(f"Gemini API call failed: {last_error}") from last_error
        raise RuntimeError("Gemini API call failed without response")

    async def agenerate_response(
        self,
        messages: list[LLMMessage],
        system_prompt: str,
        active_services: list[dict[str, Any]],
        available_tools: list[dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> LLMResponse:
        """Call Gemini REST API asynchronously with strict bounded timeout and circuit breaker."""
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured on the server.")

        start_time = time.perf_counter()
        overall_timeout = 7.0
        max_retries = 1

        if not gemini_circuit_breaker.can_execute():
            gemini_circuit_breaker.record_fallback()
            logger.warning("Gemini Circuit Breaker is OPEN. Fast-failing to conversational fallback.")
            raise GeminiCircuitOpenError("Gemini circuit breaker is OPEN due to repeated upstream 503/rate-limit failures.")

        gemini_circuit_breaker.total_calls += 1

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        body = self._build_request_body(
            messages=messages,
            system_prompt=system_prompt,
            available_tools=available_tools,
            temperature=temperature,
            max_tokens=min(max_tokens, 180),
        )

        last_error: Exception | None = None
        client = self._async_client

        for attempt in range(max_retries + 1):
            elapsed = time.perf_counter() - start_time
            remaining = overall_timeout - elapsed
            if remaining <= 0.4:
                logger.warning(
                    "Gemini async request budget exhausted (%.2fs elapsed, %.2fs remaining). Failing fast.",
                    elapsed,
                    remaining,
                )
                gemini_circuit_breaker.record_failure(503)
                gemini_circuit_breaker.record_fallback()
                raise GeminiTimeoutError(f"Gemini LLM request exceeded bounded deadline of {overall_timeout}s")

            # Bounded per-request timeout: allows sufficient time for complex Tamil token generation
            req_timeout = httpx.Timeout(
                connect=min(2.0, remaining),
                read=min(4.5, remaining),
                write=2.0,
                pool=2.0,
            )

            try:
                resp = await client.post(url, json=body, timeout=req_timeout)
                if resp.status_code == 200:
                    gemini_circuit_breaker.record_success()
                    return self._parse_candidate_response(resp.json(), messages)

                if resp.status_code in (429, 503):
                    gemini_circuit_breaker.record_failure(resp.status_code)
                    if attempt < max_retries:
                        elapsed = time.perf_counter() - start_time
                        remaining = overall_timeout - elapsed
                        jitter = random.uniform(0.05, 0.15)
                        backoff = min(0.15 * (1.5 ** attempt) + jitter, 0.40)
                        if remaining > (backoff + 0.8):
                            gemini_circuit_breaker.record_retry()
                            logger.warning(
                                "Gemini API returned %s (attempt %d/%d). Bounded async backoff %.2fs with jitter...",
                                resp.status_code,
                                attempt + 1,
                                max_retries + 1,
                                backoff,
                            )
                            await asyncio.sleep(backoff)
                            continue
                        else:
                            gemini_circuit_breaker.record_fallback()
                            raise RuntimeError(f"Gemini API returned {resp.status_code} and time budget exhausted")

                gemini_circuit_breaker.record_failure(resp.status_code)
                gemini_circuit_breaker.record_fallback()
                logger.error(
                    "Gemini API returned %s: %s (key: %s)",
                    resp.status_code,
                    resp.text,
                    _mask_key(self.api_key),
                )
                raise RuntimeError(f"Gemini API error ({resp.status_code}): {resp.text}")

            except (httpx.TimeoutException, httpx.NetworkError) as net_err:
                last_error = net_err
                gemini_circuit_breaker.record_failure()
                if attempt < max_retries:
                    elapsed = time.perf_counter() - start_time
                    remaining = overall_timeout - elapsed
                    jitter = random.uniform(0.05, 0.15)
                    backoff = min(0.15 + jitter, 0.35)
                    if remaining > (backoff + 0.8):
                        gemini_circuit_breaker.record_retry()
                        logger.warning(
                            "Gemini async network timeout/error (attempt %d/%d). Quick retry in %.2fs...",
                            attempt + 1,
                            max_retries + 1,
                            backoff,
                        )
                        await asyncio.sleep(backoff)
                        continue
                logger.error("Gemini API connection failed after retries: %s", net_err)
                break

        gemini_circuit_breaker.record_fallback()
        if last_error:
            raise RuntimeError(f"Gemini API call failed: {last_error}") from last_error
        raise RuntimeError("Gemini API call failed without response")
        raise RuntimeError("Gemini API call failed without response")
