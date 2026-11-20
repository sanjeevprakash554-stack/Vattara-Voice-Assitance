"""Conversational Voice Assistant service powered by LLM Conversational Engine and Phase 2 Scheduling."""

from datetime import date, datetime, time as dt_time, timedelta, timezone
from difflib import SequenceMatcher
import json
import re
from typing import Any
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models.appointment import Appointment
from app.models.assistant import AssistantConfig, FAQ, Service
from app.models.business import Business
from app.models.business_hours import BusinessHour
from app.models.call import Call
from app.models.conversation_session import ConversationSession
from app.models.customer import Customer
from app.models.staff_schedule import StaffSchedule
from app.services.ai.base import BaseLLMProvider, LLMMessage, LLMResponse
from app.services.ai.factory import get_llm_provider
from app.services.ai.language_detector import (
    EXPLICIT_ENGLISH_SWITCH_REGEX,
    EXPLICIT_TAMIL_SWITCH_REGEX,
    EXPLICIT_TANGLISH_SWITCH_REGEX,
    EXPLICIT_TELUGU_SWITCH_REGEX,
    detect_language,
    get_display_language_name,
    is_tamil_script,
)
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
    find_matching_faq,
    format_spoken_response,
    get_contextual_continuation_prompt,
    get_emergency_response,
    get_medical_advice_boundary_response,
    has_symptom_or_illness,
    is_conversational_recovery,
    is_hold_or_pause_request,
    match_unrelated_general_query,
    retrieve_tenant_knowledge,
)
from app.services.ai.prompts import build_system_prompt
from app.services.ai.tools import AI_TOOLS_SPEC, execute_tool_call
from app.services.appointment_service import book_appointment_core
from app.services.dashboard_events import dashboard_event_manager
from app.services.scheduling_service import (
    DAY_NAMES,
    calculate_available_slots,
    cancel_appointment_core,
    find_alternative_slots,
    get_all_operating_hours,
    get_business_timezone,
    reschedule_appointment_core,
)

logger = get_logger(__name__)

# Distinctive service alias keywords for intelligent mapping across English, Indian English, Tamil, and Telugu
SERVICE_ALIASES: dict[str, list[str]] = {
    "cardio": [
        "cardio", "cardiology", "heart", "ecg", "cardiac", "cardiac checkup", "heart problem", "heart doctor", "chest pain",
        "இதய பரிசோதனை", "இதயம்", "கார்டியாலஜி", "இதய", "நெஞ்சு", "ஈசிஜி",
        "idhayam", "idhaya maruthuvar", "cardiology checkup", "heart ecg",
        "గుండె పరీక్ష", "గుండె", "కార్డియాలజీ", "గుండె జబ్బు", "హృదయ", "ఈసీజీ",
        "gunde", "gunde noppi", "gunde doctor"
    ],
    "physician": [
        "physician", "general physician", "general medicine", "internal medicine", "general doctor", "family doctor", "general consultation",
        "unwell", "sick", "ill", "headache", "fever", "cough", "cold", "body pain", "stomach pain", "not feeling well", "not well", "not fine", "see a doctor", "consult a doctor",
        "பொது மருத்துவம்", "பொது மருத்துவர்", "பொது",
        "podhu maruthuvam", "podhu maruthuvar", "general physician consultation",
        "doctor", "doctor ah", "doctor-ah", "doctor paakanum", "doctor parkanum", "doctor venum", "doctor kidaikuma",
        "paakanum", "pakanum", "parkanum", "paarkanum", "maruthuvar",
        "odambu seri illa", "udambu mudiyala", "odambu mudiyala", "udambu seri illa", "odambu", "udambu",
        "thala vali", "thalavali", "kaachal", "sali", "irumal", "valikudhu", "valikuthu", "vali",
        "உடம்பு சரியில்லை", "உடம்பு முடியல", "தலைவலி", "காய்ச்சல்", "சளி", "இருமல்", "மருத்துவர் பார்க்க", "டாக்டர் பார்க்க", "மருத்துவர்", "டாக்டர்",
        "சாధారణ వైద్యం", "సాధారణ వైద్యుడు", "సాధారణ",
        "vaidhyudu consultation", "vaidhyudu", "vaidyudu", "sadharana vaidyam", "sadharana vaidyudu", "general medicine",
        "doctoru", "ontlo bagoledu", "thala noppi", "jwaram", "daggu", "jalubu", "noppi"
    ],
    "pediatric": [
        "pediatric", "pediatrician", "paediatric", "paediatrics", "pediatrix", "mediatrix", "padiatric", "pedia",
        "child", "children", "baby", "kid", "vaccine", "immunization",
        "pediatric health", "pediatric checkup", "child checkup", "baby checkup", "kid checkup", "health checkup", "head checkup", "pediatric health checkup",
        "குழந்தை", "குழந்தைகள்", "குழந்தை மருத்துவம்", "குழந்தை பரிசோதனை",
        "kuzhandhai", "kuzhandhai maruthuvam", "paappa", "paapa", "paappa checkup", "paappa health checkup", "kuzhandhai doctor",
        "పిల్లల", "పిల్లలు", "పిల్లల వైద్యుడు", "పిల్లల డాక్టర్", "పిల్లల ఆరోగ్య పరీక్ష", "పీడియాట్రిక్", "పీడియాట్రిక్స్", "పీడియాట్రిక్ చెకప్",
        "pillalu", "chinna pillalu", "pillala doctor", "pillala checkup", "pillala health checkup"
    ],
    "dental": [
        "dental", "dentist", "teeth", "tooth", "cleaning", "cavity", "teeth cleaning", "dental cleaning", "polish", "scaling", "teeth polish",
        "பல்", "பல் மருத்துவம்", "பல் சுத்தம்",
        "pal", "pal vali", "pal doctor",
        "పళ్ళు", "దంత", "పంటి నొప్పి", "పంటి", "పళ్ళు శుభ్రం",
        "pallu", "panti noppi", "danta chikitsa", "pallu clean"
    ],
    "diagnostics": [
        "blood test", "diagnostic", "diagnostics", "lab test", "lipid", "full body", "blood profile", "complete blood", "laboratory",
        "இரத்த பரிசோதனை", "இரத்த சோதனை", "ரத்த பரிசோதனை",
        "raththam", "raththa test", "blood test", "lab test",
        "రక్త పరీక్ష", "ల్యాబ్ టెస్ట్",
        "raktha pareeksha", "raktha test"
    ],
}


