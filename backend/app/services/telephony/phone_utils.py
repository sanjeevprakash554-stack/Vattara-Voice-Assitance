"""Canonical telephony phone number normalization and validation utilities.

Ensures that all Indian mobile numbers are normalized consistently to E.164 (+91 followed by exactly 10 digits).
Strictly adheres to:
- +91XXXXXXXXXX -> +91XXXXXXXXXX
- 91XXXXXXXXXX  -> +91XXXXXXXXXX
- 0XXXXXXXXXX   -> +91XXXXXXXXXX
- XXXXXXXXXX    -> +91XXXXXXXXXX
- Never silently truncate or remove digits from invalid-length numbers.
- Preprocesses and cleans speech transcription noise (e.g. Deepgram time artifacts like 09:04 -> 9 04).
"""

import re
from typing import Any

# Spoken digit mapping for English, Tamil (Unicode & Tanglish), and Telugu (Unicode & Teluglish)
SPOKEN_DIGIT_MAP: dict[str, str] = {
    # English digits & equivalents
    "zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    # Tamil Unicode
    "பூஜ்ஜியம்": "0", "சுழி": "0", "ஜீரோ": "0", "ஒன்று": "1", "ஒன்னு": "1",
    "இரண்டு": "2", "ரெண்டு": "2", "மூன்று": "3", "மூணு": "3", "நான்கு": "4",
    "நாலு": "4", "ஐந்து": "5", "அஞ்சு": "5", "ஆறு": "6", "ஏழு": "7",
    "எட்டு": "8", "ஒன்பது": "9",
    # Tamil Phonetic / Tanglish
    "poojiyam": "0", "suzhi": "0", "ondru": "1", "onnu": "1", "onn": "1",
    "irandu": "2", "rendu": "2", "moondru": "3", "moonu": "3", "naangu": "4",
    "naalu": "4", "aindhu": "5", "ainthu": "5", "anju": "5", "aaru": "6",
    "ezhu": "7", "yezhu": "7", "ettu": "8", "onbadhu": "9", "onpathu": "9",
    # Telugu Unicode
    "సున్నా": "0", "ఒకటి": "1", "రెండు": "2", "మూడు": "3", "నాలుగు": "4",
    "ఐదు": "5", "ఆరు": "6", "ఏడు": "7", "ఎనిమిది": "8", "తొమ్మిది": "9",
    # Telugu Phonetic / Teluglish
    "sunna": "0", "okati": "1", "moodu": "3", "naalugu": "4", "aidu": "5",
    "yedu": "7", "edu": "7", "enimidi": "8", "tommidi": "9", "thommidi": "9",
}


def clean_phone_digits(phone: str | None) -> str:
    """Extract all numeric digits from phone string for relaxed matching."""
    if not phone:
        return ""
    return re.sub(r"\D", "", str(phone))


def sanitize_transcription_noise(text: str | None) -> str:
    """Clean common STT transcription artifacts from spoken phone utterances.
    
    Specifically handles:
    - Deepgram smart-formatting artifact converting spoken digits '9 0 4' into time '09:04' (with spurious leading zero).
    - Colons, hyphens, slashes, and periods between digits.
    - Common spoken multipliers (e.g., 'double nine' -> '9 9', 'triple eight' -> '8 8 8').
    """
    if not text:
        return ""
    raw = text.lower().strip()

    # 1. Detect Deepgram time formatting artifacts with spurious leading zeros: e.g. "09:04" -> "9 04"
    # When surrounded by digit context or phone words, a leading zero is an artifact of time formatting
    raw = re.sub(r"\b0([1-9]):(\d{2})\b", r"\1 \2", raw)

    # 2. Separate any remaining colon-separated numbers e.g. "9:04" -> "9 04", "10:30" -> "10 30"
    raw = re.sub(r"(\d+):(\d+)", r"\1 \2", raw)

    # 3. Handle multipliers
    raw = re.sub(r"\b(?:double|இரட்டை)\s+([a-z0-9\u0B80-\u0BFF\u0C00-\u0C7F]+)", r"\1 \1", raw)
    raw = re.sub(r"\b(?:triple|மூன்று\s+முறை)\s+([a-z0-9\u0B80-\u0BFF\u0C00-\u0C7F]+)", r"\1 \1 \1", raw)

    # 4. Map spoken words to numeric digits
    tokens = re.split(r"[\s,.-]+", raw)
    normalized_tokens = [SPOKEN_DIGIT_MAP.get(tok, tok) for tok in tokens if tok]
    return " ".join(normalized_tokens)


