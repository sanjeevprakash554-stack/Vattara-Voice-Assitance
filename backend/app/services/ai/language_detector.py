"""Multilingual detection and language normalization for English, Tamil, and Telugu."""

import re

# Comprehensive dictionary of distinctive Tanglish terms and phonetic roots
TANGLISH_VOCABULARY = {
    # Pronouns & Conjunctions & Particles
    "naan", "enakku", "enaku", "namma", "namakku", "neenga", "ungalukku", "ungala",
    "enna", "ethu", "edhu", "enge", "enga", "engae", "eppo", "eppothu", "yeppo",
    "epdi", "eppadi", "yeppadi", "yen", "evlo", "yevlo", "evvalavu", "evalo",
    "yaar", "yaaru", "aana", "aanaal", "illai", "illa", "illaiya", "illana", "illena",
    "kooda", "thaan", "thaane", "dhaan", "dhane", "la", "le", "nu", "ku", "ki",
    "aam", "aama", "aamam", "seri", "sari", "kandippa",
    
    # Greetings & Politeness
    "vanakkam", "nandri", "romba", "mikka", "thayavu", "thayavuseithu", "mannikanum", "mannikavum",
    
    # Verbs (actions, intentions, requests, modals)
    "venum", "vendum", "vendam", "venam", "venuma", "venungala", "parkanum", "paarkanum", "paakanum", "pakanum", "paakanuma", "paaka", "paarka", "pannanum", "pannunga",
    "panunga", "pannalam", "panren", "pannren", "pannidunga", "panidunga", "pannikonga", "pannidalaam", "pannidalam", "seiyanum", "seiyunga", "irukka", "irukku", "iruka", "iruku",
    "irukum", "irukkum", "irukaangala", "irukangala", "irukkangala", "irukaara", "irukara", "irukkaru", "irupaara", "irupaaru", "irundhaa", "irundha", "varanum", "vaanga", "varuvaara", "varuvaangala", "pesanum",
    "pesunga", "sollunga", "solunga", "solreengala", "theriyum", "theriyala", "theriyuma", "kudunga", "kodunga", "edunga",
    "kelunga", "mudiyuma", "mudiyum", "mudila", "mudiyala", "aaguma", "podhum", "vaiyunga", "kidaikum",
    "kidaikkum", "kedaikum", "kedaikkum", "kidaikuma", "kedaikuma", "available-ah", "available-a", "available-aa",
    
    # Time & Days & Relatives
    "iniku", "iniki", "inraiku", "indraiku", "naalaiki", "naalaki", "naalai",
    "naalaikku", "naalaiku", "nalaikku", "nalaiku", "marunaal", "munnal",
    "kaalai", "kaalaila", "madhiyam", "mathiyam", "saayandhram", "sayanthiram",
    "saayangaalam", "iravu", "mani", "manikku", "maniki", "neram", "kizhamai",
    "thingal", "sevvai", "budhan", "vyazhan", "velli", "sani", "gnaayiru",
    "vara", "varam", "maasam", "varusham",
    
    # Medical & Appointment terms in Tanglish
    "maruthuvar", "maruthuvam", "noi", "valikithu", "valikudhu", "valikuthu", "vali", "udambu", "udambu mudiyala",
    "odambu", "odambu seri illa", "odambu mudiyala", "udambu seri illa", "thala", "thalavali", "thala vali",
    "kaachal", "irumal", "sali", "thalai vali", "vayiru", "raththam", "parithothanai",
    "parisothanai", "pal", "marunthu", "marundhu", "munpathivu", "munpadhivu",
    "pathivu", "padhivu", "kuzhanthai", "nalam",
}

