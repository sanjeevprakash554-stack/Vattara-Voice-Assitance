"""Audio encoding, decoding, transcoding, and VAD utilities for real-time telephony streaming.

Compliant with:
- ITU-T G.711 standard mu-law (PCMU) companding.
- Twilio Media Streams format (8000 Hz, 8-bit mono mu-law).
- Deepgram / Whisper / ElevenLabs formats (16000 Hz / 24000 Hz 16-bit linear PCM and WAV containers).
- Pure-Python implementation compatible with Python 3.13 (no reliance on removed audioop).
"""

import base64
import math
import struct

# ==============================================================================
# ITU-T G.711 Mu-Law Lookup Tables
# ==============================================================================

# Precompute standard 256-entry table for decoding 8-bit mu-law to 16-bit signed linear PCM
MULAW_TO_LINEAR_TABLE: list[int] = []
for _i in range(256):
    _inv = ~_i & 0xFF
    _sign = -1 if (_inv & 0x80) else 1
    _exponent = (_inv >> 4) & 0x07
    _mantissa = _inv & 0x0F
    _sample = ((_mantissa << 3) + 0x84) << _exponent
    _sample -= 0x84
    MULAW_TO_LINEAR_TABLE.append(_sign * _sample)

# Mu-law companding constants
BIAS = 0x84
CLIP = 32635


def mulaw_to_pcm16(data: bytes) -> bytes:
    """Decode 8-bit ITU-T G.711 mu-law audio bytes into 16-bit signed linear PCM bytes (little-endian)."""
    if not data:
        return b""
    samples = [MULAW_TO_LINEAR_TABLE[b] for b in data]
    return struct.pack(f"<{len(samples)}h", *samples)


def pcm16_to_mulaw(data: bytes) -> bytes:
    """Encode 16-bit signed linear PCM bytes (little-endian) into 8-bit ITU-T G.711 mu-law bytes."""
    if not data:
        return b""
    num_samples = len(data) // 2
    if num_samples == 0:
        return b""

    samples = struct.unpack(f"<{num_samples}h", data[: num_samples * 2])
    out = bytearray(num_samples)

    for idx, sample in enumerate(samples):
        sign = 0x80 if sample < 0 else 0
        if sample < 0:
            sample = -sample
        if sample > CLIP:
            sample = CLIP
        sample += BIAS

        exponent = 7
        for exp in range(7):
            if sample <= (0x1F << (exp + 3)):
                exponent = exp
                break

        mantissa = (sample >> (exponent + 3)) & 0x0F
        out[idx] = ~(sign | (exponent << 4) | mantissa) & 0xFF

    return bytes(out)


def base64_to_mulaw(b64_str: str) -> bytes:
    """Decode base64 string from Twilio media payload into raw mu-law bytes."""
    if not b64_str:
        return b""
    return base64.b64decode(b64_str)


def mulaw_to_base64(mulaw_bytes: bytes) -> str:
    """Encode raw mu-law bytes into base64 ASCII string for Twilio media payload."""
    if not mulaw_bytes:
        return ""
    return base64.b64encode(mulaw_bytes).decode("ascii")


def resample_pcm16(data: bytes, orig_sr: int, target_sr: int) -> bytes:
    """Resample 16-bit signed mono linear PCM audio between common telephony sample rates.
    
    Supported transitions:
    - 8000 Hz -> 16000 Hz (2x upsampling via linear interpolation).
    - 16000 Hz -> 8000 Hz (2x decimation).
    - 24000 Hz -> 8000 Hz (3x decimation).
    - Arbitrary integer/fractional ratios using linear interpolation.
    """
    if not data or orig_sr == target_sr:
        return data

    num_samples = len(data) // 2
    if num_samples < 2:
        return data

    samples = struct.unpack(f"<{num_samples}h", data[: num_samples * 2])

    # Direct 2x upsampling optimization (8kHz -> 16kHz)
    if orig_sr == 8000 and target_sr == 16000:
        out_samples: list[int] = []
        for i in range(num_samples - 1):
            s1 = samples[i]
            s2 = samples[i + 1]
            out_samples.append(s1)
            out_samples.append((s1 + s2) // 2)
        out_samples.append(samples[-1])
        out_samples.append(samples[-1])
        return struct.pack(f"<{len(out_samples)}h", *out_samples)

    # Direct 2x decimation optimization (16kHz -> 8kHz)
    if orig_sr == 16000 and target_sr == 8000:
        out_samples = [samples[i] for i in range(0, num_samples, 2)]
        return struct.pack(f"<{len(out_samples)}h", *out_samples)

    # Direct 3x decimation optimization (24kHz -> 8kHz)
    if orig_sr == 24000 and target_sr == 8000:
        out_samples = [samples[i] for i in range(0, num_samples, 3)]
        return struct.pack(f"<{len(out_samples)}h", *out_samples)

    # General fractional resampler
    ratio = target_sr / orig_sr
    target_count = int(num_samples * ratio)
    out_samples = []

    for i in range(target_count):
        orig_index = i / ratio
        idx1 = int(orig_index)
        idx2 = min(idx1 + 1, num_samples - 1)
        frac = orig_index - idx1
        interpolated = int(samples[idx1] * (1.0 - frac) + samples[idx2] * frac)
        out_samples.append(max(-32768, min(32767, interpolated)))

    return struct.pack(f"<{len(out_samples)}h", *out_samples)


def compute_rms_energy(pcm16_bytes: bytes) -> float:
    """Compute Root-Mean-Square (RMS) amplitude of 16-bit signed linear PCM audio."""
    if not pcm16_bytes or len(pcm16_bytes) < 2:
        return 0.0

    num_samples = len(pcm16_bytes) // 2
    samples = struct.unpack(f"<{num_samples}h", pcm16_bytes[: num_samples * 2])

    sum_squares = sum(s * s for s in samples)
    mean_square = sum_squares / num_samples
    return math.sqrt(mean_square)


def is_speech_active(energy: float, threshold: float = 300.0) -> bool:
    """Classify audio frame as human speech or background noise/silence."""
    return energy >= threshold


def generate_wav_container(
    pcm16_bytes: bytes,
    sample_rate: int = 8000,
    channels: int = 1,
) -> bytes:
    """Wrap raw 16-bit linear PCM audio into a standard 44-byte RIFF/WAVE container."""
    byte_rate = sample_rate * channels * 2
    block_align = channels * 2
    data_size = len(pcm16_bytes)
    riff_chunk_size = 36 + data_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        riff_chunk_size,
        b"WAVE",
        b"fmt ",
        16,  # Subchunk1Size for PCM
        1,   # AudioFormat 1 = PCM
        channels,
        sample_rate,
        byte_rate,
        block_align,
        16,  # BitsPerSample
        b"data",
        data_size,
    )
    return header + pcm16_bytes


def chunk_audio(data: bytes, chunk_size: int = 160) -> list[bytes]:
    """Slice raw audio buffer into fixed telephony packet frames (e.g. 160 bytes = 20ms mu-law)."""
    if not data or chunk_size <= 0:
        return []
    return [data[i : i + chunk_size] for i in range(0, len(data), chunk_size)]
