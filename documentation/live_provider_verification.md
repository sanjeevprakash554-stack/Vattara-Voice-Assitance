# Vattara Voice Assistance – Live Provider Verification & Carrier Integration Guide

This guide details the exact procedures for connecting, validating, and smoke-testing real-world carrier and AI provider integrations in production environments.

> **CRITICAL ARCHITECTURAL DISTINCTION**:
> The automated test suite (`pytest`) runs in **isolated mock mode** to ensure deterministic execution, rapid CI/CD runs, and zero carrier per-minute charges during development.
> The procedures below are strictly for **live production staging verification** using real carrier SIMs, telephony gateways, and vendor API tokens.

---

## 1. Integration Matrix & Capability Overview

| Provider | Category | Audio Protocol | Live Verification Endpoint | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Twilio** | Telephony (Global) | Bidirectional WebSocket (mulaw 8kHz) | `/api/v1/voice/incoming` | Implemented & Tested |
| **Tata Smartflo** | Telephony (India PRI/SIP) | Click2Call REST + Webhook | `/api/v1/telephony/smartflo/incoming` | Implemented & Tested |
| **Exotel** | Telephony (India) | REST API + Webhook | `/api/v1/telephony/exotel/incoming` | Implemented & Tested |
| **Deepgram** | Speech-to-Text | Real-time WebSocket (Nova-2) | `wss://api.deepgram.com/v1/listen` | Adapter Implemented |
| **ElevenLabs** | Text-to-Speech | HTTP Chunked Streaming (Multilingual v2) | `https://api.elevenlabs.io/v1/text-to-speech` | Adapter Implemented |

---

## 2. Twilio Live Verification Procedure

### Prerequisites
1. Twilio Account SID and Auth Token.
2. A provisioned Twilio Phone Number (e.g. `+12292523194` or an Indian local number if enabled).
3. Public HTTPS/WSS URL mapped to your Vattara deployment (via domain SSL or temporary ngrok).

### Configuration
In `.env.production`:
```ini
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_real_auth_token_here
TWILIO_PHONE_NUMBER=+12292523194
PUBLIC_BASE_URL=https://api.vattara.com
```

### Verification Steps
1. **Configure Twilio Console Webhook**:
   - Navigate to **Phone Numbers** -> **Manage** -> **Active Numbers** -> click your number.
   - Under **Voice Configuration**, set **A CALL COMES IN**:
     - Webhook URL: `https://api.vattara.com/api/v1/voice/incoming`
     - HTTP Method: `HTTP POST`
2. **Execute Inbound Voice Call**:
   - Dial the Twilio number from a physical mobile phone.
   - **Expected Behavior**:
     - Twilio sends POST to `/api/v1/voice/incoming`.
     - Vattara returns TwiML with `<Connect><Stream url="wss://api.vattara.com/api/v1/voice/stream" />`.
     - Caller hears greeting: *"Hello! Welcome to Vattara City Clinic. How may I help you today?"*.
     - Speak: *"I need to book a cardiology appointment tomorrow morning"*.
     - Assistant triages, queries doctor availability, and reserves slot.
3. **Inspect Call History in Dashboard**:
   - Open Vattara Dashboard -> **Call Logs**.
   - Verify call appears with duration, caller number, status `completed`, and generated transcript.

---

## 3. Tata Smartflo Live Verification Procedure

### Prerequisites
1. Tata Smartflo Portal credentials with Administrator API access.
2. Virtual Agent Extension and Agent Number configured.
3. Authorized Outbound Caller ID (DID).

### Configuration
In `.env.production`:
```ini
SMARTFLO_API_TOKEN=your_smartflo_bearer_jwt_token
SMARTFLO_CLICK2CALL_KEY=your_smartflo_click2call_api_key
SMARTFLO_CALLER_ID=914428289000
SMARTFLO_BASE_URL=https://api-smartflo.tatateleservices.com/v1
SMARTFLO_WEBHOOK_TOKEN=your_shared_webhook_secret_key
SMARTFLO_BUSINESS_MAPPING=914428289000:demo-biz-vattara-health
```

