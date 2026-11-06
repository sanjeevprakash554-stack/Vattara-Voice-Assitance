"""Automated tests for Customer Management and Customer Interaction History."""

from datetime import date, datetime, time, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.models.appointment import Appointment
from app.models.business import Business
from app.models.call_history import CallHistory
from app.models.customer import Customer
from app.models.user import User, UserRole


@pytest.fixture
def two_tenants(db_session: Session) -> dict:
    """Fixture creating two distinct business tenants with admin and staff users."""
    biz1 = Business(
        business_name="City Hospital",
        business_type="hospital",
        email="contact@cityhospital.com",
        phone_number="+1-555-7777",
        is_active=True,
    )
    biz2 = Business(
        business_name="Metropolis Hotel",
        business_type="hotel",
        email="contact@metropolishotel.com",
        phone_number="+1-555-8888",
        is_active=True,
    )
    db_session.add_all([biz1, biz2])
    db_session.flush()

    admin1 = User(
        business_id=biz1.id,
        full_name="Hospital Admin",
        email="admin@cityhospital.com",
        password_hash=get_password_hash("AdminPass123!"),
        role=UserRole.BUSINESS_ADMIN.value,
        is_active=True,
    )
    staff1 = User(
        business_id=biz1.id,
        full_name="Hospital Nurse",
        email="nurse@cityhospital.com",
        password_hash=get_password_hash("StaffPass123!"),
        role=UserRole.STAFF.value,
        is_active=True,
    )

    admin2 = User(
        business_id=biz2.id,
        full_name="Hotel Manager",
        email="manager@metropolishotel.com",
        password_hash=get_password_hash("AdminPass123!"),
        role=UserRole.BUSINESS_ADMIN.value,
        is_active=True,
    )
    db_session.add_all([admin1, staff1, admin2])
    db_session.commit()

    token_b1_admin = create_access_token(subject=admin1.id, business_id=biz1.id, role=admin1.role)
    token_b1_staff = create_access_token(subject=staff1.id, business_id=biz1.id, role=staff1.role)
    token_b2_admin = create_access_token(subject=admin2.id, business_id=biz2.id, role=admin2.role)

    return {
        "b1": biz1,
        "b2": biz2,
        "b1_admin_token": token_b1_admin,
        "b1_staff_token": token_b1_staff,
        "b2_admin_token": token_b2_admin,
    }


# ==============================================================================
# CUSTOMER CRUD & SEARCH TESTS
# ==============================================================================

