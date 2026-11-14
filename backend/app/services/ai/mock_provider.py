"""Deterministic intelligent Mock LLM Provider for unit/integration testing and zero-cost offline execution."""

from datetime import date, datetime, timedelta, timezone
import re
from typing import Any

from app.core.logging import get_logger
from app.services.ai.base import (
    BaseLLMProvider,
    ExtractedEntities,
    FunctionCallRequest,
    LLMMessage,
    LLMResponse,
)
from app.services.ai.language_detector import detect_language

logger = get_logger(__name__)

# Service aliases for intelligent semantic matching in English, Tamil, and Telugu
SERVICE_KEYWORD_MAP: dict[str, list[str]] = {
    "cardio": ["cardio", "cardiology", "heart", "ecg", "cardiac", "இதயம்", "நெஞ்சு", "idhayam", "heart problem", "గుండె", "కార్డియాలజీ", "gunde", "gunde noppi"],
    "physician": ["physician", "general physician", "general medicine", "internal medicine", "பொது மருத்துவம்", "maruthuvar", "maruthuvam", "సాధారణ వైద్యం", "వైద్యుడు", "vaidhyudu", "vaidyudu", "doctoru"],
    "pediatric": ["pediatric", "pediatrician", "child", "baby", "kid", "vaccine", "குழந்தை", "kuzhandhai", "paappa", "పిల్లల", "పిల్లలు", "pillalu", "chinna pillalu"],
    "dental": ["dental", "dentist", "teeth", "tooth", "cleaning", "cavity", "பல்", "pal", "pal vali", "పళ్ళు", "దంత", "పంటి నొప్పి", "pallu", "panti noppi"],
    "diagnostics": ["blood test", "diagnostic", "diagnostics", "lab test", "lipid", "பரிசோதனை", "raththam", "blood", "రక్త పరీక్ష", "పరీక్ష", "raktha pareeksha"],
}


