"""Automated Appointment Reminder scheduling, lifecycle management, and calling window enforcement."""

from datetime import datetime, time, timedelta, timezone
import re
from typing import Any
from zoneinfo import ZoneInfo
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.appointment import Appointment
from app.models.assistant import AssistantConfig, Service
from app.models.business import Business
from app.models.customer import Customer
from app.models.reminder import Reminder, ReminderSetting

logger = get_logger(__name__)


def get_business_timezone(business: Business) -> ZoneInfo:
    """Safely resolve business timezone with Asia/Kolkata default fallback."""
    tz_name = business.timezone if business and business.timezone else "Asia/Kolkata"
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("Asia/Kolkata")


def get_or_create_reminder_settings(db: Session, business_id: str) -> ReminderSetting:
    """Retrieve tenant reminder configuration or initialize defaults (24h & 2h intervals)."""
    setting = db.scalar(
        select(ReminderSetting).where(ReminderSetting.business_id == business_id)
    )
    if not setting:
        setting = ReminderSetting(
            business_id=business_id,
            reminder_intervals_hours="24,2",
            calling_start_time="09:00",
            calling_end_time="20:00",
            max_retries=3,
            retry_delay_minutes=15,
            is_enabled=True,
            default_channel="voice",
        )
        db.add(setting)
        db.commit()
        db.refresh(setting)
        logger.info("Initialized default reminder settings for tenant %s (intervals: 24h, 2h)", business_id)
    return setting


def is_within_calling_window(
    business: Business,
    setting: ReminderSetting,
    target_utc: datetime | None = None,
) -> bool:
    """Check whether given time (or now) falls within tenant's allowed local calling hours."""
    now_utc = target_utc or datetime.now(timezone.utc)
    biz_tz = get_business_timezone(business)
    local_dt = now_utc.astimezone(biz_tz)

    try:
        start_parts = [int(p) for p in setting.calling_start_time.split(":")[:2]]
        end_parts = [int(p) for p in setting.calling_end_time.split(":")[:2]]
        start_t = time(hour=start_parts[0], minute=start_parts[1])
        end_t = time(hour=end_parts[0], minute=end_parts[1])
    except Exception:
        start_t = time(9, 0)
        end_t = time(20, 0)

    current_t = local_dt.time()
    return start_t <= current_t <= end_t


def generate_reminder_message(
    business_name: str,
    customer_name: str | None,
    service_name: str | None,
    appointment_time_local: datetime,
    language: str = "en-IN",
) -> str:
    """Generate conversational reminder script in English, Tamil, or Tanglish."""
    cust_display = customer_name if customer_name and not customer_name.startswith("Caller ") else "valued customer"
    service_display = service_name or "consultation"
    date_str = appointment_time_local.strftime("%A, %B %d")
    time_str = appointment_time_local.strftime("%I:%M %p")

    if language.startswith("ta-IN"):
        return (
            f"வணக்கம் {cust_display}! இது {business_name}-லிருந்து நினைவூட்டல் அழைப்பு. "
            f"உங்களுக்கு {date_str} அன்று {time_str} மணிக்கு {service_display} முன்பதிவு உள்ளது. "
            f"முன்பதிவை உறுதிப்படுத்த விரும்புகிறீர்களா?"
        )
    elif language.startswith("ta-Latn"):
        return (
            f"Vanakkam {cust_display}! Idhu {business_name}-la irundhu appointment reminder call. "
            f"Ungalukku {date_str} at {time_str}-ku {service_display} appointment irukku. "
            f"Confirm panna virumbureengala?"
        )

    return (
        f"Hello {cust_display}, this is an automated appointment reminder from {business_name}. "
        f"You have an upcoming appointment for {service_display} on {date_str} at {time_str}. "
        f"Would you like to confirm this appointment?"
    )


