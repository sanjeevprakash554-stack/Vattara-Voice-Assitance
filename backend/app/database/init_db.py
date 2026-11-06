"""Database initialization and realistic demo data seeding."""

from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.logging import get_logger
from app.core.security import get_password_hash
from app.database.base import Base
from app.database.connection import engine
from app.models.appointment import Appointment
from app.models.assistant import AssistantConfig, FAQ, Service
from app.models.business import Business
from app.models.call import Call
from app.models.customer import Customer
from app.models.reminder import Reminder
from app.models.user import User

logger = get_logger(__name__)


def init_db(db: Session) -> None:
    """Create all registered database tables and seed realistic demo data if empty."""
    # Ensure all tables exist on the active session's bind
    Base.metadata.create_all(bind=db.get_bind())

    # Check if a business already exists
    existing_business = db.scalar(select(Business).limit(1))
    if existing_business:
        logger.info("Database already initialized with business: %s", existing_business.name)
        return

    logger.info("Seeding initial demo data for Vattara Voice Assistance...")

    # 1. Create Demo Business
    business = Business(
        id="demo-biz-vattara-health",
        name="Vattara City Clinic & Diagnostics",
        vertical="clinic",
        phone="+91 44 2828 9000",
        email="contact@vattaraclinic.com",
        timezone="Asia/Kolkata",
        address="42, Anna Salai, Chennai, Tamil Nadu 600002",
        is_active=True,
    )
    db.add(business)

    # 2. Create Admin User
    admin_user = User(
        id="demo-user-admin",
        business_id=business.id,
        email="admin@vattara.com",
        full_name="Dr. Rajesh Kumar",
        hashed_password=get_password_hash("Admin@123"),
        role="admin",
        is_active=True,
    )
    db.add(admin_user)

    # 3. Create Assistant Configuration
    assistant_config = AssistantConfig(
        id="demo-assistant-config",
        business_id=business.id,
        assistant_name="Vattara Voice AI",
        language="en-US",
        voice="alloy",
        system_prompt=(
            "You are Vattara AI, the courteous and intelligent voice receptionist for "
            "Vattara City Clinic & Diagnostics. You handle patient triage, schedule appointments, "
            "explain consultation fees and clinical timings, and answer FAQs. Always be compassionate, "
            "precise, and professional."
        ),
        business_info=(
            "Vattara City Clinic & Diagnostics is a multi-specialty healthcare centre offering "
            "general physician consultations, cardiology checkups, pediatrics, and diagnostic lab services."
        ),
        working_hours=(
            '{"monday":{"open":"08:30","close":"20:00","enabled":true},'
            '"tuesday":{"open":"08:30","close":"20:00","enabled":true},'
            '"wednesday":{"open":"08:30","close":"20:00","enabled":true},'
            '"thursday":{"open":"08:30","close":"20:00","enabled":true},'
            '"friday":{"open":"08:30","close":"20:00","enabled":true},'
            '"saturday":{"open":"09:00","close":"18:00","enabled":true},'
            '"sunday":{"open":"10:00","close":"14:00","enabled":false}}'
        ),
        is_active=True,
    )
    db.add(assistant_config)

    # 4. Create Services
    services_data = [
        ("General Physician Consultation", "Routine health examination and diagnosis", 30, 500.0),
        ("Cardiology Consultation & ECG", "Comprehensive heart health evaluation", 45, 1200.0),
        ("Pediatric Health Checkup", "Complete child health and immunization review", 30, 700.0),
        ("Full Body Blood Diagnostics", "Complete blood count, lipid, and diabetes panel", 15, 1500.0),
        ("Dental Cleaning & Polish", "Preventative dental scaling and oral screening", 40, 800.0),
    ]
    service_objs = []
    for idx, (name, desc, duration, price) in enumerate(services_data, start=1):
        srv = Service(
            id=f"demo-service-{idx}",
            business_id=business.id,
            name=name,
            description=desc,
            duration_minutes=duration,
            price=price,
            is_active=True,
        )
        db.add(srv)
        service_objs.append(srv)

    # 5. Create FAQs
    faqs_data = [
        ("Appointments", "How do I book an appointment?", "You can book directly through this voice call, via our online portal, or by visiting our reception."),
        ("Consultation", "What is the consultation fee for a General Physician?", "Our General Physician consultation fee is ₹500."),
        ("Timings", "What are your outpatient clinic timings?", "We are open Monday to Friday 8:30 AM to 8:00 PM, and Saturday 9:00 AM to 6:00 PM."),
        ("Insurance", "Do you accept cashless health insurance?", "Yes, we support all major TPA and private health insurance cashless claims."),
        ("Emergency", "How are medical emergencies handled?", "Our triage unit provides immediate stabilization. For acute life-threatening situations, we coordinate immediate hospital ICU transfers."),
    ]
    for idx, (cat, q, a) in enumerate(faqs_data, start=1):
        faq = FAQ(
            id=f"demo-faq-{idx}",
            business_id=business.id,
            category=cat,
            question=q,
            answer=a,
            is_active=True,
        )
        db.add(faq)

    # 6. Create Customers
    customers_data = [
        ("Ananya Sharma", "+91 98401 23456", "ananya.sharma@example.com", "Patient has seasonal allergies."),
        ("Vikramaditya Raman", "+91 98840 98765", "vikram.raman@example.com", "Requires quarterly cardiac follow-up."),
        ("Meera Swaminathan", "+91 94441 55678", "meera.s@example.com", "Prefers morning slots for pediatric visits."),
        ("Karthik Natarajan", "+91 97910 11223", "karthik.n@example.com", "Regular dental hygiene checkups."),
        ("Priya Sundaram", "+91 99620 44332", "priya.s@example.com", "Requested diagnostic report copy over WhatsApp."),
    ]
    customer_objs = []
    for idx, (c_name, c_phone, c_email, c_notes) in enumerate(customers_data, start=1):
        cust = Customer(
            id=f"demo-customer-{idx}",
            business_id=business.id,
            name=c_name,
            phone=c_phone,
            email=c_email,
            notes=c_notes,
            total_calls=2,
            total_appointments=1,
        )
        db.add(cust)
        customer_objs.append(cust)

    now = datetime.now(timezone.utc)

    # 7. Create Calls
    calls_data = [
        (customer_objs[0], "incoming", "completed", 168, "Inquired about Saturday morning cardiology slots and booked consultation.", "Patient called to inquire about cardiologist availability on Saturday. AI confirmed Dr. Raghavan has an open slot at 10:30 AM. Patient confirmed booking."),
        (customer_objs[1], "incoming", "completed", 195, "Asked about fasting requirements for complete blood lipid panel.", "Caller wanted clarification on lipid test fasting duration. AI stated 10-12 hours fasting required and water is allowed."),
        (customer_objs[2], "outgoing", "completed", 84, "Automated voice reminder for upcoming pediatric vaccination.", "Outbound call dispatched by AI assistant reminding parent of scheduled measles booster at 11:00 AM tomorrow."),
        (None, "incoming", "missed", 0, "Missed incoming call after clinic hours.", "Caller disconnected after 4 rings during night hours. Logged for morning callback triage.", "+91 98412 88990", "Unknown Caller"),
        (customer_objs[3], "incoming", "completed", 142, "Rescheduled dental cleaning from Thursday to Friday afternoon.", "Customer requested reschedule due to travel conflict. AI updated booking to Friday 3:00 PM without friction."),
        (customer_objs[4], "outgoing", "completed", 95, "Diagnostic report delivery notification.", "Outbound automated notification alerting patient that lab test reports are ready for pickup or email download."),
    ]

    for idx, item in enumerate(calls_data, start=1):
        c_cust = item[0]
        c_type = item[1]
        c_status = item[2]
        c_dur = item[3]
        c_summary = item[4]
        c_trans = item[5]
        c_phone = item[6] if len(item) > 6 else c_cust.phone
        c_name = item[7] if len(item) > 7 else c_cust.name

        call = Call(
            id=f"demo-call-{idx}",
            business_id=business.id,
            customer_id=c_cust.id if c_cust else None,
            caller_name=c_name,
            caller_phone=c_phone,
            call_type=c_type,
            status=c_status,
            duration_seconds=c_dur,
            summary=c_summary,
            transcript=c_trans,
            recording_url="https://sample-audio.vattara.ai/recordings/demo-call.mp3",
            initiated_at=now - timedelta(hours=idx * 4),
            ended_at=now - timedelta(hours=idx * 4) + timedelta(seconds=c_dur),
        )
        db.add(call)

    # 8. Create Appointments
    appointments_data = [
        (customer_objs[0], service_objs[1], now + timedelta(days=1, hours=2), "upcoming", "ai_call", "Referred by Dr. Rajesh for cardiac ECG checkup."),
        (customer_objs[1], service_objs[3], now + timedelta(days=2, hours=4), "upcoming", "ai_call", "Fasting blood test profile."),
        (customer_objs[2], service_objs[2], now - timedelta(days=2), "completed", "manual", "Routine 18-month vaccination administered."),
        (customer_objs[3], service_objs[4], now + timedelta(days=3, hours=1), "upcoming", "ai_call", "Rescheduled dental cleaning slot."),
        (customer_objs[4], service_objs[0], now - timedelta(days=5), "cancelled", "ai_call", "Cancelled by patient due to work schedule."),
    ]
    appt_objs = []
    for idx, (cust, srv, a_time, a_status, a_src, notes) in enumerate(appointments_data, start=1):
        appt = Appointment(
            id=f"demo-appointment-{idx}",
            business_id=business.id,
            customer_id=cust.id,
            service_id=srv.id if srv else None,
            appointment_time=a_time,
            end_time=a_time + timedelta(minutes=srv.duration_minutes if srv else 30),
            status=a_status,
            notes=notes,
            source=a_src,
        )
        db.add(appt)
        appt_objs.append(appt)

    # 9. Create Reminders
    reminders_data = [
        (customer_objs[0], appt_objs[0], "sms", now + timedelta(hours=18), "pending", "Reminder: Your Cardiology Consultation is scheduled for tomorrow at 10:30 AM at Vattara City Clinic."),
        (customer_objs[1], appt_objs[1], "voice", now + timedelta(days=1, hours=12), "pending", "Automated Voice Reminder: Fasting blood profile scheduled for Friday morning at Vattara Diagnostics."),
        (customer_objs[2], appt_objs[2], "sms", now - timedelta(days=2, hours=12), "sent", "Reminder: Pediatric Checkup today at 11:00 AM."),
        (customer_objs[3], appt_objs[3], "sms", now + timedelta(days=2), "pending", "Reminder: Dental Cleaning scheduled for Saturday at 3:00 PM."),
    ]
    for idx, (cust, appt, r_type, s_time, r_status, msg) in enumerate(reminders_data, start=1):
        rem = Reminder(
            id=f"demo-reminder-{idx}",
            business_id=business.id,
            appointment_id=appt.id if appt else None,
            customer_id=cust.id,
            reminder_type=r_type,
            scheduled_time=s_time,
            status=r_status,
            message=msg,
            sent_at=now - timedelta(days=2) if r_status == "sent" else None,
        )
        db.add(rem)

    db.commit()
    logger.info("Demo database seeding complete!")
