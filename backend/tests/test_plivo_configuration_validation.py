"""Automated Validation Test Suite for Plivo Integration.

Validates the 6 core requirements:
1. Plivo API authentication (read-only Account probe, credential masking).
2. Application ID configuration (Application ID 33725332161907688, Answer URL, Hangup URL, POST methods).
3. Phone number configuration (+918031794113, active state, voice enabled, application association, tenant routing).
4. Incoming webhook (/api/v1/plivo/incoming, V3 signature check, tenant mapping, <Stream> XML, 403/400 errors).
5. WebSocket connection (/api/v1/plivo/stream, bidirectional audio handshake, playAudio greeting, stop & completion).
6. Plivo signature validation (HMAC-SHA256 V3 algorithm, replay protection, key rotation).

Constraints:
- No paid calls initiated.
- No modifications to Twilio or Exotel.
- Zero credential leakage.
"""

import base64
import hashlib
import hmac
import json
import anyio
import httpx
import pytest
from starlette.testclient import TestClient


def _receive_ws_text_with_timeout(ws, timeout_seconds: float = 3.0) -> str:
    """Receive a message from Starlette WebSocketTestSession with strict timeout to prevent indefinite hang."""
    async def _recv():
        with anyio.fail_after(timeout_seconds):
            return await ws._send_rx.receive()

    message = ws.portal.call(_recv)
    ws._raise_on_close(message)
    return str(message["text"])

from app.api.routes.voice import resolve_business_by_phone
from app.core.config import settings
from app.models.business import Business
from app.models.call import Call
from app.models.customer import Customer
from app.services.plivo_service import PlivoService, get_plivo_service

EXPECTED_APP_ID = "33725332161907688"
EXPECTED_PHONE_NUMBER = "+918031794113"


def compute_v3_signature(url: str, params: dict, nonce: str, auth_token: str) -> str:
    """Compute Plivo V3 HMAC-SHA256 signature using official specification."""
    return PlivoService.compute_v3_signature(
        auth_token=auth_token,
        uri=url,
        nonce=nonce,
        method="POST",
        params=params,
    )


# ==============================================================================
# Requirement 1: Plivo API Authentication
# ==============================================================================

def test_1_plivo_api_authentication():
    """Validate Plivo REST API authentication with configured credentials without exposing secrets."""
    assert settings.PLIVO_AUTH_ID, "PLIVO_AUTH_ID is not configured in settings/environment."
    assert settings.PLIVO_AUTH_TOKEN, "PLIVO_AUTH_TOKEN is not configured in settings/environment."

    service = get_plivo_service()
    assert service.is_configured is True

    # 1. Verify credentials masking (no raw secret exposure)
    masked = service.mask_auth_id(settings.PLIVO_AUTH_ID)
    assert masked is not None
    assert "..." in masked or "****" in masked
    assert settings.PLIVO_AUTH_TOKEN not in masked

    # 2. Check connection health via read-only Account endpoint
    health = service.check_connection()
    assert health["status"] == "connected", f"Plivo connection failed: {health.get('message')}"
    assert health["configured"] is True
    assert health["auth_id_masked"] == masked
    assert health["phone_number"] == EXPECTED_PHONE_NUMBER
    assert "Successfully authenticated" in health["message"]

    # 3. Direct read-only HTTP GET verification against Plivo REST Account API
    account_url = f"https://api.plivo.com/v1/Account/{settings.PLIVO_AUTH_ID}/"
    with httpx.Client(timeout=10.0) as client:
        res = client.get(account_url, auth=(settings.PLIVO_AUTH_ID, settings.PLIVO_AUTH_TOKEN))
        assert res.status_code == 200, f"Plivo API returned unexpected status {res.status_code}: {res.text}"
        data = res.json()
        assert "name" in data
        assert "account_type" in data
        # Ensure auth token is never echoed back by Plivo in response
        assert settings.PLIVO_AUTH_TOKEN not in res.text


# ==============================================================================
# Requirement 2: Application ID Configuration
# ==============================================================================

