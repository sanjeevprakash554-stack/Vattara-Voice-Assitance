"""Comprehensive Phase 7 automated tests for SaaS dashboard, multi-tenancy, and RBAC.

Covers:
- Super Admin clearance and access control (403 for ordinary admins)
- Platform KPIs and cross-tenant overview
- Business status activation/suspension toggles
- Subscription tiers, plan changes, and quota tracking
- Staff member management and plan quota limit enforcement
- Telephony integrations configuration with masked secrets and trunk ping testing
- Enriched dashboard statistics and reporting analytics
- Multi-report CSV exports
- Strict multi-tenant data isolation
"""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.core.security import create_access_token, get_password_hash
from app.models.business import Business
from app.models.integration import BusinessIntegration
from app.models.subscription import Invoice, Subscription
from app.models.user import User


@pytest.fixture
def super_admin_headers() -> dict[str, str]:
    """Provide authorization header for platform super administrator."""
    token = create_access_token(
        subject="demo-user-superadmin",
        extra_claims={"business_id": "demo-biz-vattara-health", "role": "super_admin"},
    )
    return {"Authorization": f"Bearer {token}"}


def test_super_admin_access_allowed(client: TestClient, super_admin_headers: dict[str, str]):
    """Super admin can access platform stats and all tenant records."""
    # 1. Platform stats
    stats_resp = client.get("/api/v1/super-admin/stats", headers=super_admin_headers)
    assert stats_resp.status_code == 200
    data = stats_resp.json()
    assert "total_businesses" in data
    assert "active_businesses" in data
    assert "total_users" in data
    assert "total_calls" in data
    assert "total_appointments" in data
    assert "plans_breakdown" in data
    assert data["total_businesses"] >= 1

    # 2. Businesses list
    biz_resp = client.get("/api/v1/super-admin/businesses", headers=super_admin_headers)
    assert biz_resp.status_code == 200
    biz_list = biz_resp.json()
    assert isinstance(biz_list, list)
    assert len(biz_list) >= 1
    assert any(b["id"] == "demo-biz-vattara-health" for b in biz_list)


def test_super_admin_access_forbidden_for_regular_admin(client: TestClient, auth_headers: dict[str, str]):
    """Regular business admin cannot access platform administration endpoints (403 Forbidden)."""
    stats_resp = client.get("/api/v1/super-admin/stats", headers=auth_headers)
    assert stats_resp.status_code == 403
    assert "super" in stats_resp.json().get("detail", "").lower()

    biz_resp = client.get("/api/v1/super-admin/businesses", headers=auth_headers)
    assert biz_resp.status_code == 403


def test_super_admin_toggle_business_status(client: TestClient, super_admin_headers: dict[str, str]):
    """Super admin can toggle tenant active/suspended status."""
    # Toggle to suspended
    resp1 = client.post(
        "/api/v1/super-admin/businesses/demo-biz-vattara-health/toggle-status",
        headers=super_admin_headers,
    )
    assert resp1.status_code == 200
    assert resp1.json()["is_active"] is False

    # Toggle back to active
    resp2 = client.post(
        "/api/v1/super-admin/businesses/demo-biz-vattara-health/toggle-status",
        headers=super_admin_headers,
    )
    assert resp2.status_code == 200
    assert resp2.json()["is_active"] is True