def get_or_create_conversation_session(
    db: Session,
    call_sid: str,
    business_id: str,
    caller_phone: str,
    default_language: str = "en-IN",
) -> ConversationSession:
    """Retrieve existing conversation session or initialize a new persistent session."""
    session = db.get(ConversationSession, call_sid)
    if session:
        return session

    # Normalize caller phone consistently to +91 followed by 10 digits
    clean_phone = normalize_indian_mobile_number(caller_phone) or caller_phone.strip()
    from_digits = clean_phone_digits(clean_phone)
    cust = db.scalar(
        select(Customer).where(
            Customer.business_id == business_id,
            Customer.phone == clean_phone,
        )
    )
    if not cust and from_digits:
        for c in db.scalars(select(Customer).where(Customer.business_id == business_id)).all():
            if c.phone and clean_phone_digits(c.phone) == from_digits:
                cust = c
                break
    returning_name: str | None = None
    if cust and cust.name and not cust.name.startswith("Caller "):
        returning_name = cust.name

    # Check assistant configuration for business default language
    cfg = db.scalar(
        select(AssistantConfig).where(AssistantConfig.business_id == business_id)
    )
    # Do not initialise every conversation as English when caller language is unknown
    initial_lang = cfg.language if (cfg and cfg.language and cfg.language not in ("en-US", "en-IN")) else getattr(settings, "DEFAULT_GREETING_MODE", "ta-IN")
    if initial_lang in ("bilingual", "auto"):
        initial_lang = "ta-IN"

    session = ConversationSession(
        call_sid=call_sid,
        business_id=business_id,
        caller_phone=clean_phone,
        customer_name=None,  # Always collect / confirm caller's actual name for new appointment
        step="greeting",
        language=initial_lang,
        detected_language=None,  # Start unknown until speech evidence arrives
        dialog_history=json.dumps([]),
        metadata_json=json.dumps({"require_confirmation": True, "returning_customer_name": returning_name}),
        retry_count=0,
        is_completed=False,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    logger.info("Initialized persistent conversation session for CallSid: %s", call_sid)
    return session


def is_short_affirmative_or_filler(text: str) -> bool:
    """Check if the utterance is a short conversational acknowledgment, filler, or echo artifact."""
    if not text:
        return False
    clean = re.sub(r"[^\w\s\u0B80-\u0BFF\u0C00-\u0C7F]", " ", text.lower()).strip()
    words = clean.split()
    if not words or len(words) > 4:
        return False
    filler_set = {
        "yes", "yeah", "yep", "sure", "okay", "ok", "fine", "correct",
        "thanks", "thank", "you", "thx", "right", "uh", "um", "ah",
        "சரி", "ஆம்", "ஆமாம்", "நன்றி", "sari", "aama", "kandippa",
        "అవును", "సరే", "ఖచ్చితంగా", "ధన్యవాదాలు", "avunu", "thappakunda", "alage", "nijam", "thanksandi"
    }
    return all(w in filler_set for w in words)


from app.services.telephony.phone_utils import (
    SPOKEN_DIGIT_MAP,
    clean_phone_digits,
    extract_phone_number,
    normalize_indian_mobile_number,
    sanitize_transcription_noise,
)


# Set of short noise fillers and breathing artifacts routinely hallucinated by STT on background sound
NOISE_FILLER_TOKENS = {
    "uh", "um", "ah", "eh", "er", "hmm", "hm", "huh", "oh", "ha", "mm", "mhm",
    "shh", "ss", "tsk", "tch", "brr", "zzz", "psst", "bzz",
    # Tamil filler / noise syllables
    "ம்", "ஆ", "அ", "ஹ்ம்", "ஊ", "ஏ", "ஓ", "ஹ்",
    # Telugu filler / noise syllables
    "ఊ", "ఆ", "అ", "హ్మ్", "హ్",
}

# Hallucinated boilerplate phrases produced by neural ASR on silence / static
HALLUCINATED_ASR_PHRASES = {
    "thank you", "thanks for watching", "thank you for watching", "subtitle by", "subtitles by", "amara.org", "amara org",
    "mbc", "you", "the", "a", "an", "bye", "please", "cough", "laughter", "applause",
    "music", "audio", "silence", "noise", "subscribe", "like share subscribe",
    # Tamil / Tanglish / Telugu ASR hallucinations on static
    "சப்ஸ்கிரைப்", "லைக் பண்ணுங்க", "ஷேர் பண்ணுங்க", "நன்றி வணக்கம்", "வணக்கம் நன்றி",
    "சந்தா செலுத்துங்கள்", "సబ్‌స్క్రైబ్", "ధన్యవాదాలు",
}


def is_unreliable_or_noise_transcript(text: str | None, current_step: str = "greeting") -> bool:
    """Detect empty, acoustic echo, line noise, DTMF or spurious hallucinated transcripts.
    
    Prevents corrupting conversational state or repeating confusing questions on artifacts.
    Note: Legitimate spoken phone numbers in any language or digit format are NEVER rejected.
    """
    if not text:
        return True

    clean = text.strip()
    if not clean:
        return True

    # 1. Punctuation only or bracketed noise tags like [music], (laughter)
    if re.match(r"^[\s.,?!:;\-_'\"/\\()\[\]{}]+$", clean):
        return True
    if re.match(r"^(\[|\()(music|applause|laughter|noise|cough|cheering|throat clearing)(\]|\))$", clean.lower()):
        return True

    # 2. Check if text contains a valid phone number (in digits or spoken words)
    if extract_phone_number(clean):
        return False

    # 3. Pure digit strings (with optional trailing dots/commas/spaces) e.g. "880.", "880", "123"
    digits_only = re.sub(r"[^\d]", "", clean)
    letters_only = re.sub(r"[^A-Za-z\u0B80-\u0BFF\u0C00-\u0C7F]", "", clean)

    if digits_only and not letters_only:
        # A phone number or long sequence of digits is never noise
        if len(digits_only) >= 10:
            return False
        # If in awaiting_datetime, rescheduling_datetime, or phone step, numbers represent time or phone
        if current_step in ("awaiting_datetime", "rescheduling_datetime", "awaiting_phone", "phone_number"):
            return False
        # In other steps, short bare digits (< 7 digits, e.g. "880.", "12", "123") are line noise/DTMF
        if len(digits_only) < 7:
            return True
        return False

    # 4. Very short noise bursts (e.g. single non-vowel Latin letter like 'x', 'q', 'z', 'k', '.')
    if len(clean) == 1 and clean.lower() not in ("a", "i", "o", "u"):
        return True

    # 5. Common hallucinated ASR boilerplate on silence
    clean_lower = clean.lower()
    clean_norm = re.sub(r"[^\w\s\u0B80-\u0BFF\u0C00-\u0C7F]", " ", clean_lower).strip()
    normalized_phrase = " ".join(clean_norm.split())
    if clean_lower in HALLUCINATED_ASR_PHRASES or normalized_phrase in HALLUCINATED_ASR_PHRASES:
        return True

    # 6. Noise filler tokens and breathing artifacts (e.g. "uh", "um", "ah hmm", "ம்", "ஆ")
    tokens = clean_norm.split()
    if tokens and all(t in NOISE_FILLER_TOKENS for t in tokens):
        return True

    # 7. Repetitive noise syllables / stutter hallucinations (e.g. "ha ha ha", "la la la")
    if len(tokens) >= 3 and len(set(tokens)) == 1:
        return True

    return False


def detect_intent(text: str) -> str:
    """Classify the caller's intent from speech input with multilingual support."""
    if not text:
        return "unknown"

    # 1. Advanced Natural Receptionist Intent Classification
    nat_intent, _ = classify_natural_receptionist_intent(text)
    if nat_intent != "unknown":
        return nat_intent

    lower = text.lower()

    # 1. Exit / Goodbye keywords (Note: 'நன்றி' alone means 'Thank you' and is not cancellation)
    if any(k in lower for k in [
        "bye", "goodbye", "exit", "nevermind", "no thanks",
        "don't want", "dont want", "வேண்டாம்", "போதும்",
        "vendam", "podhum", "mudikalam", "call cut",
        "వద్దు", "vaddu", "vaddhu", "చాలు", "chalu", "chalamma",
        "undandi", "call cut cheyandi",
    ]) or "வேண்டாம் நன்றி" in lower or "நன்றி வேண்டாம்" in lower:
        return "cancellation"

    # 2. Existing Appointment Enquiry
    if any(k in lower for k in [
        "check my appointment", "check appointment", "do i have an appointment",
        "do i have an upcoming appointment", "upcoming appointment", "have an appointment",
        "have any appointment", "my upcoming appointment",
        "existing appointment", "my appointment details", "when is my appointment",
        "status of my appointment", "check my booking", "enquire appointment",
        "appointment iruka", "appointment eppo", "ennoda appointment",
        "முன்பதிவு இருக்கிறதா", "என் முன்பதிவு", "முன்பதிவு நிலை",
        "appointment undha", "naa appointment", "eppudu appointment",
        "అపాయింట్‌మెంట్ ఉందా", "నా అపాయింట్‌మెంట్", "అపాయింట్‌మెంట్ వివరాలు",
    ]):
        return "check_existing_appointment"

    # 3. Appointment Cancellation intent
    if any(k in lower for k in [
        "cancel appointment", "cancel my appointment", "appointment cancel",
        "drop appointment", "ரத்து", "முன்பதிவை ரத்து", "ரத்து செய்",
        "cancel pannanum", "appointment-ai cancel",
        "రద్దు", "రద్దు చేయండి", "అపాయింట్‌మెంట్ రద్దు",
        "cancel cheyandi", "raddhu cheyandi", "cancel cheyali", "appointment-ni cancel",
    ]):
        return "cancel_appointment"

    # 4. Appointment Rescheduling intent
    if any(k in lower for k in [
        "reschedule", "change time", "change date", "postpone", "prepone",
        "மாற்ற வேண்டும்", "நேரத்தை மாற்ற", "தேதியை மாற்ற",
        "mathanum", "maathanum", "reschedule pannanum", "appointment matha",
        "మార్చండి", "సమయం మార్చండి", "తేదీ మార్చండి",
        "marchandi", "change cheyandi", "reschedule cheyandi", "time marchali", "date marchali",
    ]):
        return "reschedule_appointment"

    # 5. Business Information Queries
    if any(k in lower for k in [
        "where are you located", "where is the clinic", "where is the hospital",
        "what is your address", "location of clinic", "hospital location",
        "where is your clinic", "where is your office",
        "directions", "எங்கே உள்ளது", "முகவரி", "engirukku", "engae",
        "ekkada undi", "address enti", "చిరునామా", "ఎక్కడ ఉంది",
    ]):
        return "business_inquiry_address"

    if any(k in lower for k in [
        "working hours", "timings", "opening hours", "when are you open",
        "what time do you open", "open on sunday", "open today", "clinic timings",
        "operating hours", "business hours", "when does the clinic open", "what time does the clinic open",
        "வேலை நேரம்", "திறந்திருக்கும் நேரம்", "திறக்கும் நேரம்", "எத்தனை மணிக்கு திறக்கும்", "எப்போது திறக்கும்", "திறக்கும்",
        "opening time", "closing time", "ethana maniki thirakkum",
        "panichese samayam", "timings enti", "pani vela", "పనిచేసే సమయం", "వేళలు", "eppudu therustharu", "eppudu open",
    ]):
        return "business_inquiry_hours"

    if any(k in lower for k in [
        "what services", "list of services", "which doctors", "what treatments",
        "what departments", "what do you offer", "services available",
        "available services", "specialities",
        "என்ன சேவைகள்", "என்னென்ன சிகிச்சைகள்", "services enna", "services enti",
        "ye services unnayi", "ఏ సేవలు ఉన్నాయి",
    ]):
        return "business_inquiry_services"

    # 6. Check Availability / Slots intent
    if any(k in lower for k in [
        "slots", "available", "availability", "when can i", "is doctor available",
        "free slots", "open slots", "is the doctor there", "doctor availability",
        "நேரம் இருக்கிறதா", "நேரம் இருக்குமா", "எப்போது கிடைக்கும்", "டாக்டர் இருக்கிறாரா", "மருத்துவர் இருக்கிறாரா",
        "டாக்டர் இருப்பாரா", "மருத்துவர் இருப்பாரா", "டாக்டர் எப்போது வருவார்",
        "கிடைக்குமா", "appointment கிடைக்குமா", "slot கிடைக்குமா",
        "slot iruka", "slots iruka", "slot irukka", "slots irukka", "neram iruka", "neram irukka", "available-ah", "eppo varalam",
        "time irukka", "time iruka", "time irukkuma", "time kidaikuma", "morning la time irukka", "morning time irukka", "morning time iruka", "kaalaila time irukka",
        "doctor irukaara", "doctor irukangala", "doctor available-ah",
        "kidaikuma", "kedaikuma", "appointment kidaikuma", "slot kidaikuma", "slots kidaikuma",
        "స్లాట్లు ఉన్నాయా", "సమయం ఉందా", "ఎప్పుడు రావచ్చు", "డాక్టర్ ఉన్నారా",
        "slots unnaya", "time undha", "eppudu raavachu", "available undha", "doctor unnara",
    ]):
        return "check_availability"

    # 7. Denial keywords (checked BEFORE confirmation because "don't confirm" contains "confirm")
    if any(k in lower for k in [
        "no don't", "no dont", "dont confirm", "don't confirm", "do not confirm",
        "no that's wrong", "not now", "no do not", "cancel it", "don't book", "dont book",
        "no", "வேண்டாம்", "வద్దు", "vaddu", "vendam", "vaddhu",
    ]):
        return "denial"

    # 8. Conversational recovery or hold checks
    if is_conversational_recovery(lower):
        return "conversational_recovery"
    if is_hold_or_pause_request(lower):
        return "hold_request"

    # 9. Symptom / Illness Report (Reporting illness must NEVER be classified as confirming an appointment)
    if has_symptom_or_illness(lower):
        return "booking"

    # 10. Affirmative / Confirmation keywords (checked BEFORE booking so phrases like "seri book pannunga" confirm)
    if not has_symptom_or_illness(lower) and any(k in lower for k in [
        "yes please", "confirm", "confirm booking", "confirm my appointment",
        "yes confirm", "please confirm", "sure confirm", "சரி உறுதி",
        "உறுதி செய்", "ஆம் சரி", "ஆம் உறுதி", "అవును నిర్ధారించండి",
        "ఖచ్చితంగా నిర్ధారించండి", "అవును సరే", "avunu thappakunda",
        "confirm pannanum", "confirm cheyandi",
        "seri book pannunga", "book pannunga", "book pannidunga", "seri pannunga",
        "pannunga", "pannidunga", "சரி பதிவு செய்யுங்கள்", "பதிவு செய்யுங்கள்",
        "sare book cheyandi", "book cheyandi",
    ]):
        if not re.search(r"\b(?:not\s+fine|not\s+okay|seri\s+illa|sari\s+illa|mudiyala|mudila)\b", lower):
            return "confirmation"

    # Conversational acknowledgment / filler
    if not has_symptom_or_illness(lower) and any(k in lower for k in [
        "yes", "sure", "okay", "fine", "correct",
        "yeah", "yep", "சரி", "ஆம்", "ஆமாம்", "sari", "aama", "kandippa",
        "అవును", "సరే", "ఖచ్చితంగా", "avunu", "thappakunda", "alage", "nijam",
    ]):
        if not re.search(r"\b(?:not\s+fine|not\s+okay|seri\s+illa|sari\s+illa|mudiyala|mudila)\b", lower):
            return "confirmation"

    # 11. Booking & Symptom intent
    if any(k in lower for k in [
        "book", "appointment", "schedule", "reserve", "doctor",
        "consultation", "visit", "see", "checkup", "physician",
        "unwell", "sick", "ill", "headache", "fever", "cough", "cold", "pain",
        "see a doctor", "consult a doctor", "doctor consultation", "medical consultation",
        "need an appointment", "want an appointment", "book an appointment",
        "அப்பாயின்ட்மென்ட்", "முன்பதிவு", "டாக்டர்", "டாக்டர", "பார்க்க", "பார்க்க வேண்டும்",
        "வேண்டும்", "ஆலோசனை", "சிகிச்சை",
        "venum", "parkanum", "pannanum", "doctor-ah parkanum", "doctor-ah paakanum",
        "doctor paakanum", "paakanum", "pakanum", "paarkanum", "maruthuvar",
        "odambu seri illa", "udambu mudiyala", "odambu mudiyala", "udambu seri illa", "odambu", "udambu",
        "thala vali", "thalavali", "kaachal", "sali", "irumal", "valikudhu", "valikuthu", "vali",
        "உடம்பு சரியில்லை", "உடம்பு முடியல", "தலைவலி", "காய்ச்சல்", "சளி", "இருமல்",
        "బుక్ చేయాలి", "అపాయింట్‌మెంట్", "అపాయింట్‌మెంట్ కావాలి", "డాక్టర్ కావాలి", "డాక్టర్", "డాక్టర", "దర్శనం",
        "book cheyali", "appointment kavali", "doctor kavali", "chupinchukovali", "chudali",
        "ontlo bagoledu", "thala noppi", "jwaram", "daggu", "jalubu", "noppi",
    ]):
        return "booking"

    # 10. Greeting keywords
    if any(k in lower for k in [
        "hello", "hi", "hey", "good morning", "good evening",
        "வணக்கம்", "vanakkam", "namaste",
        "నమస్కారం", "నమస్తే", "namaskaram", "namaskaramandi",
    ]):
        return "greeting"

    return "unknown"


def match_service_from_catalog(text: str, services: list[Service]) -> Service | None:
    """Identify the requested service from speech matching against active business catalog.

    Supports:
    1. Direct name match and substring matching.
    2. Domain alias and STT confusion mapping across English, Indian English, Tamil, Tanglish, Telugu, Teluglish.
    3. Full string fuzzy sequence matching (e.g. 'mediatrix head checkup' -> 'Pediatric Health Checkup').
    4. Word-level fuzzy similarity (e.g. 'mediatrix' -> 'pediatric', 'head' -> 'health').
    5. Distinctive keyword mapping against active catalog offerings with stopword weighting.
    """
    if not text or not services:
        return None

    # Filter only active services
    active_services = [s for s in services if getattr(s, "is_active", True)]
    if not active_services:
        return None

    clean_text = re.sub(r"[^\w\s\u0B80-\u0BFF\u0C00-\u0C7F]", " ", text.lower()).strip()
    if not clean_text or is_short_affirmative_or_filler(clean_text) or is_unreliable_or_noise_transcript(clean_text, "awaiting_service"):
        return None

    # 1. Direct name match (full service name or distinctive name)
    for srv in active_services:
        if not srv.name:
            continue
        srv_clean = re.sub(r"[^\w\s\u0B80-\u0BFF\u0C00-\u0C7F]", " ", srv.name.lower()).strip()
        if srv_clean in clean_text or clean_text in srv_clean:
            return srv

    # 2. Domain alias & STT confusion matching across English, Tamil, and Telugu
    matched_candidates: list[tuple[int, Service]] = []
    for key, aliases in SERVICE_ALIASES.items():
        for alias in aliases:
            is_matched = False
            if re.search(r"[\u0B80-\u0BFF\u0C00-\u0C7F]", alias):
                is_matched = alias in clean_text
            else:
                is_matched = bool(re.search(r"\b" + re.escape(alias) + r"\b", clean_text, re.IGNORECASE))

            if is_matched:
                for srv in active_services:
                    srv_lower = srv.name.lower()
                    key_match = False
                    if key == "physician" and any(k in srv_lower for k in ("physician", "general", "medicine", "doctor", "consultation")):
                        key_match = True
                    elif key == "cardio" and any(k in srv_lower for k in ("cardio", "heart", "ecg")):
                        key_match = True
                    elif key == "pediatric" and any(k in srv_lower for k in ("pediatric", "child", "baby", "kid")):
                        key_match = True
                    elif key == "dental" and any(k in srv_lower for k in ("dental", "dentist", "tooth", "teeth")):
                        key_match = True
                    elif key == "diagnostics" and any(k in srv_lower for k in ("blood", "diagnostic", "lab", "profile")):
                        key_match = True
                    elif any(a in srv_lower for a in aliases):
                        key_match = True

                    if key_match:
                        matched_candidates.append((len(alias), srv))

    if matched_candidates:
        matched_candidates.sort(key=lambda x: x[0], reverse=True)
        return matched_candidates[0][1]

    # 3. Fuzzy sequence matching against catalog service names (e.g. 'mediatrix head checkup' vs 'pediatric health checkup')
    best_fuzzy_srv: Service | None = None
    best_fuzzy_score = 0.0
    for srv in active_services:
        if not srv.name:
            continue
        srv_lower = srv.name.lower()
        ratio = SequenceMatcher(None, clean_text, srv_lower).ratio()
        if ratio > best_fuzzy_score:
            best_fuzzy_score = ratio
            best_fuzzy_srv = srv

    if best_fuzzy_srv and best_fuzzy_score >= 0.60:
        logger.info("Matched service '%s' via fuzzy string similarity (score: %.3f) for speech '%s'", best_fuzzy_srv.name, best_fuzzy_score, text)
        return best_fuzzy_srv

    # 4. Word-level fuzzy similarity (e.g. 'mediatrix' vs 'pediatric' >= 0.72)
    best_word_srv: Service | None = None
    best_word_score = 0
    clean_words = [w for w in clean_text.split() if len(w) >= 4]
    for srv in active_services:
        srv_tokens = [t for t in re.findall(r"\w+", srv.name.lower()) if len(t) >= 4]
        match_count = 0
        for cw in clean_words:
            for st in srv_tokens:
                if SequenceMatcher(None, cw, st).ratio() >= 0.72:
                    match_count += 1
                    break
        if match_count > best_word_score:
            best_word_score = match_count
            best_word_srv = srv

    if best_word_srv and best_word_score > 0:
        logger.info("Matched service '%s' via word-level fuzzy tokens (matches: %d) for speech '%s'", best_word_srv.name, best_word_score, text)
        return best_word_srv

    # 5. Match distinctive words of service name (excluding generic words like 'and', 'care', 'consultation')
    generic_stopwords = {"and", "care", "consultation", "service", "center", "clinic", "for", "the", "please", "want", "book", "appointment"}
    best_match: Service | None = None
    best_score = 0
    for srv in active_services:
        tokens = [
            t for t in re.findall(r"\w+", srv.name.lower())
            if len(t) > 3 and t not in generic_stopwords
        ]
        score = sum(1 for token in tokens if re.search(r"\b" + re.escape(token) + r"\b", clean_text))
        if score > best_score:
            best_score = score
            best_match = srv

    if best_match and best_score > 0:
        return best_match

    return None


def extract_datetime_from_speech(
    text: str,
    reference_dt: datetime | None = None,
) -> tuple[datetime | None, str | None]:
    """Parse relative or explicit date and time from spoken utterance in English, Tamil, or Tanglish."""
    if not text:
        return None, "empty_text"

    now = reference_dt or datetime.now(timezone.utc)
    lower = text.lower()

    # --- 1. Target Date Resolution ---
    target_date = None

    # Check relative dates
    if any(k in lower for k in ["today", "இன்று", "iniku", "iniki", "ఈ రోజు", "ఈరోజు", "ivvala", "ee roju", "eeroju"]):
        target_date = now.date()
    elif any(k in lower for k in ["day after tomorrow", "நாளை மறுநாள்", "naalai marunaal", "ఎల్లుండి", "ellundi"]):
        target_date = (now + timedelta(days=2)).date()
    elif any(k in lower for k in ["tomorrow", "நாளை", "naalaiki", "naalaiku", "naalaki", "nalaiku", "nalaikku", "naalaikku", "naalai", "రేపు", "repu"]):
        target_date = (now + timedelta(days=1)).date()
    else:
        # Check weekdays
        weekdays = {
            "monday": 0, "திங்கள்": 0, "thingal": 0, "సోమవారం": 0, "somavaram": 0,
            "tuesday": 1, "செவ்வாய்": 1, "sevvai": 1, "మంగళవారం": 1, "mangalavaram": 1,
            "wednesday": 2, "புதன்": 2, "budhan": 2, "బుధవారం": 2, "budhavaram": 2,
            "thursday": 3, "வியாழன்": 3, "vyazhan": 3, "గురువారం": 3, "guruvaram": 3,
            "friday": 4, "வெள்ளி": 4, "velli": 4, "శుక్రవారం": 4, "sukravaram": 4,
            "saturday": 5, "சனி": 5, "sani": 5, "శనివారం": 5, "sanivaram": 5,
            "sunday": 6, "ஞாயிறு": 6, "gnaayiru": 6, "ఆదివారం": 6, "aadhivaram": 6, "adivaram": 6,
        }
        for day_name, day_idx in weekdays.items():
            if day_name in lower:
                days_ahead = (day_idx - now.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7
                target_date = (now + timedelta(days=days_ahead)).date()
                break

        # Check explicit ISO format: YYYY-MM-DD
        if not target_date:
            iso_match = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", lower)
            if iso_match:
                try:
                    target_date = datetime(
                        int(iso_match.group(1)),
                        int(iso_match.group(2)),
                        int(iso_match.group(3)),
                    ).date()
                except ValueError:
                    pass

    # --- 2. Target Time Resolution ---
    hour: int | None = None
    minute: int = 0

    # Pattern A: 10:30 AM / 10 AM / 2 PM
    time_ampm = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)\b", lower)
    if time_ampm:
        raw_hour = int(time_ampm.group(1))
        minute = int(time_ampm.group(2) or 0)
        ampm = time_ampm.group(3).replace(".", "").lower()
        if ampm == "pm" and raw_hour < 12:
            hour = raw_hour + 12
        elif ampm == "am" and raw_hour == 12:
            hour = 0
        else:
            hour = raw_hour

    # Pattern B: Tamil / Tanglish / Telugu "10 மணிக்கு" / "10 maniki" / "10 గంటలకు" / "10 gantalu"
    if hour is None:
        mani_match = re.search(
            r"\b(\d{1,2})(?::(\d{2}))?\s*(?:மணி|மணிக்க|மணிக்கு|manikku|maniku|mani|maniki|mani-ku|గంట|గంటలు|గంటలకు|గంటలకి|ganta|gantalu|gantaku|gantalaki|gantalaku|ki)",
            lower,
        )
        if mani_match:
            raw_hour = int(mani_match.group(1))
            minute = int(mani_match.group(2) or 0)
            if any(k in lower for k in ["மாலை", "இரவு", "maalai", "sayanthiram", "night", "pm", "సాయంత్రం", "రాత్రి", "sayantram", "raathri"]) and raw_hour < 12:
                hour = raw_hour + 12
            elif any(k in lower for k in ["மதியம்", "madhiyam", "afternoon", "మధ్యాహ్నం", "madhyanam"]) and raw_hour <= 4:
                hour = raw_hour + 12
            else:
                hour = raw_hour

    # Pattern C: Military 24h: 14:00, 10:30
    if hour is None:
        mil_match = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", lower)
        if mil_match:
            hour = int(mil_match.group(1))
            minute = int(mil_match.group(2))

    # Pattern D: "at 10", "around 11", "10 o'clock", "actually 11 AM", "make it 4 PM"
    if hour is None:
        oclock_match = re.search(r"\b(\d{1,2})\s*(?:o'clock|oclock|clock)\b", lower)
        if not oclock_match:
            oclock_match = re.search(r"\b(?:at|around|actually|make it)\s+(\d{1,2})(?:[:.](\d{2}))?\b", lower)
        if oclock_match:
            raw_h = int(oclock_match.group(1))
            if 1 <= raw_h <= 12:
                minute = int(oclock_match.group(2) or 0) if oclock_match.lastindex and oclock_match.lastindex >= 2 and oclock_match.group(2) else 0
                if any(k in lower for k in ["afternoon", "evening", "night", "pm"]) and raw_h < 12:
                    hour = raw_h + 12
                elif any(k in lower for k in ["morning", "am"]):
                    hour = 0 if raw_h == 12 else raw_h
                elif 1 <= raw_h <= 6:
                    hour = raw_h + 12
                else:
                    hour = raw_h

    if target_date and hour is not None:
        parsed_dt = datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            hour,
            minute,
            tzinfo=timezone.utc,
        )
        return parsed_dt, None

    if target_date and hour is None:
        return None, "missing_time"

    if not target_date and hour is not None:
        return None, "missing_date"

    return None, "missing_datetime"


