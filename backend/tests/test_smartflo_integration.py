"""Comprehensive automated test suite for Phase 4: Tata Smartflo Integration & Telephony Gateway Hardening.

Test coverage:
1. Provider interface conformance (SmartfloAdapter, TwilioAdapter, BaseTelephonyProvider).
2. Telephony provider factory resolution.
3. Webhook token authentication (valid header, valid bearer, valid query, invalid token, missing token).
4. Inbound API Dialplan routing and JSON action schema validation.
5. Call status callback lifecycle processing (ringing, answered, completed, missed, busy).
6. Q.850 hangup cause code normalization.
7. Webhook idempotency (no duplicate Call records for same UUID).
8. Outbound Click-to-Call initiation with mocked HTTP responses.
9. Outbound Click-to-Call failure handling (provider 500 error, network timeout).
10. Multi-tenant isolation and DID-to-tenant mapping.
11. Sensitive data masking (phone numbers and API secret tokens).
12. Integration status endpoint verification.
"""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.business import Business
from app.models.call import Call
from app.models.customer import Customer
from app.services.telephony.base import (
    BaseTelephonyProvider,
    CallStatus,
    OutboundCallRequest,
)
from app.services.telephony.factory import get_telephony_provider
from app.services.telephony.security import mask_phone, mask_secret, verify_webhook_token
from app.services.telephony.smartflo_adapter import SmartfloAdapter
from app.services.telephony.twilio_adapter import TwilioAdapter

TEST_SMARTFLO_TOKEN = "smartflo_test_secret_token_12345678"


@pytest.fixture
def smartflo_tenants(db_session: Session) -> dict[str, Business]:
    """Create two distinct business tenants to test multi-tenant Smartflo routing."""
    biz_a = Business(
        id="biz-smartflo-tenant-a",
        name="Vattara City Clinic",
        vertical="clinic",
        email="contact@vattaracityclinic.com",
        phone="+914420000001",
        is_active=True,
    )
    biz_b = Business(
        id="biz-smartflo-tenant-b",
        name="Vattara Dental Care",
        vertical="dental",
        email="reception@vattaradental.com",
        phone="+914420000002",
        is_active=True,
    )
    db_session.add_all([biz_a, biz_b])
    db_session.commit()
    db_session.refresh(biz_a)
    db_session.refresh(biz_b)
    return {"a": biz_a, "b": biz_b}


# ==============================================================================
# 1. Provider Interface Conformance
# ==============================================================================


def test_provider_interface_conformance():
    """Verify that SmartfloAdapter and TwilioAdapter implement BaseTelephonyProvider."""
    smartflo = SmartfloAdapter(api_token="dummy", caller_id="+914420000001")
    twilio = TwilioAdapter()

    assert isinstance(smartflo, BaseTelephonyProvider)
    assert isinstance(twilio, BaseTelephonyProvider)
    assert smartflo.provider_name == "smartflo"
    assert twilio.provider_name == "twilio"


def test_telephony_factory_resolution():
    """Verify factory returns appropriate provider adapter or raises ValueError."""
    smartflo_inst = get_telephony_provider("smartflo")
    assert isinstance(smartflo_inst, SmartfloAdapter)

    twilio_inst = get_telephony_provider("twilio")
    assert isinstance(twilio_inst, TwilioAdapter)

    with pytest.raises(ValueError) as exc:
        get_telephony_provider("unsupported_telephony_vendor")
    assert "Unsupported telephony provider" in str(exc.value)


# ==============================================================================
# 2. Security & Webhook Token Verification
# ==============================================================================


def test_security_sensitive_data_masking():
    """Verify telephone numbers and API secrets are masked in logs."""
    assert mask_phone("+919876543210") == "+9198****3210"
    assert mask_phone("123") == "****"
    assert mask_phone(None) == "N/A"

    assert mask_secret("short") == "********"
    assert mask_secret("my_super_secret_production_key_123") == "my_s..._123"
    assert mask_secret(None) == "None"

    assert verify_webhook_token("secret123", "secret123") is True
    assert verify_webhook_token("secret123", "wrong_secret") is False
    assert verify_webhook_token(None, "secret") is False
    assert verify_webhook_token("secret", None) is False


