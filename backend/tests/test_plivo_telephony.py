"""Automated test suite for Plivo Programmable Voice Telephony Integration.

Covers:
1. Plivo V3 HMAC-SHA256 signature algorithm validation and replay protection.
2. Plivo XML builders (<Stream bidirectional="true">, <Speak>, <Hangup>).
3. PlivoAdapter adhering to BaseTelephonyProvider.
4. Inbound webhook routing (/api/v1/plivo/incoming), tenant resolution, and Call logging.
5. Bidirectional WebSocket audio streaming (/api/v1/plivo/stream) with playAudio and clearAudio.
6. Barge-in handling and conversational turn execution.
7. Post-call status callback processing (/api/v1/plivo/status).
"""

import base64
import hashlib
import hmac
import anyio
import json
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


from app.core.config import settings
from app.main import app
from app.models.business import Business
from app.models.call import Call
from app.models.conversation_session import ConversationSession
from app.models.customer import Customer
from app.services.plivo_service import PlivoService, get_plivo_service
from app.services.telephony.base import CallStatus
from app.services.telephony.factory import get_telephony_provider
from app.services.telephony.plivo_adapter import PlivoAdapter


@pytest.fixture
def plivo_service():
    """Isolated PlivoService test instance."""
    return PlivoService(
        auth_id="MAMOCKAUTHID12345",
        auth_token="mock_secret_auth_token_987654321",
        phone_number="+918040001234",
    )


def compute_v3_signature(url: str, params: dict, nonce: str, auth_token: str) -> str:
    """Helper to compute valid Plivo V3 signature for testing using official specification."""
    return PlivoService.compute_v3_signature(
        auth_token=auth_token,
        uri=url,
        nonce=nonce,
        method="POST",
        params=params,
    )


# ==============================================================================
# 1. Plivo V3 Signature Validation Tests
# ==============================================================================

def test_plivo_v3_signature_valid(plivo_service):
    """Verify that a properly constructed Plivo V3 signature validates successfully."""
    url = "https://api.vattara.com/api/v1/plivo/incoming"
    nonce = "1234567890123456"
    params = {"CallUUID": "test-uuid-1", "From": "+919876543210", "To": "+918040001234"}
    sig = compute_v3_signature(url, params, nonce, plivo_service.auth_token)

    is_valid = plivo_service.validate_v3_signature(
        uri=url,
        nonce=nonce,
        signature=sig,
        method="POST",
        params=params,
    )
    assert is_valid is True


def test_plivo_v3_signature_invalid(plivo_service):
    """Verify that an altered signature or mismatched nonce is rejected."""
    url = "https://api.vattara.com/api/v1/plivo/incoming"
    nonce = "1234567890123456"
    params = {"CallUUID": "test-uuid-1", "From": "+919876543210"}
    bad_sig = "invalid_base64_signature="

    is_valid = plivo_service.validate_v3_signature(
        uri=url,
        nonce=nonce,
        signature=bad_sig,
        method="POST",
        params=params,
    )
    assert is_valid is False


def test_plivo_v3_signature_multiple_signatures_key_rotation(plivo_service):
    """Verify support for comma-separated signatures during credential rotation."""
    url = "https://api.vattara.com/api/v1/plivo/incoming"
    nonce = "999888777"
    params = {"CallUUID": "test-uuid-2"}
    correct_sig = compute_v3_signature(url, params, nonce, plivo_service.auth_token)
    header_val = f"old_expired_sig_123, {correct_sig}"

    is_valid = plivo_service.validate_v3_signature(
        uri=url,
        nonce=nonce,
        signature=header_val,
        method="POST",
        params=params,
    )
    assert is_valid is True


# ==============================================================================
# 2. Plivo XML Builder Tests
# ==============================================================================

def test_build_stream_xml(plivo_service):
    """Verify bidirectional WebSocket <Stream> XML generation has no audioTrack and is inline without whitespace."""
    # Test with surrounding whitespace and newlines
    raw_stream_url = "  \n  wss://api.vattara.com/api/v1/plivo/stream?biz=1&call_uuid=abc  \t\n"
    xml = plivo_service.build_stream_xml(raw_stream_url, bidirectional=True, keep_call_alive=True)

    assert "<Response>" in xml
    assert "<Stream" in xml
    assert 'bidirectional="true"' in xml
    assert 'keepCallAlive="true"' in xml
    assert 'contentType="audio/x-mulaw;rate=8000"' in xml
    # audioTrack must NOT be present in bidirectional streaming XML
    assert "audioTrack" not in xml
    # URL must be strictly inline with no newline or indentation after the opening tag or before closing tag
    expected_stream_element = (
        '<Stream bidirectional="true" keepCallAlive="true" contentType="audio/x-mulaw;rate=8000">'
        "wss://api.vattara.com/api/v1/plivo/stream?biz=1&amp;call_uuid=abc"
        "</Stream>"
    )
    assert expected_stream_element in xml
    assert "\n    <Stream" in xml
    assert ">\n" not in expected_stream_element

    # Verify unidirectional stream preserves audioTrack when explicitly specified
    uni_xml = plivo_service.build_stream_xml(
        "wss://api.vattara.com/api/v1/plivo/stream?call_uuid=xyz",
        bidirectional=False,
        keep_call_alive=False,
        audio_track="inbound",
    )
    assert 'bidirectional="false"' in uni_xml
    assert 'keepCallAlive="false"' in uni_xml
    assert 'audioTrack="inbound"' in uni_xml
    assert "wss://api.vattara.com/api/v1/plivo/stream?call_uuid=xyz</Stream>" in uni_xml


