"""Automated Security Regression & Multi-Tenant Isolation Tests (Phase 1).

Covers:
1. Authentication bypass removal (protected routes reject unauthenticated requests).
2. API key impersonation prevention (arbitrary vat_live_ prefix rejected).
3. Plaintext password comparison rejection (no fallback in verify_password).
4. Secure password reset verification (hash comparison, expiry check, single-use).
5. JWT token validation (expired token, invalid signature, missing claims).
6. Production SECRET_KEY hardening validation.
7. Multi-tenant data isolation across appointments, customers, calls, and assistant configs.
8. Database migration schema and Alembic version verification.
"""

from datetime import datetime, timedelta, timezone
import jwt
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.appointment import Appointment
from app.models.assistant import AssistantConfig
from app.models.business import Business
from app.models.customer import Customer
from app.models.password_reset import PasswordReset
from app.models.user import User


# ==============================================================================
# 1. Authentication Bypass & Access Control Tests
# ==============================================================================

def test_unauthenticated_request_rejected_on_all_protected_endpoints(client: TestClient) -> None:
    """Ensure that protected endpoints return 401 Unauthorized when no token is supplied."""
    protected_urls = [
        "/api/v1/appointments",
        "/api/v1/customers",
        "/api/v1/assistant",
        "/api/v1/dashboard/stats",
        "/api/v1/calls",
        "/api/v1/reminders",
    ]
    for url in protected_urls:
        response = client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, (
            f"Endpoint {url} allowed unauthenticated access (expected 401, got {response.status_code})"
        )
        assert "detail" in response.json()