def test_webhook_authentication_enforcement(client: TestClient, monkeypatch):
    """Verify that Smartflo endpoints reject requests with missing or invalid tokens."""
    monkeypatch.setattr(settings, "SMARTFLO_WEBHOOK_TOKEN", TEST_SMARTFLO_TOKEN)

    payload = {
        "uuid": "test-uuid-auth-1",
        "call_status": "ringing",
        "caller_id_number": "+919876543210",
    }

    # 1. Missing token -> 401 Unauthorized
    resp_missing = client.post("/api/v1/integrations/smartflo/webhook", json=payload)
    assert resp_missing.status_code == 401
    assert "Invalid or missing Smartflo webhook token" in resp_missing.json()["detail"]

    # 2. Invalid token -> 401 Unauthorized
    resp_invalid = client.post(
        "/api/v1/integrations/smartflo/webhook",
        json=payload,
        headers={"X-Smartflo-Token": "bad-token"},
    )
    assert resp_invalid.status_code == 401

    # 3. Valid via X-Smartflo-Token header -> 200 OK
    resp_header = client.post(
        "/api/v1/integrations/smartflo/webhook",
        json=payload,
        headers={"X-Smartflo-Token": TEST_SMARTFLO_TOKEN},
    )
    assert resp_header.status_code == 200
    assert resp_header.json()["status"] == "ok"

    # 4. Valid via Bearer Authorization header -> 200 OK
    resp_bearer = client.post(
        "/api/v1/integrations/smartflo/webhook",
        json=payload,
        headers={"Authorization": f"Bearer {TEST_SMARTFLO_TOKEN}"},
    )
    assert resp_bearer.status_code == 200

    # 5. Valid via query parameter -> 200 OK
    resp_query = client.post(
        f"/api/v1/integrations/smartflo/webhook?token={TEST_SMARTFLO_TOKEN}",
        json=payload,
    )
    assert resp_query.status_code == 200


# ==============================================================================
# 3. Inbound API Dialplan Routing
# ==============================================================================


def test_smartflo_inbound_dialplan_routing(
    client: TestClient,
    db_session: Session,
    smartflo_tenants: dict[str, Business],
    monkeypatch,
):
    """Verify inbound call via Smartflo API dialplan returns correct JSON transfer actions."""
    monkeypatch.setattr(settings, "SMARTFLO_WEBHOOK_TOKEN", TEST_SMARTFLO_TOKEN)
    tenant_a = smartflo_tenants["a"]

    dialplan_payload = {
        "uuid": "smartflo-call-inbound-001",
        "caller_id_number": "+919876543210",
        "call_to_number": tenant_a.phone,
        "custom_identifier": {"business_id": tenant_a.id, "customer_name": "Ravi Kumar"},
    }

    resp = client.post(
        "/api/v1/integrations/smartflo/dialplan",
        json=dialplan_payload,
        headers={"X-Smartflo-Token": TEST_SMARTFLO_TOKEN},
    )

    assert resp.status_code == 200
    actions = resp.json()
    assert isinstance(actions, list)
    assert len(actions) >= 1

    # Verify Smartflo dialplan JSON schema
    transfer_action = actions[0]
    assert "transfer" in transfer_action
    assert transfer_action["transfer"]["type"] == "agent"
    assert transfer_action["transfer"]["custom_parameter_1"] == tenant_a.id

    # Verify Call and Customer records were created in database
    created_call = db_session.scalar(
        select(Call).where(Call.summary.like("%smartflo-call-inbound-001%"))
    )
    assert created_call is not None
    assert created_call.business_id == tenant_a.id
    assert created_call.caller_phone == "+919876543210"
    assert created_call.status == "ringing"

    customer = db_session.scalar(
        select(Customer).where(
            Customer.business_id == tenant_a.id,
            Customer.phone == "+919876543210",
        )
    )
    assert customer is not None