### Verification Steps
1. **Configure Smartflo Inbound Webhook**:
   - In Tata Smartflo Admin Portal, set Inbound Route Webhook to:
     `https://api.vattara.com/api/v1/telephony/smartflo/incoming`
   - Set Authorization Header: `Bearer your_shared_webhook_secret_key`.
2. **Inbound Call Triage Test**:
   - Dial `+91 44 2828 9000` from an Indian mobile carrier (Airtel/Jio/Vodafone).
   - Ensure webhook maps the DID `914428289000` to tenant `demo-biz-vattara-health`.
   - Verify immediate conversational AI response in Tamil or English based on assistant settings.
3. **Outbound Click2Call Verification**:
   - Trigger test outbound reminder or staff call via curl:
   ```bash
   curl -X POST https://api.vattara.com/api/v1/telephony/smartflo/outbound \
     -H "Authorization: Bearer <tenant_jwt>" \
     -H "Content-Type: application/json" \
     -d '{"customer_phone": "+919840123456", "customer_name": "Test Patient"}'
   ```
   - Target handset will ring. Upon pickup, AI audio plays.

---

## 4. Exotel Live Verification Procedure

### Configuration
In `.env.production`:
```ini
EXOTEL_API_KEY=your_exotel_account_sid_or_subdomain
EXOTEL_CALLER_ID=08047100000
EXOTEL_BUSINESS_API_KEYS=vat_live_apollo_key:demo-biz-vattara-health
```

### Verification Steps
1. Configure Exotel Applet Passthrough URL: `https://api.vattara.com/api/v1/telephony/exotel/incoming`.
2. Place test call to Exotel Virtual Number.
3. Verify that Exotel call parameters (`CallSid`, `From`, `To`) create an active call session and log conversation transcripts.

---

## 5. Deepgram Nova-2 STT Live Verification

### Configuration
```ini
STT_PROVIDER=deepgram
DEEPGRAM_API_KEY=your_live_deepgram_api_key
```

### Live Test Command
Run real-time audio chunk transcription test via curl/python:
```bash
python -c "
from app.services.streaming.stt_provider import DeepgramStreamingSTT
stt = DeepgramStreamingSTT()
print('Deepgram Provider initialized successfully:', stt.provider_name)
"
```
During an active call:
- Monitor latency from user speech ending to final transcript: target is **< 300ms**.
- Verify multilingual recognition in Tamil Unicode (`வணக்கம்`) and Latin script Tanglish (`Vanakkam`).

---

## 6. ElevenLabs Live TTS Verification

### Configuration
```ini
TTS_PROVIDER=elevenlabs
ELEVENLABS_API_KEY=your_live_elevenlabs_api_key
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM
ELEVENLABS_MODEL_ID=eleven_multilingual_v2
```

### Live Test Script
```bash
python -c "
from app.services.streaming.tts_provider import ElevenLabsStreamingTTS
tts = ElevenLabsStreamingTTS()
audio = tts.synthesize_to_mulaw('வணக்கம், உங்கள் சந்திப்பு பதிவு செய்யப்பட்டுள்ளது.', language='ta-IN')
print(f'Synthesized {len(audio)} bytes of 8kHz mu-law audio.')
"
```
Verify audio clarity, natural Tamil prosody, and absence of clipping or stutter.

---

## 7. Production Troubleshooting & Triage Checklist

| Symptom | Probable Cause | Diagnostic Command | Remediation |
| :--- | :--- | :--- | :--- |
| Inbound call drops after 5 seconds | Webhook returns HTTP 500 or timeout | `docker compose logs backend --tail=100` | Verify `PUBLIC_BASE_URL` matches public DNS and SSL is valid |
| Assistant stays silent after user speaks | VAD energy threshold too high or STT offline | Check `/api/v1/health` and logs | Lower `VAD_ENERGY_THRESHOLD` to 200.0 or check Deepgram API key |
| "Too Many Requests" (HTTP 429) during login | Rate limiter triggered by brute force | `SlidingWindowRateLimiter.reset_all()` | Wait for sliding window (60s) or increase `RATE_LIMIT_LOGIN_PER_MINUTE` |
| Invoice marked as "pending" after plan change | Normal behavior (awaiting gateway payment) | POST to `/api/v1/subscriptions/invoices/{id}/confirm-payment` | Trigger payment confirmation with gateway transaction reference |
