"""Voice telephony phone resolution and customer management helpers."""

import re
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.logging import get_logger
from app.models.business import Business
from app.models.customer import Customer
from app.services.telephony.phone_utils import clean_phone_digits, normalize_indian_mobile_number
from fastapi import APIRouter

logger = get_logger(__name__)
router = APIRouter()


def clean_phone_digits(phone: str | None) -> str:
    """Strip all non-numeric characters from a phone number for relaxed matching."""
    if not phone:
        return ""
    return re.sub(r"\D", "", phone)


def resolve_business_by_phone(db: Session, destination_phone: str) -> Business | None:
    """Identify the business tenant associated with the incoming destination phone number."""
    clean_to = destination_phone.strip()
    to_digits = clean_phone_digits(clean_to)

    # 1. Direct exact match on Business.phone
    business = db.scalar(
        select(Business).where(Business.phone == clean_to, Business.is_active.is_(True))
    )
    if business:
        return business

    # 2. Relaxed digit-only comparison against active businesses
    if to_digits:
        active_businesses = db.scalars(
            select(Business).where(Business.is_active.is_(True), Business.phone.isnot(None))
        ).all()
        for b in active_businesses:
            if b.phone and clean_phone_digits(b.phone) == to_digits:
                return b

    # 3. Check BusinessIntegration phone numbers (Plivo)
    try:
        from app.models.integration import BusinessIntegration
        integrations = db.scalars(select(BusinessIntegration)).all()
        for integ in integrations:
            candidate_phones = [
                getattr(integ, "plivo_phone_number", None),
            ]
            for cp in candidate_phones:
                if cp and (cp == clean_to or (to_digits and clean_phone_digits(cp) == to_digits)):
                    biz = db.get(Business, integ.business_id)
                    if biz and biz.is_active:
                        return biz
    except Exception:
        pass

    # 4. Check if destination phone matches global platform PLIVO_PHONE_NUMBER
    configured_global_numbers = [
        getattr(settings, "PLIVO_PHONE_NUMBER", None),
    ]
    for gn in configured_global_numbers:
        if gn and to_digits and clean_phone_digits(gn) == to_digits:
            matched_biz = db.scalar(
                select(Business).where(
                    Business.phone == gn, Business.is_active.is_(True)
                )
            )
            if matched_biz:
                return matched_biz

            # Fallback to the primary active business if only one tenant is deployed
            primary_biz = db.scalar(select(Business).where(Business.is_active.is_(True)).limit(1))
            if primary_biz:
                return primary_biz

    return None


def resolve_or_create_customer(db: Session, business_id: str, caller_phone: str) -> Customer:
    """Find existing customer by phone number within the tenant, or create a new customer record."""
    norm_from = normalize_indian_mobile_number(caller_phone) or caller_phone.strip()
    from_digits = clean_phone_digits(norm_from)

    # 1. Exact match within tenant
    customer = db.scalar(
        select(Customer).where(
            Customer.business_id == business_id, Customer.phone == norm_from
        )
    )
    if customer:
        customer.total_calls = (customer.total_calls or 0) + 1
        db.commit()
        db.refresh(customer)
        return customer

    # 2. Relaxed digit match within tenant
    if from_digits:
        tenant_customers = db.scalars(
            select(Customer).where(Customer.business_id == business_id)
        ).all()
        for c in tenant_customers:
            if c.phone and clean_phone_digits(c.phone) == from_digits:
                c.total_calls = (c.total_calls or 0) + 1
                if norm_from.startswith("+91") and not c.phone.startswith("+91"):
                    c.phone = norm_from
                db.commit()
                db.refresh(c)
                return c

    # 3. Customer does not exist; create new customer
    customer = Customer(
        business_id=business_id,
        name=f"Caller {norm_from}",
        phone=norm_from,
        notes="Auto-created from incoming voice receptionist call.",
        total_calls=1,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    logger.info(
        "Created new customer ID %s for caller %s in Business ID %s",
        customer.id,
        norm_from,
        business_id,
    )
    return customer
