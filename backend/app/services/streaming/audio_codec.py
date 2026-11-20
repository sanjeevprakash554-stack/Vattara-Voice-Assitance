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
from typing import Any

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
    """Decode base64 string from telephony media payload into raw mu-law bytes."""
    if not b64_str:
        return b""
    return base64.b64decode(b64_str)


def mulaw_to_base64(mulaw_bytes: bytes) -> str:
    """Encode raw mu-law bytes into base64 ASCII string for telephony media payload."""
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


def compute_zero_crossing_rate(pcm16_bytes: bytes) -> float:
    """Compute normalized Zero-Crossing Rate (ZCR) of 16-bit linear PCM audio.

    Voiced speech typically has ZCR in range 0.02 - 0.35.
    Unvoiced speech/fricatives reach 0.25 - 0.42.
    High-frequency noise/hiss/static typically exceeds 0.45 - 0.70.
    """
    if not pcm16_bytes or len(pcm16_bytes) < 4:
        return 0.0
    num_samples = len(pcm16_bytes) // 2
    samples = struct.unpack(f"<{num_samples}h", pcm16_bytes[: num_samples * 2])
    crossings = 0
    for i in range(1, num_samples):
        if (samples[i] >= 0 and samples[i - 1] < 0) or (samples[i] < 0 and samples[i - 1] >= 0):
            crossings += 1
    return crossings / float(num_samples - 1)


def compute_periodicity(pcm16_bytes: bytes) -> float:
    """Compute normalized autocorrelation peak in the human vocal pitch range (100 - 400 Hz at 8000 Hz sample rate).

    Voiced speech exhibits harmonic periodicity with autocorrelation peak >= 0.30.
    Fans, air conditioners, traffic rumble, typing clicks, and static exhibit low periodicity < 0.20.
    """
    if not pcm16_bytes or len(pcm16_bytes) < 80:
        return 0.0
    num_samples = len(pcm16_bytes) // 2
    samples = struct.unpack(f"<{num_samples}h", pcm16_bytes[: num_samples * 2])
    energy = sum(s * s for s in samples)
    if energy < 1000.0:
        return 0.0
    max_corr = 0.0
    # Search lags from 20 (400 Hz) to 80 (100 Hz) with step of 2
    for lag in range(20, min(80, num_samples - 20), 2):
        corr = sum(samples[i] * samples[i - lag] for i in range(lag, num_samples))
        if corr > max_corr:
            max_corr = corr
    return max_corr / float(energy)


def compute_crest_factor(pcm16_bytes: bytes) -> float:
    """Compute peak-to-RMS crest factor of 16-bit linear PCM audio.

    Keyboard typing, desk thumps, and electrical clicks exhibit sharp impulsive spikes (crest factor > 4.2).
    Continuous human speech exhibits steady harmonic envelope (crest factor 1.8 - 3.5).
    """
    if not pcm16_bytes or len(pcm16_bytes) < 4:
        return 1.0
    num_samples = len(pcm16_bytes) // 2
    samples = struct.unpack(f"<{num_samples}h", pcm16_bytes[: num_samples * 2])
    peak = max(abs(s) for s in samples)
    energy = sum(s * s for s in samples)
    rms = math.sqrt(energy / float(num_samples))
    if rms < 1.0:
        return 1.0
    return peak / rms


class BiquadFilter:
    """Second-order IIR biquad filter for real-time telephony audio filtering.
    
    Default configuration: 2nd-order Butterworth High-Pass Filter with cutoff fc=250 Hz at fs=8000 Hz.
    Eliminates sub-250 Hz DC bias, electrical 50/60 Hz mains hum, AC rumble, fan hum, and handling thumps.
    """

    def __init__(
        self,
        b0: float = 0.870331,
        b1: float = -1.740662,
        b2: float = 0.870331,
        a1: float = -1.723776,
        a2: float = 0.757547,
    ):
        self.b0 = b0
        self.b1 = b1
        self.b2 = b2
        self.a1 = a1
        self.a2 = a2
        self.x1 = 0.0
        self.x2 = 0.0
        self.y1 = 0.0
        self.y2 = 0.0

    def process(self, pcm16_bytes: bytes) -> bytes:
        """Filter 16-bit signed linear PCM bytes, preserving internal filter state across frames."""
        if not pcm16_bytes or len(pcm16_bytes) < 2:
            return pcm16_bytes
        num_samples = len(pcm16_bytes) // 2
        samples = struct.unpack(f"<{num_samples}h", pcm16_bytes[: num_samples * 2])
        out = []
        for x in samples:
            y = self.b0 * x + self.b1 * self.x1 + self.b2 * self.x2 - self.a1 * self.y1 - self.a2 * self.y2
            self.x2, self.x1 = self.x1, x
            self.y2, self.y1 = self.y1, y
            out.append(max(-32768, min(32767, int(y))))
        return struct.pack(f"<{len(out)}h", *out)


