"""AI Function Calling (Tools) definitions and execution dispatcher for Phase 2 Scheduling Engine."""

from datetime import date, datetime, timezone
import json
from typing import Any
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from fastapi import HTTPException
from app.core.logging import get_logger
from app.models.appointment import Appointment
from app.models.assistant import AssistantConfig, Service
from app.models.availability import (
    BusinessBreak,
    BusinessHoliday,
    SpecialDateOverride,
)
from app.models.business_hours import BusinessHour
from app.models.customer import Customer
from app.schemas.appointment import AppointmentCreate
from app.services.appointment_service import book_appointment_core
from app.services.dashboard_events import dashboard_event_manager
from app.services.scheduling_service import (
    calculate_available_slots,
    cancel_appointment_core,
    find_alternative_slots,
    get_all_operating_hours,
    reschedule_appointment_core,
)

logger = get_logger(__name__)

# Standard JSON schema declarations for LLM function calling
AI_TOOLS_SPEC: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "check_available_slots",
            "description": "Query live database for available appointment slots on a given date. NEVER hallucinate slots without calling this tool.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "The target date in YYYY-MM-DD format (e.g., '2026-11-12').",
                    },
                    "service_id": {
                        "type": "string",
                        "description": "Optional service ID to calculate duration-specific slots.",
                    },
                    "staff_id": {
                        "type": "string",
                        "description": "Optional doctor or staff member ID.",
                    },
                },
                "required": ["date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Finalize and commit a new appointment in the database once customer details and slot are chosen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string", "description": "Full name of the caller/patient."},
                    "customer_phone": {"type": "string", "description": "Caller phone number with country code."},
                    "service_id": {"type": "string", "description": "ID of the requested service from catalog."},
                    "appointment_time": {
                        "type": "string",
                        "description": "Selected ISO 8601 appointment datetime (e.g., '2026-11-12T10:30:00+05:30').",
                    },
                    "notes": {"type": "string", "description": "Optional notes or chief symptoms."},
                },
                "required": ["customer_name", "customer_phone", "appointment_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_appointment",
            "description": "Reschedule an existing active appointment to a new date and time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_phone": {"type": "string", "description": "Customer phone number to look up their appointment."},
                    "new_appointment_time": {
                        "type": "string",
                        "description": "The new target ISO 8601 appointment datetime (e.g., '2026-11-14T14:00:00+05:30').",
                    },
                    "appointment_id": {"type": "string", "description": "Optional specific appointment ID if known."},
                    "reason": {"type": "string", "description": "Reason for rescheduling."},
                },
                "required": ["customer_phone", "new_appointment_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancel an existing active appointment and immediately free up the slot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_phone": {"type": "string", "description": "Customer phone number to look up active appointment."},
                    "appointment_id": {"type": "string", "description": "Optional specific appointment ID if known."},
                    "reason": {"type": "string", "description": "Reason for cancellation."},
                },
                "required": ["customer_phone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_services_and_hours",
            "description": "Retrieve current clinic services list, prices, and weekly operating hours.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "transfer_to_human",
            "description": "Transfer caller to human receptionist or emergency contact desk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Reason for transferring to human staff."},
                },
            },
        },
    },
]


