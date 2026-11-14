"""Platform-Level Super Administrator management endpoints.

Provides multi-tenant administration, cross-business telemetry, subscription oversight,
and business tenant lifecycle activation/suspension. Enforces strict super_admin RBAC.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_super_admin, get_db_session
from app.core.logging import get_logger
from app.models.appointment import Appointment
from app.models.business import Business
from app.models.call import Call
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.super_admin import PlatformStats, TenantOverview, UpdateTenantSubscription

logger = get_logger(__name__)
router = APIRouter()


@router.get("/stats", response_model=PlatformStats)
def get_platform_stats(
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db_session),
) -> PlatformStats:
    """Retrieve global platform analytics and cross-tenant SaaS metrics."""
    total_biz = db.scalar(select(func.count(Business.id))) or 0
    active_biz = db.scalar(select(func.count(Business.id)).where(Business.is_active.is_(True))) or 0
    inactive_biz = total_biz - active_biz

    total_users = db.scalar(select(func.count(User.id))) or 0
    total_calls = db.scalar(select(func.count(Call.id))) or 0
    total_appts = db.scalar(select(func.count(Appointment.id))) or 0

    active_subs = (
        db.scalar(select(func.count(Subscription.id)).where(Subscription.status == "active")) or 0
    )
    trial_subs = (
        db.scalar(select(func.count(Subscription.id)).where(Subscription.status == "trial")) or 0
    )

    total_mins = db.scalar(select(func.sum(Subscription.used_call_minutes))) or 0

    # Plans breakdown
    plans_counts = {"starter": 0, "professional": 0, "enterprise": 0}
    plan_rows = db.execute(
        select(Subscription.plan_name, func.count(Subscription.id)).group_by(Subscription.plan_name)
    ).all()
    for row in plan_rows:
        plans_counts[row[0].lower()] = row[1]

    return PlatformStats(
        total_businesses=total_biz,
        active_businesses=active_biz,
        inactive_businesses=inactive_biz,
        total_users=total_users,
        total_calls=total_calls,
        total_appointments=total_appts,
        active_subscriptions=active_subs,
        trial_subscriptions=trial_subs,
        plans_breakdown=plans_counts,
        total_minutes_consumed=int(total_mins),
    )


@router.get("/businesses", response_model=list[TenantOverview])
def list_tenants(
    search: str | None = Query(None, description="Search by business name or email"),
    status_filter: str | None = Query(None, alias="status", description="active or inactive"),
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db_session),
) -> list[TenantOverview]:
    """List all registered business tenants with aggregated activity and subscription status."""
    stmt = select(Business).order_by(Business.created_at.desc())

    if status_filter == "active":
        stmt = stmt.where(Business.is_active.is_(True))
    elif status_filter == "inactive":
        stmt = stmt.where(Business.is_active.is_(False))

    if search:
        s = f"%{search.strip()}%"
        stmt = stmt.where((Business.name.ilike(s)) | (Business.email.ilike(s)))

    businesses = db.scalars(stmt).all()
    results: list[TenantOverview] = []

    for biz in businesses:
        u_count = db.scalar(select(func.count(User.id)).where(User.business_id == biz.id)) or 0
        c_count = db.scalar(select(func.count(Call.id)).where(Call.business_id == biz.id)) or 0
        a_count = (
            db.scalar(select(func.count(Appointment.id)).where(Appointment.business_id == biz.id)) or 0
        )

        sub = db.scalar(select(Subscription).where(Subscription.business_id == biz.id))

        results.append(
            TenantOverview(
                id=biz.id,
                name=biz.name,
                vertical=biz.vertical,
                phone=biz.phone,
                email=biz.email,
                timezone=biz.timezone,
                is_active=biz.is_active,
                user_count=u_count,
                call_count=c_count,
                appointment_count=a_count,
                plan_name=sub.plan_name if sub else "starter",
                subscription_status=sub.status if sub else ("active" if biz.is_active else "suspended"),
                created_at=biz.created_at,
            )
        )

    return results


@router.post("/businesses/{business_id}/toggle-status", response_model=TenantOverview)
def toggle_tenant_status(
    business_id: str,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db_session),
) -> TenantOverview:
    """Activate or suspend a business tenant organization across the SaaS platform."""
    biz = db.get(Business, business_id)
    if not biz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business tenant not found.")

    biz.is_active = not biz.is_active

    sub = db.scalar(select(Subscription).where(Subscription.business_id == biz.id))
    if sub:
        sub.status = "active" if biz.is_active else "suspended"

    db.commit()
    db.refresh(biz)

    logger.info(
        "SuperAdmin %s toggled tenant '%s' (%s) status to is_active=%s",
        super_admin.email,
        biz.name,
        biz.id,
        biz.is_active,
    )

    u_count = db.scalar(select(func.count(User.id)).where(User.business_id == biz.id)) or 0
    c_count = db.scalar(select(func.count(Call.id)).where(Call.business_id == biz.id)) or 0
    a_count = db.scalar(select(func.count(Appointment.id)).where(Appointment.business_id == biz.id)) or 0

    return TenantOverview(
        id=biz.id,
        name=biz.name,
        vertical=biz.vertical,
        phone=biz.phone,
        email=biz.email,
        timezone=biz.timezone,
        is_active=biz.is_active,
        user_count=u_count,
        call_count=c_count,
        appointment_count=a_count,
        plan_name=sub.plan_name if sub else "starter",
        subscription_status=sub.status if sub else ("active" if biz.is_active else "suspended"),
        created_at=biz.created_at,
    )


@router.put("/businesses/{business_id}/subscription", response_model=TenantOverview)
def update_tenant_subscription_by_admin(
    business_id: str,
    payload: UpdateTenantSubscription,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db_session),
) -> TenantOverview:
    """Super Admin override for tenant subscription plan, quota limits, and billing status."""
    biz = db.get(Business, business_id)
    if not biz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business tenant not found.")

    sub = db.scalar(select(Subscription).where(Subscription.business_id == biz.id))
    if not sub:
        sub = Subscription(
            business_id=biz.id,
            plan_name="starter",
            billing_cycle="monthly",
            status="active",
        )
        db.add(sub)

    if payload.plan_name:
        sub.plan_name = payload.plan_name.lower().strip()
        if sub.plan_name == "starter":
            sub.monthly_call_minutes_limit = 500
        elif sub.plan_name == "professional":
            sub.monthly_call_minutes_limit = 1500
        elif sub.plan_name == "enterprise":
            sub.monthly_call_minutes_limit = 5000

    if payload.status:
        sub.status = payload.status.lower().strip()

    if payload.monthly_call_minutes_limit is not None:
        sub.monthly_call_minutes_limit = payload.monthly_call_minutes_limit

    db.commit()
    db.refresh(biz)

    u_count = db.scalar(select(func.count(User.id)).where(User.business_id == biz.id)) or 0
    c_count = db.scalar(select(func.count(Call.id)).where(Call.business_id == biz.id)) or 0
    a_count = db.scalar(select(func.count(Appointment.id)).where(Appointment.business_id == biz.id)) or 0

    return TenantOverview(
        id=biz.id,
        name=biz.name,
        vertical=biz.vertical,
        phone=biz.phone,
        email=biz.email,
        timezone=biz.timezone,
        is_active=biz.is_active,
        user_count=u_count,
        call_count=c_count,
        appointment_count=a_count,
        plan_name=sub.plan_name,
        subscription_status=sub.status,
        created_at=biz.created_at,
    )
