"""Automated test suite for Exotel Voice Agent Server-to-Server Authentication and Appointment Booking."""

from datetime import datetime, timezone
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


TEST_EXOTEL_KEY = "vat_live_test_exotel_secret_key_12345"


@pytest.fixture
def exotel_tenants_setup(db_session: Session) -> dict[str, Business | User]:
    """Create test businesses and users for dual auth and multi-tenant testing."""
    biz1 = Business(
        id="exotel-biz-clinic-1",
        name="Vattara Apollo Clinic",
        vertical="clinic",
        email="apollo@vattaraclinic.com",
        phone="+914428280001",
        is_active=True,
    )
    biz2 = Business(
        id="exotel-biz-dental-2",
        name="Vattara City Dental",
        vertical="clinic",
        email="dental@vattaraclinic.com",
        phone="+914428280002",
        is_active=True,
    )
    db_session.add_all([biz1, biz2])
    db_session.flush()

    user1 = User(
        id="exotel-user-admin-1",
        business_id=biz1.id,
        email="admin@apollo.com",
        full_name="Dr. Apollo Admin",
        hashed_password="dummy_hashed_password",
        role="admin",
        is_active=True,
    )
    user2 = User(
        id="exotel-user-admin-2",
        business_id=biz2.id,
        email="admin@dental.com",
        full_name="Dr. Dental Admin",
        hashed_password="dummy_hashed_password",
        role="admin",
        is_active=True,
    )
    db_session.add_all([user1, user2])

    service1 = Service(
        id="exotel-service-cardio",
        business_id=biz1.id,
        name="Cardiology Consultation",
        price=750.0,
        duration_minutes=30,
        is_active=True,
    )
    db_session.add(service1)
    db_session.commit()

    return {
        "biz1": biz1,
        "biz2": biz2,
        "user1": user1,
        "user2": user2,
        "service1": service1,
    }


# ==============================================================================
# AUTHENTICATION TESTS
# ==============================================================================

