"""Natural AI Receptionist Engine for Vattara Voice Assistance.

Powers human-like conversational intelligence:
- Phase 1: 16 Intent categories classification.
- Phase 2: Natural intermediate question answering mid-booking.
- Phase 3: Tenant-specific business knowledge base (services, hours, staff, FAQs, policies).
- Phase 4: Unrelated question handling with safe general knowledge and polite redirection.
- Phase 5: Medical safety boundaries (emergency triage, non-prescribing).
- Phase 6: Multi-turn conversational context retention across topic switches.
- Phase 7: Natural voice optimization for telephony (no markdown, spoken currency, concise).
- Phase 8: Unknown question handling and human front desk escalation/callbacks.
- Phase 9: Clean modular architecture.
"""

from datetime import date, datetime, timezone
from difflib import SequenceMatcher
import json
import re
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.assistant import AssistantConfig, FAQ, Service
from app.models.business import Business
from app.models.business_hours import BusinessHour
from app.models.conversation_session import ConversationSession
from app.models.staff_schedule import StaffSchedule

logger = get_logger(__name__)

# Medical Emergency Trigger Patterns (English, Tamil, Telugu, Tanglish, Teluglish)
EMERGENCY_PATTERNS = [
    r"\b(?:chest pain|heart attack|cardiac arrest|angina)\b",
    r"\b(?:can'?t breathe|cannot breathe|difficulty breathing|shortness of breath|trouble breathing|gasping|suffocating)\b",
    r"\b(?:unconscious|passed out|fainted|loss of consciousness|unresponsive)\b",
    r"\b(?:stroke|facial droop|slurred speech|sudden numbness|paralysis)\b",
    r"\b(?:heavy bleeding|bleeding heavily|severe hemorrhage|hemorrhage)\b",
    r"\b(?:poison|poisoning|overdose|swallowed chemicals)\b",
    r"\b(?:severe burn|third degree burn|electric shock)\b",
    r"\b(?:choking|airway blocked)\b",
    # Tamil Unicode & Tanglish (expanded with colloquial emergency expressions)
    r"(?:நெஞ்சு வலி|மாரடைப்பு|மூச்சுத் திணறல்|மூச்சு திணறல்|மயக்கம்|மயங்கி|அதிக ரத்தப்போக்கு|வலிப்பு|காக்கா வலிப்பு|ரத்த வாந்தி|சுயநினைவு இன்றி)",
    r"\b(?:nenju vali|maaradippu|moochu thinaral|mayakkam|mayangi|adhiga raththam)\b",
    r"\b(?:nenjula|nenjil|nenju)\b.*?(?:baram|baaram|kanam|vali|tightness|heavy|heaviness)",
    r"\b(?:moochu|swasam)\b.*?(?:vida\s+mudiyala|muttudhu|muttuthu|thinarudhu|thinaral|kastam)",
    r"\b(?:valippu|kaaka\s*valippu|seizure|fits)\b",
    r"\b(?:kai\s*kaal\s*marathupochu|marathu\s*pochu|vaai\s*oru\s*pakkam\s*saayudhu)\b",
    r"\b(?:raththa\s*vaandhi|blood\s*vomiting|bleeding\s*heavily)\b",
    # Telugu Unicode & Teluglish
    r"(?:గుండె నొప్పి|గుండెపోటు|శ్వాస ఆడటం లేదు|శ్వాస తీసుకోవడంలో ఇబ్బంది|స్పృహ తప్పి|రక్తస్రావం)",
    r"\b(?:gunde noppi|gundepotu|oopiri aadatledu|spruha thappi|rakthasravam)\b",
]

# Medical Advice / Prescribing Inquiry Patterns
MEDICAL_ADVICE_PATTERNS = [
    r"\b(?:what (?:medicine|tablet|pill|syrup|drug|dose|dosage) (?:should i|can i|to) (?:take|give|use))\b",
    r"\b(?:what (?:dose|dosage) of)\b",
    r"\b(?:how much (?:dose|dosage|paracetamol|mg|medicine))\b",
    r"\b(?:how many (?:tablets|pills) (?:should i|can i) take)\b",
    r"\b(?:prescribe|prescription|which tablet|which medicine)\b",
    r"\b(?:can you give me (?:medicine|tablets|drugs|antibiotics))\b",
    r"\b(?:cure .*? permanently)\b",
    r"(?:என்ன மாத்திரை சாப்பிட வேண்டும்|மருந்து பரிந்துரைக்க முடியுமா|மருந்து பெயர்)",
    r"(?:ye mandhu vaadali|tablet cheppandi|ye tablet veyyali)",
]

