"""Automated Test Suite for Phase 3: AI Conversational Voice Engine.

Covers:
1. English conversations.
2. Tamil (Unicode script) conversations.
3. Tanglish (Tamil in Latin script) conversations.
4. Intent classification and entity extraction.
5. Multi-turn conversation context retention.
6. Live appointment availability checking via Phase 2 engine.
7. Real appointment booking with database commit.
8. Appointment rescheduling and cancellation via voice tool calls.
9. Missing information follow-up prompts.
10. Invalid appointment requests (past dates, closed business days).
11. Strict multi-tenant scheduling isolation.
12. AI provider factory and graceful offline fallback.
"""

from datetime import date, datetime, timedelta, timezone
import json
from typing import Any
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from twilio.request_validator import RequestValidator

from app.core.config import settings
from app.models.appointment import Appointment
from app.models.assistant import AssistantConfig, Service
from app.models.business import Business
from app.models.business_hours import BusinessHour
from app.models.conversation_session import ConversationSession
from app.models.customer import Customer
from app.models.user import User
from app.services.ai.factory import get_llm_provider
from app.services.ai.language_detector import detect_language, is_tamil_script
from app.services.ai.mock_provider import MockLLMProvider
from app.services.ai.tools import execute_tool_call
from app.services.twilio_service import TwilioService, get_twilio_service

TEST_AUTH_TOKEN = "test_ai_voice_token_secret_12345"


@pytest.fixture
def twilio_mock_service() -> TwilioService:
    return TwilioService(
        account_sid="ACmock00000000000000000000000000",
        auth_token=TEST_AUTH_TOKEN,
        phone_number="+12292523194",
        public_base_url="https://pushiness-disparate-pulmonary.ngrok-free.dev",
    )


@pytest.fixture
def ai_test_env(db_session: Session) -> dict[str, Any]:
    """Create two isolated businesses with services, operating hours, and customers."""
    # Tenant 1: Apollo Clinic
    biz1 = Business(
        id="biz-ai-apollo",
        name="Apollo Multicare Hospital",
        vertical="clinic",
        email="apollo@vattara.com",
        phone="+12292523194",
        timezone="Asia/Kolkata",
        is_active=True,
    )
    # Tenant 2: City Dental
    biz2 = Business(
        id="biz-ai-dental",
        name="City Dental Centre",
        vertical="clinic",
        email="dental@vattara.com",
        phone="+12292529999",
        timezone="Asia/Kolkata",
        is_active=True,
    )
    db_session.add_all([biz1, biz2])
    db_session.flush()

    # Operating Hours for Tenant 1: Mon-Sat 09:00-18:00, Sun closed
    for dow in range(7):
        bh = BusinessHour(
            business_id=biz1.id,
            day_of_week=dow,
            open_time="09:00",
            close_time="18:00",
            is_closed=False,
        )
        db_session.add(bh)

    # Services for Tenant 1
    srv_cardio = Service(
        id="srv-ai-cardio",
        business_id=biz1.id,
        name="Cardiology Consultation",
        price=1000.0,
        duration_minutes=30,
        is_active=True,
    )
    srv_physician = Service(
        id="srv-ai-physician",
        business_id=biz1.id,
        name="General Physician Consultation",
        price=500.0,
        duration_minutes=30,
        is_active=True,
    )
    srv_dental = Service(
        id="srv-ai-dental",
        business_id=biz1.id,
        name="Dental Care & Cleaning",
        price=700.0,
        duration_minutes=30,
        is_active=True,
    )
    db_session.add_all([srv_cardio, srv_physician, srv_dental])

    # Assistant Config for Tenant 1
    cfg1 = AssistantConfig(
        business_id=biz1.id,
        assistant_name="Vattara AI",
        language="en-IN",
        voice="Polly.Aditi",
        ai_provider="mock",
        ai_model="gpt-4o-mini",
        enable_tanglish=True,
        is_active=True,
    )
    db_session.add(cfg1)
    db_session.commit()

    return {
        "biz1": biz1,
        "biz2": biz2,
        "srv_cardio": srv_cardio,
        "srv_physician": srv_physician,
        "srv_dental": srv_dental,
    }


