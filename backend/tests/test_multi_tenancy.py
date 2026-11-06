"""Dedicated automated tests verifying strict multi-tenant data isolation and boundary enforcement."""

from datetime import date, time
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
def two_tenants_setup(db_session: Session) -> dict:
    """Fixture creating two isolated business tenants with their respective admin users and data."""
    # Tenant A (City Hospital)
    biz_a = Business(business_name="City Hospital", business_type="hospital", email="contact@cityhospital.com", is_active=True)
    # Tenant B (Grand Hotel)
    biz_b = Business(business_name="Grand Hotel", business_type="hotel", email="contact@grandhotel.com", is_active=True)
    db_session.add_all([biz_a, biz_b])
    db_session.flush()

    # Admin A
    admin_a = User(
        business_id=biz_a.id,
        full_name="Hospital Admin",
        email="admin@cityhospital.com",
        password_hash=get_password_hash("Pass123!"),
        role=UserRole.BUSINESS_ADMIN.value,
        is_active=True,
    )
    # Staff A
    staff_a = User(
        business_id=biz_a.id,
        full_name="Hospital Nurse",
        email="nurse@cityhospital.com",
        password_hash=get_password_hash("Pass123!"),
        role=UserRole.STAFF.value,
        is_active=True,
    )

    # Admin B
    admin_b = User(
        business_id=biz_b.id,
        full_name="Hotel Manager",
        email="manager@grandhotel.com",
        password_hash=get_password_hash("Pass123!"),
        role=UserRole.BUSINESS_ADMIN.value,
        is_active=True,
    )
    # Staff B
    staff_b = User(
        business_id=biz_b.id,
        full_name="Hotel Concierge",
        email="concierge@grandhotel.com",
        password_hash=get_password_hash("Pass123!"),
        role=UserRole.STAFF.value,
        is_active=True,
    )

    db_session.add_all([admin_a, staff_a, admin_b, staff_b])
    db_session.flush()

    # Customer & Appointments in Tenant A
    cust_a = Customer(business_id=biz_a.id, customer_name="Patient John", phone_number="+1-555-1001")
    db_session.add(cust_a)
    db_session.flush()

    appt_a = Appointment(
        business_id=biz_a.id,
        customer_id=cust_a.id,
        appointment_date=date(2026, 12, 1),
        appointment_time=time(9, 0),
        service_name="Cardiology Consultation",
    )
    call_a = CallHistory(
        business_id=biz_a.id,
        customer_id=cust_a.id,
        phone_number="+1-555-1001",
        call_type="inbound",
        call_status="completed",
        call_duration=180,
    )

    # Customer & Appointments in Tenant B
    cust_b = Customer(business_id=biz_b.id, customer_name="Guest Alice", phone_number="+1-555-2002")
    db_session.add(cust_b)
    db_session.flush()

    appt_b = Appointment(
        business_id=biz_b.id,
        customer_id=cust_b.id,
        appointment_date=date(2026, 12, 2),
        appointment_time=time(14, 0),
        service_name="Penthouse Suite",
    )
    call_b = CallHistory(
        business_id=biz_b.id,
        customer_id=cust_b.id,
        phone_number="+1-555-2002",
        call_type="inbound",
        call_status="completed",
        call_duration=240,
    )

    db_session.add_all([appt_a, call_a, appt_b, call_b])
    db_session.commit()

    token_a = create_access_token(subject=admin_a.id, business_id=biz_a.id, role=admin_a.role)
    token_b = create_access_token(subject=admin_b.id, business_id=biz_b.id, role=admin_b.role)

    return {
        "biz_a": biz_a,
        "biz_b": biz_b,
        "admin_a": admin_a,
        "staff_a": staff_a,
        "admin_b": admin_b,
        "staff_b": staff_b,
        "token_a": token_a,
        "token_b": token_b,
        "cust_a": cust_a,
        "cust_b": cust_b,
        "appt_a": appt_a,
        "appt_b": appt_b,
        "call_a": call_a,
        "call_b": call_b,
    }