def execute_tool_call(
    db: Session,
    business_id: str,
    function_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Execute a function call requested by the AI engine against live Phase 2 services."""
    logger.info("Executing AI tool '%s' for business %s with args: %s", function_name, business_id, arguments)

    try:
        # 1. Check Available Slots
        if function_name == "check_available_slots":
            date_str = arguments.get("date")
            if not date_str:
                return {"error": "Missing required 'date' argument (YYYY-MM-DD)."}

            try:
                target_date = date.fromisoformat(date_str)
            except ValueError:
                return {"error": f"Invalid date format '{date_str}'. Expected YYYY-MM-DD."}

            service_id = arguments.get("service_id")
            staff_id = arguments.get("staff_id")

            availability = calculate_available_slots(
                db=db,
                business_id=business_id,
                target_date=target_date,
                service_id=service_id,
                staff_id=staff_id,
            )

            # Return concise summary for LLM context
            available_times = [s.time for s in availability.slots if s.available]
            result = {
                "date": date_str,
                "is_open": availability.is_open,
                "service_name": availability.service_name,
                "duration_minutes": availability.duration_minutes,
                "available_slots_count": availability.available_slots_count,
                "available_slots": available_times[:12],  # Provide up to first 12 slots to prevent token blowup
                "operating_hours": f"{availability.operating_hours.get('open')} - {availability.operating_hours.get('close')}",
            }
            if not availability.is_open or availability.available_slots_count == 0:
                alternatives = find_alternative_slots(
                    db=db,
                    business_id=business_id,
                    target_date=target_date,
                    service_id=service_id,
                    staff_id=staff_id,
                    limit_per_day=3,
                    days_ahead=5,
                )
                if alternatives:
                    result["alternative_suggestions"] = alternatives
            return result

        # 2. Book Appointment
        elif function_name == "book_appointment":
            appt_time_raw = arguments.get("appointment_time")
            if not appt_time_raw:
                return {"error": "Missing 'appointment_time'."}

            try:
                parsed_dt = datetime.fromisoformat(appt_time_raw)
            except ValueError:
                return {"error": f"Invalid ISO datetime '{appt_time_raw}'."}

            booking_payload = AppointmentCreate(
                customer_name=arguments.get("customer_name"),
                customer_phone=arguments.get("customer_phone"),
                service_id=arguments.get("service_id"),
                appointment_time=parsed_dt,
                source="ai_call",
                notes=arguments.get("notes") or "Booked autonomously by AI Receptionist.",
            )

            has_configured_availability = (
                db.scalar(select(BusinessHour.id).where(BusinessHour.business_id == business_id).limit(1)) is not None
                or db.scalar(select(BusinessBreak.id).where(BusinessBreak.business_id == business_id).limit(1)) is not None
                or db.scalar(select(BusinessHoliday.id).where(BusinessHoliday.business_id == business_id).limit(1)) is not None
                or db.scalar(select(SpecialDateOverride.id).where(SpecialDateOverride.business_id == business_id).limit(1)) is not None
            )

            try:
                appt = book_appointment_core(
                    db=db,
                    business_id=business_id,
                    payload=booking_payload,
                    validate_conflicts=True,
                    enforce_operating_hours=has_configured_availability,
                    enforce_past_check=True,
                )
            except HTTPException as exc:
                alternatives = find_alternative_slots(
                    db=db,
                    business_id=business_id,
                    target_date=parsed_dt.date(),
                    service_id=booking_payload.service_id,
                    limit_per_day=3,
                    days_ahead=5,
                )
                return {
                    "success": False,
                    "error": exc.detail,
                    "alternative_suggestions": alternatives,
                }

            dashboard_event_manager.dispatch(
                business_id=business_id,
                event_type="APPOINTMENT_CREATED",
                data={
                    "appointment_id": appt.id,
                    "customer_name": arguments.get("customer_name"),
                    "customer_phone": arguments.get("customer_phone"),
                    "service_id": appt.service_id,
                    "appointment_time": appt.appointment_time.isoformat(),
                    "status": appt.status,
                    "source": "voice_ai",
                },
            )

            return {
                "success": True,
                "appointment_id": appt.id,
                "status": appt.status,
                "customer_name": arguments.get("customer_name"),
                "appointment_time": appt.appointment_time.isoformat(),
                "end_time": appt.end_time.isoformat() if appt.end_time else None,
                "service_id": appt.service_id,
            }

        # 3. Reschedule Appointment
        elif function_name == "reschedule_appointment":
            customer_phone = arguments.get("customer_phone", "").strip()
            new_time_raw = arguments.get("new_appointment_time")
            appointment_id = arguments.get("appointment_id")
            reason = arguments.get("reason", "Customer requested reschedule via voice AI.")

            if not new_time_raw:
                return {"error": "Missing 'new_appointment_time'."}

            try:
                new_dt = datetime.fromisoformat(new_time_raw)
            except ValueError:
                return {"error": f"Invalid ISO datetime '{new_time_raw}'."}

            # If appointment_id is not given, find the most recent active appointment for customer
            if not appointment_id and customer_phone:
                active_appt = db.scalar(
                    select(Appointment)
                    .join(Customer, Appointment.customer_id == Customer.id)
                    .where(
                        Appointment.business_id == business_id,
                        Customer.phone == customer_phone,
                        Appointment.status.in_(["upcoming", "confirmed", "rescheduled"]),
                    )
                    .order_by(Appointment.appointment_time.asc())
                )
                if not active_appt:
                    return {"error": f"No active appointment found for phone number {customer_phone} to reschedule."}
                appointment_id = active_appt.id

            if not appointment_id:
                return {"error": "Could not identify an active appointment to reschedule."}

            try:
                rescheduled = reschedule_appointment_core(
                    db=db,
                    business_id=business_id,
                    appointment_id=appointment_id,
                    new_appointment_time=new_dt,
                    reason=reason,
                )
            except HTTPException as exc:
                alternatives = find_alternative_slots(
                    db=db,
                    business_id=business_id,
                    target_date=new_dt.date(),
                    limit_per_day=3,
                    days_ahead=5,
                )
                return {
                    "success": False,
                    "error": exc.detail,
                    "alternative_suggestions": alternatives,
                }

            dashboard_event_manager.dispatch(
                business_id=business_id,
                event_type="APPOINTMENT_UPDATED",
                data={
                    "appointment_id": rescheduled.id,
                    "status": rescheduled.status,
                    "appointment_time": rescheduled.appointment_time.isoformat(),
                    "reason": rescheduled.reschedule_reason,
                },
            )

            return {
                "success": True,
                "appointment_id": rescheduled.id,
                "status": rescheduled.status,
                "new_appointment_time": rescheduled.appointment_time.isoformat(),
                "end_time": rescheduled.end_time.isoformat() if rescheduled.end_time else None,
                "reschedule_reason": rescheduled.reschedule_reason,
            }

        # 4. Cancel Appointment
        elif function_name == "cancel_appointment":
            customer_phone = arguments.get("customer_phone", "").strip()
            appointment_id = arguments.get("appointment_id")
            reason = arguments.get("reason", "Customer requested cancellation via voice AI.")

            # If appointment_id not given, locate active appointment by phone
            if not appointment_id and customer_phone:
                active_appt = db.scalar(
                    select(Appointment)
                    .join(Customer, Appointment.customer_id == Customer.id)
                    .where(
                        Appointment.business_id == business_id,
                        Customer.phone == customer_phone,
                        Appointment.status.in_(["upcoming", "confirmed", "rescheduled"]),
                    )
                    .order_by(Appointment.appointment_time.asc())
                )
                if not active_appt:
                    return {"error": f"No active appointment found for phone number {customer_phone} to cancel."}
                appointment_id = active_appt.id

            if not appointment_id:
                return {"error": "Could not identify an active appointment to cancel."}

            cancelled = cancel_appointment_core(
                db=db,
                business_id=business_id,
                appointment_id=appointment_id,
                reason=reason,
            )

            dashboard_event_manager.dispatch(
                business_id=business_id,
                event_type="APPOINTMENT_UPDATED",
                data={
                    "appointment_id": cancelled.id,
                    "status": cancelled.status,
                    "reason": reason,
                },
            )

            return {
                "success": True,
                "appointment_id": cancelled.id,
                "status": cancelled.status,
                "cancel_reason": cancelled.cancel_reason,
            }

        # 5. Get Services & Hours
        elif function_name == "get_services_and_hours":
            services = db.scalars(
                select(Service).where(Service.business_id == business_id, Service.is_active.is_(True))
            ).all()
            schedule = get_all_operating_hours(db, business_id)

            return {
                "services": [
                    {"id": s.id, "name": s.name, "duration_minutes": s.duration_minutes, "price": s.price}
                    for s in services
                ],
                "operating_schedule": [
                    {"day": h.day_name, "open": h.open_time, "close": h.close_time, "closed": h.is_closed}
                    for h in schedule
                ],
            }

        # 6. Transfer to Human Receptionist
        elif function_name == "transfer_to_human":
            reason = arguments.get("reason", "Caller requested human assistance.")
            assistant = db.scalar(select(AssistantConfig).where(AssistantConfig.business_id == business_id))
            fallback_num = assistant.fallback_number if assistant else None
            return {
                "success": True,
                "action": "transfer",
                "transfer_number": fallback_num,
                "reason": reason,
                "message": "Transferring call to clinic front desk receptionist.",
            }

        else:
            return {"error": f"Unknown function '{function_name}'."}

    except Exception as e:
        logger.error("Error executing tool %s: %s", function_name, e, exc_info=True)
        return {"error": str(e)}