def test_jwt_authentication_still_works(
    client: TestClient,
    exotel_tenants_setup: dict[str, Business | User],
) -> None:
    """Verify standard JWT bearer authentication continues to work seamlessly."""
    user1 = exotel_tenants_setup["user1"]
    jwt_token = create_access_token(subject=user1.id, extra_claims={"business_id": user1.business_id})

    headers = {"Authorization": f"Bearer {jwt_token}"}
    response = client.get(f"{settings.API_V1_STR}/appointments", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_valid_exotel_api_key_bearer(
    client: TestClient,
    exotel_tenants_setup: dict[str, Business | User],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify Exotel request with Authorization: Bearer <API_KEY> is accepted."""
    biz1 = exotel_tenants_setup["biz1"]
    monkeypatch.setattr(settings, "EXOTEL_BUSINESS_API_KEYS", f"{TEST_EXOTEL_KEY}:{biz1.id}")

    headers = {"Authorization": f"Bearer {TEST_EXOTEL_KEY}"}
    response = client.get(f"{settings.API_V1_STR}/appointments", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_valid_exotel_api_key_x_header(
    client: TestClient,
    exotel_tenants_setup: dict[str, Business | User],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify Exotel request with X-API-Key: <API_KEY> header is accepted."""
    biz1 = exotel_tenants_setup["biz1"]
    monkeypatch.setattr(settings, "EXOTEL_BUSINESS_API_KEYS", f"{TEST_EXOTEL_KEY}:{biz1.id}")

    headers = {"X-API-Key": TEST_EXOTEL_KEY}
    response = client.get(f"{settings.API_V1_STR}/appointments", headers=headers)
    assert response.status_code == 200


def test_invalid_api_key_rejected(
    client: TestClient,
    exotel_tenants_setup: dict[str, Business | User],
) -> None:
    """Verify request with an invalid/forged API key returns HTTP 401 Unauthorized."""
    headers = {"Authorization": "Bearer vat_invalid_unrecognized_key_99999"}
    response = client.get(f"{settings.API_V1_STR}/appointments", headers=headers)
    assert response.status_code == 401
    assert "Invalid API key" in response.json()["detail"]


def test_missing_api_key_in_production_rejected(
    client: TestClient,
    exotel_tenants_setup: dict[str, Business | User],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that unauthenticated requests in production are strictly rejected (developer fallback disabled)."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    response = client.get(f"{settings.API_V1_STR}/appointments")
    assert response.status_code == 401
    assert "credentials were not provided" in response.json()["detail"].lower()


# ==============================================================================
# APPOINTMENT BOOKING TESTS (EXOTEL PAYLOAD)
# ==============================================================================

def test_exotel_booking_with_customer_id_new(
    client: TestClient,
    exotel_tenants_setup: dict[str, Business | User],
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test exact Exotel booking payload with customer_id='new' auto-creates customer and appointment."""
    biz1 = exotel_tenants_setup["biz1"]
    monkeypatch.setattr(settings, "EXOTEL_BUSINESS_API_KEYS", f"{TEST_EXOTEL_KEY}:{biz1.id}")

    payload = {
        "customer_name": "Arun Kumar",
        "customer_phone": "+919876543210",
        "service_id": None,
        "appointment_time": "2026-11-08T10:00:00+05:30",
        "end_time": "2026-11-08T10:30:00+05:30",
        "notes": "Booked through Exotel AI voice assistant",
        "source": "ai_call",
        "customer_id": "new",
    }
    headers = {"Authorization": f"Bearer {TEST_EXOTEL_KEY}"}
    response = client.post(f"{settings.API_V1_STR}/appointments", json=payload, headers=headers)

    assert response.status_code == 201
    data = response.json()
    assert data["source"] == "ai_call"
    assert data["status"] == "upcoming"
    assert data["business_id"] == biz1.id

    # Verify customer was auto-created
    customer = db_session.scalar(
        select(Customer).where(Customer.phone == "+919876543210", Customer.business_id == biz1.id)
    )
    assert customer is not None
    assert customer.name == "Arun Kumar"
    assert customer.total_appointments == 1
    assert data["customer_id"] == customer.id


def test_exotel_booking_with_customer_id_null(
    client: TestClient,
    exotel_tenants_setup: dict[str, Business | User],
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test Exotel booking payload with customer_id=None (JSON null) is accepted by schema."""
    biz1 = exotel_tenants_setup["biz1"]
    monkeypatch.setattr(settings, "EXOTEL_BUSINESS_API_KEYS", f"{TEST_EXOTEL_KEY}:{biz1.id}")

    payload = {
        "customer_name": "Kavitha Raman",
        "customer_phone": "+919876543299",
        "service_id": None,
        "appointment_time": "2026-11-08T11:00:00+05:30",
        "end_time": "2026-11-08T11:30:00+05:30",
        "notes": "Booked through Exotel with null customer_id",
        "source": "ai_call",
        "customer_id": None,
    }
    headers = {"Authorization": f"Bearer {TEST_EXOTEL_KEY}"}
    response = client.post(f"{settings.API_V1_STR}/appointments", json=payload, headers=headers)

    assert response.status_code == 201
    data = response.json()
    assert data["business_id"] == biz1.id
    assert data["customer_id"] is not None

    # Verify customer was auto-created
    cust = db_session.scalar(
        select(Customer).where(Customer.phone == "+919876543299", Customer.business_id == biz1.id)
    )
    assert cust is not None
    assert cust.name == "Kavitha Raman"


def test_existing_customer_reuse(
    client: TestClient,
    exotel_tenants_setup: dict[str, Business | User],
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test repeated booking for same phone number reuses customer and increments total_appointments."""
    biz1 = exotel_tenants_setup["biz1"]
    monkeypatch.setattr(settings, "EXOTEL_BUSINESS_API_KEYS", f"{TEST_EXOTEL_KEY}:{biz1.id}")

    # First booking
    p1 = {
        "customer_name": "Repeated Caller",
        "customer_phone": "+919800011122",
        "appointment_time": "2026-11-08T14:00:00+05:30",
        "customer_id": "new",
    }
    headers = {"Authorization": f"Bearer {TEST_EXOTEL_KEY}"}
    res1 = client.post(f"{settings.API_V1_STR}/appointments", json=p1, headers=headers)
    assert res1.status_code == 201
    cust_id_1 = res1.json()["customer_id"]

    # Second booking
    p2 = {
        "customer_name": "Repeated Caller",
        "customer_phone": "+919800011122",
        "appointment_time": "2026-11-09T14:00:00+05:30",
        "customer_id": None,
    }
    res2 = client.post(f"{settings.API_V1_STR}/appointments", json=p2, headers=headers)
    assert res2.status_code == 201
    cust_id_2 = res2.json()["customer_id"]

    # Must be the exact same customer ID
    assert cust_id_1 == cust_id_2

    # Verify only 1 customer record exists and total_appointments is 2
    customers = db_session.scalars(
        select(Customer).where(Customer.phone == "+919800011122", Customer.business_id == biz1.id)
    ).all()
    assert len(customers) == 1
    assert customers[0].total_appointments == 2


def test_invalid_service_id_rejected(
    client: TestClient,
    exotel_tenants_setup: dict[str, Business | User],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test booking with invalid/placeholder service_id returns HTTP 400 Bad Request."""
    biz1 = exotel_tenants_setup["biz1"]
    monkeypatch.setattr(settings, "EXOTEL_BUSINESS_API_KEYS", f"{TEST_EXOTEL_KEY}:{biz1.id}")

    payload = {
        "customer_name": "Arun Kumar",
        "customer_phone": "+919876543210",
        "service_id": "SERVICE_ID_HERE",  # Invalid placeholder
        "appointment_time": "2026-11-08T10:00:00+05:30",
        "customer_id": "new",
    }
    headers = {"Authorization": f"Bearer {TEST_EXOTEL_KEY}"}
    response = client.post(f"{settings.API_V1_STR}/appointments", json=payload, headers=headers)
    assert response.status_code == 400
    assert "Service ID" in response.json()["detail"]


def test_valid_service_id_linked(
    client: TestClient,
    exotel_tenants_setup: dict[str, Business | User],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test booking with valid service_id links service correctly."""
    biz1 = exotel_tenants_setup["biz1"]
    service1 = exotel_tenants_setup["service1"]
    monkeypatch.setattr(settings, "EXOTEL_BUSINESS_API_KEYS", f"{TEST_EXOTEL_KEY}:{biz1.id}")

    payload = {
        "customer_name": "Cardio Patient",
        "customer_phone": "+919844455566",
        "service_id": service1.id,
        "appointment_time": "2026-11-08T15:00:00+05:30",
        "customer_id": "new",
    }
    headers = {"Authorization": f"Bearer {TEST_EXOTEL_KEY}"}
    response = client.post(f"{settings.API_V1_STR}/appointments", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["service_id"] == service1.id
    assert data["service"]["name"] == "Cardiology Consultation"


def test_missing_appointment_time_rejected(
    client: TestClient,
    exotel_tenants_setup: dict[str, Business | User],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test payload missing mandatory appointment_time returns HTTP 422 Unprocessable Entity."""
    biz1 = exotel_tenants_setup["biz1"]
    monkeypatch.setattr(settings, "EXOTEL_BUSINESS_API_KEYS", f"{TEST_EXOTEL_KEY}:{biz1.id}")

    payload = {
        "customer_name": "Arun Kumar",
        "customer_phone": "+919876543210",
        # Missing appointment_time
        "customer_id": "new",
    }
    headers = {"Authorization": f"Bearer {TEST_EXOTEL_KEY}"}
    response = client.post(f"{settings.API_V1_STR}/appointments", json=payload, headers=headers)
    assert response.status_code == 422


def test_cross_tenant_isolation(
    client: TestClient,
    exotel_tenants_setup: dict[str, Business | User],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test appointments created by Business 1 API key cannot be accessed by Business 2."""
    biz1 = exotel_tenants_setup["biz1"]
    biz2 = exotel_tenants_setup["biz2"]

    key1 = "vat_live_biz1_key_aaa"
    key2 = "vat_live_biz2_key_bbb"
    monkeypatch.setattr(
        settings, "EXOTEL_BUSINESS_API_KEYS", f"{key1}:{biz1.id},{key2}:{biz2.id}"
    )

    # 1. Book appointment using Business 1 API key
    payload = {
        "customer_name": "Tenant 1 Patient",
        "customer_phone": "+919700011100",
        "appointment_time": "2026-11-08T16:00:00+05:30",
        "customer_id": "new",
    }
    headers1 = {"Authorization": f"Bearer {key1}"}
    res1 = client.post(f"{settings.API_V1_STR}/appointments", json=payload, headers=headers1)
    assert res1.status_code == 201
    appt_id_1 = res1.json()["id"]

    # 2. Query appointment list with Business 2 API key
    headers2 = {"Authorization": f"Bearer {key2}"}
    res2 = client.get(f"{settings.API_V1_STR}/appointments", headers=headers2)
    assert res2.status_code == 200
    biz2_appts = res2.json()
    assert not any(a["id"] == appt_id_1 for a in biz2_appts)

    # 3. Attempt direct access to Business 1 appointment using Business 2 API key
    res3 = client.get(f"{settings.API_V1_STR}/appointments/{appt_id_1}", headers=headers2)
    assert res3.status_code == 404