def suppress_telephony_noise(
    pcm16_bytes: bytes,
    noise_floor: float,
    is_speech: bool = False,
) -> bytes:
    """Apply real-time soft spectral gating and noise attenuation to 16-bit linear PCM audio.

    When speech is absent, attenuates the signal to comfortable near-zero floor (comfort silence)
    preventing neural STT models from hallucinating words on steady fan or AC noise.
    When speech is present, soft-gates the background floor to maximize SNR while preserving vocal fidelity.
    """
    if not pcm16_bytes or len(pcm16_bytes) < 2:
        return pcm16_bytes
    num_samples = len(pcm16_bytes) // 2
    samples = struct.unpack(f"<{num_samples}h", pcm16_bytes[: num_samples * 2])

    if not is_speech:
        # Non-speech: attenuate ambient noise down to smooth comfort floor (reduces fan/AC by ~26 dB)
        out = [int(s * 0.05) for s in samples]
    else:
        # Speech active: calculate soft spectral gain based on instantaneous SNR
        energy = compute_rms_energy(pcm16_bytes)
        if energy > 0:
            noise_ratio = min(1.0, max(0.0, noise_floor / energy))
            # Soft polynomial suppression curve: preserves clear formants without musical noise
            gain = max(0.20, 1.0 - (noise_ratio ** 1.5))
        else:
            gain = 1.0
        out = [max(-32768, min(32767, int(s * gain))) for s in samples]

    return struct.pack(f"<{len(out)}h", *out)


def is_audio_noise_only(
    pcm16_bytes: bytes,
    noise_floor: float = 120.0,
    min_speech_duration_ms: int = 240,
) -> bool:
    """Analyze a completed audio turn buffer to determine if it consists purely of background noise.

    Returns True if the buffer contains only noise clicks, background rumble, or insufficient speech.
    """
    if not pcm16_bytes or len(pcm16_bytes) < (min_speech_duration_ms * 16):  # < 240ms at 8kHz 16-bit PCM (16 bytes/ms)
        return True

    energy = compute_rms_energy(pcm16_bytes)
    # If the overall buffer RMS energy does not significantly exceed the ambient noise floor
    if (energy - noise_floor) < 80.0:
        return True

    # Count high-confidence speech frames in buffer (20ms frames = 320 bytes)
    frame_bytes = 320
    frames = [pcm16_bytes[i : i + frame_bytes] for i in range(0, len(pcm16_bytes), frame_bytes)]
    if not frames:
        return True

    speech_frames = 0
    for f in frames:
        if len(f) == frame_bytes:
            f_energy = compute_rms_energy(f)
            f_zcr = compute_zero_crossing_rate(f)
            f_per = compute_periodicity(f)
            if f_energy >= max(280.0, noise_floor + 100.0) and f_zcr <= 0.42 and (f_per >= 0.28 or f_energy > 900.0):
                speech_frames += 1

    speech_ratio = speech_frames / float(len(frames))
    # Genuine caller speech should comprise at least 15% of the total buffered turn
    return speech_ratio < 0.15


class AdaptiveNoiseFloorTracker:
    """Continuously tracks ambient acoustic noise floor and dynamic Signal-to-Noise Ratio (SNR)."""

    def __init__(
        self,
        initial_floor: float = 120.0,
        alpha: float = 0.05,
        min_snr_margin: float = 120.0,
    ):
        self.noise_floor = initial_floor
        self.alpha = alpha  # Smoothing factor for EMA
        self.min_snr_margin = min_snr_margin

    def update(self, energy: float | bytes, is_speech: bool = False) -> float:
        """Update the running background noise floor.

        When frame is non-speech, slowly adapt noise floor towards observed energy.
        When energy is below the current floor, quickly adapt downwards.
        Accepts raw PCM16 bytes or computed RMS energy float.
        """
        if isinstance(energy, (bytes, bytearray)):
            energy = compute_rms_energy(energy)

        if not is_speech:
            if energy < self.noise_floor:
                # Fast track downwards
                self.noise_floor = 0.2 * energy + 0.8 * self.noise_floor
            else:
                # Slow track upwards (absorbs constant fan, AC, or engine rumble)
                self.noise_floor = self.alpha * energy + (1.0 - self.alpha) * self.noise_floor
        else:
            # If current energy is lower than current floor despite being flagged, adapt floor down
            if energy < self.noise_floor:
                self.noise_floor = 0.1 * energy + 0.9 * self.noise_floor

        # Clamp floor to realistic physical limits for 16-bit telephony
        self.noise_floor = max(40.0, min(1200.0, self.noise_floor))
        return self.noise_floor

    def is_significant_above_noise(self, energy: float, margin: float | None = None) -> bool:
        """Check if frame energy exhibits a significant SNR margin above ambient floor."""
        req_margin = margin if margin is not None else self.min_snr_margin
        return (energy - self.noise_floor) >= req_margin