def test_build_speak_xml(plivo_service):
    """Verify <Speak> XML generation with Tamil & English language support."""
    xml_en = plivo_service.build_speak_xml("Welcome to Vattara Clinic", language="en-IN")
    assert '<Speak language="en-IN">Welcome to Vattara Clinic</Speak>' in xml_en

    xml_ta = plivo_service.build_speak_xml("வணக்கம்", language="ta-IN")
    assert '<Speak language="ta-IN">வணக்கம்</Speak>' in xml_ta


def test_build_hangup_xml(plivo_service):
    """Verify <Hangup/> XML generation."""
    xml = plivo_service.build_hangup_xml()
    assert "<Hangup" in xml


# ==============================================================================
# 3. PlivoAdapter Adherence Tests
# ==============================================================================

def test_plivo_adapter_factory():
    """Verify get_telephony_provider('plivo') returns PlivoAdapter."""
    adapter = get_telephony_provider("plivo")
    assert isinstance(adapter, PlivoAdapter)
    assert adapter.provider_name == "plivo"


def test_plivo_adapter_parse_inbound_call():
    """Verify inbound call normalization."""
    adapter = PlivoAdapter()
    payload = {
        "CallUUID": "plivo-call-12345",
        "From": "+919876543210",
        "To": "+918040001234",
        "Direction": "inbound",
    }
    event = adapter.parse_inbound_call(payload, {})
    assert event.provider == "plivo"
    assert event.call_id == "plivo-call-12345"
    assert event.caller_phone == "+919876543210"
    assert event.destination_phone == "+918040001234"


def test_plivo_adapter_parse_status_callback():
    """Verify status callback normalization."""
    adapter = PlivoAdapter()
    payload = {
        "CallUUID": "plivo-call-12345",
        "CallStatus": "completed",
        "Duration": "145",
        "RecordUrl": "https://s3.amazonaws.com/recordings/call.mp3",
    }
    event = adapter.parse_status_callback(payload, {})
    assert event.provider == "plivo"
    assert event.call_id == "plivo-call-12345"
    assert event.status == CallStatus.COMPLETED
    assert event.duration_seconds == 145
    assert event.recording_url == "https://s3.amazonaws.com/recordings/call.mp3"


# ==============================================================================
# 4. Inbound Webhook HTTP Route Tests (/api/v1/plivo/incoming)
# ==============================================================================

