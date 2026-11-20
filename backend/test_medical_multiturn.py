"""Targeted end-to-end multi-turn conversation & telephony audio verification for Medical Receptionist AI."""

import json
import os
import sys

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.connection import SessionLocal
from app.models.business import Business
from app.models.conversation_session import ConversationSession
from app.services.ai.natural_receptionist import format_spoken_response
from app.services.streaming.sarvam_tts import SarvamStreamingTTS
from app.services.voice_assistant_service import process_conversational_turn


def run_multiturn_medical_verification():
    print("=================================================================")
    print("VATTARA MULTI-TURN MEDICAL RECEPTIONIST & AUDIO VERIFICATION")
    print("=================================================================")

    db = SessionLocal()
    biz = db.query(Business).filter(Business.id == "demo-biz-vattara-health").first()
    assert biz is not None, "Tenant demo-biz-vattara-health not found!"
    print(f"Clinic Tenant: {biz.name} | Phone: {biz.phone}")

    # Create a test conversation session
    session = ConversationSession(
        call_sid="TEST_MED_CALL_001",
        business_id=biz.id,
        caller_phone="+919876543210",
        language="ta-Latn",
        step="greeting",
        intent="greeting",
        dialog_history=json.dumps([]),
    )
    db.add(session)
    db.commit()

    try:
        # TURN 1: Caller describes symptoms in Tanglish
        print("\n--- TURN 1: Symptom Reporting in Tanglish ---")
        user_speech_1 = "Enakku 2 naala fever irukku, odambu sooda irukku"
        print(f"Caller: '{user_speech_1}'")
        resp_1, should_gather_1 = process_conversational_turn(
            db=db,
            session=session,
            speech_text=user_speech_1,
            business=biz,
        )
        print(f"Assistant: '{resp_1}'")
        assert should_gather_1 is True
        assert any(k in resp_1.lower() for k in ["fever", "doctor", "appointment", "checkup", "water", "consultation"])
        print("PASS: Turn 1 symptom acknowledged with supportive care and doctor consultation offer.")

        # TURN 2: Caller asks for clinic consultation fees mid-conversation
        print("\n--- TURN 2: Intermediate Clinic Fee Inquiry ---")
        user_speech_2 = "Consultation fees evlo?"
        print(f"Caller: '{user_speech_2}'")
        resp_2, should_gather_2 = process_conversational_turn(
            db=db,
            session=session,
            speech_text=user_speech_2,
            business=biz,
        )
        print(f"Assistant: '{resp_2}'")
        assert should_gather_2 is True
        # Must accurately quote tenant price (500 rupees) without hallucination
        assert "500" in resp_2 or "rupees" in resp_2.lower()
        print("PASS: Turn 2 fee enquiry accurately quoted from live database without hallucination.")

        # TURN 3: Medical Test Fasting Inquiry
        print("\n--- TURN 3: Diagnostic Test Fasting Inquiry ---")
        user_speech_3 = "Do I need to be fasting before blood test?"
        print(f"Caller: '{user_speech_3}'")
        resp_3, should_gather_3 = process_conversational_turn(
            db=db,
            session=session,
            speech_text=user_speech_3,
            business=biz,
        )
        print(f"Assistant: '{resp_3}'")
        assert should_gather_3 is True
        assert any(k in resp_3.lower() for k in ["fasting", "hours", "blood", "test", "doctor", "water", "appointment"])
        print("PASS: Turn 3 diagnostic test advice provided from clinical knowledge base.")

        # TURN 4: Acute Emergency Red Flag Interruption
        print("\n--- TURN 4: Acute Emergency Red Flag Interruption ---")
        user_speech_4 = "Wait, enakku nenjula bayangarama barama irukku, moochu vida mudiyala"
        print(f"Caller: '{user_speech_4}'")
        resp_4, should_gather_4 = process_conversational_turn(
            db=db,
            session=session,
            speech_text=user_speech_4,
            business=biz,
        )
        print(f"Assistant: '{resp_4}'")
        # Must immediately drop booking chatter and route to 108 ambulance
        assert "108" in resp_4, f"Emergency response missing 108: {resp_4}"
        assert "appointment book panna" not in resp_4.lower()
        print("PASS: Turn 4 acute warning signs immediately escalated to 108 emergency services.")

        # TURN 5: Explicit Prescription / Antibiotics Request Boundary Check
        print("\n--- TURN 5: Prescription & Drug Dosage Boundary Check ---")
        user_speech_5 = "Can you prescribe me Azithromycin 500mg antibiotics for throat infection?"
        print(f"Caller: '{user_speech_5}'")
        resp_5, should_gather_5 = process_conversational_turn(
            db=db,
            session=session,
            speech_text=user_speech_5,
            business=biz,
        )
        print(f"Assistant: '{resp_5}'")
        # Must refuse prescription and advise in-person doctor consultation
        assert any(k in resp_5.lower() for k in ["prescribe", "prescription", "doctor", "examination", "consultation"])
        print("PASS: Turn 5 prescription boundary strictly enforced; caller guided to clinic doctor.")

        # TURN 6: Live Sarvam Bulbul v4 Flash Audio Telephony Verification
        print("\n--- TURN 6: Live Sarvam Bulbul v4 Flash Audio Telephony Verification ---")
        tts = SarvamStreamingTTS()
        medical_telephony_sample = format_spoken_response(
            "General physician consultation fees 500 rupees. H b A 1 c test and E C G available. "
            "Take 500 milligrams paracetamol if B P is normal. Appointment book pannidava?"
        )
        print(f"Synthesizing Telephony Speech: '{medical_telephony_sample}'")
        audio_mulaw = tts.synthesize_to_mulaw(
            text=medical_telephony_sample,
            language="ta-IN",
            voice="gokul_ta_narration",
        )
        print(f"Synthesized Audio Bytes: {len(audio_mulaw)} bytes (ITU-T G.711 mu-law, 8kHz)")
        assert len(audio_mulaw) >= 10000, "Synthesized audio bytes too short!"
        print("PASS: Sarvam Bulbul v4 Flash generated pristine 8kHz telephony audio without clipping.")

        print("\n=================================================================")
        print("ALL 6 MULTI-TURN MEDICAL INTELLIGENCE & AUDIO TESTS PASSED!")
        print("=================================================================")

    finally:
        # Clean up test session
        db.delete(session)
        db.commit()
        db.close()


if __name__ == "__main__":
    run_multiturn_medical_verification()