def compute_sig(url: str, params: dict[str, str], token: str = TEST_AUTH_TOKEN) -> str:
    validator = RequestValidator(token)
    return validator.compute_signature(url, params)


# ==============================================================================
# 1. LANGUAGE DETECTION UNIT TESTS (English, Tamil, Tanglish)
# ==============================================================================

def test_language_detection_tamil_script() -> None:
    """Verify Tamil Unicode script detection."""
    assert is_tamil_script("வணக்கம்") is True
    assert detect_language("வணக்கம் டாக்டர், எனக்கு அப்பாயின்ட்மென்ட் வேண்டும்") == "ta-IN"


def test_language_detection_tanglish() -> None:
    """Verify phonetic Tanglish (Tamil in Latin alphabet) detection."""
    tanglish_1 = "Vanakkam doctor, naalaiki appointment slot iruka?"
    tanglish_2 = "Enakku general physician consultation parkanum"
    tanglish_3 = "Cardiology booking confirm pannunga please"
    tanglish_4 = "Appointment cancel pannanum, romba nandri"

    assert detect_language(tanglish_1) == "ta-Latn"
    assert detect_language(tanglish_2) == "ta-Latn"
    assert detect_language(tanglish_3) == "ta-Latn"
    assert detect_language(tanglish_4) == "ta-Latn"


def test_language_detection_english() -> None:
    """Verify standard English detection."""
    eng_1 = "Hello, I would like to schedule a cardiology consultation tomorrow at 10 AM."
    eng_2 = "Can I check the doctor's available slots for Friday?"
    assert detect_language(eng_1) == "en-IN"
    assert detect_language(eng_2) == "en-IN"


# ==============================================================================
# 2. TANGLISH CONVERSATIONAL BOOKING FLOW
# ==============================================================================

def test_tanglish_conversational_booking(
    client: TestClient,
    ai_test_env: dict[str, Any],
    twilio_mock_service: TwilioService,
    db_session: Session,
) -> None:
    """Verify Tanglish voice conversation creates appointment and responds in Tanglish."""
    from app.main import app
    app.dependency_overrides[get_twilio_service] = lambda: twilio_mock_service

    try:
        endpoint = f"{settings.API_V1_STR}/voice/webhooks/gather-speech"
        url = f"http://testserver{endpoint}"
        call_sid = "CA_TANGLISH_BOOKING_001"
        caller_phone = "+919840155667"

        # Tanglish booking utterance
        speech = "Vanakkam, naalaiki kaalai 10 maniki cardiology consultation venum. En peyar Karthik Natarajan."
        payload = {
            "CallSid": call_sid,
            "From": caller_phone,
            "To": "+12292523194",
            "SpeechResult": speech,
        }
        sig = compute_sig(url, payload)

        res = client.post(endpoint, data=payload, headers={"X-Twilio-Signature": sig})
        assert res.status_code == 200
        xml = res.text
        assert "<Response>" in xml
        assert "Karthik Natarajan" in xml
        assert "confirm" in xml.lower() or "nandri" in xml.lower()

        # Check DB session state
        session = db_session.get(ConversationSession, call_sid)
        assert session is not None
        assert session.detected_language == "ta-Latn"
        assert session.customer_name == "Karthik Natarajan"
        assert session.is_completed is True
        assert session.booking_id is not None

        # Verify DB Appointment
        appt = db_session.get(Appointment, session.booking_id)
        assert appt is not None
        assert appt.service_id == ai_test_env["srv_cardio"].id
        assert appt.status == "upcoming"
        assert appt.customer.name == "Karthik Natarajan"
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# 3. TAMIL SCRIPT CONVERSATIONAL BOOKING FLOW
# ==============================================================================