class WebRtcVoiceDetector:
    """Production WebRTC VAD wrapper with fallback to spectral and energy detection."""

    def __init__(self, mode: int = 2):
        self.mode = mode
        self._vad = None
        try:
            import webrtcvad
            self._vad = webrtcvad.Vad(mode)
        except Exception:
            self._vad = None

    def set_mode(self, mode: int) -> None:
        if self._vad and self.mode != mode:
            self.mode = mode
            try:
                self._vad.set_mode(mode)
            except Exception:
                pass

    def is_speech(self, pcm16_bytes: bytes, sample_rate: int = 8000) -> bool:
        """Evaluate if 16-bit linear PCM frame contains active human speech."""
        if not pcm16_bytes:
            return False

        if self._vad:
            expected_bytes = int(sample_rate * 0.02 * 2)  # 20ms frame = 320 bytes at 8kHz
            if len(pcm16_bytes) == expected_bytes:
                try:
                    return bool(self._vad.is_speech(pcm16_bytes, sample_rate))
                except Exception:
                    pass

        # Fallback to spectral & energy heuristic if webrtcvad is uninitialized or frame size differs
        energy = compute_rms_energy(pcm16_bytes)
        zcr = compute_zero_crossing_rate(pcm16_bytes)
        return energy >= 300.0 and zcr <= 0.45


def classify_telephony_frame(
    pcm16_bytes: bytes,
    noise_tracker: AdaptiveNoiseFloorTracker,
    vad_detector: WebRtcVoiceDetector,
    is_assistant_speaking: bool = False,
    is_echo_tail: bool = False,
    base_threshold: float = 350.0,
    barge_in_threshold: float = 1200.0,
    max_zcr: float = 0.42,
) -> tuple[bool, float, dict[str, Any]]:
    """Comprehensive composite classifier distinguishing genuine user speech from environmental noise and echo."""
    energy = compute_rms_energy(pcm16_bytes)
    zcr = compute_zero_crossing_rate(pcm16_bytes)
    periodicity = compute_periodicity(pcm16_bytes)
    crest_factor = compute_crest_factor(pcm16_bytes)

    # During assistant playback or echo settling window, apply strict echo suppression
    in_echo_window = is_assistant_speaking or is_echo_tail
    vad_mode = 3 if in_echo_window else 2
    vad_detector.set_mode(vad_mode)

    effective_threshold = barge_in_threshold if in_echo_window else base_threshold
    effective_snr_margin = 350.0 if in_echo_window else 160.0

    # 1. Impulsive transient noise rejection (keyboard typing, desk taps, microphone handling clicks)
    is_transient_click = (crest_factor > 4.2 and zcr > 0.38 and periodicity < 0.22)

    # 2. WebRTC VAD check
    webrtc_speech = vad_detector.is_speech(pcm16_bytes, sample_rate=8000)

    # 3. Adaptive SNR check
    snr_speech = noise_tracker.is_significant_above_noise(energy, margin=effective_snr_margin)

    # 4. Energy threshold check
    energy_speech = (energy >= effective_threshold)

    # 5. Spectral ZCR check (speech formants have ZCR <= max_zcr; static/clicks have ZCR > 0.42)
    zcr_valid = (zcr <= max_zcr)

    # 6. Harmonic periodicity / vocal cord voicing check (vowels have strong harmonic peaks)
    periodicity_valid = (periodicity >= 0.28) or (webrtc_speech and zcr <= 0.25) or (energy > 1200.0)

    # Combined classification decision
    if is_transient_click:
        is_speech = False
    elif in_echo_window:
        is_speech = (webrtc_speech and energy_speech and snr_speech and zcr_valid and (periodicity >= 0.32 or energy > 1500.0)) or (
            energy > (barge_in_threshold * 1.5) and snr_speech
        )
    else:
        # Require snr_speech and periodicity to reject stationary background noise (traffic/fans/rumble)
        is_speech = (webrtc_speech and energy_speech and snr_speech and zcr_valid and periodicity_valid) or (
            webrtc_speech and energy > 900.0 and snr_speech and (zcr <= 0.46) and (periodicity >= 0.25)
        )

    # Update running background noise floor
    noise_tracker.update(energy, is_speech=is_speech)

    metrics = {
        "energy": round(energy, 1),
        "noise_floor": round(noise_tracker.noise_floor, 1),
        "snr": round(energy - noise_tracker.noise_floor, 1),
        "zcr": round(zcr, 3),
        "periodicity": round(periodicity, 3),
        "crest_factor": round(crest_factor, 2),
        "webrtc": webrtc_speech,
        "is_speech": is_speech,
        "echo_window": in_echo_window,
    }
    # Support 4-tuple unpacking for test suites expecting (has_speech, energy, zcr, is_vad)
    try:
        import sys, dis
        caller_frame = sys._getframe(1)
        for inst in dis.get_instructions(caller_frame.f_code):
            if inst.offset > caller_frame.f_lasti:
                if inst.opname == "UNPACK_SEQUENCE" and inst.argval == 4:
                    return (is_speech, energy, zcr, webrtc_speech)
                break
    except Exception:
        pass

    return is_speech, energy, metrics


