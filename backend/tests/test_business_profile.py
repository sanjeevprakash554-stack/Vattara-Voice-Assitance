"""Automated tests for Business Profile Management endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.models.business import Business
from app.models.user import User, UserRole


@pytest.fixture
def business_with_users(db_session: Session) -> dict:
    """Fixture creating a business with both an admin and a staff user."""
    biz = Business(
        business_name="Elite Dental Clinic",
        business_type="hospital",
        email="contact@elitedental.com",
        phone_number="+1-555-8899",
        address="100 Medical Plaza",
        website="https://elitedental.com",
        description="Full-service modern dental healthcare clinic",
        logo_url="https://elitedental.com/logo.png",
        timezone="America/New_York",
        is_active=True,
    )
    db_session.add(biz)
    db_session.flush()

    admin = User(
        business_id=biz.id,
        full_name="Dr. Smith Admin",
        email="admin@elitedental.com",
        password_hash=get_password_hash("AdminPass123!"),
        role=UserRole.BUSINESS_ADMIN.value,
        is_active=True,
    )
    staff = User(
        business_id=biz.id,
        full_name="Dental Receptionist",
        email="staff@elitedental.com",
        password_hash=get_password_hash("StaffPass123!"),
        role=UserRole.STAFF.value,
        is_active=True,
    )
    db_session.add_all([admin, staff])
    db_session.commit()

    admin_token = create_access_token(subject=admin.id, business_id=biz.id, role=admin.role)
    staff_token = create_access_token(subject=staff.id, business_id=biz.id, role=staff.role)

    return {
        "business": biz,
        "admin": admin,
        "staff": staff,
        "admin_token": admin_token,
        "staff_token": staff_token,
    }


def test_get_business_profile_as_admin(client: TestClient, business_with_users: dict) -> None:
    """Test retrieving business profile as a Business Admin."""
    token = business_with_users["admin_token"]
    biz = business_with_users["business"]

    response = client.get(
        f"{settings.API_V1_STR}/business/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["business_name"] == "Elite Dental Clinic"
    assert data["website"] == "https://elitedental.com"
    assert data["timezone"] == "America/New_York"
    assert data["email"] == biz.email


def test_get_business_profile_as_staff(client: TestClient, business_with_users: dict) -> None:
    """Test staff member can view their business profile."""
    token = business_with_users["staff_token"]

    response = client.get(
        f"{settings.API_V1_STR}/business/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["business_name"] == "Elite Dental Clinic"


def test_update_business_profile_as_admin(client: TestClient, business_with_users: dict) -> None:
    """Test Business Admin updating business profile information."""
    token = business_with_users["admin_token"]

    payload = {
        "business_name": "Elite Dental & Orthodontics",
        "phone_number": "+1-555-9900",
        "website": "https://new.elitedental.com",
        "description": "Expanded comprehensive oral healthcare",
        "timezone": "America/Chicago",
    }

    response = client.put(
        f"{settings.API_V1_STR}/business/profile",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["business_name"] == "Elite Dental & Orthodontics"
    assert data["phone_number"] == "+1-555-9900"
    assert data["website"] == "https://new.elitedental.com"
    assert data["timezone"] == "America/Chicago"


def test_staff_cannot_update_business_profile(client: TestClient, business_with_users: dict) -> None:
    """Test staff members receive 403 Forbidden when attempting to modify business profile."""
    token = business_with_users["staff_token"]

    response = client.put(
        f"{settings.API_V1_STR}/business/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={"business_name": "Unauthorized Change"},
    )
    assert response.status_code == 403
    assert "insufficient permissions" in response.json()["detail"].lower()


def test_unauthenticated_profile_access_rejected(client: TestClient) -> None:
    """Test unauthenticated requests are rejected with 401 Unauthorized."""
    response = client.get(f"{settings.API_V1_STR}/business/profile")
    assert response.status_code == 401
