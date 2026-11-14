"""Automated tests for Phase 5.2 Twilio Voice Webhooks and Telephony Integration.

Verifies:
1. Valid incoming webhook processing and TwiML generation.
2. Twilio signature validation (valid, invalid, missing).
3. Required parameters validation (CallSid, From, To).
4. Unknown dialed phone number handling and polite rejection TwiML.
5. Customer resolution, auto-creation, and total_calls incrementing.
6. Call record creation and duplicate CallSid idempotency.
7. Multi-tenant call isolation.
8. Twilio health endpoint verification (connected, unconfigured, error).
"""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from twilio.base.exceptions import TwilioRestException
from twilio.request_validator import RequestValidator

from app.core.config import settings
from app.models.business import Business
from app.models.call import Call
from app.models.customer import Customer
from app.services.twilio_service import TwilioService, get_twilio_service

TEST_AUTH_TOKEN = "test_twilio_secret_token_abcdef12345"


@pytest.fixture
def twilio_mock_service() -> TwilioService:
    """Twilio service initialized with known deterministic test credentials."""
    return TwilioService(
        account_sid="ACmock00000000000000000000000000",
        auth_token=TEST_AUTH_TOKEN,
        phone_number="+12292523194",
        public_base_url="https://pushiness-disparate-pulmonary.ngrok-free.dev",
    )


@pytest.fixture
def test_tenants(db_session: Session) -> dict[str, Business]:
    """Create two distinct business tenants to verify routing and multi-tenant isolation."""
    biz1 = Business(
        name="Metro Care Hospital",
        vertical="hospital",
        email="reception@metrocare.com",
        phone="+12292523194",
        is_active=True,
    )
    biz2 = Business(
        name="Grand Azure Resort",
        vertical="hotel",
        email="frontdesk@grandazure.com",
        phone="+15559876543",
        is_active=True,
    )
    db_session.add_all([biz1, biz2])
    db_session.commit()
    db_session.refresh(biz1)
    db_session.refresh(biz2)
    return {"biz1": biz1, "biz2": biz2}


def compute_test_signature(url: str, params: dict[str, str], token: str = TEST_AUTH_TOKEN) -> str:
    """Helper to compute valid Twilio signature for mock requests."""
    validator = RequestValidator(token)
    return validator.compute_signature(url, params)


# ==============================================================================
# INCOMING VOICE WEBHOOK TESTS
# ==============================================================================

def test_valid_incoming_webhook_new_customer(
    client: TestClient,
    test_tenants: dict[str, Business],
    twilio_mock_service: TwilioService,
    db_session: Session,
) -> None:
    """Test valid incoming call creating a new Customer, logging Call record, and returning valid TwiML."""
    from app.main import app
    app.dependency_overrides[get_twilio_service] = lambda: twilio_mock_service

    try:
        endpoint = f"{settings.API_V1_STR}/voice/webhooks/incoming"
        url = f"http://testserver{endpoint}"

        payload = {
            "CallSid": "CA_TEST_CALL_ALPHA_001",
            "From": "+15551112222",
            "To": "+12292523194",
            "CallStatus": "ringing",
            "Direction": "inbound",
        }
        signature = compute_test_signature(url, payload)

        response = client.post(
            endpoint,
            data=payload,
            headers={"X-Twilio-Signature": signature},
        )

        assert response.status_code == 200
        assert "application/xml" in response.headers["content-type"]
        body = response.text
        assert "<Response>" in body
        assert "<Say" in body
        assert "Metro Care Hospital" in body
        assert "<Pause length=\"1\"" in body or "<Pause length=\"1\" />" in body or "length=\"1\"" in body

        # Verify Customer was created under biz1
        biz1 = test_tenants["biz1"]
        cust = db_session.scalar(
            select(Customer).where(
                Customer.business_id == biz1.id,
                Customer.phone == "+15551112222",
            )
        )
        assert cust is not None
        assert "Caller +15551112222" in cust.name
        assert cust.total_calls == 1

        # Verify Call record was created in calls table
        call = db_session.scalar(
            select(Call).where(Call.caller_phone == "+15551112222")
        )
        assert call is not None
        assert call.business_id == biz1.id
        assert call.customer_id == cust.id
        assert call.call_type == "incoming"
        assert call.status == "in_progress"
        assert "CA_TEST_CALL_ALPHA_001" in (call.id + (call.summary or ""))
    finally:
        app.dependency_overrides.pop(get_twilio_service, None)