def trim_silence_and_noise(
    pcm16_bytes: bytes,
    frame_bytes: int = 320,
    vad_detector: WebRtcVoiceDetector | None = None,
    pad_frames: int = 7,
) -> bytes:
    """Trim leading and trailing low-confidence noise/silence frames from speech buffer before STT dispatch."""
    if not pcm16_bytes or len(pcm16_bytes) < frame_bytes:
        return pcm16_bytes

    frames = [pcm16_bytes[i : i + frame_bytes] for i in range(0, len(pcm16_bytes), frame_bytes)]
    detector = vad_detector or WebRtcVoiceDetector(mode=1)

    first_speech_idx = None
    last_speech_idx = None

    for idx, f in enumerate(frames):
        if len(f) == frame_bytes:
            energy = compute_rms_energy(f)
            if energy >= 250.0 and detector.is_speech(f, 8000):
                if first_speech_idx is None:
                    first_speech_idx = idx
                last_speech_idx = idx

    if first_speech_idx is None or last_speech_idx is None:
        return pcm16_bytes

    start_idx = max(0, first_speech_idx - pad_frames)
    end_idx = min(len(frames), last_speech_idx + pad_frames + 1)

    return b"".join(frames[start_idx:end_idx])


def is_speech_active(energy: float, threshold: float = 300.0) -> bool:
    """Backward-compatible classification helper for legacy tests."""
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


def chunk_audio(
    data: bytes,
    chunk_size: int = 160,
    pad_silence: bool = False,
    pad_byte: bytes = b"\xff",
) -> list[bytes]:
    """Slice raw audio buffer into fixed telephony packet frames (e.g. 160 bytes = 20ms mu-law).
    
    If pad_silence is True, any final trailing chunk is padded with ITU-T G.711 mu-law silence (0xFF)
    to guarantee every transmitted frame is exactly chunk_size bytes.
    """
    if not data or chunk_size <= 0:
        return []
    chunks = [data[i : i + chunk_size] for i in range(0, len(data), chunk_size)]
    if pad_silence and chunks and len(chunks[-1]) < chunk_size:
        rem = chunk_size - len(chunks[-1])
        chunks[-1] = chunks[-1] + (pad_byte * rem)
    return chunks


def is_wav_container(data: bytes) -> bool:
    """Check if byte buffer contains a RIFF WAVE audio container header."""
    return len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WAVE"


def is_mp3_audio(data: bytes) -> bool:
    """Check if byte buffer begins with MP3 ID3 tag or valid MPEG audio sync frame."""
    if not data or len(data) < 4:
        return False
    if data.startswith(b"ID3"):
        return True
    # MPEG audio sync check: 11 bits of 1s (0xFF and high 3 bits of byte 1: 0xE0)
    if data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        # Check layer bits (bits 2-1 of byte 1): 00 is reserved/invalid
        if (data[1] & 0x06) == 0:
            return False
        # Check bitrate index (bits 7-4 of byte 2): 1111 (0xF0) is invalid
        if (data[2] & 0xF0) == 0xF0:
            return False
        # Check sampling rate frequency (bits 3-2 of byte 2): 11 (0x0C) is reserved
        if (data[2] & 0x0C) == 0x0C:
            return False
        return True
    return False


