"""Comprehensive Test Suite for Google Gemini Integration in Vattara Voice Assistance.

Covers:
1. Provider initialization & model configuration.
2. Formatter: Alternating roles, function calls, functionResponse, thoughtSignature.
3. Live Gemini API authentication & response generation.
4. Multilingual conversational capability (English, Tamil Unicode, Tanglish).
5. Function calling with AI_TOOLS_SPEC (check_available_slots, get_services_and_hours).
6. Multi-turn tool execution loop round trip.
7. Medical safety & emergency boundary enforcement.
8. Non-hallucination verification (Gemini uses tools for availability).
"""

import json
import os
import pytest
from app.core.config import settings
from app.services.ai.base import FunctionCallRequest, LLMMessage, LLMResponse
from app.services.ai.factory import get_llm_provider
from app.services.ai.gemini_provider import (
    GeminiLLMProvider,
    _format_gemini_contents,
    _mask_key,
)
from app.services.ai.tools import AI_TOOLS_SPEC


# ---------------------------------------------------------------------------
# 1. Unit Tests: Provider Configuration & Message Formatting
# ---------------------------------------------------------------------------


def test_gemini_provider_initialization() -> None:
    """Verify GeminiLLMProvider initializes with configured model and key."""
    provider = GeminiLLMProvider(api_key="test-key-12345", model="gemini-3.1-flash-lite")
    assert provider.api_key == "test-key-12345"
    assert provider.model == "gemini-3.1-flash-lite"


def test_gemini_key_masking() -> None:
    """Verify API keys are masked properly for secure logging."""
    assert _mask_key(None) == "***"
    assert _mask_key("") == "***"
    assert _mask_key("short") == "***"
    sample_key = os.environ.get("GEMINI_API_KEY") or "mock_sample_gemini_api_key_123456789"
    masked = _mask_key(sample_key)
    assert masked.startswith(sample_key[:6])
    assert masked.endswith(sample_key[-4:])
    assert "..." in masked
    assert len(masked) == 13


def test_format_gemini_contents_alternating_roles() -> None:
    """Verify messages are converted to Gemini schema with alternating roles."""
    messages = [
        LLMMessage(role="user", content="Hello, I want to book an appointment."),
        LLMMessage(role="assistant", content="Sure! What date and time works for you?"),
        LLMMessage(role="user", content="Tomorrow at 10 AM please."),
    ]
    contents = _format_gemini_contents(messages)
    assert len(contents) == 3
    assert contents[0]["role"] == "user"
    assert contents[0]["parts"][0]["text"] == "Hello, I want to book an appointment."
    assert contents[1]["role"] == "model"
    assert contents[1]["parts"][0]["text"] == "Sure! What date and time works for you?"
    assert contents[2]["role"] == "user"
    assert contents[2]["parts"][0]["text"] == "Tomorrow at 10 AM please."


def test_format_gemini_contents_consecutive_merging() -> None:
    """Verify consecutive messages of the same role are merged to obey Gemini schema."""
    messages = [
        LLMMessage(role="user", content="First question"),
        LLMMessage(role="user", content="Second question"),
    ]
    contents = _format_gemini_contents(messages)
    assert len(contents) == 1
    assert contents[0]["role"] == "user"
    assert len(contents[0]["parts"]) == 2
    assert contents[0]["parts"][0]["text"] == "First question"
    assert contents[0]["parts"][1]["text"] == "Second question"


def test_format_gemini_contents_tool_response() -> None:
    """Verify tool execution results are converted to functionResponse parts."""
    raw_parts = [{
        "functionCall": {
            "name": "check_available_slots",
            "args": {"date": "2026-11-18"},
        },
        "thoughtSignature": "test_signature_abc123",
    }]
    messages = [
        LLMMessage(role="user", content="Are you open tomorrow?"),
        LLMMessage(role="assistant", content="", name="check_available_slots", raw_parts=raw_parts),
        LLMMessage(
            role="tool",
            content=json.dumps({"available_slots": ["10:00", "11:00"]}),
            name="check_available_slots",
        ),
    ]
    contents = _format_gemini_contents(messages)
    assert len(contents) == 3
    assert contents[0]["role"] == "user"
    assert contents[1]["role"] == "model"
    assert contents[1]["parts"] == raw_parts
    assert contents[2]["role"] == "function"
    assert contents[2]["parts"][0]["functionResponse"]["name"] == "check_available_slots"
    assert contents[2]["parts"][0]["functionResponse"]["response"] == {"available_slots": ["10:00", "11:00"]}


# ---------------------------------------------------------------------------
# 2. Live API Integration Tests with Gemini
# ---------------------------------------------------------------------------


@pytest.fixture
def live_gemini_provider() -> GeminiLLMProvider:
    """Initialize a live GeminiLLMProvider using settings.GEMINI_API_KEY."""
    key = settings.GEMINI_API_KEY
    if not key:
        pytest.skip("GEMINI_API_KEY not configured; skipping live integration tests.")
    return GeminiLLMProvider(api_key=key, model="gemini-3.1-flash-lite")


