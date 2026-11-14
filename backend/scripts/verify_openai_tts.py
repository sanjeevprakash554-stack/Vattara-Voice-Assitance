"""Verification script for OpenAI TTS-1 integration in Vattara Voice Assistance.

Tests:
1. Configuration loading from app.core.config.settings
2. Key sanitization (whitespace, quotes, Bearer prefix)
3. HTTP POST to https://api.openai.com/v1/audio/speech
4. Downsampling from 24kHz raw PCM to 8kHz G.711 mu-law
5. Returns non-empty bytes
"""

import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.services.streaming.tts_provider import OpenAIStreamingTTS


def verify_tts(custom_key: str | None = None) -> bool:
    print("=" * 60)
    print("Vattara Voice Assistance - OpenAI TTS Verification")
    print("=" * 60)

    tts = OpenAIStreamingTTS(api_key=custom_key)
    if not tts.api_key:
        print("[-] Error: OPENAI_API_KEY is not configured or is empty.")
        print("    Please configure OPENAI_API_KEY in backend/.env")
        return False

    masked_key = tts.api_key[:7] + "..." + tts.api_key[-3:] if len(tts.api_key) > 10 else "***"
    print(f"[+] Using configured key prefix/suffix: {masked_key} (len={len(tts.api_key)})")
    print(f"[+] Provider: {tts.provider_name}, Model: {tts.model}")

    test_phrase = "Hello! Welcome to Vattara Voice Assistance. Your appointment is confirmed."
    print(f"[+] Synthesizing test phrase: '{test_phrase}'")

    audio_bytes = tts.synthesize_to_mulaw(test_phrase, language="en-IN")

    if audio_bytes and len(audio_bytes) > 0:
        duration_sec = len(audio_bytes) / 8000.0
        print(f"[SUCCESS] Synthesized {len(audio_bytes)} bytes of 8kHz mu-law audio ({duration_sec:.2f}s).")
        return True
    else:
        print("[-] Failure: 0 audio bytes returned. Check credentials and network connectivity.")
        return False


if __name__ == "__main__":
    key_override = sys.argv[1] if len(sys.argv) > 1 else None
    success = verify_tts(key_override)
    sys.exit(0 if success else 1)
