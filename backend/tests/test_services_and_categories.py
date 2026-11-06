"""Automated tests for Service Categories and Business Services."""

from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.models.business import Business
from app.models.business_service import BusinessService
from app.models.service_category import ServiceCategory
from app.models.user import User, UserRole


@pytest.fixture
def two_businesses(db_session: Session) -> dict:
    """Fixture creating two separate businesses with admins and staff for multi-tenant tests."""
    # Business 1: Salon
    biz1 = Business(
        business_name="Luxe Salon & Spa",
        business_type="salon",
        email="contact@luxesalon.com",
        phone_number="+1-555-1111",
        timezone="America/New_York",
        is_active=True,
    )
    # Business 2: Auto Center
    biz2 = Business(
        business_name="Apex Auto Service",
        business_type="automobile",
        email="contact@apexauto.com",
        phone_number="+1-555-2222",
        timezone="America/Chicago",
        is_active=True,
    )
    db_session.add_all([biz1, biz2])
    db_session.flush()

    admin1 = User(
        business_id=biz1.id,
        full_name="Salon Owner",
        email="owner@luxesalon.com",
        password_hash=get_password_hash("AdminPass123!"),
        role=UserRole.BUSINESS_ADMIN.value,
        is_active=True,
    )
    staff1 = User(
        business_id=biz1.id,
        full_name="Salon Stylist",
        email="stylist@luxesalon.com",
        password_hash=get_password_hash("StaffPass123!"),
        role=UserRole.STAFF.value,
        is_active=True,
    )

    admin2 = User(
        business_id=biz2.id,
        full_name="Auto Manager",
        email="manager@apexauto.com",
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
# CATEGORY TESTS
# ==============================================================================

def test_create_category_success(client: TestClient, two_businesses: dict) -> None:
    """Test creating a service category as Business Admin."""
    token = two_businesses["b1_admin_token"]
    payload = {
        "category_name": "Hair Care",
        "description": "Hair cuts, coloring, and treatments",
    }
    response = client.post(
        f"{settings.API_V1_STR}/business/categories",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["category_name"] == "Hair Care"
    assert data["description"] == payload["description"]
    assert data["is_active"] is True
    assert data["id"] is not None


def test_create_category_duplicate_rejected(client: TestClient, two_businesses: dict) -> None:
    """Test creating duplicate category with same name in same tenant is rejected with 400."""
    token = two_businesses["b1_admin_token"]
    payload = {"category_name": "Nail Services"}
    res1 = client.post(
        f"{settings.API_V1_STR}/business/categories",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res1.status_code == 201

    # Try duplicate with different casing/trailing spaces
    res2 = client.post(
        f"{settings.API_V1_STR}/business/categories",
        json={"category_name": "  nail services  "},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"]


def test_create_category_staff_forbidden(client: TestClient, two_businesses: dict) -> None:
    """Test staff cannot create a category (requires Admin)."""
    token = two_businesses["b1_staff_token"]
    response = client.post(
        f"{settings.API_V1_STR}/business/categories",
        json={"category_name": "Skincare"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_list_and_get_category(client: TestClient, two_businesses: dict, db_session: Session) -> None:
    """Test listing categories and retrieving a single category."""
    b1 = two_businesses["b1"]
    cat1 = ServiceCategory(business_id=b1.id, category_name="Massage", is_active=True)
    cat2 = ServiceCategory(business_id=b1.id, category_name="Archived Service", is_active=False)
    db_session.add_all([cat1, cat2])
    db_session.commit()

    token = two_businesses["b1_admin_token"]

    # List all
    res = client.get(
        f"{settings.API_V1_STR}/business/categories",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    names = [c["category_name"] for c in res.json()]
    assert "Massage" in names
    assert "Archived Service" in names

    # Filter active only
    res_active = client.get(
        f"{settings.API_V1_STR}/business/categories?is_active=true",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_active.status_code == 200
    active_names = [c["category_name"] for c in res_active.json()]
    assert "Massage" in active_names
    assert "Archived Service" not in active_names

    # Get single category
    res_single = client.get(
        f"{settings.API_V1_STR}/business/categories/{cat1.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_single.status_code == 200
    assert res_single.json()["category_name"] == "Massage"


def test_cross_tenant_category_isolation(client: TestClient, two_businesses: dict, db_session: Session) -> None:
    """Test Business 2 admin cannot access or update Business 1's category (404 Not Found)."""
    b1 = two_businesses["b1"]
    cat = ServiceCategory(business_id=b1.id, category_name="Private B1 Category", is_active=True)
    db_session.add(cat)
    db_session.commit()

    token_b2 = two_businesses["b2_admin_token"]

    # B2 tries to retrieve B1 category -> 404
    res = client.get(
        f"{settings.API_V1_STR}/business/categories/{cat.id}",
        headers={"Authorization": f"Bearer {token_b2}"},
    )
    assert res.status_code == 404

    # B2 tries to update B1 category -> 404
    res_update = client.put(
        f"{settings.API_V1_STR}/business/categories/{cat.id}",
        json={"category_name": "Hacked Name"},
        headers={"Authorization": f"Bearer {token_b2}"},
    )
    assert res_update.status_code == 404


def test_update_and_delete_category(client: TestClient, two_businesses: dict, db_session: Session) -> None:
    """Test updating and soft-deactivating a category."""
    b1 = two_businesses["b1"]
    cat = ServiceCategory(business_id=b1.id, category_name="Facial Care", is_active=True)
    db_session.add(cat)
    db_session.commit()

    token = two_businesses["b1_admin_token"]

    # Update category
    res_update = client.put(
        f"{settings.API_V1_STR}/business/categories/{cat.id}",
        json={"category_name": "Advanced Facial Care", "description": "Organic facials"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_update.status_code == 200
    assert res_update.json()["category_name"] == "Advanced Facial Care"
    assert res_update.json()["description"] == "Organic facials"

    # Soft delete (deactivate)
    res_del = client.delete(
        f"{settings.API_V1_STR}/business/categories/{cat.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_del.status_code == 200
    assert "deactivated" in res_del.json()["message"]

    db_session.refresh(cat)
    assert cat.is_active is False


# ==============================================================================
# SERVICE TESTS
# ==============================================================================

def test_create_service_with_category(client: TestClient, two_businesses: dict, db_session: Session) -> None:
    """Test creating a business service with a valid category."""
    b1 = two_businesses["b1"]
    cat = ServiceCategory(business_id=b1.id, category_name="Styling", is_active=True)
    db_session.add(cat)
    db_session.commit()

    token = two_businesses["b1_admin_token"]
    payload = {
        "service_name": "Premium Haircut",
        "category_id": cat.id,
        "description": "Wash, cut, and blow dry",
        "duration_minutes": 45,
        "price": 50.00,
        "currency": "USD",
    }
    response = client.post(
        f"{settings.API_V1_STR}/business/services",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["service_name"] == "Premium Haircut"
    assert data["category_name"] == "Styling"
    assert data["duration_minutes"] == 45
    assert float(data["price"]) == 50.00
    assert data["currency"] == "USD"
    assert data["is_active"] is True


def test_create_service_foreign_category_rejected(client: TestClient, two_businesses: dict, db_session: Session) -> None:
    """Test creating a service referencing a category from another business is rejected (400)."""
    b2 = two_businesses["b2"]
    cat_b2 = ServiceCategory(business_id=b2.id, category_name="B2 Auto Category", is_active=True)
    db_session.add(cat_b2)
    db_session.commit()

    token_b1 = two_businesses["b1_admin_token"]
    payload = {
        "service_name": "Invalid Category Service",
        "category_id": cat_b2.id,
        "duration_minutes": 30,
        "price": 30.00,
    }
    response = client.post(
        f"{settings.API_V1_STR}/business/services",
        json=payload,
        headers={"Authorization": f"Bearer {token_b1}"},
    )
    assert response.status_code == 400
    assert "does not belong to your business" in response.json()["detail"]


def test_create_service_duplicate_name_rejected(client: TestClient, two_businesses: dict) -> None:
    """Test duplicate active service name in same business is rejected (400)."""
    token = two_businesses["b1_admin_token"]
    payload = {
        "service_name": "Manicure",
        "duration_minutes": 30,
        "price": 25.00,
    }
    res1 = client.post(
        f"{settings.API_V1_STR}/business/services",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res1.status_code == 201

    res2 = client.post(
        f"{settings.API_V1_STR}/business/services",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"]


def test_service_validation_rules(client: TestClient, two_businesses: dict) -> None:
    """Test price and duration validation constraints."""
    token = two_businesses["b1_admin_token"]

    # Negative price rejected
    res = client.post(
        f"{settings.API_V1_STR}/business/services",
        json={"service_name": "Free Service", "duration_minutes": 30, "price": -5.00},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422

    # Zero duration rejected
    res_dur = client.post(
        f"{settings.API_V1_STR}/business/services",
        json={"service_name": "Instant Service", "duration_minutes": 0, "price": 10.00},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_dur.status_code == 422


def test_list_services_search_and_filter(client: TestClient, two_businesses: dict, db_session: Session) -> None:
    """Test searching services by name/description, filtering by category, and pagination."""
    b1 = two_businesses["b1"]
    cat1 = ServiceCategory(business_id=b1.id, category_name="Hair", is_active=True)
    cat2 = ServiceCategory(business_id=b1.id, category_name="Spa", is_active=True)
    db_session.add_all([cat1, cat2])
    db_session.flush()

    s1 = BusinessService(
        business_id=b1.id,
        category_id=cat1.id,
        service_name="Beard Grooming",
        description="Hot towel and trim",
        duration_minutes=30,
        price=Decimal("35.00"),
        is_active=True,
    )
    s2 = BusinessService(
        business_id=b1.id,
        category_id=cat2.id,
        service_name="Aromatherapy Massage",
        description="Relaxing essential oils",
        duration_minutes=60,
        price=Decimal("90.00"),
        is_active=True,
    )
    s3 = BusinessService(
        business_id=b1.id,
        category_id=cat1.id,
        service_name="Old Haircut",
        duration_minutes=20,
        price=Decimal("15.00"),
        is_active=False,
    )
    db_session.add_all([s1, s2, s3])
    db_session.commit()

    token = two_businesses["b1_admin_token"]

    # Search by text "towel" in description
    res_search = client.get(
        f"{settings.API_V1_STR}/business/services?search=towel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_search.status_code == 200
    data = res_search.json()
    assert len(data) == 1
    assert data[0]["service_name"] == "Beard Grooming"

    # Filter by category
    res_cat = client.get(
        f"{settings.API_V1_STR}/business/services?category_id={cat2.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_cat.status_code == 200
    assert len(res_cat.json()) == 1
    assert res_cat.json()[0]["service_name"] == "Aromatherapy Massage"

    # Filter by active only
    res_active = client.get(
        f"{settings.API_V1_STR}/business/services?is_active=true",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_active.status_code == 200
    names = [s["service_name"] for s in res_active.json()]
    assert "Beard Grooming" in names
    assert "Aromatherapy Massage" in names
    assert "Old Haircut" not in names


def test_cross_tenant_service_isolation(client: TestClient, two_businesses: dict, db_session: Session) -> None:
    """Test Business 2 cannot view or update Business 1's services (404)."""
    b1 = two_businesses["b1"]
    srv = BusinessService(
        business_id=b1.id,
        service_name="VIP Executive Haircut",
        duration_minutes=45,
        price=Decimal("100.00"),
        is_active=True,
    )
    db_session.add(srv)
    db_session.commit()

    token_b2 = two_businesses["b2_admin_token"]

    # B2 attempts to view B1 service -> 404
    res = client.get(
        f"{settings.API_V1_STR}/business/services/{srv.id}",
        headers={"Authorization": f"Bearer {token_b2}"},
    )
    assert res.status_code == 404

    # B2 attempts to update B1 service -> 404
    res_update = client.put(
        f"{settings.API_V1_STR}/business/services/{srv.id}",
        json={"price": 10.00},
        headers={"Authorization": f"Bearer {token_b2}"},
    )
    assert res_update.status_code == 404


def test_update_and_delete_service(client: TestClient, two_businesses: dict, db_session: Session) -> None:
    """Test updating service attributes and soft-deleting a service."""
    b1 = two_businesses["b1"]
    srv = BusinessService(
        business_id=b1.id,
        service_name="Express Trim",
        duration_minutes=20,
        price=Decimal("20.00"),
        is_active=True,
    )
    db_session.add(srv)
    db_session.commit()

    token = two_businesses["b1_admin_token"]

    # Update service
    res_update = client.put(
        f"{settings.API_V1_STR}/business/services/{srv.id}",
        json={"price": 25.00, "duration_minutes": 25, "service_name": "Express Trim Deluxe"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_update.status_code == 200
    assert float(res_update.json()["price"]) == 25.00
    assert res_update.json()["duration_minutes"] == 25
    assert res_update.json()["service_name"] == "Express Trim Deluxe"

    # Soft delete service
    res_del = client.delete(
        f"{settings.API_V1_STR}/business/services/{srv.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_del.status_code == 200
    assert "deactivated" in res_del.json()["message"]

    db_session.refresh(srv)
    assert srv.is_active is False
