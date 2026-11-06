"""Appointment Management routes."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db_session
from app.models.appointment import Appointment
from app.models.assistant import Service
from app.models.customer import Customer
from app.models.user import User
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentUpdate,
)

router = APIRouter()


@router.get("", response_model=list[AppointmentResponse])
def list_appointments(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[AppointmentResponse]:
    """List appointments for the business with optional status filter."""
    stmt = (
        select(Appointment)
        .where(Appointment.business_id == current_user.business_id)
        .order_by(Appointment.appointment_time.desc())
    )

    if status_filter:
        stmt = stmt.where(Appointment.status == status_filter)

    stmt = stmt.offset(offset).limit(limit)
    appointments = db.scalars(stmt).all()
    return [AppointmentResponse.model_validate(a) for a in appointments]


@router.get("/{appointment_id}", response_model=AppointmentResponse)
def get_appointment(
    appointment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> AppointmentResponse:
    """Get single appointment details."""
    appt = db.scalar(
        select(Appointment).where(
            Appointment.id == appointment_id, Appointment.business_id == current_user.business_id
        )
    )
    if not appt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")

    return AppointmentResponse.model_validate(appt)


@router.post("", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
def create_appointment(
    payload: AppointmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> AppointmentResponse:
    """Create a new appointment, creating customer if needed."""
    customer_id = payload.customer_id

    # If customer_id is a placeholder or name/phone is provided, verify or create customer
    if payload.customer_phone and (not customer_id or customer_id == "new"):
        customer = db.scalar(
            select(Customer).where(
                Customer.business_id == current_user.business_id,
                Customer.phone == payload.customer_phone,
            )
        )
        if not customer:
            customer = Customer(
                business_id=current_user.business_id,
                name=payload.customer_name or "New Client",
                phone=payload.customer_phone,
                total_appointments=1,
            )
            db.add(customer)
            db.flush()
        else:
            customer.total_appointments += 1
        customer_id = customer.id
    else:
        cust = db.get(Customer, customer_id)
        if cust:
            cust.total_appointments += 1

    appt = Appointment(
        business_id=current_user.business_id,
        customer_id=customer_id,
        service_id=payload.service_id,
        appointment_time=payload.appointment_time,
        end_time=payload.end_time,
        status=payload.status or "upcoming",
        notes=payload.notes,
        source=payload.source or "manual",
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)

    return AppointmentResponse.model_validate(appt)


@router.put("/{appointment_id}", response_model=AppointmentResponse)
def update_appointment(
    appointment_id: str,
    payload: AppointmentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> AppointmentResponse:
    """Update or reschedule an appointment."""
    appt = db.scalar(
        select(Appointment).where(
            Appointment.id == appointment_id, Appointment.business_id == current_user.business_id
        )
    )
    if not appt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")

    if payload.appointment_time is not None:
        appt.appointment_time = payload.appointment_time
    if payload.end_time is not None:
        appt.end_time = payload.end_time
    if payload.status is not None:
        appt.status = payload.status
    if payload.service_id is not None:
        appt.service_id = payload.service_id
    if payload.notes is not None:
        appt.notes = payload.notes

    db.commit()
    db.refresh(appt)
    return AppointmentResponse.model_validate(appt)


@router.post("/{appointment_id}/cancel", response_model=AppointmentResponse)
def cancel_appointment(
    appointment_id: str,
    reason: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> AppointmentResponse:
    """Cancel an appointment."""
    appt = db.scalar(
        select(Appointment).where(
            Appointment.id == appointment_id, Appointment.business_id == current_user.business_id
        )
    )
    if not appt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")

    appt.status = "cancelled"
    if reason:
        appt.notes = f"{appt.notes or ''} [Cancelled: {reason}]".strip()

    db.commit()
    db.refresh(appt)
    return AppointmentResponse.model_validate(appt)


@router.post("/{appointment_id}/complete", response_model=AppointmentResponse)
def complete_appointment(
    appointment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> AppointmentResponse:
    """Mark an appointment as completed."""
    appt = db.scalar(
        select(Appointment).where(
            Appointment.id == appointment_id, Appointment.business_id == current_user.business_id
        )
    )
    if not appt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")

    appt.status = "completed"
    db.commit()
    db.refresh(appt)
    return AppointmentResponse.model_validate(appt)