# Comprehensive dictionary of distinctive Teluglish terms and phonetic roots
TELUGU_LATIN_VOCABULARY = {
    "nenu", "naaku", "naku", "naa", "peru", "kosam", "maaku", "memu", "manamu", "meeru", "meeku", "miku",
    "atanu", "aame", "vaallu", "vaaru", "enti", "eppudu", "ekkada", "ela",
    "endhuku", "enduku", "evaru", "edi", "edhi", "deni", "dheniki", "inkenti", "emiti",
    "kaani", "kani", "mari", "kooda", "kadha", "kada", "ante", "ani",
    
    # Greetings & Politeness
    "namaskaram", "namaskaramandi", "namaste", "dhanyavadalu", "dhanyavadamulu",
    "dayachesi", "dayavunchi", "kshaminchandi", "thappakunda", "chala", "manchi",
    
    # Verbs (actions, intentions, requests)
    "kavali", "kaavali", "vaddu", "vaddhu", "undi", "undha", "undhi", "ledu", "ledha",
    "cheyali", "cheyandi", "cheyagalaru", "chesukondi", "cheskovali", "chesanu",
    "kudhurthunda", "kudhurthundha", "kudurthundi", "kudurthundha", "chudali",
    "chupinchukovali", "matladali", "matladandi", "cheppandi", "telusu", "teliyadu",
    "ivvandi", "theesukondi", "vellali", "vastanu", "randi", "vasta", "unnamu",
    "marchandi",
    
    # Time & Days & Relatives
    "ivvala", "ee roju", "eeroju", "repu", "ellundi", "monna",
    "udayam", "sayantram", "sayantramu", "madhyanam", "raathri", "rathri",
    "ganta", "gantalu", "gantaku", "gantalaku", "gantalaki", "samayam", "varam",
    "aadhivaram", "adivaram", "somavaram", "mangalavaram", "budhavaram",
    "guruvaram", "sukravaram", "sanivaram", "nela", "samvatsaram",
    
    # Medical & Appointment terms in Teluglish
    "vaidhyudu", "vaidyudu", "doctoru", "chikitsa", "rogi", "noppi",
    "thala noppi", "kadupu", "kadupu noppi", "jwaram", "daggu", "jalubu",
    "raktham", "pareeksha", "pallu", "panti", "mandhu", "mandhulu",
    "mundhugaa", "darshanam", "raddhu", "marpu", "sare", "avunu", "nijam", "alage",
}

# Common English medical, clinical, and scheduling loanwords routinely borrowed into Indian languages
INDIAN_ENGLISH_LOANWORDS = {
    # Medical & Clinical loanwords
    "doctor", "dr", "appointment", "consultation", "checkup", "clinic", "hospital",
    "physician", "cardiology", "cardiac", "pediatric", "pediatrician", "dental",
    "dentist", "cleaning", "blood", "test", "diagnostics", "lab", "medicine",
    "tablet", "fever", "cough", "pain", "treatment", "operation", "surgery",
    "scan", "xray", "ecg", "icu", "opd", "emergency", "ambulance",
    "fees", "fee", "cost", "charge", "charges", "price", "payment", "card",
    "gpay", "phonepe", "upi", "cash",
    # Scheduling & Logistics loanwords
    "slot", "slots", "time", "timing", "timings", "date", "morning", "afternoon",
    "evening", "night", "today", "tomorrow", "sunday", "monday", "tuesday",
    "wednesday", "thursday", "friday", "saturday", "week", "month", "year",
    "book", "booking", "cancel", "cancellation", "reschedule", "confirm",
    "confirmation", "available", "availability", "open", "close", "closed",
    "hours", "address", "location", "near", "parking",
    # Conversational Fillers, Times & Affirmations
    "please", "thanks", "thank", "you", "okay", "ok", "yes", "no", "actually",
    "just", "already", "problem", "issue", "help", "sir", "madam",
    "am", "pm", "good", "fine", "great", "sure", "is", "it", "that", "this", "name",
}

# Structural English grammatical words that signal intentional English speech
ENGLISH_GRAMMAR_WORDS = {
    "can", "could", "would", "will", "should", "what", "when", "where", "which",
    "how", "why", "who", "is", "are", "am", "was", "were", "have", "has", "had",
    "do", "does", "did", "i", "we", "my", "our", "your", "the", "an", "a",
    "at", "in", "on", "for", "to", "from", "with", "about", "tell", "want",
    "like", "need", "give", "speak", "switch", "english", "language", "understand",
}

EXPLICIT_ENGLISH_SWITCH_REGEX = re.compile(
    r"\b(?:switch to english|change to english|speak in english|speak english|talk in english|talk english|talk to me in english|in english please|in english|can you speak in english|can you speak english|could you speak english|can we speak english|can we talk in english|i want to speak in english|i want english|english please|english only|only english|english-la pesunga|english la pesunga|english lo matladandi|do you speak english|from now on english)\b",
    re.IGNORECASE,
)

