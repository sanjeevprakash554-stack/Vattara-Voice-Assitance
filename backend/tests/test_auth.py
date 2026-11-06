"""Automated tests for Authentication, Registration, JWT lifecycle, and Profile endpoints."""

from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.models.business import Business
from app.models.user import User, UserRole


def test_business_registration_success(client: TestClient) -> None:
    """Test successful business registration creating business and admin account."""
    payload = {
        "business_name": "Sunrise Dental Care",
        "business_type": "hospital",
        "business_email": "contact@sunrisedental.com",
        "business_phone_number": "+1-555-7788",
        "business_address": "456 Healthcare Way, Sunnyvale",
        "admin_full_name": "Dr. Marcus Vance",
        "admin_email": "marcus.vance@sunrisedental.com",
        "admin_password": "SecurePassword123!",
        "confirm_password": "SecurePassword123!",
    }

    response = client.post(f"{settings.API_V1_STR}/auth/register", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert "business" in data
    assert "admin_user" in data
    assert data["business"]["business_name"] == "Sunrise Dental Care"
    assert data["business"]["is_active"] is True
    assert data["admin_user"]["email"] == "marcus.vance@sunrisedental.com"
    assert data["admin_user"]["role"] == UserRole.BUSINESS_ADMIN.value
    assert data["admin_user"]["is_active"] is True
    # Ensure sensitive credentials are never leaked
    assert "password" not in data["admin_user"]
    assert "password_hash" not in data["admin_user"]


def test_registration_duplicate_business_email(client: TestClient, db_session: Session) -> None:
    """Test registration failure when business email already exists."""
    business = Business(
        business_name="Existing Clinic",
        business_type="hospital",
        email="existing@clinic.com",
    )
    db_session.add(business)
    db_session.commit()

    payload = {
        "business_name": "Another Clinic",
        "business_type": "hospital",
        "business_email": "existing@clinic.com",
        "admin_full_name": "Admin User",
        "admin_email": "newadmin@clinic.com",
        "admin_password": "StrongPassword123!",
        "confirm_password": "StrongPassword123!",
    }

    response = client.post(f"{settings.API_V1_STR}/auth/register", json=payload)
    assert response.status_code == 400
    assert "business with this email address is already registered" in response.json()["detail"].lower()


def test_registration_duplicate_admin_email(client: TestClient, db_session: Session) -> None:
    """Test registration failure when admin email is already registered."""
    user = User(
        business_id=None,
        full_name="Existing User",
        email="existing.user@example.com",
        password_hash="some_hash",
        role=UserRole.STAFF.value,
    )
    db_session.add(user)
    db_session.commit()

    payload = {
        "business_name": "Brand New Business",
        "business_type": "salon",
        "business_email": "brandnew@salon.com",
        "admin_full_name": "Admin User",
        "admin_email": "existing.user@example.com",
        "admin_password": "StrongPassword123!",
        "confirm_password": "StrongPassword123!",
    }

    response = client.post(f"{settings.API_V1_STR}/auth/register", json=payload)
    assert response.status_code == 400
    assert "user with this administrator email address already exists" in response.json()["detail"].lower()


def test_registration_password_mismatch(client: TestClient) -> None:
    """Test registration validation when password confirmation fails."""
    payload = {
        "business_name": "Mismatch Spa",
        "business_type": "salon",
        "business_email": "mismatch@spa.com",
        "admin_full_name": "Admin User",
        "admin_email": "admin@spa.com",
        "admin_password": "StrongPassword123!",
        "confirm_password": "DifferentPassword123!",
    }

    response = client.post(f"{settings.API_V1_STR}/auth/register", json=payload)
    assert response.status_code == 422


def test_registration_weak_password(client: TestClient) -> None:
    """Test registration validation when password does not meet complexity requirements."""
    payload = {
        "business_name": "Weak Pass Org",
        "business_type": "hotel",
        "business_email": "weak@hotel.com",
        "admin_full_name": "Admin User",
        "admin_email": "admin@weakhotel.com",
        "admin_password": "weak",
        "confirm_password": "weak",
    }

    response = client.post(f"{settings.API_V1_STR}/auth/register", json=payload)
    assert response.status_code == 422  # Fails min_length constraint


def test_login_success_json(client: TestClient, db_session: Session) -> None:
    """Test user login with JSON payload returning valid JWT token."""
    raw_password = "ValidPassword123!"
    business = Business(
        business_name="Downtown Hotel",
        business_type="hotel",
        email="info@downtownhotel.com",
        is_active=True,
    )
    db_session.add(business)
    db_session.flush()

    user = User(
        business_id=business.id,
        full_name="John Doe",
        email="john.doe@downtownhotel.com",
        password_hash=get_password_hash(raw_password),
        role=UserRole.BUSINESS_ADMIN.value,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={"email": "john.doe@downtownhotel.com", "password": raw_password},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "john.doe@downtownhotel.com"
    assert data["user"]["business_name"] == "Downtown Hotel"


def test_login_success_oauth2_form(client: TestClient, db_session: Session) -> None:
    """Test user login with standard OAuth2 form payload (for Swagger UI Authorize button)."""
    raw_password = "OAuthPassword123!"
    user = User(
        business_id=None,
        full_name="Platform Operator",
        email="operator@platform.com",
        password_hash=get_password_hash(raw_password),
        role=UserRole.SUPER_ADMIN.value,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        f"{settings.API_V1_STR}/auth/login",
        data={"username": "operator@platform.com", "password": raw_password},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_invalid_credentials(client: TestClient, db_session: Session) -> None:
    """Test that incorrect credentials return generic 401 without user enumeration."""
    user = User(
        business_id=None,
        full_name="Valid User",
        email="valid@example.com",
        password_hash=get_password_hash("CorrectPassword123!"),
        role=UserRole.STAFF.value,
    )
    db_session.add(user)
    db_session.commit()

    # Wrong password
    resp1 = client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={"email": "valid@example.com", "password": "WrongPassword123!"},
    )
    assert resp1.status_code == 401
    assert resp1.json()["detail"] == "Invalid email or password"

    # Non-existent email
    resp2 = client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={"email": "nonexistent@example.com", "password": "AnyPassword123!"},
    )
    assert resp2.status_code == 401
    assert resp2.json()["detail"] == "Invalid email or password"


def test_login_deactivated_user_blocked(client: TestClient, db_session: Session) -> None:
    """Test that deactivated users are blocked from logging in with 403."""
    user = User(
        business_id=None,
        full_name="Banned User",
        email="banned@example.com",
        password_hash=get_password_hash("ValidPass123!"),
        role=UserRole.STAFF.value,
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={"email": "banned@example.com", "password": "ValidPass123!"},
    )
    assert response.status_code == 403
    assert "deactivated" in response.json()["detail"].lower()


def test_login_deactivated_business_blocked(client: TestClient, db_session: Session) -> None:
    """Test that users belonging to deactivated business tenants cannot log in."""
    business = Business(
        business_name="Suspended Hotel",
        business_type="hotel",
        email="admin@suspended.com",
        is_active=False,
    )
    db_session.add(business)
    db_session.flush()

    user = User(
        business_id=business.id,
        full_name="Staff Person",
        email="staff@suspended.com",
        password_hash=get_password_hash("ValidPass123!"),
        role=UserRole.STAFF.value,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={"email": "staff@suspended.com", "password": "ValidPass123!"},
    )
    assert response.status_code == 403
    assert "business account is inactive" in response.json()["detail"].lower()


def test_get_current_user_profile(client: TestClient, db_session: Session) -> None:
    """Test retrieving authenticated user profile."""
    business = Business(
        business_name="Urban Auto Repair",
        business_type="automobile",
        email="service@urbanauto.com",
        is_active=True,
    )
    db_session.add(business)
    db_session.flush()

    user = User(
        business_id=business.id,
        full_name="Michael Scott",
        email="michael@urbanauto.com",
        password_hash=get_password_hash("Pass123!"),
        role=UserRole.BUSINESS_ADMIN.value,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    token = create_access_token(subject=user.id, business_id=business.id, role=user.role)

    response = client.get(
        f"{settings.API_V1_STR}/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "michael@urbanauto.com"
    assert data["full_name"] == "Michael Scott"
    assert data["business_name"] == "Urban Auto Repair"


def test_update_current_user_profile(client: TestClient, db_session: Session) -> None:
    """Test updating user profile display name."""
    user = User(
        business_id=None,
        full_name="Original Name",
        email="update.me@example.com",
        password_hash="dummy_hash",
        role=UserRole.STAFF.value,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    token = create_access_token(subject=user.id, role=user.role)

    response = client.put(
        f"{settings.API_V1_STR}/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "Updated Name"},
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Name"


def test_change_password_success(client: TestClient, db_session: Session) -> None:
    """Test changing password and logging in with the new password."""
    old_password = "OldPassword123!"
    new_password = "NewStrongPassword456!"

    user = User(
        business_id=None,
        full_name="Password Changer",
        email="changer@example.com",
        password_hash=get_password_hash(old_password),
        role=UserRole.STAFF.value,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    token = create_access_token(subject=user.id, role=user.role)

    response = client.post(
        f"{settings.API_V1_STR}/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": old_password,
            "new_password": new_password,
            "confirm_new_password": new_password,
        },
    )
    assert response.status_code == 200
    assert "successfully" in response.json()["message"].lower()

    # Old password no longer works
    login_old = client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={"email": "changer@example.com", "password": old_password},
    )
    assert login_old.status_code == 401

    # New password succeeds
    login_new = client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={"email": "changer@example.com", "password": new_password},
    )
    assert login_new.status_code == 200


def test_change_password_wrong_current(client: TestClient, db_session: Session) -> None:
    """Test changing password failure with wrong current password."""
    user = User(
        business_id=None,
        full_name="Test User",
        email="wrongpass@example.com",
        password_hash=get_password_hash("RealPassword123!"),
        role=UserRole.STAFF.value,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    token = create_access_token(subject=user.id, role=user.role)

    response = client.post(
        f"{settings.API_V1_STR}/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "WrongPassword123!",
            "new_password": "AnotherPassword123!",
            "confirm_new_password": "AnotherPassword123!",
        },
    )
    assert response.status_code == 400
    assert "incorrect current password" in response.json()["detail"].lower()


def test_expired_jwt_token_rejected(client: TestClient) -> None:
    """Test that expired JWT access tokens return 401 Unauthorized."""
    expired_token = create_access_token(
        subject=999,
        expires_delta=timedelta(seconds=-10),  # expired 10 seconds ago
    )

    response = client.get(
        f"{settings.API_V1_STR}/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


def test_malformed_jwt_token_rejected(client: TestClient) -> None:
    """Test that invalid tokens return 401 Unauthorized."""
    response = client.get(
        f"{settings.API_V1_STR}/auth/me",
        headers={"Authorization": "Bearer invalid_gibberish_token"},
    )
    assert response.status_code == 401
    assert "could not validate credentials" in response.json()["detail"].lower()