def test_create_customer_success(client: TestClient, two_tenants: dict) -> None:
    """Test creating a customer profile with all attributes."""
    token = two_tenants["b1_staff_token"]
    payload = {
        "customer_name": "Alice Johnson",
        "phone_number": "+1-555-0199",
        "email": "alice.johnson@example.com",
        "address": "456 Oak Street, Suite 2",
        "notes": "Prefers morning appointments",
    }
    response = client.post(
        f"{settings.API_V1_STR}/customers",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["customer_name"] == "Alice Johnson"
    assert data["phone_number"] == "+1-555-0199"
    assert data["email"] == "alice.johnson@example.com"
    assert data["address"] == "456 Oak Street, Suite 2"
    assert data["notes"] == "Prefers morning appointments"
    assert data["is_active"] is True
    assert data["id"] is not None


def test_create_customer_duplicate_phone_rejected(client: TestClient, two_tenants: dict) -> None:
    """Test duplicate phone number within the same tenant is rejected with 400."""
    token = two_tenants["b1_staff_token"]
    payload = {
        "customer_name": "Bob Smith",
        "phone_number": "+1-555-0200",
    }
    res1 = client.post(
        f"{settings.API_V1_STR}/customers",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res1.status_code == 201

    res2 = client.post(
        f"{settings.API_V1_STR}/customers",
        json={"customer_name": "Bob Smith Duplicate", "phone_number": "+1-555-0200"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res2.status_code == 400
    assert "already exists in your business" in res2.json()["detail"]


def test_same_phone_in_different_tenants_allowed(client: TestClient, two_tenants: dict) -> None:
    """Test that two different businesses can have customers with the same phone number."""
    token_b1 = two_tenants["b1_admin_token"]
    token_b2 = two_tenants["b2_admin_token"]
    payload = {"customer_name": "Shared Phone User", "phone_number": "+1-555-9999"}

    # Business 1 creates customer
    res1 = client.post(
        f"{settings.API_V1_STR}/customers",
        json=payload,
        headers={"Authorization": f"Bearer {token_b1}"},
    )
    assert res1.status_code == 201

    # Business 2 creates customer with same phone number -> Should succeed!
    res2 = client.post(
        f"{settings.API_V1_STR}/customers",
        json=payload,
        headers={"Authorization": f"Bearer {token_b2}"},
    )
    assert res2.status_code == 201
    assert res1.json()["id"] != res2.json()["id"]


def test_list_and_search_customers(client: TestClient, two_tenants: dict, db_session: Session) -> None:
    """Test customer search by name, phone, and email, along with pagination."""
    b1 = two_tenants["b1"]
    c1 = Customer(
        business_id=b1.id,
        customer_name="Michael Scott",
        phone_number="+1-555-0301",
        email="michael@dundermifflin.com",
        is_active=True,
    )
    c2 = Customer(
        business_id=b1.id,
        customer_name="Dwight Schrute",
        phone_number="+1-555-0302",
        email="dwight@schrute-farms.com",
        is_active=True,
    )
    c3 = Customer(
        business_id=b1.id,
        customer_name="Jim Halpert",
        phone_number="+1-555-0303",
        email="jim@dundermifflin.com",
        is_active=False,
    )
    db_session.add_all([c1, c2, c3])
    db_session.commit()

    token = two_tenants["b1_staff_token"]

    # Search by partial email "schrute"
    res_search = client.get(
        f"{settings.API_V1_STR}/customers?search=schrute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_search.status_code == 200
    assert len(res_search.json()) == 1
    assert res_search.json()[0]["customer_name"] == "Dwight Schrute"

    # Search by partial phone "0301"
    res_phone = client.get(
        f"{settings.API_V1_STR}/customers?search=0301",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_phone.status_code == 200
    assert len(res_phone.json()) == 1
    assert res_phone.json()[0]["customer_name"] == "Michael Scott"

    # Filter active only
    res_active = client.get(
        f"{settings.API_V1_STR}/customers?is_active=true",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_active.status_code == 200
    names = [c["customer_name"] for c in res_active.json()]
    assert "Michael Scott" in names
    assert "Dwight Schrute" in names
    assert "Jim Halpert" not in names


def test_update_and_deactivate_customer(client: TestClient, two_tenants: dict, db_session: Session) -> None:
    """Test updating customer fields and soft-deactivating a customer."""
    b1 = two_tenants["b1"]
    cust = Customer(
        business_id=b1.id,
        customer_name="Pam Beesly",
        phone_number="+1-555-0400",
        notes="Old notes",
        is_active=True,
    )
    db_session.add(cust)
    db_session.commit()

    token = two_tenants["b1_staff_token"]

    # Update notes and address
    res_update = client.put(
        f"{settings.API_V1_STR}/customers/{cust.id}",
        json={"notes": "Updated receptionist notes", "address": "Scranton, PA"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_update.status_code == 200
    assert res_update.json()["notes"] == "Updated receptionist notes"
    assert res_update.json()["address"] == "Scranton, PA"

    # Deactivate
    res_del = client.delete(
        f"{settings.API_V1_STR}/customers/{cust.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_del.status_code == 200
    assert "deactivated" in res_del.json()["message"]

    db_session.refresh(cust)
    assert cust.is_active is False


def test_cross_tenant_customer_isolation(client: TestClient, two_tenants: dict, db_session: Session) -> None:
    """Test Business 2 cannot get, update, or deactivate Business 1's customer (404)."""
    b1 = two_tenants["b1"]
    cust = Customer(
        business_id=b1.id,
        customer_name="Private B1 Patient",
        phone_number="+1-555-0999",
        is_active=True,
    )
    db_session.add(cust)
    db_session.commit()

    token_b2 = two_tenants["b2_admin_token"]

    # B2 attempts to view B1 customer
    res = client.get(
        f"{settings.API_V1_STR}/customers/{cust.id}",
        headers={"Authorization": f"Bearer {token_b2}"},
    )
    assert res.status_code == 404

    # B2 attempts to update B1 customer
    res_update = client.put(
        f"{settings.API_V1_STR}/customers/{cust.id}",
        json={"customer_name": "Tampered Name"},
        headers={"Authorization": f"Bearer {token_b2}"},
    )
    assert res_update.status_code == 404

    # B2 attempts to deactivate B1 customer
    res_del = client.delete(
        f"{settings.API_V1_STR}/customers/{cust.id}",
        headers={"Authorization": f"Bearer {token_b2}"},
    )
    assert res_del.status_code == 404


# ==============================================================================
# CUSTOMER INTERACTION HISTORY TESTS
# ==============================================================================

def test_customer_history_with_calls_and_appointments(client: TestClient, two_tenants: dict, db_session: Session) -> None:
    """Test retrieving complete interaction history dossier with appointments and call history."""
    b1 = two_tenants["b1"]
    cust = Customer(
        business_id=b1.id,
        customer_name="Stanley Hudson",
        phone_number="+1-555-0555",
        is_active=True,
    )
    db_session.add(cust)
    db_session.flush()

    # Add 2 appointments
    appt1 = Appointment(
        business_id=b1.id,
        customer_id=cust.id,
        appointment_date=date(2026, 11, 10),
        appointment_time=time(14, 30),
        service_name="Annual Physical Checkup",
        status="confirmed",
    )
    appt2 = Appointment(
        business_id=b1.id,
        customer_id=cust.id,
        appointment_date=date(2026, 11, 20),
        appointment_time=time(10, 0),
        service_name="Blood Test Followup",
        status="scheduled",
    )

    # Add 2 call records
    call1 = CallHistory(
        business_id=b1.id,
        customer_id=cust.id,
        phone_number="+1-555-0555",
        call_type="inbound",
        call_status="completed",
        call_duration=185,
        recording_url="https://recordings.example.com/call-1.mp3",
    )
    call2 = CallHistory(
        business_id=b1.id,
        customer_id=cust.id,
        phone_number="+1-555-0555",
        call_type="outbound",
        call_status="completed",
        call_duration=64,
        recording_url=None,
    )
    db_session.add_all([appt1, appt2, call1, call2])
    db_session.commit()

    token = two_tenants["b1_staff_token"]

    response = client.get(
        f"{settings.API_V1_STR}/customers/{cust.id}/history",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["customer"]["customer_name"] == "Stanley Hudson"
    assert data["total_appointments"] == 2
    assert data["total_calls"] == 2
    assert len(data["appointments"]) == 2
    assert len(data["call_history"]) == 2

    # Verify appointment details
    appt_services = [a["service_name"] for a in data["appointments"]]
    assert "Annual Physical Checkup" in appt_services
    assert "Blood Test Followup" in appt_services

    # Verify call details
    call_durations = [c["call_duration"] for c in data["call_history"]]
    assert 185 in call_durations
    assert 64 in call_durations

    # Verify last_interaction_date is computed
    assert data["last_interaction_date"] is not None


def test_customer_history_empty(client: TestClient, two_tenants: dict, db_session: Session) -> None:
    """Test retrieving history for a new customer with zero calls and zero appointments."""
    b1 = two_tenants["b1"]
    cust = Customer(
        business_id=b1.id,
        customer_name="Brand New Customer",
        phone_number="+1-555-0001",
        is_active=True,
    )
    db_session.add(cust)
    db_session.commit()

    token = two_tenants["b1_staff_token"]

    response = client.get(
        f"{settings.API_V1_STR}/customers/{cust.id}/history",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_appointments"] == 0
    assert data["total_calls"] == 0
    assert data["appointments"] == []
    assert data["call_history"] == []
    assert data["last_interaction_date"] is None


def test_customer_history_cross_tenant_forbidden(client: TestClient, two_tenants: dict, db_session: Session) -> None:
    """Test Business 2 cannot access Business 1's customer history (returns 404)."""
    b1 = two_tenants["b1"]
    cust = Customer(
        business_id=b1.id,
        customer_name="Confidential B1 Client",
        phone_number="+1-555-0888",
        is_active=True,
    )
    db_session.add(cust)
    db_session.commit()

    token_b2 = two_tenants["b2_admin_token"]

    response = client.get(
        f"{settings.API_V1_STR}/customers/{cust.id}/history",
        headers={"Authorization": f"Bearer {token_b2}"},
    )
    assert response.status_code == 404