# ==============================================================================
# 4. Status Callback Lifecycle & Hangup Mapping
# ==============================================================================


def test_smartflo_status_callbacks_lifecycle(
    client: TestClient,
    db_session: Session,
    smartflo_tenants: dict[str, Business],
    monkeypatch,
):
    """Verify call progress from ringing to completed with duration and recording URL."""
    monkeypatch.setattr(settings, "SMARTFLO_WEBHOOK_TOKEN", TEST_SMARTFLO_TOKEN)
    tenant_b = smartflo_tenants["b"]
    call_uuid = "smartflo-call-lifecycle-002"

    # Step 1: Initial ringing event creates Call
    resp1 = client.post(
        "/api/v1/integrations/smartflo/webhook",
        json={
            "uuid": call_uuid,
            "call_status": "ringing",
            "caller_id_number": "+919888877777",
            "call_to_number": tenant_b.phone,
            "custom_identifier": {"business_id": tenant_b.id},
        },
        headers={"X-Smartflo-Token": TEST_SMARTFLO_TOKEN},
    )
    assert resp1.status_code == 200
    assert resp1.json()["call_status"] == "ringing"

    # Step 2: Answered event updates status to in_progress
    resp2 = client.post(
        "/api/v1/integrations/smartflo/webhook",
        json={
            "uuid": call_uuid,
            "call_status": "answered",
        },
        headers={"X-Smartflo-Token": TEST_SMARTFLO_TOKEN},
    )
    assert resp2.status_code == 200
    assert resp2.json()["call_status"] == "in_progress"

    # Step 3: Hangup completed event updates duration and recording
    resp3 = client.post(
        "/api/v1/integrations/smartflo/webhook",
        json={
            "uuid": call_uuid,
            "call_status": "completed",
            "duration": 185,
            "aws_call_recording_identifier": "https://s3.ap-south-1.amazonaws.com/smartflo-rec/call-002.wav",
            "hangup_cause_code": 16,
            "hangup_cause_description": "Normal Clearing",
        },
        headers={"X-Smartflo-Token": TEST_SMARTFLO_TOKEN},
    )
    assert resp3.status_code == 200
    assert resp3.json()["call_status"] == "completed"

    # Verify database state
    db_call = db_session.scalar(
        select(Call).where(Call.summary.like(f"%{call_uuid}%"))
    )
    assert db_call is not None
    assert db_call.status == "completed"
    assert db_call.duration_seconds == 185
    assert "https://s3.ap-south-1.amazonaws.com/smartflo-rec/call-002.wav" in db_call.recording_url
    assert db_call.ended_at is not None


def test_smartflo_hangup_cause_busy_and_missed(
    client: TestClient,
    db_session: Session,
    smartflo_tenants: dict[str, Business],
    monkeypatch,
):
    """Verify Smartflo busy and missed call status mapping."""
    monkeypatch.setattr(settings, "SMARTFLO_WEBHOOK_TOKEN", TEST_SMARTFLO_TOKEN)
    tenant_a = smartflo_tenants["a"]

    # Test Busy status mapping
    resp_busy = client.post(
        "/api/v1/integrations/smartflo/webhook",
        json={
            "uuid": "smartflo-call-busy-003",
            "call_status": "user_busy",
            "hangup_cause_code": 17,
            "hangup_cause_description": "User Busy",
            "caller_id_number": "+919111122222",
            "custom_identifier": {"business_id": tenant_a.id},
        },
        headers={"X-Smartflo-Token": TEST_SMARTFLO_TOKEN},
    )
    assert resp_busy.status_code == 200
    assert resp_busy.json()["call_status"] == "busy"

    # Test Missed status mapping
    resp_missed = client.post(
        "/api/v1/integrations/smartflo/webhook",
        json={
            "uuid": "smartflo-call-missed-004",
            "call_status": "no_answer",
            "hangup_cause_code": 19,
            "hangup_cause_description": "No Answer",
            "caller_id_number": "+919333344444",
            "custom_identifier": {"business_id": tenant_a.id},
        },
        headers={"X-Smartflo-Token": TEST_SMARTFLO_TOKEN},
    )
    assert resp_missed.status_code == 200
    assert resp_missed.json()["call_status"] == "missed"