def extract_date_and_time_parts(
    text: str,
    reference_dt: datetime | None = None,
) -> tuple[date | None, tuple[int, int] | None]:
    """Parse relative or explicit date and time from spoken utterance in English, Tamil, Telugu, Tanglish, or Teluglish.

    Returns:
        tuple[date | None, tuple[int, int] | None]: (extracted_date, (hour, minute))
    """
    if not text:
        return None, None

    now = reference_dt or datetime.now(timezone.utc)
    lower = text.lower()

    # 1. Date
    target_date = None
    if any(k in lower for k in ["today", "இன்று", "iniku", "iniki", "இந்த நாள்", "இந்த தேதி", "ఈ రోజు", "ఈరోజు", "ivvala", "ee roju", "eeroju"]):
        target_date = now.date()
    elif any(k in lower for k in ["day after tomorrow", "நாளை மறுநாள்", "naalai marunaal", "naalai maru naal", "ఎల్లుండి", "ellundi"]):
        target_date = (now + timedelta(days=2)).date()
    elif any(k in lower for k in ["tomorrow", "நாளை", "naalaiki", "naalaiku", "naalaki", "nalaiku", "nalaikku", "naalaikku", "naalai", "ரேபு", "రేపు", "repu"]):
        target_date = (now + timedelta(days=1)).date()
    else:
        weekdays = {
            "monday": 0, "திங்கள்": 0, "thingal": 0, "சோமవారం": 0, "somavaram": 0,
            "tuesday": 1, "செவ்வாய்": 1, "sevvai": 1, "మంగళవారం": 1, "mangalavaram": 1,
            "wednesday": 2, "புதன்": 2, "budhan": 2, "புதன்கிழமை": 2, "బుధవారం": 2, "budhavaram": 2,
            "thursday": 3, "வியாழன்": 3, "vyazhan": 3, "வியாழக்கிழமை": 3, "గురువారం": 3, "guruvaram": 3,
            "friday": 4, "வெள்ளி": 4, "velli": 4, "வெள்ளிக்கிழமை": 4, "శుక్రవారం": 4, "sukravaram": 4,
            "saturday": 5, "சனி": 5, "sani": 5, "சனிக்கிழமை": 5, "శనివారం": 5, "sanivaram": 5,
            "sunday": 6, "ஞாயிறு": 6, "gnaayiru": 6, "ஞாயிற்றுக்கிழமை": 6, "ఆదివారం": 6, "aadhivaram": 6, "adivaram": 6,
        }
        for day_name, day_idx in weekdays.items():
            is_match = (re.search(r"\b" + re.escape(day_name) + r"\b", lower) is not None) if day_name.isascii() else (day_name in lower)
            if is_match:
                days_ahead = (day_idx - now.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7
                target_date = (now + timedelta(days=days_ahead)).date()
                break

        if not target_date:
            iso_match = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", lower)
            if iso_match:
                try:
                    target_date = datetime(
                        int(iso_match.group(1)),
                        int(iso_match.group(2)),
                        int(iso_match.group(3)),
                    ).date()
                except ValueError:
                    pass

    # 2. Time
    hour: int | None = None
    minute: int = 0

    time_ampm = re.search(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)\b", lower)
    if time_ampm:
        raw_hour = int(time_ampm.group(1))
        minute = int(time_ampm.group(2) or 0)
        ampm = time_ampm.group(3).replace(".", "").lower()
        if ampm == "pm" and raw_hour < 12:
            hour = raw_hour + 12
        elif ampm == "am" and raw_hour == 12:
            hour = 0
        else:
            hour = raw_hour

    if hour is None:
        mani_match = re.search(
            r"\b(\d{1,2})(?:[:.](\d{2}))?\s*(?:மணி|மணிக்க|மணிக்கு|manikku|maniku|mani|maniki|mani-ku|மனி|గంట|గంటలు|గంటలకు|గంటలకి|గంటకు|ganta|gantalu|gantaku|gantalaki|gantalaku|ki)",
            lower,
        )
        if mani_match:
            raw_hour = int(mani_match.group(1))
            minute = int(mani_match.group(2) or 0)
            if any(k in lower for k in ["மாலை", "இரவு", "maalai", "sayanthiram", "night", "pm", "సాయంత్రం", "రాత్రి", "sayantram", "raathri"]) and raw_hour < 12:
                hour = raw_hour + 12
            elif any(k in lower for k in ["மதியம்", "madhiyam", "afternoon", "మధ్యాహ్నం", "madhyanam"]) and raw_hour <= 4:
                hour = raw_hour + 12
            elif any(k in lower for k in ["காலை", "kaalai", "morning", "ఉదయం", "పొద్దున", "udhayam", "podduna"]) and raw_hour == 12:
                hour = 0
            else:
                hour = raw_hour

    if hour is None:
        mil_match = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", lower)
        if mil_match:
            hour = int(mil_match.group(1))
            minute = int(mil_match.group(2))

    if hour is None:
        oclock_match = re.search(r"\b(\d{1,2})\s*(?:o'clock|oclock|clock)\b", lower)
        if not oclock_match:
            oclock_match = re.search(r"\b(?:at|around|actually|make it)\s+(\d{1,2})(?:[:.](\d{2}))?\b", lower)
        if oclock_match:
            raw_h = int(oclock_match.group(1))
            if 1 <= raw_h <= 12:
                minute = int(oclock_match.group(2) or 0) if oclock_match.lastindex and oclock_match.lastindex >= 2 and oclock_match.group(2) else 0
                if any(k in lower for k in ["afternoon", "evening", "night", "pm"]) and raw_h < 12:
                    hour = raw_h + 12
                elif any(k in lower for k in ["morning", "am"]):
                    hour = 0 if raw_h == 12 else raw_h
                elif 1 <= raw_h <= 6:
                    hour = raw_h + 12
                else:
                    hour = raw_h

    time_tuple = (hour, minute) if hour is not None else None
    return target_date, time_tuple


def extract_caller_name(text: str, is_awaiting_name: bool = False) -> str | None:
    """Extract caller's name from spoken text."""
    if not text:
        return None

    # Never extract a name from an utterance reporting illness, symptoms, or emergency
    if has_symptom_or_illness(text) or check_medical_emergency(text):
        return None

    # Pattern matches
    patterns = [
        r"(?:my name is|this is|i am|name is|\bname\b(?:\s+is)?|i'm|call me|book for|patient is|patient name is)\s+([A-Za-z\s]+)",
        r"(?:என் பெயர்|பெயர்)\s+([^\s,]+)",
        r"(?:en peyar|en peru)\s+([A-Za-z\s]+)",
        r"(?:నా పేరు|పేరు)\s+([^\s,]+)",
        r"(?:naa peru|na peru)\s+([A-Za-z\s]+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            candidate = re.sub(r"[^\w\s\u0B80-\u0BFF\u0C00-\u0C7F]", "", candidate).strip()
            words = candidate.split()
            filtered = [w for w in words if w.lower() not in {"and", "i", "want", "to", "book", "please", "consultation"}]
            if filtered:
                return " ".join(filtered[:3]).title()

    # If the assistant specifically asked for name, process direct answers
    if is_awaiting_name:
        cleaned = re.sub(r"^(?:yes|sure|okay|yeah|it is|it's|its|my name is|i am|en peyar|naa peru)\s+", "", text.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r"[^\w\s\u0B80-\u0BFF\u0C00-\u0C7F]", "", cleaned).strip()
        words = cleaned.split()
        if 1 <= len(words) <= 4:
            invalid_words = {
                "appointment", "doctor", "cardiology", "physician", "hospital", "clinic", "cancel", "yes", "no",
                "odambu", "udambu", "seri", "sari", "illa", "thala", "vali", "kaachal", "sali", "irumal", "mudiyala",
                "fever", "cough", "cold", "headache", "pain", "unwell", "sick", "ill", "not", "well", "fine",
                "ontlo", "bagoledu", "noppi", "jwaram", "daggu", "jalubu", "morning", "afternoon", "evening",
                "time", "date", "today", "tomorrow", "repu", "naalai", "naalaiku"
            }
            if not any(w.lower() in invalid_words for w in words):
                return " ".join(words).title()

    return None


def format_confirmation_date(dt: datetime, language: str = "en-IN", biz_tz: Any = None) -> str:
    """Format appointment datetime for natural speech synthesis in local business timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if biz_tz:
        dt = dt.astimezone(biz_tz)
    if language == "ta-Latn" or language == "te-Latn":
        return dt.strftime("%B %d")
    if language.startswith("ta"):
        months_ta = [
            "", "ஜனவரி", "பிப்ரவரி", "மார்ச்", "ஏப்ரல்", "மே", "ஜூன்",
            "ஜூலை", "ஆகஸ்ட்", "செப்டம்பர்", "அக்டோபர்", "நவம்பர்", "டிசம்பர்",
        ]
        return f"{dt.day} {months_ta[dt.month]}"
    if language.startswith("te"):
        months_te = [
            "", "జనవరి", "ఫిబ్రవరి", "మార్చి", "ఏప్రిల్", "మే", "జూన్",
            "జూలై", "ఆగస్టు", "సెప్టెంబరు", "అక్టోబరు", "నవంబరు", "డిసెంబరు",
        ]
        return f"{dt.day} {months_te[dt.month]}"
    return dt.strftime("%B %d, %Y")


def format_confirmation_time(dt: datetime, language: str = "en-IN", biz_tz: Any = None) -> str:
    """Format appointment time for natural speech synthesis in local business timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if biz_tz:
        dt = dt.astimezone(biz_tz)
    time_str = dt.strftime("%I:%M %p").lstrip("0")
    return time_str


_TENANT_CATALOG_CACHE: dict[str, dict[str, Any]] = {}


def get_cached_business_catalog(
    db: Session,
    business_id: str,
    ttl_seconds: float = 60.0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Retrieve tenant services, operating hours, and doctor schedules with a TTL cache to avoid redundant DB queries."""
    import time as _pytime
    now_mono = _pytime.monotonic()
    cached = _TENANT_CATALOG_CACHE.get(business_id)
    if cached and (now_mono - cached["timestamp"]) < ttl_seconds:
        return cached["services"], cached["hours"], cached["doctors"]

    # 1. Active services
    active_services = db.scalars(
        select(Service).where(Service.business_id == business_id, Service.is_active.is_(True))
    ).all()
    services_list = [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description or "",
            "duration_minutes": s.duration_minutes,
            "price": s.price,
        }
        for s in active_services
    ]

    # 2. Operating schedule
    op_schedule = get_all_operating_hours(db, business_id)
    hours_list = [
        {"day": h.day_name, "open": h.open_time, "close": h.close_time, "closed": h.is_closed}
        for h in op_schedule
    ]

    # 3. Doctor / staff availability
    staff_schedules = db.scalars(
        select(StaffSchedule).where(StaffSchedule.business_id == business_id, StaffSchedule.is_active.is_(True))
    ).all()
    day_map = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"}
    doc_map: dict[str, dict[str, Any]] = {}
    for s in staff_schedules:
        if s.staff_name not in doc_map:
            doc_map[s.staff_name] = {"name": s.staff_name, "available_days": []}
        doc_map[s.staff_name]["available_days"].append({
            "day": day_map.get(s.day_of_week, str(s.day_of_week)),
            "start": s.start_time,
            "end": s.end_time,
        })
    doctor_list = list(doc_map.values())

    _TENANT_CATALOG_CACHE[business_id] = {
        "timestamp": now_mono,
        "services": services_list,
        "hours": hours_list,
        "doctors": doctor_list,
    }
    return services_list, hours_list, doctor_list


def invalidate_tenant_catalog_cache(business_id: str | None = None) -> None:
    """Invalidate tenant cache on service or schedule updates."""
    if business_id:
        _TENANT_CATALOG_CACHE.pop(business_id, None)
    else:
        _TENANT_CATALOG_CACHE.clear()


# Standard clinical, medical, receptionist, and conversational loanwords/phrases
# mapped from Tamil script to standard English loanwords and natural Tanglish
TAMIL_LOANWORD_AND_PHRASE_MAP: list[tuple[str, str]] = [
    # English clinical & receptionist terms in Tamil script
    ("டாக்டர்களிடம்", "doctors kitta"),
    ("டாக்டரிடம்", "doctor kitta"),
    ("டாக்டர்களின்", "doctors oda"),
    ("டாக்டரின்", "doctor oda"),
    ("டாக்டர்கள்", "doctors"),
    ("டாக்டரா", "doctor ah"),
    ("டாக்டர்", "doctor"),
    ("அப்பாயின்ட்மென்ட்டுக்கு", "appointment ku"),
    ("அப்பாயிண்ட்மென்ட்டுக்கு", "appointment ku"),
    ("அப்பாயின்ட்மென்ட்க்கு", "appointment ku"),
    ("அப்பாயிண்ட்மென்ட்க்கு", "appointment ku"),
    ("அப்பாயின்ட்மென்ட்", "appointment"),
    ("அப்பாயிண்ட்மெண்ட்", "appointment"),
    ("அப்பாயின்மென்ட்", "appointment"),
    ("அப்பாயின்மெண்ட்", "appointment"),
    ("அப்பாயிண்ட்மென்ட்", "appointment"),
    ("புக்கிங்", "booking"),
    ("புக்", "book"),
    ("ஸ்லாட்டுகள்", "slots"),
    ("ஸ்லாட்டுக்கு", "slot ku"),
    ("ஸ்லாட்", "slot"),
    ("கிளினிக்கு", "clinic ku"),
    ("கிளினிக்கில்", "clinic la"),
    ("கிளினிக்", "clinic"),
    ("கன்சல்டேஷன்", "consultation"),
    ("கன்சல்ட்", "consult"),
    ("பிசிஷியன்", "physician"),
    ("ஜெனரல்", "general"),
    ("கார்டியாலஜிஸ்ட்", "cardiologist"),
    ("கார்டியாலஜி", "cardiology"),
    ("பீடியாட்ரிசியன்", "pediatrician"),
    ("பீடியாட்ரிக்", "pediatric"),
    ("செக்கப்", "checkup"),
    ("செக்", "check"),
    ("கட்டணம்", "fees"),
    ("பீஸ்", "fees"),
    ("பீ", "fee"),
    ("மார்னிங்", "morning"),
    ("ஈவினிங்", "evening"),
    ("ஆஃப்டர்நூன்", "afternoon"),
    ("டைமிங்", "timing"),
    ("டைம்", "time"),
    ("ஹலோ", "hello"),
    ("கன்பர்மேஷன்", "confirmation"),
    ("கன்பார்ம்", "confirm"),
    ("அவைலபிளா", "available ah"),
    ("அவைலபிள்", "available"),
    ("ஹாஸ்பிடல்", "hospital"),
    ("ஸ்பெஷலிஸ்ட்", "specialist"),
    ("சர்வீஸ்", "service"),
    ("போன்", "phone"),
    ("நம்பர்", "number"),
    ("ஆன்லைன்", "online"),
    ("பேமெண்ட்", "payment"),
    ("அட்ரஸ்", "address"),
    ("லொகேஷன்", "location"),
    ("ஃபீவர்", "fever"),
    ("காய்ச்சல்", "fever"),
    # Spoken conversational Tamil words & particles
    ("வணக்கம்", "Vanakkam"),
    ("இருக்கிறார்களா", "irukaangala"),
    ("இருக்காங்களா", "irukaangala"),
    ("இருக்காங்க", "irukaanga"),
    ("இருக்கிறார்", "irukaaru"),
    ("இருக்கின்றன", "irukku"),
    ("இருக்கும்", "irukum"),
    ("இருக்கு", "irukku"),
    ("இல்லையா", "illaya"),
    ("இல்லை", "illa"),
    ("இல்ல", "illa"),
    ("ஆமாம்", "aama"),
    ("ஆமா", "aama"),
    ("ஆம்", "aama"),
    ("நிச்சயமாக", "kandippa"),
    ("கண்டிப்பா", "kandippa"),
    ("சரி", "seri"),
    ("நாளைக்கு", "naalaiku"),
    ("இன்னிக்கு", "iniku"),
    ("இன்று", "iniku"),
    ("மணிக்கு", "manikku"),
    ("மணி", "mani"),
    ("காலை", "morning"),
    ("மதியம்", "afternoon"),
    ("மாலை", "evening"),
    ("இரவு", "night"),
    ("நேரங்கள்", "times"),
    ("நேரம்", "time"),
    ("பண்ணனுமா", "pannanuma"),
    ("பண்ணலாமா", "pannalaama"),
    ("பண்ணிடுங்க", "pannidunga"),
    ("பண்ணுங்க", "pannunga"),
    ("பண்ணுகிறேன்", "panren"),
    ("பார்க்கலாம்", "paarkalaam"),
    ("பார்க்கலாமா", "paarkalaama"),
    ("வேண்டுமா", "venuma"),
    ("வேணும்", "venum"),
    ("உங்களுக்கு", "ungalukku"),
    ("உங்க", "unga"),
    ("எந்த", "endha"),
    ("எப்போது", "eppo"),
    ("எப்பொழுது", "eppo"),
    ("எங்க", "enga"),
    ("எங்கு", "enga"),
    ("எப்படி", "eppadi"),
    ("சொல்லுங்கள்", "sollunga"),
    ("சொல்லுங்க", "sollunga"),
    ("பெயர்", "peru"),
    ("பேர்", "peru"),
    ("வசதியாக", "convenient ah"),
    ("வசதியா", "convenient ah"),
    ("வசதி", "convenient"),
    ("நன்றி", "nandri"),
    ("ரூபாய்", "rupees"),
    ("நகரில்", "Nagar la"),
    ("நகர்ல", "Nagar la"),
    ("அண்ணா", "Anna"),
]


def tamil_script_to_tanglish(text: str) -> str:
    """Phonetically transliterate Tamil Unicode script into natural, readable Tanglish (Latin alphabet).

    Preserves standard English clinical loanwords (doctor, appointment, book, slot, morning, fees)
    and conversational receptionist phrases (Vanakkam, irukaanga, naalaiku, pannanuma, kandippa)
    so Sarvam Bulbul v4 Flash pronounces them clearly without phonetic distortion or stuttering.
    """
    if not text:
        return ""

    # 1. First replace known clinical loanwords and receptionist phrases
    res = text
    for tamil_term, tanglish_equiv in sorted(TAMIL_LOANWORD_AND_PHRASE_MAP, key=lambda x: -len(x[0])):
        res = res.replace(tamil_term, tanglish_equiv)

    # If no remaining Tamil Unicode characters, return immediately
    if not re.search(r"[\u0B80-\u0BFF]", res):
        return res

    # 2. Phonetically transliterate any remaining Tamil Unicode syllables
    tamil_vowels = {
        "\u0B85": "a", "\u0B86": "aa", "\u0B87": "i", "\u0B88": "ee",
        "\u0B89": "u", "\u0B8A": "oo", "\u0B8E": "e", "\u0B8F": "ae",
        "\u0B90": "ai", "\u0B92": "o", "\u0B93": "oa", "\u0B94": "au",
        "\u0B83": "h",
    }
    tamil_consonants = {
        "\u0B95": "k", "\u0B99": "ng", "\u0B9A": "ch", "\u0B9C": "j",
        "\u0B9E": "nj", "\u0B9F": "t", "\u0BA3": "n", "\u0BA4": "th",
        "\u0BA8": "n", "\u0BA9": "n", "\u0BAA": "p", "\u0BAE": "m",
        "\u0BAF": "y", "\u0BB0": "r", "\u0BB1": "r", "\u0BB2": "l",
        "\u0BB3": "l", "\u0BB4": "zh", "\u0BB5": "v", "\u0BB7": "sh",
        "\u0BB8": "s", "\u0BB9": "h",
    }
    tamil_vowel_signs = {
        "\u0BBE": "aa", "\u0BBF": "i", "\u0BC0": "ee", "\u0BC1": "u",
        "\u0BC2": "oo", "\u0BC6": "e", "\u0BC7": "ae", "\u0BC8": "ai",
        "\u0BCA": "o", "\u0BCB": "oa", "\u0BCC": "au",
    }
    virama = "\u0BCD"

    out: list[str] = []
    i = 0
    n = len(res)
    while i < n:
        c = res[i]
        if c in tamil_vowels:
            out.append(tamil_vowels[c])
            i += 1
        elif c in tamil_consonants:
            base = tamil_consonants[c]
            if i + 1 < n and res[i + 1] == virama:
                out.append(base)
                i += 2
            elif i + 1 < n and res[i + 1] in tamil_vowel_signs:
                out.append(base + tamil_vowel_signs[res[i + 1]])
                i += 2
            else:
                out.append(base + "a")
                i += 1
        elif c in tamil_vowel_signs or c == virama:
            out.append(tamil_vowel_signs.get(c, ""))
            i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def generate_natural_fallback_response(
    session: ConversationSession,
    business: Business,
    speech_clean: str,
    db: Session,
) -> tuple[str, bool]:
    """Generate a fast, natural, language-consistent fallback response when LLM is unavailable or times out.

    Preserves full conversational state (step, entities, caller phone, customer name, slot).
    """
    lang = session.language or "en-IN"
    step = session.step or "greeting"

    # 1. If appointment was already confirmed in this session
    if session.booking_id:
        if lang == "ta-Latn":
            msg = f"Unga appointment confirm aayidichu. {business.name}-ku call pannadhukku nandri. Vera edhavadhu udhavi thevaiya?"
        elif lang.startswith("ta"):
            msg = f"உங்கள் முன்பதிவு உறுதி செய்யப்பட்டுள்ளது. {business.name} அழைத்ததற்கு நன்றி. வேறு ஏதேனும் உதவி தேவையா?"
        elif lang == "te-Latn":
            msg = f"Mee appointment confirm ayyindi. {business.name}-ki call chesinanduku thanks. Inka emaina help kavala?"
        elif lang.startswith("te"):
            msg = f"మీ అపాయింట్‌మెంట్ విజయవంతంగా నిర్ధారించబడింది. {business.name} కు కాల్ చేసినందుకు ధన్యవాదాలు. ఇంకేమైనా సహాయం కావాలా?"
        else:
            msg = f"Your appointment has been successfully confirmed. Thank you for choosing {business.name}. Is there anything else I can assist you with?"
        return msg, True

    # 1b. Check for clinical question or symptom guidance fallback
    if speech_clean and step not in ("awaiting_datetime", "awaiting_name", "awaiting_confirmation"):
        try:
            from app.services.ai.medical_knowledge import (
                get_medical_guidance_for_response,
                query_medical_knowledge,
            )

            med_topic = query_medical_knowledge(speech_clean, lang)
            if med_topic:
                services = db.scalars(
                    select(Service).where(Service.business_id == business.id, Service.is_active.is_(True))
                ).all()
                srv_dicts = [{"id": s.id, "name": s.name, "price": s.price} for s in services]
                guidance = get_medical_guidance_for_response(med_topic, lang, matching_services=srv_dicts)
                exp = guidance.get("explanation", "")
                home = guidance.get("home_care", "")
                if lang == "ta-Latn":
                    msg = f"{exp} {home} Doctor checkup-ku appointment book pannidava?"
                elif lang.startswith("ta"):
                    msg = f"{exp} {home} மருத்துவரிடம் அப்பாயிண்ட்மெண்ட் பதிவு செய்யவா?"
                elif lang == "te-Latn":
                    msg = f"{exp} {home} Doctor appointment book cheyamantara?"
                elif lang.startswith("te"):
                    msg = f"{exp} {home} వైద్యులను సంప్రదించడానికి అపాయింట్‌మెంట్ బుక్ చేయమంటారా?"
                else:
                    msg = f"{exp} {home} Would you like to schedule a consultation with our doctor?"
                msg = format_spoken_response(msg)
                history = []
                if session.dialog_history:
                    try:
                        history = json.loads(session.dialog_history)
                    except Exception:
                        history = []
                if speech_clean and not (history and history[-1].get("text") == speech_clean):
                    history.append({"role": "caller", "text": speech_clean})
                history.append({"role": "assistant", "text": msg})
                session.dialog_history = json.dumps(history)
                db.commit()
                return msg, True
        except Exception as e:
            logger.warning("Error generating medical fallback: %s", e)

    # 2. Context-aware natural receptionist fallback based on session step
    if lang == "ta-Latn":
        if step in ("awaiting_datetime", "awaiting_time", "awaiting_date"):
            msg = "Doctor schedule-ah check panren. Ungalukku convenient aana date and time thirumba solla mudiyuma?"
        elif step in ("awaiting_service", "service_selection"):
            msg = f"Vanakkam, {business.name}-la neenga entha medical consultation book panna virumbureenga?"
        elif step in ("awaiting_name", "customer_name"):
            msg = "Unga booking confirm panna unga full name sollunga please."
        elif step in ("awaiting_confirmation", "confirming"):
            msg = "Unga appointment details confirm panna virumbureengala? Yes or no sollunga."
        else:
            msg = f"Vanakkam! {business.name} reception desk. Ungalukku indru naan eppadi udhavalam?"
    elif lang.startswith("ta"):
        if step in ("awaiting_datetime", "awaiting_time", "awaiting_date"):
            msg = "மருத்துவரின் நேர அட்டவணையை சரிபார்க்கிறேன். நீங்கள் விரும்பும் தேதி மற்றும் நேரத்தை மீண்டும் கூற முடியுமா?"
        elif step in ("awaiting_service", "service_selection"):
            msg = f"வணக்கம், {business.name}-ல் நீங்கள் எந்த மருத்துவ ஆலோசனை அல்லது சிகிச்சை பெற விரும்புகிறீர்கள்?"
        elif step in ("awaiting_name", "customer_name"):
            msg = "உங்கள் முன்பதிவிற்காக, உங்கள் முழு பெயரை தெளிவாக கூறவும்."
        elif step in ("awaiting_confirmation", "confirming"):
            msg = "உங்கள் முன்பதிவு விவரங்களை உறுதி செய்ய விரும்புகிறீர்கள்? ஆம் அல்லது இல்லை என்று கூறவும்."
        else:
            msg = f"வணக்கம்! {business.name} வரவேற்பு மையம். உங்களுக்கு இன்று நான் எவ்வாறு உதவ முடியும்?"
    elif lang == "te-Latn":
        if step in ("awaiting_datetime", "awaiting_time", "awaiting_date"):
            msg = "Doctor schedule check chestunnanu. Meku kavalsina date mariyu time malli cheppandi please."
        elif step in ("awaiting_service", "service_selection"):
            msg = f"Namaskaram, {business.name}-lo meeru ye doctor consultation book chesukovali anukuntunnaru?"
        elif step in ("awaiting_name", "customer_name"):
            msg = "Mee booking record kosam mee full name cheppandi please."
        elif step in ("awaiting_confirmation", "confirming"):
            msg = "Mee appointment confirm cheyamantara? Yes leda no cheppandi."
        else:
            msg = f"Namaskaram! {business.name}-ki swagatham. Nenu meku ela sahayam cheyagalanu?"
    elif lang.startswith("te"):
        if step in ("awaiting_datetime", "awaiting_time", "awaiting_date"):
            msg = "డాక్టర్ షెడ్యూల్ పరిశీలిస్తున్నాను. మీకు కావలసిన తేదీ మరియు సమయాన్ని మళ్ళీ చెప్పండి."
        elif step in ("awaiting_service", "service_selection"):
            msg = f"నమస్కారం, {business.name} లో మీరు ఏ వైద్య సేవ కోసం సంప్రదించాలనుకుంటున్నారు?"
        elif step in ("awaiting_name", "customer_name"):
            msg = "మీ అపాయింట్‌మెంట్ కోసం మీ పూర్తి పేరును దయచేసి చెప్పండి."
        elif step in ("awaiting_confirmation", "confirming"):
            msg = "మీ అపాయింట్‌మెంట్ వివరాలను నిర్ధారించాలనుకుంటున్నారా? అవును లేదా కాదు అని చెప్పండి."
        else:
            msg = f"నమస్కారం! {business.name} కు స్వాగతం. నేను మీకు ఎలా సహాయపడగలను?"
    else:  # en-IN / English
        if step in ("awaiting_datetime", "awaiting_time", "awaiting_date"):
            msg = "I am checking the doctor's appointment calendar right now. Could you please repeat your preferred date and time?"
        elif step in ("awaiting_service", "service_selection"):
            msg = f"Welcome to {business.name}. Which consultation or service would you like to book today?"
        elif step in ("awaiting_name", "customer_name"):
            msg = "To complete your booking, could you please provide your full name?"
        elif step in ("awaiting_confirmation", "confirming"):
            msg = "Would you like me to confirm this appointment? Please say yes or no."
        else:
            msg = f"Hello, thank you for calling {business.name}. How can I assist you with an appointment today?"

    msg = format_spoken_response(msg)

    # Append to dialog history to preserve context
    history = []
    if session.dialog_history:
        try:
            history = json.loads(session.dialog_history)
        except Exception:
            history = []
    if speech_clean and not (history and history[-1].get("text") == speech_clean):
        history.append({"role": "caller", "text": speech_clean})
    history.append({"role": "assistant", "text": msg})
    session.dialog_history = json.dumps(history)
    db.commit()

    return msg, True


def execute_llm_conversational_turn(
    db: Session,
    session: ConversationSession,
    speech_clean: str,
    business: Business,
    llm_provider: BaseLLMProvider | None = None,
    timeout_seconds: float = 8.0,
) -> tuple[str, bool]:
    """Execute a conversational turn using dynamic LLM reasoning, system prompt, and Phase 2/3 tool calling.

    Returns:
        tuple[str, bool]: (spoken_response_text, should_continue_gather)
    """
    # 1. Resolve Provider
    if llm_provider is None:
        cfg = business.assistant_config
        is_test = settings.ENVIRONMENT.lower() in ("test", "testing")
        # Ensure database "mock" does not override configured production LLM in non-test runs
        if is_test and cfg and cfg.ai_provider == "mock":
            provider_name = "mock"
            model_name = "mock"
        elif cfg and cfg.ai_provider and cfg.ai_provider not in ("mock",):
            provider_name = cfg.ai_provider
            model_name = cfg.ai_model or settings.AI_MODEL
        else:
            provider_name = settings.AI_PROVIDER or "gemini"
            model_name = settings.AI_MODEL or "gemini-3.1-flash-lite"
        llm_provider = get_llm_provider(provider_name=provider_name, model=model_name)

    # 2. Retrieve cached tenant services catalog, hours, and staff schedules
    services_list, hours_list, doctor_list = get_cached_business_catalog(db, business.id)

    # Extract phone number from speech if caller stated it in this turn
    extracted_phone = extract_phone_number(speech_clean)
    if extracted_phone:
        session.caller_phone = extracted_phone

    # 3. Build dynamic system prompt
    cfg = business.assistant_config
    assistant_name = cfg.assistant_name if cfg and cfg.assistant_name else "Vattara AI"
    profile_info = f"{business.name} ({business.vertical}). Phone: {business.phone}. Address: {business.address or 'Address on file'}."
    if cfg and cfg.business_info:
        profile_info += f" Overview: {cfg.business_info}"

    session_state = {
        "service_name": session.service_name,
        "appointment_datetime_iso": session.appointment_datetime_iso,
        "customer_name": session.customer_name,
        "customer_phone": session.caller_phone,
        "language": session.language,
        "step": session.step,
    }

    biz_tz = get_business_timezone(business)
    now_local = datetime.now(biz_tz)

    # Medical topic lookup for clinical guidance grounding
    medical_guidance_text = None
    try:
        from app.services.ai.medical_knowledge import (
            format_medical_guidance_for_prompt,
            query_medical_knowledge,
        )

        matched_topic = query_medical_knowledge(speech_clean, session.language)
        if matched_topic:
            medical_guidance_text = format_medical_guidance_for_prompt(matched_topic)
    except Exception as med_err:
        logger.warning("Error fetching medical guidance for system prompt: %s", med_err)

    system_prompt = build_system_prompt(
        assistant_name=assistant_name,
        business_name=business.name,
        current_datetime_str=now_local.strftime("%Y-%m-%d %H:%M:%S %Z"),
        timezone_str=business.timezone or "Asia/Kolkata",
        services=services_list,
        operating_hours=hours_list,
        business_profile=profile_info,
        doctor_schedules=doctor_list,
        session_state=session_state,
        medical_guidance=medical_guidance_text,
    )

    # 6. Build message history
    history: list[dict[str, str]] = []
    if session.dialog_history:
        try:
            history = json.loads(session.dialog_history)
        except Exception:
            history = []

    llm_messages: list[LLMMessage] = []
    for turn in history:
        r = "assistant" if turn.get("role") == "assistant" else "user"
        llm_messages.append(LLMMessage(role=r, content=turn.get("text", "")))
    llm_messages.append(LLMMessage(role="user", content=speech_clean))

    # 7. Invoke LLM with tools
    logger.info(
        "Invoking LLM provider '%s' for CallSid %s (speech: '%s')",
        type(llm_provider).__name__,
        session.call_sid,
        speech_clean,
    )

    llm_resp = llm_provider.generate_response(
        messages=llm_messages,
        system_prompt=system_prompt,
        active_services=services_list,
        available_tools=AI_TOOLS_SPEC,
        temperature=0.2,
        max_tokens=512,
    )

    # 8. Tool Execution Loop with Deduplication & Booking Idempotency
    max_tool_rounds = 3
    tool_round = 0
    executed_tools: set[str] = set()

    while llm_resp.tool_calls and tool_round < max_tool_rounds:
        tool_round += 1
        for tc in llm_resp.tool_calls:
            tool_key = f"{tc.function_name}_{json.dumps(tc.arguments, sort_keys=True)}"
            if tool_key in executed_tools:
                logger.info("Tool call %s already executed in this turn. Skipping duplicate.", tool_key)
                continue
            executed_tools.add(tool_key)

            logger.info("Executing tool '%s' with args %s for CallSid %s", tc.function_name, tc.arguments, session.call_sid)
            if session.caller_phone:
                raw_arg_phone = tc.arguments.get("customer_phone")
                norm_arg_phone = normalize_indian_mobile_number(raw_arg_phone) if raw_arg_phone else None
                norm_session_phone = normalize_indian_mobile_number(session.caller_phone) or session.caller_phone
                # If argument phone is missing, invalid length/unparseable (e.g. 11 digits like 70904743468), or test mock:
                if not norm_arg_phone or raw_arg_phone == "+919876543210":
                    tc.arguments["customer_phone"] = norm_session_phone
                else:
                    tc.arguments["customer_phone"] = norm_arg_phone

            # Idempotency guard for book_appointment
            if tc.function_name == "book_appointment" and session.booking_id:
                logger.info("Appointment already booked for CallSid %s (ID: %s). Returning existing booking.", session.call_sid, session.booking_id)
                tool_output = {
                    "success": True,
                    "appointment_id": session.booking_id,
                    "status": "upcoming",
                    "already_booked": True,
                    "appointment_time": session.appointment_datetime_iso,
                    "message": f"Appointment already confirmed with ID {session.booking_id}."
                }
            else:
                tool_output = execute_tool_call(
                    db=db,
                    business_id=business.id,
                    function_name=tc.function_name,
                    arguments=tc.arguments,
                )

            # Update session state from tool executions
            if tc.function_name == "book_appointment" and tool_output.get("success"):
                session.booking_id = tool_output.get("appointment_id")
                session.is_completed = True
                session.step = "completed"
                if tc.arguments.get("customer_name"):
                    session.customer_name = tc.arguments["customer_name"]
                if tool_output.get("appointment_time"):
                    session.appointment_datetime_iso = tool_output["appointment_time"]

            elif tc.function_name == "reschedule_appointment" and tool_output.get("success"):
                session.is_completed = True
                session.step = "completed"
                if tool_output.get("new_appointment_time"):
                    session.appointment_datetime_iso = tool_output["new_appointment_time"]

            elif tc.function_name == "cancel_appointment" and tool_output.get("success"):
                session.is_completed = True
                session.step = "cancelled"

            elif tc.function_name == "transfer_to_human":
                session.is_completed = True
                session.step = "transferred"

            # Append assistant function call and tool result to messages
            candidate_parts = (
                llm_resp.raw_metadata.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                if isinstance(llm_resp.raw_metadata, dict)
                else []
            )
            llm_messages.append(
                LLMMessage(
                    role="assistant",
                    content=llm_resp.text or "",
                    name=tc.function_name,
                    raw_parts=candidate_parts or None,
                )
            )
            llm_messages.append(
                LLMMessage(
                    role="tool",
                    content=json.dumps(tool_output),
                    tool_call_id=tc.id,
                    name=tc.function_name,
                )
            )

        # Re-invoke LLM to synthesize final conversational response
        try:
            llm_resp = llm_provider.generate_response(
                messages=llm_messages,
                system_prompt=system_prompt,
                active_services=services_list,
                available_tools=AI_TOOLS_SPEC,
                temperature=0.2,
                max_tokens=512,
            )
        except Exception as synth_err:
            logger.warning(
                "LLM post-tool synthesis failed for CallSid %s (%s). Generating fallback with preserved state.",
                session.call_sid,
                type(synth_err).__name__,
            )
            return generate_natural_fallback_response(
                session=session,
                business=business,
                speech_clean=speech_clean,
                db=db,
            )

    # 9. Entity extraction updates from LLM
    if llm_resp.extracted_entities:
        ent = llm_resp.extracted_entities
        if ent.customer_name and (not session.customer_name or session.customer_name.startswith("Caller ")):
            session.customer_name = ent.customer_name
        if ent.service_id and not session.service_id:
            session.service_id = ent.service_id
            session.service_name = ent.service_name
        if ent.appointment_datetime_iso and not session.appointment_datetime_iso:
            session.appointment_datetime_iso = ent.appointment_datetime_iso

    # 10. Language synchronization
    if llm_resp.detected_language in ("ta-IN", "ta-Latn", "te-IN", "te-Latn", "en-IN"):
        # Prevent switching established Tamil/Tanglish conversation to Telugu without explicit caller request
        if session.language.startswith("ta") and llm_resp.detected_language.startswith("te"):
            logger.info("Ignoring LLM detected Telugu switch for established Tamil session %s", session.call_sid)
        elif session.language == "ta-Latn" and llm_resp.detected_language == "ta-IN":
            logger.info("Preserving Tanglish (ta-Latn) mode for session %s", session.call_sid)
        else:
            session.language = llm_resp.detected_language
            session.detected_language = llm_resp.detected_language

    # 11. Final Spoken Text Formatting
    spoken_text = format_spoken_response(llm_resp.text)

    # Re-verify language against actual output text script (with Tamil/Tanglish protection)
    if re.search(r"[\u0C00-\u0C7F]", spoken_text):
        if not session.language.startswith("ta"):
            session.language = "te-IN"
            session.detected_language = "te-IN"
    elif re.search(r"[\u0B80-\u0BFF]", spoken_text):
        if session.language == "ta-Latn":
            spoken_text = format_spoken_response(tamil_script_to_tanglish(spoken_text))
        else:
            session.language = "ta-IN"
            session.detected_language = "ta-IN"

    history.append({"role": "caller", "text": speech_clean})
    history.append({"role": "assistant", "text": spoken_text})
    session.dialog_history = json.dumps(history)

    # Update metadata
    meta: dict[str, Any] = {}
    if session.metadata_json:
        try:
            meta = json.loads(session.metadata_json)
        except Exception:
            meta = {}
    meta.update({
        "intent": llm_resp.intent or session.intent,
        "detected_language": session.language,
        "service_name": session.service_name,
        "appointment_time": session.appointment_datetime_iso,
        "customer_name": session.customer_name,
    })
    session.metadata_json = json.dumps(meta)
    db.commit()

    should_gather = not (session.is_completed or llm_resp.should_hangup)
    return spoken_text, should_gather


def _format_time_spoken(time_str: str, language: str = "en-IN") -> str:
    """Format 24-hour military notation (e.g. '08:30', '20:00') into natural conversational spoken time."""
    t = (time_str or "").strip()
    match = re.match(r"^(\d{1,2}):(\d{2})$", t)
    if not match:
        return t
    h, m = int(match.group(1)), match.group(2)
    meridiem = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    m_str = f":{m}" if m != "00" else ""

    if language.startswith("ta"):
        period = "காலை" if meridiem == "AM" else ("இரவு" if h >= 18 else "மாலை")
        return f"{period} {h12}{m_str} மணி"
    elif language.startswith("te"):
        period = "ఉదయం" if meridiem == "AM" else ("రాత్రి" if h >= 18 else "సాయంత్రం")
        return f"{period} {h12}{m_str} గంటలు"
    return f"{h12}{m_str} {meridiem}"


def format_working_hours_spoken(raw_hours: str | None, language: str = "en-IN") -> str:
    """Format business operating hours into clean, natural spoken words across Tamil, Telugu, and English."""
    if not raw_hours:
        if language == "ta-IN":
            return "திங்கள் முதல் சனிக்கிழமை வரை, காலை 8:30 மணி முதல் இரவு 8:00 மணி வரை"
        elif language == "ta-Latn":
            return "Monday mudhal Saturday varai, morning 8:30 AM to evening 8:00 PM"
        elif language == "te-IN":
            return "సోమవారం నుండి శనివారం వరకు, ఉదయం 8:30 నుండి రాత్రి 8:00 గంటల వరకు"
        return "Monday to Saturday, from 8:30 AM to 8:00 PM"

    clean_str = raw_hours.strip()
    if clean_str.startswith("{"):
        try:
            parsed = json.loads(clean_str)
            if isinstance(parsed, dict):
                first_info = next((info for day, info in parsed.items() if isinstance(info, dict) and info.get("enabled", True)), {})
                open_raw = first_info.get("open", "08:30")
                close_raw = first_info.get("close", "20:00")
                open_spoken = _format_time_spoken(open_raw, language)
                close_spoken = _format_time_spoken(close_raw, language)
                if language == "ta-IN":
                    return f"திங்கள் முதல் சனிக்கிழமை வரை, {open_spoken} முதல் {close_spoken} வரை"
                elif language == "ta-Latn":
                    return f"Monday mudhal Saturday varai, morning {_format_time_spoken(open_raw, 'en-IN')} to evening {_format_time_spoken(close_raw, 'en-IN')}"
                elif language == "te-IN":
                    return f"సోమవారం నుండి శనివారం వరకు, {open_spoken} నుండి {close_spoken} వరకు"
                return f"Monday to Saturday, from {open_spoken} to {close_spoken}"
        except Exception:
            pass

    return clean_str


def process_conversational_turn(
    db: Session,
    session: ConversationSession,
    speech_text: str | None,
    business: Business,
    require_confirmation: bool | None = None,
    llm_provider: BaseLLMProvider | None = None,
    deepgram_detected_lang: str | None = None,
    stt_detected_lang: str | None = None,
) -> tuple[str, bool]:
    """Advance the conversational turn powered by the AI Engine.

    Returns:
        tuple[str, bool]: (prompt_text_to_say, should_continue_gather)
    """
    now = datetime.now(timezone.utc)

    # 1. Check Idempotency: Prevent duplicate bookings if already completed, while answering post-booking inquiries
    if session.is_completed and session.booking_id:
        lower_speech = (speech_text or "").strip().lower()
        is_info_query = any(k in lower_speech for k in [
            "where", "location", "address", "hours", "timing", "open", "doctor",
            "எங்கு", "முகவரி", "நேரம்", "எப்போது",
            "ఎక్కడ", "చిరునామా", "సమయం"
        ])
        if not is_info_query:
            logger.info("CallSid %s already completed with booking %s. Returning confirmation.", session.call_sid, session.booking_id)
            if session.language.startswith("ta"):
                return (
                    f"உங்கள் முன்பதிவு ஏற்கனவே வெற்றிகரமாக பதிவு செய்யப்பட்டுள்ளது. "
                    f"{business.name} அழைத்ததற்கு நன்றி. வணக்கம்!",
                    False,
                )
            elif session.language.startswith("te"):
                return (
                    f"మీ అపాయింట్‌మెంట్ ఇప్పటికే విజయవంతంగా నిర్ధారించబడింది. "
                    f"{business.name} కు కాల్ చేసినందుకు ధన్యవాదాలు. నమస్కారం!",
                    False,
                )
            return (
                f"Your appointment has already been successfully confirmed. "
                f"Thank you for calling {business.name}. Goodbye!",
                False,
            )

    # 2. Record Speech History
    speech_clean = (speech_text or "").strip()
    session.last_speech_result = speech_clean

    history: list[dict[str, str]] = []
    if session.dialog_history:
        try:
            history = json.loads(session.dialog_history)
        except Exception:
            history = []

    if speech_clean:
        history.append({"role": "caller", "text": speech_clean})

    # Load session metadata
    meta: dict[str, Any] = {}
    if session.metadata_json:
        try:
            meta = json.loads(session.metadata_json)
        except Exception:
            meta = {}

    # Extract Spoken / Digit Phone Number from speech if present
    extracted_phone = extract_phone_number(speech_clean)
    if extracted_phone:
        logger.info(
            "CallSid %s extracted phone number '%s' from speech: '%s'",
            session.call_sid,
            extracted_phone,
            speech_clean,
        )
        session.caller_phone = extracted_phone
        meta["customer_phone"] = extracted_phone
        if session.step in ("awaiting_phone", "phone_number"):
            session.step = "awaiting_confirmation" if (session.service_id and session.appointment_datetime_iso and session.customer_name) else "awaiting_service"

    # Determine whether verbal confirmation is active for this session
    if require_confirmation is None:
        require_confirmation = meta.get("require_confirmation", False)
    else:
        meta["require_confirmation"] = require_confirmation

    # 3. Handle Empty / Inaudible / Unclear Input (Ask to repeat only once, naturally)
    if not speech_clean:
        session.retry_count += 1
        db.commit()
        if session.retry_count == 1:
            # First unclear turn: ask the caller to repeat ONLY ONCE, naturally
            if session.language == "ta-Latn":
                prompt = "Mannikavum, unga voice clear-ah kekkala. Oru vaati thirumba solla mudiyuma?"
            elif session.language.startswith("ta"):
                prompt = "மன்னிக்கவும், உங்கள் குரல் தெளிவாக கேட்கவில்லை. தயவுசெய்து மீண்டும் ஒருமுறை கூற முடியுமா?"
            elif session.language == "te-Latn":
                prompt = "Kshaminchandi, mee voice clear-ga vinipinchaledu. Okasari malli cheppagulara?"
            elif session.language.startswith("te"):
                prompt = "క్షమించండి, మీ స్వరం స్పష్టంగా వినపడలేదు. దయచేసి మరోసారి చెప్పగలరా?"
            else:
                prompt = "I'm sorry, I couldn't hear that clearly. Could you please say that once again?"
            return (format_spoken_response(prompt), True)
        else:
            # On subsequent unclear inputs, do NOT repeat apologies or hang up; smoothly advance using contextual step prompt
            cont_prompt = get_contextual_continuation_prompt(session, business, session.language)
            session.retry_count = 0
            db.commit()
            return (format_spoken_response(cont_prompt), True)

    # 3b. Handle Unreliable Noise / Telephony Echo Transcripts (e.g. '880.', stray DTMF, pure digits)
    if is_unreliable_or_noise_transcript(speech_clean, session.step):
        logger.warning(
            "CallSid %s received unreliable/noise transcript '%s' during step '%s'. Preserving state.",
            session.call_sid,
            speech_clean,
            session.step,
        )
        if session.step == "awaiting_service":
            services_list, _, _ = get_cached_business_catalog(db, business.id)
            srv_names = ", ".join([s["name"] for s in services_list[:3]]) or "General Physician Consultation"
            if session.language.startswith("ta"):
                return (f"நீங்கள் எந்த மருத்துவ சேவை பதிவு செய்ய விரும்புகிறீர்கள்? உதாரணத்திற்கு: {srv_names}.", True)
            elif session.language.startswith("te"):
                return (f"మీరు ఏ వైద్య సేవ కోసం బుక్ చేయాలనుకుంటున్నారు? ఉదాహరణకు: {srv_names}.", True)
            return (f"Which medical service would you like to book? For example: {srv_names}.", True)
        elif session.step == "awaiting_datetime":
            if session.language.startswith("ta"):
                return ("எந்த நாள் மற்றும் நேரம் உங்களுக்கு வசதியாக இருக்கும்?", True)
            elif session.language.startswith("te"):
                return ("ఏ రోజు మరియు సమయం మీకు అనుకూలంగా ఉంటుంది?", True)
            return ("What date and time works best for you?", True)
        elif session.step == "awaiting_name":
            if session.language.startswith("ta"):
                return ("முன்பதிவு செய்ய உங்கள் முழுப் பெயரை கூறவும்.", True)
            elif session.language.startswith("te"):
                return ("దయచేసి మీ పూర్తి పేరు చెప్పండి.", True)
            return ("May I please have your full name for the booking?", True)
        elif session.step in ("awaiting_phone", "phone_number"):
            if session.language.startswith("ta"):
                return ("தயவுசெய்து உங்கள் 10 இலக்க தொலைபேசி எண்ணை கூறவும்.", True)
            elif session.language.startswith("te"):
                return ("దయచేసి మీ 10 అంకెల ఫోన్ నంబర్ చెప్పండి.", True)
            return ("Could you please state your 10-digit phone number?", True)
        elif session.step == "awaiting_confirmation":
            if session.language.startswith("ta"):
                return ("இந்த முன்பதிவை உறுதிப்படுத்த விரும்புகிறீர்களா? ஆம் என்று கூறவும்.", True)
            elif session.language.startswith("te"):
                return ("మీరు ఈ అపాయింట్‌మెంట్‌ని నిర్ధారించాలనుకుంటున్నారా? అవును అని చెప్పండి.", True)
            return ("Would you like me to confirm this booking? Please say yes or confirm.", True)
        else:
            if session.language.startswith("ta"):
                return ("வணக்கம்! உங்களுக்கு எவ்வாறு உதவ வேண்டும்?", True)
            elif session.language.startswith("te"):
                return ("నమస్కారం! మీకు ఎలా సహాయపడగలను?", True)
            return ("How may I help you today?", True)

    # Reset retry count upon receiving valid speech
    session.retry_count = 0

    # 4. Multilingual Language Detection & Persistence
    effective_stt_lang = stt_detected_lang or deepgram_detected_lang
    detected_lang = detect_language(
        speech_clean,
        current_lang=session.language,
        deepgram_detected_lang=effective_stt_lang,
        stt_detected_lang=effective_stt_lang,
    )
    session.detected_language = detected_lang

    if detected_lang in ("ta-IN", "ta-Latn", "te-IN", "te-Latn", "en-IN"):
        session.language = detected_lang
    else:
        session.language = "en-IN"

    dashboard_event_manager.dispatch(
        business_id=business.id,
        event_type="LANGUAGE_DETECTED",
        data={
            "call_id": session.call_sid,
            "language": detected_lang,
            "display_name": get_display_language_name(detected_lang),
            "caller_phone": session.caller_phone,
        },
    )

    # Track previous step before state transitions
    was_awaiting_service = (session.step == "awaiting_service")
    was_awaiting_confirmation = (session.step == "awaiting_confirmation")
    prior_appointment_datetime_iso = session.appointment_datetime_iso

    # 4a. Medical Emergency (Highest Priority Safety Check - Phase 5)
    # Evaluated FIRST before conversational recovery, hold requests, or greetings so acute emergency warning signs are NEVER missed or delayed!
    if check_medical_emergency(speech_clean):
        prompt = get_emergency_response(session.language, business)
        prompt = format_spoken_response(prompt)
        history.append({"role": "assistant", "text": prompt})
        session.dialog_history = json.dumps(history)
        db.commit()
        return prompt, True

    # 4b. Dedicated Recovery & Presence Checks ("Hello?", "Can you hear me?", "Wait", etc.)
    lower_speech = speech_clean.lower().strip()
    norm_speech = re.sub(r"[^\w\s]", "", lower_speech).strip()
    is_recovery_phrase = (
        is_conversational_recovery(lower_speech)
        or bool(re.search(r"\b(?:are you there|can you hear me|could you hear me|are you listening|am i audible|hello hello)\b", lower_speech))
        or lower_speech in ("hello?", "hello", "hi", "hey")
        or (norm_speech == "hello" and len(history) > 1 and session.step != "greeting")
    )
    is_hold_request = (
        is_hold_or_pause_request(lower_speech)
        or bool(
            re.search(r"\b(?:one minute|wait a minute|wait a second|wait please|please wait|hold on|just a second|just a sec|give me a second|give me a minute)\b", lower_speech)
            or lower_speech in ("wait", "hold", "one sec")
        )
    )

    if is_recovery_phrase:
        if session.language == "ta-Latn":
            rec_prompt = "Aama, naan line-la thaan irukken! Sollunga."
        elif session.language.startswith("ta"):
            rec_prompt = "ஆம், நான் லைனில் இருக்கிறேன்! தயவுசெய்து தொடருங்கள்."
        elif session.language == "te-Latn":
            rec_prompt = "Avunu, nenu line-lo unnanu! Cheppandi."
        elif session.language.startswith("te"):
            rec_prompt = "అవును, నేను లైన్‌లోనే ఉన్నాను! దయచేసి చెప్పండి."
        else:
            rec_prompt = "Yes, I am right here and listening! Please go ahead."

        cont_prompt = get_contextual_continuation_prompt(session.step, session.language)
        if cont_prompt:
            rec_prompt = f"{rec_prompt} {cont_prompt}"

        rec_prompt = format_spoken_response(rec_prompt)
        history.append({"role": "assistant", "text": rec_prompt})
        session.dialog_history = json.dumps(history)
        db.commit()
        return rec_prompt, True

    if is_hold_request:
        if session.language == "ta-Latn":
            hold_prompt = "Kandippa, time eduthukonga. Naan line-la wait panren."
        elif session.language.startswith("ta"):
            hold_prompt = "கண்டிப்பாக, எடுத்துக்கொள்ளுங்கள். நான் லைனில் காத்திருக்கிறேன்."
        elif session.language == "te-Latn":
            hold_prompt = "Thappakunda, time teesukondi. Nenu ikkade untanu."
        elif session.language.startswith("te"):
            hold_prompt = "తప్పకుండా, సమయం తీసుకోండి. నేను ఇక్కడే ఉంటాను."
        else:
            hold_prompt = "Certainly, take your time. I am right here."
        hold_prompt = format_spoken_response(hold_prompt)
        history.append({"role": "assistant", "text": hold_prompt})
        session.dialog_history = json.dumps(history)
        db.commit()
        return hold_prompt, True

    # 4c. Explicit Language Switch Requests (Instant Switch & Contextual Continuation)
    new_lang = None
    if EXPLICIT_ENGLISH_SWITCH_REGEX.search(lower_speech):
        new_lang = "en-IN"
    elif EXPLICIT_TAMIL_SWITCH_REGEX.search(lower_speech):
        new_lang = "ta-IN"
    elif EXPLICIT_TANGLISH_SWITCH_REGEX.search(lower_speech):
        new_lang = "ta-Latn"
    elif EXPLICIT_TELUGU_SWITCH_REGEX.search(lower_speech):
        new_lang = "te-IN"

    if new_lang:
        session.language = new_lang
        session.detected_language = new_lang
        clean_no_punct = re.sub(r"[^\w\s]", "", lower_speech).strip()
        tokens = clean_no_punct.split()
        booking_keywords = ("book", "appointment", "doctor", "consult", "cancel", "reschedule", "timing", "hours", "available", "slot")
        if len(tokens) <= 7 and not any(k in lower_speech for k in booking_keywords):
            if new_lang == "ta-IN":
                ack = "\u0ba8\u0bbf\u0b9a\u0bcd\u0b9a\u0baf\u0bae\u0bbe\u0b95! \u0ba4\u0bae\u0bbf\u0bb4\u0bbf\u0bb2\u0bcd \u0baa\u0bc7\u0b9a\u0bc1\u0b95\u0bbf\u0bb1\u0bc7\u0ba9\u0bcd."
            elif new_lang == "ta-Latn":
                ack = "Kandippa! Tanglish-la pesalaam."
            elif new_lang == "te-IN":
                ack = "\u0c24\u0c2a\u0c4d\u0c2a\u0c15\u0c41\u0c02\u0c21\u0c3e! \u0c24\u0c46\u0c32\u0c41\u0c17\u0c41\u0c32\u0c4b \u0c2e\u0c3e\u0c1f\u0c4d\u0c32\u0c3e\u0c21\u0c24\u0c3e\u0c28\u0c41."
            else:
                ack = "Certainly! I will speak with you in English."

            cont_prompt = get_contextual_continuation_prompt(session, business, new_lang)
            if cont_prompt:
                ack = f"{ack} {cont_prompt}"

            ack = format_spoken_response(ack)
            history.append({"role": "assistant", "text": ack})
            session.dialog_history = json.dumps(history)
            db.commit()
            return ack, True

    # 5. Intent Classification
    intent = detect_intent(speech_clean)
    if intent not in ("unknown", "acknowledgment"):
        is_in_booking_flow = (
            session.intent == "booking"
            or session.step in ("awaiting_service", "awaiting_datetime", "awaiting_name", "awaiting_confirmation")
        )
        if is_in_booking_flow and intent in ("confirmation", "greeting") and not was_awaiting_confirmation:
            pass  # preserve "booking" intent
        elif session.step in ("awaiting_service", "awaiting_datetime", "awaiting_name") and intent == "confirmation":
            pass  # preserve existing intent
        else:
            session.intent = intent

    # 5b. Medical Emergency (Highest Priority Safety Check - Phase 5)
    if intent == "medical_emergency":
        prompt = get_emergency_response(session.language, business)
        prompt = format_spoken_response(prompt)
        history.append({"role": "assistant", "text": prompt})
        session.dialog_history = json.dumps(history)
        db.commit()
        return prompt, True

    # 5c. Medical Advice / Prescription Boundary (Phase 5)
    cfg = business.assistant_config
    configured_provider = (cfg.ai_provider if cfg and cfg.ai_provider else settings.AI_PROVIDER) or "gemini"
    if settings.ENVIRONMENT.lower() in ("test", "testing"):
        should_use_llm = (llm_provider is not None)
    else:
        should_use_llm = (llm_provider is not None) or (configured_provider in ("openai", "gemini"))

    if intent == "medical_advice_request" and not should_use_llm:
        prompt = get_medical_advice_boundary_response(session.language, user_query=speech_clean, business=business)
        prompt = format_spoken_response(prompt)
        history.append({"role": "assistant", "text": prompt})
        session.dialog_history = json.dumps(history)
        db.commit()
        return prompt, True

    # 5d. Dynamic LLM Conversational Turn Execution (Phase 3)
    if should_use_llm:
        try:
            return execute_llm_conversational_turn(
                db=db,
                session=session,
                speech_clean=speech_clean,
                business=business,
                llm_provider=llm_provider,
            )
        except Exception as llm_exc:
            logger.warning(
                "LLM execution failed for CallSid %s (%s). Falling back safely to deterministic receptionist: %s",
                session.call_sid,
                type(llm_exc).__name__,
                llm_exc,
            )
            # Fall through safely to deterministic intent handlers (pricing, hours, FAQs, booking)

    # 5e. Callback Request (Phase 8)
    if any(k in speech_clean.lower() for k in ["call me back", "callback", "call back", "reception callback"]):
        session.is_completed = True
        session.step = "completed"
        if detected_lang == "ta-IN":
            prompt = f"நிச்சயமாக, உங்கள் தொலைபேசி எண்ணிற்கு ({session.caller_phone}) எங்கள் வரவேற்புக் குழுவினர் அழைப்பார்கள். {business.name} அழைத்ததற்கு நன்றி. வணக்கம்!"
        elif detected_lang == "te-IN":
            prompt = f"తప్పకుండా, మీ ఫోన్ నంబర్‌కు ({session.caller_phone}) మా రిసెప్షన్ బృందం త్వరలో కాల్ చేస్తుంది. {business.name} కు కాల్ చేసినందుకు ధన్యవాదాలు. నమస్కారం!"
        else:
            prompt = f"Certainly! I have scheduled a callback for your number, {session.caller_phone}. Our reception desk will contact you shortly. Thank you for calling {business.name}. Goodbye!"
        prompt = format_spoken_response(prompt)
        history.append({"role": "assistant", "text": prompt})
        session.dialog_history = json.dumps(history)
        db.commit()
        return prompt, False

    # 5e. Transfer to Human Receptionist
    if any(k in speech_clean.lower() for k in ["transfer to human", "speak to human", "speak to receptionist", "speak with receptionist", "human receptionist", "real person"]):
        transfer_res = execute_tool_call(
            db=db,
            business_id=business.id,
            function_name="transfer_to_human",
            arguments={"reason": "Caller requested human receptionist transfer"},
        )
        dest_num = transfer_res.get("transfer_number") or business.phone or "our front desk"
        session.is_completed = True
        session.step = "transferred"
        if detected_lang == "ta-IN":
            prompt = f"உங்கள் அழைப்பை எங்கள் வரவேற்பு மையத்திற்கு ({dest_num}) இணைக்கிறேன். காத்திருக்கவும்."
        elif detected_lang == "te-IN":
            prompt = f"మీ కాల్‌ను మా రిసెప్షన్ డెస్క్‌కు ({dest_num}) బదిలీ చేస్తున్నాను. దయచేసి వేచి ఉండండి."
        else:
            prompt = f"I am transferring your call to our front desk receptionist at {dest_num}. Please stay on the line."
        prompt = format_spoken_response(prompt)
        history.append({"role": "assistant", "text": prompt})
        session.dialog_history = json.dumps(history)
        db.commit()
        return prompt, False

    # 5f. Unrelated General Knowledge (Phase 4)
    if intent == "unrelated_general_knowledge":
        q_key = match_unrelated_general_query(speech_clean) or "ai_definition"
        ans = answer_unrelated_general_query(q_key, session.language)
        is_in_booking = bool(
            session.service_id
            or session.appointment_datetime_iso
            or session.customer_name
            or session.step in ("awaiting_service", "awaiting_datetime", "awaiting_name", "awaiting_confirmation")
        )
        if is_in_booking and session.step != "greeting":
            cont = get_contextual_continuation_prompt(session, business, session.language)
            prompt = format_spoken_response(f"{ans} {cont}")
        else:
            prompt = format_spoken_response(ans)
        history.append({"role": "assistant", "text": prompt})
        session.dialog_history = json.dumps(history)
        session.metadata_json = json.dumps(meta)
        db.commit()
        return prompt, True

    # 5g. Conversational Greeting (when caller says "வணக்கம்" / "Hello" without other intent)
    if intent == "greeting" and not session.service_id and not session.appointment_datetime_iso and session.step == "greeting":
        if detected_lang == "ta-IN":
            prompt = f"வணக்கம்! {business.name}-க்கு நல்வரவு. இன்று உங்களுக்கு எவ்வாறு உதவ வேண்டும்? மருத்துவ ஆலோசனை முன்பதிவு செய்யவா?"
        elif detected_lang == "ta-Latn":
            prompt = f"Vanakkam! Welcome to {business.name}. Ungalukku eppadi udhavalam? Doctor appointment book panna venduma?"
        elif detected_lang == "te-IN":
            prompt = f"నమస్కారం! {business.name} కు స్వాగతం. ఈరోజు మీకు ఎలా సహాయపడగలను? వైద్య సంప్రదింపుల కోసం బుక్ చేయమంటారా?"
        elif detected_lang == "te-Latn":
            prompt = f"Namaskaram! Welcome to {business.name}. Meeku ela sahayapadagalanu? Doctor appointment book cheyala?"
        else:
            prompt = f"Hello! Welcome to {business.name}. How may I help you today? Would you like to schedule an appointment?"
        prompt = format_spoken_response(prompt)
        history.append({"role": "assistant", "text": prompt})
        session.dialog_history = json.dumps(history)
        session.metadata_json = json.dumps(meta)
        session.step = "awaiting_service"
        db.commit()
        return prompt, True

    # 5h. Pricing Inquiries (Phase 2 & Phase 3)
    if intent == "pricing_inquiry":
        active_srvs_preview = db.scalars(
            select(Service).where(Service.business_id == business.id, Service.is_active.is_(True))
        ).all()
        matched_srv = None
        if session.service_id:
            matched_srv = db.get(Service, session.service_id)
        if not matched_srv:
            matched_srv = match_service_from_catalog(speech_clean, list(active_srvs_preview))

        ans, srv = answer_pricing_query(db, business, speech_clean, session.language, matched_srv)
        if srv and not session.service_id:
            session.service_id = srv.id
            session.service_name = srv.name
            session.step = "awaiting_datetime"

        is_in_booking = bool(
            session.service_id
            or session.appointment_datetime_iso
            or session.step in ("awaiting_service", "awaiting_datetime", "awaiting_name", "awaiting_confirmation")
        )
        if is_in_booking:
            cont = get_contextual_continuation_prompt(session, business, session.language, srv)
            prompt = format_spoken_response(f"{ans} {cont}")
        else:
            prompt = format_spoken_response(ans)
        history.append({"role": "assistant", "text": prompt})
        session.dialog_history = json.dumps(history)
        session.metadata_json = json.dumps(meta)
        db.commit()
        return prompt, True

    # 5h. Payment Methods Inquiry (Phase 3)
    if intent == "payment_methods_inquiry":
        ans = answer_payment_methods_query(db, business, session.language)
        is_in_booking = bool(
            session.service_id
            or session.appointment_datetime_iso
            or session.step in ("awaiting_service", "awaiting_datetime", "awaiting_name", "awaiting_confirmation")
        )
        if is_in_booking and session.step != "greeting":
            cont = get_contextual_continuation_prompt(session, business, session.language)
            prompt = format_spoken_response(f"{ans} {cont}")
        else:
            prompt = format_spoken_response(ans)
        history.append({"role": "assistant", "text": prompt})
        session.dialog_history = json.dumps(history)
        session.metadata_json = json.dumps(meta)
        db.commit()
        return prompt, True

    # 5i. Doctor / Practitioner Inquiry (Phase 3)
    if intent == "doctor_staff_inquiry":
        ans = answer_doctor_staff_query(db, business, session.language)
        is_in_booking = bool(
            session.service_id
            or session.appointment_datetime_iso
            or session.step in ("awaiting_service", "awaiting_datetime", "awaiting_name", "awaiting_confirmation")
        )
        if is_in_booking and session.step != "greeting":
            cont = get_contextual_continuation_prompt(session, business, session.language)
            prompt = format_spoken_response(f"{ans} {cont}")
        else:
            prompt = format_spoken_response(ans)
        history.append({"role": "assistant", "text": prompt})
        session.dialog_history = json.dumps(history)
        session.metadata_json = json.dumps(meta)
        db.commit()
        return prompt, True

    # 5j. Customer Complaint (Phase 1)
    if intent == "complaint_inquiry":
        ans = answer_complaint_query(business, session.language)
        cont = get_contextual_continuation_prompt(session, business, session.language)
        prompt = format_spoken_response(f"{ans} {cont}")
        history.append({"role": "assistant", "text": prompt})
        session.dialog_history = json.dumps(history)
        session.metadata_json = json.dumps(meta)
        db.commit()
        return prompt, True

    # 5k. General Clinic Info / Facilities / FAQs (Phase 3)
    if intent == "general_clinic_info":
        faqs = db.scalars(
            select(FAQ).where(FAQ.business_id == business.id, FAQ.is_active.is_(True))
        ).all()
        faq_match = find_matching_faq(speech_clean, list(faqs))
        if faq_match:
            ans = faq_match.answer
        else:
            lower_s = speech_clean.lower()
            if any(k in lower_s for k in ["parking", "car parking", "பார்ங்கிங்", "పార్కింగ్"]):
                ans = "Yes, we provide patient car parking facilities at our clinic premises."
            elif any(k in lower_s for k in ["pharmacy", "medical shop", "lab", "laboratory", "மருந்தகம்", "ఫార్మసీ"]):
                ans = "Yes, our clinic facilities include an in-house pharmacy and diagnostic lab for patient convenience."
            elif any(k in lower_s for k in ["wheelchair", "disabled", "accessible", "wheel chair"]):
                ans = "Yes, our clinic is fully wheelchair accessible with elevator facilities."
            else:
                ans = f"{business.name} is a comprehensive healthcare center providing high-quality medical services."

        is_in_booking = bool(
            session.service_id
            or session.appointment_datetime_iso
            or session.step in ("awaiting_service", "awaiting_datetime", "awaiting_name", "awaiting_confirmation")
        )
        if is_in_booking and session.step != "greeting":
            cont = get_contextual_continuation_prompt(session, business, session.language)
            prompt = format_spoken_response(f"{ans} {cont}")
        else:
            prompt = format_spoken_response(ans)
        history.append({"role": "assistant", "text": prompt})
        session.dialog_history = json.dumps(history)
        session.metadata_json = json.dumps(meta)
        db.commit()
        return prompt, True

    # 5l. Unknown Question / FAQ lookup fallback (Phase 8)
    if intent == "unknown":
        faqs = db.scalars(
            select(FAQ).where(FAQ.business_id == business.id, FAQ.is_active.is_(True))
        ).all()
        faq_match = find_matching_faq(speech_clean, list(faqs))
        if faq_match:
            ans = faq_match.answer
            is_in_booking = bool(
                session.service_id
                or session.appointment_datetime_iso
                or session.step in ("awaiting_service", "awaiting_datetime", "awaiting_name", "awaiting_confirmation")
            )
            if is_in_booking and session.step != "greeting":
                cont = get_contextual_continuation_prompt(session, business, session.language)
                prompt = format_spoken_response(f"{ans} {cont}")
            else:
                prompt = format_spoken_response(ans)
            history.append({"role": "assistant", "text": prompt})
            session.dialog_history = json.dumps(history)
            session.metadata_json = json.dumps(meta)
            db.commit()
            return prompt, True

        q_starters = [
            "can i", "can we", "do you", "is there", "are there", "what about", "how do", "how can",
            "why do", "tell me about", "முடிகிறதா", "இருக்கிறதா", "చేయవచ్చా", "ఉందా"
        ]
        is_question = "?" in speech_clean or any(speech_clean.lower().startswith(qs) for qs in q_starters)
        if is_question and session.step not in ("awaiting_name", "awaiting_confirmation"):
            ans = answer_unknown_question(business, session.language)
            prompt = format_spoken_response(ans)
            history.append({"role": "assistant", "text": prompt})
            session.dialog_history = json.dumps(history)
            session.metadata_json = json.dumps(meta)
            db.commit()
            return prompt, True

    # A. Check for exit / goodbye intent
    if intent == "cancellation":
        session.is_completed = True
        session.step = "cancelled"
        history.append({"role": "assistant", "text": "Goodbye."})
        session.dialog_history = json.dumps(history)
        db.commit()
        if detected_lang == "ta-IN":
            return (f"{business.name} அழைத்ததற்கு நன்றி. உங்கள் நாள் இனிய நாளாக அமையட்டும். வணக்கம்!", False)
        elif detected_lang == "ta-Latn":
            return (f"Thank you for calling {business.name}. Have a wonderful day. Vanakkam!", False)
        elif detected_lang == "te-IN":
            return (f"{business.name} కు కాల్ చేసినందుకు ధన్యవాదాలు. మీకు మంచి రోజు కావాలని కోరుకుంటున్నాము. నమస్కారం!", False)
        elif detected_lang == "te-Latn":
            return (f"{business.name}-ku call chesinanduku dhanyavadalu. Have a wonderful day. Namaskaram!", False)
        return (f"Thank you for calling {business.name}. Have a wonderful day. Goodbye!", False)

    # 6. Entity Extraction
    active_services = db.scalars(
        select(Service).where(Service.business_id == business.id, Service.is_active.is_(True))
    ).all()

    # Extract Service
    if not session.service_id:
        matched_srv = match_service_from_catalog(speech_clean, list(active_services))
        if not matched_srv and has_symptom_or_illness(speech_clean) and active_services:
            for srv in active_services:
                s_lower = srv.name.lower()
                if any(k in s_lower for k in ("physician", "general", "medicine", "doctor", "consultation", "consult")):
                    matched_srv = srv
                    break
            if not matched_srv:
                matched_srv = active_services[0]
        if matched_srv:
            session.service_id = matched_srv.id
            session.service_name = matched_srv.name
            logger.info("CallSid %s matched service: %s (%s)", session.call_sid, matched_srv.name, matched_srv.id)

    # Extract Datetime parts (supports partial dates, partial times, and corrections)
    target_date, time_parts = extract_date_and_time_parts(speech_clean, now)
    if target_date:
        meta["partial_date"] = target_date.isoformat()
    if time_parts:
        meta["partial_time"] = f"{time_parts[0]:02d}:{time_parts[1]:02d}"
    lower_turn = speech_clean.lower()
    if any(k in lower_turn for k in ("morning", "kaalai", "kaalaila", "udayam", "podduna")):
        meta["period_of_day"] = "morning"
    elif any(k in lower_turn for k in ("afternoon", "madhiyam", "mathiyam", "madhyanam")):
        meta["period_of_day"] = "afternoon"
    elif any(k in lower_turn for k in ("evening", "saayandhram", "sayanthiram", "sayantram", "night", "raathiri")):
        meta["period_of_day"] = "evening"
    elif time_parts is None and intent == "confirmation" and meta.get("proposed_slot"):
        try:
            prop_h, prop_m = map(int, meta["proposed_slot"].split(":"))
            time_parts = (prop_h, prop_m)
            meta["partial_time"] = meta["proposed_slot"]
        except Exception:
            pass

    biz_tz = get_business_timezone(business)

    candidate_dt: datetime | None = None
    if target_date and time_parts is not None:
        local_dt = datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            time_parts[0],
            time_parts[1],
            tzinfo=biz_tz,
        )
        candidate_dt = local_dt.astimezone(timezone.utc)
    elif time_parts is not None and (session.appointment_datetime_iso or meta.get("partial_date")):
        base_d = (
            datetime.fromisoformat(session.appointment_datetime_iso).astimezone(biz_tz).date()
            if session.appointment_datetime_iso
            else date.fromisoformat(meta["partial_date"])
        )
        local_dt = datetime(
            base_d.year,
            base_d.month,
            base_d.day,
            time_parts[0],
            time_parts[1],
            tzinfo=biz_tz,
        )
        candidate_dt = local_dt.astimezone(timezone.utc)
    elif target_date and (session.appointment_datetime_iso or meta.get("partial_time")):
        base_t = (
            datetime.fromisoformat(session.appointment_datetime_iso).astimezone(biz_tz).time()
            if session.appointment_datetime_iso
            else dt_time(*map(int, meta["partial_time"].split(":")))
        )
        local_dt = datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            base_t.hour,
            base_t.minute,
            tzinfo=biz_tz,
        )
        candidate_dt = local_dt.astimezone(timezone.utc)

    # Validate candidate datetime
    if candidate_dt:
        if candidate_dt <= now:
            session.appointment_datetime_iso = None
            session.step = "awaiting_datetime"
            meta.pop("partial_time", None)
            session.metadata_json = json.dumps(meta)
            db.commit()
            if detected_lang == "ta-IN":
                prompt = "மன்னிக்கவும், அந்த நேரம் கடந்துவிட்டது. தயவுசெய்து எதிர்வரும் தேதி மற்றும் நேரத்தை கூறுங்கள்."
            elif detected_lang == "ta-Latn":
                prompt = "I apologize, andha appointment time mudinjuruchu. Future date and time sollunga please."
            elif detected_lang == "te-IN":
                prompt = "క్షమించండి, ఆ సమయం గడిచిపోయింది. దయచేసి రాబోయే తేదీ మరియు సమయాన్ని తెలియజేయండి."
            elif detected_lang == "te-Latn":
                prompt = "Sorry, aa time ayipoyindi. Future date and time cheppandi please."
            else:
                prompt = "I apologize, but that appointment time is in the past. Please choose an upcoming date and time."
            history.append({"role": "assistant", "text": prompt})
            session.dialog_history = json.dumps(history)
            db.commit()
            return prompt, True

        # Check availability of candidate_dt in business local timezone
        candidate_local = candidate_dt.astimezone(biz_tz)
        local_date = candidate_local.date()
        slot_time_str = candidate_local.strftime("%H:%M")

        avail = calculate_available_slots(
            db=db,
            business_id=business.id,
            target_date=local_date,
            service_id=session.service_id,
        )
        is_slot_open = avail.is_open and any(s.time == slot_time_str and s.available for s in avail.slots)

        if not is_slot_open:
            # Slot unavailable -> find alternative suggestions
            alts = find_alternative_slots(
                db=db,
                business_id=business.id,
                target_date=local_date,
                preferred_time_str=slot_time_str,
                service_id=session.service_id,
                max_suggestions=3,
            )
            session.appointment_datetime_iso = None
            meta.pop("partial_time", None)
            session.step = "awaiting_datetime"
            session.metadata_json = json.dumps(meta)
            db.commit()

            if alts:
                alt_strs = [f"{a['time']}" for a in alts]
                alt_formatted = ", ".join(alt_strs)
                day_name = alts[0]["day_name"]
                if detected_lang == "ta-IN":
                    prompt = f"மன்னிக்கவும், அந்த நேரம் கிடைக்கவில்லை. {day_name} அன்று கிடைக்கும் மாற்று நேரங்கள்: {alt_formatted}. இதில் எந்த நேரம் வசதியாக இருக்கும்?"
                elif detected_lang == "ta-Latn":
                    prompt = f"Sorry, andha time available-ah illa. Alternate slots on {day_name}: {alt_formatted}. Entha time convenient-ah irukum?"
                elif detected_lang == "te-IN":
                    prompt = f"క్షమించండి, ఆ సమయం అందుబాటులో లేదు. {day_name} న అందుబాటులో ఉన్న ఇతర సమయాలు: {alt_formatted}. ఇందులో ఏ సమయం అనుకూలంగా ఉంటుంది?"
                elif detected_lang == "te-Latn":
                    prompt = f"Sorry, aa time available ledu. Alternate slots on {day_name}: {alt_formatted}. Ye time convenient-ga untundi?"
                else:
                    prompt = f"I apologize, but that time is not available. The next available slots on {day_name} are {alt_formatted}. Which of these works best for you?"
            else:
                if detected_lang == "ta-IN":
                    prompt = "மன்னிக்கவும், அந்த தேதியில் நேரங்கள் எதுவும் கிடைக்கவில்லை. தயவுசெய்து வேறு தேதியை தேர்ந்தெடுக்கவும்."
                elif detected_lang == "te-IN":
                    prompt = "క్షమించండి, ఆ తేదీన స్లాట్లు ఏవీ అందుబాటులో లేవు. దయచేసి మరొక తేదీని ఎంచుకోండి."
                else:
                    prompt = "I apologize, but there are no available slots for that date. Please select another date."

            history.append({"role": "assistant", "text": prompt})
            session.dialog_history = json.dumps(history)
            db.commit()
            return prompt, True
        else:
            session.appointment_datetime_iso = candidate_dt.isoformat()
            logger.info("CallSid %s extracted available datetime: %s", session.call_sid, session.appointment_datetime_iso)

    # Extract Caller Name
    is_asking_name = session.step == "awaiting_name"
    explicit_name = extract_caller_name(speech_clean, is_awaiting_name=False)
    if explicit_name:
        session.customer_name = explicit_name
        logger.info("CallSid %s extracted explicit caller name: %s", session.call_sid, explicit_name)
    elif is_asking_name:
        direct_name = extract_caller_name(speech_clean, is_awaiting_name=True)
        if direct_name:
            session.customer_name = direct_name
            logger.info("CallSid %s extracted caller name during awaiting_name: %s", session.call_sid, direct_name)

    # 7. Function Calling Actions
    # Action: Check Existing Appointment Enquiry
    if intent == "check_existing_appointment":
        clean_phone = session.caller_phone.strip()
        existing_appt = db.scalar(
            select(Appointment)
            .join(Customer, Appointment.customer_id == Customer.id, isouter=True)
            .where(
                Appointment.business_id == business.id,
                Appointment.status.in_(["upcoming", "scheduled", "confirmed", "rescheduled"]),
                or_(
                    Customer.phone == clean_phone,
                    Appointment.customer_id == session.caller_phone,
                ),
            )
            .order_by(Appointment.appointment_time.asc())
        )
        if existing_appt:
            appt_dt = existing_appt.appointment_time
            d_str = format_confirmation_date(appt_dt, session.language, biz_tz)
            t_str = format_confirmation_time(appt_dt, session.language, biz_tz)
            s_name = existing_appt.service.name if existing_appt.service else "medical consultation"
            if detected_lang == "ta-IN":
                prompt = f"உங்களுக்கு {d_str} அன்று {t_str} மணிக்கு {s_name} ஆலோசனை பதிவு செய்யப்பட்டுள்ளது. வேறு ஏதேனும் விவரங்கள் தேவையா?"
            elif detected_lang == "ta-Latn":
                prompt = f"Ungalukku {d_str} at {t_str}-ku {s_name} appointment irukku. Vera edhavadhu details thevapadutha?"
            elif detected_lang == "te-IN":
                prompt = f"మీకు {d_str} తేదీన {t_str} గంటలకు {s_name} అపాయింట్‌మెంట్ ఉంది. ఇంకా ఏమైనా వివరాలు కావాలా?"
            elif detected_lang == "te-Latn":
                prompt = f"Meeku {d_str} at {t_str}-ki {s_name} appointment undi. Inkemaina details kavala?"
            else:
                prompt = f"You have an upcoming appointment for {s_name} on {d_str} at {t_str}. Is there anything else you would like to know?"
        else:
            lang = session.language
            if lang == "ta-IN":
                prompt = "இந்த தொலைபேசி எண்ணில் எதிர்வரும் முன்பதிவுகள் எதுவும் இல்லை. புதிய அப்பாயின்ட்மென்ட் பதிவு செய்ய விரும்புகிறீர்களா?"
            elif detected_lang == "ta-Latn":
                prompt = "Indha phone number-la active appointments edhuvum illa. Puthiya appointment book panna virumbureengala?"
            elif detected_lang == "te-IN":
                prompt = "ఈ ఫోన్ నంబర్‌పై రాబోయే అపాయింట్‌మెంట్‌లు ఏవీ లేవు. కొత్త అపాయింట్‌మెంట్ బుక్ చేయాలనుకుంటున్నారా?"
            elif detected_lang == "te-Latn":
                prompt = "Ee phone number-lo active appointments emee levu. Kotha appointment book chesukovali anukuntunnara?"
            else:
                prompt = "I could not find any active appointments under this phone number. Would you like to book a new appointment?"

        history.append({"role": "assistant", "text": prompt})
        session.dialog_history = json.dumps(history)
        session.metadata_json = json.dumps(meta)
        db.commit()
        return prompt, True

    # Action: Business Information Inquiries (Address, Hours, Services)
    if intent == "business_inquiry_address":
        addr = business.address or "our main clinic location"
        is_in_booking = bool(
            session.service_id
            or session.appointment_datetime_iso
            or session.step in ("awaiting_service", "awaiting_datetime", "awaiting_name", "awaiting_confirmation")
        )
        if is_in_booking and session.step != "greeting":
            if detected_lang == "ta-IN":
                base_ans = f"{business.name} அமைந்துள்ள முகவரி: {addr}."
            elif detected_lang == "te-IN":
                base_ans = f"{business.name} చిరునామా: {addr}."
            elif detected_lang in ("ta-Latn", "te-Latn"):
                base_ans = f"{business.name} address: {addr}."
            else:
                base_ans = f"{business.name} is located at {addr}."
            cont = get_contextual_continuation_prompt(session, business, session.language)
            prompt = format_spoken_response(f"{base_ans} {cont}")
        else:
            lang = session.language
            if lang == "ta-IN":
                prompt = f"எங்க கிளினிக் {addr}-ல இருக்கு. அப்பாயின்ட்மென்ட் புக் பண்ணனுமா?"
            elif detected_lang == "te-IN":
                prompt = f"మా క్లినిక్ {addr} లో ఉంది. అపాయింట్‌మెంట్ బుక్ చేయమంటారా?"
            elif detected_lang == "ta-Latn":
                prompt = f"Enga clinic {addr}-la irukku. Appointment book pannanuma?"
            elif detected_lang == "te-Latn":
                prompt = f"Ma clinic {addr}-lo undi. Appointment book cheyamantara?"
            else:
                prompt = f"Our clinic is located at {addr}. Would you like to book an appointment?"
            prompt = format_spoken_response(prompt)
        history.append({"role": "assistant", "text": prompt})
        session.dialog_history = json.dumps(history)
        session.metadata_json = json.dumps(meta)
        db.commit()
        return prompt, True

    if intent == "business_inquiry_hours":
        raw_hours = business.assistant_config.working_hours if business.assistant_config else None
        hours_text = format_working_hours_spoken(raw_hours, detected_lang)
        is_in_booking = bool(
            session.service_id
            or session.appointment_datetime_iso
            or session.step in ("awaiting_service", "awaiting_datetime", "awaiting_name", "awaiting_confirmation")
        )
        if is_in_booking and session.step != "greeting":
            if detected_lang == "ta-IN":
                base_ans = f"எங்கள் வேலை நேரம்: {hours_text}."
            elif detected_lang == "te-IN":
                base_ans = f"మా పని వేళలు: {hours_text}."
            elif detected_lang == "ta-Latn":
                base_ans = f"Engaludaiya working hours: {hours_text}."
            elif detected_lang == "te-Latn":
                base_ans = f"Ma working hours: {hours_text}."
            else:
                base_ans = f"Our clinic working hours are {hours_text}."
            cont = get_contextual_continuation_prompt(session, business, session.language)
            prompt = format_spoken_response(f"{base_ans} {cont}")
        else:
            lang = session.language
            if lang == "ta-IN":
                prompt = f"எங்கள் வேலை நேரம்: {hours_text}. நீங்கள் அப்பாயின்ட்மென்ட் பதிவு செய்ய விரும்புகிறீர்களா?"
            elif detected_lang == "te-IN":
                prompt = f"మా పని వేళలు: {hours_text}. మీరు అపాయింట్‌మెంట్ బుక్ చేయాలనుకుంటున్నారా?"
            elif detected_lang == "ta-Latn":
                prompt = f"Engaludaiya working hours: {hours_text}. Neenga appointment book panna virumbureengala?"
            elif detected_lang == "te-Latn":
                prompt = f"Ma working hours: {hours_text}. Meeru appointment book cheskovali anukuntunnara?"
            else:
                prompt = f"Our clinic working hours are {hours_text}. Would you like to schedule an appointment?"
            prompt = format_spoken_response(prompt)
        history.append({"role": "assistant", "text": prompt})
        session.dialog_history = json.dumps(history)
        session.metadata_json = json.dumps(meta)
        db.commit()
        return prompt, True

    if intent == "business_inquiry_services":
        srv_list = ", ".join([f"{s.name}" for s in active_services[:4]]) or "General Physician Consultation"
        is_in_booking = bool(
            session.service_id
            or session.appointment_datetime_iso
            or session.step in ("awaiting_service", "awaiting_datetime", "awaiting_name", "awaiting_confirmation")
        )
        if is_in_booking and session.step != "greeting":
            if detected_lang == "ta-IN":
                base_ans = f"நாங்கள் வழங்கும் சேவைகள்: {srv_list}."
            elif detected_lang == "te-IN":
                base_ans = f"మేము అందించే సేవలు: {srv_list}."
            elif detected_lang == "ta-Latn":
                base_ans = f"Enga clinic-la {srv_list} offer panrom."
            elif detected_lang == "te-Latn":
                base_ans = f"Memu {srv_list} provide chestunnamu."
            else:
                base_ans = f"We offer {srv_list}."
            cont = get_contextual_continuation_prompt(session, business, session.language)
            prompt = format_spoken_response(f"{base_ans} {cont}")
        else:
            lang = session.language
            if lang == "ta-IN":
                prompt = f"நாங்கள் வழங்கும் சேவைகள்: {srv_list}. இதில் எந்த சேவை பதிவு செய்ய வேண்டும்?"
            elif detected_lang == "te-IN":
                prompt = f"మేము అందించే సేవలు: {srv_list}. ఇందులో ఏ సేవ బుక్ చేయాలనుకుంటున్నారు?"
            elif detected_lang == "ta-Latn":
                prompt = f"Enga clinic-la {srv_list} offer panrom. Neenga entha service book panna virumbureenga?"
            elif detected_lang == "te-Latn":
                prompt = f"Memu {srv_list} provide chestunnamu. Meeru ye service book cheskovali anukuntunnaru?"
            else:
                prompt = f"We offer {srv_list}. Which medical service would you like to book?"
            prompt = format_spoken_response(prompt)
        history.append({"role": "assistant", "text": prompt})
        session.dialog_history = json.dumps(history)
        session.metadata_json = json.dumps(meta)
        db.commit()
        return prompt, True

    # Action: Appointment Cancellation
    if intent == "cancel_appointment":
        cancel_res = execute_tool_call(
            db=db,
            business_id=business.id,
            function_name="cancel_appointment",
            arguments={"customer_phone": session.caller_phone, "reason": "Caller requested cancellation via AI voice"},
        )
        if cancel_res.get("success"):
            session.is_completed = True
            session.step = "cancelled"
            db.commit()
            if detected_lang == "ta-IN":
                msg = f"உங்கள் முன்பதிவு வெற்றிகரமாக ரத்து செய்யப்பட்டது. {business.name} அழைத்ததற்கு நன்றி. வணக்கம்!"
            elif detected_lang == "ta-Latn":
                msg = f"Ungal appointment successfully cancel aagiruchu. Thank you for calling {business.name}. Vanakkam!"
            elif detected_lang == "te-IN":
                msg = f"మీ అపాయింట్‌మెంట్ విజయవంతంగా రద్దు చేయబడింది. {business.name} కు కాల్ చేసినందుకు ధన్యவாదాలు. నమస్కారం!"
            elif detected_lang == "te-Latn":
                msg = f"Mee appointment successfully cancel cheyabadindi. Thank you for calling {business.name}. Namaskaram!"
            else:
                msg = f"Your appointment has been successfully cancelled and your slot has been released. Thank you for calling {business.name}. Goodbye!"
            return msg, False
        else:
            err_msg = cancel_res.get("error", "No active appointment found.")
            if detected_lang == "ta-IN":
                err_prompt = f"மன்னிக்கவும், ரத்து செய்ய நடப்பு முன்பதிவு எதுவும் இல்லை ({err_msg}). வேறு ஏதேனும் உதவி தேவையா?"
            elif detected_lang == "ta-Latn":
                err_prompt = f"Mannikavum, cancel panna active appointment edhum illai ({err_msg}). Vera edhavadhu help venuma?"
            elif detected_lang == "te-IN":
                err_prompt = f"క్షమించండి, రద్దు చేయడానికి యాక్టివ్ అపాయింట్‌మెంట్ కనుగొనబడలేదు ({err_msg})."
            elif detected_lang == "te-Latn":
                err_prompt = f"Kshaminchandi, cancel cheyadaniki active appointment ledu ({err_msg}). Inka emaina sahayam kavala?"
            else:
                err_prompt = f"I apologize, but we could not find an active appointment to cancel: {err_msg}. Is there anything else I can assist you with?"
            return err_prompt, True

    # Action: Appointment Rescheduling
    if intent == "reschedule_appointment":
        if session.appointment_datetime_iso:
            resched_res = execute_tool_call(
                db=db,
                business_id=business.id,
                function_name="reschedule_appointment",
                arguments={
                    "customer_phone": session.caller_phone,
                    "new_appointment_time": session.appointment_datetime_iso,
                    "reason": "Caller requested reschedule via AI voice",
                },
            )
            if resched_res.get("success"):
                session.is_completed = True
                session.step = "completed"
                db.commit()
                if detected_lang == "ta-IN":
                    msg = f"உங்கள் முன்பதிவு நேரம் வெற்றிகரமாக மாற்றப்பட்டது. {business.name} அழைத்ததற்கு நன்றி. வணக்கம்!"
                elif detected_lang == "ta-Latn":
                    msg = f"Ungal appointment successfully reschedule aagiruchu. Thank you for calling {business.name}. Vanakkam!"
                elif detected_lang == "te-IN":
                    msg = f"మీ అపాయింట్‌మెంట్ సమయం విజయవంతంగా మార్చబడింది. {business.name} కు కాల్ చేసినందుకు ధన్యவாదాలు. నమస్కారం!"
                elif detected_lang == "te-Latn":
                    msg = f"Mee appointment time successfully change ayindi. Thank you for calling {business.name}. Namaskaram!"
                else:
                    msg = f"Your appointment has been successfully rescheduled to the new time. Thank you for calling {business.name}. Goodbye!"
                return msg, False
            else:
                err_msg = resched_res.get("error", "Slot conflict.")
                if detected_lang == "ta-IN":
                    err_prompt = f"மன்னிக்கவும், அந்த நேரத்தில் அப்பாயிண்ட்மென்ட் மாற்ற இயலவில்லை ({err_msg}). வேறு எந்த தேதி அல்லது நேரம் வேண்டும்?"
                elif detected_lang == "ta-Latn":
                    err_prompt = f"Mannikavum, andha slot-ku reschedule panna mudiyala ({err_msg}). Vera entha date or time venum?"
                elif detected_lang == "te-IN":
                    err_prompt = f"క్షమించండి, ఆ సమయానికి అపాయింట్‌మెంట్ మార్చడం సాధ్యం కాలేదు ({err_msg}). వేరే ఏ తేదీ లేదా సమయం కావాలి?"
                elif detected_lang == "te-Latn":
                    err_prompt = f"Kshaminchandi, aa slot-ki reschedule cheyalekapoyamu ({err_msg}). Vera date leda time cheppandi please?"
                else:
                    err_prompt = f"I apologize, but that slot is unavailable to reschedule: {err_msg}. What alternate date or time would you prefer?"
                return err_prompt, True
        else:
            session.step = "awaiting_datetime"
            db.commit()
            if detected_lang == "ta-IN":
                return "புதிய முன்பதிவுக்கு எந்த நாள் மற்றும் நேரம் வசதியாக இருக்கும்?", True
            elif detected_lang == "ta-Latn":
                return "Puthiya appointment-ku entha date and time convenient-ah irukum?", True
            elif detected_lang == "te-IN":
                return "కొత్త అపాయింట్‌మెంట్ కోసం ఏ రోజు మరియు సమయం అనుకూలంగా ఉంటుంది?", True
            elif detected_lang == "te-Latn":
                return "Kotha appointment kosam ye date and time convenient-ga untundi?", True
            return "What new date and time would you like to reschedule your appointment to?", True

    # Action: Check Availability
    if intent == "check_availability":
        target_d = (now + timedelta(days=1)).date()
        if session.appointment_datetime_iso:
            try:
                target_d = datetime.fromisoformat(session.appointment_datetime_iso).date()
            except Exception:
                pass
        elif meta.get("partial_date"):
            try:
                target_d = date.fromisoformat(meta["partial_date"])
            except Exception:
                pass

        avail_res = execute_tool_call(
            db=db,
            business_id=business.id,
            function_name="check_available_slots",
            arguments={"date": target_d.isoformat(), "service_id": session.service_id},
        )
        slots = avail_res.get("available_slots", [])
        lower_speech = speech_clean.lower()
        if any(k in lower_speech for k in ("morning", "kaalai", "kaalaila", "udayam", "podduna")):
            morning_slots = [s for s in slots if int(s.split(":")[0]) < 12]
            if morning_slots:
                slots = morning_slots
        elif any(k in lower_speech for k in ("afternoon", "madhiyam", "mathiyam", "madhyanam")):
            aft_slots = [s for s in slots if 12 <= int(s.split(":")[0]) < 16]
            if aft_slots:
                slots = aft_slots
        elif any(k in lower_speech for k in ("evening", "saayandhram", "sayanthiram", "sayantram", "night")):
            eve_slots = [s for s in slots if int(s.split(":")[0]) >= 16]
            if eve_slots:
                slots = eve_slots

        if slots:
            meta["partial_date"] = target_d.isoformat()
            meta["proposed_slot"] = slots[0]
            session.step = "awaiting_datetime"
            slot_str = ", ".join(slots[:4])
            if detected_lang == "ta-IN":
                prompt = f"{target_d} அன்று மருத்துவர்கள் ஆலோசனைகள் வழங்குகிறார்கள். கிடைக்கும் நேரங்கள்: {slot_str}. இதில் எந்த நேரம் உங்களுக்கு வசதியாக இருக்கும்?"
            elif detected_lang == "ta-Latn":
                prompt = f"{target_d}-la doctors available-ah irukaanga. Available slots: {slot_str}. Entha time ungalukku convenient-ah irukum?"
            elif detected_lang == "te-IN":
                prompt = f"{target_d} తేదీన వైద్యులు అందుబాటులో ఉన్నారు. అందుబాటులో ఉన్న సమయాలు: {slot_str}. ఇందులో ఏ సమయం అనుకూలంగా ఉంటుంది?"
            elif detected_lang == "te-Latn":
                prompt = f"{target_d}-lo doctors available-ga unnaru. Available slots: {slot_str}. Ee time meeku convenient-ga untundi?"
            else:
                prompt = f"On {target_d}, doctors are available. Available slots are: {slot_str}. Which time works best for you?"
        else:
            if detected_lang == "ta-IN":
                prompt = f"மன்னிக்கவும், {target_d} அன்று மருத்துவர் ஆலோசனை நேரம் கிடைக்கவில்லை. தயவுசெய்து வேறு தேதியை தேர்ந்தெடுக்கவும்."
            elif detected_lang == "ta-Latn":
                prompt = f"Sorry, {target_d}-la open slots illai. Vera date select panreengala?"
            elif detected_lang == "te-IN":
                prompt = f"క్షమించండి, {target_d} తేదీన స్లాట్లు అందుబాటులో లేవు. దయచేసి మరొక తేదీని ఎంచుకోండి."
            elif detected_lang == "te-Latn":
                prompt = f"Sorry, {target_d}-lo open slots levu. Vera date select chestara?"
            else:
                prompt = f"I apologize, but there are no open slots on {target_d}. Please choose another date."

        history.append({"role": "assistant", "text": prompt})
        session.dialog_history = json.dumps(history)
        session.metadata_json = json.dumps(meta)
        db.commit()
        return prompt, True

    # 8. Slot-Filling State Transitions for Appointment Booking

    # A. Missing Service
    if not session.service_id:
        if has_symptom_or_illness(speech_clean):
            physician_srv = None
            for srv in active_services:
                s_lower = srv.name.lower()
                if any(k in s_lower for k in ("physician", "general", "medicine", "doctor", "consultation", "consult")):
                    physician_srv = srv
                    break
            if not physician_srv and active_services:
                physician_srv = active_services[0]
            if physician_srv:
                session.service_id = physician_srv.id
                session.service_name = physician_srv.name
                meta["service_name"] = physician_srv.name
                session.step = "awaiting_datetime"
                srv_label = session.service_name
                db.commit()

                if detected_lang == "ta-IN":
                    prompt = f"உடம்பு சரியில்லையா, நிச்சயமாக பொது மருத்துவரிடம் ஆலோசிக்கலாம். உங்கள் {srv_label} முன்பதிவு செய்ய எந்த நாள் மற்றும் நேரம் வசதியாக இருக்கும்?"
                elif detected_lang == "ta-Latn":
                    prompt = f"Odambu seri illaya, kandippa doctor-ai paarkalam. Ungal {srv_label}-ku entha date and time convenient-ah irukum?"
                elif detected_lang == "te-IN":
                    prompt = f"ఒంట్లో బాగోలేదా, తప్పకుండా సాధారణ వైద్యుడి సంప్రదింపులకు ఏర్పాటు చేస్తాను. ఏ రోజు మరియు సమయం అనుకూలంగా ఉంటుంది?"
                elif detected_lang == "te-Latn":
                    prompt = f"Ontlo bagoledha, thappakunda doctor consultation chudham. Ye date and time convenient-ga untundi?"
                else:
                    prompt = f"I'm sorry to hear that you're not feeling well. Let's arrange a {srv_label}. What date and time works best for you?"

                history.append({"role": "assistant", "text": prompt})
                session.dialog_history = json.dumps(history)
                session.metadata_json = json.dumps(meta)
                db.commit()
                return prompt, True

        session.step = "awaiting_service"
        db.commit()
        sample_services = ", ".join([s.name for s in active_services[:3]]) or "General Physician Consultation"

        if was_awaiting_service:
            if is_short_affirmative_or_filler(speech_clean):
                if detected_lang == "ta-IN":
                    prompt = f"மகிழ்ச்சி. நீங்கள் எந்த மருத்துவ சேவை பதிவு செய்ய விரும்புகிறீர்கள்? உதாரணத்திற்கு: {sample_services}."
                elif detected_lang == "ta-Latn":
                    prompt = f"Sure. Neenga entha medical service book panna virumbureenga? For example: {sample_services}."
                elif detected_lang == "te-IN":
                    prompt = f"తప్పకుండా. మీరు ఏ వైద్య సేవ కోసం బుక్ చేయాలనుకుంటున్నారో దయచేసి చెప్పగలరా? ఉదాహరణకు: {sample_services}."
                elif detected_lang == "te-Latn":
                    prompt = f"Sure. Meeru ye medical service book cheyalani anukuntunnaro cheppandi please? For example: {sample_services}."
                else:
                    prompt = f"I'd be glad to help you book an appointment. Which medical service would you like? For example: {sample_services}."
            else:
                if detected_lang == "ta-IN":
                    prompt = f"மன்னிக்கவும், நீங்கள் குறிப்பிட்ட மருத்துவ சேவை தெளிவாக புரியவில்லை. நாங்கள் வழங்கும் சேவைகள்: {sample_services}. இதில் எது வேண்டும் என்று மீண்டும் கூற முடியுமா?"
                elif detected_lang == "ta-Latn":
                    prompt = f"Mannikavum, neenga sonna medical service puriyala. We offer: {sample_services}. Edhu venum-nu thirumba solla mudiyuma?"
                elif detected_lang == "te-IN":
                    prompt = f"క్షమించండి, మీరు చెప్పిన వైద్య సేవ స్పష్టంగా అర్థం కాలేదు. మేము అందించే సేవలు: {sample_services}. ఇందులో మీకు ఏది కావాలో దయచేసి మళ్ళీ చెప్పండి."
                elif detected_lang == "te-Latn":
                    prompt = f"Kshaminchandi, meeru cheppina medical service ardham kaaledu. We offer: {sample_services}. Edi kavaalo malli cheppandi please."
                else:
                    prompt = f"I didn't quite catch the medical service name. We offer {sample_services}. Could you please repeat which medical service you would like?"
        else:
            lang = session.language
            if lang == "ta-IN":
                prompt = "நீங்கள் எந்த மருத்துவ ஆலோசனை பதிவு செய்ய விரும்புகிறீர்கள்? பொது மருத்துவம் அல்லது இதய சிகிச்சை ஆலோசனை பெறலாம்."
            elif detected_lang == "ta-Latn":
                prompt = f"Neenga entha medical service book panna virumbureenga? For example: {sample_services}."
            elif detected_lang == "te-IN":
                prompt = f"మీరు ఏ వైద్య సేవ కోసం అపాయింట్‌మెంట్ బుక్ చేయాలనుకుంటున్నారు? ఉదాహరణకు: {sample_services}."
            elif detected_lang == "te-Latn":
                prompt = f"Meeru ye medical service book cheyalani anukuntunnaru? For example: {sample_services}."
            else:
                sample_services = ", ".join([s.name for s in active_services[:3]]) or "General Physician"
                prompt = f"Which medical service would you like to book? For example: {sample_services}."

        history.append({"role": "assistant", "text": prompt})
        session.dialog_history = json.dumps(history)
        session.metadata_json = json.dumps(meta)
        db.commit()
        return prompt, True

    # B. Missing Date & Time
    if not session.appointment_datetime_iso:
        session.step = "awaiting_datetime"
        srv_label = session.service_name or "appointment"

        if meta.get("partial_date") and not meta.get("partial_time"):
            p_date_str = meta["partial_date"]
            period = meta.get("period_of_day")
            is_tomorrow = False
            try:
                d_obj = date.fromisoformat(p_date_str)
                if d_obj == (now + timedelta(days=1)).date():
                    is_tomorrow = True
            except Exception:
                pass

            if is_tomorrow and period == "morning":
                if detected_lang == "ta-IN":
                    prompt = "சரிங்க! நாளைக்கு காலைல அப்பாயின்ட்மென்ட் செக் பண்றேன். எந்த நேரம் உங்களுக்கு வசதி?"
                elif detected_lang == "ta-Latn":
                    prompt = "Seri! Naalaiku morning appointment check panren. Endha time convenient?"
                elif detected_lang == "te-IN":
                    prompt = "సరే! రేపు ఉదయం అపాయింట్‌మెంట్ చూస్తాను. ఏ సమయం మీకు అనుకూలంగా ఉంటుంది?"
                elif detected_lang == "te-Latn":
                    prompt = "Sare! Repu morning appointment check chestanu. Ye time convenient-ga untundi?"
                else:
                    prompt = "Sure! Checking appointments for tomorrow morning. What time is convenient for you?"
            elif is_tomorrow:
                if detected_lang == "ta-IN":
                    prompt = "சரிங்க! நாளைக்கு அப்பாயின்ட்மென்ட் செக் பண்றேன். எந்த நேரம் உங்களுக்கு வசதி?"
                elif detected_lang == "ta-Latn":
                    prompt = "Seri! Naalaiku appointment check panren. Endha time convenient?"
                elif detected_lang == "te-IN":
                    prompt = "సరే! రేపు అపాయింట్‌మెంట్ చూస్తాను. ఏ సమయం మీకు అనుకూలంగా ఉంటుంది?"
                elif detected_lang == "te-Latn":
                    prompt = "Sare! Repu appointment check chestanu. Ye time convenient-ga untundi?"
                else:
                    prompt = "Sure! Checking appointments for tomorrow. What time works best for you?"
            else:
                if detected_lang == "ta-IN":
                    prompt = f"சரிங்க! {p_date_str} அன்று எந்த நேரம் வசதியாக இருக்கும்?"
                elif detected_lang == "ta-Latn":
                    prompt = f"Seri! {p_date_str}-la entha time convenient-ah irukum?"
                elif detected_lang == "te-IN":
                    prompt = f"{p_date_str} తేదీన ఏ సమయం అనుకూలంగా ఉంటుంది?"
                elif detected_lang == "te-Latn":
                    prompt = f"{p_date_str} roju ye time convenient-ga untundi?"
                else:
                    prompt = f"What time on {p_date_str} works best for you?"
        elif meta.get("partial_time") and not meta.get("partial_date"):
            p_time_str = meta["partial_time"]
            if detected_lang == "ta-IN":
                prompt = f"{p_time_str} மணிக்கு எந்த தேதி வேண்டும்?"
            elif detected_lang == "ta-Latn":
                prompt = f"{p_time_str}-ku entha date venum?"
            elif detected_lang == "te-IN":
                prompt = f"{p_time_str} సమయానికి ఏ తేదీ అనుకూలంగా ఉంటుంది?"
            elif detected_lang == "te-Latn":
                prompt = f"{p_time_str}-ki ye date kavali?"
            else:
                prompt = f"Which date would you like for your {p_time_str} appointment?"
        else:
            lang = session.language
            if lang == "ta-IN":
                prompt = f"நிச்சயமாக. கிடைக்கக்கூடிய அப்பாயிண்ட்மென்ட்களை சரிபார்க்கிறேன். உங்கள் {srv_label} மருத்துவ ஆலோசனையை பதிவு செய்ய எந்த நாள் மற்றும் நேரம் வசதியாக இருக்கும்?"
            elif detected_lang == "ta-Latn":
                prompt = f"Certainly. Available appointments-ai check panren. Ungal {srv_label}-ku entha date and time convenient-ah irukum?"
            elif detected_lang == "te-IN":
                prompt = f"తప్పకుండా. అందుబాటులో ఉన్న అపాయింట్‌మెంట్‌లను పరిశీలిస్తాను. మీ {srv_label} సంప్రదింపులకు ఏ రోజు மற்றும் సమయం అనుకూలంగా ఉంటుంది?"
            elif detected_lang == "te-Latn":
                prompt = f"Certainly. Available appointments check chestanu. Mee {srv_label} kosam ye date and time convenient-ga untundi?"
            else:
                prompt = f"Certainly. Let me check the available appointments. What date and time works best for your {srv_label}?"

        history.append({"role": "assistant", "text": prompt})
        session.dialog_history = json.dumps(history)
        session.metadata_json = json.dumps(meta)
        db.commit()
        return prompt, True

    # C. Missing Customer Name
    if not session.customer_name or session.customer_name.startswith("Caller "):
        session.step = "awaiting_name"
        slot_ack = ""
        if meta.get("partial_time"):
            try:
                h, m = meta["partial_time"].split(":")
                raw_h = int(h)
                h12 = raw_h if (1 <= raw_h <= 12) else (raw_h - 12 if raw_h > 12 else 12)
                if detected_lang == "ta-Latn":
                    slot_ack = f"Seri, {h12} mani slot available-ah irukku. "
                elif detected_lang == "ta-IN":
                    slot_ack = f"சரிங்க, {h12} மணி ஸ்லாட் இருக்கு. "
                elif detected_lang == "te-IN":
                    slot_ack = f"సరే, {h12} గంటల స్లాట్ అందుబాటులో ఉంది. "
                elif detected_lang == "te-Latn":
                    slot_ack = f"Sare, {h12} gantala slot available-ga undi. "
                else:
                    slot_ack = f"The {h12} o'clock slot is available. "
            except Exception:
                slot_ack = ""

        if detected_lang == "ta-IN":
            prompt = f"{slot_ack}முன்பதிவு செய்ய உங்கள் பெயரை கூறுங்கள் please?"
        elif detected_lang == "ta-Latn":
            prompt = f"{slot_ack}Booking confirm panna unga full name sollunga please?"
        elif detected_lang == "te-IN":
            prompt = f"{slot_ack}బుకింగ్ నిర్ధారించడానికి మీ పూర్తి పేరు చెప్పండి please?"
        elif detected_lang == "te-Latn":
            prompt = f"{slot_ack}Booking confirm cheyadaniki mee full name cheppandi please?"
        else:
            prompt = f"{slot_ack}May I please have your full name for the booking record?"

        history.append({"role": "assistant", "text": prompt})
        session.dialog_history = json.dumps(history)
        session.metadata_json = json.dumps(meta)
        db.commit()
        return prompt, True

    # C2. Missing Customer Phone (if caller_phone is placeholder and not yet captured)
    is_placeholder_phone = not session.caller_phone or session.caller_phone in ("+919876543210", "unknown", "anonymous", "")
    if is_placeholder_phone and not meta.get("customer_phone") and (session.step in ("awaiting_phone", "phone_number") or meta.get("require_phone")):
        session.step = "awaiting_phone"
        if detected_lang == "ta-IN":
            prompt = "முன்பதிவை உறுதிசெய்ய உங்கள் தொலைபேசி எண்ணை கூற முடியுமா?"
        elif detected_lang == "ta-Latn":
            prompt = "Booking confirm panna ungal phone number sollunga please?"
        elif detected_lang == "te-IN":
            prompt = "అపాయింట్‌మెంట్ నిర్ధారణ కోసం మీ ఫోన్ నంబర్ తెలియజేయగలరా?"
        elif detected_lang == "te-Latn":
            prompt = "Booking confirm cheyadaniki mee phone number cheppandi please?"
        else:
            prompt = "May I please have your phone number to complete the booking?"

        history.append({"role": "assistant", "text": prompt})
        session.dialog_history = json.dumps(history)
        session.metadata_json = json.dumps(meta)
        db.commit()
        return prompt, True

    # D. Verbal Confirmation Step (All 3 entities present)
    parsed_dt = datetime.fromisoformat(session.appointment_datetime_iso)
    date_str = format_confirmation_date(parsed_dt, session.language, biz_tz)
    time_str = format_confirmation_time(parsed_dt, session.language, biz_tz)
    srv_name = session.service_name or "consultation"

    if require_confirmation:
        if session.step != "awaiting_confirmation":
            session.step = "awaiting_confirmation"
            session.metadata_json = json.dumps(meta)
            db.commit()

            if detected_lang == "ta-IN":
                prompt = f"{session.customer_name}, {date_str} அன்று {time_str} மணிக்கு {srv_name} ஆலோசனையை பதிவு செய்யவா? உறுதிப்படுத்த விரும்புகிறீர்களா?"
            elif detected_lang == "ta-Latn":
                prompt = f"{session.customer_name}, {date_str} at {time_str}-ku {srv_name} appointment confirm pannava?"
            elif detected_lang == "te-IN":
                prompt = f"{session.customer_name} గారూ, {date_str} తేదీన {time_str} గంటలకు {srv_name} అపాయింట్‌మెంట్ నమోదు చేయమంటారా? నిర్ధారించమంటారా?"
            elif detected_lang == "te-Latn":
                prompt = f"{session.customer_name} garu, {date_str} at {time_str}-ki {srv_name} appointment confirm cheyyamantare?"
            else:
                prompt = f"I have you down for a {srv_name} appointment on {date_str} at {time_str} for {session.customer_name}. Would you like me to confirm this booking?"

            history.append({"role": "assistant", "text": prompt})
            session.dialog_history = json.dumps(history)
            db.commit()
            return prompt, True

        # In awaiting_confirmation:
        # Check if caller cancelled or denied
        if intent in ("denial", "cancellation") and not candidate_dt:
            session.step = "greeting"
            session.appointment_datetime_iso = None
            meta.pop("partial_time", None)
            session.metadata_json = json.dumps(meta)
            db.commit()
            if detected_lang == "ta-IN":
                prompt = "சரி, உங்கள் முன்பதிவு கோரிக்கை ரத்து செய்யப்பட்டது. வேறு ஏதேனும் உதவி தேவையா?"
            elif detected_lang == "te-IN":
                prompt = "సరే, మీ అపాయింట్‌మెంట్ రద్దు చేయబడింది. మీకు ఇంకేమైనా సహాయం కావాలా?"
            else:
                prompt = "Understood, I will not confirm this booking. Is there anything else I can assist you with?"
            history.append({"role": "assistant", "text": prompt})
            session.dialog_history = json.dumps(history)
            db.commit()
            return prompt, True

        # Check if caller provided a correction
        is_datetime_changed = (
            candidate_dt is not None
            and prior_appointment_datetime_iso is not None
            and candidate_dt.isoformat() != prior_appointment_datetime_iso
        )
        if is_datetime_changed:
            session.appointment_datetime_iso = candidate_dt.isoformat()
            parsed_dt = candidate_dt
            date_str = format_confirmation_date(parsed_dt, session.language, biz_tz)
            time_str = format_confirmation_time(parsed_dt, session.language, biz_tz)
            session.metadata_json = json.dumps(meta)
            db.commit()

            if detected_lang == "ta-IN":
                prompt = f"உங்கள் முன்பதிவு நேரத்தை {date_str} {time_str} மணிக்கு மாற்றியுள்ளேன். இப்போது பதிவு செய்யவா?"
            elif detected_lang == "te-IN":
                prompt = f"మీ అపాయింట్‌మెంట్ సమయాన్ని {date_str} {time_str} కు మార్చాను. ఇప్పుడు నిర్ధారించమంటారా?"
            else:
                prompt = f"I have updated your appointment to {srv_name} on {date_str} at {time_str} for {session.customer_name}. Would you like me to confirm this booking?"
            history.append({"role": "assistant", "text": prompt})
            session.dialog_history = json.dumps(history)
            db.commit()
            return prompt, True

        # Require explicit confirmation before committing booking
        if intent != "confirmation":
            if has_symptom_or_illness(speech_clean):
                if detected_lang == "ta-IN":
                    prompt = f"கவலைப்பட வேண்டாம், உங்கள் மருத்துவரிடம் இதை தெரிவிக்கலாம். முதலில் உங்கள் {srv_name} ஆலோசனையை {date_str} {time_str} மணிக்கு பதிவு செய்ய உறுதிப்படுத்துகிறீர்களா?"
                elif detected_lang == "ta-Latn":
                    prompt = f"Kavalapadadheenga, doctor kitta idhai sollalam. Ungal {srv_name} appointment-ai {date_str} at {time_str}-ku confirm pannava?"
                elif detected_lang == "te-IN":
                    prompt = f"కంగారు పడకండి, డాక్టర్‌తో ఇది మాట్లాడవచ్చు. మొదట మీ {srv_name} అపాయింట్‌మెంట్‌ను {date_str} {time_str} కు నిర్ధారించమంటారా?"
                elif detected_lang == "te-Latn":
                    prompt = f"Kangarupadakandi, doctor-tho matladadam. Mee {srv_name} appointment {date_str} at {time_str}-ki confirm cheyyamantare?"
                else:
                    prompt = f"I understand your concern and the doctor will assist you with that. Should I go ahead and confirm your {srv_name} appointment for {date_str} at {time_str}?"
            else:
                if detected_lang == "ta-IN":
                    prompt = f"நான் உங்கள் {srv_name} ஆலோசனையை {date_str} அன்று {time_str} மணிக்கு பதிவு செய்யவா? தயவுசெய்து 'ஆம்' அல்லது 'இல்லை' என்று கூறவும்."
                elif detected_lang == "ta-Latn":
                    prompt = f"Ungal {srv_name} appointment-ai {date_str} at {time_str}-ku confirm pannava? Yes or No sollunga please."
                elif detected_lang == "te-IN":
                    prompt = f"నేను మీ {srv_name} అపాయింట్‌మెంట్‌ను {date_str} తేదీన {time_str} గంటలకు నమోదు చేయమంటారా? దయచేసి 'అవును' లేదా 'వద్దు' అని చెప్పండి."
                elif detected_lang == "te-Latn":
                    prompt = f"Mee {srv_name} appointment-ni {date_str} at {time_str}-ki confirm cheyyamantare? Yes leda No cheppandi please."
                else:
                    prompt = f"Just to confirm, would you like me to book your {srv_name} appointment on {date_str} at {time_str}? Please say yes to confirm or no to cancel."

            history.append({"role": "assistant", "text": prompt})
            session.dialog_history = json.dumps(history)
            db.commit()
            return prompt, True

    # 9. Commit Booking via Tool Dispatcher!
    try:
        book_res = execute_tool_call(
            db=db,
            business_id=business.id,
            function_name="book_appointment",
            arguments={
                "customer_name": session.customer_name,
                "customer_phone": session.caller_phone,
                "service_id": session.service_id,
                "appointment_time": parsed_dt.isoformat(),
                "notes": f"Booked autonomously via AI Voice Receptionist (CallSid: {session.call_sid}).",
            },
        )

        if not book_res.get("success"):
            err_detail = book_res.get("error", "Slot unavailable")
            logger.warning("Booking failed for CallSid %s: %s", session.call_sid, err_detail)
            session.appointment_datetime_iso = None
            session.step = "awaiting_datetime"
            meta.pop("partial_time", None)
            session.metadata_json = json.dumps(meta)
            db.commit()
            if detected_lang == "ta-IN":
                err_prompt = f"மன்னிக்கவும், அந்த நேரத்தில் அப்பாயிண்ட்மென்ட் பதிவு செய்ய முடியவில்லை ({err_detail}). தயவுசெய்து வேறு ஒரு நேரத்தை தேர்ந்தெடுக்கவும்."
            elif detected_lang == "ta-Latn":
                err_prompt = f"Mannikavum, andha time-la appointment book panna mudiyala ({err_detail}). Vera time select pannunga please."
            elif detected_lang == "te-IN":
                err_prompt = f"క్షమించండి, ఆ సమయంలో అపాయింట్‌మెంట్ బుక్ చేయలేకపోయాము ({err_detail}). దయచేసి వేరే సమయాన్ని ఎంచుకోండి."
            elif detected_lang == "te-Latn":
                err_prompt = f"Kshaminchandi, aa time-lo appointment book cheyalekapoyamu ({err_detail}). Vera time select cheskondi please."
            else:
                err_prompt = f"I apologize, but that appointment slot could not be booked ({err_detail}). Please select another time."
            history.append({"role": "assistant", "text": err_prompt})
            session.dialog_history = json.dumps(history)
            db.commit()
            return err_prompt, True

        session.booking_id = book_res.get("appointment_id")
        session.is_completed = True
        session.step = "completed"

        dashboard_event_manager.dispatch(
            business_id=business.id,
            event_type="APPOINTMENT_CREATED",
            data={
                "appointment_id": session.booking_id,
                "call_id": session.call_sid,
                "customer_name": session.customer_name,
                "customer_phone": session.caller_phone,
                "service_name": session.service_name,
                "appointment_time": parsed_dt.isoformat(),
                "status": "upcoming",
                "source": "voice_ai",
            },
        )

        date_str = format_confirmation_date(parsed_dt, session.language, biz_tz)
        time_str = format_confirmation_time(parsed_dt, session.language, biz_tz)
        srv_name = session.service_name or "consultation"

        if detected_lang == "ta-IN":
            confirmation = (
                f"நன்றி {session.customer_name}. உங்கள் {srv_name} ஆலோசனை "
                f"{date_str} அன்று {time_str} மணிக்கு வெற்றிகரமாக பதிவு செய்யப்பட்டது. "
                f"{business.name} அழைத்ததற்கு நன்றி. வணக்கம்!"
            )
        elif detected_lang == "ta-Latn":
            confirmation = (
                f"Nandri {session.customer_name}. Ungal appointment for {srv_name} "
                f"on {date_str} at {time_str} successfully confirmed. "
                f"Thank you for calling {business.name}. Vanakkam!"
            )
        elif detected_lang == "te-IN":
            confirmation = (
                f"ధన్యవాదాలు {session.customer_name}. మీ {srv_name} సంప్రదింపులు "
                f"{date_str} తేదీన {time_str} గంటలకు విజయవంతంగా నిర్ధారించబడ్డాయి. "
                f"{business.name} కు కాల్ చేసినందుకు ధన్యవాదాలు. నమస్కారం!"
            )
        elif detected_lang == "te-Latn":
            confirmation = (
                f"Dhanyavadalu {session.customer_name}. Mee {srv_name} appointment "
                f"on {date_str} at {time_str} successfully confirmed. "
                f"Thank you for calling {business.name}. Namaskaram!"
            )
        else:
            confirmation = (
                f"Thank you, {session.customer_name}. Your appointment for {srv_name} "
                f"on {date_str} at {time_str} has been successfully confirmed. "
                f"A confirmation has been registered for {session.caller_phone}. "
                f"Thank you for calling {business.name}. Goodbye!"
            )

        history.append({"role": "assistant", "text": confirmation})
        session.dialog_history = json.dumps(history)

        # Store metadata
        meta.update({
            "intent": session.intent,
            "detected_language": detected_lang,
            "service_id": session.service_id,
            "service_name": session.service_name,
            "customer_name": session.customer_name,
            "appointment_id": session.booking_id,
            "appointment_time": session.appointment_datetime_iso,
        })
        session.metadata_json = json.dumps(meta)

        # Synchronize transcript to existing Call record
        call_rec = db.scalar(
            select(Call).where(
                or_(Call.id == session.call_sid, Call.summary.like(f"%{session.call_sid}%"))
            )
        )
        if call_rec:
            call_rec.status = "completed"
            call_rec.caller_name = session.customer_name or call_rec.caller_name
            if not call_rec.customer_id:
                cust = db.scalar(
                    select(Customer).where(
                        Customer.phone == session.caller_phone.strip(),
                        Customer.business_id == business.id,
                    )
                )
                if cust:
                    call_rec.customer_id = cust.id
            call_rec.summary = (
                f"Autonomous voice booking: {srv_name} on {date_str} at {time_str} for {session.customer_name}. "
                f"(Booking ID: {session.booking_id})"
            )
            call_rec.transcript = "\n".join([f"{t['role'].upper()}: {t['text']}" for t in history])

        db.commit()
        logger.info("Successfully booked appointment %s for CallSid %s", session.booking_id, session.call_sid)
        return confirmation, False

    except Exception as exc:
        logger.error("Error finalizing appointment booking for CallSid %s: %s", session.call_sid, exc, exc_info=True)
        db.rollback()
        if session.language.startswith("ta"):
            return ("மன்னிக்கவும், முன்பதிவில் சிறிய பிழை ஏற்பட்டுள்ளது. தயவுசெய்து சிறிது நேரம் கழித்து அழைக்கவும்.", False)
        elif session.language.startswith("te"):
            return ("క్షమించండి, బుకింగ్‌లో చిన్న సాంకేతిక లోపం ఏర్పడింది. దయచేసి కాసేపటి తర్వాత మళ్ళీ కాల్ చేయండి.", False)
        return ("I apologize, but we encountered an error while confirming your reservation. Please try calling back later.", False)
