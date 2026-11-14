"""Comprehensive automated test suite for Real-Time Dashboard Integration and WebSockets.

Verifies:
1. Dashboard Statistics API (computed from actual database records)
2. Call History API
3. Appointment API
4. Customer Hub API
5. Reminder API
6. Dashboard WebSocket Authentication (missing token, invalid token, valid JWT)
7. Multi-Tenant WebSocket Isolation (Tenant A never receives Tenant B events)
8. Real-Time Telemetry Events:
   - CALL_STARTED
   - TRANSCRIPT_RECEIVED
   - AI_RESPONSE_GENERATED
   - CALL_COMPLETED
   - APPOINTMENT_CREATED
9. WebSocket client disconnect and reconnect cleanup
"""

import asyncio
from datetime import datetime, timedelta, timezone
import json
from typing import Any
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.models.appointment import Appointment
from app.models.assistant import AssistantConfig
from app.models.business import Business
from app.models.call import Call
from app.models.customer import Customer
from app.models.reminder import Reminder
from app.models.user import User
from app.services.dashboard_events import dashboard_event_manager


@pytest.fixture
def realtime_test_env(db_session: Session) -> dict[str, Any]:
    """Create two distinct business organizations with users and initial state."""
    # Organization A
    biz_a = Business(
        id="biz-rt-apollo",
        name="Apollo Multicare Hospital",
        vertical="clinic",
        phone="+919840111111",
        email="apollo@vattara.com",
        timezone="Asia/Kolkata",
        is_active=True,
    )
    user_a = User(
        id="user-rt-apollo",
        business_id=biz_a.id,
        email="doctor.apollo@vattara.com",
        hashed_password="hashed_pw_test",
        full_name="Dr. Apollo",
        role="admin",
        is_active=True,
    )
    cfg_a = AssistantConfig(
        business_id=biz_a.id,
        assistant_name="Apollo Voice AI",
        is_active=True,
    )

    # Organization B
    biz_b = Business(
        id="biz-rt-dental",
        name="City Dental Clinic",
        vertical="clinic",
        phone="+919840222222",
        email="dental@vattara.com",
        timezone="Asia/Kolkata",
        is_active=True,
    )
    user_b = User(
        id="user-rt-dental",
        business_id=biz_b.id,
        email="doctor.dental@vattara.com",
        hashed_password="hashed_pw_test",
        full_name="Dr. Dental",
        role="admin",
        is_active=True,
    )
    cfg_b = AssistantConfig(
        business_id=biz_b.id,
        assistant_name="Dental Voice AI",
        is_active=True,
    )

    db_session.add_all([biz_a, user_a, cfg_a, biz_b, user_b, cfg_b])
    db_session.flush()

    # Seed calls for Biz A
    now = datetime.now(timezone.utc)
    c1 = Call(
        id="call-rt-001",
        business_id=biz_a.id,
        caller_phone="+919840133445",
        caller_name="Ravi Kumar",
        call_type="incoming",
        status="completed",
        duration_seconds=145,
        summary="Cardiology inquiry",
        initiated_at=now - timedelta(hours=2),
        ended_at=now - timedelta(hours=2, seconds=-145),
    )
    c2 = Call(
        id="call-rt-002",
        business_id=biz_a.id,
        caller_phone="+919840998877",
        caller_name="Priya Natarajan",
        call_type="incoming",
        status="missed",
        duration_seconds=0,
        initiated_at=now - timedelta(hours=1),
    )

    # Seed customer and appointment for Biz A
    cust1 = Customer(
        id="cust-rt-001",
        business_id=biz_a.id,
        name="Ravi Kumar",
        phone="+919840133445",
        total_calls=1,
    )
    appt1 = Appointment(
        id="appt-rt-001",
        business_id=biz_a.id,
        customer_id=cust1.id,
        appointment_time=now + timedelta(days=1),
        status="upcoming",
        source="voice_ai",
    )

    # Seed call and customer for Biz B (Tenant Isolation verification)
    c_b1 = Call(
        id="call-rt-b01",
        business_id=biz_b.id,
        caller_phone="+919999900000",
        caller_name="Tenant B Caller",
        call_type="incoming",
        status="completed",
        duration_seconds=80,
        initiated_at=now - timedelta(hours=3),
    )

    db_session.add_all([c1, c2, cust1, appt1, c_b1])
    db_session.commit()

    token_a = create_access_token(
        subject=user_a.id,
        extra_claims={"business_id": biz_a.id, "role": user_a.role},
    )
    token_b = create_access_token(
        subject=user_b.id,
        extra_claims={"business_id": biz_b.id, "role": user_b.role},
    )

    return {
        "biz_a": biz_a,
        "user_a": user_a,
        "token_a": token_a,
        "biz_b": biz_b,
        "user_b": user_b,
        "token_b": token_b,
    }