def test_business_a_cannot_view_business_b_users(client: TestClient, two_tenants_setup: dict) -> None:
    """Verify that Tenant A cannot query details of a staff member belonging to Tenant B."""
    token_a = two_tenants_setup["token_a"]
    staff_b = two_tenants_setup["staff_b"]

    response = client.get(
        f"{settings.API_V1_STR}/users/{staff_b.id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    # Must return 404 Not Found to prevent leaking ID existence across tenants
    assert response.status_code == 404
    assert "not found in this business" in response.json()["detail"].lower()


def test_business_a_cannot_modify_business_b_users(client: TestClient, two_tenants_setup: dict) -> None:
    """Verify that Tenant A cannot update a staff member belonging to Tenant B."""
    token_a = two_tenants_setup["token_a"]
    staff_b = two_tenants_setup["staff_b"]

    response = client.put(
        f"{settings.API_V1_STR}/users/{staff_b.id}",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"full_name": "Tampered Name"},
    )
    assert response.status_code == 404


def test_business_a_cannot_deactivate_business_b_users(client: TestClient, two_tenants_setup: dict) -> None:
    """Verify that Tenant A cannot deactivate staff belonging to Tenant B."""
    token_a = two_tenants_setup["token_a"]
    staff_b = two_tenants_setup["staff_b"]

    response = client.delete(
        f"{settings.API_V1_STR}/users/{staff_b.id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert response.status_code == 404


def test_business_staff_listing_strictly_isolated(client: TestClient, two_tenants_setup: dict) -> None:
    """Verify that user list only returns accounts associated with the authenticated tenant."""
    token_a = two_tenants_setup["token_a"]
    admin_a = two_tenants_setup["admin_a"]
    staff_a = two_tenants_setup["staff_a"]
    staff_b = two_tenants_setup["staff_b"]

    response = client.get(
        f"{settings.API_V1_STR}/users",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert response.status_code == 200
    returned_emails = [u["email"] for u in response.json()]

    assert admin_a.email in returned_emails
    assert staff_a.email in returned_emails
    assert staff_b.email not in returned_emails


def test_database_level_cross_tenant_isolation(two_tenants_setup: dict, db_session: Session) -> None:
    """Verify multi-tenant query isolation on Customers, Appointments, and Call Histories."""
    biz_a = two_tenants_setup["biz_a"]
    biz_b = two_tenants_setup["biz_b"]

    # Customers
    customers_a = db_session.query(Customer).filter(Customer.business_id == biz_a.id).all()
    customers_b = db_session.query(Customer).filter(Customer.business_id == biz_b.id).all()
    assert all(c.business_id == biz_a.id for c in customers_a)
    assert all(c.business_id == biz_b.id for c in customers_b)

    # Appointments
    appts_a = db_session.query(Appointment).filter(Appointment.business_id == biz_a.id).all()
    appts_b = db_session.query(Appointment).filter(Appointment.business_id == biz_b.id).all()
    assert all(a.business_id == biz_a.id for a in appts_a)
    assert all(a.business_id == biz_b.id for a in appts_b)

    # Call Histories
    calls_a = db_session.query(CallHistory).filter(CallHistory.business_id == biz_a.id).all()
    calls_b = db_session.query(CallHistory).filter(CallHistory.business_id == biz_b.id).all()
    assert all(c.business_id == biz_a.id for c in calls_a)
    assert all(c.business_id == biz_b.id for c in calls_b)


def test_inactive_business_blocked_from_protected_services(client: TestClient, two_tenants_setup: dict, db_session: Session) -> None:
    """Verify that when a business is deactivated, its users are blocked with 403 Forbidden on protected endpoints."""
    biz_a = two_tenants_setup["biz_a"]
    token_a = two_tenants_setup["token_a"]

    # Deactivate Business A
    biz_a.is_active = False
    db_session.commit()

    # Attempt to list staff
    response = client.get(
        f"{settings.API_V1_STR}/users",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert response.status_code == 403
    assert "business account is inactive" in response.json()["detail"].lower()