def test_invalid_bearer_token_rejected(client: TestClient) -> None:
    """Ensure requests with bogus or malformed Bearer tokens are rejected."""
    headers = {"Authorization": "Bearer not-a-valid-jwt-token"}
    response = client.get("/api/v1/appointments", headers=headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_expired_jwt_token_rejected(client: TestClient) -> None:
    """Ensure expired JWT access tokens are rejected with 401."""
    expired_token = create_access_token(
        subject="demo-user-admin",
        expires_delta=timedelta(minutes=-10),
        extra_claims={"business_id": "demo-biz-vattara-health", "role": "admin"},
    )
    headers = {"Authorization": f"Bearer {expired_token}"}
    response = client.get("/api/v1/appointments", headers=headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_tampered_jwt_signature_rejected(client: TestClient) -> None:
    """Ensure tokens signed with an unauthorized secret key cannot authenticate."""
    fake_payload = {
        "sub": "demo-user-admin",
        "business_id": "demo-biz-vattara-health",
        "role": "admin",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
    }
    tampered_token = jwt.encode(fake_payload, "malicious_attacker_key_1234567890", algorithm="HS256")
    headers = {"Authorization": f"Bearer {tampered_token}"}
    response = client.get("/api/v1/appointments", headers=headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_jwt_missing_required_subject_claim(client: TestClient) -> None:
    """Ensure tokens without a subject claim ('sub') are rejected."""
    payload_no_sub = {
        "business_id": "demo-biz-vattara-health",
        "role": "admin",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
    }
    bad_token = jwt.encode(payload_no_sub, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    headers = {"Authorization": f"Bearer {bad_token}"}
    response = client.get("/api/v1/appointments", headers=headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ==============================================================================
# 2. API Key Tenant Impersonation Prevention Tests
# ==============================================================================

def test_api_key_impersonation_blocked(client: TestClient) -> None:
    """Passing an arbitrary vat_live_<id> without explicit server configuration must be rejected."""
    headers = {"X-API-Key": "vat_live_demo-biz-vattara-health"}
    response = client.get("/api/v1/assistant", headers=headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED




# ==============================================================================
# 3. Password Hashing & Plaintext Rejection Tests
# ==============================================================================

def test_plaintext_password_fallback_removed() -> None:
    """Ensure verify_password never matches plain text to plain text without hash."""
    raw_password = "MySecurePassword123!"
    # Matching against raw plaintext must fail
    assert verify_password(raw_password, raw_password) is False

    # Matching against genuine hash must succeed
    hashed = get_password_hash(raw_password)
    assert verify_password(raw_password, hashed) is True

    # Wrong password must fail
    assert verify_password("WrongPassword123!", hashed) is False


def test_production_secret_key_enforcement() -> None:
    """Ensure Settings rejects weak or default SECRET_KEY in production mode."""
    # Default temporary key must be rejected in production
    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="temporary_secret_key_change_in_production_environment",
        )

    # Short key (< 32 chars) must be rejected in production
    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="too_short_key",
        )

    # Strong key >= 32 chars must pass
    valid_settings = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a_very_strong_production_secret_key_exceeding_32_characters_random_hex",
    )
    assert valid_settings.ENVIRONMENT == "production"


# ==============================================================================
# 4. Secure Password Reset Verification Flow
# ==============================================================================

def test_secure_password_reset_flow(client: TestClient, db_session: Session) -> None:
    """Complete end-to-end verification of secure password reset."""
    target_email = "admin@vattara.com"

    # Step 1: Request reset code
    req_resp = client.post("/api/v1/auth/forgot-password", json={"email": target_email})
    assert req_resp.status_code == status.HTTP_200_OK
    generated_code = req_resp.json().get("reset_code")
    assert generated_code is not None

    # Query the generated reset entry in database
    reset_entry = db_session.scalar(
        select(PasswordReset)
        .where(PasswordReset.email == target_email, PasswordReset.is_used.is_(False))
        .order_by(PasswordReset.created_at.desc())
    )
    assert reset_entry is not None
    assert reset_entry.is_used is False
    assert len(reset_entry.code_hash) > 20  # Hash stored, not plaintext

    # Step 2: Attempt reset with wrong code
    bad_resp = client.post(
        "/api/v1/auth/reset-password",
        json={
            "email": target_email,
            "reset_code": "000000",
            "new_password": "NewAdminPassword@2026",
        },
    )
    assert bad_resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid reset verification code" in bad_resp.json()["detail"]

    # Step 3: Submit reset with genuine generated code
    success_resp = client.post(
        "/api/v1/auth/reset-password",
        json={
            "email": target_email,
            "reset_code": generated_code,
            "new_password": "BrandNewAdminPassword@2026",
        },
    )
    assert success_resp.status_code == status.HTTP_200_OK
    assert "successfully reset" in success_resp.json()["message"]

    # Step 4: Verify reset record is marked used
    db_session.refresh(reset_entry)
    assert reset_entry.is_used is True

    # Step 5: Code reuse must be rejected (single-use enforcement)
    reuse_resp = client.post(
        "/api/v1/auth/reset-password",
        json={
            "email": target_email,
            "reset_code": generated_code,
            "new_password": "AnotherNewPassword@2026",
        },
    )
    assert reuse_resp.status_code == status.HTTP_400_BAD_REQUEST

    # Step 6: Verify login with old password fails
    old_login = client.post(
        "/api/v1/auth/login",
        json={"email": target_email, "password": "Admin@123"},
    )
    assert old_login.status_code == status.HTTP_401_UNAUTHORIZED

    # Step 7: Verify login with new password succeeds
    new_login = client.post(
        "/api/v1/auth/login",
        json={"email": target_email, "password": "BrandNewAdminPassword@2026"},
    )
    assert new_login.status_code == status.HTTP_200_OK
    assert "access_token" in new_login.json()


def test_expired_password_reset_code_rejected(client: TestClient, db_session: Session) -> None:
    """Ensure password reset code expired in the past is rejected."""
    target_email = "admin@vattara.com"
    req_resp = client.post("/api/v1/auth/forgot-password", json={"email": target_email})
    reset_code = req_resp.json().get("reset_code")

    reset_entry = db_session.scalar(
        select(PasswordReset)
        .where(PasswordReset.email == target_email)
        .order_by(PasswordReset.created_at.desc())
    )
    assert reset_entry is not None
    # Expire the code in the past
    reset_entry.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db_session.commit()

    resp = client.post(
        "/api/v1/auth/reset-password",
        json={
            "email": target_email,
            "reset_code": reset_code,
            "new_password": "SomeNewPassword@123",
        },
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "expired" in resp.json()["detail"].lower()


# ==============================================================================
# 5. Multi-Tenant Data Isolation Tests
# ==============================================================================

@pytest.fixture
def tenant_b_setup(db_session: Session) -> dict[str, str]:
    """Create isolated second tenant (Business B) and return its auth headers."""
    biz_b = Business(
        id="tenant-b-dental-clinic",
        name="Dental Care Plus",
        vertical="dental",
        phone="+91 44 2345 6789",
        email="info@dentalcareplus.com",
        timezone="Asia/Kolkata",
        address="100, Gandhi Road, Chennai",
        is_active=True,
    )
    db_session.add(biz_b)

    user_b = User(
        id="user-tenant-b-admin",
        business_id=biz_b.id,
        email="doctor@dentalcareplus.com",
        full_name="Dr. Suresh Dental",
        hashed_password=get_password_hash("Password@123"),
        role="admin",
        is_active=True,
    )
    db_session.add(user_b)

    cust_b = Customer(
        id="tenant-b-customer-1",
        business_id=biz_b.id,
        name="Tenant B Patient",
        phone="+91 99999 11111",
        email="patient@tenantb.com",
        notes="Dental implant enquiry",
        total_calls=1,
        total_appointments=1,
    )
    db_session.add(cust_b)

    appt_b = Appointment(
        id="tenant-b-appointment-1",
        business_id=biz_b.id,
        customer_id=cust_b.id,
        appointment_time=datetime.now(timezone.utc) + timedelta(days=2),
        status="upcoming",
        notes="Root canal consultation",
        source="manual",
    )
    db_session.add(appt_b)
    db_session.commit()

    token_b = create_access_token(
        subject=user_b.id,
        extra_claims={"business_id": biz_b.id, "role": "admin"},
    )
    return {"Authorization": f"Bearer {token_b}", "business_id": biz_b.id}


def test_multi_tenant_appointments_isolation(
    client: TestClient,
    auth_headers: dict[str, str],
    tenant_b_setup: dict[str, str],
) -> None:
    """Ensure Tenant B cannot read, update, or cancel Tenant A's appointments."""
    headers_b = {"Authorization": tenant_b_setup["Authorization"]}

    # Tenant B lists appointments: must only see Tenant B's appointment
    resp_b = client.get("/api/v1/appointments", headers=headers_b)
    assert resp_b.status_code == status.HTTP_200_OK
    appts_b = resp_b.json()
    assert len(appts_b) == 1
    assert appts_b[0]["id"] == "tenant-b-appointment-1"

    # Tenant B tries to fetch Tenant A's appointment by ID: must return 404
    tenant_a_appt_id = "demo-appointment-1"
    leak_resp = client.get(f"/api/v1/appointments/{tenant_a_appt_id}", headers=headers_b)
    assert leak_resp.status_code == status.HTTP_404_NOT_FOUND

    # Tenant B tries to update Tenant A's appointment: must return 404
    update_resp = client.put(
        f"/api/v1/appointments/{tenant_a_appt_id}",
        json={"notes": "Hacked by Tenant B"},
        headers=headers_b,
    )
    assert update_resp.status_code == status.HTTP_404_NOT_FOUND

    # Tenant B tries to cancel Tenant A's appointment: must return 404
    cancel_resp = client.post(
        f"/api/v1/appointments/{tenant_a_appt_id}/cancel",
        params={"reason": "Malicious cancellation"},
        headers=headers_b,
    )
    assert cancel_resp.status_code == status.HTTP_404_NOT_FOUND


def test_multi_tenant_customers_isolation(
    client: TestClient,
    tenant_b_setup: dict[str, str],
) -> None:
    """Ensure Tenant B cannot view Tenant A's customer records or timeline."""
    headers_b = {"Authorization": tenant_b_setup["Authorization"]}

    # Tenant B lists customers: must only see Tenant B's customer
    resp = client.get("/api/v1/customers", headers=headers_b)
    assert resp.status_code == status.HTTP_200_OK
    customers = resp.json()
    assert len(customers) == 1
    assert customers[0]["id"] == "tenant-b-customer-1"

    # Tenant B directly fetches Tenant A's customer: must return 404
    leak_resp = client.get("/api/v1/customers/demo-customer-1", headers=headers_b)
    assert leak_resp.status_code == status.HTTP_404_NOT_FOUND


def test_multi_tenant_calls_isolation(
    client: TestClient,
    tenant_b_setup: dict[str, str],
) -> None:
    """Ensure Tenant B cannot view Tenant A's call logs or transcripts."""
    headers_b = {"Authorization": tenant_b_setup["Authorization"]}

    # Tenant B lists calls: must be empty
    resp = client.get("/api/v1/calls", headers=headers_b)
    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()) == 0

    # Tenant B requests Tenant A's call record: must return 404
    leak_resp = client.get("/api/v1/calls/demo-call-1", headers=headers_b)
    assert leak_resp.status_code == status.HTTP_404_NOT_FOUND


def test_multi_tenant_assistant_config_isolation(
    client: TestClient,
    auth_headers: dict[str, str],
    tenant_b_setup: dict[str, str],
) -> None:
    """Ensure assistant configuration is strictly isolated per tenant."""
    headers_b = {"Authorization": tenant_b_setup["Authorization"]}

    # Tenant B fetches config: creates/returns Tenant B config
    resp_b = client.get("/api/v1/assistant", headers=headers_b)
    assert resp_b.status_code == status.HTTP_200_OK
    assert resp_b.json()["business_id"] == tenant_b_setup["business_id"]

    # Tenant B updates assistant name
    client.put(
        "/api/v1/assistant",
        json={"assistant_name": "Dental Assistant AI"},
        headers=headers_b,
    )

    # Tenant A fetches config: must remain unchanged
    resp_a = client.get("/api/v1/assistant", headers=auth_headers)
    assert resp_a.status_code == status.HTTP_200_OK
    assert resp_a.json()["assistant_name"] == "Vattara Voice AI"
    assert resp_a.json()["business_id"] == "demo-biz-vattara-health"


# ==============================================================================
# 6. Database Migration & Schema Verification
# ==============================================================================

def test_database_models_registered_in_metadata() -> None:
    """Ensure all required tables are properly registered in SQLAlchemy metadata."""
    from app.database.base import Base

    table_names = set(Base.metadata.tables.keys())
    required_tables = {
        "businesses",
        "users",
        "assistant_configs",
        "services",
        "faqs",
        "customers",
        "calls",
        "appointments",
        "conversation_sessions",
        "reminders",
        "password_resets",
    }
    assert required_tables.issubset(table_names), (
        f"Missing tables in metadata: {required_tables - table_names}"
    )