# Unrelated / General Knowledge Patterns
GENERAL_KNOWLEDGE_QUESTIONS: dict[str, dict[str, str]] = {
    "prime_minister": {
        "en": "The Prime Minister of India is Narendra Modi. How can I assist you with your clinic appointment or inquiry today?",
        "ta": "இந்தியாவின் பிரதமர் நரேந்திர மோடி அவர்கள். எங்கள் மருத்துவமனை முன்பதிவு அல்லது விவரங்களுக்கு நான் எவ்வாறு உதவ வேண்டும்?",
        "te": "భారత ప్రధాని నరేంద్ర మోదీ గారు. మా క్లినిక్ అపాయింట్‌మెంట్ లేదా సేవల గురించి మీకు ఎలా సహాయపడగలను?",
        "ta_latn": "India-vin Prime Minister Narendra Modi avargal. Ungalukku clinic appointment book panna eppadi udhava mudiyum?",
        "te_latn": "India Prime Minister Narendra Modi garu. Meeku clinic appointment kosam ela sahayam cheyagalanu?",
    },
    "president": {
        "en": "The President of India is Droupadi Murmu. How can I help you with our clinic services today?",
        "ta": "இந்தியாவின் குடியரசுத் தலைவர் திரௌபதி முர்மு அவர்கள். எங்கள் மருத்துவ ஆலோசனைக்கு எவ்வாறு உதவலாம்?",
        "te": "భారత రాష్ట్రపతి ద్రౌపది ముర్ము గారు. మా క్లినిక్ సేవలపై మీకు ఎలా సహాయపడగలను?",
        "ta_latn": "India-vin President Droupadi Murmu avargal. Clinic services-ku eppadi udhava mudiyum?",
        "te_latn": "India President Droupadi Murmu garu. Clinic services kosam ela sahayam cheyali?",
    },
    "ai_definition": {
        "en": "Artificial intelligence refers to computer systems engineered to perform tasks that typically require human reasoning, such as understanding speech and scheduling appointments. How may I assist you with our clinic today?",
        "ta": "செயற்கை நுண்ணறிவு (AI) என்பது மனிதர்களைப் போல சிந்தித்து செயல்படும் கணினி தொழில்நுட்பமாகும். இன்று எங்கள் மருத்துவ சேவைகளில் உங்களுக்கு எவ்வாறு உதவ வேண்டும்?",
        "te": "కృత్రిమ మేధస్సు (AI) అనేది మానవ మేధస్సు అవసరమయ్యే పనులను కంప్యూటర్ల ద్వారా చేయించే సాంకేతికత. మా క్లినిక్ సేవలలో మీకు ఎలా సహాయపడగలను?",
        "ta_latn": "Artificial Intelligence (AI) enbathu human intelligence maadhiri pesavum purinjukavum koodiya computer technology. Clinic-la eppadi help pannanum?",
        "te_latn": "Artificial Intelligence (AI) ante human intelligence tho computer pani chese technology. Clinic-lo ela help cheyali?",
    },
    "joke": {
        "en": "Why did the doctor carry a red pen? In case they needed to draw blood! Now, how can I assist you with your clinic visit today?",
        "ta": "மருத்துவர் ஏன் எப்போதும் சிகப்பு பேனாவை வைத்திருக்கிறார்? ரத்தப் பரிசோதனை சீட்டு எழுதத்தான்! இன்று உங்களுக்கு மருத்துவ ஆலோசனை பதிவு செய்யவா?",
        "te": "డాక్టర్ ఎప్పుడూ రెడ్ పెన్ ఎందుకు పెట్టుకుంటారు? బ్లడ్ టెస్ట్ రాయడానికి! మా క్లినిక్ సేవలలో మీకు ఎలా సహాయపడగలను?",
        "ta_latn": "Doctor yen red pen vechirukaaru? Blood test ezhudhadhaan! Clinic visit-ku eppadi help pannanum?",
        "te_latn": "Doctor enduku red pen pettukuntaru? Blood test rayadaniki! Clinic visit kosam ela sahayam cheyali?",
    },
    "capital_france": {
        "en": "The capital of France is Paris. How can I help you with your clinic appointment today?",
        "ta": "பிரான்ஸ் நாட்டின் தலைநகரம் பாரிஸ். எங்கள் மருத்துவமனை அப்பாயிண்ட்மென்ட்க்கு எவ்வாறு உதவலாம்?",
        "te": "ఫ్రాన్స్ రాజధాని ప్యారిస్. మా క్లినిక్ అపాయింట్‌మెంట్ కోసం మీకు ఎలా సహాయపడగలను?",
        "ta_latn": "France capital Paris. Ungalukku clinic appointment-ku eppadi help pannanum?",
        "te_latn": "France capital Paris. Meeku clinic appointment kosam ela sahayam cheyali?",
    },
    "capital_india": {
        "en": "The capital of India is New Delhi. How can I assist you with your medical consultation today?",
        "ta": "இந்தியாவின் தலைநகரம் புது தில்லி. இன்று உங்கள் மருத்துவ ஆலோசனைக்கு எவ்வாறு உதவ முடியும்?",
        "te": "భారత రాజధాని న్యూఢిల్లీ. మీ వైద్య సంప్రదింపులకు ఎలా సహాయపడగలను?",
        "ta_latn": "India capital New Delhi. Ungal medical appointment-ku eppadi udhava mudiyum?",
        "te_latn": "India capital New Delhi. Mee medical consultation kosam ela sahayam cheyali?",
    },
    "weather": {
        "en": "I do not have real-time weather reports, but I am ready to help you with clinic hours and appointments. How can I assist you?",
        "ta": "வானிலை தகவல்கள் என்னிடம் இல்லை, ஆனால் மருத்துவ ஆலோசனை மற்றும் நேரங்களுக்கு நான் உதவ முடியும். எவ்வாறு உதவ வேண்டும்?",
        "te": "వాతావరణ వివరాలు నా వద్ద లేవు, కానీ క్లినిక్ వేళలు మరియు అపాయింట్‌మెంట్‌ల గురించి సహాయపడగలను. మీకు ఎలా సహాయపడాలి?",
        "ta_latn": "Weather updates ennoda system-la illa, but clinic appointment-ku help panna mudiyum. Eppadi help pannanum?",
        "te_latn": "Weather updates levu, kani clinic appointment kosam sahayam cheyagalanu. Ela help cheyali?",
    },
}