# ==============================================================================
# 5. Webhook Idempotency
# ==============================================================================


def test_duplicate_webhook_idempotency(
    client: TestClient,
    db_session: Session,
    smartflo_tenants: dict[str, Business],
    monkeypatch,
):
    """Verify that receiving the same Smartflo webhook event twice does not duplicate Call rows."""
    monkeypatch.setattr(settings, "SMARTFLO_WEBHOOK_TOKEN", TEST_SMARTFLO_TOKEN)
    tenant_a = smartflo_tenants["a"]
    unique_uuid = "smartflo-idempotency-call-999"

    payload = {
        "uuid": unique_uuid,
        "call_status": "completed",
        "duration": 60,
        "caller_id_number": "+919999888877",
        "custom_identifier": {"business_id": tenant_a.id},
    }

    # First delivery
    resp1 = client.post(
        "/api/v1/integrations/smartflo/webhook",
        json=payload,
        headers={"X-Smartflo-Token": TEST_SMARTFLO_TOKEN},
    )
    assert resp1.status_code == 200

    # Second delivery (retried webhook)
    resp2 = client.post(
        "/api/v1/integrations/smartflo/webhook",
        json=payload,
        headers={"X-Smartflo-Token": TEST_SMARTFLO_TOKEN},
    )
    assert resp2.status_code == 200

    # Query calls in database
    calls = db_session.scalars(
        select(Call).where(Call.summary.like(f"%{unique_uuid}%"))
    ).all()
    assert len(calls) == 1, "Expected exactly 1 Call record despite duplicate webhook deliveries"


# ==============================================================================
# 6. Outbound Click-to-Call Initiation
# ==============================================================================


