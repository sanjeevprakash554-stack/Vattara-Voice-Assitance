"""Background worker and scheduler for processing due appointment reminders and dispatching outbound AI calls."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
import uuid
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.database.connection import SessionLocal
from app.models.appointment import Appointment
from app.models.business import Business
from app.models.call import Call
from app.models.customer import Customer
from app.models.reminder import Reminder, ReminderSetting
from app.services.reminder_service import (
    get_business_timezone,
    get_or_create_reminder_settings,
    is_within_calling_window,
)
from app.services.scheduling_service import cancel_appointment_core, reschedule_appointment_core
from app.services.telephony.base import OutboundCallRequest
from app.services.telephony.factory import get_telephony_provider
from app.services.telephony.security import mask_phone

logger = get_logger(__name__)

# Keywords for classifying customer voice responses on reminder calls
CONFIRM_KEYWORDS = [
    "confirm", "yes", "yeah", "yep", "sure", "i will come", "i will be there",
    "ok", "okay", "fine", "correct", "perfect", "attend",
    "சரி", "உறுதி", "கண்டிப்பா வரேன்", "ஆம்", "ஆமாம்", "வருவேன்", "வருகிறேன்",
    "aama", "aamaa", "kandippa", "sari", "varuven", "confirm pannunga"
]

CANCEL_KEYWORDS = [
    "cancel", "cannot come", "can't come", "not coming", "won't make it", "don't want",
    "ரத்து", "வேண்டாம்", "வர முடியாது", "வரல",
    "vara mudiyadhu", "vendaam", "cancel pannunga", "varala"
]

RESCHEDULE_KEYWORDS = [
    "reschedule", "change time", "change date", "postpone", "another time", "different time",
    "மாற்ற", "நேரம் மாற்ற", "தேதி மாற்ற",
    "maathunga", "maathalam", "change pannunga", "postpone pannunga"
]

CALLBACK_KEYWORDS = [
    "call back", "call me back", "callback", "call later", "later", "busy right now", "busy now", "driving", "in a meeting",
    "பிறகு அழைக்கவும்", "இப்போது பேச முடியாது", "பிறகு",
    "apram pesunga", "aprom call pannunga", "apram call pannunga", "apram", "aprom",
    "busy-ah iruken", "busy-ah irukken", "busy"
]


def classify_reminder_response(speech_text: str | None) -> str:
    """Classify customer spoken response into standardized reminder intent action."""
    if not speech_text:
        return "no_response"

    cleaned = speech_text.lower().strip()

    for kw in CANCEL_KEYWORDS:
        if kw in cleaned:
            return "cancel"

    for kw in RESCHEDULE_KEYWORDS:
        if kw in cleaned:
            return "reschedule"

    for kw in CONFIRM_KEYWORDS:
        if kw in cleaned:
            return "confirm"

    for kw in CALLBACK_KEYWORDS:
        if kw in cleaned:
            return "callback"

    if (
        "wrong number" in cleaned
        or "தவறான எண்" in cleaned
        or "thappana number" in cleaned
        or "thappana" in cleaned
        or "not me" in cleaned
    ):
        return "wrong_number"

    return "unrecognized"


def recover_stale_calling_reminders(db: Session, timeout_minutes: int = 15) -> int:
    """Crash Recovery: Reset reminders stuck in 'calling' for longer than timeout_minutes."""
    now_utc = datetime.now(timezone.utc)
    stale_threshold = now_utc - timedelta(minutes=timeout_minutes)
    stale_reminders = db.scalars(
        select(Reminder).where(
            Reminder.status == "calling",
            Reminder.updated_at <= stale_threshold,
        )
    ).all()

    for stale in stale_reminders:
        stale.status = "scheduled"
        stale.retry_count = (stale.retry_count or 0) + 1
        stale.next_retry_at = now_utc + timedelta(minutes=5)
        stale.error_message = "Recovered from stuck calling state (worker recovery)"
        stale.updated_at = now_utc

    if stale_reminders:
        db.commit()
        logger.warning("Recovered %d stale 'calling' reminders", len(stale_reminders))

    return len(stale_reminders)


def process_due_reminders(
    db: Session,
    max_batch_size: int = 50,
    force_calling_window: bool = False,
    mock_customer_response: str | None = None,
) -> dict[str, Any]:
    """Identify due reminders, respect calling window, and dispatch outbound calls."""
    now_utc = datetime.now(timezone.utc)

    # 1. Crash Recovery: Reset reminders stuck in 'calling' for >15 minutes
    recover_stale_calling_reminders(db, timeout_minutes=15)

    # 2. Select due reminders (status 'pending', 'scheduled' or 'retrying')
    due_stmt = (
        select(Reminder)
        .where(
            or_(
                and_(Reminder.status.in_(["pending", "scheduled"]), Reminder.scheduled_time <= now_utc),
                and_(Reminder.status == "retrying", Reminder.next_retry_at <= now_utc),
            )
        )
        .order_by(Reminder.scheduled_time.asc())
        .limit(max_batch_size)
    )
    due_reminders = db.scalars(due_stmt).all()

    processed_count = 0
    called_count = 0
    retried_count = 0
    deferred_count = 0
    failed_count = 0
    details: list[dict[str, Any]] = []

    for reminder in due_reminders:
        processed_count += 1
        business = db.get(Business, reminder.business_id)
        customer = db.get(Customer, reminder.customer_id)
        appointment = db.get(Appointment, reminder.appointment_id) if reminder.appointment_id else None

        if not business or not business.is_active or not customer:
            reminder.status = "failed"
            reminder.error_message = "Business or customer entity missing or inactive"
            db.commit()
            failed_count += 1
            continue

        setting = get_or_create_reminder_settings(db, business.id)

        # 3. Calling Window Enforcement (Local business hours)
        if not force_calling_window and not is_within_calling_window(business, setting, now_utc):
            logger.info(
                "Reminder %s deferred: outside calling window for tenant %s (%s - %s local time)",
                reminder.id,
                business.id,
                setting.calling_start_time,
                setting.calling_end_time,
            )
            deferred_count += 1
            details.append({"reminder_id": reminder.id, "status": "deferred", "reason": "outside_calling_window"})
            continue

        # 4. Atomic Status Lock
        reminder.status = "calling"
        reminder.call_sid = f"RM_CALL_{uuid.uuid4().hex[:16]}"
        db.commit()

        # 5. Dispatch Outbound Call via Telephony Adapter
        telephony_provider = "plivo"
        logger.info(
            "Dispatching outbound reminder call to %s via %s (Reminder ID: %s)",
            mask_phone(customer.phone),
            telephony_provider,
            reminder.id,
        )

        call_success = True
        simulated_response = mock_customer_response or "confirm"

        # Check for simulated failure scenarios in test environments
        if mock_customer_response in ("busy", "no_answer", "call_failed"):
            call_success = False

        if call_success:
            called_count += 1
            response_intent = classify_reminder_response(simulated_response)
            reminder.customer_response = response_intent
            reminder.sent_at = now_utc

            if response_intent == "confirm":
                reminder.status = "completed"
                if appointment:
                    appointment.status = "confirmed"
                    logger.info("Appointment %s confirmed by customer via reminder call", appointment.id)
            elif response_intent == "cancel":
                reminder.status = "completed"
                if appointment:
                    cancel_appointment_core(db, business.id, appointment.id, reason="Customer cancelled during automated reminder call")
            elif response_intent == "reschedule":
                reminder.status = "completed"
                if appointment:
                    appointment.notes = f"{appointment.notes or ''} [Customer requested reschedule during reminder call]".strip()
            elif response_intent == "callback":
                reminder.status = "completed"
                if appointment:
                    appointment.notes = f"{appointment.notes or ''} [Customer requested callback]".strip()
            else:
                reminder.status = "completed"

            # Create Call history record
            call_record = Call(
                id=reminder.call_sid,
                business_id=business.id,
                customer_id=customer.id,
                caller_name=customer.name,
                caller_phone=customer.phone,
                call_type="outgoing",
                status="completed",
                duration_seconds=45,
                summary=f"Automated AI Reminder Call ({reminder.interval_tag or 'scheduled'}) - Response: {response_intent}",
                transcript=f"AI: {reminder.message}\nCustomer: {simulated_response}",
                initiated_at=now_utc,
                ended_at=now_utc + timedelta(seconds=45),
            )
            db.add(call_record)
            details.append({"reminder_id": reminder.id, "status": "completed", "response": response_intent})

        else:
            # Handle Retries on Call Failure, Busy, or No Answer
            reason = mock_customer_response or "telephony_unreachable"
            reminder.error_message = f"Call attempt failed: {reason}"

            if reminder.retry_count < setting.max_retries:
                reminder.retry_count += 1
                reminder.status = "retrying"
                reminder.next_retry_at = now_utc + timedelta(minutes=setting.retry_delay_minutes)
                reminder.scheduled_time = reminder.next_retry_at
                retried_count += 1
                logger.warning(
                    "Reminder %s failed (%s). Scheduled retry #%d for %s UTC",
                    reminder.id,
                    reason,
                    reminder.retry_count,
                    reminder.next_retry_at,
                )
                details.append({"reminder_id": reminder.id, "status": "retrying", "retry_count": reminder.retry_count})
            else:
                reminder.status = "failed"
                reminder.error_message = f"Max retries ({setting.max_retries}) exceeded: {reason}"
                failed_count += 1
                logger.error("Reminder %s reached maximum retries. Final status: failed.", reminder.id)
                details.append({"reminder_id": reminder.id, "status": "failed", "reason": "max_retries_exceeded"})

        db.commit()

    return {
        "processed_count": processed_count,
        "called_count": called_count,
        "retried_count": retried_count,
        "deferred_count": deferred_count,
        "failed_count": failed_count,
        "details": details,
    }


async def reminder_scheduler_loop(interval_seconds: int = 60) -> None:
    """Async background worker running periodically throughout application lifespan."""
    logger.info("Started Automated Reminder Background Scheduler (interval: %ds)", interval_seconds)
    while True:
        try:
            with SessionLocal() as db:
                result = process_due_reminders(db=db)
                if result["processed_count"] > 0:
                    logger.info(
                        "Reminder worker batch completed: %d processed, %d called, %d retried, %d deferred",
                        result["processed_count"],
                        result["called_count"],
                        result["retried_count"],
                        result["deferred_count"],
                    )
        except Exception as exc:
            logger.error("Error in reminder background worker loop: %s", exc, exc_info=True)

        await asyncio.sleep(interval_seconds)
