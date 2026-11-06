"""Automated tests for Super Admin platform management endpoints and CLI bootstrap."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.cli import create_super_admin
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.business import Business
from app.models.user import User, UserRole


@pytest.fixture
def super_admin_setup(db_session: Session) -> tuple[User, str]:
    """Fixture creating a platform Super Admin user and generating auth token."""
    super_admin = User(
        business_id=None,
        full_name="Platform Overseer",
        email="root@platform.io",
        password_hash=get_password_hash("SuperSecretPass123!"),
        role=UserRole.SUPER_ADMIN.value,
        is_active=True,
    )
    db_session.add(super_admin)
    db_session.commit()

    token = create_access_token(
        subject=super_admin.id,
        business_id=None,
        role=super_admin.role,
    )
    return super_admin, token


def test_super_admin_list_businesses(client: TestClient, super_admin_setup: tuple, db_session: Session) -> None:
    """Test Super Admin listing registered businesses."""
    _, token = super_admin_setup

    b1 = Business(business_name="Biz One", business_type="hospital", email="b1@hospital.com")
    b2 = Business(business_name="Biz Two", business_type="hotel", email="b2@hotel.com")
    db_session.add_all([b1, b2])
    db_session.commit()

    response = client.get(
        f"{settings.API_V1_STR}/admin/businesses",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    businesses = response.json()
    assert len(businesses) >= 2
    names = [b["business_name"] for b in businesses]
    assert "Biz One" in names
    assert "Biz Two" in names


def test_super_admin_get_business_details(client: TestClient, super_admin_setup: tuple, db_session: Session) -> None:
    """Test Super Admin inspecting business details with aggregate counters."""
    _, token = super_admin_setup

    b = Business(business_name="Audit Clinic", business_type="hospital", email="audit@clinic.com")
    db_session.add(b)
    db_session.commit()

    response = client.get(
        f"{settings.API_V1_STR}/admin/businesses/{b.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["business_name"] == "Audit Clinic"
    assert "users_count" in data
    assert "customers_count" in data
    assert "appointments_count" in data


def test_super_admin_toggle_business_status(client: TestClient, super_admin_setup: tuple, db_session: Session) -> None:
    """Test Super Admin activating/deactivating a business tenant."""
    _, token = super_admin_setup

    b = Business(business_name="Toggle Hotel", business_type="hotel", email="toggle@hotel.com", is_active=True)
    db_session.add(b)
    db_session.commit()

    # Deactivate
    resp_deact = client.patch(
        f"{settings.API_V1_STR}/admin/businesses/{b.id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"is_active": False},
    )
    assert resp_deact.status_code == 200
    assert resp_deact.json()["is_active"] is False

    db_session.refresh(b)
    assert b.is_active is False

    # Reactivate
    resp_react = client.patch(
        f"{settings.API_V1_STR}/admin/businesses/{b.id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"is_active": True},
    )
    assert resp_react.status_code == 200
    assert resp_react.json()["is_active"] is True


def test_non_super_admin_cannot_access_admin_endpoints(client: TestClient, db_session: Session) -> None:
    """Test that Business Admin and Staff users receive 403 Forbidden on admin endpoints."""
    biz = Business(business_name="Regular Biz", business_type="salon", email="reg@biz.com")
    db_session.add(biz)
    db_session.flush()

    biz_admin = User(
        business_id=biz.id,
        full_name="Biz Admin",
        email="admin@regbiz.com",
        password_hash="hash",
        role=UserRole.BUSINESS_ADMIN.value,
        is_active=True,
    )
    db_session.add(biz_admin)
    db_session.commit()

    token = create_access_token(subject=biz_admin.id, business_id=biz.id, role=biz_admin.role)

    response = client.get(
        f"{settings.API_V1_STR}/admin/businesses",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert "insufficient permissions" in response.json()["detail"].lower()


def test_cli_create_super_admin(db_session: Session) -> None:
    """Test the administrative CLI function creates a Super Admin with no business association."""
    email = "bootstrap.admin@voiceplatform.com"
    raw_password = "SuperSecurePassword999!"

    # Run CLI creation function
    create_super_admin(
        email=email,
        full_name="CLI Bootstrap Admin",
        password=raw_password,
        db=db_session,
    )

    created_user = db_session.query(User).filter(User.email == email).first()
    assert created_user is not None
    assert created_user.role == UserRole.SUPER_ADMIN.value
    assert created_user.business_id is None
    assert created_user.is_active is True
    assert verify_password(raw_password, created_user.password_hash) is True