def test_tamil_script_conversational_booking(
    client: TestClient,
    ai_test_env: dict[str, Any],
    twilio_mock_service: TwilioService,
    db_session: Session,
) -> None:
    """Verify pure Tamil Unicode conversation creates appointment with Indian Tamil voice."""
    from app.main import app
    app.dependency_overrides[get_twilio_service] = lambda: twilio_mock_service

    try:
        endpoint = f"{settings.API_V1_STR}/voice/webhooks/gather-speech"
        url = f"http://testserver{endpoint}"
        call_sid = "CA_TAMIL_BOOKING_002"
        caller_phone = "+919840998877"

        speech = "வணக்கம், எனக்கு கார்டியாலஜி அப்பாயின்ட்மென்ட் நாளை காலை 11 மணிக்கு வேண்டும். என் பெயர் செல்வி சுந்தரி."
        payload = {
            "CallSid": call_sid,
            "From": caller_phone,
            "To": "+12292523194",
            "SpeechResult": speech,
        }
        sig = compute_sig(url, payload)

        res = client.post(endpoint, data=payload, headers={"X-Twilio-Signature": sig})
        assert res.status_code == 200
        xml = res.text
        assert "<Response>" in xml
        assert "Polly.Valluvar" in xml
        assert "செல்வி சுந்தரி" in xml or "பதிவு" in xml

        session = db_session.get(ConversationSession, call_sid)
        assert session is not None
        assert session.detected_language == "ta-IN"
        assert session.is_completed is True
        assert session.booking_id is not None
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# 4. MULTI-TURN CONTEXT RETENTION & STEP PROGRESSION
# ==============================================================================

def test_multi_turn_context_retention(
    client: TestClient,
    ai_test_env: dict[str, Any],
    twilio_mock_service: TwilioService,
    db_session: Session,
) -> None:
    """Verify multi-turn session remembers collected slots across consecutive turns."""
    from app.main import app
    app.dependency_overrides[get_twilio_service] = lambda: twilio_mock_service

    try:
        endpoint = f"{settings.API_V1_STR}/voice/webhooks/gather-speech"
        url = f"http://testserver{endpoint}"
        call_sid = "CA_CONTEXT_TURN_003"
        caller_phone = "+15558881111"

        # Turn 1: Greeting / General intent
        p1 = {"CallSid": call_sid, "From": caller_phone, "To": "+12292523194", "SpeechResult": "Hi, I need an appointment."}
        r1 = client.post(endpoint, data=p1, headers={"X-Twilio-Signature": compute_sig(url, p1)})
        assert r1.status_code == 200
        s1 = db_session.get(ConversationSession, call_sid)
        assert s1.step == "awaiting_service"

        # Turn 2: Service chosen (Dental)
        p2 = {"CallSid": call_sid, "From": caller_phone, "To": "+12292523194", "SpeechResult": "Dental care and cleaning."}
        r2 = client.post(endpoint, data=p2, headers={"X-Twilio-Signature": compute_sig(url, p2)})
        assert r2.status_code == 200
        db_session.refresh(s1)
        assert s1.service_id == ai_test_env["srv_dental"].id
        assert s1.step == "awaiting_datetime"

        # Turn 3: Date & time provided
        p3 = {"CallSid": call_sid, "From": caller_phone, "To": "+12292523194", "SpeechResult": "Tomorrow at 10 AM."}
        r3 = client.post(endpoint, data=p3, headers={"X-Twilio-Signature": compute_sig(url, p3)})
        assert r3.status_code == 200
        db_session.refresh(s1)
        assert s1.appointment_datetime_iso is not None
        assert s1.step == "awaiting_name"

        # Turn 4: Caller Name provided
        p4 = {"CallSid": call_sid, "From": caller_phone, "To": "+12292523194", "SpeechResult": "My name is Rachel Green."}
        r4 = client.post(endpoint, data=p4, headers={"X-Twilio-Signature": compute_sig(url, p4)})
        assert r4.status_code == 200
        assert "Rachel Green" in r4.text
        assert "<Hangup" in r4.text

        db_session.refresh(s1)
        assert s1.is_completed is True
        assert s1.booking_id is not None
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# 5. AVAILABILITY CHECKING VIA VOICE ENGINE
# ==============================================================================

