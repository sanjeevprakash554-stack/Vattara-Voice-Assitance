import os, sys, time, wave, httpx
sys.path.insert(0, os.path.abspath('backend'))
from dotenv import load_dotenv
from app.services.streaming.audio_codec import mulaw_to_pcm16

load_dotenv('backend/.env')
API_KEY = os.getenv('ELEVENLABS_API_KEY')

VOICES = {
    'Meera (Native Tamil Conversational)': 'gCr8TeSJgJaeaIoV4RWH',
    'Sarah (Default Premade)': 'EXAVITQu4vr4xnSDxMaL',
}

TEST_CASES = [
    ('ta_greeting', 'வணக்கம்! Vattara City Clinic. உங்களுக்கு எப்படி உதவலாம்?', 'ta'),
    ('en_greeting', 'Hello! Welcome to Vattara City Clinic. How may I help you today?', 'en'),
    ('ta_booking', 'நிச்சயமாக! எந்த மருத்துவ சேவைக்கு அப்பாயின்ட்மென்ட் வேண்டும்? பொது மருத்துவம் அல்லது இதய சிகிச்சை ஆலோசனை பெறலாம்.', 'ta'),
    ('en_booking', 'Sure! Which medical service would you like to book? For example, General Physician Consultation or Cardiology Consultation.', 'en'),
    ('tanglish_mixed', 'Kandippa, naalaiku doctors available-ah irukaanga. Available slots: kaalai 8:30, 9:00, 9:30. Entha time ungalukku convenient-ah irukum?', 'ta'),
    ('clinic_hours_en', 'Our clinic working hours are Monday to Saturday, from 8:30 AM to 8:00 PM. Would you like to schedule an appointment?', 'en'),
    ('clinic_hours_ta', 'எங்கள் கிளினிக் வேலை நேரம்: திங்கள் முதல் சனிக்கிழமை வரை, காலை 8:30 மணி முதல் இரவு 8:00 மணி வரை. நீங்கள் அப்பாயின்ட்மென்ட் பதிவு செய்ய விரும்புகிறீர்களா?', 'ta'),
    ('doc_avail_en', 'On Tuesday, November 17th, doctors are available for consultation. Available slots are: 8:30 AM, 9:00 AM, and 9:30 AM. Which time works best for you?', 'en'),
    ('doc_avail_ta', 'நவம்பர் 17, செவ்வாய்க்கிழமை அன்று, மருத்துவர்கள் ஆலோசனைகள் வழங்குகிறார்கள். கிடைக்கும் நேரங்கள்: காலை 8:30, 9:00, மற்றும் 9:30. இதில் எந்த நேரம் உங்களுக்கு வசதியாக இருக்கும்?', 'ta'),
    ('confirmation_ta', 'நன்றி கார்த்திக். உங்கள் General Physician Consultation ஆலோசனை, நவம்பர் 17 அன்று, காலை 8:30 மணிக்கு வெற்றிகரமாக பதிவு செய்யப்பட்டது. Vattara City Clinic-ஐ தொடர்பு கொண்டதற்கு நன்றி. வணக்கம்!', 'ta'),
    ('confirmation_en', 'Thank you Steve. Your appointment for General Physician Consultation on Tuesday, November 17th at 8:30 AM is confirmed. Thank you for calling Vattara City Clinic. Have a wonderful day!', 'en'),
]

results = []

def save_wav_from_mulaw(mulaw_bytes: bytes, filename: str):
    pcm = mulaw_to_pcm16(mulaw_bytes)
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(8000)
        wf.writeframes(pcm)

def generate_voice_samples():
    for tag, text, lang in TEST_CASES:
        for vname, vid in VOICES.items():
            vprefix = 'meera' if 'Meera' in vname else 'sarah'
            out_wav = f"backend/audio_samples/{vprefix}_{tag}.wav"
            
            t0 = time.perf_counter()
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{vid}/stream"
            params = {"output_format": "ulaw_8000", "optimize_streaming_latency": 3}
            headers = {"xi-api-key": API_KEY, "Content-Type": "application/json", "Accept": "audio/basic"}
            
            # Receptionist tuned parameters
            payload = {
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.60,
                    "similarity_boost": 0.85,
                    "style": 0.05,
                    "use_speaker_boost": True,
                }
            }
            if lang:
                payload["language_code"] = lang
                
            try:
                with httpx.Client(timeout=15.0) as client:
                    resp = client.post(url, params=params, headers=headers, json=payload)
                    t1 = time.perf_counter()
                    latency_ms = int((t1 - t0) * 1000)
                    if resp.status_code == 200:
                        audio_data = resp.content
                        save_wav_from_mulaw(audio_data, out_wav)
                        dur_s = len(audio_data) / 8000.0
                        print(f"[{vprefix.upper()}] {tag} ({lang}) -> HTTP 200 | {len(audio_data)} bytes | {dur_s:.2f}s audio | Latency: {latency_ms}ms | Saved {out_wav}")
                        results.append({
                            "tag": tag,
                            "voice": vname,
                            "lang": lang,
                            "bytes": len(audio_data),
                            "duration": dur_s,
                            "latency_ms": latency_ms,
                            "path": out_wav
                        })
                    else:
                        print(f"[{vprefix.upper()}] {tag} FAILED HTTP {resp.status_code}: {resp.text}")
            except Exception as e:
                print(f"[{vprefix.upper()}] {tag} ERROR: {e}")

    print(f"\nCompleted {len(results)} audio syntheses successfully!")


if __name__ == "__main__":
    generate_voice_samples()