def test_super_admin_update_subscription(client: TestClient, super_admin_headers: dict[str, str]):
    """Super admin can override a tenant's subscription tier."""
    resp = client.put(
        "/api/v1/super-admin/businesses/demo-biz-vattara-health/subscription",
        headers=super_admin_headers,
        json={"plan_name": "enterprise", "status": "active", "monthly_call_minutes_limit": 10000},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["plan_name"] == "enterprise"


def test_subscriptions_api(client: TestClient, auth_headers: dict[str, str]):
    """Tenant admin can query current subscription, inspect available plans, and switch tiers."""
    # 1. Current subscription
    curr_resp = client.get("/api/v1/subscriptions/current", headers=auth_headers)
    assert curr_resp.status_code == 200
    curr = curr_resp.json()
    assert curr["plan_name"] in ["starter", "professional", "enterprise"]
    assert curr["max_staff"] >= 2
    assert "used_call_minutes" in curr

    # 2. Available plans catalog
    plans_resp = client.get("/api/v1/subscriptions/plans", headers=auth_headers)
    assert plans_resp.status_code == 200
    plans = plans_resp.json()
    assert len(plans) == 3
    plan_ids = [p["id"] for p in plans]
    assert "starter" in plan_ids
    assert "professional" in plan_ids
    assert "enterprise" in plan_ids

    # 3. Change plan to starter
    change_resp = client.post(
        "/api/v1/subscriptions/change-plan",
        headers=auth_headers,
        json={"plan_name": "starter", "billing_cycle": "monthly"},
    )
    assert change_resp.status_code == 200
    assert change_resp.json()["plan_name"] == "starter"
    assert change_resp.json()["max_staff"] == 3

    # 4. Invoices ledger - newly generated invoice is pending until gateway confirmation
    inv_resp = client.get("/api/v1/subscriptions/invoices", headers=auth_headers)
    assert inv_resp.status_code == 200
    inv_list = inv_resp.json()
    assert isinstance(inv_list, list)
    assert len(inv_list) >= 1
    assert inv_list[0]["status"] == "pending"

    # 5. Confirm payment for the pending invoice
    confirm_resp = client.post(
        f"/api/v1/subscriptions/invoices/{inv_list[0]['id']}/confirm-payment",
        headers=auth_headers,
        json={"payment_id": "pay_test_gateway_123", "payment_method": "upi"},
    )
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["status"] == "paid"
    assert confirm_resp.json()["paid_at"] is not None


def test_staff_management_crud(client: TestClient, auth_headers: dict[str, str]):
    """Tenant admin can manage clinical and administrative staff members."""
    # First, switch to professional tier to have adequate staff quota
    client.post(
        "/api/v1/subscriptions/change-plan",
        headers=auth_headers,
        json={"plan_name": "professional", "billing_cycle": "monthly"},
    )

    # 1. List staff
    initial_resp = client.get("/api/v1/staff", headers=auth_headers)
    assert initial_resp.status_code == 200
    initial_count = len(initial_resp.json())

    # 2. Create doctor
    create_resp = client.post(
        "/api/v1/staff",
        headers=auth_headers,
        json={
            "full_name": "Dr. Anirudh Sharma",
            "email": "anirudh.sharma@vattara.com",
            "password": "SecurePassword@123",
            "role": "doctor",
        },
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["full_name"] == "Dr. Anirudh Sharma"
    assert created["role"] == "doctor"
    staff_id = created["id"]

    # 3. Update staff member
    update_resp = client.put(
        f"/api/v1/staff/{staff_id}",
        headers=auth_headers,
        json={"full_name": "Dr. Anirudh Sharma, MD", "role": "doctor"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["full_name"] == "Dr. Anirudh Sharma, MD"

    # 4. Delete staff member
    del_resp = client.delete(f"/api/v1/staff/{staff_id}", headers=auth_headers)
    assert del_resp.status_code == 204

    # 5. Verify deletion
    final_resp = client.get("/api/v1/staff", headers=auth_headers)
    assert len(final_resp.json()) == initial_count


def test_staff_quota_enforcement(client: TestClient, auth_headers: dict[str, str]):
    """Adding staff beyond subscription tier limits raises HTTP 403 Forbidden."""
    # Set to starter plan (max_staff = 3)
    change_resp = client.post(
        "/api/v1/subscriptions/change-plan",
        headers=auth_headers,
        json={"plan_name": "starter", "billing_cycle": "monthly"},
    )
    assert change_resp.status_code == 200
    assert change_resp.json()["max_staff"] == 3

    # Ensure there are 3 staff members
    staff_list = client.get("/api/v1/staff", headers=auth_headers).json()
    while len(staff_list) < 3:
        idx = len(staff_list) + 1
        res = client.post(
            "/api/v1/staff",
            headers=auth_headers,
            json={
                "full_name": f"Staff Member {idx}",
                "email": f"staff{idx}_{idx}@vattara.com",
                "password": "Password@123",
                "role": "staff",
            },
        )
        assert res.status_code == 201
        staff_list = client.get("/api/v1/staff", headers=auth_headers).json()

    # Attempt to add a 4th member (should be rejected as quota exceeded)
    excess_resp = client.post(
        "/api/v1/staff",
        headers=auth_headers,
        json={
            "full_name": "Excess Staff Member",
            "email": "excess@vattara.com",
            "password": "Password@123",
            "role": "receptionist",
        },
    )
    assert excess_resp.status_code in [400, 403]
    assert "limit reached" in excess_resp.json().get("detail", "").lower()


def test_telephony_integrations_and_masking(client: TestClient, auth_headers: dict[str, str]):
    """Telephony settings mask raw credentials and support connection health checks."""
    # 1. Update settings with raw tokens
    put_resp = client.put(
        "/api/v1/integrations/settings",
        headers=auth_headers,
        json={
            "primary_provider": "smartflo",
            "twilio_account_sid": "ACmock_saas_twilio_sid_12345",
            "twilio_phone_number": "+14155552671",
            "smartflo_caller_id": "918040009999",
            "smartflo_api_key": "tsf_secret_token_live_key_9999",
            "exotel_caller_id": "08088887777",
        },
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["primary_provider"] == "smartflo"

    # 2. Get settings: tokens MUST be masked
    get_resp = client.get("/api/v1/integrations/settings", headers=auth_headers)
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["primary_provider"] == "smartflo"
    assert "••••" in data["twilio_account_sid_masked"]
    assert "••••" in data["smartflo_api_key_masked"]
    # Raw token never returned
    assert data["twilio_account_sid_masked"] != "ACmock_saas_twilio_sid_12345"
    assert data["smartflo_api_key_masked"] != "tsf_secret_token_live_key_9999"

    # 3. Test connectivity for each provider
    for prov in ["twilio", "smartflo", "exotel"]:
        test_resp = client.post(
            "/api/v1/integrations/test-connection",
            headers=auth_headers,
            json={"provider": prov},
        )
        assert test_resp.status_code == 200
        tdata = test_resp.json()
        assert tdata["provider"] == prov
        assert tdata["is_connected"] is True
        assert tdata["latency_ms"] > 0


def test_enriched_dashboard_stats(client: TestClient, auth_headers: dict[str, str]):
    """Dashboard KPIs provide real aggregated metrics for answered calls and appointments."""
    resp = client.get("/api/v1/dashboard/stats", headers=auth_headers)
    assert resp.status_code == 200
    stats = resp.json()
    assert "total_calls" in stats
    assert "answered_calls" in stats
    assert "missed_calls" in stats
    assert "call_success_rate" in stats
    assert "total_appointments" in stats
    assert "upcoming_appointments_count" in stats
    assert "completed_appointments_count" in stats
    assert "cancelled_appointments_count" in stats
    assert "total_reminders" in stats
    assert "sent_reminders" in stats


def test_reports_analytics_and_csv_export(client: TestClient, auth_headers: dict[str, str]):
    """Reports summary provides distributions and CSV exports."""
    # 1. Summary analytics
    summary_resp = client.get("/api/v1/reports/summary?range_type=30d", headers=auth_headers)
    assert summary_resp.status_code == 200
    sdata = summary_resp.json()
    assert "metrics" in sdata
    assert "duration_distribution" in sdata
    assert "provider_breakdown" in sdata
    assert "reminder_delivery" in sdata
    assert "timeline" in sdata

    # 2. CSV Exports
    for rtype in ["calls", "appointments", "reminders"]:
        csv_resp = client.get(f"/api/v1/reports/export-csv?report_type={rtype}", headers=auth_headers)
        assert csv_resp.status_code == 200
        assert "text/csv" in csv_resp.headers.get("content-type", "")
        assert "attachment" in csv_resp.headers.get("content-disposition", "")
        assert len(csv_resp.text) > 0


def test_multi_tenant_data_isolation(client: TestClient, db_session: Session):
    """Different tenants are strictly isolated across staff, subscriptions, and integrations."""
    # Create Tenant 2
    biz2 = Business(
        id="biz-tenant-2-apollo",
        name="Apollo Specialty Dental",
        vertical="dental",
        phone="+91 44 4949 1111",
        email="contact@apollodental.com",
        timezone="Asia/Kolkata",
        address="100, Mount Road, Chennai",
        is_active=True,
    )
    db_session.add(biz2)

    user2 = User(
        id="user-tenant-2-admin",
        business_id=biz2.id,
        email="admin@apollodental.com",
        full_name="Dr. Harish Dental",
        hashed_password=get_password_hash("Dental@123"),
        role="admin",
        is_active=True,
    )
    db_session.add(user2)

    sub2 = Subscription(
        id="sub-tenant-2",
        business_id=biz2.id,
        plan_name="enterprise",
        status="active",
        max_staff=50,
        monthly_call_minutes_limit=10000,
    )
    db_session.add(sub2)

    now = datetime.now(timezone.utc)
    inv2 = Invoice(
        id="inv-tenant-2",
        business_id=biz2.id,
        subscription_id=sub2.id,
        invoice_number="INV-DENTAL-001",
        amount=18999.0,
        currency="INR",
        status="paid",
        billing_date=now,
    )
    db_session.add(inv2)

    integ2 = BusinessIntegration(
        id="integ-tenant-2",
        business_id=biz2.id,
        primary_provider="smartflo",
        smartflo_caller_id="918049990000",
        smartflo_api_key="tsf_apollo_key_999",
    )
    db_session.add(integ2)
    db_session.commit()

    token2 = create_access_token(
        subject="user-tenant-2-admin",
        extra_claims={"business_id": "biz-tenant-2-apollo", "role": "admin"},
    )
    headers2 = {"Authorization": f"Bearer {token2}"}

    # Query Tenant 2 invoices: must only see Tenant 2 invoice
    inv_resp = client.get("/api/v1/subscriptions/invoices", headers=headers2)
    assert inv_resp.status_code == 200
    invoices = inv_resp.json()
    assert len(invoices) == 1
    assert invoices[0]["invoice_number"] == "INV-DENTAL-001"

    # Query Tenant 2 integrations
    integ_resp = client.get("/api/v1/integrations/settings", headers=headers2)
    assert integ_resp.status_code == 200
    assert integ_resp.json()["primary_provider"] == "smartflo"
    assert integ_resp.json()["smartflo_caller_id"] == "918049990000"

    # Tenant 2 staff query only returns Tenant 2 staff
    staff_resp = client.get("/api/v1/staff", headers=headers2)
    assert staff_resp.status_code == 200
    assert len(staff_resp.json()) == 1
    assert staff_resp.json()[0]["email"] == "admin@apollodental.com"