def normalize_indian_mobile_number(phone: str | None) -> str | None:
    """Normalize any valid Indian mobile phone number into canonical E.164 format (+91 followed by 10 digits).
    
    Accepts:
    - '+91XXXXXXXXXX' (e.g. '+917904743468')
    - '91XXXXXXXXXX'  (e.g. '917904743468')
    - '0XXXXXXXXXX'   (e.g. '07904743468')
    - 'XXXXXXXXXX'    (e.g. '7904743468')
    - Strings containing formatting characters (+, -, ., spaces, parentheses).

    Validation rules:
    - The 10-digit mobile number MUST begin with 6, 7, 8, or 9 (National Numbering Plan of India).
    - NEVER silently truncate or remove digits from invalid-length numbers (e.g., 11 digits not starting with 0, 9 digits, 13 digits).
    - Returns normalized '+91XXXXXXXXXX' on valid Indian mobile numbers.
    - Returns None on invalid length, invalid prefix, or unparseable input.
    """
    if not phone:
        return None
    raw = str(phone).strip()
    if not raw:
        return None

    # Preprocess speech transcription noise if present
    cleaned = sanitize_transcription_noise(raw)

    # Extract all digits
    digits = re.sub(r"\D", "", cleaned)
    if not digits:
        return None

    # Case 1: 12 digits starting with '91'
    if len(digits) == 12 and digits.startswith("91"):
        mobile_part = digits[2:]
        if mobile_part[0] in "6789":
            return f"+91{mobile_part}"
        return None

    # Case 2: 11 digits starting with '0' (trunk prefix 0)
    if len(digits) == 11 and digits.startswith("0"):
        mobile_part = digits[1:]
        if mobile_part[0] in "6789":
            return f"+91{mobile_part}"
        return None

    # Case 3: Exactly 10 digits starting with [6-9]
    if len(digits) == 10 and digits[0] in "6789":
        return f"+91{digits}"

    # Invalid-length numbers (e.g. 11 digits starting with [1-9], 9 digits, 8 digits, >12 digits)
    # NEVER silently truncate!
    return None


def extract_phone_number(text: str | None) -> str | None:
    """Extract and normalize a valid Indian mobile number from speech transcript in Tamil, English, or Telugu."""
    if not text:
        return None

    cleaned_text = sanitize_transcription_noise(text)

    # 1. Look for sequences with +91 or 91 country code followed by 10 digits starting with [6-9]
    match = re.search(r"(?:\+?91[\s.-]*)?[6-9](?:[\s.-]*\d){9}\b", cleaned_text)
    if match:
        norm = normalize_indian_mobile_number(match.group(0))
        if norm:
            return norm

    # 2. Look for 11-digit numbers with leading 0 trunk prefix
    match_zero = re.search(r"\b0[6-9](?:[\s.-]*\d){9}\b", cleaned_text)
    if match_zero:
        norm = normalize_indian_mobile_number(match_zero.group(0))
        if norm:
            return norm

    # 3. Look for any contiguous digit sequence and attempt normalization
    digit_sequences = re.findall(r"\b\d[\d\s.-]{8,15}\d\b", cleaned_text)
    for seq in digit_sequences:
        norm = normalize_indian_mobile_number(seq)
        if norm:
            return norm

    return None
