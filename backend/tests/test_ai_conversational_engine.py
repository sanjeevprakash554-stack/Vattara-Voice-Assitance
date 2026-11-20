"""Automated Test Suite for AI Conversational Voice Engine.

Covers:
1. English language detection.
2. Tamil (Unicode script) language detection.
3. Tanglish (Tamil in Latin script) language detection.
4. Multi-tenant isolation in AI voice tools.
5. AI provider factory and graceful offline fallback.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.appointment import Appointment
from app.models.assistant import AssistantConfig, Service
from app.models.business import Business
from app.models.business_hours import BusinessHour
from app.models.customer import Customer
from app.services.ai.factory import get_llm_provider
from app.services.ai.language_detector import detect_language, is_tamil_script
from app.services.ai.mock_provider import MockLLMProvider
from app.services.ai.tools import execute_tool_call


@pytest.fixture
def ai_test_env(db_session: Session) -> dict[str, Any]:
    """Create two isolated businesses with services, operating hours, and customers."""
    # Tenant 1: Apollo Clinic
    biz1 = Business(
        id="biz-ai-apollo",
        name="Apollo Multicare Hospital",
        vertical="clinic",
        email="apollo@vattara.com",
        phone="+918040001234",
        timezone="Asia/Kolkata",
        is_active=True,
    )
    # Tenant 2: City Dental
    biz2 = Business(
        id="biz-ai-dental",
        name="City Dental Centre",
        vertical="clinic",
        email="dental@vattara.com",
        phone="+918040009999",
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
        voice="alloy",
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
# 2. MULTI-TENANT ISOLATION IN AI TOOLS
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
# 3. AI PROVIDER FACTORY AND FALLBACK
# ==============================================================================


def test_ai_provider_factory_and_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_llm_provider returns MockLLMProvider when keys are missing or offline."""
    # 1. Default mock provider
    p1 = get_llm_provider("mock")
    assert isinstance(p1, MockLLMProvider)

    # 2. OpenAI provider without key falls back to MockLLMProvider in test/dev
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")
    p2 = get_llm_provider("openai")
    assert isinstance(p2, MockLLMProvider)

    # 3. Gemini provider without key falls back to MockLLMProvider in test/dev
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
    p3 = get_llm_provider("gemini")
    assert isinstance(p3, MockLLMProvider)