def test_2_application_id_configuration():
    """Validate Application ID configuration, Answer URL, and Hangup URL on Plivo Console/API."""
    assert settings.PLIVO_APP_ID == EXPECTED_APP_ID, (
        f"Configured PLIVO_APP_ID ({settings.PLIVO_APP_ID}) does not match expected {EXPECTED_APP_ID}"
    )

    app_url = f"https://api.plivo.com/v1/Account/{settings.PLIVO_AUTH_ID}/Application/{EXPECTED_APP_ID}/"
    with httpx.Client(timeout=10.0) as client:
        res = client.get(app_url, auth=(settings.PLIVO_AUTH_ID, settings.PLIVO_AUTH_TOKEN))
        assert res.status_code == 200, f"Plivo Application lookup failed (HTTP {res.status_code}): {res.text}"
        app_data = res.json()

        # Check App Name
        assert app_data.get("app_name") == "Vattara_Voice_Agent"

        # Check Answer URL & Method
        answer_url = app_data.get("answer_url") or ""
        assert "/api/v1/plivo/incoming" in answer_url, f"Answer URL missing '/api/v1/plivo/incoming': {answer_url}"
        assert app_data.get("answer_method", "").upper() == "POST"

        # Check Hangup URL & Method
        hangup_url = app_data.get("hangup_url") or ""
        assert "/api/v1/plivo/status" in hangup_url, f"Hangup URL missing '/api/v1/plivo/status': {hangup_url}"
        assert app_data.get("hangup_method", "").upper() == "POST"


# ==============================================================================
# Requirement 3: Phone Number Configuration
# ==============================================================================

def test_3_phone_number_configuration(db_session):
    """Validate phone number is active, voice-enabled, linked to Application ID, and mapped to tenant."""
    assert settings.PLIVO_PHONE_NUMBER == EXPECTED_PHONE_NUMBER, (
        f"Configured PLIVO_PHONE_NUMBER ({settings.PLIVO_PHONE_NUMBER}) does not match {EXPECTED_PHONE_NUMBER}"
    )

    clean_number = EXPECTED_PHONE_NUMBER.replace("+", "").strip()
    num_url = f"https://api.plivo.com/v1/Account/{settings.PLIVO_AUTH_ID}/Number/{clean_number}/"
    with httpx.Client(timeout=10.0) as client:
        res = client.get(num_url, auth=(settings.PLIVO_AUTH_ID, settings.PLIVO_AUTH_TOKEN))
        assert res.status_code == 200, f"Plivo Number lookup failed (HTTP {res.status_code}): {res.text}"
        num_data = res.json()

        assert num_data.get("active") is True, "Phone number is not active in Plivo account."
        assert num_data.get("voice_enabled") is True, "Phone number does not have voice enabled."
        assert num_data.get("number") == clean_number

        # Verify application association links to EXPECTED_APP_ID
        app_uri = num_data.get("application") or ""
        assert EXPECTED_APP_ID in app_uri, (
            f"Phone number application link ({app_uri}) does not reference Application ID {EXPECTED_APP_ID}"
        )

    # Verify inbound number tenant routing resolves to an active Business
    resolved_biz = resolve_business_by_phone(db_session, EXPECTED_PHONE_NUMBER)
    assert resolved_biz is not None, f"Destination phone {EXPECTED_PHONE_NUMBER} did not resolve to any Business."
    assert resolved_biz.is_active is True


# ==============================================================================
# Requirement 4: Incoming Webhook Validation (/api/v1/plivo/incoming)
# ==============================================================================

def test_4_incoming_webhook_flow(client: TestClient, db_session):
    """Validate incoming call webhook processing, DB session creation, and bidirectional <Stream> XML."""
    call_uuid = "val-plivo-call-4001"
    caller = "+919876543210"
    destination = EXPECTED_PHONE_NUMBER

    payload = {
        "CallUUID": call_uuid,
        "From": caller,
        "To": destination,
        "CallStatus": "ringing",
        "Direction": "inbound",
    }
    endpoint = "/api/v1/plivo/incoming"
    url = f"http://testserver{endpoint}"
    nonce = "777888999111"
    sig = compute_v3_signature(url, payload, nonce, settings.PLIVO_AUTH_TOKEN)

    response = client.post(
        endpoint,
        data=payload,
        headers={
            "X-Plivo-Signature-V3": sig,
            "X-Plivo-Signature-V3-Nonce": nonce,
        },
    )

    assert response.status_code == 200
    assert "application/xml" in response.headers.get("content-type", "")
    content = response.text
    assert "<Response>" in content
    assert "<Stream" in content
    assert 'bidirectional="true"' in content
    assert 'keepCallAlive="true"' in content
    assert 'contentType="audio/x-mulaw;rate=8000"' in content
    assert f"call_uuid={call_uuid}" in content
    assert f"to={destination.replace('+', '%2B')}" in content or f"to={destination}" in content

    # Verify Call record in DB
    call = db_session.get(Call, call_uuid)
    assert call is not None
    assert call.caller_phone == caller
    assert call.status == "in_progress"

    # Verify Customer record
    customer = db_session.get(Customer, call.customer_id)
    assert customer is not None
    assert customer.phone == caller