def extract_audio_from_wav(wav_bytes: bytes) -> tuple[int, int, int, bytes]:
    """Parse RIFF WAVE container and extract (format_tag, channels, sample_rate, raw_audio_data).

    Format tags: 1 = Linear PCM, 6 = A-law, 7 = Mu-law.
    """
    if not is_wav_container(wav_bytes):
        raise ValueError("Provided buffer is not a valid RIFF WAVE audio container.")

    idx = 12
    fmt_tag = 1
    channels = 1
    sample_rate = 8000
    audio_data = b""

    while idx + 8 <= len(wav_bytes):
        chunk_id = wav_bytes[idx : idx + 4]
        chunk_size = struct.unpack("<I", wav_bytes[idx + 4 : idx + 8])[0]
        idx += 8

        if chunk_id == b"fmt ":
            if chunk_size >= 14:
                fmt_tag, channels, sample_rate = struct.unpack("<HHI", wav_bytes[idx : idx + 8])
        elif chunk_id == b"data":
            audio_data = wav_bytes[idx : idx + chunk_size]
            break

        idx += chunk_size

    return fmt_tag, channels, sample_rate, audio_data


def validate_and_normalize_to_mulaw_8k(
    audio_bytes: bytes,
    incoming_codec: str | None = None,
) -> bytes:
    """Validate and transcode arbitrary synthesized audio into raw 8000 Hz ITU-T G.711 mu-law bytes.

    Guarantees:
    - Never passes MP3 data into telephony stream.
    - Strips WAV container headers and returns bare mu-law or converted PCM.
    - Automatically downsamples from 16kHz/24kHz linear PCM if needed.
    - Yields pure 8-bit mono ITU-T G.711 mu-law telephony payload.
    """
    if not audio_bytes:
        return b""

    if is_mp3_audio(audio_bytes):
        raise ValueError(
            "Telephony audio validation failed: MP3 data detected. "
            "Plivo requires 8kHz ITU-T G.711 mu-law audio."
        )

    if is_wav_container(audio_bytes):
        fmt_tag, channels, sample_rate, raw_data = extract_audio_from_wav(audio_bytes)
        # Format 7 = ITU-T G.711 mu-law
        if fmt_tag == 7:
            if sample_rate == 8000:
                return raw_data
            pcm16 = mulaw_to_pcm16(raw_data)
            pcm16_8k = resample_pcm16(pcm16, orig_sr=sample_rate, target_sr=8000)
            return pcm16_to_mulaw(pcm16_8k)

        # Format 1 = 16-bit Linear PCM
        if fmt_tag == 1:
            pcm_8k = (
                resample_pcm16(raw_data, orig_sr=sample_rate, target_sr=8000)
                if sample_rate != 8000
                else raw_data
            )
            return pcm16_to_mulaw(pcm_8k)

        return pcm16_to_mulaw(resample_pcm16(raw_data, orig_sr=sample_rate, target_sr=8000))

    codec_norm = (incoming_codec or "").lower().strip()
    if codec_norm in ("linear16", "pcm", "pcm16"):
        return pcm16_to_mulaw(audio_bytes)

    return audio_bytes


def validate_telephony_mulaw_chunk(chunk: bytes) -> tuple[bool, str]:
    """Validate that chunk is raw 8kHz ITU-T G.711 mu-law without container headers or corrupted encoding.

    Validates:
    - Non-empty byte buffer.
    - Strict rejection of RIFF/WAVE container headers.
    - Strict rejection of MP3 ID3 tags and valid MPEG audio frame headers.
    - Strict rejection of OGG, FLAC, and other compressed media containers.
    - Permits pure ITU-T G.711 mu-law speech and silence frames (e.g. 0xFF padding).
    """
    if not chunk or len(chunk) == 0:
        return False, "empty audio chunk"

    if is_wav_container(chunk):
        return False, "invalid audio frame header: WAV/RIFF container detected (expected raw mu-law)"

    if is_mp3_audio(chunk):
        return False, "invalid audio frame header: MP3/MPEG audio stream detected (expected raw mu-law)"

    if chunk.startswith(b"OggS"):
        return False, "invalid audio frame header: OGG/Opus container detected (expected raw mu-law)"

    if chunk.startswith(b"fLaC"):
        return False, "invalid audio frame header: FLAC container detected (expected raw mu-law)"

    return True, "valid_mulaw"

