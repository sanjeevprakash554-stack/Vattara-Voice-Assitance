"""Central Voice Identity and Language Management Registry.

Manages:
- Persistent receptionist voice identity per language for Sarvam AI and ElevenLabs.
- Deterministic voice-to-language mapping ensuring identical voice across consecutive responses.
- Validation ensuring incompatible speakers are never sent to TTS providers.
- Single source of truth for language and speaker resolution across streaming sessions.
"""

from dataclasses import dataclass, field
import re
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.services.ai.language_detector import detect_language

logger = get_logger(__name__)

# Valid Sarvam bulbul:v4-flash model-compatible personas:
# Consistent calm, warm, professional receptionist persona across languages:
# Tamil & Tanglish: gokul_ta_narration, English: shubh_en_narration_gentle, Telugu: tarun_te_narration
SARVAM_DEFAULT_VOICE_MAP: dict[str, str] = {
    "ta-IN": "gokul_ta_narration",
    "ta-Latn": "gokul_ta_narration",
    "en-IN": "shubh_en_narration_gentle",
    "en-US": "shubh_en_narration_gentle",
    "te-IN": "tarun_te_narration",
    "te-Latn": "tarun_te_narration",
}

# ElevenLabs Multilingual v2 fallback voices
ELEVENLABS_DEFAULT_VOICE_MAP: dict[str, str] = {
    "ta-IN": "EXAVITQu4vr4xnSDxMaL",  # Sarah / configured multilingual voice
    "ta-Latn": "EXAVITQu4vr4xnSDxMaL",
    "en-IN": "EXAVITQu4vr4xnSDxMaL",
    "en-US": "EXAVITQu4vr4xnSDxMaL",
    "te-IN": "EXAVITQu4vr4xnSDxMaL",
    "te-Latn": "EXAVITQu4vr4xnSDxMaL",
}


@dataclass
class VoiceIdentityState:
    """Encapsulates the single source of truth for active language and voice identity in a call session."""
    detected_language: str = "en-IN"
    preferred_language: str = "en-IN"
    active_response_language: str = "en-IN"
    active_tts_language: str = "en-IN"
    active_tts_speaker: str = "gokul_ta_narration"
    custom_voice_map: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "detected_language": self.detected_language,
            "preferred_language": self.preferred_language,
            "active_response_language": self.active_response_language,
            "active_tts_language": self.active_tts_language,
            "active_tts_speaker": self.active_tts_speaker,
        }


def resolve_canonical_language(lang_str: str | None, default: str = "en-IN") -> str:
    """Normalize language code or string to canonical BCP-47 identifier."""
    if not lang_str:
        return default
    clean = lang_str.strip().lower()
    if clean.startswith("ta-latn") or clean == "tanglish":
        return "ta-Latn"
    if clean.startswith("ta") or clean == "tamil":
        return "ta-IN"
    if clean.startswith("te-latn") or clean == "teluglish":
        return "te-Latn"
    if clean.startswith("te") or clean == "telugu":
        return "te-IN"
    if clean.startswith("en") or clean == "english":
        return "en-IN"
    if clean in ("bilingual", "multi", "auto"):
        return default
    return default