def test_4_incoming_webhook_security_rejections(client: TestClient):
    """Validate incoming webhook security: rejection of invalid signatures and malformed payloads."""
    # 1. Invalid signature -> 403 Forbidden
    res_403 = client.post(
        "/api/v1/plivo/incoming",
        data={"CallUUID": "val-bad-sig", "From": "+919876543210", "To": EXPECTED_PHONE_NUMBER},
        headers={
            "X-Plivo-Signature-V3": "completely_bogus_signature==",
            "X-Plivo-Signature-V3-Nonce": "999999",
        },
    )
    assert res_403.status_code == 403
    assert "Invalid Plivo V3 signature" in res_403.text

    # 2. Missing mandatory fields -> 400 Bad Request
    payload = {"CallUUID": "val-missing-to", "From": "+919876543210"}
    url = "http://testserver/api/v1/plivo/incoming"
    nonce = "888111222"
    sig = compute_v3_signature(url, payload, nonce, settings.PLIVO_AUTH_TOKEN)

    res_400 = client.post(
        "/api/v1/plivo/incoming",
        data=payload,
        headers={
            "X-Plivo-Signature-V3": sig,
            "X-Plivo-Signature-V3-Nonce": nonce,
        },
    )
    assert res_400.status_code == 400
    assert "Missing required Plivo call parameters" in res_400.text


# ==============================================================================
# Requirement 5: WebSocket Connection Validation (/api/v1/plivo/stream)
# ==============================================================================

def test_5_websocket_connection_and_audio_streaming(client: TestClient, db_session):
    """Validate bidirectional WebSocket audio stream connection, start handshake, and playAudio packets."""
    biz = resolve_business_by_phone(db_session, EXPECTED_PHONE_NUMBER)
    call_uuid = "val-ws-call-5001"
    stream_id = f"plivo_{call_uuid}"
    caller = "+919876543210"

    # Seed call record
    call = Call(
        id=call_uuid,
        business_id=biz.id,
        caller_phone=caller,
        status="in_progress",
        duration_seconds=0,
    )
    db_session.add(call)
    db_session.commit()

    ws_url = (
        f"/api/v1/plivo/stream?business_id={biz.id}&call_uuid={call_uuid}"
        f"&caller_phone={caller}&to={EXPECTED_PHONE_NUMBER}"
    )

    with client.websocket_connect(ws_url) as ws:
        # 1. Send Plivo 'start' event
        ws.send_text(
            json.dumps({
                "event": "start",
                "start": {
                    "streamId": stream_id,
                    "callId": call_uuid,
                },
            })
        )

        # 2. Receive AI greeting playAudio packet
        received_play_audio = False
        for _ in range(5):
            try:
                raw = _receive_ws_text_with_timeout(ws, timeout_seconds=3.0)
            except TimeoutError:
                break
            msg = json.loads(raw)
            if msg.get("event") == "playAudio":
                media = msg.get("media", {})
                assert media.get("contentType") == "audio/x-mulaw"
                assert media.get("sampleRate") == 8000
                assert "payload" in media
                received_play_audio = True
                break

        assert received_play_audio is True, "Expected 'playAudio' event from WebSocket stream."

        # 3. Send Plivo 'stop' event
        ws.send_text(
            json.dumps({
                "event": "stop",
                "stop": {
                    "streamId": stream_id,
                },
            })
        )

    # 4. Verify Call status transitioned to completed
    db_session.refresh(call)
    assert call.status == "completed"


