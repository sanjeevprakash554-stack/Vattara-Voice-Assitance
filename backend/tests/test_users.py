"""Automated tests for Staff and User Management endpoints (RBAC and business admin operations)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.models.business import Business
from app.models.user import User, UserRole


@pytest.fixture
def business_setup(db_session: Session) -> tuple[Business, User, str]:
    """Fixture providing a test business, an admin user, and an auth token."""
    business = Business(
        business_name="Prestige Motors",
        business_type="automobile",
        email="contact@prestigemotors.com",
        is_active=True,
    )
    db_session.add(business)
    db_session.flush()

    admin = User(
        business_id=business.id,
        full_name="Admin Manager",
        email="admin@prestigemotors.com",
        password_hash=get_password_hash("AdminPass123!"),
        role=UserRole.BUSINESS_ADMIN.value,
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()

    token = create_access_token(subject=admin.id, business_id=business.id, role=admin.role)
    return business, admin, token


def test_create_staff_user_success(client: TestClient, business_setup: tuple) -> None:
    """Test Business Admin creating a staff account."""
    business, admin, token = business_setup

    payload = {
        "full_name": "James Receptionist",
        "email": "james@prestigemotors.com",
        "password": "SecurePassword123!",
        "role": UserRole.STAFF.value,
    }

    response = client.post(
        f"{settings.API_V1_STR}/users",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "james@prestigemotors.com"
    assert data["business_id"] == business.id
    assert data["role"] == UserRole.STAFF.value
    assert data["is_active"] is True
    assert "password_hash" not in data


def test_business_admin_cannot_create_super_admin(client: TestClient, business_setup: tuple) -> None:
    """Test that a Business Admin cannot elevate or create a Super Admin."""
    _, _, token = business_setup

    payload = {
        "full_name": "Rogue Admin",
        "email": "rogue@example.com",
        "password": "SecurePassword123!",
        "role": UserRole.SUPER_ADMIN.value,
    }

    response = client.post(
        f"{settings.API_V1_STR}/users",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert response.status_code == 403
    assert "cannot create super admin" in response.json()["detail"].lower()


def test_create_staff_duplicate_email(client: TestClient, business_setup: tuple) -> None:
    """Test creating a staff member fails if the email already exists."""
    _, admin, token = business_setup

    payload = {
        "full_name": "Duplicate User",
        "email": admin.email,  # already used by the admin
        "password": "SecurePassword123!",
        "role": UserRole.STAFF.value,
    }

    response = client.post(
        f"{settings.API_V1_STR}/users",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()


def test_list_business_staff(client: TestClient, business_setup: tuple, db_session: Session) -> None:
    """Test listing staff members scoped strictly to the current business."""
    business, admin, token = business_setup

    staff1 = User(
        business_id=business.id,
        full_name="Staff One",
        email="staff1@prestigemotors.com",
        password_hash="hash",
        role=UserRole.STAFF.value,
    )
    db_session.add(staff1)
    db_session.commit()

    response = client.get(
        f"{settings.API_V1_STR}/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    staff_list = response.json()
    assert len(staff_list) >= 2  # Admin + staff1
    emails = [u["email"] for u in staff_list]
    assert admin.email in emails
    assert "staff1@prestigemotors.com" in emails


def test_get_staff_member_details(client: TestClient, business_setup: tuple, db_session: Session) -> None:
    """Test viewing details of a specific staff member."""
    business, _, token = business_setup

    staff = User(
        business_id=business.id,
        full_name="Kelly Kapoor",
        email="kelly@prestigemotors.com",
        password_hash="hash",
        role=UserRole.STAFF.value,
    )
    db_session.add(staff)
    db_session.commit()

    response = client.get(
        f"{settings.API_V1_STR}/users/{staff.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == staff.id
    assert data["full_name"] == "Kelly Kapoor"


def test_update_staff_member(client: TestClient, business_setup: tuple, db_session: Session) -> None:
    """Test updating permitted staff fields."""
    business, _, token = business_setup

    staff = User(
        business_id=business.id,
        full_name="Dwight Schrute",
        email="dwight@prestigemotors.com",
        password_hash="hash",
        role=UserRole.STAFF.value,
    )
    db_session.add(staff)
    db_session.commit()

    response = client.put(
        f"{settings.API_V1_STR}/users/{staff.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "Dwight K. Schrute", "role": UserRole.BUSINESS_ADMIN.value},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Dwight K. Schrute"
    assert data["role"] == UserRole.BUSINESS_ADMIN.value


def test_deactivate_staff_member(client: TestClient, business_setup: tuple, db_session: Session) -> None:
    """Test deactivating a staff member account."""
    business, _, token = business_setup

    staff = User(
        business_id=business.id,
        full_name="Jim Halpert",
        email="jim@prestigemotors.com",
        password_hash="hash",
        role=UserRole.STAFF.value,
        is_active=True,
    )
    db_session.add(staff)
    db_session.commit()

    response = client.delete(
        f"{settings.API_V1_STR}/users/{staff.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert "deactivated" in response.json()["message"].lower()

    # Verify status in database
    db_session.refresh(staff)
    assert staff.is_active is False


def test_business_admin_cannot_deactivate_self(client: TestClient, business_setup: tuple) -> None:
    """Test that an administrator cannot accidentally deactivate their own account."""
    _, admin, token = business_setup

    response = client.delete(
        f"{settings.API_V1_STR}/users/{admin.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    assert "cannot deactivate your own" in response.json()["detail"].lower()


def test_staff_cannot_manage_users(client: TestClient, business_setup: tuple, db_session: Session) -> None:
    """Test that regular staff accounts receive 403 Forbidden when attempting staff management."""
    business, _, _ = business_setup

    staff_user = User(
        business_id=business.id,
        full_name="Regular Staff",
        email="regular@prestigemotors.com",
        password_hash="hash",
        role=UserRole.STAFF.value,
        is_active=True,
    )
    db_session.add(staff_user)
    db_session.commit()

    staff_token = create_access_token(
        subject=staff_user.id,
        business_id=business.id,
        role=staff_user.role,
    )

    response = client.post(
        f"{settings.API_V1_STR}/users",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={"full_name": "Test", "email": "test@test.com", "password": "Pass123!"},
    )
    assert response.status_code == 403
    assert "insufficient permissions" in response.json()["detail"].lower()