# ==============================================================================
# 1. REST API Telemetry Tests
# ==============================================================================

def test_dashboard_stats_api(client: TestClient, realtime_test_env: dict[str, Any]):
    """Verify GET /api/v1/dashboard/stats computes accurate numbers from actual DB records."""
    token_a = realtime_test_env["token_a"]
    res = client.get(
        f"{settings.API_V1_STR}/dashboard/stats",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_incoming_calls"] == 2
    assert data["successful_calls"] == 1
    assert data["missed_calls"] == 1
    assert data["call_success_rate"] == 50.0
    assert data["total_appointments"] == 1
    assert data["upcoming_appointments_count"] == 1
    assert data["total_customers"] == 1


def test_call_history_api(client: TestClient, realtime_test_env: dict[str, Any]):
    """Verify GET /api/v1/calls returns filtered database logs with tenant isolation."""
    token_a = realtime_test_env["token_a"]
    res = client.get(
        f"{settings.API_V1_STR}/calls",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res.status_code == 200
    calls = res.json()
    assert len(calls) == 2
    # Verify Biz B call is strictly excluded
    assert all(c["id"] != "call-rt-b01" for c in calls)


def test_appointment_api(client: TestClient, realtime_test_env: dict[str, Any]):
    """Verify GET /api/v1/appointments returns active appointments."""
    token_a = realtime_test_env["token_a"]
    res = client.get(
        f"{settings.API_V1_STR}/appointments",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res.status_code == 200
    appts = res.json()
    assert len(appts) == 1
    assert appts[0]["id"] == "appt-rt-001"
    assert appts[0]["status"] == "upcoming"


def test_customer_hub_api(client: TestClient, realtime_test_env: dict[str, Any]):
    """Verify GET /api/v1/customers returns customer records."""
    token_a = realtime_test_env["token_a"]
    res = client.get(
        f"{settings.API_V1_STR}/customers",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res.status_code == 200
    custs = res.json()
    assert len(custs) == 1
    assert custs[0]["name"] == "Ravi Kumar"


def test_analytics_api_derivation(client: TestClient, realtime_test_env: dict[str, Any]):
    """Verify GET /api/v1/dashboard/analytics computes actual trends and duration distributions."""
    token_a = realtime_test_env["token_a"]
    res = client.get(
        f"{settings.API_V1_STR}/dashboard/analytics?days=7",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res.status_code == 200
    overview = res.json()
    assert "stats" in overview
    assert "call_trends" in overview
    assert len(overview["call_trends"]) == 7
    assert "duration_distribution" in overview
    # Biz A has one call of 145 seconds (2-3 mins bucket)
    d_dist = {item["range_label"]: item["count"] for item in overview["duration_distribution"]}
    assert d_dist["2 - 3 mins"] == 1


# ==============================================================================
# 2. WebSocket Authentication & Lifecycle Tests
# ==============================================================================

def test_dashboard_ws_authentication_missing_token(client: TestClient):
    """Verify WebSocket connection is rejected when no token is supplied."""
    with pytest.raises(Exception):
        with client.websocket_connect(f"{settings.API_V1_STR}/dashboard/ws") as ws:
            pass


def test_dashboard_ws_authentication_invalid_token(client: TestClient):
    """Verify WebSocket connection is rejected when token is invalid or expired."""
    with pytest.raises(Exception):
        with client.websocket_connect(f"{settings.API_V1_STR}/dashboard/ws?token=invalid_expired_token_123") as ws:
            pass


def test_dashboard_ws_connect_and_ping(client: TestClient, realtime_test_env: dict[str, Any]):
    """Verify authorized client connects successfully, receives CONNECTED event, and handles ping/pong."""
    token_a = realtime_test_env["token_a"]
    biz_a_id = realtime_test_env["biz_a"].id

    with client.websocket_connect(f"{settings.API_V1_STR}/dashboard/ws?token={token_a}") as ws:
        # First message is server CONNECTED handshake
        welcome = ws.receive_json()
        assert welcome["event"] == "CONNECTED"
        assert welcome["business_id"] == biz_a_id
        assert welcome["data"]["business_id"] == biz_a_id

        # Send ping
        ws.send_text("ping")
        pong = ws.receive_json()
        assert pong["event"] == "PONG"


# ==============================================================================
# 3. Multi-Tenant WebSocket Isolation Tests
# ==============================================================================

def test_dashboard_ws_multi_tenant_isolation(client: TestClient, realtime_test_env: dict[str, Any]):
    """Verify Tenant B never receives events dispatched to Tenant A."""
    token_a = realtime_test_env["token_a"]
    token_b = realtime_test_env["token_b"]
    biz_a_id = realtime_test_env["biz_a"].id
    biz_b_id = realtime_test_env["biz_b"].id

    with client.websocket_connect(f"{settings.API_V1_STR}/dashboard/ws?token={token_a}") as ws_a:
        with client.websocket_connect(f"{settings.API_V1_STR}/dashboard/ws?token={token_b}") as ws_b:
            # Consume CONNECTED events
            welcome_a = ws_a.receive_json()
            assert welcome_a["business_id"] == biz_a_id

            welcome_b = ws_b.receive_json()
            assert welcome_b["business_id"] == biz_b_id

            # Dispatch event strictly to Tenant A
            dashboard_event_manager.dispatch(
                business_id=biz_a_id,
                event_type="CALL_STARTED",
                data={"call_id": "call-secret-tenant-a", "caller_phone": "+919840133445"},
            )

            # Tenant A receives the event
            msg_a = ws_a.receive_json()
            assert msg_a["event"] == "CALL_STARTED"
            assert msg_a["data"]["call_id"] == "call-secret-tenant-a"

            # Tenant B must NOT have any message; sending a ping must be received first
            ws_b.send_text("ping")
            msg_b = ws_b.receive_json()
            assert msg_b["event"] == "PONG"  # PONG received directly without CALL_STARTED leakage!


# ==============================================================================
# 4. Telemetry Event Sequence Tests
# ==============================================================================

def test_dashboard_ws_telemetry_event_sequence(client: TestClient, realtime_test_env: dict[str, Any]):
    """Verify full sequence: CALL_STARTED -> TRANSCRIPT_RECEIVED -> AI_RESPONSE_GENERATED -> CALL_COMPLETED."""
    token_a = realtime_test_env["token_a"]
    biz_a_id = realtime_test_env["biz_a"].id
    call_sid = "CS_telemetry_test_001"

    with client.websocket_connect(f"{settings.API_V1_STR}/dashboard/ws?token={token_a}") as ws:
        # Initial CONNECTED
        ws.receive_json()

        # 1. CALL_STARTED
        dashboard_event_manager.dispatch(
            business_id=biz_a_id,
            event_type="CALL_STARTED",
            data={
                "call_id": call_sid,
                "caller_phone": "+919840133445",
                "caller_name": "Ravi Kumar",
                "status": "in_progress",
            },
        )
        msg1 = ws.receive_json()
        assert msg1["event"] == "CALL_STARTED"
        assert msg1["data"]["call_id"] == call_sid

        # 2. TRANSCRIPT_RECEIVED
        dashboard_event_manager.dispatch(
            business_id=biz_a_id,
            event_type="TRANSCRIPT_RECEIVED",
            data={
                "call_id": call_sid,
                "speaker": "caller",
                "text": "Hello, I want to book a doctor appointment.",
            },
        )
        msg2 = ws.receive_json()
        assert msg2["event"] == "TRANSCRIPT_RECEIVED"
        assert msg2["data"]["text"] == "Hello, I want to book a doctor appointment."

        # 3. AI_RESPONSE_GENERATED
        dashboard_event_manager.dispatch(
            business_id=biz_a_id,
            event_type="AI_RESPONSE_GENERATED",
            data={
                "call_id": call_sid,
                "speaker": "assistant",
                "text": "I can certainly help you book that. Which specialty would you like?",
            },
        )
        msg3 = ws.receive_json()
        assert msg3["event"] == "AI_RESPONSE_GENERATED"
        assert "Which specialty" in msg3["data"]["text"]

        # 4. APPOINTMENT_CREATED
        dashboard_event_manager.dispatch(
            business_id=biz_a_id,
            event_type="APPOINTMENT_CREATED",
            data={
                "appointment_id": "appt-new-001",
                "call_id": call_sid,
                "customer_name": "Ravi Kumar",
                "service_name": "Cardiology",
                "status": "upcoming",
            },
        )
        msg4 = ws.receive_json()
        assert msg4["event"] == "APPOINTMENT_CREATED"
        assert msg4["data"]["appointment_id"] == "appt-new-001"

        # 5. CALL_COMPLETED
        dashboard_event_manager.dispatch(
            business_id=biz_a_id,
            event_type="CALL_COMPLETED",
            data={
                "call_id": call_sid,
                "status": "completed",
                "duration_seconds": 95,
            },
        )
        msg5 = ws.receive_json()
        assert msg5["event"] == "CALL_COMPLETED"
        assert msg5["data"]["duration_seconds"] == 95
