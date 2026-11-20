"""Automated Test Suite for Intelligent AI Voice Receptionist Engine (Phases 1-10).

Verifies:
- Phase 1: All 16 Intent Categories classification.
- Phase 2: Natural mid-workflow question answering.
- Phase 3: Tenant-specific business knowledge base (services, hours, staff, FAQs, policies).
- Phase 4: Unrelated question handling (PM of India, AI definition, joke, capital, weather).
- Phase 5: Medical safety boundaries (emergency triage, non-prescribing).
- Phase 6: Full multi-turn conversation context retention across topic switches.
- Phase 7: Natural voice optimization (no markdown, spoken currency, concise sentences).
- Phase 8: Unknown questions and human front desk escalation/callbacks.
- Phase 9: Clean architecture and modular handlers.
- Phase 10: Complete end-to-end booking verification with database persistence.
"""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import json
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.assistant import AssistantConfig, FAQ, Service
from app.models.business import Business
from app.models.business_hours import BusinessHour
from app.models.conversation_session import ConversationSession
from app.models.customer import Customer
from app.models.staff_schedule import StaffSchedule
from app.services.ai.natural_receptionist import (
    answer_complaint_query,
    answer_doctor_staff_query,
    answer_payment_methods_query,
    answer_pricing_query,
    answer_unknown_question,
    answer_unrelated_general_query,
    check_medical_advice_request,
    check_medical_emergency,
    classify_natural_receptionist_intent,
    format_spoken_response,
    get_emergency_response,
    get_medical_advice_boundary_response,
    retrieve_tenant_knowledge,
)
from app.services.voice_assistant_service import (
    detect_intent,
    process_conversational_turn,
)


@pytest.fixture
def intelligent_receptionist_env(db_session: Session) -> dict:
    """Fixture providing an active business tenant with full knowledge base."""
    biz = Business(
        id="demo-ai-clinic-tenant",
        name="Vattara City Medical Center",
        vertical="clinic",
        email="reception@vattaramedical.com",
        phone="+914428280000",
        address="124 Anna Salai, Thousand Lights, Chennai, Tamil Nadu 600006",
        timezone="Asia/Kolkata",
        is_active=True,
    )
    db_session.add(biz)
    db_session.flush()

    cfg = AssistantConfig(
        business_id=biz.id,
        assistant_name="Vattara Health Assistant",
        language="en-IN",
        working_hours="Monday to Saturday: 9:00 AM to 6:00 PM, Sunday: Closed",
        fallback_number="+914428280001",
    )
    db_session.add(cfg)

    # 7 Operating Hours
    for dow in range(7):
        bh = BusinessHour(
            business_id=biz.id,
            day_of_week=dow,
            open_time="09:00",
            close_time="18:00",
            is_closed=(dow == 6),  # Sunday closed
        )
        db_session.add(bh)

    # Services
    srv1 = Service(
        id="srv-gp-1",
        business_id=biz.id,
        name="General Physician Consultation",
        price=500.0,
        duration_minutes=30,
        is_active=True,
    )
    srv2 = Service(
        id="srv-ped-1",
        business_id=biz.id,
        name="Pediatric Health Checkup",
        price=700.0,
        duration_minutes=30,
        is_active=True,
    )
    srv3 = Service(
        id="srv-cardio-1",
        business_id=biz.id,
        name="Cardiology Consultation",
        price=800.0,
        duration_minutes=45,
        is_active=True,
    )
    srv4 = Service(
        id="srv-dental-1",
        business_id=biz.id,
        name="Dental Cleaning and Polish",
        price=600.0,
        duration_minutes=30,
        is_active=True,
    )
    srv5 = Service(
        id="srv-blood-1",
        business_id=biz.id,
        name="Complete Blood Diagnostics",
        price=450.0,
        duration_minutes=15,
        is_active=True,
    )
    db_session.add_all([srv1, srv2, srv3, srv4, srv5])

    # Doctors / Staff
    doc1 = StaffSchedule(
        business_id=biz.id,
        staff_name="Dr. Ramesh (Senior Cardiologist)",
        day_of_week=0,
        start_time="09:00",
        end_time="17:00",
        slot_duration_minutes=45,
        is_active=True,
    )
    doc2 = StaffSchedule(
        business_id=biz.id,
        staff_name="Dr. Ananya (Consultant Pediatrician)",
        day_of_week=1,
        start_time="10:00",
        end_time="18:00",
        slot_duration_minutes=30,
        is_active=True,
    )
    db_session.add_all([doc1, doc2])

    # FAQs
    faq1 = FAQ(
        business_id=biz.id,
        category="Facilities",
        question="Do you have parking facilities?",
        answer="Yes, we provide complimentary valet and patient car parking in our building basement.",
        is_active=True,
    )
    faq2 = FAQ(
        business_id=biz.id,
        category="Payment",
        question="What payment methods do you accept?",
        answer="We accept Cash, UPI via Google Pay, PhonePe, credit and debit cards, and cashless health insurance.",
        is_active=True,
    )
    faq3 = FAQ(
        business_id=biz.id,
        category="Facilities",
        question="Do you have a wheelchair or ramp?",
        answer="Yes, our facility is 100% wheelchair accessible with ramp access and patient elevators.",
        is_active=True,
    )
    db_session.add_all([faq1, faq2, faq3])
    db_session.commit()

    return {
        "business": biz,
        "config": cfg,
        "services": [srv1, srv2, srv3, srv4, srv5],
    }


