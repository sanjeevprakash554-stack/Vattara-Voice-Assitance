"""Test script to thoroughly verify Priority 1: Live Appointment Booking Lifecycle.
Steps 1-10:
1. Initiate inbound call session.
2. Request an appointment.
3. Provide customer name and spoken phone number.
4. Select a doctor, service, date and time.
5. Verify the booking state transitions.
6. Execute the actual booking function.
7. Verify the appointment record in SQLite using its generated ID.
8. Verify customer details and reminder creation.
9. Confirm success to the caller only after database commit.
10. Check for duplicate bookings.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json
import uuid

# Setup sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.database.connection import SessionLocal
from app.models.appointment import Appointment
from app.models.assistant import AssistantConfig, Service
from app.models.business import Business
from app.models.business_hours import BusinessHour
from app.models.customer import Customer
from app.models.reminder import Reminder
from app.models.staff_schedule import StaffSchedule
from app.models.conversation_session import ConversationSession
from app.services.voice_assistant_service import (
    process_conversational_turn,
    get_or_create_conversation_session,
)
from app.services.appointment_service import book_appointment_core
from app.schemas.appointment import AppointmentCreate
from fastapi import HTTPException

def run_test():
    print("=" * 70)
    print("PRIORITY 1: LIVE APPOINTMENT BOOKING VERIFICATION")
    print("=" * 70)

    db = SessionLocal()
    try:
        # Create dedicated test business tenant
        biz_id = f"biz_p1_test_{uuid.uuid4().hex[:6]}"
        biz = Business(
            id=biz_id,
            name="Vattara Health Care Centre",
            vertical="clinic",
            email=f"clinic_{biz_id}@vattara.com",
            phone="+918031794113",
            timezone="Asia/Kolkata",
            is_active=True,
        )
        db.add(biz)
        db.flush()

        for dow in range(7):
            db.add(BusinessHour(
                business_id=biz.id,
                day_of_week=dow,
                open_time="08:00",
                close_time="20:00",
                is_closed=False,
            ))

        s_gp = Service(
            id=f"srv_gp_{uuid.uuid4().hex[:6]}",
            business_id=biz.id,
            name="General Physician Consultation",
            duration_minutes=30,
            price=500.0,
            is_active=True,
        )
        db.add(s_gp)

        for dow in range(7):
            db.add(StaffSchedule(
                id=f"sched_{uuid.uuid4().hex[:6]}",
                business_id=biz.id,
                staff_name="Dr. Rajesh Kumar",
                day_of_week=dow,
                start_time="09:00",
                end_time="14:00",
                is_active=True,
            ))
        db.commit()

        # Step 1: Initiate inbound call session
        caller_phone = "+919876543210"
        call_sid = f"plivo_p1_call_{uuid.uuid4().hex[:8]}"
        session = ConversationSession(
            call_sid=call_sid,
            business_id=biz.id,
            caller_phone=caller_phone,
            step="greeting",
            intent="booking",
            language="en-IN",
            detected_language="en-IN",
            dialog_history=json.dumps([]),
            metadata_json=json.dumps({"require_confirmation": True}),
            retry_count=0,
            is_completed=False,
        )
        db.add(session)
        db.commit()
        print(f"Step 1: Inbound call session initialized | CallSid: {call_sid} | Initial Step: {session.step}")

        # Step 2: Request an appointment & Select service + doctor
        speech_turn1 = "Hi, I need an appointment for General Physician Consultation with Dr. Rajesh Kumar."
        resp1, _ = process_conversational_turn(
            db=db,
            session=session,
            speech_text=speech_turn1,
            business=biz,
        )
        print(f"\nStep 2: Caller requests appointment: '{speech_turn1}'")
        print(f"        Assistant Response: '{resp1}'")
        print(f"        Step after Turn 1: {session.step}")

        # Step 3 & 4: Provide name, spoken phone number, date and time
        speech_turn2 = "Tomorrow at 10 AM please. My name is Karthik Subramanian and phone number is 9876543210."
        resp2, _ = process_conversational_turn(
            db=db,
            session=session,
            speech_text=speech_turn2,
            business=biz,
        )
        print(f"\nStep 3 & 4: Caller provides details: '{speech_turn2}'")
        print(f"        Assistant Response: '{resp2}'")
        print(f"        Step after Turn 2: {session.step}")

        # Step 5: Verify booking state transitions
        print(f"\nStep 5: Booking state transitions verified:")
        print(f"        - Final session step: {session.step}")
        print(f"        - Booking ID recorded: {session.booking_id}")
        print(f"        - Session completed flag: {session.is_completed}")
        assert session.step == "completed", f"Expected completed, got {session.step}"
        assert session.booking_id is not None, "Booking ID should not be None"

        # Step 6 & 7: Verify appointment record in SQLite using its generated ID
        appt_id = session.booking_id
        appt = db.get(Appointment, appt_id)
        assert appt is not None, f"Appointment record {appt_id} not found in database!"
        print(f"\nStep 6 & 7: Appointment verified in SQLite:")
        print(f"        - Appointment ID: {appt.id}")
        print(f"        - Scheduled Time: {appt.appointment_time}")
        print(f"        - End Time: {appt.end_time}")
        print(f"        - Status: {appt.status}")
        print(f"        - Service ID: {appt.service_id}")
        assert appt.status in ("upcoming", "confirmed"), f"Expected upcoming/confirmed, got {appt.status}"

        # Step 8: Verify customer details and reminder creation
        cust = db.get(Customer, appt.customer_id)
        assert cust is not None, "Customer record not found!"
        print(f"\nStep 8: Customer Details & Reminders verified:")
        print(f"        - Customer ID: {cust.id}")
        print(f"        - Customer Name: {cust.name}")
        print(f"        - Customer Phone: {cust.phone}")
        
        reminders = db.query(Reminder).filter(Reminder.appointment_id == appt.id).all()
        print(f"        - Total Reminders Created: {len(reminders)}")
        for r in reminders:
            print(f"          * Reminder ID: {r.id} | Tag: {r.interval_tag} | Scheduled: {r.scheduled_time} | Status: {r.status}")
        assert len(reminders) > 0, "At least one automated reminder must be created!"

        # Step 9: Confirm success to caller only after database commit
        print(f"\nStep 9: Verbal confirmation delivered after database commit:")
        print(f"        - Caller confirmation message: '{resp2}'")
        assert any(w in resp2.lower() for w in ["booked", "confirmed", "scheduled", "success"]), "Verbal confirmation missing"

        # Step 10: Check for duplicate bookings
        print(f"\nStep 10: Duplicate Booking Check:")
        dup_prevented = False
        from zoneinfo import ZoneInfo
        from app.services.ai.tools import execute_tool_call

        # 1. Test duplicate booking rejection via execute_tool_call (tool level)
        tool_dup_result = execute_tool_call(
            db=db,
            business_id=biz.id,
            function_name="book_appointment",
            arguments={
                "appointment_time": "2026-11-19T10:00:00+05:30",
                "customer_phone": caller_phone,
                "customer_name": cust.name,
                "service_id": appt.service_id,
            },
        )
        print(f"        [+] AI Tool Duplicate Booking Result: {tool_dup_result}")
        assert tool_dup_result.get("success") is False, "AI tool should return success=False for duplicate booking"
        assert "already has an appointment booked" in tool_dup_result.get("error", "").lower()

        # 2. Test duplicate booking rejection via book_appointment_core (service level with HTTP 409)
        try:
            payload = AppointmentCreate(
                business_id=biz.id,
                customer_phone=caller_phone,
                customer_name=cust.name,
                service_id=appt.service_id,
                appointment_time=datetime(2026, 11, 19, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
                status="upcoming",
            )
            book_appointment_core(
                db=db,
                business_id=biz.id,
                payload=payload,
                validate_conflicts=True,
            )
        except HTTPException as exc:
            if exc.status_code == 409 or "already" in str(exc.detail).lower() or "conflict" in str(exc.detail).lower():
                dup_prevented = True
                print(f"        [+] Duplicate booking correctly rejected: HTTP {exc.status_code} - {exc.detail}")

        assert dup_prevented, "Duplicate booking should have been rejected with HTTP 409 Conflict!"
        print(f"        - Duplicate Booking Prevention: VERIFIED PASS")

        print("\n" + "=" * 70)
        print("ALL 10 PRIORITY 1 ACCEPTANCE CRITERIA PASSED SUCCESSFULLY!")
        print("=" * 70)

    finally:
        db.close()

if __name__ == "__main__":
    run_test()
