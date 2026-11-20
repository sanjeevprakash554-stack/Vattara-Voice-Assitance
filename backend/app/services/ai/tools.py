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
from app.models.business import Business
from app.models.business_hours import BusinessHour
from app.models.customer import Customer
from app.models.staff_schedule import StaffSchedule
from app.schemas.appointment import AppointmentCreate
from app.services.appointment_service import book_appointment_core
from app.services.dashboard_events import dashboard_event_manager
from app.services.scheduling_service import (
    calculate_available_slots,
    cancel_appointment_core,
    find_alternative_slots,
    get_all_operating_hours,
    get_business_timezone,
    reschedule_appointment_core,
)
from app.services.telephony.phone_utils import normalize_indian_mobile_number

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
            "name": "get_doctors",
            "description": "Retrieve list of doctors, staff members, specialties, and their working schedules.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_name": {
                        "type": "string",
                        "description": "Optional name or specialty of a specific doctor to query.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_business_info",
            "description": "Retrieve clinic or business information such as address, contact phone, email, facilities, and general clinic overview.",
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
    {
        "type": "function",
        "function": {
            "name": "get_medical_information",
            "description": "Retrieve medically reviewed clinical guidance, safe home care, red flag warnings, relevant diagnostic tests, and doctor department recommendations for symptoms or health queries. Grounded in WHO, MoHFW, and ICMR protocols.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The symptom, medical condition, or clinical question mentioned by the caller (e.g., 'fever and cough', 'diabetes checkup', 'HbA1c test', 'headache', 'skin rash', 'child fever').",
                    },
                    "caller_language": {
                        "type": "string",
                        "description": "Optional caller language code (e.g. 'ta-Latn', 'ta-IN', 'en-IN').",
                    },
                },
                "required": ["query"],
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

            business = db.get(Business, business_id)
            biz_tz = get_business_timezone(business) if business else timezone.utc
            if parsed_dt.tzinfo is None:
                parsed_dt = parsed_dt.replace(tzinfo=biz_tz)

            raw_phone = arguments.get("customer_phone")
            norm_phone = normalize_indian_mobile_number(raw_phone) if raw_phone else None

            booking_payload = AppointmentCreate(
                customer_name=arguments.get("customer_name"),
                customer_phone=norm_phone or raw_phone,
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
                # Idempotency check: if customer already booked this exact slot (e.g. retry during turn), return existing appointment
                if exc.status_code == 409 and "already has an appointment" in str(exc.detail).lower() and booking_payload.customer_phone:
                    from app.services.scheduling_service import ACTIVE_APPOINTMENT_STATUSES
                    existing_appt = (
                        db.query(Appointment)
                        .join(Customer, Appointment.customer_id == Customer.id)
                        .filter(
                            Appointment.business_id == business_id,
                            Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
                            Customer.phone == booking_payload.customer_phone.strip(),
                        )
                        .order_by(Appointment.created_at.desc())
                        .first()
                    )
                    if existing_appt:
                        logger.info("Idempotent booking hit for CallSid %s: Reusing existing appointment ID %s", arguments.get("call_id"), existing_appt.id)
                        return {
                            "success": True,
                            "appointment_id": existing_appt.id,
                            "customer_name": booking_payload.customer_name,
                            "service_name": getattr(existing_appt.service, "name", "Consultation") if existing_appt.service else "Consultation",
                            "appointment_time": existing_appt.appointment_time.isoformat(),
                            "status": existing_appt.status,
                            "already_booked": True,
                            "message": f"Appointment already confirmed with ID {existing_appt.id}.",
                        }

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
            raw_phone = arguments.get("customer_phone", "").strip()
            customer_phone = normalize_indian_mobile_number(raw_phone) or raw_phone
            phone_variants = [customer_phone]
            if customer_phone.startswith("+91"):
                phone_variants.extend([customer_phone.replace("+91", "91"), customer_phone.replace("+91", "")])
            elif customer_phone.startswith("91"):
                phone_variants.extend([f"+{customer_phone}", customer_phone[2:]])

            new_time_raw = arguments.get("new_appointment_time") or arguments.get("new_date_time")
            appointment_id = arguments.get("appointment_id")
            reason = arguments.get("reason", "Customer requested reschedule via voice AI.")

            if not new_time_raw:
                return {"error": "Missing 'new_appointment_time'."}

            try:
                new_dt = datetime.fromisoformat(new_time_raw)
            except ValueError:
                return {"error": f"Invalid ISO datetime '{new_time_raw}'."}

            business = db.get(Business, business_id)
            biz_tz = get_business_timezone(business) if business else timezone.utc
            if new_dt.tzinfo is None:
                new_dt = new_dt.replace(tzinfo=biz_tz)

            # If appointment_id is not given, find the most recent active appointment for customer
            if not appointment_id and customer_phone:
                active_appt = db.scalar(
                    select(Appointment)
                    .join(Customer, Appointment.customer_id == Customer.id)
                    .where(
                        Appointment.business_id == business_id,
                        Customer.phone.in_(phone_variants),
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
            raw_phone = arguments.get("customer_phone", "").strip()
            customer_phone = normalize_indian_mobile_number(raw_phone) or raw_phone
            phone_variants = [customer_phone]
            if customer_phone.startswith("+91"):
                phone_variants.extend([customer_phone.replace("+91", "91"), customer_phone.replace("+91", "")])
            elif customer_phone.startswith("91"):
                phone_variants.extend([f"+{customer_phone}", customer_phone[2:]])

            appointment_id = arguments.get("appointment_id")
            reason = arguments.get("reason", "Customer requested cancellation via voice AI.")

            # If appointment_id not given, locate active appointment by phone
            if not appointment_id and customer_phone:
                active_appt = db.scalar(
                    select(Appointment)
                    .join(Customer, Appointment.customer_id == Customer.id)
                    .where(
                        Appointment.business_id == business_id,
                        Customer.phone.in_(phone_variants),
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

        # 7. Get Doctors / Staff
        elif function_name == "get_doctors":
            doc_query = (arguments.get("doctor_name") or "").strip().lower()
            stmt = select(StaffSchedule).where(
                StaffSchedule.business_id == business_id,
                StaffSchedule.is_active.is_(True),
            )
            schedules = db.scalars(stmt).all()
            day_map = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"}

            doctors_map: dict[str, dict[str, Any]] = {}
            for s in schedules:
                if doc_query and doc_query not in s.staff_name.lower():
                    continue
                if s.staff_name not in doctors_map:
                    doctors_map[s.staff_name] = {
                        "name": s.staff_name,
                        "slot_duration_minutes": s.slot_duration_minutes,
                        "available_days": [],
                    }
                doctors_map[s.staff_name]["available_days"].append({
                    "day": day_map.get(s.day_of_week, str(s.day_of_week)),
                    "start": s.start_time,
                    "end": s.end_time,
                })

            doctors_list = list(doctors_map.values())
            if not doctors_list:
                doctors_list = [{"name": "Duty Medical Practitioner / Pediatrician", "availability": "Regular clinic operating hours"}]
            return {"doctors": doctors_list}

        # 8. Get Business Info
        elif function_name == "get_business_info":
            biz = db.scalar(select(Business).where(Business.id == business_id))
            assistant = db.scalar(select(AssistantConfig).where(AssistantConfig.business_id == business_id))
            if not biz:
                return {"error": "Business not found."}
            return {
                "name": biz.name,
                "vertical": biz.vertical,
                "phone": biz.phone,
                "email": biz.email,
                "address": biz.address or "Address on file",
                "timezone": biz.timezone,
                "business_info": assistant.business_info if assistant and assistant.business_info else None,
            }

        # 9. Get Medical Information
        elif function_name == "get_medical_information":
            from app.services.ai.medical_knowledge import (
                get_medical_guidance_for_response,
                query_medical_knowledge,
            )

            query = (arguments.get("query") or "").strip()
            caller_lang = arguments.get("caller_language", "en-IN")
            if not query:
                return {"error": "Missing 'query' parameter."}

            topic = query_medical_knowledge(query, caller_lang)
            if not topic:
                return {
                    "found": False,
                    "message": "No specific clinical guideline matched. Recommend direct doctor consultation for physical examination.",
                    "recommended_specialty": "General Physician",
                }

            services = db.scalars(
                select(Service).where(Service.business_id == business_id, Service.is_active.is_(True))
            ).all()
            srv_dicts = [
                {"id": s.id, "name": s.name, "price": s.price, "duration_minutes": s.duration_minutes}
                for s in services
            ]
            staff = db.scalars(
                select(StaffSchedule).where(StaffSchedule.business_id == business_id, StaffSchedule.is_active.is_(True))
            ).all()
            staff_dicts = [{"name": s.staff_name, "specialty": s.staff_name} for s in staff]

            guidance = get_medical_guidance_for_response(
                topic=topic,
                language=caller_lang,
                matching_services=srv_dicts,
                matching_doctors=staff_dicts,
            )
            return {
                "found": True,
                "topic": topic.id,
                "category": topic.category,
                "specialty": topic.recommended_specialty,
                "explanation": guidance["explanation"],
                "home_care": guidance["home_care"],
                "red_flags": guidance["red_flags"],
                "triage_question": guidance["triage_question"],
                "disclaimer": guidance["disclaimer"],
                "relevant_tests": guidance["relevant_tests"],
                "matched_service": guidance["matched_service"],
                "matched_doctor": guidance["matched_doctor"],
                "source": guidance["source"],
            }

        else:
            return {"error": f"Unknown function '{function_name}'."}

    except Exception as e:
        logger.error("Error executing tool %s: %s", function_name, e, exc_info=True)
        return {"error": str(e)}