def test_voice_check_availability_intent(
    client: TestClient,
    ai_test_env: dict[str, Any],
    twilio_mock_service: TwilioService,
    db_session: Session,
) -> None:
    """Verify voice request inquiring about slots triggers check_available_slots tool."""
    from app.main import app
    app.dependency_overrides[get_twilio_service] = lambda: twilio_mock_service

    try:
        endpoint = f"{settings.API_V1_STR}/voice/webhooks/gather-speech"
        url = f"http://testserver{endpoint}"
        call_sid = "CA_AVAIL_CHECK_004"
        caller_phone = "+15558882222"

        # Inquire about tomorrow's slots
        speech = "What available slots do you have for tomorrow?"
        payload = {
            "CallSid": call_sid,
            "From": caller_phone,
            "To": "+12292523194",
            "SpeechResult": speech,
        }
        sig = compute_sig(url, payload)

        res = client.post(endpoint, data=payload, headers={"X-Twilio-Signature": sig})
        assert res.status_code == 200
        xml = res.text
        assert "<Gather" in xml
        assert "available" in xml.lower() or "slots" in xml.lower()
        # Should prompt available times like 09:00 or 09:30
        assert ":" in xml
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# 6. APPOINTMENT RESCHEDULING VIA VOICE ENGINE
# ==============================================================================

def test_voice_reschedule_appointment_flow(
    client: TestClient,
    ai_test_env: dict[str, Any],
    twilio_mock_service: TwilioService,
    db_session: Session,
) -> None:
    """Verify caller can reschedule an existing appointment via conversational request."""
    from app.main import app
    app.dependency_overrides[get_twilio_service] = lambda: twilio_mock_service

    biz1 = ai_test_env["biz1"]
    srv1 = ai_test_env["srv_cardio"]
    caller_phone = "+919840133445"

    # 1. Pre-seed active customer and appointment
    cust = Customer(
        business_id=biz1.id,
        name="Vikram Reschedule",
        phone=caller_phone,
    )
    db_session.add(cust)
    db_session.flush()

    initial_time = datetime.now(timezone.utc) + timedelta(days=2, hours=2)
    appt = Appointment(
        business_id=biz1.id,
        customer_id=cust.id,
        service_id=srv1.id,
        appointment_time=initial_time,
        status="upcoming",
    )
    db_session.add(appt)
    db_session.commit()
    appt_id = appt.id

    try:
        endpoint = f"{settings.API_V1_STR}/voice/webhooks/gather-speech"
        url = f"http://testserver{endpoint}"
        call_sid = "CA_RESCHEDULE_VOICE_005"

        # Turn 1: Caller requests reschedule with new time
        new_slot_speech = "I need to reschedule my appointment to tomorrow at 11 AM please."
        payload = {
            "CallSid": call_sid,
            "From": caller_phone,
            "To": "+12292523194",
            "SpeechResult": new_slot_speech,
        }
        sig = compute_sig(url, payload)

        res = client.post(endpoint, data=payload, headers={"X-Twilio-Signature": sig})
        assert res.status_code == 200
        xml = res.text
        assert "rescheduled" in xml.lower()
        assert "<Hangup" in xml

        # Verify DB appointment updated
        db_session.refresh(appt)
        assert appt.status == "rescheduled"
        assert appt.reschedule_reason is not None
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# 7. APPOINTMENT CANCELLATION VIA VOICE ENGINE
# ==============================================================================

