"""Unit and regression tests for Gemini 503 handling, Circuit Breaker, bounded timeout, and state preservation."""

import pytest
import time
import json
import uuid
from app.services.ai.gemini_provider import (
    GeminiCircuitBreaker,
    GeminiCircuitOpenError,
    GeminiTimeoutError,
    GeminiLLMProvider,
)
from app.services.ai.base import LLMMessage
from app.database.connection import SessionLocal
from app.models.business import Business
from app.models.conversation_session import ConversationSession
from app.models.appointment import Appointment
from app.models.customer import Customer
from app.models.assistant import Service
from app.services.voice_assistant_service import (
    generate_natural_fallback_response,
    execute_llm_conversational_turn,
)
from app.services.ai.tools import execute_tool_call


def test_circuit_breaker_lifecycle():
    cb = GeminiCircuitBreaker(failure_threshold=3, recovery_timeout_sec=0.5)
    assert cb.state == "CLOSED"
    assert cb.can_execute() is True

    # Record 2 failures -> remains CLOSED
    cb.record_failure(503)
    cb.record_failure(503)
    assert cb.state == "CLOSED"
    assert cb.can_execute() is True

    # 3rd consecutive failure -> trips to OPEN
    cb.record_failure(503)
    assert cb.state == "OPEN"
    assert cb.can_execute() is False

    # During recovery timeout -> still OPEN
    assert cb.can_execute() is False

    # After recovery timeout -> enters HALF_OPEN
    time.sleep(0.55)
    assert cb.can_execute() is True
    assert cb.state == "HALF_OPEN"

    # Success in HALF_OPEN resets to CLOSED
    cb.record_success()
    assert cb.state == "CLOSED"
    assert cb.consecutive_failures == 0


def test_natural_fallback_preserves_state():
    db = SessionLocal()
    try:
        biz = Business(
            id=f"biz_cb_{uuid.uuid4().hex[:6]}",
            name="Vattara City Clinic",
            vertical="clinic",
            email=f"cb_{uuid.uuid4().hex[:6]}@vattara.com",
            phone="+918031794113",
            timezone="Asia/Kolkata",
            is_active=True,
        )
        db.add(biz)
        db.flush()

        # Session in awaiting_datetime
        session = ConversationSession(
            call_sid=f"call_cb_{uuid.uuid4().hex[:6]}",
            business_id=biz.id,
            caller_phone="+919876543210",
            step="awaiting_datetime",
            intent="booking",
            language="en-IN",
            detected_language="en-IN",
            dialog_history=json.dumps([]),
            metadata_json=json.dumps({"customer_name": "Karthik"}),
            retry_count=0,
            is_completed=False,
        )
        db.add(session)
        db.commit()

        # Trigger fallback
        msg, cont = generate_natural_fallback_response(
            session=session,
            business=biz,
            speech_clean="Tomorrow morning please",
            db=db,
        )

        assert cont is True
        assert "doctor" in msg.lower() or "calendar" in msg.lower() or "preferred" in msg.lower()
        # Ensure state was preserved!
        assert session.step == "awaiting_datetime"
        assert session.caller_phone == "+919876543210"

        # Check Tamil fallback
        session_ta = ConversationSession(
            call_sid=f"call_cb_ta_{uuid.uuid4().hex[:6]}",
            business_id=biz.id,
            caller_phone="+919876543210",
            step="awaiting_datetime",
            intent="booking",
            language="ta-IN",
            detected_language="ta-IN",
            dialog_history=json.dumps([]),
            metadata_json=json.dumps({}),
            retry_count=0,
            is_completed=False,
        )
        db.add(session_ta)
        db.commit()

        msg_ta, cont_ta = generate_natural_fallback_response(
            session=session_ta,
            business=biz,
            speech_clean="நாளை காலை 10 மணிக்கு",
            db=db,
        )
        assert cont_ta is True
        assert any(w in msg_ta for w in ["மருத்துவர்", "தேதி", "நேரம்"])
        assert session_ta.step == "awaiting_datetime"

    finally:
        db.close()


def test_booking_idempotency_on_retry():
    db = SessionLocal()
    try:
        biz = Business(
            id=f"biz_idem_{uuid.uuid4().hex[:6]}",
            name="Vattara City Clinic",
            vertical="clinic",
            email=f"idem_{uuid.uuid4().hex[:6]}@vattara.com",
            phone="+918031794113",
            timezone="Asia/Kolkata",
            is_active=True,
        )
        db.add(biz)
        db.flush()

        srv = Service(
            id=f"srv_idem_{uuid.uuid4().hex[:6]}",
            business_id=biz.id,
            name="General Physician Consultation",
            duration_minutes=30,
            price=500.0,
            is_active=True,
        )
        db.add(srv)
        db.commit()

        # First booking call via tool
        args = {
            "customer_name": "Ramesh Kumar",
            "customer_phone": "+919888877777",
            "service_id": srv.id,
            "appointment_time": "2026-11-20T10:00:00+05:30",
        }
        res1 = execute_tool_call(db=db, business_id=biz.id, function_name="book_appointment", arguments=args)
        assert res1.get("success") is True
        appt_id = res1["appointment_id"]

        # Duplicate retry call with exact same args
        res2 = execute_tool_call(db=db, business_id=biz.id, function_name="book_appointment", arguments=args)
        assert res2.get("success") is True
        assert res2.get("already_booked") is True
        assert res2["appointment_id"] == appt_id  # Reuses same appointment without duplicate!

    finally:
        db.close()