def test_valid_incoming_webhook_existing_customer(
    client: TestClient,
    test_tenants: dict[str, Business],
    twilio_mock_service: TwilioService,
    db_session: Session,
) -> None:
    """Test incoming call recognizes an existing customer and increments total_calls."""
    from app.main import app
    app.dependency_overrides[get_twilio_service] = lambda: twilio_mock_service

    biz1 = test_tenants["biz1"]
    existing_cust = Customer(
        business_id=biz1.id,
        name="John Doe",
        phone="+15553334444",
        total_calls=3,
    )
    db_session.add(existing_cust)
    db_session.commit()
    db_session.refresh(existing_cust)

    try:
        endpoint = f"{settings.API_V1_STR}/voice/webhooks/incoming"
        url = f"http://testserver{endpoint}"

        payload = {
            "CallSid": "CA_TEST_CALL_BETA_002",
            "From": "+15553334444",
            "To": "+12292523194",
            "CallStatus": "ringing",
            "Direction": "inbound",
        }
        signature = compute_test_signature(url, payload)

        response = client.post(
            endpoint,
            data=payload,
            headers={"X-Twilio-Signature": signature},
        )
        assert response.status_code == 200

        # Verify existing customer total_calls incremented
        db_session.refresh(existing_cust)
        assert existing_cust.total_calls == 4
        assert existing_cust.name == "John Doe"

        # Verify Call record logged with customer's name
        call = db_session.scalar(
            select(Call).where(Call.caller_phone == "+15553334444")
        )
        assert call is not None
        assert call.caller_name == "John Doe"
        assert call.customer_id == existing_cust.id
    finally:
        app.dependency_overrides.pop(get_twilio_service, None)


def test_invalid_signature_rejected(
    client: TestClient,
    test_tenants: dict[str, Business],
    twilio_mock_service: TwilioService,
) -> None:
    """Test that a request with a forged/invalid signature is rejected with HTTP 403 Forbidden."""
    from app.main import app
    app.dependency_overrides[get_twilio_service] = lambda: twilio_mock_service

    try:
        endpoint = f"{settings.API_V1_STR}/voice/webhooks/incoming"
        payload = {
            "CallSid": "CA_FAKE_CALL_001",
            "From": "+15550009999",
            "To": "+12292523194",
        }
        response = client.post(
            endpoint,
            data=payload,
            headers={"X-Twilio-Signature": "invalid_forged_signature_xyz"},
        )
        assert response.status_code == 403
        assert "Invalid Twilio signature" in response.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_twilio_service, None)


def test_missing_signature_rejected(
    client: TestClient,
    test_tenants: dict[str, Business],
    twilio_mock_service: TwilioService,
) -> None:
    """Test that a request lacking the X-Twilio-Signature header is rejected with HTTP 403."""
    from app.main import app
    app.dependency_overrides[get_twilio_service] = lambda: twilio_mock_service

    try:
        endpoint = f"{settings.API_V1_STR}/voice/webhooks/incoming"
        payload = {
            "CallSid": "CA_NO_SIG_001",
            "From": "+15550009999",
            "To": "+12292523194",
        }
        response = client.post(endpoint, data=payload)
        assert response.status_code == 403
        assert "Invalid Twilio signature" in response.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_twilio_service, None)


def test_missing_required_call_parameters(
    client: TestClient,
    twilio_mock_service: TwilioService,
) -> None:
    """Test that a request missing mandatory fields (CallSid, From, or To) returns HTTP 400 Bad Request."""
    from app.main import app
    app.dependency_overrides[get_twilio_service] = lambda: twilio_mock_service

    try:
        endpoint = f"{settings.API_V1_STR}/voice/webhooks/incoming"
        url = f"http://testserver{endpoint}"

        # Missing To
        payload = {"CallSid": "CA_INCOMPLETE_001", "From": "+15551234567"}
        sig = compute_test_signature(url, payload)

        response = client.post(
            endpoint,
            data=payload,
            headers={"X-Twilio-Signature": sig},
        )
        assert response.status_code == 400
        assert "Missing required Twilio call parameters" in response.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_twilio_service, None)


