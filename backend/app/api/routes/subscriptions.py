"""SaaS Subscription, Plan Tiers, Usage Limits, and Billing Invoices endpoints."""

import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db_session
from app.core.logging import get_logger
from app.models.business import Business
from app.models.subscription import Invoice, Subscription
from app.models.user import User
from app.schemas.subscription import (
    ChangePlanRequest,
    ConfirmPaymentRequest,
    InvoiceResponse,
    SubscriptionPlan,
    SubscriptionResponse,
)

logger = get_logger(__name__)
router = APIRouter()

# Static SaaS Plan Catalog
SAAS_PLANS = [
    SubscriptionPlan(
        id="starter",
        name="Starter Voice",
        tagline="Essential AI receptionist for solo clinics & boutique practices",
        monthly_price=1999.0,
        annual_price=19990.0,
        monthly_minutes=500,
        max_assistants=1,
        max_staff=3,
        is_popular=False,
        features=[
            "500 Outbound & Inbound AI Voice Minutes",
            "1 Active Voice Assistant",
            "Multi-lingual Tamil, English & Tanglish",
            "Standard Appointment Scheduling",
            "SMS & WhatsApp Follow-ups",
            "Up to 3 Staff User Accounts",
            "Community & Email Support",
        ],
    ),
    SubscriptionPlan(
        id="professional",
        name="Professional Suite",
        tagline="Comprehensive conversational intelligence for growing clinics & hospitals",
        monthly_price=4999.0,
        annual_price=49990.0,
        monthly_minutes=1500,
        max_assistants=3,
        max_staff=10,
        is_popular=True,
        features=[
            "1,500 Outbound & Inbound AI Voice Minutes",
            "3 Active AI Voice Assistants with Custom Personas",
            "Real-time WebSocket Bidirectional Audio Streaming",
            "Doctor Shift & Break Scheduling Engine",
            "Automated 24h & 2h AI Voice Reminder Calling",
            "Twilio & Tata Smartflo Telephony Integration",
            "Up to 10 Staff & Doctor User Accounts",
            "Priority Telephony Support (99.9% SLA)",
        ],
    ),
    SubscriptionPlan(
        id="enterprise",
        name="Enterprise Hospital",
        tagline="High-throughput voice infrastructure with custom telephony & EHR sync",
        monthly_price=12999.0,
        annual_price=129990.0,
        monthly_minutes=5000,
        max_assistants=10,
        max_staff=50,
        is_popular=False,
        features=[
            "5,000 Outbound & Inbound AI Voice Minutes",
            "Unlimited Concurrent Call Handling",
            "Dedicated SIP Trunking & Carrier DID Mapping",
            "Custom LLM Fine-tuning & Doctor Catalog Sync",
            "Multi-branch / Multi-location Architecture",
            "Unlimited Staff Accounts & Role Permissions",
            "HIPAA & Healthcare Data Compliance",
            "24/7 Dedicated Technical Account Manager",
        ],
    ),
]


def get_or_create_subscription(db: Session, business_id: str) -> Subscription:
    """Resolve active subscription for tenant or initialize default trial."""
    sub = db.scalar(select(Subscription).where(Subscription.business_id == business_id))
    if not sub:
        now = datetime.now(timezone.utc)
        sub = Subscription(
            business_id=business_id,
            plan_name="professional",
            billing_cycle="monthly",
            status="active",
            trial_ends_at=now + timedelta(days=14),
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            monthly_call_minutes_limit=1500,
            used_call_minutes=340,
            max_assistants=3,
            max_staff=10,
        )
        db.add(sub)
        db.commit()
        db.refresh(sub)
    return sub


@router.get("/current", response_model=SubscriptionResponse)
def get_current_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> SubscriptionResponse:
    """Retrieve active subscription tier, call-minute consumption, and quotas for authenticated tenant."""
    sub = get_or_create_subscription(db, current_user.business_id)
    return SubscriptionResponse.model_validate(sub)


@router.get("/plans", response_model=list[SubscriptionPlan])
def list_subscription_plans() -> list[SubscriptionPlan]:
    """Retrieve public SaaS subscription plan catalog and feature comparisons."""
    return SAAS_PLANS


@router.post("/change-plan", response_model=SubscriptionResponse)
def change_subscription_plan(
    payload: ChangePlanRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> SubscriptionResponse:
    """Upgrade or downgrade tenant subscription plan tier and billing cycle."""
    sub = get_or_create_subscription(db, current_user.business_id)
    target_plan = next((p for p in SAAS_PLANS if p.id == payload.plan_name.lower().strip()), None)

    if not target_plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid subscription plan '{payload.plan_name}'. Must be one of: starter, professional, enterprise.",
        )

    now = datetime.now(timezone.utc)
    sub.plan_name = target_plan.id
    sub.billing_cycle = payload.billing_cycle.lower().strip()
    sub.monthly_call_minutes_limit = target_plan.monthly_minutes
    sub.max_assistants = target_plan.max_assistants
    sub.max_staff = target_plan.max_staff
    sub.status = "active"
    sub.current_period_start = now
    sub.current_period_end = now + timedelta(days=365 if sub.billing_cycle == "annual" else 30)

    # Generate an invoice ledger record for the plan change (Pending payment confirmation)
    amount = target_plan.annual_price if sub.billing_cycle == "annual" else target_plan.monthly_price
    invoice = Invoice(
        business_id=current_user.business_id,
        subscription_id=sub.id,
        invoice_number=f"INV-{now.strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}",
        amount=amount,
        currency="INR",
        status="pending",
        billing_date=now,
        paid_at=None,
    )
    db.add(invoice)

    db.commit()
    db.refresh(sub)

    logger.info(
        "Tenant %s requested plan change to %s (%s) - Invoice %s generated (pending payment)",
        current_user.business_id,
        sub.plan_name,
        sub.billing_cycle,
        invoice.invoice_number,
    )
    return SubscriptionResponse.model_validate(sub)


@router.get("/invoices", response_model=list[InvoiceResponse])
def list_invoices(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[InvoiceResponse]:
    """Retrieve billing ledger history and payment statements for the authenticated tenant."""
    sub = get_or_create_subscription(db, current_user.business_id)
    invoices = db.scalars(
        select(Invoice)
        .where(Invoice.business_id == current_user.business_id)
        .order_by(Invoice.billing_date.desc())
    ).all()
    return [InvoiceResponse.model_validate(inv) for inv in invoices]


@router.post("/invoices/{invoice_id}/confirm-payment", response_model=InvoiceResponse)
def confirm_invoice_payment(
    invoice_id: str,
    payload: ConfirmPaymentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> InvoiceResponse:
    """Verify and transition invoice status to paid upon payment gateway confirmation."""
    invoice = db.scalar(
        select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.business_id == current_user.business_id,
        )
    )
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found or access unauthorized.",
        )

    if invoice.status == "paid":
        return InvoiceResponse.model_validate(invoice)

    now = datetime.now(timezone.utc)
    invoice.status = "paid"
    invoice.paid_at = now
    db.commit()
    db.refresh(invoice)

    logger.info(
        "Invoice %s (%s) confirmed paid via %s (ref: %s)",
        invoice.invoice_number,
        invoice.id,
        payload.payment_method,
        payload.payment_id,
    )
    return InvoiceResponse.model_validate(invoice)