EXPLICIT_TAMIL_SWITCH_REGEX = re.compile(
    r"(?:\b(?:switch to tamil|change to tamil|tamil-la pesunga|thamizhla pesunga|tamil la pesunga|tamizhil pesunga|tamilil pesungal|tamil-il pesunga|speak in tamil|speak tamil|talk in tamil|talk tamil|talk to me in tamil|tamil please|tamil only|only tamil|in tamil please|in tamil|can you speak in tamil|can you speak tamil|could you speak tamil|can we speak in tamil|i want to speak in tamil|do you speak tamil|do you know tamil)\b|தமிழில் பேசுங்கள்|தமிழில் பேசவும்|தமிழில்|தமிழ்)",
    re.IGNORECASE,
)

EXPLICIT_TELUGU_SWITCH_REGEX = re.compile(
    r"(?:\b(?:switch to telugu|change to telugu|telugu-lo matladandi|telugulo matladandi|telugu lo matladandi|telugu lo maatladandi|telugulo maatladandi|telugu matladandi|speak in telugu|speak telugu|talk in telugu|talk telugu|telugu please|in telugu please|in telugu|can you speak in telugu|can you speak telugu|could you speak telugu|do you speak telugu|do you know telugu)\b|తెలుగులో మాట్లాడండి|తెలుగులో మాట్లాడగలరా|తెలుగులో|తెలుగు)",
    re.IGNORECASE,
)

EXPLICIT_TANGLISH_SWITCH_REGEX = re.compile(
    r"\b(?:tanglish-la pesunga|tanglish la pesunga|tanglish please|tanglish only|only tanglish|speak in tanglish|speak tanglish|switch to tanglish|in tanglish|talk in tanglish)\b",
    re.IGNORECASE,
)

# Common short conversational acknowledgments, fillers, and recovery checks that must NEVER alter language preference
SHORT_CONVERSATIONAL_FILLERS = {
    "hello", "hi", "hey", "yes", "yeah", "yep", "no", "nope", "okay", "ok", "k",
    "sure", "fine", "good", "alright", "right", "thanks", "thank you", "please",
    "sari", "seri", "aama", "aamam", "avunu", "alage", "sare",
    "ah", "um", "uh", "hmm", "oh",
}

CONVERSATIONAL_RECOVERY_PHRASES = {
    "hello?", "are you there", "are you there?", "can you hear me", "can you hear me?",
    "could you hear me", "are you listening", "hello hello", "hello hello?",
    "one minute", "wait", "wait a minute", "just a second", "just a sec", "hold on",
    "am i audible", "am i audible?", "still there", "still there?",
}


def is_tamil_script(text: str) -> bool:
    """Check if the text contains Tamil Unicode script characters (U+0B80 to U+0BFF)."""
    if not text:
        return False
    return bool(re.search(r"[\u0B80-\u0BFF]", text))


def is_telugu_script(text: str) -> bool:
    """Check if the text contains Telugu Unicode script characters (U+0C00 to U+0C7F)."""
    if not text:
        return False
    return bool(re.search(r"[\u0C00-\u0C7F]", text))