def format_spoken_response(text: str) -> str:
    """Format textual response into clean, natural spoken telephony dialogue.

    - Expands abbreviations and titles (Dr. -> Doctor, Appt -> Appointment).
    - Converts symbols to natural spoken words (e.g. ₹700 -> 700 rupees).
    - Normalizes 24-hr/redundant zeroes in spoken time (10:00 AM -> 10 AM).
    - Detaches hyphenated Tanglish colloquial particles (available-ah -> available ah, clinic-la -> clinic la)
      so Sarvam Bulbul v4 Flash pronounces both English and Tamil words smoothly without clipping.
    - Strips markdown formatting, HTML tags, and trailing whitespace.
    - Cleans punctuation for natural conversational pauses and prosody.
    """
    if not text:
        return ""

    # 1. Expand common medical & receptionist titles and abbreviations before stripping punctuation
    cleaned = re.sub(r"\bDr\.\s*", "Doctor ", text)
    cleaned = re.sub(r"\bDr\b(?=\s+[A-Z])", "Doctor", cleaned)
    cleaned = re.sub(r"\bAppt\.?\b", "Appointment", cleaned)
    cleaned = re.sub(r"\bPh:\s*|\bPhone:\s*", "phone ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bNo\.?\s*(\d+)", r"number \1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bID:\s*", "ID ", cleaned)

    # 2. Replace currency symbols with spoken words
    cleaned = re.sub(r"₹\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:/[-–—]*)?", r"\1 rupees", cleaned)
    cleaned = re.sub(r"Rs\.?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:/[-–—]*)?", r"\1 rupees", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(\d+)\s*/[-–—]*\b", r"\1 rupees", cleaned)
    cleaned = re.sub(r"\brupees\s*/[-–—]*", "rupees", cleaned, flags=re.IGNORECASE)

    # 3. Spoken time normalization (10:00 AM -> 10 AM, 10:00 -> 10)
    cleaned = re.sub(r"\b(\d{1,2}):00\s*(AM|PM|am|pm)\b", r"\1 \2", cleaned)
    cleaned = re.sub(r"\b(\d{1,2}):00\b", r"\1", cleaned)

    # 4. Detach Tanglish colloquial suffix particles joined with hyphens (e.g. available-ah -> available ah)
    cleaned = re.sub(
        r"\b([a-zA-Z]+)-(ah|la|ku|oda|va|ne|dhan|kitta|ga)\b",
        r"\1 \2",
        cleaned,
        flags=re.IGNORECASE,
    )

    # 4b. Space out medical acronyms and lab tests for crystal-clear telephony TTS pronunciation
    cleaned = re.sub(r"\bHbA1c\b|\bHBA1C\b|\bhba1c\b", "H b A 1 c", cleaned)
    cleaned = re.sub(r"\bECG\b|\bEcg\b", "E C G", cleaned)
    cleaned = re.sub(r"\bCBC\b|\bCbc\b", "C B C", cleaned)
    cleaned = re.sub(r"\bBP\b|\bB\.P\.\b", "B P", cleaned)
    cleaned = re.sub(r"\bORS\b", "O R S", cleaned)
    cleaned = re.sub(r"\bFBS\b", "F B S", cleaned)
    cleaned = re.sub(r"\bPPBS\b", "P P B S", cleaned)
    cleaned = re.sub(r"\bTSH\b", "T S H", cleaned)
    cleaned = re.sub(r"\bMRI\b", "M R I", cleaned)
    cleaned = re.sub(r"\bCT\s*scan\b", "C T scan", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bICU\b", "I C U", cleaned)
    cleaned = re.sub(r"\b(\d+)\s*mg\b", r"\1 milligrams", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(\d+)\s*ml\b", r"\1 millilitres", cleaned, flags=re.IGNORECASE)

    # 5. Strip markdown bold/italic
    cleaned = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", cleaned)
    cleaned = re.sub(r"_{1,3}(.*?)_{1,3}", r"\1", cleaned)

    # Strip markdown headers (#, ##)
    cleaned = re.sub(r"^\s*#{1,6}\s*", "", cleaned, flags=re.MULTILINE)

    # Strip list bullets (*, -, +)
    cleaned = re.sub(r"^\s*[\*\-\+]\s+", "", cleaned, flags=re.MULTILINE)

    # Strip code backticks
    cleaned = re.sub(r"`(.*?)`", r"\1", cleaned)

    # Strip HTML tags
    cleaned = re.sub(r"<[^>]+>", "", cleaned)

    # 6. Prosody & pause smoothing for telephony TTS
    cleaned = re.sub(r"[\u2014\u2013]", ", ", cleaned)  # em-dash and en-dash
    cleaned = re.sub(r"\s*--\s*", ", ", cleaned)
    cleaned = re.sub(r"\.{3,}", ", ", cleaned)  # ellipses to natural pause
    cleaned = re.sub(r"[\"']", "", cleaned)  # strip quotation marks that cause hesitation

    # Clean redundant whitespaces
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\s*,\s*", ", ", cleaned)
    cleaned = re.sub(r"\s*\.\s*", ". ", cleaned)
    cleaned = re.sub(r"\n+", " ", cleaned).strip()

    return cleaned


def check_medical_emergency(text: str) -> bool:
    """Determine whether the caller is expressing an acute medical emergency."""
    if not text:
        return False
    lower = text.lower()
    for pattern in EMERGENCY_PATTERNS:
        if re.search(pattern, lower, re.IGNORECASE):
            return True
    return False


def check_medical_advice_request(text: str) -> bool:
    """Determine whether the caller is asking the AI to diagnose or prescribe medicines."""
    if not text:
        return False
    lower = text.lower()
    for pattern in MEDICAL_ADVICE_PATTERNS:
        if re.search(pattern, lower, re.IGNORECASE):
            return True
    return False


def has_symptom_or_illness(text: str) -> bool:
    """Check if the caller is reporting medical symptoms, pain, illness, or feeling unwell."""
    if not text:
        return False
    lower = text.lower()
    symptom_patterns = [
        # English symptoms & illness expressions
        r"\b(?:not\s+feeling\s+well|not\s+well|not\s+fine|unwell|sick|ill|headache|fever|cough|cold|stomach\s+ache|stomach\s+pain|chest\s+pain|body\s+pain|joint\s+pain|throat\s+pain|back\s+pain|vomiting|dizziness|infection|injury)\b",
        # Tamil & Tanglish symptoms & illness expressions
        r"\b(?:odambu\s+seri\s+illa|odambu\s+sari\s+illa|udambu\s+mudiyala|odambu\s+mudiyala|udambu\s+seri\s+illa|seri\s+illa|sari\s+illa|mudiyala|mudila)\b",
        r"\b(?:thala\s*vali|thalavali|kaachal|sali|irumal|valikudhu|valikuthu|vali|vayiru\s*vali|nenju\s*vali|mutti\s*vali)\b",
        r"(?:உடம்பு\s*சரியில்லை|உடம்பு\s*முடியல|தலைவலி|காய்ச்சல்|சளி|இருமல்|வலி|வயிற்று\s*வலி|நெஞ்சு\s*வலி)",
        # Telugu & Teluglish symptoms & illness expressions
        r"\b(?:ontlo\s*bagoledu|bagoledhu|thala\s*noppi|thalanoppi|jwaram|daggu|jalubu|noppi|kadupu\s*noppi|gunde\s*noppi)\b",
        r"(?:ఒంట్లో\s*బాగోలేదు|తలనోప్పి|జ్వరం|దగ్గు|జలుబు|నొప్పి|బాధ)",
    ]
    for pat in symptom_patterns:
        if re.search(pat, lower, re.IGNORECASE):
            return True
    return False


def is_conversational_recovery(text: str) -> bool:
    """Check if the caller is asking whether the assistant is listening, audible, or on the line."""
    if not text:
        return False
    lower = text.lower().strip().rstrip(".,?!")
    patterns = [
        r"\b(?:are\s+you\s+there|can\s+you\s+hear\s+me|am\s+i\s+audible|hello\s+hello|is\s+anyone\s+there|you\s+there|still\s+there)\b",
        r"\b(?:pesuradhu\s+kekudha|pesurathu\s+kekudha|kekudha|kekudhaa|line-la\s+irukingala|line\s+la\s+irukingala)\b",
        r"(?:கேட்கிறதா|லைனில்\s*இருக்கிறீர்களா|பேசுவது\s*கேட்கிறதா)",
        r"\b(?:vinapadutonda|vinapaduthundha|line-lo\s+unnara|line\s+lo\s+unnara)\b",
        r"(?:వినపడుతోందా|లైన్‌లో\s*ఉన్నారా|మాట్లాడేది\s*వినపడుతోందా)",
    ]
    for pat in patterns:
        if re.search(pat, lower, re.IGNORECASE):
            return True
    return False


def is_hold_or_pause_request(text: str) -> bool:
    """Check if the caller is asking for a pause, hold, or waiting moment."""
    if not text:
        return False
    lower = text.lower().strip().rstrip(".,?!")
    # Medical emergencies and symptoms take strict priority and must never be classified as a hold request
    if check_medical_emergency(lower) or has_symptom_or_illness(lower):
        return False
    # If the user speaks a longer sentence (> 5 words), it is a query or statement, not a hold request
    words = lower.split()
    if len(words) > 5 and not any(p in lower for p in ["konjam wait", "please wait", "give me a minute", "give me a second", "wait a minute"]):
        return False
    patterns = [
        r"\b(?:wait\s+a\s+minute|wait\s+a\s+second|wait\s+please|please\s+wait|hold\s+on|just\s+a\s+second|just\s+a\s+sec|one\s+second|one\s+sec|one\s+minute|give\s+me\s+a\s+second|give\s+me\s+a\s+minute)\b",
        r"^(?:wait|hold)$",
        r"\b(?:oru\s+nimisham|oru\s+second|konjam\s+irunga|konjam\s+wait\s+pannunga|wait\s+pannunga)\b",
        r"(?:ஒரு\s*நிமிடம்|ஒரு\s*நிமிஷம்|காத்திருங்கள்|கொஞ்சம்\s*இருங்க)",
        r"\b(?:okka\s+nimisham|okka\s+second|aagandi|wait\s+cheyandi)\b",
        r"(?:ఒక్క\s*నిమిషం|ఆగండి|వేచి\s*ఉండండి)",
    ]
    for pat in patterns:
        if re.search(pat, lower, re.IGNORECASE):
            return True
    return False


def match_unrelated_general_query(text: str) -> str | None:
    """Match caller questions against safe, common general knowledge queries."""
    if not text:
        return None
    lower = text.lower()

    if any(k in lower for k in ["prime minister", "pm of india", "who is narendra modi", "பிரதமர் யார்", "பிரதமர்", "ప్రధాని ఎవరు"]):
        return "prime_minister"
    if any(k in lower for k in ["president of india", "who is president", "குடியரசுத் தலைவர்", "రాష్ట్రపతి ఎవరు"]):
        return "president"
    if any(k in lower for k in ["what is ai", "what is artificial intelligence", "what does ai mean", "செயற்கை நுண்ணறிவு", "కృత్రిమ మేధస్సు"]):
        return "ai_definition"
    if any(k in lower for k in ["tell me a joke", "say a joke", "make me laugh", "ஒரு ஜோக் சொல்லுங்க", "జోక్ చెప్పండి"]):
        return "joke"
    if any(k in lower for k in ["capital of france", "france capital"]):
        return "capital_france"
    if any(k in lower for k in ["capital of india", "india capital", "இந்தியாவின் தலைநகரம்", "భారత రాజధాని"]):
        return "capital_india"
    if any(k in lower for k in ["what is the weather", "how is the weather", "rain today", "வானிலை எப்படி", "వాతావరణం ఎలా ఉంది"]):
        return "weather"

    return None


def get_emergency_response(language: str, business: Business) -> str:
    """Generate emergency triage advice without forcing appointment booking."""
    phone = business.phone or "our emergency desk"
    if language.startswith("ta"):
        if language == "ta-Latn":
            return format_spoken_response(
                f"Severe chest pain, moochu thinaral illa emergency symptoms irundha udane 108 ambulance-ku "
                f"call pannunga, illa kitta irukkura hospital emergency room-ku ponga. "
                f"Unga safety romba mukkiyam. Emergency help-ku {business.name} helpline: {phone}."
            )
        return format_spoken_response(
            f"நெஞ்சு வலி அல்லது மூச்சுத் திணறல் போன்ற தீவிர அறிகுறிகள் இருந்தால், உடனடியாக 108 அவசர சிகிச்சை "
            f"வாகனத்தை அழைக்கவும் அல்லது அருகில் உள்ள அவசர சிகிச்சைப் பிரிவுக்குச் செல்லவும். "
            f"உங்கள் நலம் மிக முக்கியம். எங்கள் அவசர உதவி எண்: {phone}."
        )
    elif language.startswith("te"):
        if language == "te-Latn":
            return format_spoken_response(
                f"Gunde noppi, oopiri aadaka povadam emergency aavochu. Ventane 108 ambulance-ku call cheyandi, "
                f"leda daggarloni emergency hospital-ki vellandi. "
                f"Mee safety chala mukhyam. Ma emergency number: {phone}."
            )
        return format_spoken_response(
            f"గుండె నొప్పి లేదా శ్వాస తీసుకోవడంలో తీవ్రమైన ఇబ్బంది ఉంటే, దయచేసి వెంటనే 108 అత్యవసర నంబర్‌కు "
            f"కాల్ చేయండి లేదా సమీపంలోని ఆసుపత్రి ఎమర్జెన్సీ విభాగానికి వెళ్లండి. "
            f"మీ ప్రాణ రక్షణ ముఖ్యం. మా సహాయక నంబర్: {phone}."
        )
    return format_spoken_response(
        f"If you or the patient are experiencing severe symptoms like chest pain, difficulty breathing, "
        f"or sudden numbness, please immediately call 108 or your local emergency services, or proceed to the nearest emergency room. "
        f"Your safety is paramount. You can also reach our clinic emergency desk at {phone}."
    )


def get_medical_advice_boundary_response(
    language: str,
    user_query: str = "",
    business: Business | None = None,
) -> str:
    """Enforce ethical boundary with grounded medical knowledge: Educate safely, never prescribe, and route to clinic doctor."""
    if user_query:
        try:
            from app.services.ai.medical_knowledge import (
                get_medical_guidance_for_response,
                query_medical_knowledge,
            )

            topic = query_medical_knowledge(user_query, language)
            if topic:
                guidance = get_medical_guidance_for_response(topic, language)
                explanation = guidance.get("explanation", "")
                home_care = guidance.get("home_care", "")
                if language.startswith("ta"):
                    if language == "ta-Latn":
                        resp = f"{explanation} {home_care} Doctor kitta proper checkup panna appointment book pannidava?"
                    else:
                        resp = f"{explanation} {home_care} முறையான பரிசோதனைக்கு எங்கள் மருத்துவரிடம் அப்பாயிண்ட்மெண்ட் பதிவு செய்யவா?"
                elif language.startswith("te"):
                    if language == "te-Latn":
                        resp = f"{explanation} {home_care} Doctor tho proper checkup kosam appointment book cheyamantara?"
                    else:
                        resp = f"{explanation} {home_care} సరైన పరీక్ష కోసం మా వైద్యులను సంప్రదించడానికి అపాయింట్‌మెంట్ బుక్ చేయమంటారా?"
                else:
                    resp = f"{explanation} {home_care} I recommend an in-person consultation with our doctor for proper diagnosis. Would you like to schedule an appointment?"
                return format_spoken_response(resp)
        except Exception as e:
            logger.warning("Error querying medical knowledge in boundary response: %s", e)

    if language.startswith("ta"):
        if language == "ta-Latn":
            return format_spoken_response(
                "Naan AI receptionist enbadhala direct-ah prescription thara mudiyadhu. "
                "Safe treatment-ku namma doctor kitta consult panna appointment book panna kattuma?"
            )
        return format_spoken_response(
            "நான் ஒரு AI வரவேற்பாளர் என்பதால் நேரடி மருத்துவ சிகிச்சையோ மாத்திரைகளோ பரிந்துரைக்க இயலாது. "
            "எங்கள் மருத்துவரிடம் முழுமையான பரிசோதனை பெற அப்பாயிண்ட்மெண்ட் பதிவு செய்யவா?"
        )
    elif language.startswith("te"):
        if language == "te-Latn":
            return format_spoken_response(
                "Nenu AI receptionist kabatti direct-ga mandhulu suggest cheyalenu. "
                "Ma doctor tho consultation kosam appointment book cheyamantara?"
            )
        return format_spoken_response(
            "నేను AI రిసెప్షనిస్ట్‌ని మాత్రమే, కాబట్టి నేరుగా మందులు లేదా చికిత్సను సూచించలేను. "
            "మా వైద్యులను సంప్రదించడానికి అపాయింట్‌మెంట్ బుక్ చేయమంటారా?"
        )
    return format_spoken_response(
        "I am an AI receptionist, so I cannot diagnose medical conditions or prescribe medications over the phone. "
        "I would be glad to help you schedule an appointment with one of our qualified doctors for a proper consultation. "
        "Would you like to book an appointment?"
    )


def retrieve_tenant_knowledge(db: Session, business: Business) -> dict[str, Any]:
    """Retrieve tenant-specific knowledge base data strictly scoped to business_id.

    Zero cross-tenant leakage. Returns active services, business hours, doctors, FAQs, and policies.
    """
    # 1. Services
    services = db.scalars(
        select(Service).where(Service.business_id == business.id, Service.is_active.is_(True))
    ).all()

    # 2. Operating Hours
    b_hours = db.scalars(
        select(BusinessHour).where(BusinessHour.business_id == business.id).order_by(BusinessHour.day_of_week.asc())
    ).all()

    # 3. Staff / Doctors
    staff = db.scalars(
        select(StaffSchedule).where(StaffSchedule.business_id == business.id, StaffSchedule.is_active.is_(True))
    ).all()

    # 4. FAQs
    faqs = db.scalars(
        select(FAQ).where(FAQ.business_id == business.id, FAQ.is_active.is_(True))
    ).all()

    # 5. Assistant Config
    cfg = business.assistant_config

    return {
        "business_name": business.name,
        "address": business.address or "our main clinic location",
        "phone": business.phone,
        "email": business.email,
        "services": list(services),
        "business_hours": list(b_hours),
        "staff_schedules": list(staff),
        "faqs": list(faqs),
        "working_hours_text": cfg.working_hours if cfg and cfg.working_hours else None,
        "fallback_number": cfg.fallback_number if cfg and cfg.fallback_number else business.phone,
    }


def find_matching_faq(query_text: str, faqs: list[FAQ]) -> FAQ | None:
    """Find most relevant active FAQ entry for a caller question using token and fuzzy overlap."""
    if not query_text or not faqs:
        return None

    clean_query = re.sub(r"[^\w\s\u0B80-\u0BFF\u0C00-\u0C7F]", " ", query_text.lower()).strip()
    words = [w for w in clean_query.split() if len(w) >= 3]
    if not words:
        return None

    best_faq: FAQ | None = None
    best_score = 0.0

    for faq in faqs:
        if not faq.question or not faq.answer:
            continue
        clean_q = re.sub(r"[^\w\s\u0B80-\u0BFF\u0C00-\u0C7F]", " ", faq.question.lower()).strip()
        clean_cat = re.sub(r"[^\w\s\u0B80-\u0BFF\u0C00-\u0C7F]", " ", (faq.category or "").lower()).strip()

        # Token match score
        matches = sum(1 for w in words if w in clean_q or w in clean_cat)
        ratio = SequenceMatcher(None, clean_query, clean_q).ratio()

        composite_score = matches * 1.5 + ratio
        if composite_score > best_score and (matches >= 2 or ratio >= 0.65):
            best_score = composite_score
            best_faq = faq

    return best_faq


def _matches_any_keyword(text: str, keywords: list[str]) -> bool:
    """Helper to match keywords respecting word boundaries for Latin and substring for Indic scripts."""
    for k in keywords:
        if re.search(r"[\u0B80-\u0BFF\u0C00-\u0C7F]", k):
            if k in text:
                return True
        else:
            if re.search(r"\b" + re.escape(k) + r"\b", text, re.IGNORECASE):
                return True
    return False


def classify_natural_receptionist_intent(
    text: str,
    session: ConversationSession | None = None,
    business: Business | None = None,
) -> tuple[str, dict[str, Any]]:
    """Intelligently classify caller utterance across 16 receptionist intents.

    Returns:
        tuple[intent_name, intent_metadata]
    """
    if not text:
        return "unknown", {}

    lower = text.lower().strip()

    # 1. Medical Emergency (Highest Priority Safety Check)
    if check_medical_emergency(lower):
        return "medical_emergency", {}

    # 2. Medical Advice / Prescription request
    if check_medical_advice_request(lower):
        return "medical_advice_request", {}

    # 3. Conversational Recovery (are you there / can you hear me)
    if is_conversational_recovery(lower):
        return "conversational_recovery", {}

    # 4. Hold / Pause request (one minute / wait a second)
    if is_hold_or_pause_request(lower):
        return "hold_request", {}

    # 5. Symptom / Illness Report (High Priority: Reporting illness maps to doctor consultation, NEVER confirmation)
    if has_symptom_or_illness(lower):
        return "booking", {"symptom": True}

    # 6. Unrelated General Knowledge Query
    gen_key = match_unrelated_general_query(lower)
    if gen_key:
        return "unrelated_general_knowledge", {"key": gen_key}

    # 4. Pricing / Fee Inquiry (e.g. "How much is pediatric checkup?", "Cost of cardiology")
    pricing_keywords = [
        "how much", "cost", "price", "pricing", "fee", "fees", "rate", "charges",
        "expensive", "charge", "எவ்வளவு", "கட்டணம்", "விலை", "fees evvalavu",
        "evlo", "evvalavu", "fees evlo", "consultation fees evlo", "rate evlo", "cost evlo",
        "ధర ఎంత", "ఫీజు ఎంత", "ఖర్చు ఎంత", "cost entha", "fees entha"
    ]
    if _matches_any_keyword(lower, pricing_keywords):
        return "pricing_inquiry", {}

    # 5. Payment Methods Inquiry
    payment_keywords = [
        "payment", "pay", "mode of payment", "payment methods", "accept cash", "credit card", "debit card",
        "upi", "google pay", "gpay", "phonepe", "paytm", "insurance", "cashless", "tpa",
        "பணம்", "பணம் செலுத்தும்", "பேமெண்ட்", "డబ్బులు", "చెల్లింపు", "పేమెంట్"
    ]
    if _matches_any_keyword(lower, payment_keywords):
        return "payment_methods_inquiry", {}

    # 6. Doctor / Practitioner Inquiry (Doctor qualifications / who are the doctors)
    doctor_keywords = [
        "which doctor", "which doctors", "who is the doctor", "who are the doctors", "doctor name",
        "list of doctors", "pediatrician name",
        "who is the cardiologist", "who is the pediatrician",
        "is dr", "is doctor", "is doctor available", "doctor available-ah",
        "doctor irukaangala", "doctor irukangala", "doctor irukaara", "doctor irukara",
        "doctor iruka", "doctor irukka", "doctor eppo varuvaaru", "doctor eppo irupaaru",
        "specialist", "practitioner", "physician name",
        "மருத்துவர் யார்", "டாக்டர் பெயர்", "எந்த டாக்டர்", "மருத்துவர் விவரங்கள்", "டாக்டர் விவரங்கள்",
        "டாக்டர் இருக்கிறாரா", "டாக்டர் இருக்காங்களா",
        "డాక్టర్ ఎవరు", "ఏ డాక్టర్", "వైద్యుల వివరాలు"
    ]
    if _matches_any_keyword(lower, doctor_keywords):
        has_rel_date = any(k in lower for k in ["tomorrow", "நாளை", "naalaiku", "naalai", "naalaiki", "repu", "today", "இன்று", "inniku", "iniku"])
        if not has_rel_date:
            return "doctor_staff_inquiry", {}

    # 7. Customer Complaint Inquiry
    complaint_keywords = [
        "complaint", "file a complaint", "bad service", "rude", "poor service", "long waiting",
        "waited too long", "waste of time", "dissatisfied", "angry", "unhappy",
        "புகார்", "மோசமான சேவை", "ఫిర్యాదు"
    ]
    if _matches_any_keyword(lower, complaint_keywords):
        return "complaint_inquiry", {}

    # 8. General Clinic Information (Parking, Pharmacy, Wheelchair, Facilities)
    facility_keywords = [
        "parking", "car parking", "pharmacy", "medical shop", "lab", "laboratory", "wheelchair",
        "facilities", "amenities", "wifi", "cafeteria", "canteen", "about the clinic",
        "பார்ஸ்", "பார்ங்கிங்", "மருந்தகம்", "పార్కింగ్", "ఫార్మసీ"
    ]
    if _matches_any_keyword(lower, facility_keywords):
        return "general_clinic_info", {}

    # 9. Business Address Inquiry
    address_keywords = [
        "where are you located", "where is the clinic", "where is the hospital", "what is your address",
        "clinic address", "hospital address", "address", "location", "hospital location", "clinic location",
        "where is your clinic", "where is your office", "directions", "how to reach",
        "location enga irukku", "location enga", "enga irukku", "enga iruku", "engirukku", "engae", "address sollunga", "address enna",
        "clinic enga irukku", "hospital enga irukku",
        "எங்கே உள்ளது", "முகவரி",
        "ఎక్కడ ఉంది", "చిరునామా", "ekkada undi", "address cheppandi"
    ]
    if _matches_any_keyword(lower, address_keywords):
        return "business_inquiry_address", {}

    # 10. Business Operating Hours Inquiry
    hours_keywords = [
        "working hours", "timings", "opening hours", "when are you open", "what time do you open",
        "open on sunday", "open today", "clinic timings", "operating hours", "business hours",
        "when does the clinic open", "what time does the clinic open",
        "வேலை நேரம்", "திறந்திருக்கும் நேரம்", "திறக்கும் நேரம்", "எத்தனை மணிக்கு திறக்கும்", "எப்போது திறக்கும்", "திறக்கும்", "மூடும் நேரம்",
        "opening time", "closing time", "sunday open", "ethana maniki thirakkum", "clinic open time",
        "పనిచేసే సమయం", "వేళలు", "timings enti", "sunday open", "eppudu therustharu", "eppudu open"
    ]
    if _matches_any_keyword(lower, hours_keywords):
        return "business_inquiry_hours", {}

    # 11. Services Available Inquiry
    services_keywords = [
        "what services", "list of services", "all services", "what treatments", "what do you provide",
        "what do you offer", "specialities", "services available", "available services",
        "என்ன சேவைகள்", "என்னென்ன சிகிச்சைகள்", "services enna", "services enti", "ye services unnayi"
    ]
    if _matches_any_keyword(lower, services_keywords):
        return "business_inquiry_services", {}

    # 12. Check Existing Appointment
    existing_keywords = [
        "check my appointment", "check appointment", "do i have an appointment",
        "do i have an upcoming appointment", "upcoming appointment", "have an appointment",
        "have any appointment", "my upcoming appointment",
        "existing appointment", "my appointment details", "when is my appointment",
        "status of my appointment", "check my booking", "enquire appointment",
        "appointment iruka", "appointment eppo", "ennoda appointment",
        "முன்பதிவு இருக்கிறதா", "என் முன்பதிவு", "முன்பதிவு நிலை",
        "appointment undha", "naa appointment", "eppudu appointment",
        "అపాయింట్‌మెంట్ ఉందా", "నా అపాయింట్‌మెంట్", "అపాయింట్‌మెంట్ వివరాలు",
    ]
    if _matches_any_keyword(lower, existing_keywords):
        return "check_existing_appointment", {}

    # 13. Cancellation of Appointment
    cancel_keywords = [
        "cancel appointment", "cancel my appointment", "appointment cancel",
        "drop appointment", "ரத்து", "முன்பதிவை ரத்து", "ரத்து செய்",
        "cancel pannanum", "appointment-ai cancel",
        "రద్దు", "రద్దు చేయండి", "అపాయింట్‌మెంట్ రద్దు",
        "cancel cheyandi", "raddhu cheyandi", "cancel cheyali", "appointment-ni cancel",
    ]
    if _matches_any_keyword(lower, cancel_keywords):
        return "cancel_appointment", {}

    # 14. Rescheduling of Appointment
    resched_keywords = [
        "reschedule", "change time", "change date", "postpone", "prepone",
        "மாற்ற வேண்டும்", "நேரத்தை மாற்ற", "தேதியை மாற்ற",
        "mathanum", "maathanum", "reschedule pannanum", "appointment matha",
        "మార్చండి", "సమయం మార్చండి", "తేదీ మార్చండి",
        "marchandi", "change cheyandi", "reschedule cheyandi", "time marchali", "date marchali",
    ]
    if _matches_any_keyword(lower, resched_keywords):
        return "reschedule_appointment", {}

    # 15. Check Availability / Slots
    avail_keywords = [
        "slots", "available", "availability", "when can i", "is doctor available", "doctor available",
        "free slots", "open slots", "is the doctor there", "doctor availability", "doctors available",
        "doctor eppo available", "eppo available", "doctor eppo irupaaru", "doctor eppo irupaanga",
        "naalaiku morning slot irukka", "morning slot irukka", "morning slot iruka", "evening slot irukka", "afternoon slot irukka",
        "slot irukka", "slots irukka", "slot iruka", "slots iruka", "slot irukku", "slots irukku",
        "நேரம் இருக்கிறதா", "நேரம் இருக்குமா", "எப்போது கிடைக்கும்", "டாக்டர் இருக்கிறாரா", "மருத்துவர் இருக்கிறாரா",
        "டாக்டர் இருப்பாரா", "மருத்துவர் இருப்பாரா", "டாக்டர் எப்போது வருவார்",
        "கிடைக்குமா", "appointment கிடைக்குமா", "slot கிடைக்குமா",
        "neram iruka", "neram irukka", "available-ah", "eppo varalam",
        "time irukka", "time iruka", "time irukkuma", "time kidaikuma", "morning la time irukka", "morning time irukka", "morning time iruka", "kaalaila time irukka",
        "doctor irukaara", "doctor irukangala", "doctor available-ah",
        "kidaikuma", "kedaikuma", "appointment kidaikuma", "slot kidaikuma", "slots kidaikuma",
        "స్లాట్లు ఉన్నాయా", "సమయం ఉందా", "ఎప్పుడు రావచ్చు", "డాక్టర్ ఉన్నారా",
        "slots unnaya", "time undha", "eppudu raavachu", "available undha", "doctor unnara",
    ]
    if _matches_any_keyword(lower, avail_keywords):
        return "check_availability", {}

    # 16. Goodbye / Exit
    exit_keywords = [
        "bye", "goodbye", "exit", "nevermind", "no thanks",
        "don't want", "dont want", "வேண்டாம்", "போதும்",
        "vendam", "podhum", "mudikalam", "call cut",
        "வద్దు", "vaddu", "vaddhu", "చాలు", "chalu", "chalamma",
        "undandi", "call cut cheyandi", "வேண்டாம் நன்றி", "நன்றி வேண்டாம்",
    ]
    if _matches_any_keyword(lower, exit_keywords):
        return "cancellation", {}

    # 17. Denial keywords (checked BEFORE confirmation because "don't confirm" contains "confirm")
    denial_keywords = [
        "no don't", "no dont", "dont confirm", "don't confirm", "do not confirm",
        "no that's wrong", "not now", "no do not", "cancel it", "don't book", "dont book",
        "no", "வேண்டாம்", "வద్దు", "vaddu", "vendam", "vaddhu"
    ]
    if _matches_any_keyword(lower, denial_keywords):
        return "denial", {}

    # 18. Affirmative / Confirmation keywords (checked BEFORE booking so phrases like "seri book pannunga" confirm)
    confirm_keywords = [
        "yes please", "confirm", "confirm booking", "confirm my appointment",
        "yes confirm", "please confirm", "sure confirm", "சரி உறுதி",
        "உறுதி செய்", "ஆம் சரி", "ஆம் உறுதி", "అవును నిర్ధారించండి",
        "ఖచ్చితంగా నిర్ధారించండి", "అవును సరే", "avunu thappakunda",
        "confirm pannanum", "confirm cheyandi",
        "seri book pannunga", "book pannunga", "book pannidunga", "seri pannunga",
        "pannunga", "pannidunga", "சரி பதிவு செய்யுங்கள்", "பதிவு செய்யுங்கள்",
        "sare book cheyandi", "book cheyandi",
        "yes", "sure", "okay", "fine", "correct", "yeah", "yep",
        "சரி", "ஆம்", "ஆமாம்", "sari", "aama", "kandippa",
        "అవును", "సరే", "ఖచ్చితంగా", "avunu", "alage", "nijam"
    ]
    if not has_symptom_or_illness(lower) and _matches_any_keyword(lower, confirm_keywords):
        # Do not treat as a bare confirmation if the user specified booking/datetime details
        has_booking_details = bool(re.search(
            r"\b(?:naalaiku|nalaiku|naalai|naalaikku|tomorrow|repu|today|inniku|innikku|morning|evening|afternoon|night|"
            r"kaalai|kaalaila|madhiyam|mathiyam|sayanthiram|slot|slots|mani|manikku|maniku|clock|am|pm|venum|vendum|kavali)\b",
            lower
        ))
        if not has_booking_details and not re.search(r"\b(?:not\s+fine|not\s+okay|seri\s+illa|sari\s+illa|mudiyala|mudila)\b", lower):
            return "confirmation", {}

    # 19. Booking & Symptom intent
    booking_keywords = [
        "book", "appointment", "schedule", "reserve", "doctor",
        "consultation", "visit", "see", "checkup", "physician",
        "unwell", "sick", "ill", "headache", "fever", "cough", "cold", "pain",
        "see a doctor", "consult a doctor", "doctor consultation", "medical consultation",
        "need an appointment", "want an appointment", "book an appointment",
        "enakku appointment venum", "appointment venum", "enakku fever irukku", "fever irukku",
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
    ]
    if _matches_any_keyword(lower, booking_keywords):
        return "booking", {}

    # 20. Greeting / Casual Conversation
    greeting_keywords = [
        "hello", "hi", "hey", "good morning", "good evening", "how are you", "who are you",
        "வணக்கம்", "vanakkam", "நலமா", "నమస్కారం", "namaskaram", "ela unnaru"
    ]
    if _matches_any_keyword(lower, greeting_keywords):
        return "greeting", {}

    return "unknown", {}


def answer_unrelated_general_query(query_key: str, language: str) -> str:
    """Provide safe, brief factual answers for general knowledge queries."""
    entry = GENERAL_KNOWLEDGE_QUESTIONS.get(query_key, {})
    if language.startswith("ta"):
        if language == "ta-Latn":
            return entry.get("ta_latn") or entry.get("ta") or entry.get("en", "")
        return entry.get("ta") or entry.get("en", "")
    elif language.startswith("te"):
        if language == "te-Latn":
            return entry.get("te_latn") or entry.get("te") or entry.get("en", "")
        return entry.get("te") or entry.get("en", "")
    return entry.get("en", "")


def answer_pricing_query(
    db: Session,
    business: Business,
    speech_text: str,
    language: str,
    matched_service: Service | None = None,
) -> tuple[str, Service | None]:
    """Retrieve service pricing and duration from the active catalog."""
    active_srvs = db.scalars(
        select(Service).where(Service.business_id == business.id, Service.is_active.is_(True))
    ).all()

    target_srv = matched_service
    if not target_srv and active_srvs:
        # Check if caller specifically asked about a service name
        clean_speech = speech_text.lower()
        for srv in active_srvs:
            if srv.name and srv.name.lower() in clean_speech:
                target_srv = srv
                break

    if target_srv:
        fee = int(target_srv.price)
        dur = target_srv.duration_minutes
        if language.startswith("ta"):
            if language == "ta-Latn":
                resp = f"{target_srv.name} consultation fees {fee} rupees. Appointment book pannanuma?"
            else:
                resp = f"{target_srv.name} ஆலோசனை கட்டணம் {fee} ரூபாய். அப்பாயின்ட்மென்ட் புக் பண்ணனுமா?"
        elif language.startswith("te"):
            if language == "te-Latn":
                resp = f"{target_srv.name} fee {fee} rupees. Appointment book cheyamantara?"
            else:
                resp = f"{target_srv.name} సంప్రదింపుల ధర {fee} రూపాయలు. అపాయింట్‌మెంట్ బుక్ చేయమంటారా?"
        else:
            resp = f"{target_srv.name} consultation fee is {fee} rupees. Would you like to book an appointment?"
        return format_spoken_response(resp), target_srv

    # If no specific service identified, summarize top services
    if active_srvs:
        p_fee = int(active_srvs[0].price)
        if language.startswith("ta"):
            if language == "ta-Latn":
                resp = f"General physician consultation fees {p_fee} rupees. Appointment book pannanuma?"
            else:
                resp = f"பொது மருத்துவ ஆலோசனை கட்டணம் {p_fee} ரூபாய். அப்பாயின்ட்மென்ட் புக் பண்ணனுமா?"
        elif language.startswith("te"):
            if language == "te-Latn":
                resp = f"General physician consultation fee {p_fee} rupees. Appointment book cheyamantara?"
            else:
                resp = f"సాధారణ వైద్య సంప్రదింపుల ధర {p_fee} రూపాయలు. అపాయింట్‌మెంట్ బుక్ చేయమంటారా?"
        else:
            resp = f"General physician consultation fee is {p_fee} rupees. Would you like to book an appointment?"
        return format_spoken_response(resp), None

    if language.startswith("ta"):
        if language == "ta-Latn":
            return "General physician consultation fees 500 rupees. Appointment book pannanuma?", None
        return "பொது மருத்துவ ஆலோசனை கட்டணம் 500 ரூபாய். அப்பாயின்ட்மென்ட் புக் பண்ணனுமா?", None
    elif language.startswith("te"):
        if language == "te-Latn":
            return "General physician consultation fee 500 rupees. Appointment book cheyamantara?", None
        return "సాధారణ వైద్య సంప్రదింపుల ధర 500 రూపాయలు. అపాయింట్‌మెంట్ బుక్ చేయమంటారా?", None
    return "General physician consultation fee is 500 rupees. Would you like to book an appointment?", None


def answer_payment_methods_query(db: Session, business: Business, language: str) -> str:
    """Retrieve accepted payment modes and insurance policies."""
    # Check if business has custom FAQ on payment
    faqs = db.scalars(
        select(FAQ).where(FAQ.business_id == business.id, FAQ.is_active.is_(True))
    ).all()
    faq_match = find_matching_faq("payment methods upi cash credit card", list(faqs))
    if faq_match:
        return format_spoken_response(faq_match.answer)

    if language.startswith("ta"):
        if language == "ta-Latn":
            return "Naanga Cash, Google Pay, PhonePe maadhiri UPI, Credit and Debit cards accept panrom."
        return "நாங்கள் ரொக்கப் பணம், Google Pay, PhonePe போன்ற UPI, கிரெடிட் மற்றும் டெபிட் கார்டுகளை ஏற்றுக்கொள்கிறோம்."
    elif language.startswith("te"):
        if language == "te-Latn":
            return "Memu Cash, Google Pay, PhonePe vanti UPI, Credit and Debit cards accept chestamu."
        return "మేము నగదు, Google Pay, PhonePe వంటి UPI, క్రెడిట్ మరియు డెబిట్ కార్డులను స్వీకరిస్తాము."
    return "We accept Cash, UPI such as Google Pay and PhonePe, as well as Credit and Debit cards at our reception."


def answer_doctor_staff_query(db: Session, business: Business, language: str) -> str:
    """Retrieve doctor and practitioner availability details from StaffSchedule or FAQs."""
    schedules = db.scalars(
        select(StaffSchedule).where(StaffSchedule.business_id == business.id, StaffSchedule.is_active.is_(True))
    ).all()

    doctor_names: list[str] = []
    for s in schedules:
        if s.staff_name and s.staff_name not in doctor_names:
            doctor_names.append(s.staff_name)

    if doctor_names:
        names_str = ", ".join(doctor_names[:3])
        if language.startswith("ta"):
            if language == "ta-Latn":
                return format_spoken_response(f"Enga clinic-la Dr. {names_str} irukaanga. Appointment book pannanuma?")
            return format_spoken_response(f"எங்க கிளினிக்ல டாக்டர் {names_str} இருக்காங்க. அப்பாயின்ட்மென்ட் புக் பண்ணனுமா?")
        elif language.startswith("te"):
            if language == "te-Latn":
                return format_spoken_response(f"Ma clinic-lo Dr. {names_str} unnaru. Appointment book cheyamantara?")
            return format_spoken_response(f"మా ఆసుపత్రిలో డాక్టర్ {names_str} అందుబాటులో ఉన్నారు. అపాయింట్‌మెంట్ బుక్ చేయమంటారా?")
        return format_spoken_response(f"At our clinic, Dr. {names_str} is available. Would you like to book an appointment?")

    if language.startswith("ta"):
        if language == "ta-Latn":
            return format_spoken_response("Vanakkam! Aama, doctor irukaanga. Appointment book pannanuma?")
        return format_spoken_response("வணக்கம்! ஆமா, டாக்டர் இருக்காங்க. அப்பாயின்ட்மென்ட் புக் பண்ணனுமா?")
    elif language.startswith("te"):
        if language == "te-Latn":
            return format_spoken_response("Namaskaram! Avunu, doctor unnaru. Appointment book cheyamantara?")
        return format_spoken_response("నమస్కారం! అవును, డాక్టర్ అందుబాటులో ఉన్నారు. అపాయింట్‌మెంట్ బుక్ చేయమంటారా?")
    return format_spoken_response("Hello! Yes, the doctor is available. Would you like to book an appointment?")


def answer_complaint_query(business: Business, language: str) -> str:
    """Acknowledge patient grievance empathetically and offer escalation."""
    if language.startswith("ta"):
        if language == "ta-Latn":
            return format_spoken_response(
                "Ungalukku erpatta kashtathuku mannikavum. Patient care engalukku romba mukkiyam. "
                "Unga complaint-ai clinic management-ku note panren."
            )
        return format_spoken_response(
            "உங்களுக்கு ஏற்பட்ட சிரமத்திற்கு மிகவும் வருந்துகிறோம். நோயாளிகளின் திருப்தியே எங்கள் நோக்கம். "
            "உங்கள் கருத்தை எங்கள் மருத்துவமனை நிர்வாகத்திற்கு பதிவு செய்துள்ளேன்."
        )
    elif language.startswith("te"):
        if language == "te-Latn":
            return format_spoken_response(
                "Meeku kaligina asoukaryaniki kshaminchandi. Mee complaint-ni ma management-ku note chestanu."
            )
        return format_spoken_response(
            "మీకు కలిగిన అసౌకర్యానికి మేము చింతిస్తున్నాము. రోగుల సంరక్షణ మా మొదటి ప్రాధాన్యత. "
            "మీ ఫిర్యాదును మా నిర్వాహకులకు తెలియజేస్తున్నాను."
        )
    return format_spoken_response(
        "I am truly sorry to hear that you had an unpleasant experience. Patient satisfaction is our highest priority. "
        "I have registered your feedback for our clinic management to review."
    )


def answer_unknown_question(business: Business, language: str) -> str:
    """Honestly acknowledge lack of records and offer front desk callback/transfer."""
    phone = business.phone or "our reception desk"
    if language.startswith("ta"):
        if language == "ta-Latn":
            return format_spoken_response(
                f"Andha detail ennoda records-la illa. Ungalukku reception callback arrange pannava, "
                f"illa direct-ah {phone} number-ku call panreengala?"
            )
        return format_spoken_response(
            f"அந்த தகவல் தற்போது எனது பதிவேட்டில் இல்லை. எங்கள் வரவேற்புக் குழுவினர் உங்களை மீண்டும் அழைக்க ஏற்பாடு செய்யவா, "
            f"அல்லது {phone} என்ற எண்ணில் தொடர்பு கொள்ள விரும்புகிறீர்களா?"
        )
    elif language.startswith("te"):
        if language == "te-Latn":
            return format_spoken_response(
                f"Aa details na records-lo levu. Ma reception team meeku callback chesela arrange cheyamantara, "
                f"leda {phone} number-ku direct-ga call chestara?"
            )
        return format_spoken_response(
            f"ఆ వివరాలు ప్రస్తుతానికి నా వద్ద లేవు. మా రిసెప్షన్ బృందం మీకు తిరిగి కాల్ చేసేలా ఏర్పాటు చేయమంటారా, "
            f"లేదా నేరుగా {phone} నంబర్‌కు కాల్ చేస్తారా?"
        )
    return format_spoken_response(
        f"I do not have that specific information in my records. I can arrange for our reception team to call you back, "
        f"or you can speak directly with our front desk at {phone}. Would you like me to request a callback?"
    )


def get_contextual_continuation_prompt(
    session: ConversationSession | str,
    business: Business | str | None = None,
    language: str | None = None,
    matched_service: Service | None = None,
) -> str:
    """Seamlessly transition from an informational question back to the active workflow."""
    if isinstance(session, str):
        step = session
        language = business if isinstance(business, str) else (language or "en-IN")
        service_name = "consultation"
    else:
        step = session.step
        language = language or session.language or "en-IN"
        service_name = session.service_name or "consultation"

    if step == "awaiting_service":
        if matched_service:
            if language.startswith("ta"):
                if language == "ta-Latn":
                    return f"Ungalukku {matched_service.name}-ku appointment book panna udhavava?"
                return f"{matched_service.name} ஆலோசனைக்கு அப்பாயிண்ட்மெண்ட் பதிவு செய்ய உதவவா?"
            elif language.startswith("te"):
                if language == "te-Latn":
                    return f"Meku {matched_service.name} kosam appointment book cheyamantara?"
                return f"మీకు {matched_service.name} కోసం అపాయింట్‌మెంట్ బుక్ చేయమంటారా?"
            return f"Would you like me to help you schedule an appointment for {matched_service.name}?"

        active_srvs = session.service_name or "General Physician"
        if language.startswith("ta"):
            if language == "ta-Latn":
                return "Neenga entha medical service book panna virumbureenga?"
            return "நீங்கள் எந்த மருத்துவ ஆலோசனை பதிவு செய்ய விரும்புகிறீர்கள்?"
        elif language.startswith("te"):
            if language == "te-Latn":
                return "Meeru ye medical service book cheyalani anukuntunnaru?"
            return "మీరు ఏ వైద్య సేవ కోసం అపాయింట్‌మెంట్ బుక్ చేయాలనుకుంటున్నారు?"
        return "Which medical service would you like to book?"

    elif step == "awaiting_datetime":
        srv = session.service_name or "consultation"
        if language.startswith("ta"):
            if language == "ta-Latn":
                return "Endha date and time convenient-ah irukum?"
            return "எந்த நாள் மற்றும் நேரம் உங்களுக்கு வசதி?"
        elif language.startswith("te"):
            if language == "te-Latn":
                return "Ye date and time convenient-ga untundi?"
            return "ఏ రోజు మరియు సమయం అనుకూలంగా ఉంటుంది?"
        return "What date and time works best for you?"

    elif step == "awaiting_name":
        if language.startswith("ta"):
            if language == "ta-Latn":
                return "Booking confirm panna unga peru sollunga please?"
            return "முன்பதிவு செய்ய உங்கள் பெயர் சொல்லுங்க please?"
        elif language.startswith("te"):
            if language == "te-Latn":
                return "Booking confirm cheyadaniki mee peru cheppandi please?"
            return "బుకింగ్ కోసం మీ పేరు చెప్పండి?"
        return "May I please have your name for the booking record?"

    elif step == "awaiting_confirmation":
        if language.startswith("ta"):
            if language == "ta-Latn":
                return "Indha booking-ai confirm pannava?"
            return "இந்த முன்பதிவை உறுதி செய்யவா?"
        elif language.startswith("te"):
            if language == "te-Latn":
                return "Ee booking-ni confirm cheyala?"
            return "ఈ అపాయింట్‌మెంట్‌ని నిర్ధారించాలా?"
        return "Shall I go ahead and confirm this appointment for you?"

    # Generic standby
    if language.startswith("ta"):
        if language == "ta-Latn":
            return "Indru ungal appointment-ku eppadi udhavalam?"
        return "இன்று உங்கள் மருத்துவ ஆலோசனைக்கு நான் எவ்வாறு உதவ முடியும்?"
    elif language.startswith("te"):
        if language == "te-Latn":
            return "Ee roju mee appointment kosam ela sahayam cheyali?"
        return "ఈరోజు మీకు ఎలా సహాయపడగలను?"
    return "How can I assist you with your clinic visit today?"