def _make_session(db: Session, business_id: str, call_sid: str, phone: str = "+919876543210", language: str = "en-IN") -> ConversationSession:
    sess = ConversationSession(
        call_sid=call_sid,
        business_id=business_id,
        caller_phone=phone,
        step="greeting",
        language=language,
        detected_language=language,
        dialog_history=json.dumps([]),
        metadata_json=json.dumps({"require_confirmation": True}),
        retry_count=0,
        is_completed=False,
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return sess


# ------------------------------------------------------------------------------
# Test 1: Phase 1 - All 16 Intent Categories Recognized
# ------------------------------------------------------------------------------
def test_phase1_intent_classification_all_categories():
    # 1. Medical emergency
    assert detect_intent("I have severe chest pain and trouble breathing") == "medical_emergency"
    assert detect_intent("Patient is unconscious and bleeding heavily") == "medical_emergency"
    assert detect_intent("எனக்கு கடுமையான நெஞ்சு வலி உள்ளது") == "medical_emergency"
    assert detect_intent("గుండె నొప్పి ఎక్కువగా ఉంది") == "medical_emergency"

    # 2. Medical advice boundary
    assert detect_intent("What medicine should I take for fever?") == "medical_advice_request"
    assert detect_intent("Can you prescribe antibiotics for my cough?") == "medical_advice_request"

    # 3. Unrelated general knowledge
    assert detect_intent("Who is the Prime Minister of India?") == "unrelated_general_knowledge"
    assert detect_intent("What is artificial intelligence?") == "unrelated_general_knowledge"
    assert detect_intent("Tell me a joke") == "unrelated_general_knowledge"
    assert detect_intent("What is the capital of France?") == "unrelated_general_knowledge"
    assert detect_intent("How is the weather today?") == "unrelated_general_knowledge"

    # 4. Pricing inquiry
    assert detect_intent("How much is a pediatric checkup?") == "pricing_inquiry"
    assert detect_intent("What is the cost of cardiology consultation?") == "pricing_inquiry"
    assert detect_intent("What are your fees?") == "pricing_inquiry"

    # 5. Payment methods inquiry
    assert detect_intent("What payment methods do you accept?") == "payment_methods_inquiry"
    assert detect_intent("Can I pay by Google Pay or credit card?") == "payment_methods_inquiry"
    assert detect_intent("Do you accept health insurance?") == "payment_methods_inquiry"

    # 6. Doctor and practitioner inquiry
    assert detect_intent("Which doctors are available?") == "doctor_staff_inquiry"
    assert detect_intent("Who is the cardiologist?") == "doctor_staff_inquiry"
    assert detect_intent("Is Dr. Ramesh available?") == "doctor_staff_inquiry"

    # 7. Customer complaints
    assert detect_intent("I have a complaint about long waiting times") == "complaint_inquiry"
    assert detect_intent("Your receptionist was very rude to me") == "complaint_inquiry"

    # 8. General clinic info and facilities
    assert detect_intent("Do you have car parking?") == "general_clinic_info"
    assert detect_intent("Is there wheelchair access?") == "general_clinic_info"
    assert detect_intent("Do you have a pharmacy?") == "general_clinic_info"

    # 9. Business address
    assert detect_intent("Where are you located?") == "business_inquiry_address"
    assert detect_intent("What is your clinic address?") == "business_inquiry_address"

    # 10. Business hours
    assert detect_intent("What are your working hours?") == "business_inquiry_hours"
    assert detect_intent("Are you open on Sunday?") == "business_inquiry_hours"

    # 11. Service inquiry
    assert detect_intent("What services do you provide?") == "business_inquiry_services"
    assert detect_intent("List of services") == "business_inquiry_services"

    # 12. Check existing appointment
    assert detect_intent("Do I have an upcoming appointment?") == "check_existing_appointment"

    # 13. Cancellation
    assert detect_intent("Cancel my appointment") == "cancel_appointment"

    # 14. Rescheduling
    assert detect_intent("Reschedule my appointment") == "reschedule_appointment"

    # 15. Check availability
    assert detect_intent("What slots are available tomorrow?") == "check_availability"

    # 16. Booking
    assert detect_intent("I want to book an appointment") == "booking"


# ------------------------------------------------------------------------------
# Test 2: Phase 2 & 6 - Natural Mid-Workflow Q&A with Context Retention
# ------------------------------------------------------------------------------
def test_phase2_and_6_natural_mid_workflow_booking_dialogue(db_session: Session, intelligent_receptionist_env: dict):
    biz = intelligent_receptionist_env["business"]
    session = _make_session(db_session, biz.id, "call-ai-natural-1", phone="+917904743468")

    # Turn 1: Caller asks for services list
    p1, c1 = process_conversational_turn(db_session, session, "What services do you provide?", biz)
    assert c1 is True
    assert "General Physician" in p1 or "Pediatric" in p1

    # Turn 2: Caller asks for price of pediatric checkup mid-conversation
    p2, c2 = process_conversational_turn(db_session, session, "How much is a pediatric checkup?", biz)
    assert c2 is True
    assert "700" in p2
    assert "Pediatric Health Checkup" in p2
    # Verify context saved service
    assert session.service_id is not None
    assert session.service_name == "Pediatric Health Checkup"

    # Turn 3: Caller asks clinic location while in the middle of booking
    p3, c3 = process_conversational_turn(db_session, session, "Where is your clinic located?", biz)
    assert c3 is True
    assert "124 Anna Salai" in p3
    # Verify service was NOT forgotten!
    assert "Pediatric Health Checkup" in p3
    assert session.service_id is not None

    # Turn 4: Caller provides appointment date and time
    p4, c4 = process_conversational_turn(db_session, session, "Tomorrow at 10 AM", biz)
    assert c4 is True
    assert session.appointment_datetime_iso is not None
    assert "name" in p4.lower()

    # Turn 5: Caller asks payment methods before giving name
    p5, c5 = process_conversational_turn(db_session, session, "What payment methods do you accept?", biz)
    assert c5 is True
    assert "cash" in p5.lower() or "upi" in p5.lower() or "cards" in p5.lower()
    # Verify still asks for name without losing date/time or service!
    assert "name" in p5.lower()
    assert session.appointment_datetime_iso is not None
    assert session.service_id is not None

    # Turn 6: Caller gives name
    p6, c6 = process_conversational_turn(db_session, session, "My name is Steve", biz)
    assert c6 is True
    assert session.customer_name == "Steve"
    assert "confirm" in p6.lower()

    # Turn 7: Caller confirms
    p7, c7 = process_conversational_turn(db_session, session, "Yes, confirm", biz)
    assert c7 is False
    assert session.is_completed is True
    assert session.booking_id is not None
    assert "Steve" in p7
    assert "Pediatric Health Checkup" in p7

    # Verify actual database appointment committed
    appt = db_session.get(Appointment, session.booking_id)
    assert appt is not None
    assert appt.service_id == "srv-ped-1"
    assert appt.status == "upcoming"


# ------------------------------------------------------------------------------
# Test 3: Phase 3 - Tenant-Specific Knowledge Isolation
# ------------------------------------------------------------------------------
def test_phase3_tenant_knowledge_isolation(db_session: Session, intelligent_receptionist_env: dict):
    biz = intelligent_receptionist_env["business"]

    # Create second business tenant
    biz_b = Business(
        id="demo-tenant-b-dental",
        name="Apex Dental Care",
        vertical="clinic",
        email="info@apexdental.com",
        phone="+914440001111",
        address="99 Mount Road, Chennai",
        timezone="Asia/Kolkata",
        is_active=True,
    )
    db_session.add(biz_b)
    db_session.flush()

    srv_b = Service(
        id="srv-root-canal",
        business_id=biz_b.id,
        name="Advanced Root Canal Treatment",
        price=3500.0,
        duration_minutes=60,
        is_active=True,
    )
    db_session.add(srv_b)
    db_session.commit()

    # Knowledge retrieval for Tenant A must NEVER include Root Canal or Apex Dental
    k_a = retrieve_tenant_knowledge(db_session, biz)
    assert k_a["business_name"] == "Vattara City Medical Center"
    service_names_a = [s.name for s in k_a["services"]]
    assert "Advanced Root Canal Treatment" not in service_names_a
    assert "Pediatric Health Checkup" in service_names_a

    # Knowledge retrieval for Tenant B must only include Tenant B's data
    k_b = retrieve_tenant_knowledge(db_session, biz_b)
    assert k_b["business_name"] == "Apex Dental Care"
    service_names_b = [s.name for s in k_b["services"]]
    assert "Pediatric Health Checkup" not in service_names_b
    assert "Advanced Root Canal Treatment" in service_names_b


# ------------------------------------------------------------------------------
# Test 4: Phase 4 - Unrelated Question Handling with Safe Pivots
# ------------------------------------------------------------------------------
def test_phase4_unrelated_general_knowledge_safe_handling(db_session: Session, intelligent_receptionist_env: dict):
    biz = intelligent_receptionist_env["business"]
    session = _make_session(db_session, biz.id, "call-ai-unrelated-1")

    # Caller asks for PM of India
    p1, c1 = process_conversational_turn(db_session, session, "Who is the Prime Minister of India?", biz)
    assert c1 is True
    assert "Narendra Modi" in p1
    assert "Vattara" in p1 or "clinic" in p1 or "appointment" in p1
    # Verify AI did NOT misidentify Narendra Modi as a medical service!
    assert session.service_id is None

    # Caller asks for a joke
    p2, c2 = process_conversational_turn(db_session, session, "Tell me a joke", biz)
    assert c2 is True
    assert "doctor" in p2.lower()
    assert session.service_id is None

    # Caller asks for AI definition
    p3, c3 = process_conversational_turn(db_session, session, "What is artificial intelligence?", biz)
    assert c3 is True
    assert "intelligence" in p3.lower() or "computer" in p3.lower()


# ------------------------------------------------------------------------------
# Test 5: Phase 5 - Medical Safety Boundaries (Emergency Triage & Non-Prescribing)
# ------------------------------------------------------------------------------
def test_phase5_medical_safety_emergency_and_non_prescribing(db_session: Session, intelligent_receptionist_env: dict):
    biz = intelligent_receptionist_env["business"]

    # 1. Emergency Case: Severe chest pain and shortness of breath
    sess_emerg = _make_session(db_session, biz.id, "call-ai-emerg-1")
    p_emerg, c_emerg = process_conversational_turn(
        db_session, sess_emerg, "I am having severe chest pain and cannot breathe", biz
    )
    assert c_emerg is True
    # Must immediately advise 108 or emergency room
    assert "108" in p_emerg or "emergency" in p_emerg.lower()
    # Must NOT attempt to force booking
    assert sess_emerg.step == "greeting"
    assert sess_emerg.service_id is None

    # 2. Medication Request Case: Prescribing boundary
    sess_med = _make_session(db_session, biz.id, "call-ai-med-1")
    p_med, c_med = process_conversational_turn(
        db_session, sess_med, "What medicine should I take for high fever?", biz
    )
    assert c_med is True
    # Must explain ethical non-prescribing boundary
    assert "cannot" in p_med.lower() or "ai receptionist" in p_med.lower()
    assert "appointment" in p_med.lower() or "doctor" in p_med.lower()


# ------------------------------------------------------------------------------
# Test 6: Phase 7 - Natural Voice Optimization (No Markdown & Clean Phrasing)
# ------------------------------------------------------------------------------
def test_phase7_voice_formatting_clean_spoken_text():
    sample_text = "**Vattara Clinic** fee is ₹700 for *Pediatric Checkup*:\n- 10:00 AM\n- 11:00 AM\n`call +914428280000`"
    cleaned = format_spoken_response(sample_text)
    assert "**" not in cleaned
    assert "*" not in cleaned
    assert "`" not in cleaned
    assert "₹" not in cleaned
    assert "700 rupees" in cleaned
    assert "\n" not in cleaned


# ------------------------------------------------------------------------------
# Test 7: Phase 8 - Unknown Questions and Front Desk Escalation / Callback
# ------------------------------------------------------------------------------
def test_phase8_unknown_question_and_callback_flow(db_session: Session, intelligent_receptionist_env: dict):
    biz = intelligent_receptionist_env["business"]
    session = _make_session(db_session, biz.id, "call-ai-unknown-1", phone="+919876543210")

    # Turn 1: Unknown question outside knowledge base
    p1, c1 = process_conversational_turn(db_session, session, "Can I bring my pet iguana into the clinic?", biz)
    assert c1 is True
    assert "records" in p1.lower() or "callback" in p1.lower() or "front desk" in p1.lower()

    # Turn 2: Caller requests callback
    p2, c2 = process_conversational_turn(db_session, session, "Yes, please call me back", biz)
    assert c2 is False  # Call completes
    assert session.is_completed is True
    assert "+919876543210" in p2
    assert "callback" in p2.lower()


# ------------------------------------------------------------------------------
# Test 8: Multilingual Natural Receptionist (Tamil & Telugu Mid-Workflow)
# ------------------------------------------------------------------------------
def test_multilingual_natural_receptionist_tamil_and_telugu(db_session: Session, intelligent_receptionist_env: dict):
    biz = intelligent_receptionist_env["business"]

    # Tamil Pricing Inquiry
    sess_ta = _make_session(db_session, biz.id, "call-ta-mid-1", language="ta-IN")
    p_ta, _ = process_conversational_turn(db_session, sess_ta, "குழந்தை பரிசோதனை கட்டணம் எவ்வளவு?", biz)
    assert "700" in p_ta
    assert "ரூபாய்" in p_ta

    # Telugu Pricing Inquiry
    sess_te = _make_session(db_session, biz.id, "call-te-mid-1", language="te-IN")
    p_te, _ = process_conversational_turn(db_session, sess_te, "పీడియాట్రిక్ చెకప్ ధర ఎంత?", biz)
    assert "700" in p_te
    assert "రూపాయలు" in p_te