def get_voice_for_language(
    language: str,
    provider: str = "sarvam",
    custom_voice: str | None = None,
) -> str:
    """Resolve the persistent voice persona for a given language and provider.
    
    Guarantees:
    - Never randomly selects a voice.
    - Reuses the configured voice persona across consecutive turns in that language.
    """
    canonical_lang = resolve_canonical_language(language)
    prov = (provider or "sarvam").lower()

    if prov == "sarvam":
        if custom_voice and custom_voice.strip():
            cv = custom_voice.strip()
            if cv.lower() != "ratan":
                return cv
            # Plain 'ratan' causes HTTP 422 on bulbul:v4-flash; map to language-specific model speaker
            return SARVAM_DEFAULT_VOICE_MAP.get(canonical_lang, "gokul_ta_narration")

        # 1. Language-specific configured speakers take precedence
        if canonical_lang.startswith("ta"):
            env_spk = getattr(settings, "SARVAM_TAMIL_SPEAKER", None)
            if env_spk and env_spk.strip() and env_spk.strip().lower() != "ratan":
                return env_spk.strip()
            return "gokul_ta_narration"
        elif canonical_lang.startswith("te"):
            env_spk = getattr(settings, "SARVAM_TELUGU_SPEAKER", None)
            if env_spk and env_spk.strip() and env_spk.strip().lower() != "ratan":
                return env_spk.strip()
            return "tarun_te_narration"
        elif canonical_lang.startswith("en"):
            env_spk = getattr(settings, "SARVAM_ENGLISH_SPEAKER", None)
            if env_spk and env_spk.strip() and env_spk.strip().lower() != "ratan":
                return env_spk.strip()
            return "shubh_en_narration_gentle"

        # 2. Central configured Sarvam voice ID
        central_voice = getattr(settings, "SARVAM_VOICE_ID", None)
        if central_voice and central_voice.strip() and central_voice.strip().lower() != "ratan":
            return central_voice.strip()

        # 3. Default voice map fallback
        return SARVAM_DEFAULT_VOICE_MAP.get(canonical_lang, "gokul_ta_narration")

    elif prov == "elevenlabs":
        if custom_voice and custom_voice.strip():
            return custom_voice.strip()

        if canonical_lang.startswith("ta"):
            env_voice = getattr(settings, "ELEVENLABS_VOICE_ID_TA", None)
            if env_voice and env_voice.strip():
                return env_voice.strip()
        elif canonical_lang.startswith("te"):
            env_voice = getattr(settings, "ELEVENLABS_VOICE_ID_TE", None)
            if env_voice and env_voice.strip():
                return env_voice.strip()
        elif canonical_lang.startswith("en"):
            env_voice = getattr(settings, "ELEVENLABS_VOICE_ID_EN", None)
            if env_voice and env_voice.strip():
                return env_voice.strip()

        base_id = getattr(settings, "ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")
        return ELEVENLABS_DEFAULT_VOICE_MAP.get(canonical_lang, base_id)

    return "gokul_ta_narration"


def detect_script_language_from_text(text: str) -> str | None:
    """Inspect text characters directly to determine native script language.
    
    Returns:
    - 'te-IN' if Telugu script is present.
    - 'ta-IN' if Tamil script is present.
    - None if only Latin / punctuation / numbers are present.
    """
    if not text:
        return None
    if re.search(r"[\u0C00-\u0C7F]", text):
        return "te-IN"
    if re.search(r"[\u0B80-\u0BFF]", text):
        return "ta-IN"
    return None


def synchronize_voice_and_language(
    response_text: str,
    session_language: str,
    provider: str = "sarvam",
    custom_voice: str | None = None,
) -> tuple[str, str, str]:
    """Single source of truth synchronizing response text, TTS language, and TTS speaker.

    Guarantees:
    - If the LLM generates Telugu script, active_tts_language is forced to 'te-IN'.
    - If the LLM generates Tamil script, active_tts_language is forced to 'ta-IN'.
    - Never sends Telugu text with an English TTS language or speaker.
    - Never sends Tamil text with an English TTS language or speaker.
    - Returns (active_response_language, active_tts_language, active_tts_speaker).
    """
    script_lang = detect_script_language_from_text(response_text)
    if script_lang:
        # Preserve established language continuity against accidental cross-language script pollution
        canonical_session = resolve_canonical_language(session_language)
        if canonical_session in ("ta-IN", "ta-Latn") and script_lang.startswith("te"):
            logger.warning(
                "Prevented Telugu voice hijack on established Tamil session: script_lang=%s, session_lang=%s",
                script_lang,
                session_language,
            )
            active_response_lang = canonical_session
            active_tts_lang = "ta-IN"
        elif canonical_session in ("te-IN", "te-Latn") and script_lang.startswith("ta"):
            logger.warning(
                "Prevented Tamil voice hijack on established Telugu session: script_lang=%s, session_lang=%s",
                script_lang,
                session_language,
            )
            active_response_lang = canonical_session
            active_tts_lang = "te-IN"
        else:
            active_response_lang = script_lang
            active_tts_lang = script_lang
    else:
        # For non-Indic script text (Latin text), evaluate whether response text is Tanglish, Teluglish, or English
        detected_text_lang = detect_language(response_text, current_lang=session_language)
        active_response_lang = resolve_canonical_language(detected_text_lang or session_language)
        # For Sarvam, Tanglish routes to ta-IN language code with Tamil speaker
        if active_response_lang == "ta-Latn":
            active_tts_lang = "ta-IN"
        elif active_response_lang == "te-Latn":
            active_tts_lang = "te-IN"
        else:
            active_tts_lang = active_response_lang

    active_speaker = get_voice_for_language(
        language=active_tts_lang,
        provider=provider,
        custom_voice=custom_voice,
    )

    logger.debug(
        "Synchronized voice & language: response_lang=%s, tts_lang=%s, speaker=%s (provider=%s)",
        active_response_lang,
        active_tts_lang,
        active_speaker,
        provider,
    )
    return active_response_lang, active_tts_lang, active_speaker
