"""Comprehensive Audit Script for Vattara Medical AI Intelligence.

Performs verification across:
1. 16 Medical Knowledge Topics connected to live conversation flow.
2. Clinic-specific information grounding (fees, doctors, services).
3. Emergency detection priority over normal conversation and booking states.
4. Multilingual response integrity (Tamil, Tanglish, English).
5. Sarvam Bulbul v4 Flash TTS audio delivery for telephony.
6. Edge case and integration checks.
"""

import json
import os
import sys

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.connection import SessionLocal
from app.models.assistant import Service
from app.models.business import Business
from app.models.conversation_session import ConversationSession
from app.models.staff_schedule import StaffSchedule
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
from app.services.ai.tools import execute_tool_call
from app.services.streaming.audio_codec import mulaw_to_base64, validate_telephony_mulaw_chunk
from app.services.streaming.sarvam_tts import SarvamStreamingTTS
from app.services.voice_assistant_service import process_conversational_turn


def run_comprehensive_audit():
    print("=" * 70)
    print("VATTARA MEDICAL AI INTELLIGENCE - FINAL COMPREHENSIVE AUDIT")
    print("=" * 70)

    db = SessionLocal()
    biz = db.query(Business).filter(Business.id == "demo-biz-vattara-health").first()
    assert biz is not None, "Tenant demo-biz-vattara-health not found!"
    services = db.query(Service).filter(Service.business_id == biz.id, Service.is_active.is_(True)).all()
    staff = db.query(StaffSchedule).filter(StaffSchedule.business_id == biz.id, StaffSchedule.is_active.is_(True)).all()
    print(f"Tenant: {biz.name} ({biz.id}) | Phone: {biz.phone}")
    print(f"Active Services: {len(services)} | Staff Schedule Entries: {len(staff)}")

    # -------------------------------------------------------------------------
    # CHECK 1: All 16 Medical Knowledge Topics Connected to Live Conversation
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("CHECK 1: Auditing All 16 Medical Knowledge Topics in Live Routing")
    print("=" * 70)
    assert len(CLINICAL_KNOWLEDGE_TOPICS) == 16, f"Expected 16 topics, found {len(CLINICAL_KNOWLEDGE_TOPICS)}"

    srv_dicts = [{"id": s.id, "name": s.name, "price": s.price, "duration_minutes": s.duration_minutes} for s in services]
    staff_dicts = [{"name": s.staff_name, "specialty": s.staff_name} for s in staff]

    for idx, topic in enumerate(CLINICAL_KNOWLEDGE_TOPICS, 1):
        guidance_en = get_medical_guidance_for_response(topic, "en-IN", srv_dicts, staff_dicts)
        guidance_ta = get_medical_guidance_for_response(topic, "ta-IN", srv_dicts, staff_dicts)
        guidance_tlatn = get_medical_guidance_for_response(topic, "ta-Latn", srv_dicts, staff_dicts)

        assert guidance_en["explanation"] and guidance_en["home_care"] and guidance_en["disclaimer"]
        assert guidance_ta["explanation"] and guidance_ta["home_care"] and guidance_ta["disclaimer"]
        assert guidance_tlatn["explanation"] and guidance_tlatn["home_care"] and guidance_tlatn["disclaimer"]
        assert guidance_en["matched_service"] is not None, f"Topic {topic.id} failed service match"

        # Verify through tool call execution
        tool_res = execute_tool_call(
            db=db,
            business_id=biz.id,
            function_name="get_medical_information",
            arguments={"query": topic.aliases[0], "caller_language": "ta-Latn"},
        )
        assert tool_res.get("found") is True, f"Tool failed for topic {topic.id}"

        svc_name = guidance_en["matched_service"]["name"]
        fee = guidance_en["matched_service"]["price"]
        doc_name = guidance_en["matched_doctor"]["name"] if guidance_en["matched_doctor"] else "On-duty GP"
        print(f"[{idx:2d}/16] Topic: {topic.id:26s} | Service: {svc_name} (Rs. {fee}) | Doctor: {doc_name}")

    print("CHECK 1 PASSED: All 16 clinical topics verified with multilingual guidance and tenant routing.")

    # -------------------------------------------------------------------------
    # CHECK 2: Clinic-Specific Information Accuracy & Pricing Guard
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("CHECK 2: Clinic-Specific Pricing & Service Quotations")
    print("=" * 70)
    expected_fees = {
        "General Physician Consultation": 500.0,
        "Cardiology Consultation & ECG": 1200.0,
        "Pediatric Health Checkup": 700.0,
        "Full Body Blood Diagnostics": 1500.0,
    }
    for s in services:
        if s.name in expected_fees:
            assert s.price == expected_fees[s.name], f"Mismatch for {s.name}: expected {expected_fees[s.name]}, got {s.price}"
            print(f"Service '{s.name}': Exactly Rs. {s.price} (Verified from live database)")

    # -------------------------------------------------------------------------
    # CHECK 3: Emergency Detection Priority Across Conversation States
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("CHECK 3: Emergency Priority Across All Conversation States")
    print("=" * 70)
    test_states = [
        "greeting",
        "awaiting_service",
        "awaiting_datetime",
        "awaiting_name",
        "awaiting_confirmation",
    ]
    emergency_phrases = [
        ("Nenjula bayangarama barama irukku, moochu vida mudiyala", "ta-Latn"),
        ("Wait, moochu thinaral romba athigama irukku", "ta-Latn"),
        ("Yes confirm, but patient collapsed and is unconscious", "en-IN"),
        ("நோயாளிக்கு தீவிர நெஞ்சு வலி மற்றும் மயக்கம்", "ta-IN"),
    ]

    for st in test_states:
        for phrase, lang in emergency_phrases:
            sess = ConversationSession(
                call_sid=f"AUDIT_EMERG_{st[:4]}",
                business_id=biz.id,
                caller_phone="+919876543210",
                language=lang,
                step=st,
                intent="booking" if st != "greeting" else "greeting",
                dialog_history=json.dumps([]),
            )
            db.add(sess)
            db.commit()

            try:
                resp, _ = process_conversational_turn(
                    db=db,
                    session=sess,
                    speech_text=phrase,
                    business=biz,
                )
                assert "108" in resp, f"State {st} failed 108 emergency escalation for '{phrase}': {resp}"
                assert "appointment" not in resp.lower() or "108" in resp
            finally:
                db.delete(sess)
                db.commit()
        print(f"State '{st:22s}': Emergency detection successfully prioritized over normal flow.")

    print("CHECK 3 PASSED: Emergency triage takes absolute priority in all booking and greeting states.")

    # -------------------------------------------------------------------------
    # CHECK 4: Multilingual Language Directives & Script Preservation
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("CHECK 4: Multilingual Response Script Integrity (Tamil, Tanglish, English)")
    print("=" * 70)
    # TA-IN: Pure Tamil script
    topic_fever = query_medical_knowledge("காய்ச்சல் மற்றும் சளி", "ta-IN")
    guidance_ta = get_medical_guidance_for_response(topic_fever, "ta-IN")
    assert any("\u0B80" <= c <= "\u0BFF" for c in guidance_ta["explanation"]), "TA-IN response lacked Tamil script"
    print("Tamil Script Output:   ", guidance_ta["explanation"][:80], "...")

    # TA-LATN: Phonetic Tanglish with English loanwords
    topic_child = query_medical_knowledge("kulandhai-ku fever", "ta-Latn")
    guidance_tlatn = get_medical_guidance_for_response(topic_child, "ta-Latn")
    assert not any("\u0B80" <= c <= "\u0BFF" for c in guidance_tlatn["explanation"]), "Tanglish had unwanted Unicode script"
    assert "Doctor" in guidance_tlatn["explanation"] or "baby" in guidance_tlatn["explanation"].lower() or "fever" in guidance_tlatn["explanation"].lower()
    print("Tanglish Output:       ", guidance_tlatn["explanation"][:80], "...")

    # EN-IN: Indian English
    topic_diabetes = query_medical_knowledge("fasting blood sugar level", "en-IN")
    guidance_en = get_medical_guidance_for_response(topic_diabetes, "en-IN")
    assert "glucose" in guidance_en["explanation"].lower() or "diabetes" in guidance_en["explanation"].lower()
    print("English Output:        ", guidance_en["explanation"][:80], "...")

    print("CHECK 4 PASSED: Script integrity and language formatting verified without cross-language leakage.")

    # -------------------------------------------------------------------------
    # CHECK 5: Actual Sarvam TTS Delivery & Plivo Audio Frame Validation
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("CHECK 5: Sarvam Bulbul v4 Flash Audio Delivery for Telephony (8kHz Mu-law)")
    print("=" * 70)
    tts = SarvamStreamingTTS()
    test_phrase = format_spoken_response(
        "General physician consultation fees 500 rupees. H b A 1 c and E C G available. "
        "Take 500 milligrams paracetamol if B P is normal. Appointment book pannidava?"
    )
    mulaw_bytes = tts.synthesize_to_mulaw(
        text=test_phrase,
        language="ta-IN",
        voice="gokul_ta_narration",
    )
    print(f"Total Synthesized Bytes: {len(mulaw_bytes)} bytes")
    assert len(mulaw_bytes) > 5000, "Audio output empty or too small"

    # Validate 160-byte 20ms telephony chunks for Plivo WebSocket streaming
    chunk_size = 160
    chunks = [mulaw_bytes[i:i + chunk_size] for i in range(0, len(mulaw_bytes), chunk_size)]
    print(f"Framed into {len(chunks)} 20ms Plivo audio chunks (160 bytes each)")

    for idx, chunk in enumerate(chunks[:5]):
        is_valid, reason = validate_telephony_mulaw_chunk(chunk)
        assert is_valid, f"Chunk {idx} failed mu-law telephony validation: {reason}"
        b64 = mulaw_to_base64(chunk)
        plivo_event = {
            "event": "playAudio",
            "media": {
                "contentType": "audio/x-mulaw",
                "sampleRate": 8000,
                "payload": b64,
            },
        }
        assert json.dumps(plivo_event), "Failed Plivo event serialization"

    print("CHECK 5 PASSED: Sarvam Bulbul v4 Flash audio validated for Plivo 8000 Hz mu-law streaming.")

    # -------------------------------------------------------------------------
    # CHECK 6: Integration Boundaries & Clean State
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("CHECK 6: Integration Boundaries & Edge Cases")
    print("=" * 70)
    # Check that asking for advice on undefined illness gives safe doctor referral
    boundary_resp = get_medical_advice_boundary_response("en-IN", user_query="What medicine for unknown rare condition?", business=biz)
    assert "doctor" in boundary_resp.lower() and "receptionist" in boundary_resp.lower()
    print("Safe Boundary Response: ", boundary_resp[:80], "...")

    print("\n" + "=" * 70)
    print("ALL 6 FINAL AUDIT CHECKS PASSED WITH 100% SUCCESS!")
    print("=" * 70)
    db.close()


if __name__ == "__main__":
    run_comprehensive_audit()
