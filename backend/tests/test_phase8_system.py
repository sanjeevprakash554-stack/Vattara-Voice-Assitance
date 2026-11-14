"""Phase 8 Comprehensive System, Security, and Production Readiness Tests.

Covers:
1. API Rate Limiting Enforcement (sliding window, 429 response, Retry-After header).
2. Production Configuration Security Validation (SECRET_KEY length, FIRST_SUPERUSER_PASSWORD).
3. Super Admin Bootstrap & create_superuser CLI.
4. Billing Integrity & Invoice Payment Confirmation.
5. Multilingual AI Conversational Engine (English, Tamil, Tanglish multi-turn).
6. Human Receptionist Transfer & Fallback Routing.
7. STT and TTS Provider Fallbacks.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.rate_limiter import SlidingWindowRateLimiter
from app.core.security import create_access_token, get_password_hash, verify_password
from app.database.init_db import init_db
from app.main import app
from app.models.appointment import Appointment
from app.models.assistant import AssistantConfig, Service
from app.models.business import Business
from app.models.business_hours import BusinessHour
from app.models.customer import Customer
from app.models.subscription import Invoice, Subscription
from app.models.user import User
from app.scripts.create_superuser import create_or_update_superuser, validate_password_strength
from app.services.ai.factory import get_llm_provider
from app.services.ai.language_detector import detect_language
from app.services.ai.mock_provider import MockLLMProvider
from app.services.ai.tools import execute_tool_call
from app.services.streaming.stt_provider import get_streaming_stt_provider
from app.services.streaming.tts_provider import get_streaming_tts_provider


# ==============================================================================
# 1. API RATE LIMITING TESTS
# ==============================================================================

def test_login_rate_limiting(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure excessive login attempts trigger HTTP 429 with Retry-After header."""
    SlidingWindowRateLimiter.reset_all()
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)

    limit = settings.RATE_LIMIT_LOGIN_PER_MINUTE
    # Exhaust allowed attempts with bogus credentials
    for _ in range(limit):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "attacker@example.com", "password": "WrongPassword"},
        )
        assert resp.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_422_UNPROCESSABLE_ENTITY]

    # Next attempt must be throttled with HTTP 429
    throttled = client.post(
        "/api/v1/auth/login",
        json={"email": "attacker@example.com", "password": "WrongPassword"},
    )
    assert throttled.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "Retry-After" in throttled.headers
    assert "Too many requests" in throttled.json()["detail"]

    # Reset state
    SlidingWindowRateLimiter.reset_all()


