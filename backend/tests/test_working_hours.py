"""Automated tests for Business Working Hours endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.models.business import Business
from app.models.user import User, UserRole


@pytest.fixture
def business_setup(db_session: Session) -> dict:
    """Fixture creating a business with an admin and staff user."""
    biz = Business(
        business_name="Auto Masters",
        business_type="automobile",
        email="info@automasters.com",
        is_active=True,
    )
    db_session.add(biz)
    db_session.flush()

    admin = User(
        business_id=biz.id,
        full_name="Auto Admin",
        email="admin@automasters.com",
        password_hash=get_password_hash("Pass123!"),
        role=UserRole.BUSINESS_ADMIN.value,
        is_active=True,
    )
    staff = User(
        business_id=biz.id,
        full_name="Auto Tech",
        email="tech@automasters.com",
        password_hash=get_password_hash("Pass123!"),
        role=UserRole.STAFF.value,
        is_active=True,
    )
    db_session.add_all([admin, staff])
    db_session.commit()

    return {
        "business": biz,
        "admin_token": create_access_token(subject=admin.id, business_id=biz.id, role=admin.role),
        "staff_token": create_access_token(subject=staff.id, business_id=biz.id, role=staff.role),
    }


def test_update_and_get_working_hours(client: TestClient, business_setup: dict) -> None:
    """Test creating and retrieving weekly operating schedule."""
    admin_token = business_setup["admin_token"]
    staff_token = business_setup["staff_token"]

    payload = {
        "hours": [
            {"day_of_week": 0, "opening_time": "08:00:00", "closing_time": "17:00:00", "is_closed": False},
            {"day_of_week": 1, "opening_time": "08:00:00", "closing_time": "17:00:00", "is_closed": False},
            {"day_of_week": 2, "opening_time": "08:00:00", "closing_time": "17:00:00", "is_closed": False},
            {"day_of_week": 3, "opening_time": "08:00:00", "closing_time": "17:00:00", "is_closed": False},
            {"day_of_week": 4, "opening_time": "08:00:00", "closing_time": "16:00:00", "is_closed": False},
            {"day_of_week": 5, "opening_time": "09:00:00", "closing_time": "13:00:00", "is_closed": False},
            {"day_of_week": 6, "is_closed": True},  # Sunday closed
        ]
    }

    # Update working hours
    put_resp = client.put(
        f"{settings.API_V1_STR}/business/working-hours",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=payload,
    )
    assert put_resp.status_code == 200
    hours = put_resp.json()
    assert len(hours) == 7

    # Verify Monday
    assert hours[0]["day_name"] == "Monday"
    assert hours[0]["opening_time"] == "08:00:00"
    assert hours[0]["is_closed"] is False

    # Verify Sunday
    assert hours[6]["day_name"] == "Sunday"
    assert hours[6]["is_closed"] is True

    # Retrieve via GET (accessible by staff)
    get_resp = client.get(
        f"{settings.API_V1_STR}/business/working-hours",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert get_resp.status_code == 200
    assert len(get_resp.json()) == 7


def test_working_hours_invalid_time_range(client: TestClient, business_setup: dict) -> None:
    """Test validation rejection when opening time is greater than closing time."""
    admin_token = business_setup["admin_token"]

    payload = {
        "hours": [
            {"day_of_week": 0, "opening_time": "18:00:00", "closing_time": "09:00:00", "is_closed": False}
        ]
    }

    response = client.put(
        f"{settings.API_V1_STR}/business/working-hours",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=payload,
    )
    assert response.status_code == 422
    assert "earlier than closing_time" in str(response.json())


def test_working_hours_duplicate_days_rejected(client: TestClient, business_setup: dict) -> None:
    """Test validation rejection when duplicate days of week are supplied."""
    admin_token = business_setup["admin_token"]

    payload = {
        "hours": [
            {"day_of_week": 1, "opening_time": "09:00:00", "closing_time": "17:00:00", "is_closed": False},
            {"day_of_week": 1, "opening_time": "10:00:00", "closing_time": "18:00:00", "is_closed": False},
        ]
    }

    response = client.put(
        f"{settings.API_V1_STR}/business/working-hours",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=payload,
    )
    assert response.status_code == 422
    assert "duplicate day_of_week" in str(response.json()).lower()


def test_staff_cannot_update_working_hours(client: TestClient, business_setup: dict) -> None:
    """Test that regular staff accounts receive 403 Forbidden when attempting schedule modifications."""
    staff_token = business_setup["staff_token"]

    payload = {
        "hours": [
            {"day_of_week": 0, "is_closed": True}
        ]
    }

    response = client.put(
        f"{settings.API_V1_STR}/business/working-hours",
        headers={"Authorization": f"Bearer {staff_token}"},
        json=payload,
    )
    assert response.status_code == 403
    assert "insufficient permissions" in response.json()["detail"].lower()
