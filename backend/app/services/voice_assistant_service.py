"""Conversational Voice Assistant service powered by LLM Conversational Engine and Phase 2 Scheduling."""

from datetime import date, datetime, timedelta, timezone
import json
import re
from typing import Any
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.appointment import Appointment
from app.models.assistant import AssistantConfig, Service
from app.models.business import Business
from app.models.call import Call
from app.models.conversation_session import ConversationSession
from app.models.customer import Customer
from app.services.ai.factory import get_llm_provider
from app.services.ai.language_detector import (
    detect_language,
    get_display_language_name,
    is_tamil_script,
)
from app.services.ai.tools import execute_tool_call
from app.services.appointment_service import book_appointment_core
from app.services.dashboard_events import dashboard_event_manager
from app.services.scheduling_service import (
    calculate_available_slots,
    cancel_appointment_core,
    reschedule_appointment_core,
)

logger = get_logger(__name__)

# Distinctive service alias keywords for intelligent mapping across English, Tamil, and Telugu
SERVICE_ALIASES: dict[str, list[str]] = {
    "cardio": [
        "cardio", "cardiology", "heart", "ecg", "cardiac",
        "இதயம்", "கார்டியாலஜி", "இதய", "நெஞ்சு",
        "idhayam", "heart problem", "cardiac checkup",
        "గుండె", "కార్డియాలజీ", "గుండె జబ్బు", "హృదయ",
        "gunde", "gunde noppi", "heart problem"
    ],
    "physician": [
        "physician", "general physician", "general medicine", "internal medicine",
        "பொது மருத்துவம்", "பொது",
        "maruthuvar", "maruthuvam",
        "సాధారణ వైద్యం", "సాధారణ", "వైద్యుడు",
        "vaidhyudu", "vaidyudu", "general medicine", "doctoru"
    ],
    "pediatric": [
        "pediatric", "pediatrician", "child", "baby", "kid", "vaccine", "immunization",
        "குழந்தை", "குழந்தைகள்", "குழந்தை மருத்துவம்",
        "kuzhandhai", "paappa", "paapa",
        "పిల్లల", "పిల్లలు", "పిల్లల వైద్యుడు",
        "pillalu", "chinna pillalu", "pillala doctor"
    ],
    "dental": [
        "dental", "dentist", "teeth", "tooth", "cleaning", "cavity",
        "பல்", "பல் மருத்துவம்",
        "pal", "pal vali", "teeth cleaning",
        "పళ్ళు", "దంత", "పంటి నొప్పి", "పంటి",
        "pallu", "panti noppi", "danta chikitsa"
    ],
    "diagnostics": [
        "blood test", "diagnostic", "diagnostics", "lab test", "lipid",
        "இரத்த பரிசோதனை", "பரிசோதனை",
        "raththam", "blood", "test",
        "రక్త పరీక్ష", "పరీక్ష",
        "raktha pareeksha", "lab test"
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

    # Check if a customer already exists with a known real name
    customer_name: str | None = None
    clean_phone = caller_phone.strip()
    cust = db.scalar(
        select(Customer).where(
            Customer.business_id == business_id,
            Customer.phone == clean_phone,
        )
    )
    if cust and cust.name and not cust.name.startswith("Caller "):
        customer_name = cust.name

    # Check assistant configuration for business default language
    cfg = db.scalar(
        select(AssistantConfig).where(AssistantConfig.business_id == business_id)
    )
    initial_lang = cfg.language if cfg and cfg.language else default_language

    session = ConversationSession(
        call_sid=call_sid,
        business_id=business_id,
        caller_phone=clean_phone,
        customer_name=customer_name,
        step="greeting",
        language=initial_lang,
        detected_language="en-IN",
        dialog_history=json.dumps([]),
        metadata_json=json.dumps({}),
        retry_count=0,
        is_completed=False,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    logger.info("Initialized persistent conversation session for CallSid: %s", call_sid)
    return session


def detect_intent(text: str) -> str:
    """Classify the caller's intent from speech input with multilingual support."""
    if not text:
        return "unknown"

    lower = text.lower()

    # 1. Exit / Goodbye keywords
    if any(k in lower for k in [
        "bye", "goodbye", "exit", "nevermind", "no thanks",
        "don't want", "dont want", "வேண்டாம்", "நன்றி", "போதும்",
        "vendam", "podhum", "mudikalam", "call cut",
        "వద్దు", "vaddu", "vaddhu", "చాలు", "chalu", "chalamma",
        "undandi", "call cut cheyandi",
    ]):
        return "cancellation"

    # 2. Appointment Cancellation intent
    if any(k in lower for k in [
        "cancel appointment", "cancel my appointment", "appointment cancel",
        "drop appointment", "ரத்து", "முன்பதிவை ரத்து", "ரத்து செய்",
        "cancel pannanum", "appointment-ai cancel",
        "రద్దు", "రద్దు చేయండి", "అపాయింట్‌మెంట్ రద్దు",
        "cancel cheyandi", "raddhu cheyandi", "cancel cheyali", "appointment-ni cancel",
    ]):
        return "cancel_appointment"

    # 3. Appointment Rescheduling intent
    if any(k in lower for k in [
        "reschedule", "change time", "change date", "postpone", "prepone",
        "மாற்ற வேண்டும்", "நேரத்தை மாற்ற", "தேதியை மாற்ற",
        "mathanum", "maathanum", "reschedule pannanum", "appointment matha",
        "మార్చండి", "సమయం మార్చండి", "తేదీ మార్చండి",
        "marchandi", "change cheyandi", "reschedule cheyandi", "time marchali", "date marchali",
    ]):
        return "reschedule_appointment"

    # 4. Check Availability / Slots intent
    if any(k in lower for k in [
        "slots", "available", "availability", "when can i", "is doctor available",
        "free slots", "open slots", "நேரம் இருக்கிறதா", "எப்போது கிடைக்கும்",
        "slot iruka", "slots iruka", "neram iruka", "available-ah", "eppo varalam",
        "స్లాట్లు ఉన్నాయా", "సమయం ఉందా", "ఎప్పుడు రావచ్చు",
        "slots unnaya", "time undha", "eppudu raavachu", "available undha",
    ]):
        return "check_availability"

    # 5. Booking intent
    if any(k in lower for k in [
        "book", "appointment", "schedule", "reserve", "doctor",
        "consultation", "visit", "see", "checkup",
        "அப்பாயின்ட்மென்ட்", "முன்பதிவு", "டாக்டர்", "டாக்டர", "பார்க்க", "பார்க்க வேண்டும்",
        "venum", "parkanum", "pannanum", "doctor-ah parkanum",
        "బుక్ చేయాలి", "అపాయింట్‌మెంట్ కావాలి", "డాక్టర్ కావాలి", "డాక్టర్", "డాక్టర", "దర్శనం",
        "book cheyali", "appointment kavali", "doctor kavali", "chupinchukovali", "chudali",
    ]):
        return "booking"

    # 6. Affirmative / Confirmation keywords
    if any(k in lower for k in [
        "yes", "confirm", "sure", "okay", "fine", "correct",
        "yeah", "yep", "சரி", "ஆம்", "ஆமாம்", "sari", "aama", "kandippa",
        "అవును", "సరే", "ఖచ్చితంగా", "avunu", "thappakunda", "alage", "nijam",
    ]):
        return "confirmation"

    # 7. Greeting keywords
    if any(k in lower for k in [
        "hello", "hi", "hey", "good morning", "good evening",
        "வணக்கம்", "vanakkam", "namaste",
        "నమస్కారం", "నమస్తే", "namaskaram", "namaskaramandi",
    ]):
        return "greeting"

    return "unknown"


def match_service_from_catalog(text: str, services: list[Service]) -> Service | None:
    """Identify the requested service from speech matching against active business catalog."""
    if not text or not services:
        return None

    clean_text = text.lower()

    # 1. Direct name match (full service name or distinctive name)
    for srv in services:
        if srv.name and srv.name.lower() in clean_text:
            return srv

    # 2. Match distinctive words of service name (excluding generic words like 'and', 'care', 'consultation')
    generic_stopwords = {"and", "care", "consultation", "service", "center", "clinic", "checkup"}
    for srv in services:
        tokens = [
            t for t in re.findall(r"\w+", srv.name.lower())
            if len(t) > 3 and t not in generic_stopwords
        ]
        for token in tokens:
            if re.search(r"\b" + re.escape(token) + r"\b", clean_text):
                return srv

    # 3. Domain alias matching across English, Tamil, and Tanglish
    for key, aliases in SERVICE_ALIASES.items():
        for alias in aliases:
            is_matched = False
            if re.search(r"[\u0B80-\u0BFF\u0C00-\u0C7F]", alias):
                is_matched = alias in clean_text
            else:
                is_matched = bool(re.search(r"\b" + re.escape(alias) + r"\b", clean_text, re.IGNORECASE))

            if is_matched:
                for srv in services:
                    srv_lower = srv.name.lower()
                    if any(a in srv_lower for a in aliases):
                        return srv

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
    elif any(k in lower for k in ["tomorrow", "நாளை", "naalaiki", "naalai", "రేపు", "repu"]):
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
            r"\b(\d{1,2})(?::(\d{2}))?\s*(?:மணி|மணிக்க|மணிக்கு|mani|maniki|గంట|గంటలు|గంటలకు|గంటలకి|ganta|gantalu|gantaku|gantalaki|gantalaku|ki)",
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


def extract_caller_name(text: str, is_awaiting_name: bool = False) -> str | None:
    """Extract caller's name from spoken text."""
    if not text:
        return None

    # Pattern matches
    patterns = [
        r"(?:my name is|this is|i am|name is|i'm|call me)\s+([A-Za-z\s]+)",
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
        cleaned = re.sub(r"^(?:yes|sure|okay|yeah|it is|it's|its)\s+", "", text.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r"[^\w\s\u0B80-\u0BFF\u0C00-\u0C7F]", "", cleaned).strip()
        words = cleaned.split()
        if 1 <= len(words) <= 4:
            invalid_words = {"appointment", "doctor", "cardiology", "physician", "hospital", "clinic", "cancel", "yes", "no"}
            if not any(w.lower() in invalid_words for w in words):
                return " ".join(words).title()

    return None


def format_confirmation_date(dt: datetime, language: str = "en-IN") -> str:
    """Format appointment datetime for natural speech synthesis."""
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


def format_confirmation_time(dt: datetime, language: str = "en-IN") -> str:
    """Format appointment time for natural speech synthesis."""
    time_str = dt.strftime("%I:%M %p").lstrip("0")
    return time_str


def process_conversational_turn(
    db: Session,
    session: ConversationSession,
    speech_text: str | None,
    business: Business,
) -> tuple[str, bool]:
    """Advance the conversational turn powered by the AI Engine.

    Returns:
        tuple[str, bool]: (prompt_text_to_say, should_continue_gather)
    """
    now = datetime.now(timezone.utc)

    # 1. Check Idempotency: Prevent duplicate bookings if already completed
    if session.is_completed and session.booking_id:
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

    # 3. Handle Empty / Inaudible Input
    if not speech_clean:
        session.retry_count += 1
        db.commit()
        if session.retry_count >= 3:
            session.is_completed = True
            db.commit()
            if session.language.startswith("ta"):
                return ("உங்கள் குரல் தெளிவாக கேட்கவில்லை. தயவுசெய்து மீண்டும் அழைக்கவும். வணக்கம்.", False)
            elif session.language.startswith("te"):
                return ("మీ స్వరం స్పష్టంగా వినిపించలేదు. దయచేసి మళ్ళీ కాల్ చేయండి. నమస్కారం.", False)
            return ("We are unable to hear your response. Please call back later. Goodbye.", False)

        if session.language.startswith("ta"):
            return ("மன்னிக்கவும், உங்கள் குரல் கேட்கவில்லை. மீண்டும் கூறுங்கள்.", True)
        elif session.language.startswith("te"):
            return ("క్షమించండి, మీ స్వరం వినిపించలేదు. దయచేసి మళ్ళీ చెప్పండి.", True)
        return ("I apologize, but I did not catch that. Could you please repeat your request?", True)

    # Reset retry count upon receiving speech
    session.retry_count = 0

    # 4. Multilingual Language Detection & Persistence
    detected_lang = detect_language(speech_clean, session.language)
    session.detected_language = detected_lang

    # For telephony speech synthesis and voice routing:
    if detected_lang in ("ta-IN", "ta-Latn"):
        session.language = "ta-IN"
    elif detected_lang in ("te-IN", "te-Latn"):
        session.language = "te-IN"
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

    # 5. Intent Classification
    intent = detect_intent(speech_clean)
    if intent != "unknown":
        session.intent = intent

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
            return (f"{business.name} அழைத்ததற்கு நன்றி. Have a wonderful day. Vanakkam!", False)
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
        if matched_srv:
            session.service_id = matched_srv.id
            session.service_name = matched_srv.name
            logger.info("CallSid %s matched service: %s (%s)", session.call_sid, matched_srv.name, matched_srv.id)

    # Extract Datetime
    dt, err = extract_datetime_from_speech(speech_clean, now)
    if dt:
        session.appointment_datetime_iso = dt.isoformat()
        logger.info("CallSid %s extracted datetime: %s", session.call_sid, session.appointment_datetime_iso)

    # Extract Caller Name
    is_asking_name = session.step == "awaiting_name"
    if not session.customer_name or session.customer_name.startswith("Caller "):
        extracted_name = extract_caller_name(speech_clean, is_awaiting_name=is_asking_name)
        if extracted_name:
            session.customer_name = extracted_name
            logger.info("CallSid %s extracted caller name: %s", session.call_sid, extracted_name)

    # 7. Function Calling Actions (Cancellation, Rescheduling, Availability, Booking)

    # Action 1: Appointment Cancellation
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
                msg = f"మీ అపాయింట్‌మెంట్ విజయవంతంగా రద్దు చేయబడింది. {business.name} కు కాల్ చేసినందుకు ధన్యవాదాలు. నమస్కారం!"
            elif detected_lang == "te-Latn":
                msg = f"Mee appointment successfully cancel cheyabadindi. Thank you for calling {business.name}. Namaskaram!"
            else:
                msg = f"Your appointment has been successfully cancelled and your slot has been released. Thank you for calling {business.name}. Goodbye!"
            return msg, False
        else:
            err_msg = cancel_res.get("error", "No active appointment found.")
            return f"I apologize, but we could not find an active appointment to cancel: {err_msg}", True

    # Action 2: Appointment Rescheduling
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
                    msg = f"మీ అపాయింట్‌మెంట్ సమయం విజయవంతంగా మార్చబడింది. {business.name} కు కాల్ చేసినందుకు ధన్యవాదాలు. నమస్కారం!"
                elif detected_lang == "te-Latn":
                    msg = f"Mee appointment time successfully change ayindi. Thank you for calling {business.name}. Namaskaram!"
                else:
                    msg = f"Your appointment has been successfully rescheduled to the new time. Thank you for calling {business.name}. Goodbye!"
                return msg, False
            else:
                err_msg = resched_res.get("error", "Slot conflict.")
                return f"I apologize, but that slot is unavailable to reschedule: {err_msg}. What alternate date or time would you prefer?", True
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

    # Action 3: Check Availability
    if intent == "check_availability":
        target_date = (now + timedelta(days=1)).date()
        if session.appointment_datetime_iso:
            try:
                target_date = datetime.fromisoformat(session.appointment_datetime_iso).date()
            except Exception:
                pass

        avail_res = execute_tool_call(
            db=db,
            business_id=business.id,
            function_name="check_available_slots",
            arguments={"date": target_date.isoformat(), "service_id": session.service_id},
        )
        slots = avail_res.get("available_slots", [])
        if slots:
            slot_str = ", ".join(slots[:4])
            if detected_lang == "ta-IN":
                prompt = f"{target_date} அன்று கிடைக்கும் நேரங்கள்: {slot_str}. இதில் எந்த நேரம் வேண்டும்?"
            elif detected_lang == "ta-Latn":
                prompt = f"{target_date}-la available slots: {slot_str}. Entha time ungalukku convenient-ah irukum?"
            elif detected_lang == "te-IN":
                prompt = f"{target_date} తేదీన అందుబాటులో ఉన్న సమయాలు: {slot_str}. ఇందులో ఏ సమయం కావాలి?"
            elif detected_lang == "te-Latn":
                prompt = f"{target_date}-lo available slots: {slot_str}. Ee time meeku convenient-ga untundi?"
            else:
                prompt = f"On {target_date}, available slots are: {slot_str}. Which time works best for you?"
        else:
            prompt = f"I apologize, but there are no open slots on {target_date}. Please choose another date."
        return prompt, True

    # 8. Slot-Filling State Transitions for Appointment Booking

    # A. Missing Service
    if not session.service_id:
        session.step = "awaiting_service"
        db.commit()
        if detected_lang == "ta-IN":
            prompt = (
                "நீங்கள் எந்த மருத்துவ ஆலோசனை பதிவு செய்ய விரும்புகிறீர்கள்? "
                "பொது மருத்துவம் அல்லது இதய சிகிச்சை ஆலோசனை பெறலாம்."
            )
        elif detected_lang == "ta-Latn":
            sample_services = ", ".join([s.name for s in active_services[:3]]) or "General Physician"
            prompt = f"Neenga entha medical service book panna virumbureenga? For example: {sample_services}."
        elif detected_lang == "te-IN":
            sample_services = ", ".join([s.name for s in active_services[:3]]) or "సాధారణ వైద్యం"
            prompt = f"మీరు ఏ వైద్య సేవ కోసం అపాయింట్‌మెంట్ బుక్ చేయాలనుకుంటున్నారు? ఉదాహరణకు: {sample_services}."
        elif detected_lang == "te-Latn":
            sample_services = ", ".join([s.name for s in active_services[:3]]) or "General Physician"
            prompt = f"Meeru ye medical service book cheyalani anukuntunnaru? For example: {sample_services}."
        else:
            sample_services = ", ".join([s.name for s in active_services[:3]]) or "General Physician"
            prompt = f"Which medical service would you like to book? For example: {sample_services}."

        history.append({"role": "assistant", "text": prompt})
        session.dialog_history = json.dumps(history)
        db.commit()
        return prompt, True

    # B. Missing Date & Time
    if not session.appointment_datetime_iso:
        session.step = "awaiting_datetime"
        srv_label = session.service_name or "appointment"
        if detected_lang == "ta-IN":
            prompt = f"உங்கள் {srv_label} ஆலோசனைக்கு எந்த நாள் மற்றும் நேரம் வசதியாக இருக்கும்?"
        elif detected_lang == "ta-Latn":
            prompt = f"Ungal {srv_label} consultation-ku entha date and time convenient-ah irukum?"
        elif detected_lang == "te-IN":
            prompt = f"మీ {srv_label} సంప్రదింపులకు ఏ రోజు మరియు సమయం అనుకూలంగా ఉంటుంది?"
        elif detected_lang == "te-Latn":
            prompt = f"Mee {srv_label} consultation kosam ye date and time convenient-ga untundi?"
        else:
            prompt = f"What date and time works best for your {srv_label} consultation?"

        history.append({"role": "assistant", "text": prompt})
        session.dialog_history = json.dumps(history)
        db.commit()
        return prompt, True

    # Validate that parsed datetime is strictly in the future
    parsed_dt = datetime.fromisoformat(session.appointment_datetime_iso)
    if parsed_dt <= now:
        session.appointment_datetime_iso = None
        session.step = "awaiting_datetime"
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

    # C. Missing Customer Name
    if not session.customer_name or session.customer_name.startswith("Caller "):
        session.step = "awaiting_name"
        if detected_lang == "ta-IN":
            prompt = "முன்பதிவு செய்ய உங்கள் முழுப் பெயரை கூறுங்கள்?"
        elif detected_lang == "ta-Latn":
            prompt = "Booking confirm panna ungaludaiya full name sollunga please?"
        elif detected_lang == "te-IN":
            prompt = "బుకింగ్ నిర్ధారించడానికి మీ పూర్తి పేరు చెప్పండి?"
        elif detected_lang == "te-Latn":
            prompt = "Booking confirm cheyadaniki mee full name cheppandi please?"
        else:
            prompt = "May I please have your full name for the booking record?"

        history.append({"role": "assistant", "text": prompt})
        session.dialog_history = json.dumps(history)
        db.commit()
        return prompt, True

    # 9. All Entities Present -> Commit Booking via Tool Dispatcher!
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
            db.commit()
            return f"I apologize, but that appointment slot could not be booked ({err_detail}). Please select another time.", True

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

        date_str = format_confirmation_date(parsed_dt, session.language)
        time_str = format_confirmation_time(parsed_dt, session.language)
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
        session.metadata_json = json.dumps({
            "intent": session.intent,
            "detected_language": detected_lang,
            "service_id": session.service_id,
            "service_name": session.service_name,
            "customer_name": session.customer_name,
            "appointment_id": session.booking_id,
            "appointment_time": session.appointment_datetime_iso,
        })

        # Synchronize transcript to existing Call record
        call_rec = db.scalar(select(Call).where(Call.id == session.call_sid))
        if call_rec:
            call_rec.status = "completed"
            call_rec.summary = f"Autonomous voice booking: {srv_name} on {date_str} at {time_str} for {session.customer_name}."
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