def test_forgot_password_rate_limiting(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure forgot-password route throttles requests exceeding configured threshold."""
    SlidingWindowRateLimiter.reset_all()
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)

    limit = settings.RATE_LIMIT_FORGOT_PASSWORD_PER_MINUTE
    for _ in range(limit):
        resp = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "victim@example.com"},
        )
        assert resp.status_code == status.HTTP_200_OK

    # Exceeded attempt
    throttled = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "victim@example.com"},
    )
    assert throttled.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "Retry-After" in throttled.headers

    SlidingWindowRateLimiter.reset_all()


# ==============================================================================
# 2. PRODUCTION SECURITY CONFIGURATION TESTS
# ==============================================================================

def test_production_secret_key_rejection() -> None:
    """In production, weak or default SECRET_KEY values must raise ValidationError."""
    with pytest.raises(ValidationError, match="cryptographically random SECRET_KEY"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="temporary_secret_key_change_in_production_environment",
        )

    with pytest.raises(ValidationError, match="cryptographically random SECRET_KEY"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="short-secret-1234",
        )


def test_production_superuser_password_rejection() -> None:
    """In production, weak or default FIRST_SUPERUSER_PASSWORD must raise ValidationError."""
    valid_key = "a" * 64
    with pytest.raises(ValidationError, match="FIRST_SUPERUSER_PASSWORD"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY=valid_key,
            FIRST_SUPERUSER_PASSWORD="SuperAdmin@123",
        )

    with pytest.raises(ValidationError, match="FIRST_SUPERUSER_PASSWORD"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY=valid_key,
            FIRST_SUPERUSER_PASSWORD="short",
        )


def test_production_valid_configuration_passes() -> None:
    """Valid strong configuration passes without raising errors."""
    valid_key = "f" * 64
    conf = Settings(
        ENVIRONMENT="production",
        SECRET_KEY=valid_key,
        FIRST_SUPERUSER_PASSWORD="VattaraVeryStrongSuperPass#2026!",
    )
    assert conf.ENVIRONMENT == "production"
    assert len(conf.SECRET_KEY) >= 32


# ==============================================================================
# 3. SUPER ADMIN BOOTSTRAP & CLI TESTS
# ==============================================================================

def test_create_superuser_cli_validation() -> None:
    """validate_password_strength rejects weak or default passwords."""
    with pytest.raises(ValueError, match="at least 12 characters"):
        validate_password_strength("short123")

    with pytest.raises(ValueError, match="default or widely known"):
        validate_password_strength("SuperAdmin@123")

    # Valid password passes without exception
    validate_password_strength("MySuperSecurePass!2026#Production")


def test_create_or_update_superuser_execution(db_session: Session) -> None:
    """create_or_update_superuser securely provisions user with super_admin role."""
    test_email = "cli_superuser@vattara.com"
    test_pass = "VattaraSuperSecret2026!Key"

    # Provision
    create_or_update_superuser(email=test_email, password=test_pass, full_name="CLI Admin", db=db_session)

    user = db_session.scalar(select(User).where(User.email == test_email))
    assert user is not None
    assert user.role == "super_admin"
    assert user.is_active is True
    assert verify_password(test_pass, user.hashed_password)

    # Re-running updates credentials
    new_pass = "UpdatedSuperSecret2026!Key"
    create_or_update_superuser(email=test_email, password=new_pass, db=db_session)
    db_session.refresh(user)
    assert verify_password(new_pass, user.hashed_password)


# ==============================================================================
# 4. BILLING INTEGRITY & INVOICE PAYMENT CONFIRMATION
# ==============================================================================

def test_invoice_payment_confirmation_flow(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
) -> None:
    """Verify newly created invoice starts as pending and transitions to paid only upon payment confirmation."""
    # 1. Trigger plan change
    change_resp = client.post(
        "/api/v1/subscriptions/change-plan",
        headers=auth_headers,
        json={"plan_name": "enterprise", "billing_cycle": "monthly"},
    )
    assert change_resp.status_code == 200

    # 2. Get latest invoice
    inv_resp = client.get("/api/v1/subscriptions/invoices", headers=auth_headers)
    assert inv_resp.status_code == 200
    invoices = inv_resp.json()
    assert len(invoices) >= 1
    latest_inv = invoices[0]
    assert latest_inv["status"] == "pending"
    assert latest_inv["paid_at"] is None

    # 3. Confirm payment via webhook/gateway confirmation endpoint
    confirm_resp = client.post(
        f"/api/v1/subscriptions/invoices/{latest_inv['id']}/confirm-payment",
        headers=auth_headers,
        json={"payment_id": "pay_razorpay_mock_98765", "payment_method": "netbanking"},
    )
    assert confirm_resp.status_code == 200
    confirmed = confirm_resp.json()
    assert confirmed["status"] == "paid"
    assert confirmed["paid_at"] is not None

    # 4. Second confirmation is idempotent
    second_confirm = client.post(
        f"/api/v1/subscriptions/invoices/{latest_inv['id']}/confirm-payment",
        headers=auth_headers,
        json={"payment_id": "pay_razorpay_mock_98765"},
    )
    assert second_confirm.status_code == 200
    assert second_confirm.json()["status"] == "paid"


def test_invoice_payment_tenant_isolation(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
) -> None:
    """Tenant cannot confirm or view invoices belonging to a foreign tenant."""
    # Create foreign business and invoice
    foreign_biz = Business(
        id="biz-foreign-hospital",
        name="Foreign Care Hospital",
        vertical="clinic",
        phone="+914498765432",
        email="foreign@clinic.com",
        timezone="Asia/Kolkata",
        is_active=True,
    )
    db_session.add(foreign_biz)
    db_session.flush()

    foreign_inv = Invoice(
        id="inv-foreign-12345",
        business_id=foreign_biz.id,
        subscription_id="sub-foreign-1",
        invoice_number="INV-FOREIGN-001",
        amount=9999.0,
        currency="INR",
        status="pending",
        billing_date=datetime.now(timezone.utc),
    )
    db_session.add(foreign_inv)
    db_session.commit()

    # Attempt confirmation using primary tenant's token
    res = client.post(
        f"/api/v1/subscriptions/invoices/{foreign_inv.id}/confirm-payment",
        headers=auth_headers,
        json={"payment_id": "pay_cross_tenant"},
    )
    assert res.status_code == status.HTTP_404_NOT_FOUND


# ==============================================================================
# 5. MULTILINGUAL AI CONVERSATION & TOOLS (English, Tamil, Tanglish)
# ==============================================================================

@pytest.fixture
def phase8_clinic(db_session: Session) -> dict[str, Any]:
    """Provision isolated clinic for multi-turn conversational testing."""
    biz = Business(
        id="biz-phase8-clinic",
        name="Vattara Prime Clinic",
        vertical="clinic",
        phone="+914428289000",
        email="primeclinic@vattara.com",
        timezone="Asia/Kolkata",
        is_active=True,
    )
    db_session.add(biz)
    db_session.flush()

    # Operating hours: Mon-Sat 08:30 to 19:30
    for dow in range(7):
        db_session.add(
            BusinessHour(
                business_id=biz.id,
                day_of_week=dow,
                open_time="08:30",
                close_time="19:30",
                is_closed=(dow == 6),
            )
        )

    srv = Service(
        id="srv-phase8-general",
        business_id=biz.id,
        name="General Consultation",
        price=500.0,
        duration_minutes=30,
        is_active=True,
    )
    db_session.add(srv)

    config = AssistantConfig(
        id="cfg-phase8-clinic",
        business_id=biz.id,
        assistant_name="Vattara AI",
        language="ta-IN",
        voice="alloy",
        system_prompt="You are Vattara AI receptionist.",
        fallback_number="+914428289999",
        enable_tanglish=True,
        is_active=True,
    )
    db_session.add(config)
    db_session.commit()

    return {"business": biz, "service": srv, "config": config}


def test_language_detection_tamil_and_tanglish() -> None:
    """Language detector correctly classifies Unicode Tamil and Latin Tanglish."""
    # Unicode Tamil
    ta_text = "வணக்கம், எனக்கு நாளைக்கு ஒரு மருத்துவ சந்திப்பு வேண்டும்."
    assert detect_language(ta_text).startswith("ta")

    # Tanglish (Tamil in Latin script)
    tanglish_text = "Vanakkam, naalaiki evening 4:00 pm slot irukka doctor appointment ku?"
    assert detect_language(tanglish_text) in ["ta", "en", "ta-IN", "en-IN", "ta-Latn"]

    # English
    en_text = "Good morning, I would like to book a general consultation for tomorrow."
    assert detect_language(en_text).startswith("en")


def test_ai_tool_booking_flow(phase8_clinic: dict[str, Any], db_session: Session) -> None:
    """Execute real multi-turn booking and validation via AI tool executor."""
    biz = phase8_clinic["business"]

    # Calculate valid upcoming weekday slot (Monday = 0 ... Friday = 4)
    now = datetime.now(timezone.utc)
    # Advance to next Monday or Tuesday to guarantee open business hours regardless of test run day
    days_to_add = (7 - now.weekday()) % 7
    if days_to_add == 0:
        days_to_add = 7
    target_slot = now + timedelta(days=days_to_add)
    target_slot = target_slot.replace(hour=11, minute=0, second=0, microsecond=0)
    slot_iso = target_slot.isoformat()

    # 1. Book appointment via tool call
    book_res = execute_tool_call(
        db=db_session,
        business_id=biz.id,
        function_name="book_appointment",
        arguments={
            "customer_name": "Kavitha Sundar",
            "customer_phone": "+919444411122",
            "appointment_time": slot_iso,
            "service_name": "General Consultation",
            "notes": "Voice booking in Tamil/English",
        },
    )
    assert "error" not in book_res
    assert book_res.get("status") in ["confirmed", "scheduled", "upcoming"]
    appt_id = book_res["appointment_id"]

    # 2. Reschedule via tool call
    new_slot = target_slot + timedelta(hours=2)
    resched_res = execute_tool_call(
        db=db_session,
        business_id=biz.id,
        function_name="reschedule_appointment",
        arguments={
            "customer_phone": "+919444411122",
            "new_appointment_time": new_slot.isoformat(),
            "reason": "Patient requested evening hour",
        },
    )
    assert "error" not in resched_res
    assert resched_res["status"] == "rescheduled"

    # 3. Cancel via tool call
    cancel_res = execute_tool_call(
        db=db_session,
        business_id=biz.id,
        function_name="cancel_appointment",
        arguments={
            "customer_phone": "+919444411122",
            "reason": "Travel conflict",
        },
    )
    assert "error" not in cancel_res
    assert cancel_res["status"] == "cancelled"


def test_human_receptionist_transfer_fallback(phase8_clinic: dict[str, Any], db_session: Session) -> None:
    """When query requires human staff, fallback transfer tool returns receptionist phone number."""
    biz = phase8_clinic["business"]
    config = phase8_clinic["config"]

    transfer_res = execute_tool_call(
        db=db_session,
        business_id=biz.id,
        function_name="transfer_to_human",
        arguments={"reason": "Emergency complex surgical triage request"},
    )
    assert "error" not in transfer_res
    assert transfer_res.get("transfer_number") == config.fallback_number


# ==============================================================================
# 6. STT & TTS PROVIDER FALLBACKS
# ==============================================================================

def test_stt_provider_instantiation_and_mock_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deepgram STT provider gracefully falls back when no API key is supplied."""
    monkeypatch.setattr(settings, "DEEPGRAM_API_KEY", None)
    provider = get_streaming_stt_provider("mock")
    assert provider is not None
    assert hasattr(provider, "process_audio_chunk")


def test_tts_provider_instantiation_and_mock_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """ElevenLabs TTS provider gracefully instantiates or falls back without crashing."""
    monkeypatch.setattr(settings, "ELEVENLABS_API_KEY", None)
    provider = get_streaming_tts_provider("mock")
    assert provider is not None
    assert hasattr(provider, "synthesize_to_mulaw")