def schedule_appointment_reminders(
    db: Session,
    appointment: Appointment,
) -> list[Reminder]:
    """Generate and schedule automatic reminders (e.g. 24h & 2h prior) for an appointment."""
    if appointment.status in ("cancelled", "completed"):
        return []

    setting = get_or_create_reminder_settings(db, appointment.business_id)
    if not setting.is_enabled:
        logger.info("Reminders disabled for business %s. Skipping auto-schedule.", appointment.business_id)
        return []

    business = db.get(Business, appointment.business_id)
    customer = db.get(Customer, appointment.customer_id)
    service = db.get(Service, appointment.service_id) if appointment.service_id else None

    if not business or not customer:
        logger.warning("Cannot schedule reminders: missing business or customer entity.")
        return []

    # Resolve business language
    cfg = db.scalar(select(AssistantConfig).where(AssistantConfig.business_id == business.id))
    lang = cfg.language if cfg and cfg.language else "en-IN"

    # Ensure appointment time is timezone-aware
    appt_time = appointment.appointment_time
    if appt_time.tzinfo is None:
        appt_time = appt_time.replace(tzinfo=timezone.utc)

    biz_tz = get_business_timezone(business)
    appt_local = appt_time.astimezone(biz_tz)

    # Parse interval hours (e.g., "24,2" -> [24, 2])
    interval_hours: list[int] = []
    for part in setting.reminder_intervals_hours.split(","):
        part = part.strip()
        try:
            val = int(part)
            if val > 0:
                interval_hours.append(val)
        except ValueError:
            continue

    if not interval_hours:
        interval_hours = [24, 2]

    now_utc = datetime.now(timezone.utc)
    created_reminders: list[Reminder] = []

    for hours in interval_hours:
        tag = f"{hours}h"
        target_sched_utc = appt_time - timedelta(hours=hours)

        # Do not schedule past reminders
        if target_sched_utc <= now_utc:
            logger.debug(
                "Skipping past reminder interval %s for appointment %s (scheduled: %s <= now: %s)",
                tag,
                appointment.id,
                target_sched_utc,
                now_utc,
            )
            continue

        # Prevent duplicate reminders for same appointment and interval
        existing = db.scalar(
            select(Reminder).where(
                Reminder.appointment_id == appointment.id,
                Reminder.interval_tag == tag,
                Reminder.status.in_(["pending", "calling", "retrying", "completed", "sent"]),
            )
        )
        if existing:
            logger.debug("Reminder for appointment %s interval %s already exists.", appointment.id, tag)
            continue

        message = generate_reminder_message(
            business_name=business.name,
            customer_name=customer.name,
            service_name=service.name if service else None,
            appointment_time_local=appt_local,
            language=lang,
        )

        reminder = Reminder(
            business_id=business.id,
            appointment_id=appointment.id,
            customer_id=customer.id,
            reminder_type=setting.default_channel,
            scheduled_time=target_sched_utc,
            status="pending",
            message=message,
            interval_tag=tag,
            max_retries=setting.max_retries,
            retry_count=0,
        )
        db.add(reminder)
        created_reminders.append(reminder)

    if created_reminders:
        db.commit()
        for r in created_reminders:
            db.refresh(r)
            logger.info(
                "Scheduled %s reminder (ID %s) for appointment %s at %s UTC",
                r.interval_tag,
                r.id,
                appointment.id,
                r.scheduled_time,
            )

    return created_reminders


def reschedule_appointment_reminders(
    db: Session,
    appointment: Appointment,
) -> list[Reminder]:
    """Recalculate scheduled_time and script for all active reminders after appointment rescheduling."""
    reminders = db.scalars(
        select(Reminder).where(
            Reminder.appointment_id == appointment.id,
            Reminder.status.in_(["pending", "retrying"]),
        )
    ).all()

    if not reminders:
        # If no pending reminders exist, attempt to schedule fresh ones
        return schedule_appointment_reminders(db, appointment)

    business = db.get(Business, appointment.business_id)
    customer = db.get(Customer, appointment.customer_id)
    service = db.get(Service, appointment.service_id) if appointment.service_id else None
    if not business:
        return []

    cfg = db.scalar(select(AssistantConfig).where(AssistantConfig.business_id == business.id))
    lang = cfg.language if cfg and cfg.language else "en-IN"

    appt_time = appointment.appointment_time
    if appt_time.tzinfo is None:
        appt_time = appt_time.replace(tzinfo=timezone.utc)

    biz_tz = get_business_timezone(business)
    appt_local = appt_time.astimezone(biz_tz)
    now_utc = datetime.now(timezone.utc)

    updated_list: list[Reminder] = []
    for rem in reminders:
        hours = 24
        if rem.interval_tag:
            match = re.search(r"\d+", rem.interval_tag)
            if match:
                hours = int(match.group())

        new_sched_utc = appt_time - timedelta(hours=hours)

        if new_sched_utc <= now_utc:
            rem.status = "cancelled"
            rem.customer_response = "rescheduled_past_interval"
        else:
            rem.scheduled_time = new_sched_utc
            rem.status = "pending"
            rem.retry_count = 0
            rem.next_retry_at = None
            rem.message = generate_reminder_message(
                business_name=business.name,
                customer_name=customer.name if customer else None,
                service_name=service.name if service else None,
                appointment_time_local=appt_local,
                language=lang,
            )
            updated_list.append(rem)

    db.commit()
    logger.info("Synchronized %d reminders after rescheduling appointment %s", len(updated_list), appointment.id)
    return updated_list


def cancel_appointment_reminders(
    db: Session,
    appointment_id: str,
) -> int:
    """Cancel all pending or retrying reminders when an appointment is cancelled."""
    reminders = db.scalars(
        select(Reminder).where(
            Reminder.appointment_id == appointment_id,
            Reminder.status.in_(["pending", "retrying", "calling"]),
        )
    ).all()

    count = 0
    for rem in reminders:
        rem.status = "cancelled"
        rem.customer_response = "appointment_cancelled"
        count += 1

    if count > 0:
        db.commit()
        logger.info("Cancelled %d reminders for cancelled appointment %s", count, appointment_id)

    return count