def test_unknown_business_destination_number(
    client: TestClient,
    twilio_mock_service: TwilioService,
) -> None:
    """Test that an incoming call to an unmapped destination number returns polite rejection TwiML."""
    from app.main import app
    app.dependency_overrides[get_twilio_service] = lambda: twilio_mock_service

    try:
        endpoint = f"{settings.API_V1_STR}/voice/webhooks/incoming"
        url = f"http://testserver{endpoint}"

        payload = {
            "CallSid": "CA_UNKNOWN_NUM_001",
            "From": "+15559998888",
            "To": "+19990001111",  # Unregistered destination number
            "CallStatus": "ringing",
        }
        sig = compute_test_signature(url, payload)

        response = client.post(
            endpoint,
            data=payload,
            headers={"X-Twilio-Signature": sig},
        )
        assert response.status_code == 200
        assert "application/xml" in response.headers["content-type"]
        assert "not associated with an active business" in response.text
        assert "<Hangup" in response.text or "<Hangup/>" in response.text or "<Hangup />" in response.text
    finally:
        app.dependency_overrides.pop(get_twilio_service, None)


def test_duplicate_webhook_handling_idempotency(
    client: TestClient,
    test_tenants: dict[str, Business],
    twilio_mock_service: TwilioService,
    db_session: Session,
) -> None:
    """Test multiple webhooks for the same CallSid update existing session instead of duplicating."""
    from app.main import app
    app.dependency_overrides[get_twilio_service] = lambda: twilio_mock_service

    try:
        endpoint = f"{settings.API_V1_STR}/voice/webhooks/incoming"
        url = f"http://testserver{endpoint}"

        payload1 = {
            "CallSid": "CA_IDEMPOTENT_GAMMA_003",
            "From": "+15557778888",
            "To": "+12292523194",
            "CallStatus": "ringing",
        }
        sig1 = compute_test_signature(url, payload1)
        res1 = client.post(endpoint, data=payload1, headers={"X-Twilio-Signature": sig1})
        assert res1.status_code == 200

        # Second webhook for same CallSid with updated status
        payload2 = {
            "CallSid": "CA_IDEMPOTENT_GAMMA_003",
            "From": "+15557778888",
            "To": "+12292523194",
            "CallStatus": "in-progress",
        }
        sig2 = compute_test_signature(url, payload2)
        res2 = client.post(endpoint, data=payload2, headers={"X-Twilio-Signature": sig2})
        assert res2.status_code == 200

        # Verify only 1 Call record exists for this caller
        calls = db_session.scalars(
            select(Call).where(Call.caller_phone == "+15557778888")
        ).all()
        assert len(calls) == 1
        assert calls[0].status == "in_progress"
    finally:
        app.dependency_overrides.pop(get_twilio_service, None)


def test_multi_tenant_call_isolation(
    client: TestClient,
    test_tenants: dict[str, Business],
    twilio_mock_service: TwilioService,
    db_session: Session,
) -> None:
    """Test callers to Business 1 vs Business 2 are partitioned strictly into their respective tenants."""
    from app.main import app
    app.dependency_overrides[get_twilio_service] = lambda: twilio_mock_service

    biz1 = test_tenants["biz1"]
    biz2 = test_tenants["biz2"]

    try:
        endpoint = f"{settings.API_V1_STR}/voice/webhooks/incoming"
        url = f"http://testserver{endpoint}"

        # Call to Business 1 (Hospital)
        p1 = {
            "CallSid": "CA_ISOLATION_BIZ1",
            "From": "+15554445555",
            "To": biz1.phone,
            "CallStatus": "ringing",
        }
        res1 = client.post(endpoint, data=p1, headers={"X-Twilio-Signature": compute_test_signature(url, p1)})
        assert res1.status_code == 200
        assert "Metro Care Hospital" in res1.text

        # Same caller calls Business 2 (Resort)
        p2 = {
            "CallSid": "CA_ISOLATION_BIZ2",
            "From": "+15554445555",
            "To": biz2.phone,
            "CallStatus": "ringing",
        }
        res2 = client.post(endpoint, data=p2, headers={"X-Twilio-Signature": compute_test_signature(url, p2)})
        assert res2.status_code == 200
        assert "Grand Azure Resort" in res2.text

        # Verify Business 1 Call list contains BIZ1 call only
        b1_calls = db_session.scalars(select(Call).where(Call.business_id == biz1.id)).all()
        assert any("CA_ISOLATION_BIZ1" in (c.id + (c.summary or "")) for c in b1_calls)
        assert not any("CA_ISOLATION_BIZ2" in (c.id + (c.summary or "")) for c in b1_calls)

        # Verify Business 2 Call list contains BIZ2 call only
        b2_calls = db_session.scalars(select(Call).where(Call.business_id == biz2.id)).all()
        assert any("CA_ISOLATION_BIZ2" in (c.id + (c.summary or "")) for c in b2_calls)
        assert not any("CA_ISOLATION_BIZ1" in (c.id + (c.summary or "")) for c in b2_calls)
    finally:
        app.dependency_overrides.pop(get_twilio_service, None)