def detect_language(
    text: str,
    current_lang: str = "en-IN",
    deepgram_detected_lang: str | None = None,
    stt_detected_lang: str | None = None,
) -> str:
    """Classify user speech into 'te-IN', 'te-Latn', 'ta-IN', 'ta-Latn', or 'en-IN'.

    Maintains language continuity throughout the call:
    - Preserves established Tanglish ('ta-Latn') and Tamil ('ta-IN').
    - Distinguishes Tamil script ('ta-IN') from Tanglish ('ta-Latn').
    - Tolerates mixed scripts and common English medical/scheduling loanwords.
    - Switches smoothly to English on full English sentences or explicit switch commands.
    - Switches smoothly to Tamil/Tanglish when regional speech resumes.
    - Integrates Unicode script detection and STT (Sarvam / Deepgram) language metadata together.
    - Never permanently locks the session to its initial language.
    - Does not classify English medical terms or names as a language switch by themselves.
    """
    if not text or not text.strip():
        return current_lang

    effective_stt_lang = stt_detected_lang or deepgram_detected_lang

    clean = text.strip()
    lower_text = clean.lower()

    # 1. Native Script Checks (Highest Priority: Tamil & Telugu Unicode scripts are definitive)
    has_telugu = is_telugu_script(clean)
    has_tamil = is_tamil_script(clean)

    if has_telugu:
        # Protect established Tamil/Tanglish conversations against stray ASR hallucinations
        if current_lang in ("ta-IN", "ta-Latn"):
            if not EXPLICIT_TELUGU_SWITCH_REGEX.search(lower_text):
                return current_lang
        return "te-IN"

    if has_tamil:
        # Protect established Tanglish conversations against switching to Tamil script unless explicitly requested
        if current_lang == "ta-Latn" and not EXPLICIT_TAMIL_SWITCH_REGEX.search(lower_text):
            return "ta-Latn"
        # Protect established Telugu/Teluglish conversations against stray ASR hallucinations
        if current_lang in ("te-IN", "te-Latn"):
            if not EXPLICIT_TAMIL_SWITCH_REGEX.search(lower_text) and not EXPLICIT_TANGLISH_SWITCH_REGEX.search(lower_text):
                return current_lang
        return "ta-IN"

    # 2. Explicit Language Switch Commands (Highest Priority for Latin/English Requests)
    if EXPLICIT_TELUGU_SWITCH_REGEX.search(lower_text):
        return "te-IN"
    if EXPLICIT_TAMIL_SWITCH_REGEX.search(lower_text):
        return "ta-IN"
    if EXPLICIT_TANGLISH_SWITCH_REGEX.search(lower_text):
        return "ta-Latn"
    if EXPLICIT_ENGLISH_SWITCH_REGEX.search(lower_text):
        return "en-IN"

    # 3. Short Conversational Fillers & Recovery Checks: NEVER change language on 'Hello?', 'Are you there?', 'Okay', 'Yes'
    norm_clean = re.sub(r"[^\w\s]", "", lower_text).strip()
    if lower_text in CONVERSATIONAL_RECOVERY_PHRASES or norm_clean in CONVERSATIONAL_RECOVERY_PHRASES:
        return current_lang

    tokens = [w.lower() for w in re.findall(r"\b[a-zA-Z]+\b", clean)]
    if not tokens:
        return current_lang

    # Only treat as neutral filler if tokens don't contain regional Tanglish/Teluglish vocabulary
    has_tanglish_marker = any(t in TANGLISH_VOCABULARY for t in tokens)
    has_teluglish_marker = any(t in TELUGU_LATIN_VOCABULARY for t in tokens)
    if not has_tanglish_marker and not has_teluglish_marker:
        if norm_clean in SHORT_CONVERSATIONAL_FILLERS or all(t in SHORT_CONVERSATIONAL_FILLERS for t in tokens):
            return current_lang

    # --- Tanglish Scoring ---
    tanglish_hits = sum(1 for t in tokens if t in TANGLISH_VOCABULARY)
    tanglish_suffix_hits = sum(
        1 for t in tokens
        if len(t) > 3 and (
            t.endswith("num")
            or t.endswith("unga")
            or t.endswith("anga")
            or t.endswith("la")
            or t.endswith("ala")
            or t.endswith("kku")
            or t.endswith("ku")
            or t.endswith("iki")
            or t.endswith("iku")
            or t.endswith("kuma")
            or t.endswith("aara")
            or t.endswith("aaru")
            or t.endswith("aangala")
            or t.endswith("angala")
            or t.endswith("ren")
            or t.endswith("nren")
            or t.endswith("uma")
        )
    )
    total_tanglish_score = tanglish_hits * 2 + tanglish_suffix_hits

    # --- Teluglish Scoring ---
    teluglish_hits = sum(1 for t in tokens if t in TELUGU_LATIN_VOCABULARY)
    teluglish_suffix_hits = sum(
        1 for t in tokens
        if len(t) > 3 and (
            t.endswith("ali")
            or t.endswith("andi")
            or t.endswith("undha")
            or t.endswith("undi")
            or t.endswith("thundi")
            or t.endswith("tundi")
            or t.endswith("kovali")
            or t.endswith("galanu")
            or t.endswith("kondi")
        )
    )
    total_teluglish_score = teluglish_hits * 2 + teluglish_suffix_hits

    # Strict Language Consistency: If conversation is established in Tamil/Tanglish,
    # NEVER switch to Telugu without an explicit caller switch request.
    if current_lang in ("ta-IN", "ta-Latn"):
        if total_tanglish_score > 0 or has_tanglish_marker:
            return "ta-Latn"
        # Check if full English sentence was spoken
        grammar_hits = sum(1 for t in tokens if t in ENGLISH_GRAMMAR_WORDS)
        non_loanword_tokens = [t for t in tokens if t not in INDIAN_ENGLISH_LOANWORDS]
        if total_tanglish_score == 0 and len(non_loanword_tokens) >= 1 and (grammar_hits >= 2 or (grammar_hits >= 1 and len(tokens) >= 3)):
            return "en-IN"
        return current_lang

    # Strict Language Consistency: If conversation is established in Telugu/Teluglish,
    # NEVER switch to Tamil without an explicit caller switch request.
    if current_lang in ("te-IN", "te-Latn"):
        if total_teluglish_score > 0 or has_teluglish_marker:
            return "te-Latn"
        grammar_hits = sum(1 for t in tokens if t in ENGLISH_GRAMMAR_WORDS)
        non_loanword_tokens = [t for t in tokens if t not in INDIAN_ENGLISH_LOANWORDS]
        if total_teluglish_score == 0 and len(non_loanword_tokens) >= 1 and (grammar_hits >= 2 or (grammar_hits >= 1 and len(tokens) >= 3)):
            return "en-IN"
        return current_lang

    # For initial turn / English base:
    # Check Tanglish preference (prioritized for Tamil default greeting)
    if total_tanglish_score > 0 and total_tanglish_score >= total_teluglish_score:
        if tanglish_hits >= 1 or total_tanglish_score >= 2 or (len(tokens) <= 3 and total_tanglish_score >= 1):
            return "ta-Latn"

    # Check Teluglish preference
    if total_teluglish_score > 0 and total_teluglish_score > total_tanglish_score:
        if teluglish_hits >= 1 or total_teluglish_score >= 2 or (len(tokens) <= 3 and total_teluglish_score >= 1):
            return "te-Latn"

    # 4. STT (Sarvam / Deepgram) Metadata Synergy
    stt_lang = (effective_stt_lang or "").strip().lower()
    if stt_lang.startswith("ta") and total_tanglish_score > 0:
        return "ta-Latn"
    if stt_lang.startswith("te") and total_teluglish_score > 0:
        return "te-Latn"
    if stt_lang.startswith("ta") and current_lang in ("ta-IN", "ta-Latn"):
        return current_lang

    # 5. Caller Persistence & Intelligent Code-Switching:
    # If caller previously established a regional language (Tamil/Telugu/Tanglish/Teluglish),
    # do NOT switch away due to isolated medical/scheduling loanwords, names, numbers, or short affirmative replies.
    if current_lang in ("ta-Latn", "ta-IN", "te-Latn", "te-IN"):
        # Explicit switch command?
        if EXPLICIT_ENGLISH_SWITCH_REGEX.search(lower_text):
            return "en-IN"

        # Filter tokens into grammatical structure indicators vs borrowed loanwords
        grammar_hits = sum(1 for t in tokens if t in ENGLISH_GRAMMAR_WORDS)
        non_loanword_tokens = [t for t in tokens if t not in INDIAN_ENGLISH_LOANWORDS]

        # Isolated medical terms, personal names, or pure loanword confirmations
        # (e.g. "Cardiology", "Dr. Steve", "Tomorrow 10 AM", "Yes 10 am is good", "Okay doctor")
        # should NEVER trigger a language switch by themselves:
        if len(non_loanword_tokens) == 0:
            return current_lang
        if len(tokens) <= 2 and grammar_hits == 0:
            return current_lang

        # Switch to English if caller spoke a structured English sentence:
        # e.g., "Hello, I want to book an appointment", "What are your clinic working hours?",
        # "Can I see a doctor tomorrow?", "Where is the clinic located?"
        is_english_sentence = (
            total_tanglish_score == 0
            and total_teluglish_score == 0
            and len(non_loanword_tokens) >= 1
            and (
                grammar_hits >= 2
                or (grammar_hits >= 1 and len(tokens) >= 3)
                or (stt_lang.startswith("en") and grammar_hits >= 1)
            )
        )
        if is_english_sentence:
            return "en-IN"

        # Otherwise preserve the established regional preference
        return current_lang

    # 6. Default to standard English
    return "en-IN"


def get_display_language_name(lang_code: str) -> str:
    """Return user-friendly label for a language code."""
    mapping = {
        "te-IN": "Telugu (తెలుగు)",
        "te-Latn": "Teluglish (Telugu in English Script)",
        "ta-IN": "Tamil (தமிழ்)",
        "ta-Latn": "Tanglish (Tamil in English Script)",
        "en-IN": "English (India)",
        "en-US": "English (US)",
        "multi": "Multilingual (EN/TA/TE)",
    }
    return mapping.get(lang_code, "English")
