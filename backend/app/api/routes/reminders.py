"""Reminder Management routes."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db_session
from app.models.customer import Customer
from app.models.reminder import Reminder
from app.models.user import User
from app.schemas.reminder import (
    ReminderCreate,
    ReminderResponse,
    ReminderUpdate,
)

router = APIRouter()


@router.get("", response_model=list[ReminderResponse])
def list_reminders(
    status_filter: str | None = Query(None, alias="status"),
    reminder_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[ReminderResponse]:
    """List reminders with status or channel filters."""
    stmt = (
        select(Reminder)
        .where(Reminder.business_id == current_user.business_id)
        .order_by(Reminder.scheduled_time.asc())
    )

    if status_filter:
        stmt = stmt.where(Reminder.status == status_filter)
    if reminder_type:
        stmt = stmt.where(Reminder.reminder_type == reminder_type)

    stmt = stmt.offset(offset).limit(limit)
    reminders = db.scalars(stmt).all()
    return [ReminderResponse.model_validate(r) for r in reminders]


@router.post("", response_model=ReminderResponse, status_code=status.HTTP_201_CREATED)
def create_reminder(
    payload: ReminderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> ReminderResponse:
    """Schedule a new reminder."""
    customer = db.scalar(
        select(Customer).where(
            Customer.id == payload.customer_id, Customer.business_id == current_user.business_id
        )
    )
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    reminder = Reminder(
        business_id=current_user.business_id,
        appointment_id=payload.appointment_id,
        customer_id=payload.customer_id,
        reminder_type=payload.reminder_type,
        scheduled_time=payload.scheduled_time,
        status=payload.status or "pending",
        message=payload.message,
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return ReminderResponse.model_validate(reminder)


@router.put("/{reminder_id}", response_model=ReminderResponse)
def update_reminder(
    reminder_id: str,
    payload: ReminderUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> ReminderResponse:
    """Update a reminder schedule or message."""
    reminder = db.scalar(
        select(Reminder).where(
            Reminder.id == reminder_id, Reminder.business_id == current_user.business_id
        )
    )
    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found.")

    if payload.reminder_type is not None:
        reminder.reminder_type = payload.reminder_type
    if payload.scheduled_time is not None:
        reminder.scheduled_time = payload.scheduled_time
    if payload.status is not None:
        reminder.status = payload.status
    if payload.message is not None:
        reminder.message = payload.message

    db.commit()
    db.refresh(reminder)
    return ReminderResponse.model_validate(reminder)


@router.post("/{reminder_id}/send", response_model=ReminderResponse)
def trigger_send_reminder(
    reminder_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> ReminderResponse:
    """Manually dispatch a reminder immediately."""
    reminder = db.scalar(
        select(Reminder).where(
            Reminder.id == reminder_id, Reminder.business_id == current_user.business_id
        )
    )
    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found.")

    reminder.status = "sent"
    reminder.sent_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(reminder)
    return ReminderResponse.model_validate(reminder)


@router.delete("/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reminder(
    reminder_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> None:
    """Cancel or delete a scheduled reminder."""
    reminder = db.scalar(
        select(Reminder).where(
            Reminder.id == reminder_id, Reminder.business_id == current_user.business_id
        )
    )
    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found.")

    db.delete(reminder)
    db.commit()

