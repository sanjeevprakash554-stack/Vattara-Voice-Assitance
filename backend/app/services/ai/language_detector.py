"""Multilingual detection and language normalization for English, Tamil, and Telugu."""

import re

# Comprehensive dictionary of distinctive Tanglish terms and phonetic roots
TANGLISH_VOCABULARY = {
    # Pronouns & Conjunctions & Particles
    "naan", "enakku", "enaku", "namma", "namakku", "neenga", "ungalukku", "ungala",
    "enna", "ethu", "enge", "engae", "eppo", "eppothu", "epdi", "yeppadi", "yen",
    "aana", "aanaal", "illai", "illa", "illaiya", "illana", "illena", "kooda",
    "thaan", "thaane", "dhaan", "dhane", "la", "le", "nu", "aam", "aama", "aamam",
    
    # Greetings & Politeness
    "vanakkam", "nandri", "romba", "mikka", "thayavu", "thayavuseithu", "mannikanum",
    
    # Verbs (actions, intentions, requests)
    "venum", "vendum", "vendam", "venam", "parkanum", "paarkanum", "pannanum", "pannunga", "pannalam", "panren", "pannren",
    "seiyanum", "seiyunga", "irukka", "irukku", "iruka", "irukaangala", "varanum", "vaanga",
    "pesanum", "pesunga", "sollunga", "theriyum", "theriyala", "kudunga", "kodunga",
    "edunga", "kelunga", "mudiyuma", "aaguma", "podhum", "vaiyunga",
    
    # Time & Days & Relatives
    "iniku", "iniki", "inraiku", "indraiku", "naalaiki", "naalaki", "naalai",
    "marunaal", "munnal", "kaalai", "kaalaila", "madhiyam", "mathiyam",
    "saayandhram", "sayanthiram", "saayangaalam", "iravu", "mani", "manikku",
    "neram", "kizhamai", "thingal", "sevvai", "budhan", "vyazhan", "velli",
    "sani", "gnaayiru", "vara", "varam", "maasam", "varusham",
    
    # Medical & Appointment terms in Tanglish
    "maruthuvar", "maruthuvam", "noi", "valikithu", "vali", "udambu", "udambu mudiyala",
    "kaachal", "irumal", "sali", "thalai vali", "vayiru", "raththam", "parithothanai",
    "pal", "marunthu", "marundhu", "munpathivu", "munpadhivu", "pathivu", "padhivu",
    "sari", "kandippa", "seri",
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

# English distinct words that indicate English preference
ENGLISH_DISTINCT_WORDS = {
    "appointment", "consultation", "doctor", "physician", "cardiology",
    "pediatrician", "schedule", "reschedule", "cancel", "booking",
    "available", "slots", "morning", "afternoon", "evening", "tomorrow",
    "today", "hospital", "clinic", "checkup", "please", "thank", "hello",
    "switch", "english", "speak", "assistance",
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


def detect_language(text: str, current_lang: str = "en-IN") -> str:
    """Classify the user's speech input into:
    - 'te-IN' (Telugu in Telugu script)
    - 'te-Latn' (Teluglish: Telugu written in Latin script)
    - 'ta-IN' (Tamil in Tamil script)
    - 'ta-Latn' (Tanglish: Tamil written in Latin script)
    - 'en-IN' (English)
    
    Maintains the caller's preferred language throughout the conversation.
    Supports code-mixing and does not treat borrowed English technical words
    (e.g. 'doctor', 'appointment', 'slot', 'cardiology') as a language switch.
    """
    if not text or not text.strip():
        return current_lang

    clean = text.strip()

    # 1. Direct Telugu Unicode script check
    if is_telugu_script(clean):
        return "te-IN"

    # 2. Direct Tamil Unicode script check
    if is_tamil_script(clean):
        return "ta-IN"

    # 3. Phonetic Latin Script Analysis (Tanglish / Teluglish / English)
    tokens = [w.lower() for w in re.findall(r"\b[a-zA-Z]+\b", clean)]
    if not tokens:
        return current_lang

    # --- Tanglish Scoring ---
    tanglish_hits = sum(1 for t in tokens if t in TANGLISH_VOCABULARY)
    tanglish_suffix_hits = sum(
        1 for t in tokens
        if len(t) > 4 and (
            t.endswith("num")
            or t.endswith("unga")
            or t.endswith("la")
            or t.endswith("ala")
            or t.endswith("kku")
        )
    )
    total_tanglish_score = tanglish_hits * 2 + tanglish_suffix_hits

    # --- Teluglish Scoring ---
    teluglish_hits = sum(1 for t in tokens if t in TELUGU_LATIN_VOCABULARY)
    teluglish_suffix_hits = sum(
        1 for t in tokens
        if len(t) > 4 and (
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

    # Check Teluglish preference
    if total_teluglish_score > 0 and total_teluglish_score >= total_tanglish_score:
        if teluglish_hits >= 1 or total_teluglish_score >= 2 or (len(tokens) <= 3 and total_teluglish_score >= 1):
            return "te-Latn"

    # Check Tanglish preference
    if total_tanglish_score > 0 and total_tanglish_score > total_teluglish_score:
        if tanglish_hits >= 1 or total_tanglish_score >= 2 or (len(tokens) <= 3 and total_tanglish_score >= 1):
            return "ta-Latn"

    # 4. Caller persistence when previously speaking Telugu or Tamil:
    # Preserve preferred language unless caller explicitly switches with clear English sentences
    if current_lang in ("te-Latn", "te-IN"):
        english_hits = sum(1 for t in tokens if t in ENGLISH_DISTINCT_WORDS)
        # If caller spoke English loanwords (e.g. "doctor", "appointment", "tomorrow 10 am"),
        # do NOT switch unless there are multiple English words, zero Telugu words, and explicit switch
        if english_hits >= 3 and total_teluglish_score == 0 and total_tanglish_score == 0:
            return "en-IN"
        return current_lang

    if current_lang in ("ta-Latn", "ta-IN"):
        english_hits = sum(1 for t in tokens if t in ENGLISH_DISTINCT_WORDS)
        if english_hits >= 3 and total_tanglish_score == 0 and total_teluglish_score == 0:
            return "en-IN"
        return current_lang

    # 5. Default to standard English
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