class MockLLMProvider(BaseLLMProvider):
    """High-intelligence deterministic LLM provider simulating GPT-4o / Gemini for offline testing."""

    def __init__(self, default_timezone: str = "Asia/Kolkata"):
        self.default_timezone = default_timezone

    def generate_response(
        self,
        messages: list[LLMMessage],
        system_prompt: str,
        active_services: list[dict[str, Any]],
        available_tools: list[dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> LLMResponse:
        """Analyze message history and return structured LLMResponse with optional function calling."""
        if not messages:
            return LLMResponse(text="Hello! How may I assist you today?", intent="greeting")

        last_user_msg = next((m.content for m in reversed(messages) if m.role == "user"), "")
        full_transcript = " ".join([m.content for m in messages if m.role == "user"])
        now = datetime.now(timezone.utc)

        # 1. Detect language
        detected_lang = detect_language(last_user_msg, current_lang="en-IN")

        # 2. Extract Entities
        entities = self._extract_entities(full_transcript, last_user_msg, active_services, now)

        # 3. Classify Intent
        intent = self._classify_intent(last_user_msg, full_transcript)

        # 4. Handle Tool Results if preceding message was a tool execution
        tool_results_msg = next((m for m in reversed(messages) if m.role == "tool"), None)
        if tool_results_msg:
            return self._format_tool_result_response(tool_results_msg.content, detected_lang)

        # 5. Check if Caller intends to exit / cancel call
        if intent == "cancellation":
            return self._build_exit_response(detected_lang)

        # 6. Check if user wants to Cancel Appointment
        if intent == "cancel_appointment":
            tool_calls = [
                FunctionCallRequest(
                    id="call_cancel_1",
                    function_name="cancel_appointment",
                    arguments={
                        "customer_phone": entities.customer_phone or "",
                        "reason": entities.cancel_reason or "Cancelled by caller",
                    },
                )
            ]
            return LLMResponse(
                text=self._render_cancelling_ack(detected_lang),
                intent="cancel_appointment",
                detected_language=detected_lang,
                extracted_entities=entities,
                tool_calls=tool_calls,
            )

        # 7. Check if user wants to Reschedule Appointment
        if intent == "reschedule_appointment":
            if entities.appointment_datetime_iso:
                tool_calls = [
                    FunctionCallRequest(
                        id="call_resched_1",
                        function_name="reschedule_appointment",
                        arguments={
                            "customer_phone": entities.customer_phone or "",
                            "new_appointment_time": entities.appointment_datetime_iso,
                            "reason": entities.reschedule_reason or "Patient requested reschedule",
                        },
                    )
                ]
                return LLMResponse(
                    text=self._render_rescheduling_ack(detected_lang),
                    intent="reschedule_appointment",
                    detected_language=detected_lang,
                    extracted_entities=entities,
                    tool_calls=tool_calls,
                )
            else:
                # Ask for new date/time
                return LLMResponse(
                    text=self._render_ask_reschedule_time(detected_lang),
                    intent="reschedule_appointment",
                    detected_language=detected_lang,
                    extracted_entities=entities,
                )

        # 8. Check Availability Intent (user asked for slots / when doctor is free)
        if intent == "check_availability":
            target_date_iso = entities.target_date_iso or (now + timedelta(days=1)).date().isoformat()
            tool_calls = [
                FunctionCallRequest(
                    id="call_avail_1",
                    function_name="check_available_slots",
                    arguments={
                        "date": target_date_iso,
                        "service_id": entities.service_id,
                    },
                )
            ]
            return LLMResponse(
                text=self._render_checking_slots_prompt(target_date_iso, detected_lang),
                intent="check_availability",
                detected_language=detected_lang,
                extracted_entities=entities,
                tool_calls=tool_calls,
            )

        # 9. Appointment Booking Flow (Slot filling & Tool invocation)
        if intent in ("book_appointment", "confirmation", "greeting", "unknown"):
            # Check what's missing
            if not entities.service_id and active_services:
                return LLMResponse(
                    text=self._render_ask_service(active_services, detected_lang),
                    intent="inquire_services",
                    detected_language=detected_lang,
                    extracted_entities=entities,
                )

            if not entities.appointment_datetime_iso:
                return LLMResponse(
                    text=self._render_ask_datetime(entities.service_name, detected_lang),
                    intent="book_appointment",
                    detected_language=detected_lang,
                    extracted_entities=entities,
                )

            # Check if date is in the past
            try:
                parsed_dt = datetime.fromisoformat(entities.appointment_datetime_iso)
                if parsed_dt <= now:
                    entities.appointment_datetime_iso = None
                    return LLMResponse(
                        text=self._render_past_time_error(detected_lang),
                        intent="book_appointment",
                        detected_language=detected_lang,
                        extracted_entities=entities,
                    )
            except Exception:
                pass

            if not entities.customer_name or entities.customer_name.startswith("Caller "):
                return LLMResponse(
                    text=self._render_ask_name(detected_lang),
                    intent="book_appointment",
                    detected_language=detected_lang,
                    extracted_entities=entities,
                )

            # All required parameters present -> trigger book_appointment tool!
            tool_calls = [
                FunctionCallRequest(
                    id="call_book_1",
                    function_name="book_appointment",
                    arguments={
                        "customer_name": entities.customer_name,
                        "customer_phone": entities.customer_phone or "+919876543210",
                        "service_id": entities.service_id,
                        "appointment_time": entities.appointment_datetime_iso,
                    },
                )
            ]
            return LLMResponse(
                text=self._render_finalizing_booking(entities, detected_lang),
                intent="book_appointment",
                detected_language=detected_lang,
                extracted_entities=entities,
                tool_calls=tool_calls,
            )

        return LLMResponse(
            text="How may I assist you with your appointment today?",
            intent="greeting",
            detected_language=detected_lang,
            extracted_entities=entities,
        )

    # -------------------------------------------------------------------------
    # Helper NLU / Extraction methods
    # -------------------------------------------------------------------------

    def _classify_intent(self, latest_text: str, full_text: str) -> str:
        text = f"{latest_text} {full_text}".lower()

        if any(w in latest_text.lower() for w in [
            "bye", "exit", "nevermind", "stop", "vendam", "வேண்டாம்", "போதும்",
            "వద్దు", "vaddu", "vaddhu", "చాలు", "chalu", "chalamma",
        ]):
            return "cancellation"

        if any(w in text for w in [
            "cancel appointment", "cancel my appointment", "appointment cancel",
            "ரத்து", "cancel pannanum",
            "రద్దు", "రద్దు చేయండి", "cancel cheyandi", "raddhu cheyandi", "cancel cheyali",
        ]):
            return "cancel_appointment"

        if any(w in text for w in [
            "reschedule", "change time", "change date", "postpone", "மாற்ற வேண்டும்", "mathanum", "maathanum",
            "మార్చండి", "సమయం మార్చండి", "marchandi", "change cheyandi", "reschedule cheyandi",
        ]):
            return "reschedule_appointment"

        if any(w in text for w in [
            "slots", "available", "availability", "when can i", "open", "நேரம் இருக்கிறதா", "slot iruka", "neram iruka",
            "స్లాట్లు ఉన్నాయా", "సమయం ఉందా", "slots unnaya", "time undha", "available undha",
        ]):
            return "check_availability"

        if any(w in text for w in [
            "book", "appointment", "doctor", "consultation", "visit", "முன்பதிவு", "venum", "parkanum",
            "బుక్ చేయాలి", "అపాయింట్‌మెంట్ కావాలి", "డాక్టర్ కావాలి", "book cheyali", "appointment kavali",
        ]):
            return "book_appointment"

        if any(w in latest_text.lower() for w in [
            "yes", "confirm", "sure", "okay", "சரி", "aama", "sari",
            "అవును", "సరే", "avunu", "thappakunda", "alage",
        ]):
            return "confirmation"

        if any(w in latest_text.lower() for w in [
            "hello", "hi", "vanakkam", "வணக்கம்",
            "నమస్కారం", "నమస్తే", "namaskaram", "namaskaramandi",
        ]):
            return "greeting"

        return "unknown"

    def _extract_entities(
        self,
        full_transcript: str,
        latest_text: str,
        services: list[dict[str, Any]],
        now: datetime,
    ) -> ExtractedEntities:
        entities = ExtractedEntities()
        combined = f"{full_transcript} {latest_text}".lower()

        # 1. Match Service
        for srv in services:
            s_name = srv.get("name", "").lower()
            if s_name in combined:
                entities.service_id = srv.get("id")
                entities.service_name = srv.get("name")
                break

        if not entities.service_id:
            for s_key, aliases in SERVICE_KEYWORD_MAP.items():
                if any(a in combined for a in aliases):
                    for srv in services:
                        s_name = srv.get("name", "").lower()
                        if any(a in s_name for a in aliases):
                            entities.service_id = srv.get("id")
                            entities.service_name = srv.get("name")
                            break
                    if entities.service_id:
                        break

        # 2. Extract Date
        target_date = None
        if any(w in combined for w in ["today", "இன்று", "iniku", "iniki", "ఈ రోజు", "ఈరోజు", "ivvala", "ee roju", "eeroju"]):
            target_date = now.date()
        elif any(w in combined for w in ["day after tomorrow", "நாளை மறுநாள்", "naalai marunaal", "ఎల్లుండి", "ellundi"]):
            target_date = (now + timedelta(days=2)).date()
        elif any(w in combined for w in ["tomorrow", "நாளை", "naalaiki", "naalai", "రేపు", "repu"]):
            target_date = (now + timedelta(days=1)).date()
        else:
            # Check explicit ISO YYYY-MM-DD
            m_iso = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", combined)
            if m_iso:
                try:
                    target_date = date(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3)))
                except ValueError:
                    pass

            if not target_date:
                weekdays = {
                    "monday": 0, "திங்கள்": 0, "thingal": 0, "సోమవారం": 0, "somavaram": 0,
                    "tuesday": 1, "செவ்வாய்": 1, "sevvai": 1, "మంగళవారం": 1, "mangalavaram": 1,
                    "wednesday": 2, "புதன்": 2, "budhan": 2, "బుధవారం": 2, "budhavaram": 2,
                    "thursday": 3, "வியாழன்": 3, "vyazhan": 3, "గురువారం": 3, "guruvaram": 3,
                    "friday": 4, "வெள்ளி": 4, "velli": 4, "శుక్రవారం": 4, "sukravaram": 4,
                    "saturday": 5, "சனி": 5, "sani": 5, "శనివారం": 5, "sanivaram": 5,
                    "sunday": 6, "ஞாயிறு": 6, "gnaayiru": 6, "ఆదివారం": 6, "aadhivaram": 6, "adivaram": 6,
                }
                for day_word, d_idx in weekdays.items():
                    if day_word in combined:
                        days_ahead = (d_idx - now.weekday()) % 7
                        if days_ahead == 0:
                            days_ahead = 7
                        target_date = (now + timedelta(days=days_ahead)).date()
                        break

        if target_date:
            entities.target_date_iso = target_date.isoformat()

        # 3. Extract Time
        hour: int | None = None
        minute: int = 0

        # Pattern: 10:30 AM / 10 AM / 14:00
        time_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)\b", combined, re.IGNORECASE)
        if time_match:
            raw_h = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            ampm = time_match.group(3).lower().replace(".", "")
            if ampm == "pm" and raw_h < 12:
                hour = raw_h + 12
            elif ampm == "am" and raw_h == 12:
                hour = 0
            else:
                hour = raw_h
        else:
            # Check 24hr or "10 maniki" / "10 gantalu"
            mani_match = re.search(r"\b(\d{1,2})\s*(?:mani|maniki|மணி|గంట|గంటలు|గంటలకు|ganta|gantalu|gantaku|ki)\b", combined)
            if mani_match:
                raw_h = int(mani_match.group(1))
                if any(w in combined for w in ["evening", "maalai", "sayanthiram", "night", "సాయంత్రం", "రాత్రి", "sayantram", "raathri"]) and raw_h < 12:
                    hour = raw_h + 12
                else:
                    hour = raw_h

        if target_date and hour is not None:
            dt = datetime(target_date.year, target_date.month, target_date.day, hour, minute, tzinfo=timezone.utc)
            entities.appointment_datetime_iso = dt.isoformat()

        # 4. Extract Caller Name
        name_patterns = [
            r"(?:my name is|this is|i am|name is|i'm|call me)\s+([A-Za-z\s]+)",
            r"(?:என் பெயர்|பெயர்)\s+([^\s,]+)",
            r"(?:en peyar|en peru)\s+([A-Za-z\s]+)",
            r"(?:నా పేరు|పేరు)\s+([^\s,]+)",
            r"(?:naa peru|na peru)\s+([A-Za-z\s]+)",
        ]
        for pat in name_patterns:
            m = re.search(pat, combined, re.IGNORECASE)
            if m:
                cand = re.sub(r"[^\w\s]", "", m.group(1)).strip().split()
                filtered = [w for w in cand if w.lower() not in {"and", "i", "want", "to", "book", "please", "consultation"}]
                if filtered:
                    entities.customer_name = " ".join(filtered[:3]).title()
                    break

        return entities

    # -------------------------------------------------------------------------
    # Response Generators (Localized in English, Tamil, and Telugu)
    # -------------------------------------------------------------------------

    def _render_ask_service(self, services: list[dict[str, Any]], lang: str) -> str:
        s_names = ", ".join([s["name"] for s in services[:3]])
        if lang == "ta-IN":
            return f"வணக்கம்! நீங்கள் எந்த மருத்துவ சேவை பெற விரும்புகிறீர்கள்? உதாரணம்: {s_names}."
        elif lang == "ta-Latn":
            return f"Vanakkam! Neenga entha medical service book panna virumbureenga? For example: {s_names}."
        elif lang == "te-IN":
            return f"నమస్కారం! మీరు ఏ వైద్య సేవ కోసం సంప్రదించాలనుకుంటున్నారు? ఉదాహరణకు: {s_names}."
        elif lang == "te-Latn":
            return f"Namaskaram! Meeru ye medical service book cheyalani anukuntunnaru? For example: {s_names}."
        return f"Welcome! Which medical service would you like to book? For example: {s_names}."

    def _render_ask_datetime(self, service_name: str | None, lang: str) -> str:
        s_label = service_name or "consultation"
        if lang == "ta-IN":
            return f"உங்கள் {s_label} முன்பதிவுக்கு எந்த நாள் மற்றும் நேரம் வசதியாக இருக்கும்?"
        elif lang == "ta-Latn":
            return f"Ungal {s_label} consultation-ku entha date and time convenient-ah irukum?"
        elif lang == "te-IN":
            return f"మీ {s_label} అపాయింట్‌మెంట్ కోసం ఏ రోజు మరియు సమయం అనుకూలంగా ఉంటుంది?"
        elif lang == "te-Latn":
            return f"Mee {s_label} appointment kosam ye date and time convenient-ga untundi?"
        return f"What date and time works best for your {s_label} appointment?"

    def _render_ask_name(self, lang: str) -> str:
        if lang == "ta-IN":
            return "முன்பதிவு செய்ய உங்கள் முழுப் பெயரை தயவுசெய்து கூறுங்கள்?"
        elif lang == "ta-Latn":
            return "Booking confirm panna ungaludaiya full name sollunga please?"
        elif lang == "te-IN":
            return "అపాయింట్‌మెంట్ నమోదు చేయడానికి మీ పూర్తి పేరు చెప్పండి?"
        elif lang == "te-Latn":
            return "Booking confirm cheyadaniki mee full name cheppandi please?"
        return "May I please have your full name for the appointment record?"

    def _render_past_time_error(self, lang: str) -> str:
        if lang == "ta-IN":
            return "மன்னிக்கவும், அந்த நேரம் கடந்துவிட்டது. எதிர்வரும் தேதி மற்றும் நேரத்தை கூறுங்கள்."
        elif lang == "ta-Latn":
            return "Sorry, andha time mudinjuruchu. Future date and time sollunga please."
        elif lang == "te-IN":
            return "క్షమించండి, ఆ సమయం గడిచిపోయింది. దయచేసి రాబోయే తేదీ మరియు సమయాన్ని తెలియజేయండి."
        elif lang == "te-Latn":
            return "Sorry, aa time ayipoyindi. Future date and time cheppandi please."
        return "I apologize, but that time is in the past. Please choose an upcoming date and time."

    def _render_checking_slots_prompt(self, target_date: str, lang: str) -> str:
        if lang == "ta-IN":
            return f"{target_date} அன்று இருக்கும் நேரங்களை சரிபார்க்கிறேன். ஒரு நிமிடம்."
        elif lang == "ta-Latn":
            return f"{target_date}-la available slots check panren. Oru nimisham irunga."
        elif lang == "te-IN":
            return f"{target_date} తేదీన ఉన్న సమయాలను పరిశీలిస్తున్నాను. ఒక్క క్షణం."
        elif lang == "te-Latn":
            return f"{target_date}-lo available slots check chestunnanu. One moment please."
        return f"Checking available appointment slots for {target_date}. One moment please."

    def _render_cancelling_ack(self, lang: str) -> str:
        if lang == "ta-IN":
            return "உங்கள் முன்பதிவை ரத்து செய்கிறேன். ஒரு நிமிடம் காத்திருங்கள்."
        elif lang == "ta-Latn":
            return "Ungal appointment-ai cancel panren. One moment please."
        elif lang == "te-IN":
            return "మీ అపాయింట్‌మెంట్‌ను రద్దు చేస్తున్నాను. ఒక్క క్షణం వేచి ఉండండి."
        elif lang == "te-Latn":
            return "Mee appointment cancel chestunnanu. One moment please."
        return "Processing your appointment cancellation. Please hold on a moment."

    def _render_rescheduling_ack(self, lang: str) -> str:
        if lang == "ta-IN":
            return "உங்கள் முன்பதிவு நேரத்தை மாற்றுகிறேன். ஒரு நிமிடம் காத்திருங்கள்."
        elif lang == "ta-Latn":
            return "Ungal appointment time-ai reschedule panren. One moment please."
        elif lang == "te-IN":
            return "మీ అపాయింట్‌మెంట్ సమయాన్ని మారుస్తున్నాను. ఒక్క క్షణం వేచి ఉండండి."
        elif lang == "te-Latn":
            return "Mee appointment time reschedule chestunnanu. One moment please."
        return "Processing your appointment reschedule request. Please hold on a moment."

    def _render_ask_reschedule_time(self, lang: str) -> str:
        if lang == "ta-IN":
            return "புதிய முன்பதிவுக்கு எந்த நாள் மற்றும் நேரம் வேண்டும்?"
        elif lang == "ta-Latn":
            return "Puthiya appointment-ku entha date and time venum?"
        elif lang == "te-IN":
            return "కొత్త అపాయింట్‌మెంట్ కోసం ఏ రోజు మరియు సమయం కావాలి?"
        elif lang == "te-Latn":
            return "Kotha appointment kosam ye date and time kavali?"
        return "What new date and time would you like to reschedule your appointment to?"

    def _render_finalizing_booking(self, entities: ExtractedEntities, lang: str) -> str:
        s_name = entities.service_name or "appointment"
        if lang == "ta-IN":
            return f"{entities.customer_name} அவர்களே, உங்கள் {s_name} முன்பதிவை உறுதி செய்கிறேன்."
        elif lang == "ta-Latn":
            return f"{entities.customer_name}, ungal {s_name} booking-ai confirm panren."
        elif lang == "te-IN":
            return f"{entities.customer_name} గారు, మీ {s_name} బుకింగ్‌ను ధృవీకరిస్తున్నాను."
        elif lang == "te-Latn":
            return f"{entities.customer_name} garu, mee {s_name} booking confirm chestunnanu."
        return f"Confirming your {s_name} booking for {entities.customer_name}. One moment."

    def _build_exit_response(self, lang: str) -> LLMResponse:
        if lang == "ta-IN":
            text = "அழைத்ததற்கு நன்றி. உங்கள் நாள் இனிய நாளாக அமையட்டும். வணக்கம்!"
        elif lang == "ta-Latn":
            text = "Call pannadhukku nandri. Have a wonderful day. Vanakkam!"
        elif lang == "te-IN":
            text = "కాల్ చేసినందుకు ధన్యవాదాలు. మీకు మంచి రోజు కావాలని కోరుకుంటున్నాము. నమస్కారం!"
        elif lang == "te-Latn":
            text = "Call chesinanduku dhanyavadalu. Have a wonderful day. Namaskaram!"
        else:
            text = "Thank you for calling. Have a wonderful day. Goodbye!"

        return LLMResponse(
            text=text,
            intent="cancellation",
            detected_language=lang,
            should_hangup=True,
        )

    def _format_tool_result_response(self, tool_output_json: str, lang: str) -> LLMResponse:
        """Format the completed execution of an AI tool into conversational spoken output."""
        try:
            data = json.loads(tool_output_json) if isinstance(tool_output_json, str) else tool_output_json
        except Exception:
            data = {"result": tool_output_json}

        # Slot Check Result
        if "available_slots" in data:
            slots = data.get("available_slots", [])
            d = data.get("date")
            if not slots or not data.get("is_open"):
                if lang == "ta-IN":
                    msg = f"மன்னிக்கவும், {d} அன்று மருத்துவமனை மூடப்பட்டுள்ளது அல்லது முன்பதிவு நேரம் இல்லை."
                elif lang == "ta-Latn":
                    msg = f"Sorry, {d}-la clinic closed or slots illai. Vera date paarkalama?"
                elif lang == "te-IN":
                    msg = f"క్షమించండి, {d} తేదీన క్లినిక్ మూసివేయబడింది లేదా స్లాట్లు లేవు. వేరే తేదీ చూడమంటారా?"
                elif lang == "te-Latn":
                    msg = f"Sorry, {d}-lo clinic closed or slots levu. Vera date chudamantara?"
                else:
                    msg = f"I apologize, but there are no available slots on {d}. Would you like to check another day?"
            else:
                top_slots = ", ".join(slots[:4])
                if lang == "ta-IN":
                    msg = f"{d} அன்று கிடைக்கும் நேரங்கள்: {top_slots}. இதில் எந்த நேரம் உங்களுக்கு வசதியாக இருக்கும்?"
                elif lang == "ta-Latn":
                    msg = f"{d}-la available slots: {top_slots}. Entha time ungalukku convenient-ah irukum?"
                elif lang == "te-IN":
                    msg = f"{d} తేదీన అందుబాటులో ఉన్న సమయాలు: {top_slots}. ఇందులో ఏ సమయం మీకు అనుకూలంగా ఉంటుంది?"
                elif lang == "te-Latn":
                    msg = f"{d}-lo available slots: {top_slots}. Ee time meeku convenient-ga untundi?"
                else:
                    msg = f"On {d}, available times are {top_slots}. Which slot works best for you?"

            return LLMResponse(text=msg, intent="check_availability", detected_language=lang)

        # Booking Success Result
        if data.get("success") and "appointment_id" in data and "new_appointment_time" not in data:
            appt_time = data.get("appointment_time", "")
            name = data.get("customer_name", "Caller")
            if lang == "ta-IN":
                msg = f"நன்றி {name}. உங்கள் முன்பதிவு வெற்றிகரமாக பதிவு செய்யப்பட்டது. அழைத்ததற்கு நன்றி. வணக்கம்!"
            elif lang == "ta-Latn":
                msg = f"Nandri {name}. Ungal appointment successfully confirm aagiruchu. Thank you for calling. Vanakkam!"
            elif lang == "te-IN":
                msg = f"ధన్యవాదాలు {name}. మీ అపాయింట్‌మెంట్ విజయవంతంగా నిర్ధారించబడింది. కాల్ చేసినందుకు ధన్యవాదాలు. నమస్కారం!"
            elif lang == "te-Latn":
                msg = f"Dhanyavadalu {name}. Mee appointment successfully confirm ayindi. Thank you for calling. Namaskaram!"
            else:
                msg = f"Thank you {name}. Your appointment has been successfully confirmed. Have a great day. Goodbye!"

            return LLMResponse(text=msg, intent="book_appointment", detected_language=lang, should_hangup=True)

        # Reschedule Success Result
        if data.get("success") and "new_appointment_time" in data:
            new_time = data.get("new_appointment_time", "")
            if lang == "ta-IN":
                msg = "உங்கள் முன்பதிவு நேரம் வெற்றிகரமாக மாற்றப்பட்டது. அழைத்ததற்கு நன்றி. வணக்கம்!"
            elif lang == "ta-Latn":
                msg = "Ungal appointment successfully reschedule aagiruchu. Thank you for calling. Vanakkam!"
            elif lang == "te-IN":
                msg = "మీ అపాయింట్‌మెంట్ సమయం విజయవంతంగా మార్చబడింది. కాల్ చేసినందుకు ధన్యవాదాలు. నమస్కారం!"
            elif lang == "te-Latn":
                msg = "Mee appointment successfully reschedule ayindi. Thank you for calling. Namaskaram!"
            else:
                msg = "Your appointment has been successfully rescheduled. Thank you for calling. Goodbye!"

            return LLMResponse(text=msg, intent="reschedule_appointment", detected_language=lang, should_hangup=True)

        # Cancellation Success Result
        if data.get("success") and "cancel_reason" in data:
            if lang == "ta-IN":
                msg = "உங்கள் முன்பதிவு வெற்றிகரமாக ரத்து செய்யப்பட்டது. அழைத்ததற்கு நன்றி. வணக்கம்!"
            elif lang == "ta-Latn":
                msg = "Ungal appointment successfully cancel aagiruchu. Thank you for calling. Vanakkam!"
            elif lang == "te-IN":
                msg = "మీ అపాయింట్‌మెంట్ విజయవంతంగా రద్దు చేయబడింది. కాల్ చేసినందుకు ధన్యవాదాలు. నమస్కారం!"
            elif lang == "te-Latn":
                msg = "Mee appointment successfully cancel cheyabadindi. Thank you for calling. Namaskaram!"
            else:
                msg = "Your appointment has been successfully cancelled and the slot has been released. Goodbye!"

            return LLMResponse(text=msg, intent="cancel_appointment", detected_language=lang, should_hangup=True)

        # Tool Error Result
        if "error" in data:
            err = data["error"]
            if lang == "ta-IN":
                msg = f"மன்னிக்கவும், பிழை: {err}. வேறு நேரம் அல்லது உதவியை தேர்வு செய்யலாமா?"
            elif lang == "ta-Latn":
                msg = f"Sorry, error: {err}. Vera time try pannalama?"
            elif lang == "te-IN":
                msg = f"క్షమించండి, లోపం: {err}. వేరే సమయం ప్రయత్నిద్దామా?"
            elif lang == "te-Latn":
                msg = f"Sorry, error: {err}. Vera time try cheddama?"
            else:
                msg = f"I apologize, but we could not complete that request: {err}. Would you like to select another time?"

            return LLMResponse(text=msg, intent="clarification", detected_language=lang)

        return LLMResponse(text="Request processed. How else can I assist you?", intent="clarification", detected_language=lang)
