"""Appointment booking service for business logic, conflict prevention, and customer lifecycle."""

from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.appointment import Appointment
from app.models.assistant import Service
from app.models.customer import Customer
from app.schemas.appointment import AppointmentCreate
from app.services.scheduling_service import validate_booking_feasibility
from app.services.telephony.phone_utils import clean_phone_digits, normalize_indian_mobile_number

logger = get_logger(__name__)


def book_appointment_core(
    db: Session,
    business_id: str,
    payload: AppointmentCreate,
    validate_conflicts: bool = True,
    enforce_operating_hours: bool = False,
    enforce_past_check: bool = True,
) -> Appointment:
    """Core appointment booking logic shared by user API and telephony integrations.

    1. Identifies or creates customer record by phone number.
    2. Validates scheduling feasibility, operating hours, service duration, and conflict avoidance.
    3. Prevents duplicate and overlapping bookings.
    4. Creates and commits the appointment record strictly bound to business_id.
    """
    customer_id = payload.customer_id

    # 1. Resolve or auto-create Customer with canonical +91 phone normalization
    if payload.customer_phone and (not customer_id or customer_id == "new"):
        clean_phone = normalize_indian_mobile_number(payload.customer_phone) or payload.customer_phone.strip()
        payload.customer_phone = clean_phone
        from_digits = clean_phone_digits(clean_phone)

        # Exact match
        customer = db.scalar(
            select(Customer).where(
                Customer.business_id == business_id,
                Customer.phone == clean_phone,
            )
        )
        # Relaxed match within tenant if not exact
        if not customer and from_digits:
            for c in db.scalars(select(Customer).where(Customer.business_id == business_id)).all():
                if c.phone and clean_phone_digits(c.phone) == from_digits:
                    customer = c
                    if clean_phone.startswith("+91") and not c.phone.startswith("+91"):
                        c.phone = clean_phone
                    break

        if not customer:
            customer = Customer(
                business_id=business_id,
                name=payload.customer_name or "New Client",
                phone=clean_phone,
                total_appointments=1,
            )
            db.add(customer)
            db.flush()
            logger.info("Auto-created new customer '%s' (%s) for business %s", customer.name, customer.phone, business_id)
        else:
            customer.total_appointments = (customer.total_appointments or 0) + 1
            clean_name = payload.customer_name.strip() if payload.customer_name else None
            if clean_name and clean_name not in ("New Client", "Walk-in Customer") and not clean_name.startswith("Caller "):
                customer.name = clean_name
            db.flush()
            logger.info("Reused customer '%s' (%s), total_appointments: %d", customer.name, customer.phone, customer.total_appointments)
        customer_id = customer.id
    elif customer_id and customer_id != "new":
        cust = db.scalar(
            select(Customer).where(
                Customer.id == customer_id,
                Customer.business_id == business_id,
            )
        )
        if cust:
            cust.total_appointments = (cust.total_appointments or 0) + 1
            db.flush()
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer with ID '{customer_id}' not found.",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either customer_id or customer_phone is required to book an appointment.",
        )

    # 2. Validate Service if provided
    duration_minutes = 30
    if payload.service_id:
        service = db.scalar(
            select(Service).where(
                Service.id == payload.service_id,
                Service.business_id == business_id,
            )
        )
        if not service:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Service ID '{payload.service_id}' not found for this business.",
            )
        duration_minutes = max(10, service.duration_minutes)

    # 3. Conflict Detection, Operating Hours, and Service Duration Validation
    appointment_time = payload.appointment_time
    end_time = payload.end_time

    if validate_conflicts:
        app_time_utc, computed_end_utc, duration_minutes = validate_booking_feasibility(
            db=db,
            business_id=business_id,
            appointment_time=payload.appointment_time,
            service_id=payload.service_id,
            staff_id=payload.staff_id,
            customer_id=customer_id,
            customer_phone=payload.customer_phone,
            enforce_operating_hours=enforce_operating_hours,
            enforce_past_check=enforce_past_check,
        )
        appointment_time = app_time_utc
        if not end_time:
            end_time = computed_end_utc

    # 4. Create and Commit Appointment
    appt = Appointment(
        business_id=business_id,
        customer_id=customer_id,
        service_id=payload.service_id,
        staff_id=payload.staff_id,
        appointment_time=appointment_time,
        end_time=end_time,
        status=payload.status or "upcoming",
        notes=payload.notes,
        source=payload.source or "manual",
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)
    logger.info("Created appointment ID %s for business %s (start: %s, end: %s)", appt.id, business_id, appt.appointment_time, appt.end_time)

    # Phase 6: Auto-schedule reminders for the new appointment
    try:
        from app.services.reminder_service import schedule_appointment_reminders
        schedule_appointment_reminders(db, appt)
    except Exception as exc:
        logger.warning("Auto-scheduling reminders skipped: %s", exc)

    return appt