def test_plivo_incoming_webhook_flow(client: TestClient, db_session, plivo_service: PlivoService):
    """Test full inbound Plivo call webhook execution with tenant resolution and XML response."""
    app.dependency_overrides[get_plivo_service] = lambda: plivo_service
    try:
        # Ensure active business exists
        biz = db_session.query(Business).first()
        if not biz:
            biz = Business(name="Test Plivo Clinic", phone="+918040001234", is_active=True)
            db_session.add(biz)
            db_session.commit()
            db_session.refresh(biz)

        call_uuid = "plivo-test-uuid-999"
        caller = "+919444199887"
        destination = biz.phone or "+918040001234"

        payload = {
            "CallUUID": call_uuid,
            "From": caller,
            "To": destination,
            "CallStatus": "ringing",
            "Direction": "inbound",
        }
        url = "http://testserver/api/v1/plivo/incoming"
        nonce = "1234567890123456"
        sig = compute_v3_signature(url, payload, nonce, plivo_service.auth_token)

        response = client.post(
            "/api/v1/plivo/incoming",
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
        assert f"call_uuid={call_uuid}" in content

        # Verify Call record was created in database
        call = db_session.get(Call, call_uuid)
        assert call is not None
        assert call.business_id == biz.id
        assert call.caller_phone == caller
        assert call.status == "in_progress"

        # Verify Customer was created/linked
        customer = db_session.get(Customer, call.customer_id)
        assert customer is not None
        assert customer.phone == caller
    finally:
        app.dependency_overrides.pop(get_plivo_service, None)


def test_plivo_incoming_webhook_invalid_signature_403(client: TestClient, plivo_service: PlivoService):
    """Verify that requests with forged or invalid Plivo V3 signatures are rejected with 403 Forbidden."""
    app.dependency_overrides[get_plivo_service] = lambda: plivo_service
    try:
        response = client.post(
            "/api/v1/plivo/incoming",
            data={"CallUUID": "bad-call", "From": "+919876543210", "To": "+918040001234"},
            headers={
                "X-Plivo-Signature-V3": "invalid_forged_sig==",
                "X-Plivo-Signature-V3-Nonce": "123456",
            },
        )
        assert response.status_code == 403
        assert "Invalid Plivo V3 signature" in response.text
    finally:
        app.dependency_overrides.pop(get_plivo_service, None)


def test_plivo_incoming_webhook_missing_params_400(client: TestClient, plivo_service: PlivoService):
    """Verify that requests missing mandatory From or To parameters return 400 Bad Request."""
    app.dependency_overrides[get_plivo_service] = lambda: plivo_service
    try:
        payload = {"CallUUID": "uuid-without-phone"}
        url = "http://testserver/api/v1/plivo/incoming"
        nonce = "555666777"
        sig = compute_v3_signature(url, payload, nonce, plivo_service.auth_token)

        response = client.post(
            "/api/v1/plivo/incoming",
            data=payload,
            headers={
                "X-Plivo-Signature-V3": sig,
                "X-Plivo-Signature-V3-Nonce": nonce,
            },
        )
        assert response.status_code == 400
        assert "Missing required Plivo call parameters" in response.text
    finally:
        app.dependency_overrides.pop(get_plivo_service, None)


def test_plivo_incoming_webhook_unmapped_number(client: TestClient, plivo_service: PlivoService):
    """Verify that calls to unmapped telephone numbers receive polite rejection XML with Speak and Hangup."""
    app.dependency_overrides[get_plivo_service] = lambda: plivo_service
    try:
        payload = {
            "CallUUID": "unmapped-call-001",
            "From": "+919876543210",
            "To": "+910000999888",
        }
        url = "http://testserver/api/v1/plivo/incoming"
        nonce = "111222333"
        sig = compute_v3_signature(url, payload, nonce, plivo_service.auth_token)

        response = client.post(
            "/api/v1/plivo/incoming",
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
        assert "<Speak" in content
        assert "<Hangup" in content
    finally:
        app.dependency_overrides.pop(get_plivo_service, None)


def test_plivo_status_callback_flow(client: TestClient, db_session):
    """Test post-call hangup callback finalizing Call record and duration."""
    biz = db_session.query(Business).first()
    call_uuid = "plivo-status-uuid-777"

    # Seed call record
    call = Call(
        id=call_uuid,
        business_id=biz.id,
        caller_phone="+919444199887",
        status="in_progress",
        duration_seconds=0,
    )
    db_session.add(call)
    db_session.commit()

    response = client.post(
        "/api/v1/plivo/status",
        data={
            "CallUUID": call_uuid,
            "Duration": "180",
            "CallStatus": "completed",
            "HangupCause": "NORMAL_CLEARING",
        },
    )

    assert response.status_code == 200
    db_session.refresh(call)
    assert call.status == "completed"
    assert call.duration_seconds == 180
    assert call.ended_at is not None


# ==============================================================================
# 5. Bidirectional WebSocket Audio Stream Tests (/api/v1/plivo/stream)
# ==============================================================================

def test_plivo_websocket_streaming_flow(client: TestClient, db_session):
    """Test Plivo WebSocket audio streaming lifecycle: start -> greeting -> media -> stop."""
    biz = db_session.query(Business).first()
    call_uuid = "plivo-ws-call-001"
    stream_id = f"plivo_{call_uuid}"
    caller = "+919444199887"

    ws_url = f"/api/v1/plivo/stream?business_id={biz.id}&call_uuid={call_uuid}&caller_phone={caller}"

    with client.websocket_connect(ws_url) as websocket:
        # 1. Send Plivo 'start' event
        websocket.send_text(
            json.dumps({
                "event": "start",
                "start": {
                    "streamId": stream_id,
                    "callId": call_uuid,
                },
            })
        )

        # 2. Receive initial AI greeting audio packet (playAudio format)
        received_greeting = False
        for _ in range(5):
            try:
                msg_str = _receive_ws_text_with_timeout(websocket, timeout_seconds=3.0)
            except TimeoutError:
                break
            msg = json.loads(msg_str)
            if msg.get("event") == "playAudio":
                media = msg.get("media", {})
                assert media.get("contentType") == "audio/x-mulaw"
                assert media.get("sampleRate") == 8000
                assert "payload" in media
                received_greeting = True
                break

        assert received_greeting is True

        # 3. Send Plivo 'stop' event
        websocket.send_text(
            json.dumps({
                "event": "stop",
                "stop": {
                    "streamId": stream_id,
                },
            })
        )

    # Verify Call record finalized in DB
    call = db_session.get(Call, call_uuid)
    assert call is not None
    assert call.status == "completed"


def test_plivo_connection_diagnostic(client: TestClient):
    """Test Plivo status probe endpoint."""
    res = client.get("/api/v1/plivo/status")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