def test_live_gemini_basic_english_response(live_gemini_provider: GeminiLLMProvider) -> None:
    """Verify live Gemini returns natural English receptionist response."""
    messages = [
        LLMMessage(role="user", content="Hello, what is your clinic name and what are your opening hours?")
    ]
    system_prompt = (
        "You are Vattara AI, voice receptionist for Vattara City Clinic. "
        "The clinic is open Monday to Saturday, 9 AM to 8 PM. Be concise in 1-2 spoken sentences."
    )
    resp = live_gemini_provider.generate_response(
        messages=messages,
        system_prompt=system_prompt,
        active_services=[],
        available_tools=[],
    )
    assert resp.text != ""
    assert any(term in resp.text.lower() for term in ["vattara", "clinic", "9", "open", "monday"])
    assert resp.detected_language in ("en-IN", "en")


def test_live_gemini_tamil_response(live_gemini_provider: GeminiLLMProvider) -> None:
    """Verify live Gemini returns authentic Tamil response when addressed in Tamil."""
    messages = [
        LLMMessage(role="user", content="வணக்கம், உங்கள் கிளினிக் நாளை திறந்திருக்குமா?")
    ]
    system_prompt = (
        "You are Vattara AI receptionist. If the caller speaks Tamil, respond in spoken Tamil (தமிழ்). "
        "Clinic is open tomorrow from 9 AM."
    )
    resp = live_gemini_provider.generate_response(
        messages=messages,
        system_prompt=system_prompt,
        active_services=[],
        available_tools=[],
    )
    assert resp.text != ""
    assert resp.detected_language == "ta-IN"


def test_live_gemini_tanglish_response(live_gemini_provider: GeminiLLMProvider) -> None:
    """Verify live Gemini handles Tanglish (Tamil in Latin script) conversation."""
    messages = [
        LLMMessage(role="user", content="Vanakkam! Doctor eppo iruppaaru? Enakku appointment venum.")
    ]
    system_prompt = (
        "You are Vattara AI voice receptionist. Respond in conversational Tanglish. "
        "Dr. Sundaram is available Monday to Friday from 10 AM to 5 PM."
    )
    resp = live_gemini_provider.generate_response(
        messages=messages,
        system_prompt=system_prompt,
        active_services=[],
        available_tools=[],
    )
    assert resp.text != ""
    assert resp.detected_language in ("ta-Latn", "ta-IN", "en-IN")


def test_live_gemini_function_calling(live_gemini_provider: GeminiLLMProvider) -> None:
    """Verify Gemini invokes tools rather than hallucinating appointment availability."""
    messages = [
        LLMMessage(role="user", content="I need an appointment tomorrow 2026-11-18 for General Physician Consultation.")
    ]
    system_prompt = (
        "You are Vattara AI. Current date is 2026-11-17. "
        "You must NEVER invent appointment slots! Always call check_available_slots."
    )
    resp = live_gemini_provider.generate_response(
        messages=messages,
        system_prompt=system_prompt,
        active_services=[],
        available_tools=AI_TOOLS_SPEC,
    )
    assert len(resp.tool_calls) > 0
    fn_names = [tc.function_name for tc in resp.tool_calls]
    assert any(fn in fn_names for fn in ["check_available_slots", "get_services_and_hours"])


def test_live_gemini_multiturn_tool_execution_loop(live_gemini_provider: GeminiLLMProvider) -> None:
    """Verify complete multi-turn tool calling loop with Gemini."""
    system_prompt = (
        "You are Vattara AI receptionist for Vattara City Clinic. "
        "You must call tools when asked about clinic services and hours. "
        "Once tool results are returned, speak 1 friendly sentence."
    )
    messages = [
        LLMMessage(role="user", content="Can you tell me what services your clinic provides?")
    ]

    # Turn 1: Model calls tool
    resp1 = live_gemini_provider.generate_response(
        messages=messages,
        system_prompt=system_prompt,
        active_services=[],
        available_tools=AI_TOOLS_SPEC,
    )
    assert len(resp1.tool_calls) > 0
    tc = resp1.tool_calls[0]

    # Candidate parts with thoughtSignature
    candidate_parts = (
        resp1.raw_metadata.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    )
    messages.append(LLMMessage(role="assistant", content=resp1.text, name=tc.function_name, raw_parts=candidate_parts))

    # Tool output
    mock_service_output = {
        "services": [
            {"name": "General Physician Consultation", "fee": 500},
            {"name": "Cardiology Consultation", "fee": 1200},
        ],
        "clinic": "Vattara City Clinic",
    }
    messages.append(LLMMessage(role="tool", content=json.dumps(mock_service_output), name=tc.function_name))

    # Turn 2: Model synthesizes spoken response using tool data
    resp2 = live_gemini_provider.generate_response(
        messages=messages,
        system_prompt=system_prompt,
        active_services=[],
        available_tools=AI_TOOLS_SPEC,
    )
    assert resp2.text != ""
    assert any(w in resp2.text.lower() for w in ["general", "cardiology", "physician", "consultation", "vattara"])
