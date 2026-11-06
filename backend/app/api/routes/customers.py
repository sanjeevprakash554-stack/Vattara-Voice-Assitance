"""Customer Management routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db_session
from app.models.appointment import Appointment
from app.models.call import Call
from app.models.customer import Customer
from app.models.user import User
from app.schemas.customer import (
    CustomerCreate,
    CustomerDetailResponse,
    CustomerResponse,
    CustomerUpdate,
)

router = APIRouter()


@router.get("", response_model=list[CustomerResponse])
def list_customers(
    search: str | None = Query(None, description="Search by name, phone, or email"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[CustomerResponse]:
    """List customers with search filtering."""
    stmt = (
        select(Customer)
        .where(Customer.business_id == current_user.business_id)
        .order_by(Customer.name.asc())
    )

    if search:
        search_fmt = f"%{search}%"
        stmt = stmt.where(
            or_(
                Customer.name.ilike(search_fmt),
                Customer.phone.ilike(search_fmt),
                Customer.email.ilike(search_fmt),
            )
        )

    stmt = stmt.offset(offset).limit(limit)
    customers = db.scalars(stmt).all()
    return [CustomerResponse.model_validate(c) for c in customers]


@router.get("/{customer_id}", response_model=CustomerDetailResponse)
def get_customer_details(
    customer_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> CustomerDetailResponse:
    """Retrieve single customer and their complete timeline of calls and appointments."""
    customer = db.scalar(
        select(Customer).where(
            Customer.id == customer_id, Customer.business_id == current_user.business_id
        )
    )
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    # Fetch calls
    calls = db.scalars(
        select(Call)
        .where(Call.customer_id == customer.id)
        .order_by(Call.initiated_at.desc())
        .limit(20)
    ).all()

    # Fetch appointments
    appts = db.scalars(
        select(Appointment)
        .where(Appointment.customer_id == customer.id)
        .order_by(Appointment.appointment_time.desc())
        .limit(20)
    ).all()

    call_dicts = [
        {
            "id": c.id,
            "call_type": c.call_type,
            "status": c.status,
            "duration_seconds": c.duration_seconds,
            "summary": c.summary,
            "initiated_at": c.initiated_at.isoformat(),
        }
        for c in calls
    ]

    appt_dicts = [
        {
            "id": a.id,
            "status": a.status,
            "appointment_time": a.appointment_time.isoformat(),
            "notes": a.notes,
            "source": a.source,
            "service_name": a.service.name if a.service else "Consultation",
        }
        for a in appts
    ]

    return CustomerDetailResponse(
        id=customer.id,
        business_id=customer.business_id,
        name=customer.name,
        phone=customer.phone,
        email=customer.email,
        notes=customer.notes,
        total_calls=len(calls),
        total_appointments=len(appts),
        created_at=customer.created_at,
        updated_at=customer.updated_at,
        calls=call_dicts,
        appointments=appt_dicts,
    )


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> CustomerResponse:
    """Create a new customer profile."""
    # Check phone uniqueness within business
    existing = db.scalar(
        select(Customer).where(
            Customer.business_id == current_user.business_id,
            Customer.phone == payload.phone,
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A customer with this phone number already exists in your organization.",
        )

    customer = Customer(
        business_id=current_user.business_id,
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        notes=payload.notes,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return CustomerResponse.model_validate(customer)


@router.put("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: str,
    payload: CustomerUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> CustomerResponse:
    """Update customer details."""
    customer = db.scalar(
        select(Customer).where(
            Customer.id == customer_id, Customer.business_id == current_user.business_id
        )
    )
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    if payload.name is not None:
        customer.name = payload.name
    if payload.phone is not None:
        customer.phone = payload.phone
    if payload.email is not None:
        customer.email = payload.email
    if payload.notes is not None:
        customer.notes = payload.notes

    db.commit()
    db.refresh(customer)
    return CustomerResponse.model_validate(customer)


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
    customer_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> None:
    """Delete a customer record."""
    customer = db.scalar(
        select(Customer).where(
            Customer.id == customer_id, Customer.business_id == current_user.business_id
        )
    )
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    db.delete(customer)
    db.commit()

