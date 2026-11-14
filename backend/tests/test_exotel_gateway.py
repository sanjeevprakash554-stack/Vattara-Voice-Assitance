"""Automated test suite for dedicated Exotel Appointment API Gateway.

Gateway Endpoint: POST /api/v1/integrations/exotel/appointments
Authentication: Body-based integration_key with constant-time comparison
Tenant Binding: Server-enforced settings.EXOTEL_BUSINESS_ID
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.models.assistant import Service
from app.models.business import Business
from app.models.customer import Customer
from app.models.appointment import Appointment
from app.models.user import User


TEST_GATEWAY_KEY = "vattara_test_gateway_key_9876543210abcdef"


@pytest.fixture
def gateway_test_env(db_session: Session) -> dict[str, Business | User | Service]:
    """Create test businesses, user, and service for the Exotel gateway test suite."""
    biz1 = Business(
        id="biz-gateway-apollo-1",
        name="Apollo Heart Centre",
        vertical="clinic",
        email="apollo@gatewaytest.com",
        phone="+914428281111",
        is_active=True,
    )
    biz2 = Business(
        id="biz-gateway-dental-2",
        name="Dental Care Hub",
        vertical="clinic",
        email="dental@gatewaytest.com",
        phone="+914428282222",
        is_active=True,
    )
    db_session.add_all([biz1, biz2])
    db_session.flush()

    user1 = User(
        id="user-gateway-admin-1",
        business_id=biz1.id,
        email="admin@apolloheart.com",
        full_name="Dr. Gateway Admin",
        hashed_password="dummy_password_hash",
        role="admin",
        is_active=True,
    )
    db_session.add(user1)

    service1 = Service(
        id="service-gateway-cardio",
        business_id=biz1.id,
        name="General Consultation",
        price=500.0,
        duration_minutes=30,
        is_active=True,
    )
    db_session.add(service1)
    db_session.commit()

    return {
        "biz1": biz1,
        "biz2": biz2,
        "user1": user1,
        "service1": service1,
    }


# ==============================================================================
# 1. VALID INTEGRATION KEY & SUCCESSFUL BOOKING
# ==============================================================================

def test_exotel_gateway_valid_key_success(
    client: TestClient,
    gateway_test_env: dict[str, Business | User | Service],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify POST /api/v1/integrations/exotel/appointments succeeds with valid integration_key."""
    biz1 = gateway_test_env["biz1"]
    monkeypatch.setattr(settings, "EXOTEL_INTEGRATION_KEY", TEST_GATEWAY_KEY)
    monkeypatch.setattr(settings, "EXOTEL_BUSINESS_ID", biz1.id)

    payload = {
        "integration_key": TEST_GATEWAY_KEY,
        "customer_name": "Arun Kumar",
        "customer_phone": "+919876543210",
        "service_id": None,
        "appointment_time": "2026-11-08T10:00:00+05:30",
        "end_time": "2026-11-08T10:30:00+05:30",
        "notes": "Booked through Exotel voice assistant",
        "source": "ai_call",
        "customer_id": "new",
    }

    response = client.post(f"{settings.API_V1_STR}/integrations/exotel/appointments", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["source"] == "ai_call"
    assert data["status"] == "upcoming"
    assert data["business_id"] == biz1.id
    assert data["customer_id"] is not None
    assert data["notes"] == "Booked through Exotel voice assistant"


# ==============================================================================
# 2. INVALID INTEGRATION KEY (401 UNAUTHORIZED)
# ==============================================================================

def test_exotel_gateway_invalid_key_rejected(
    client: TestClient,
    gateway_test_env: dict[str, Business | User | Service],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify request with invalid integration_key is rejected with HTTP 401."""
    biz1 = gateway_test_env["biz1"]
    monkeypatch.setattr(settings, "EXOTEL_INTEGRATION_KEY", TEST_GATEWAY_KEY)
    monkeypatch.setattr(settings, "EXOTEL_BUSINESS_ID", biz1.id)

    payload = {
        "integration_key": "wrong_invalid_key_value",
        "customer_name": "Arun Kumar",
        "customer_phone": "+919876543210",
        "appointment_time": "2026-11-08T10:00:00+05:30",
    }

    response = client.post(f"{settings.API_V1_STR}/integrations/exotel/appointments", json=payload)
    assert response.status_code == 401
    assert "Invalid integration key" in response.json()["detail"]


# ==============================================================================
# 3. MISSING INTEGRATION KEY (401 UNAUTHORIZED)
# ==============================================================================

def test_exotel_gateway_missing_key_rejected(
    client: TestClient,
    gateway_test_env: dict[str, Business | User | Service],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify request with omitted or null integration_key is rejected with HTTP 401."""
    biz1 = gateway_test_env["biz1"]
    monkeypatch.setattr(settings, "EXOTEL_INTEGRATION_KEY", TEST_GATEWAY_KEY)
    monkeypatch.setattr(settings, "EXOTEL_BUSINESS_ID", biz1.id)

    # Payload with integration_key=None
    payload1 = {
        "integration_key": None,
        "customer_name": "Arun Kumar",
        "customer_phone": "+919876543210",
        "appointment_time": "2026-11-08T10:00:00+05:30",
    }
    response1 = client.post(f"{settings.API_V1_STR}/integrations/exotel/appointments", json=payload1)
    assert response1.status_code == 401
    assert "Missing integration key" in response1.json()["detail"]

    # Payload omitting integration_key field entirely
    payload2 = {
        "customer_name": "Arun Kumar",
        "customer_phone": "+919876543210",
        "appointment_time": "2026-11-08T10:00:00+05:30",
    }
    response2 = client.post(f"{settings.API_V1_STR}/integrations/exotel/appointments", json=payload2)
    assert response2.status_code == 401
    assert "Missing integration key" in response2.json()["detail"]


# ==============================================================================
# 4. SERVER CONFIGURATION INCOMPLETE (503 SERVICE UNAVAILABLE)
# ==============================================================================

def test_exotel_gateway_unconfigured_server_503(
    client: TestClient,
    gateway_test_env: dict[str, Business | User | Service],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify HTTP 503 is returned when EXOTEL_INTEGRATION_KEY or EXOTEL_BUSINESS_ID is unset."""
    # When EXOTEL_INTEGRATION_KEY is None
    monkeypatch.setattr(settings, "EXOTEL_INTEGRATION_KEY", None)
    monkeypatch.setattr(settings, "EXOTEL_BUSINESS_ID", "biz-gateway-apollo-1")

    payload = {
        "integration_key": TEST_GATEWAY_KEY,
        "customer_name": "Arun Kumar",
        "customer_phone": "+919876543210",
        "appointment_time": "2026-11-08T10:00:00+05:30",
    }
    response = client.post(f"{settings.API_V1_STR}/integrations/exotel/appointments", json=payload)
    assert response.status_code == 503
    assert "incomplete on server" in response.json()["detail"]

    # When EXOTEL_BUSINESS_ID points to a non-existent business
    monkeypatch.setattr(settings, "EXOTEL_INTEGRATION_KEY", TEST_GATEWAY_KEY)
    monkeypatch.setattr(settings, "EXOTEL_BUSINESS_ID", "non-existent-biz-id")
    response2 = client.post(f"{settings.API_V1_STR}/integrations/exotel/appointments", json=payload)
    assert response2.status_code == 503
    assert "inactive or not found" in response2.json()["detail"]


# ==============================================================================
# 5. MISSING APPOINTMENT TIME (422 UNPROCESSABLE ENTITY)
# ==============================================================================

def test_exotel_gateway_missing_appointment_time_422(
    client: TestClient,
    gateway_test_env: dict[str, Business | User | Service],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify missing appointment_time returns HTTP 422 Unprocessable Entity."""
    biz1 = gateway_test_env["biz1"]
    monkeypatch.setattr(settings, "EXOTEL_INTEGRATION_KEY", TEST_GATEWAY_KEY)
    monkeypatch.setattr(settings, "EXOTEL_BUSINESS_ID", biz1.id)

    payload = {
        "integration_key": TEST_GATEWAY_KEY,
        "customer_name": "Arun Kumar",
        "customer_phone": "+919876543210",
        # Missing appointment_time
    }
    response = client.post(f"{settings.API_V1_STR}/integrations/exotel/appointments", json=payload)
    assert response.status_code == 422


# ==============================================================================
# 6. CUSTOMER AUTO-CREATION & REUSE
# ==============================================================================

def test_exotel_gateway_customer_auto_creation_and_reuse(
    client: TestClient,
    gateway_test_env: dict[str, Business | User | Service],
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify first booking creates customer; second booking reuses same customer and increments count."""
    biz1 = gateway_test_env["biz1"]
    monkeypatch.setattr(settings, "EXOTEL_INTEGRATION_KEY", TEST_GATEWAY_KEY)
    monkeypatch.setattr(settings, "EXOTEL_BUSINESS_ID", biz1.id)

    phone = "+919988776655"

    # Call 1: First booking
    p1 = {
        "integration_key": TEST_GATEWAY_KEY,
        "customer_name": "Priya Sharma",
        "customer_phone": phone,
        "appointment_time": "2026-11-08T11:00:00+05:30",
        "customer_id": "new",
    }
    res1 = client.post(f"{settings.API_V1_STR}/integrations/exotel/appointments", json=p1)
    assert res1.status_code == 201
    appt1 = res1.json()
    cust_id_1 = appt1["customer_id"]

    # Verify customer in DB
    cust1 = db_session.scalar(
        select(Customer).where(Customer.phone == phone, Customer.business_id == biz1.id)
    )
    assert cust1 is not None
    assert cust1.id == cust_id_1
    assert cust1.name == "Priya Sharma"
    assert cust1.total_appointments == 1

    # Call 2: Repeat booking with customer_id=None
    p2 = {
        "integration_key": TEST_GATEWAY_KEY,
        "customer_name": "Priya Sharma",
        "customer_phone": phone,
        "appointment_time": "2026-11-09T11:00:00+05:30",
        "customer_id": None,
    }
    res2 = client.post(f"{settings.API_V1_STR}/integrations/exotel/appointments", json=p2)
    assert res2.status_code == 201
    appt2 = res2.json()
    cust_id_2 = appt2["customer_id"]

    # Must reuse the same customer ID
    assert cust_id_1 == cust_id_2

    # Verify total_appointments incremented
    db_session.refresh(cust1)
    assert cust1.total_appointments == 2


# ==============================================================================
# 7. NULL AND VALID SERVICE ID
# ==============================================================================

def test_exotel_gateway_service_id_and_customer_id_hardening(
    client: TestClient,
    gateway_test_env: dict[str, Business | User | Service],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify customer_id and service_id are always neutralized to None so voice agent cannot target arbitrary IDs."""
    biz1 = gateway_test_env["biz1"]
    service1 = gateway_test_env["service1"]
    monkeypatch.setattr(settings, "EXOTEL_INTEGRATION_KEY", TEST_GATEWAY_KEY)
    monkeypatch.setattr(settings, "EXOTEL_BUSINESS_ID", biz1.id)

    # 1. Null service_id and customer_id works cleanly
    p_null = {
        "integration_key": TEST_GATEWAY_KEY,
        "customer_name": "Test Null Service",
        "customer_phone": "+919811122233",
        "customer_id": None,
        "service_id": None,
        "appointment_time": "2026-11-08T12:00:00+05:30",
    }
    res_null = client.post(f"{settings.API_V1_STR}/integrations/exotel/appointments", json=p_null)
    assert res_null.status_code == 201
    assert res_null.json()["service_id"] is None
    assert res_null.json()["customer_id"] is not None

    # 2. Supplied service_id is neutralized to None
    p_valid_service = {
        "integration_key": TEST_GATEWAY_KEY,
        "customer_name": "Test Supplied Service",
        "customer_phone": "+919811122244",
        "service_id": service1.id,
        "appointment_time": "2026-11-08T13:00:00+05:30",
    }
    res_service = client.post(f"{settings.API_V1_STR}/integrations/exotel/appointments", json=p_valid_service)
    assert res_service.status_code == 201
    data_service = res_service.json()
    assert data_service["service_id"] is None

    # 3. Arbitrary/unrecognized service_id and arbitrary customer_id are neutralized without error
    p_arbitrary = {
        "integration_key": TEST_GATEWAY_KEY,
        "customer_name": "Targeting Guard",
        "customer_phone": "+919811122255",
        "customer_id": "forged_arbitrary_customer_id_999",
        "service_id": "non_existent_service_id_123",
        "appointment_time": "2026-11-08T14:00:00+05:30",
    }
    res_arbitrary = client.post(f"{settings.API_V1_STR}/integrations/exotel/appointments", json=p_arbitrary)
    assert res_arbitrary.status_code == 201
    data_arbitrary = res_arbitrary.json()
    assert data_arbitrary["customer_id"] != "forged_arbitrary_customer_id_999"
    assert data_arbitrary["service_id"] is None


# ==============================================================================
# 8. MULTI-SOURCE INTEGRATION KEY AUTHENTICATION & PRECEDENCE
# ==============================================================================

def test_exotel_gateway_key_via_query_param(
    client: TestClient,
    gateway_test_env: dict[str, Business | User | Service],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify integration key passed via 'key' query parameter is accepted."""
    biz1 = gateway_test_env["biz1"]
    monkeypatch.setattr(settings, "EXOTEL_INTEGRATION_KEY", TEST_GATEWAY_KEY)
    monkeypatch.setattr(settings, "EXOTEL_BUSINESS_ID", biz1.id)

    payload = {
        "customer_name": "Query Param User",
        "customer_phone": "+919111222333",
        "appointment_time": "2026-11-08T10:00:00+05:30",
    }
    url = f"{settings.API_V1_STR}/integrations/exotel/appointments?key={TEST_GATEWAY_KEY}"
    response = client.post(url, json=payload)
    assert response.status_code == 201
    assert response.json()["business_id"] == biz1.id


def test_exotel_gateway_key_via_header(
    client: TestClient,
    gateway_test_env: dict[str, Business | User | Service],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify integration key passed via 'X-Integration-Key' header is accepted."""
    biz1 = gateway_test_env["biz1"]
    monkeypatch.setattr(settings, "EXOTEL_INTEGRATION_KEY", TEST_GATEWAY_KEY)
    monkeypatch.setattr(settings, "EXOTEL_BUSINESS_ID", biz1.id)

    payload = {
        "customer_name": "Header User",
        "customer_phone": "+919222333444",
        "appointment_time": "2026-11-08T10:00:00+05:30",
    }
    headers = {"X-Integration-Key": TEST_GATEWAY_KEY}
    response = client.post(f"{settings.API_V1_STR}/integrations/exotel/appointments", json=payload, headers=headers)
    assert response.status_code == 201
    assert response.json()["business_id"] == biz1.id


def test_exotel_gateway_key_precedence(
    client: TestClient,
    gateway_test_env: dict[str, Business | User | Service],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify precedence order: query param > header > JSON body."""
    biz1 = gateway_test_env["biz1"]
    monkeypatch.setattr(settings, "EXOTEL_INTEGRATION_KEY", TEST_GATEWAY_KEY)
    monkeypatch.setattr(settings, "EXOTEL_BUSINESS_ID", biz1.id)

    payload_base = {
        "customer_name": "Precedence User",
        "customer_phone": "+919333444555",
        "appointment_time": "2026-11-08T10:00:00+05:30",
    }

    # 1. Valid query param overrides invalid header and invalid body
    p1 = {**payload_base, "integration_key": "wrong_body_key"}
    h1 = {"X-Integration-Key": "wrong_header_key"}
    r1 = client.post(
        f"{settings.API_V1_STR}/integrations/exotel/appointments?key={TEST_GATEWAY_KEY}",
        json=p1,
        headers=h1,
    )
    assert r1.status_code == 201

    # 2. Invalid query param fails even if header and body are valid (query takes precedence)
    p2 = {**payload_base, "integration_key": TEST_GATEWAY_KEY}
    h2 = {"X-Integration-Key": TEST_GATEWAY_KEY}
    r2 = client.post(
        f"{settings.API_V1_STR}/integrations/exotel/appointments?key=invalid_query_key",
        json=p2,
        headers=h2,
    )
    assert r2.status_code == 401

    # 3. Valid header overrides invalid body (when no query param is present)
    p3 = {**payload_base, "integration_key": "wrong_body_key"}
    h3 = {"X-Integration-Key": TEST_GATEWAY_KEY}
    r3 = client.post(
        f"{settings.API_V1_STR}/integrations/exotel/appointments",
        json=p3,
        headers=h3,
    )
    assert r3.status_code == 201

    # 4. Invalid header fails even if body is valid (header takes precedence over body)
    p4 = {**payload_base, "integration_key": TEST_GATEWAY_KEY}
    h4 = {"X-Integration-Key": "wrong_header_key"}
    r4 = client.post(
        f"{settings.API_V1_STR}/integrations/exotel/appointments",
        json=p4,
        headers=h4,
    )
    assert r4.status_code == 401


# ==============================================================================
# 8. MULTI-TENANT ISOLATION
# ==============================================================================

def test_exotel_gateway_tenant_isolation(
    client: TestClient,
    gateway_test_env: dict[str, Business | User | Service],
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify appointments are strictly bound to server-configured EXOTEL_BUSINESS_ID."""
    biz1 = gateway_test_env["biz1"]
    biz2 = gateway_test_env["biz2"]
    monkeypatch.setattr(settings, "EXOTEL_INTEGRATION_KEY", TEST_GATEWAY_KEY)
    monkeypatch.setattr(settings, "EXOTEL_BUSINESS_ID", biz1.id)

    payload = {
        "integration_key": TEST_GATEWAY_KEY,
        "customer_name": "Tenant Guard User",
        "customer_phone": "+919777666555",
        "appointment_time": "2026-11-08T15:00:00+05:30",
    }
    response = client.post(f"{settings.API_V1_STR}/integrations/exotel/appointments", json=payload)
    assert response.status_code == 201
    appt_data = response.json()
    assert appt_data["business_id"] == biz1.id
    assert appt_data["business_id"] != biz2.id

    # Verify database record
    appt_db = db_session.get(Appointment, appt_data["id"])
    assert appt_db is not None
    assert appt_db.business_id == biz1.id


# ==============================================================================
# 9. EXISTING JWT AUTHENTICATION REMAINS FULLY FUNCTIONAL
# ==============================================================================

def test_existing_jwt_auth_unaffected(
    client: TestClient,
    gateway_test_env: dict[str, Business | User | Service],
) -> None:
    """Verify dashboard JWT authentication continues to work on /api/v1/appointments."""
    user1 = gateway_test_env["user1"]
    jwt_token = create_access_token(subject=user1.id, extra_claims={"business_id": user1.business_id})

    headers = {"Authorization": f"Bearer {jwt_token}"}
    response = client.get(f"{settings.API_V1_STR}/appointments", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
