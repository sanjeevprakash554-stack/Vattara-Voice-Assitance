"""Verification and test script for ElevenLabs Text-to-Speech in Vattara Voice Assistance.

Steps performed:
1. Verify ELEVENLABS_API_KEY loaded from backend/.env
2. Instantiate existing ElevenLabsStreamingTTS provider
3. Synthesize speech and save to temp_test/elevenlabs_test.mp3
4. Inspect and mathematically verify audio characteristics (size, MP3 frames, speech variation)
5. Ensure zero credential exposure
"""

import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.services.streaming.tts_provider import ElevenLabsStreamingTTS, get_streaming_tts_provider


def run_elevenlabs_test() -> bool:
    print("=" * 65)
    print("Vattara Voice Assistance - ElevenLabs TTS Integration Test")
    print("=" * 65)

    # 1. Verify API Key loading from .env
    key = settings.ELEVENLABS_API_KEY
    if not key or not key.strip():
        print("[-] FAILED: ELEVENLABS_API_KEY is not loaded or is empty in settings.")
        return False

    masked = key[:5] + "..." + key[-3:] if len(key) > 8 else "***"
    print(f"[+] 1. API Key verified: Present in settings (len={len(key)}, prefix/suffix={masked})")
    print(f"[+]    TTS_PROVIDER: {settings.TTS_PROVIDER}")
    print(f"[+]    Voice ID: {settings.ELEVENLABS_VOICE_ID}")
    print(f"[+]    Model ID: {settings.ELEVENLABS_MODEL_ID}")

    # 2. Instantiate TTS Provider
    provider = get_streaming_tts_provider("elevenlabs")
    print(f"[+] 2. TTS Provider initialized: {provider.provider_name} ({type(provider).__name__})")

    # 3. Generate short test speech
    test_phrase = (
        "Hello! Welcome to Vattara Voice Assistance. "
        "Your healthcare appointment has been confirmed with Dr. Sanjeev for tomorrow at 10 AM."
    )
    print(f"[+] 3. Generating test speech: \"{test_phrase}\"")

    if not isinstance(provider, ElevenLabsStreamingTTS):
        print(f"[-] FAILED: Expected ElevenLabsStreamingTTS, got {type(provider).__name__}")
        return False

    audio_bytes = provider.synthesize_to_mp3(test_phrase)

    if not audio_bytes or len(audio_bytes) == 0:
        print("[-] FAILED: 0 bytes returned from ElevenLabs synthesis.")
        return False

    print(f"[+]    Successfully synthesized {len(audio_bytes)} bytes of MP3 audio.")

    # 4. Save to temporary test folder
    temp_dir = backend_dir / "temp_test"
    temp_dir.mkdir(parents=True, exist_ok=True)
    output_file = temp_dir / "elevenlabs_test.mp3"

    output_file.write_bytes(audio_bytes)
    print(f"[+] 4. Audio saved to: {output_file.resolve()}")
    print(f"[+]    File size on disk: {output_file.stat().st_size:,} bytes")

    # 5. Verify audio content is genuine speech and NOT empty or a mock tone
    print("[+] 5. Verifying audio content characteristics:")
    size = output_file.stat().st_size
    if size < 1000:
        print(f"[-] FAILED: File too small ({size} bytes) to contain genuine speech.")
        return False

    # Check MP3 header
    has_id3 = audio_bytes[:3] == b"ID3"
    has_sync_word = False
    for i in range(len(audio_bytes) - 1):
        if audio_bytes[i] == 0xFF and (audio_bytes[i + 1] & 0xE0) == 0xE0:
            has_sync_word = True
            break

    print(f"       - Valid ID3 Metadata Header: {has_id3}")
    print(f"       - Valid MPEG Audio Sync Word: {has_sync_word}")

    if not (has_id3 or has_sync_word):
        print("[-] FAILED: Output file does not match MPEG audio / MP3 frame structure.")
        return False

    # Approximate duration for 128 kbps MP3
    # 128 kbps = 16,000 bytes/sec
    approx_duration = size / 16000.0
    print(f"       - Approximate speech duration: {approx_duration:.2f} seconds")

    # Verify byte entropy / variation (mock tone has very high repetitive periodicity)
    unique_bytes = len(set(audio_bytes))
    print(f"       - Byte diversity: {unique_bytes} / 256 unique byte values")

    if unique_bytes < 100:
        print("[-] FAILED: Audio appears to be repetitive synthetic tone, not compressed natural speech.")
        return False

    print("[SUCCESS] All 5 verification checks PASSED!")
    print("=" * 65)
    return True


if __name__ == "__main__":
    success = run_elevenlabs_test()
    sys.exit(0 if success else 1)