# ==============================================================================
# TWILIO HEALTH ENDPOINT TESTS
# ==============================================================================

def test_twilio_health_endpoint_connected(client: TestClient) -> None:
    """Test GET /api/v1/health/twilio when Twilio connectivity probe succeeds."""
    mock_service = MagicMock(spec=TwilioService)
    mock_service.check_connection.return_value = {
        "status": "connected",
        "configured": True,
        "account_sid_masked": "AC6d...de94",
        "account_name": "Vattara Production",
        "account_status": "active",
        "phone_number": "+12292523194",
        "public_base_url": "https://pushiness-disparate-pulmonary.ngrok-free.dev",
        "details": "Successfully connected to Twilio API.",
        "error": None,
    }

    from app.main import app
    app.dependency_overrides[get_twilio_service] = lambda: mock_service

    try:
        response = client.get(f"{settings.API_V1_STR}/health/twilio")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "connected"
        assert data["configured"] is True
        assert data["account_sid_masked"] == "AC6d...de94"
        assert data["account_name"] == "Vattara Production"
        assert data["phone_number"] == "+12292523194"
        assert data["public_base_url"] == "https://pushiness-disparate-pulmonary.ngrok-free.dev"
        assert data["error"] is None
    finally:
        app.dependency_overrides.pop(get_twilio_service, None)


def test_twilio_health_endpoint_unconfigured(client: TestClient) -> None:
    """Test GET /api/v1/health/twilio when Twilio credentials are not configured."""
    mock_service = MagicMock(spec=TwilioService)
    mock_service.check_connection.return_value = {
        "status": "unconfigured",
        "configured": False,
        "account_sid_masked": None,
        "account_name": None,
        "account_status": None,
        "phone_number": None,
        "public_base_url": None,
        "details": "Twilio credentials are not configured in environment variables.",
        "error": None,
    }

    from app.main import app
    app.dependency_overrides[get_twilio_service] = lambda: mock_service

    try:
        response = client.get(f"{settings.API_V1_STR}/health/twilio")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unconfigured"
        assert data["configured"] is False
    finally:
        app.dependency_overrides.pop(get_twilio_service, None)


def test_twilio_health_endpoint_error(client: TestClient) -> None:
    """Test GET /api/v1/health/twilio returns HTTP 503 when API connection fails."""
    mock_service = MagicMock(spec=TwilioService)
    mock_service.check_connection.return_value = {
        "status": "error",
        "configured": True,
        "account_sid_masked": "AC6d...de94",
        "account_name": None,
        "account_status": None,
        "phone_number": "+12292523194",
        "public_base_url": "https://pushiness-disparate-pulmonary.ngrok-free.dev",
        "details": "Twilio API authentication failed.",
        "error": "HTTP 401 error: Unable to authenticate",
    }

    from app.main import app
    app.dependency_overrides[get_twilio_service] = lambda: mock_service

    try:
        response = client.get(f"{settings.API_V1_STR}/health/twilio")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "error"
        assert data["error"] is not None
    finally:
        app.dependency_overrides.pop(get_twilio_service, None)