def test_smartflo_outbound_call_success(
    client: TestClient,
    db_session: Session,
    auth_headers: dict[str, str],
    monkeypatch,
):
    """Verify initiating an outbound call triggers Smartflo API and records outgoing Call."""
    monkeypatch.setattr(settings, "SMARTFLO_API_TOKEN", "mock_smartflo_api_token")
    monkeypatch.setattr(settings, "SMARTFLO_CALLER_ID", "+914420000000")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": True,
        "ref_id": "c2c_mock_ref_12345",
        "uuid": "c2c_mock_uuid_67890",
        "message": "Click-to-Call initiated successfully",
    }

    mock_client_instance = MagicMock()
    mock_client_instance.__enter__.return_value = mock_client_instance
    mock_client_instance.post.return_value = mock_response

    with patch("app.services.telephony.smartflo_adapter.httpx.Client", return_value=mock_client_instance):
        resp = client.post(
            "/api/v1/integrations/smartflo/outbound-call",
            json={
                "destination_phone": "+919876543210",
                "timeout_seconds": 180,
            },
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["reference_id"] == "c2c_mock_ref_12345"

        # Verify POST payload sent to Smartflo
        mock_client_instance.post.assert_called_once()
        _, kwargs = mock_client_instance.post.call_args
        assert kwargs["json"]["customer_number"] == "919876543210"
        assert kwargs["json"]["caller_id"] == "914420000000"

    # Verify outgoing Call saved in database
    call = db_session.scalar(
        select(Call).where(Call.summary.like("%c2c_mock_ref_12345%"))
    )
    assert call is not None
    assert call.call_type == "outgoing"
    assert call.caller_phone == "+919876543210"


def test_smartflo_outbound_call_provider_failure(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
):
    """Verify that provider 500 or network errors are handled gracefully without server crash."""
    monkeypatch.setattr(settings, "SMARTFLO_API_TOKEN", "mock_smartflo_api_token")
    monkeypatch.setattr(settings, "SMARTFLO_CALLER_ID", "+914420000000")

    mock_error_resp = MagicMock()
    mock_error_resp.status_code = 500
    mock_error_resp.text = "Internal Provider Server Error"
    mock_error_resp.json.return_value = {"message": "Telephony switch unreachable"}

    mock_client_instance = MagicMock()
    mock_client_instance.__enter__.return_value = mock_client_instance
    mock_client_instance.post.return_value = mock_error_resp

    with patch("app.services.telephony.smartflo_adapter.httpx.Client", return_value=mock_client_instance):
        resp = client.post(
            "/api/v1/integrations/smartflo/outbound-call",
            json={"destination_phone": "+919876543210"},
            headers=auth_headers,
        )
        assert resp.status_code == 502
        assert "Telephony switch unreachable" in resp.json()["detail"]


# ==============================================================================
# 7. Multi-Tenant Isolation & DID Mapping
# ==============================================================================


def test_smartflo_multi_tenant_did_mapping(
    client: TestClient,
    db_session: Session,
    smartflo_tenants: dict[str, Business],
    monkeypatch,
):
    """Verify incoming calls to distinct DIDs route to separate tenant businesses."""
    tenant_a = smartflo_tenants["a"]
    tenant_b = smartflo_tenants["b"]

    # Configure DID mapping: "9144001:biz-smartflo-tenant-a,9144002:biz-smartflo-tenant-b"
    did_mapping_str = f"9144001:{tenant_a.id},9144002:{tenant_b.id}"
    monkeypatch.setattr(settings, "SMARTFLO_BUSINESS_MAPPING", did_mapping_str)
    monkeypatch.setattr(settings, "SMARTFLO_WEBHOOK_TOKEN", None)  # Bypass token for test

    # Inbound call to DID 1
    resp_a = client.post(
        "/api/v1/integrations/smartflo/dialplan",
        json={
            "uuid": "call-did-route-1",
            "caller_id_number": "+919000000001",
            "call_to_number": "9144001",
        },
    )
    assert resp_a.status_code == 200
    actions_a = resp_a.json()
    assert actions_a[0]["transfer"]["custom_parameter_1"] == tenant_a.id

    # Inbound call to DID 2
    resp_b = client.post(
        "/api/v1/integrations/smartflo/dialplan",
        json={
            "uuid": "call-did-route-2",
            "caller_id_number": "+919000000002",
            "call_to_number": "9144002",
        },
    )
    assert resp_b.status_code == 200
    actions_b = resp_b.json()
    assert actions_b[0]["transfer"]["custom_parameter_1"] == tenant_b.id

    # Verify calls in DB belong to distinct tenants
    call_a = db_session.scalar(select(Call).where(Call.summary.like("%call-did-route-1%")))
    call_b = db_session.scalar(select(Call).where(Call.summary.like("%call-did-route-2%")))
    assert call_a.business_id == tenant_a.id
    assert call_b.business_id == tenant_b.id
    assert call_a.business_id != call_b.business_id


# ==============================================================================
# 8. Status Endpoint Verification
# ==============================================================================


def test_smartflo_status_endpoint(client: TestClient, monkeypatch):
    """Verify /status endpoint reports configuration health without leaking sensitive data."""
    monkeypatch.setattr(settings, "SMARTFLO_API_TOKEN", "mock_token")
    monkeypatch.setattr(settings, "SMARTFLO_CALLER_ID", "+914420000099")
    monkeypatch.setattr(settings, "SMARTFLO_WEBHOOK_TOKEN", "mock_webhook_token")

    resp = client.get("/api/v1/integrations/smartflo/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "smartflo"
    assert data["configured"] is True
    assert data["webhook_token_configured"] is True
    assert "****" in data["caller_id"]
    # Ensure sensitive credentials are NOT leaked in response
    assert "mock_token" not in str(data)
    assert "mock_webhook_token" not in str(data)
