"""Customer management and interaction history API routes."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.api.deps import (
    get_current_active_user,
    get_current_business,
    get_db_session,
    require_staff,
)
from app.core.logging import get_logger
from app.models.appointment import Appointment
from app.models.business import Business
from app.models.call_history import CallHistory
from app.models.customer import Customer
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.customer import (
    CustomerAppointmentHistoryItem,
    CustomerCallHistoryItem,
    CustomerCreateRequest,
    CustomerHistoryResponse,
    CustomerResponse,
    CustomerUpdateRequest,
)

logger = get_logger(__name__)
router = APIRouter()


# ==============================================================================
# MODULE 5: CUSTOMER MANAGEMENT
# ==============================================================================

@router.post(
    "",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Customers"],
    summary="Create Customer",
    description="Register a new customer/client record under the authenticated business tenant.",
)
def create_customer(
    payload: CustomerCreateRequest,
    business: Business = Depends(get_current_business),
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db_session),
) -> CustomerResponse:
    """Create a customer record with duplicate prevention within the tenant."""
    clean_phone = payload.phone_number.strip()

    # Prevent duplicate active customer by phone number within the same tenant
    existing = (
        db.query(Customer)
        .filter(
            Customer.business_id == business.id,
            Customer.phone_number == clean_phone,
            Customer.is_active.is_(True),
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An active customer with phone number '{clean_phone}' already exists in your business.",
        )

    customer = Customer(
        business_id=business.id,
        customer_name=payload.customer_name.strip(),
        phone_number=clean_phone,
        email=str(payload.email).lower().strip() if payload.email else None,
        address=payload.address.strip() if payload.address else None,
        notes=payload.notes.strip() if payload.notes else None,
        is_active=True,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)

    logger.info("User ID %d created customer '%s' (ID %d) in Business ID %d", current_user.id, customer.customer_name, customer.id, business.id)
    return CustomerResponse.model_validate(customer)


@router.get(
    "",
    response_model=list[CustomerResponse],
    tags=["Customers"],
    summary="List & Search Customers",
    description="Retrieve customer records with text search (name, phone, email), active filter, and pagination.",
)
def list_customers(
    search: str | None = Query(default=None, description="Search term matching customer name, phone number, or email"),
    is_active: bool | None = Query(default=None, description="Filter by active status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db_session),
) -> list[CustomerResponse]:
    """List and search customers strictly belonging to the caller's business."""
    query = db.query(Customer).filter(Customer.business_id == business.id)

    if is_active is not None:
        query = query.filter(Customer.is_active == is_active)

    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Customer.customer_name.ilike(pattern),
                Customer.phone_number.ilike(pattern),
                Customer.email.ilike(pattern),
            )
        )

    customers = query.order_by(Customer.customer_name.asc()).offset(skip).limit(limit).all()
    return [CustomerResponse.model_validate(c) for c in customers]


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    tags=["Customers"],
    summary="Get Customer Details",
    description="Retrieve full profile details of a customer within the authenticated business.",
)
def get_customer(
    customer_id: int,
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db_session),
) -> CustomerResponse:
    """Get single customer profile enforcing multi-tenant boundaries."""
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.business_id == business.id)
        .first()
    )
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found in your business organization.",
        )
    return CustomerResponse.model_validate(customer)


@router.put(
    "/{customer_id}",
    response_model=CustomerResponse,
    tags=["Customers"],
    summary="Update Customer Profile",
    description="Update customer information, contact details, or notes.",
)
def update_customer(
    customer_id: int,
    payload: CustomerUpdateRequest,
    business: Business = Depends(get_current_business),
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db_session),
) -> CustomerResponse:
    """Update customer profile information."""
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.business_id == business.id)
        .first()
    )
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found in your business organization.",
        )

    if payload.phone_number is not None:
        clean_phone = payload.phone_number.strip()
        existing = (
            db.query(Customer)
            .filter(
                Customer.business_id == business.id,
                Customer.phone_number == clean_phone,
                Customer.id != customer.id,
                Customer.is_active.is_(True),
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Another active customer with phone number '{clean_phone}' already exists.",
            )
        customer.phone_number = clean_phone

    if payload.customer_name is not None:
        customer.customer_name = payload.customer_name.strip()
    if payload.email is not None:
        customer.email = str(payload.email).lower().strip()
    if payload.address is not None:
        customer.address = payload.address.strip()
    if payload.notes is not None:
        customer.notes = payload.notes.strip()
    if payload.is_active is not None:
        customer.is_active = payload.is_active

    db.commit()
    db.refresh(customer)

    logger.info("User ID %d updated customer ID %d in Business ID %d", current_user.id, customer.id, business.id)
    return CustomerResponse.model_validate(customer)


@router.delete(
    "/{customer_id}",
    response_model=MessageResponse,
    tags=["Customers"],
    summary="Deactivate Customer",
    description="Soft-deactivate a customer record (preserves historical calls and appointments).",
)
def delete_customer(
    customer_id: int,
    business: Business = Depends(get_current_business),
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db_session),
) -> MessageResponse:
    """Soft deactivation of customer."""
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.business_id == business.id)
        .first()
    )
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found in your business organization.",
        )

    customer.is_active = False
    db.commit()

    logger.info("User ID %d deactivated customer ID %d in Business ID %d", current_user.id, customer.id, business.id)
    return MessageResponse(message="Customer successfully deactivated.")


# ==============================================================================
# MODULE 6: CUSTOMER HISTORY
# ==============================================================================

@router.get(
    "/{customer_id}/history",
    response_model=CustomerHistoryResponse,
    tags=["Customer History"],
    summary="Get Customer Interaction History",
    description="Retrieve a comprehensive dossier of previous appointments, telephony call logs, and latest activity.",
)
def get_customer_history(
    customer_id: int,
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db_session),
) -> CustomerHistoryResponse:
    """Retrieve historical appointments and call history for a customer."""
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.business_id == business.id)
        .first()
    )
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found in your business organization.",
        )

    # 1. Fetch appointments
    appts = (
        db.query(Appointment)
        .filter(Appointment.customer_id == customer.id, Appointment.business_id == business.id)
        .order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.desc())
        .all()
    )

    # 2. Fetch call history
    calls = (
        db.query(CallHistory)
        .filter(CallHistory.customer_id == customer.id, CallHistory.business_id == business.id)
        .order_by(CallHistory.created_at.desc())
        .all()
    )

    # 3. Compute last interaction date
    candidates: list[datetime] = []
    if calls:
        candidates.append(calls[0].created_at)
    if appts:
        appt_latest = appts[0]
        # Combine date and time into timezone-aware datetime (UTC)
        appt_dt = datetime.combine(
            appt_latest.appointment_date,
            appt_latest.appointment_time,
            tzinfo=timezone.utc,
        )
        candidates.append(appt_dt)
        if appt_latest.created_at:
            candidates.append(appt_latest.created_at)

    last_interaction = max(candidates) if candidates else None

    return CustomerHistoryResponse(
        customer=CustomerResponse.model_validate(customer),
        appointments=[CustomerAppointmentHistoryItem.model_validate(a) for a in appts],
        call_history=[CustomerCallHistoryItem.model_validate(c) for c in calls],
        total_calls=len(calls),
        total_appointments=len(appts),
        last_interaction_date=last_interaction,
    )
