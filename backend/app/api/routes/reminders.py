"""Reminder Management routes with automated AI outbound calling, scheduling, and configuration."""

from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db_session
from app.models.customer import Customer
from app.models.reminder import Reminder, ReminderSetting
from app.models.user import User
from app.schemas.reminder import (
    ProcessDueRemindersResponse,
    ReminderCreate,
    ReminderResponse,
    ReminderSettingResponse,
    ReminderSettingUpdate,
    ReminderUpdate,
)
from app.services.reminder_service import get_or_create_reminder_settings
from app.services.reminder_worker import classify_reminder_response, process_due_reminders

router = APIRouter()


class ClassifyResponsePayload(BaseModel):
    speech_text: str | None = None
    transcript: str | None = None
    language: str | None = None


@router.get("/settings", response_model=ReminderSettingResponse)
def get_reminder_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> ReminderSettingResponse:
    """Retrieve reminder configuration and calling window for the authenticated business tenant."""
    setting = get_or_create_reminder_settings(db, current_user.business_id)
    return ReminderSettingResponse.model_validate(setting)


@router.put("/settings", response_model=ReminderSettingResponse)
def update_reminder_settings(
    payload: ReminderSettingUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> ReminderSettingResponse:
    """Update reminder intervals, calling hours, or retry limits for the business tenant."""
    setting = get_or_create_reminder_settings(db, current_user.business_id)

    if payload.reminder_intervals_hours is not None:
        setting.reminder_intervals_hours = payload.reminder_intervals_hours.strip()
    if payload.calling_start_time is not None:
        setting.calling_start_time = payload.calling_start_time.strip()
    if payload.calling_end_time is not None:
        setting.calling_end_time = payload.calling_end_time.strip()
    if payload.max_retries is not None:
        setting.max_retries = payload.max_retries
    if payload.retry_delay_minutes is not None:
        setting.retry_delay_minutes = payload.retry_delay_minutes
    if payload.is_enabled is not None:
        setting.is_enabled = payload.is_enabled
    if payload.default_channel is not None:
        setting.default_channel = payload.default_channel.strip()

    db.commit()
    db.refresh(setting)
    return ReminderSettingResponse.model_validate(setting)


@router.post("/process-due", response_model=ProcessDueRemindersResponse)
def trigger_process_due_reminders(
    force_calling_window: bool = Query(False, description="Bypass calling window check (e.g. for testing)"),
    mock_response: str | None = Query(None, description="Simulate specific customer answer (confirm, reschedule, cancel, busy, no_answer)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> ProcessDueRemindersResponse:
    """Trigger processing of all due appointment reminders across business tenants."""
    result = process_due_reminders(
        db=db,
        force_calling_window=force_calling_window,
        mock_customer_response=mock_response,
    )
    return ProcessDueRemindersResponse.model_validate(result)


@router.post("/classify-response")
def classify_customer_voice_response(payload: ClassifyResponsePayload) -> dict[str, str]:
    """Parse customer spoken response and determine reminder action (confirm, reschedule, cancel, callback)."""
    text = payload.speech_text or payload.transcript or ""
    intent = classify_reminder_response(text)
    return {"speech_text": text, "intent": intent}


@router.get("", response_model=list[ReminderResponse])
def list_reminders(
    status_filter: str | None = Query(None, alias="status"),
    reminder_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[ReminderResponse]:
    """List reminders with status or channel filters for the authenticated tenant."""
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
    """Schedule a new reminder manually."""
    customer = db.scalar(
        select(Customer).where(
            Customer.id == payload.customer_id, Customer.business_id == current_user.business_id
        )
    )
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    setting = get_or_create_reminder_settings(db, current_user.business_id)

    reminder = Reminder(
        business_id=current_user.business_id,
        appointment_id=payload.appointment_id,
        customer_id=payload.customer_id,
        reminder_type=payload.reminder_type or setting.default_channel,
        scheduled_time=payload.scheduled_time,
        status=payload.status or "pending",
        message=payload.message,
        interval_tag=payload.interval_tag or "manual",
        max_retries=setting.max_retries,
        retry_count=0,
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return ReminderResponse.model_validate(reminder)


@router.get("/{reminder_id}", response_model=ReminderResponse)
def get_reminder(
    reminder_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> ReminderResponse:
    """Retrieve a single reminder by ID for the authenticated business tenant."""
    reminder = db.scalar(
        select(Reminder).where(
            Reminder.id == reminder_id, Reminder.business_id == current_user.business_id
        )
    )
    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found.")
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
    if payload.retry_count is not None:
        reminder.retry_count = payload.retry_count
    if payload.next_retry_at is not None:
        reminder.next_retry_at = payload.next_retry_at
    if payload.customer_response is not None:
        reminder.customer_response = payload.customer_response
    if payload.error_message is not None:
        reminder.error_message = payload.error_message

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
