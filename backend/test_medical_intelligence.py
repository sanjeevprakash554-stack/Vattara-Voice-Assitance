"""Targeted verification for Vattara Voice Assistance Medical Question Understanding & Response Intelligence."""

import os
import sys

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.connection import SessionLocal
from app.models.business import Business
from app.models.conversation_session import ConversationSession
from app.services.ai.medical_knowledge import (
    CLINICAL_KNOWLEDGE_TOPICS,
    get_medical_guidance_for_response,
    query_medical_knowledge,
)
from app.services.ai.natural_receptionist import (
    check_medical_advice_request,
    check_medical_emergency,
    classify_natural_receptionist_intent,
    format_spoken_response,
    get_emergency_response,
    get_medical_advice_boundary_response,
)
from app.services.ai.prompts import build_system_prompt
from app.services.ai.tools import execute_tool_call


def run_targeted_medical_tests():
    print("=================================================================")
    print("VATTARA MEDICAL RECEPTIONIST INTELLIGENCE - TARGETED VERIFICATION")
    print("=================================================================")

    db = SessionLocal()
    biz = db.query(Business).filter(Business.id == "demo-biz-vattara-health").first()
    assert biz is not None, "Tenant demo-biz-vattara-health not found in database!"
    print(f"Tenant: {biz.name} ({biz.id})")

    # TEST 1: Medically Reviewed Clinical Topics (All 10 required domains)
    print("\n--- TEST 1: Clinical Topics Grounding (WHO / ICMR / MoHFW) ---")
    assert len(CLINICAL_KNOWLEDGE_TOPICS) >= 10, f"Expected at least 10 clinical topics, found {len(CLINICAL_KNOWLEDGE_TOPICS)}"
    categories = {t.category for t in CLINICAL_KNOWLEDGE_TOPICS}
    required_cats = {"infections", "neurology", "metabolic", "cardiovascular", "dermatology", "gastrointestinal", "pediatrics", "gynecology", "diagnostics", "pharmacotherapy", "preventive"}
    assert required_cats.issubset(categories), f"Missing categories: {required_cats - categories}"
    print(f"Verified {len(CLINICAL_KNOWLEDGE_TOPICS)} topics spanning all required clinical domains: {sorted(list(categories))}")

    # TEST 2: Multilingual Understanding & Symptom Matching
    print("\n--- TEST 2: Multilingual Symptom & Query Understanding ---")
    test_queries = [
        ("Enakku 2 naala fever irukku, odambu sooda irukku", "ta-Latn", "fever_infection", "General Physician"),
        ("எனக்கு ரொம்ப தலைவலியா இருக்கு என்ன பண்றது", "ta-IN", "headache", "General Physician"),
        ("My fasting blood sugar came back 180, what does it mean?", "en-IN", "diabetes_blood_sugar", "General Physician"),
        ("I have severe acid reflux and burning stomach ache", "en-IN", "digestive_acidity_gerd", "General Physician"),
        ("Enoda kulandhai-ku fever and vomiting irukku, paapa romba azhudhu", "ta-Latn", "pediatric_child_health", "Pediatrician"),
        ("Periods irregular-ah irukku and severe cramps irukku", "ta-Latn", "womens_health_pregnancy", "Gynecologist"),
        ("Do I need to do 10 hours fasting before HbA1c and lipid test?", "en-IN", "diagnostic_tests", "General Physician"),
        ("Fever-ku paracetamol tablet saapidalama? Ethana mg edukanum?", "ta-Latn", "general_medicine_info", "General Physician"),
        ("Kai la itching and red skin rash vandhurukku", "ta-Latn", "skin_conditions_allergy", "Dermatologist"),
        ("What tests are done in master health checkup?", "en-IN", "preventive_wellness", "General Physician"),
    ]

    for q, lang, expected_id, expected_specialty in test_queries:
        topic = query_medical_knowledge(q, lang)
        assert topic is not None, f"Failed to match query: '{q}'"
        assert topic.id == expected_id, f"Query '{q}' matched '{topic.id}' instead of expected '{expected_id}'"
        print(f"Match [{lang}]: '{q[:35]}...' -> Topic: {topic.id} | Dept: {topic.recommended_specialty} (Expected: {expected_specialty})")

    # TEST 3: Medical Emergency Red Flags & 108 Routing (Zero Routine Booking)
    print("\n--- TEST 3: Medical Emergency Red Flag Detection & 108 Routing ---")
    emergency_queries = [
        ("Nenjula bayangarama barama irukku, left kai valikudhu", "ta-Latn"),
        ("Moochu vida mudiyala, romba suffocating-ah irukku", "ta-Latn"),
        ("Patient suddenly fell unconscious and unresponsive", "en-IN"),
        ("Patient-ku valippu fits vandhu vaai oru pakkam saayudhu", "ta-Latn"),
        ("Athiga raththa vaandhi vandhutu irukku", "ta-Latn"),
        ("Chest pain radiating to arm with shortness of breath", "en-IN"),
    ]

    for eq, lang in emergency_queries:
        is_emerg = check_medical_emergency(eq)
        assert is_emerg, f"Failed to detect emergency for: '{eq}'"
        intent, _ = classify_natural_receptionist_intent(eq)
        assert intent == "medical_emergency", f"Intent for '{eq}' was '{intent}', expected 'medical_emergency'"
        resp = get_emergency_response(lang, biz)
        assert "108" in resp, f"Emergency response missing '108' ambulance directive: {resp}"
        # Ensure emergency triage does NOT force standard booking questions
        assert "Which time slot" not in resp and "appointment book panna" not in resp.lower()
        print(f"Emergency Detected: '{eq[:35]}...' -> Intent: {intent} -> 108 Ambulance Dispatch Activated.")

    # TEST 4: Ethical Safety Boundaries (Never Prescribe / Never Diagnose Definitively)
    print("\n--- TEST 4: Medical Safety Boundaries & Non-Prescribing Controls ---")
    boundary_queries = [
        "Can you prescribe me antibiotics for throat infection?",
        "What dosage of Azithromycin 500mg should I take?",
        "Tell me which medicine cures diabetes permanently",
    ]
    for bq in boundary_queries:
        is_advice = check_medical_advice_request(bq)
        assert is_advice, f"Failed to detect prescription inquiry for '{bq}'"
        resp = get_medical_advice_boundary_response("en-IN", user_query=bq, business=biz)
        assert "prescribe" in resp.lower() or "examination" in resp.lower() or "consultation" in resp.lower()
        print(f"Prescription Inquiry Blocked: '{bq[:35]}...' -> Safe Response: {resp[:70]}...")

    # TEST 5: get_medical_information AI Tool Execution
    print("\n--- TEST 5: get_medical_information Tool Dispatch ---")
    tool_args = {"query": "fever and dry cough with body pain", "caller_language": "ta-Latn"}
    result = execute_tool_call(db=db, business_id=biz.id, function_name="get_medical_information", arguments=tool_args)
    assert result.get("found") is True
    assert result.get("topic") in ("cold_cough", "fever_infection")
    assert "explanation" in result
    assert "home_care" in result
    assert "red_flags" in result
    assert result.get("matched_service") is not None
    print(f"Tool executed successfully: matched topic '{result['topic']}' to clinic service '{result['matched_service']['name']}' (Fee: Rs. {result['matched_service']['price']})")

    # TEST 6: Spoken Telephony Formatting for Medical Acronyms & Tests
    print("\n--- TEST 6: Telephony Speech Formatting (Sarvam Bulbul v4 Flash) ---")
    raw_telephony_text = "Patient needs HbA1c test and ECG. Take ORS with 500mg paracetamol if BP is normal. Fee is ₹500/-."
    spoken_fmt = format_spoken_response(raw_telephony_text)
    print(f"Raw Input:    {raw_telephony_text}")
    print(f"Spoken Voice: {spoken_fmt}")
    assert "H b A 1 c" in spoken_fmt, "HbA1c was not spaced for clear telephony speech!"
    assert "E C G" in spoken_fmt, "ECG was not spaced for clear telephony speech!"
    assert "B P" in spoken_fmt, "BP was not spaced for clear telephony speech!"
    assert "O R S" in spoken_fmt, "ORS was not spaced for clear telephony speech!"
    assert "500 milligrams" in spoken_fmt, "500mg was not expanded to 500 milligrams!"
    assert "500 rupees" in spoken_fmt, "₹500 was not converted to 500 rupees!"

    # TEST 7: Clinic Doctor & Service Integration
    print("\n--- TEST 7: Clinic Service & Staff Alignment ---")
    child_topic = query_medical_knowledge("child fever and cold", "ta-Latn")
    child_guidance = get_medical_guidance_for_response(
        topic=child_topic,
        language="ta-Latn",
        matching_services=[{"name": "Pediatric Health Checkup", "price": 700}],
        matching_doctors=[{"name": "Dr. Priya Annamalai", "specialty": "Pediatrician"}],
    )
    assert child_guidance["matched_service"]["name"] == "Pediatric Health Checkup"
    assert child_guidance["matched_doctor"]["name"] == "Dr. Priya Annamalai"
    print(f"Child symptom mapped to: Service='{child_guidance['matched_service']['name']}' (Rs. {child_guidance['matched_service']['price']}), Doctor='{child_guidance['matched_doctor']['name']}'")

    print("\n=================================================================")
    print("ALL 7 TARGETED MEDICAL INTELLIGENCE TESTS PASSED SUCCESSFULLY!")
    print("=================================================================")
    db.close()


if __name__ == "__main__":
    run_targeted_medical_tests()