# ==============================================================================
# Requirement 6: Plivo Signature Validation
# ==============================================================================

def test_6_plivo_signature_validation():
    """Validate Plivo V3 HMAC-SHA256 signature verification algorithm, tampered detection, and key rotation."""
    service = get_plivo_service()
    url = "https://pushiness-disparate-pulmonary.ngrok-free.dev/api/v1/plivo/incoming"
    nonce = "abcdef1234567890"
    params = {
        "CallUUID": "val-sig-test-01",
        "From": "+919876543210",
        "To": EXPECTED_PHONE_NUMBER,
    }

    # 1. Valid Signature
    correct_sig = compute_v3_signature(url, params, nonce, settings.PLIVO_AUTH_TOKEN)
    assert service.validate_v3_signature(
        uri=url,
        nonce=nonce,
        signature=correct_sig,
        method="POST",
        params=params,
    ) is True

    # 2. Tampered Parameter -> Rejection
    tampered_params = dict(params)
    tampered_params["From"] = "+910000000000"
    assert service.validate_v3_signature(
        uri=url,
        nonce=nonce,
        signature=correct_sig,
        method="POST",
        params=tampered_params,
    ) is False

    # 3. Tampered Nonce -> Rejection
    assert service.validate_v3_signature(
        uri=url,
        nonce="wrong_nonce_9999",
        signature=correct_sig,
        method="POST",
        params=params,
    ) is False

    # 4. Key Rotation / Multiple Signatures in Header
    multi_sig_header = f"expired_signature_123, {correct_sig}"
    assert service.validate_v3_signature(
        uri=url,
        nonce=nonce,
        signature=multi_sig_header,
        method="POST",
        params=params,
    ) is True

    # 5. Missing Nonce or Missing Signature -> Rejection
    assert service.validate_v3_signature(uri=url, nonce=None, signature=correct_sig, params=params) is False
    assert service.validate_v3_signature(uri=url, nonce=nonce, signature=None, params=params) is False


def test_6_exact_captured_plivo_carrier_signatures():
    """Verify official Plivo V3 validation against actual carrier webhooks captured live during live testing."""
    service = get_plivo_service()
    incoming_url = "https://pushiness-disparate-pulmonary.ngrok-free.dev/api/v1/plivo/incoming"

    # Captured from live Plivo call at 13:02:10 (HTTP 403 incident)
    payload_1302 = {
        "BillRate": "0.00475",
        "CallStatus": "ringing",
        "CallUUID": "681f0bc6-b05f-4889-ab97-e27d82d42836",
        "CallerName": "+918667520831",
        "ComplianceApplicationId": "3d69a523-0759-41c9-8da2-b0f7a4457586",
        "ComplianceStatus": "accepted",
        "CountryCode": "IN",
        "Direction": "inbound",
        "Event": "StartApp",
        "From": "918667520831",
        "ParentAuthID": "MANDAYZWYZYMMTNMNKOS",
        "RouteType": "Domestic_Anchored",
        "STIRAttestation": "Not Applicable",
        "STIRVerification": "Not Applicable",
        "SessionStart": "2026-11-13 07:32:09.567944",
        "To": "918031794113",
    }
    nonce_1302 = "97393408873788816020"
    carrier_sig_1302 = "z8a4Bh9q/ipv7uUsPI46xq6zksF0rsmooutDCp450T0="

    assert service.validate_v3_signature(
        uri=incoming_url,
        nonce=nonce_1302,
        signature=carrier_sig_1302,
        method="POST",
        params=payload_1302,
    ) is True

    # Captured from live Plivo call at 13:01:54
    payload_1301 = dict(payload_1302)
    payload_1301["CallUUID"] = "ef7e0f2b-93c9-4cb5-9ea8-ada68adb5ec6"
    payload_1301["SessionStart"] = "2026-11-13 07:31:53.417917"
    nonce_1301 = "86747780264935837593"
    carrier_sig_1301 = "3GFBmQQP4PrYPb2xE8pBJ7COgfAovZTYjlIJkbFBP1k="

    assert service.validate_v3_signature(
        uri=incoming_url,
        nonce=nonce_1301,
        signature=carrier_sig_1301,
        method="POST",
        params=payload_1301,
    ) is True