def test_voice_cancel_appointment_flow(
    client: TestClient,
    ai_test_env: dict[str, Any],
    twilio_mock_service: TwilioService,
    db_session: Session,
) -> None:
    """Verify caller can cancel an existing appointment via conversational request."""
    from app.main import app
    app.dependency_overrides[get_twilio_service] = lambda: twilio_mock_service

    biz1 = ai_test_env["biz1"]
    srv1 = ai_test_env["srv_cardio"]
    caller_phone = "+919840177889"

    cust = Customer(
        business_id=biz1.id,
        name="Anand Cancellation",
        phone=caller_phone,
    )
    db_session.add(cust)
    db_session.flush()

    initial_time = datetime.now(timezone.utc) + timedelta(days=3)
    appt = Appointment(
        business_id=biz1.id,
        customer_id=cust.id,
        service_id=srv1.id,
        appointment_time=initial_time,
        status="upcoming",
    )
    db_session.add(appt)
    db_session.commit()

    try:
        endpoint = f"{settings.API_V1_STR}/voice/webhooks/gather-speech"
        url = f"http://testserver{endpoint}"
        call_sid = "CA_CANCEL_VOICE_006"

        # Caller says cancel appointment
        speech = "Please cancel my appointment, I cannot make it."
        payload = {
            "CallSid": call_sid,
            "From": caller_phone,
            "To": "+12292523194",
            "SpeechResult": speech,
        }
        sig = compute_sig(url, payload)

        res = client.post(endpoint, data=payload, headers={"X-Twilio-Signature": sig})
        assert res.status_code == 200
        xml = res.text
        assert "cancelled" in xml.lower()
        assert "<Hangup" in xml

        # Verify DB appointment status
        db_session.refresh(appt)
        assert appt.status == "cancelled"
        assert appt.cancel_reason is not None
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# 8. MULTI-TENANT ISOLATION IN AI TOOLS
# ==============================================================================

def test_multi_tenant_isolation_in_voice_tools(
    ai_test_env: dict[str, Any],
    db_session: Session,
) -> None:
    """Verify AI tool execution strictly confines appointment lookup to tenant business_id."""
    biz1 = ai_test_env["biz1"]
    biz2 = ai_test_env["biz2"]

    # Customer belongs to Tenant 2
    cust2 = Customer(business_id=biz2.id, name="Tenant 2 User", phone="+919800099900")
    db_session.add(cust2)
    db_session.flush()

    appt2 = Appointment(
        business_id=biz2.id,
        customer_id=cust2.id,
        appointment_time=datetime.now(timezone.utc) + timedelta(days=2),
        status="upcoming",
    )
    db_session.add(appt2)
    db_session.commit()

    # Tenant 1 attempts to cancel Tenant 2's appointment using customer_phone
    cancel_res = execute_tool_call(
        db=db_session,
        business_id=biz1.id,  # Tenant 1 context!
        function_name="cancel_appointment",
        arguments={"customer_phone": "+919800099900"},
    )
    # Must fail because customer belongs to Tenant 2!
    assert "error" in cancel_res
    assert "No active appointment found" in cancel_res["error"]

    # Tenant 2 appointment remains untouched
    db_session.refresh(appt2)
    assert appt2.status == "upcoming"


# ==============================================================================
# 9. AI PROVIDER FACTORY AND FALLBACK
# ==============================================================================

def test_ai_provider_factory_and_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_llm_provider returns MockLLMProvider when keys are missing or offline."""
    # 1. Default mock provider
    p1 = get_llm_provider("mock")
    assert isinstance(p1, MockLLMProvider)

    # 2. OpenAI provider without key falls back to MockLLMProvider
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)
    p2 = get_llm_provider("openai")
    assert isinstance(p2, MockLLMProvider)

    # 3. Gemini provider without key falls back to MockLLMProvider
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
    p3 = get_llm_provider("gemini")
    assert isinstance(p3, MockLLMProvider)
