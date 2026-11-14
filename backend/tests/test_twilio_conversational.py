"""Automated tests for Phase 6: Twilio Conversational Voice Assistant.

Verifies:
1. Incoming calls initiate <Gather input="speech"> pointing to /voice/webhooks/gather-speech.
2. Single-turn conversational booking in English.
3. Multi-turn slot filling (intent -> service -> datetime -> caller name).
4. Tamil language speech recognition, entity extraction, and conversational booking.
5. Idempotent duplicate webhook retry prevention (no duplicate bookings).
6. Unrecognized service catalog handling and clarification prompt.
7. Past appointment datetime rejection and re-prompting.
8. Cancellation / exit intent handling and polite hangup.
9. Multi-turn empty speech handling and graceful disconnect after 3 retries.
10. Security: Missing/invalid Twilio signature rejection (HTTP 403) and missing CallSid (HTTP 400).
"""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from twilio.request_validator import RequestValidator

from app.core.config import settings
from app.models.appointment import Appointment
from app.models.assistant import Service
from app.models.business import Business
from app.models.conversation_session import ConversationSession
from app.models.customer import Customer
from app.services.twilio_service import TwilioService, get_twilio_service

TEST_AUTH_TOKEN = "test_twilio_secret_token_abcdef12345"


@pytest.fixture
def twilio_mock_service() -> TwilioService:
    """Twilio service initialized with test credentials."""
    return TwilioService(
        account_sid="ACmock00000000000000000000000000",
        auth_token=TEST_AUTH_TOKEN,
        phone_number="+12292523194",
        public_base_url="https://pushiness-disparate-pulmonary.ngrok-free.dev",
    )


@pytest.fixture
def conversation_test_env(db_session: Session) -> dict[str, Business | Service]:
    """Create test clinic with active services for conversational voice tests."""
    biz = Business(
        id="biz-conversational-clinic",
        name="Apollo City Hospital",
        vertical="clinic",
        email="reception@apollocity.com",
        phone="+12292523194",
        is_active=True,
    )
    db_session.add(biz)
    db_session.flush()

    srv_cardio = Service(
        id="srv-cardio-1",
        business_id=biz.id,
        name="Cardiology Consultation",
        price=1200.0,
        duration_minutes=45,
        is_active=True,
    )
    srv_physician = Service(
        id="srv-physician-2",
        business_id=biz.id,
        name="General Physician Consultation",
        price=500.0,
        duration_minutes=30,
        is_active=True,
    )
    srv_dental = Service(
        id="srv-dental-3",
        business_id=biz.id,
        name="Dental Care & Cleaning",
        price=800.0,
        duration_minutes=30,
        is_active=True,
    )
    db_session.add_all([srv_cardio, srv_physician, srv_dental])
    db_session.commit()

    return {
        "biz": biz,
        "srv_cardio": srv_cardio,
        "srv_physician": srv_physician,
        "srv_dental": srv_dental,
    }


def compute_sig(url: str, params: dict[str, str], token: str = TEST_AUTH_TOKEN) -> str:
    """Helper to compute valid Twilio signature for test requests."""
    validator = RequestValidator(token)
    return validator.compute_signature(url, params)


# ==============================================================================
# 1. INCOMING CALL INITIATES GATHER SPEECH
# ==============================================================================

def test_incoming_call_initiates_speech_gather(
    client: TestClient,
    conversation_test_env: dict[str, Business | Service],
    twilio_mock_service: TwilioService,
    db_session: Session,
) -> None:
    """Verify incoming voice call initiates <Gather input="speech"> and creates persistent session."""
    from app.main import app
    app.dependency_overrides[get_twilio_service] = lambda: twilio_mock_service

    try:
        endpoint = f"{settings.API_V1_STR}/voice/webhooks/incoming"
        url = f"http://testserver{endpoint}"

        payload = {
            "CallSid": "CA_GATHER_INIT_001",
            "From": "+15559998888",
            "To": "+12292523194",
            "CallStatus": "ringing",
            "Direction": "inbound",
        }
        sig = compute_sig(url, payload)

        res = client.post(endpoint, data=payload, headers={"X-Twilio-Signature": sig})
        assert res.status_code == 200
        assert "application/xml" in res.headers["content-type"]
        xml = res.text
        assert "<Response>" in xml
        assert "<Gather" in xml
        assert 'input="speech"' in xml
        assert "/voice/webhooks/gather-speech" in xml
        assert "Apollo City Hospital" in xml

        # Verify persistent conversation session created in DB
        session = db_session.get(ConversationSession, "CA_GATHER_INIT_001")
        assert session is not None
        assert session.business_id == conversation_test_env["biz"].id
        assert session.caller_phone == "+15559998888"
        assert session.step == "greeting"
        assert not session.is_completed
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# 2. SINGLE-TURN BOOKING (ENGLISH)
# ==============================================================================

def test_single_turn_booking_english(
    client: TestClient,
    conversation_test_env: dict[str, Business | Service],
    twilio_mock_service: TwilioService,
    db_session: Session,
) -> None:
    """Verify single-turn utterance with all details books appointment directly."""
    from app.main import app
    app.dependency_overrides[get_twilio_service] = lambda: twilio_mock_service

    try:
        endpoint = f"{settings.API_V1_STR}/voice/webhooks/gather-speech"
        url = f"http://testserver{endpoint}"

        call_sid = "CA_SINGLE_TURN_ENG_002"
        payload = {
            "CallSid": call_sid,
            "From": "+15551234567",
            "To": "+12292523194",
            "SpeechResult": "I would like to book an appointment for Cardiology Consultation for tomorrow at 10:30 AM. My name is Alex Turner.",
            "Confidence": "0.95",
        }
        sig = compute_sig(url, payload)

        res = client.post(endpoint, data=payload, headers={"X-Twilio-Signature": sig})
        assert res.status_code == 200
        xml = res.text
        assert "<Response>" in xml
        assert "confirmed" in xml.lower()
        assert "Alex Turner" in xml
        assert "<Hangup" in xml

        # Verify Appointment record in database
        biz = conversation_test_env["biz"]
        srv = conversation_test_env["srv_cardio"]
        appt = db_session.scalar(
            select(Appointment).where(
                Appointment.business_id == biz.id,
                Appointment.service_id == srv.id,
            )
        )
        assert appt is not None
        assert appt.status == "upcoming"
        assert appt.source == "ai_call"

        # Verify Customer record
        cust = db_session.get(Customer, appt.customer_id)
        assert cust is not None
        assert cust.name == "Alex Turner"
        assert cust.phone == "+15551234567"

        # Verify session is marked completed with booking_id
        session = db_session.get(ConversationSession, call_sid)
        assert session is not None
        assert session.is_completed
        assert session.booking_id == appt.id
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# 3. MULTI-TURN SLOT FILLING FLOW
# ==============================================================================

def test_multi_turn_booking_flow(
    client: TestClient,
    conversation_test_env: dict[str, Business | Service],
    twilio_mock_service: TwilioService,
    db_session: Session,
) -> None:
    """Verify multi-turn flow: general intent -> service -> datetime -> caller name."""
    from app.main import app
    app.dependency_overrides[get_twilio_service] = lambda: twilio_mock_service

    try:
        endpoint = f"{settings.API_V1_STR}/voice/webhooks/gather-speech"
        url = f"http://testserver{endpoint}"
        call_sid = "CA_MULTI_TURN_003"
        caller_phone = "+15552345678"

        # Turn 1: Caller expresses intent without details
        p1 = {
            "CallSid": call_sid,
            "From": caller_phone,
            "To": "+12292523194",
            "SpeechResult": "Hi, I need to see a doctor for a checkup.",
        }
        res1 = client.post(endpoint, data=p1, headers={"X-Twilio-Signature": compute_sig(url, p1)})
        assert res1.status_code == 200
        xml1 = res1.text
        assert "<Gather" in xml1
        assert "Which medical service" in xml1 or "service would you like" in xml1

        s1 = db_session.get(ConversationSession, call_sid)
        assert s1.step == "awaiting_service"
        assert not s1.is_completed

        # Turn 2: Caller specifies service
        p2 = {
            "CallSid": call_sid,
            "From": caller_phone,
            "To": "+12292523194",
            "SpeechResult": "Cardiology Consultation please.",
        }
        res2 = client.post(endpoint, data=p2, headers={"X-Twilio-Signature": compute_sig(url, p2)})
        assert res2.status_code == 200
        xml2 = res2.text
        assert "<Gather" in xml2
        assert "date and time" in xml2.lower()

        db_session.refresh(s1)
        assert s1.service_id == conversation_test_env["srv_cardio"].id
        assert s1.step == "awaiting_datetime"

        # Turn 3: Caller specifies date and time
        p3 = {
            "CallSid": call_sid,
            "From": caller_phone,
            "To": "+12292523194",
            "SpeechResult": "Tomorrow at 2 PM.",
        }
        res3 = client.post(endpoint, data=p3, headers={"X-Twilio-Signature": compute_sig(url, p3)})
        assert res3.status_code == 200
        xml3 = res3.text
        assert "<Gather" in xml3
        assert "full name" in xml3.lower()

        db_session.refresh(s1)
        assert s1.appointment_datetime_iso is not None
        assert s1.step == "awaiting_name"

        # Turn 4: Caller provides name
        p4 = {
            "CallSid": call_sid,
            "From": caller_phone,
            "To": "+12292523194",
            "SpeechResult": "My name is Priya Sundaram.",
        }
        res4 = client.post(endpoint, data=p4, headers={"X-Twilio-Signature": compute_sig(url, p4)})
        assert res4.status_code == 200
        xml4 = res4.text
        assert "confirmed" in xml4.lower()
        assert "Priya Sundaram" in xml4
        assert "<Hangup" in xml4

        db_session.refresh(s1)
        assert s1.is_completed
        assert s1.booking_id is not None

        # Verify DB appointment
        appt = db_session.get(Appointment, s1.booking_id)
        assert appt is not None
        assert appt.customer.name == "Priya Sundaram"
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# 4. TAMIL LANGUAGE CONVERSATIONAL BOOKING
# ==============================================================================

def test_conversational_tamil_booking(
    client: TestClient,
    conversation_test_env: dict[str, Business | Service],
    twilio_mock_service: TwilioService,
    db_session: Session,
) -> None:
    """Verify Tamil speech input adapts language and successfully creates booking."""
    from app.main import app
    app.dependency_overrides[get_twilio_service] = lambda: twilio_mock_service

    try:
        endpoint = f"{settings.API_V1_STR}/voice/webhooks/gather-speech"
        url = f"http://testserver{endpoint}"
        call_sid = "CA_TAMIL_BOOKING_004"
        caller_phone = "+919840112233"

        # Single-turn Tamil request
        payload = {
            "CallSid": call_sid,
            "From": caller_phone,
            "To": "+12292523194",
            "SpeechResult": "வணக்கம், எனக்கு கார்டியாலஜி அப்பாயின்ட்மென்ட் நாளை காலை 10 மணிக்கு வேண்டும். என் பெயர் ரமேஷ்.",
            "Confidence": "0.92",
        }
        sig = compute_sig(url, payload)

        res = client.post(endpoint, data=payload, headers={"X-Twilio-Signature": sig})
        assert res.status_code == 200
        xml = res.text
        assert "<Response>" in xml
        assert "Polly.Valluvar" in xml
        assert "ரமேஷ்" in xml or "பதிவு" in xml

        # Verify session language adapted to ta-IN
        session = db_session.get(ConversationSession, call_sid)
        assert session is not None
        assert session.language == "ta-IN"
        assert session.is_completed
        assert session.booking_id is not None

        # Verify appointment booked
        appt = db_session.get(Appointment, session.booking_id)
        assert appt is not None
        assert appt.service_id == conversation_test_env["srv_cardio"].id
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# 5. IDEMPOTENT DUPLICATE WEBHOOK RETRY PREVENTION
# ==============================================================================

def test_duplicate_webhook_retry_idempotency(
    client: TestClient,
    conversation_test_env: dict[str, Business | Service],
    twilio_mock_service: TwilioService,
    db_session: Session,
) -> None:
    """Verify network retry of final webhook does not create duplicate appointments."""
    from app.main import app
    app.dependency_overrides[get_twilio_service] = lambda: twilio_mock_service

    try:
        endpoint = f"{settings.API_V1_STR}/voice/webhooks/gather-speech"
        url = f"http://testserver{endpoint}"
        call_sid = "CA_IDEMPOTENCY_005"
        caller_phone = "+15553334444"

        payload = {
            "CallSid": call_sid,
            "From": caller_phone,
            "To": "+12292523194",
            "SpeechResult": "Book General Physician Consultation for tomorrow at 11 AM. My name is David Miller.",
        }
        sig = compute_sig(url, payload)

        # First delivery: creates appointment
        res1 = client.post(endpoint, data=payload, headers={"X-Twilio-Signature": sig})
        assert res1.status_code == 200
        assert "confirmed" in res1.text.lower()

        # Count appointments in DB
        appts_count_1 = len(
            db_session.scalars(select(Appointment).where(Appointment.customer.has(phone=caller_phone))).all()
        )
        assert appts_count_1 == 1

        # Second delivery (Twilio retry): must NOT create a second appointment
        res2 = client.post(endpoint, data=payload, headers={"X-Twilio-Signature": sig})
        assert res2.status_code == 200
        assert "confirmed" in res2.text.lower()

        appts_count_2 = len(
            db_session.scalars(select(Appointment).where(Appointment.customer.has(phone=caller_phone))).all()
        )
        assert appts_count_2 == 1  # Exactly 1 appointment!
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# 6. UNRECOGNIZED SERVICE CATALOG HANDLING
# ==============================================================================

def test_unrecognized_service_prompts_catalog(
    client: TestClient,
    conversation_test_env: dict[str, Business | Service],
    twilio_mock_service: TwilioService,
    db_session: Session,
) -> None:
    """Verify requesting an unsupported service prompts with the clinic's active catalog."""
    from app.main import app
    app.dependency_overrides[get_twilio_service] = lambda: twilio_mock_service

    try:
        endpoint = f"{settings.API_V1_STR}/voice/webhooks/gather-speech"
        url = f"http://testserver{endpoint}"
        call_sid = "CA_UNRECOGNIZED_SRV_006"

        payload = {
            "CallSid": call_sid,
            "From": "+15554445555",
            "To": "+12292523194",
            "SpeechResult": "I want to schedule neurosurgery tomorrow morning.",
        }
        sig = compute_sig(url, payload)

        res = client.post(endpoint, data=payload, headers={"X-Twilio-Signature": sig})
        assert res.status_code == 200
        xml = res.text
        assert "<Gather" in xml
        assert "Which medical service" in xml or "service would you like" in xml

        session = db_session.get(ConversationSession, call_sid)
        assert session.service_id is None
        assert session.step == "awaiting_service"
        assert not session.is_completed
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# 7. PAST DATETIME REJECTION
# ==============================================================================

def test_past_datetime_rejection(
    client: TestClient,
    conversation_test_env: dict[str, Business | Service],
    twilio_mock_service: TwilioService,
    db_session: Session,
) -> None:
    """Verify past appointment dates are rejected and re-prompted."""
    from app.main import app
    app.dependency_overrides[get_twilio_service] = lambda: twilio_mock_service

    try:
        endpoint = f"{settings.API_V1_STR}/voice/webhooks/gather-speech"
        url = f"http://testserver{endpoint}"
        call_sid = "CA_PAST_DATE_007"

        # Explicit past date
        payload = {
            "CallSid": call_sid,
            "From": "+15555556666",
            "To": "+12292523194",
            "SpeechResult": "Book Cardiology Consultation for 2020-01-01 at 10 AM. My name is Time Traveler.",
        }
        sig = compute_sig(url, payload)

        res = client.post(endpoint, data=payload, headers={"X-Twilio-Signature": sig})
        assert res.status_code == 200
        xml = res.text
        assert "<Gather" in xml
        assert "past" in xml.lower()

        session = db_session.get(ConversationSession, call_sid)
        assert session.appointment_datetime_iso is None
        assert not session.is_completed
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# 8. CANCELLATION INTENT
# ==============================================================================

def test_cancellation_intent(
    client: TestClient,
    conversation_test_env: dict[str, Business | Service],
    twilio_mock_service: TwilioService,
    db_session: Session,
) -> None:
    """Verify caller saying goodbye or cancel is greeted politely and hung up."""
    from app.main import app
    app.dependency_overrides[get_twilio_service] = lambda: twilio_mock_service

    try:
        endpoint = f"{settings.API_V1_STR}/voice/webhooks/gather-speech"
        url = f"http://testserver{endpoint}"
        call_sid = "CA_CANCEL_008"

        payload = {
            "CallSid": call_sid,
            "From": "+15556667777",
            "To": "+12292523194",
            "SpeechResult": "No thanks, cancel that, goodbye.",
        }
        sig = compute_sig(url, payload)

        res = client.post(endpoint, data=payload, headers={"X-Twilio-Signature": sig})
        assert res.status_code == 200
        xml = res.text
        assert "goodbye" in xml.lower()
        assert "<Hangup" in xml

        session = db_session.get(ConversationSession, call_sid)
        assert session.is_completed
        assert session.booking_id is None
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# 9. EMPTY SPEECH RETRIES AND DISCONNECT
# ==============================================================================

def test_empty_speech_retries_and_disconnect(
    client: TestClient,
    conversation_test_env: dict[str, Business | Service],
    twilio_mock_service: TwilioService,
    db_session: Session,
) -> None:
    """Verify 3 consecutive empty speech inputs results in polite disconnect."""
    from app.main import app
    app.dependency_overrides[get_twilio_service] = lambda: twilio_mock_service

    try:
        endpoint = f"{settings.API_V1_STR}/voice/webhooks/gather-speech"
        url = f"http://testserver{endpoint}"
        call_sid = "CA_EMPTY_SPEECH_009"
        payload = {
            "CallSid": call_sid,
            "From": "+15557778888",
            "To": "+12292523194",
            "SpeechResult": "",  # Empty input
        }
        sig = compute_sig(url, payload)

        # Retry 1
        res1 = client.post(endpoint, data=payload, headers={"X-Twilio-Signature": sig})
        assert res1.status_code == 200
        assert "<Gather" in res1.text

        # Retry 2
        res2 = client.post(endpoint, data=payload, headers={"X-Twilio-Signature": sig})
        assert res2.status_code == 200
        assert "<Gather" in res2.text

        # Retry 3: Must disconnect
        res3 = client.post(endpoint, data=payload, headers={"X-Twilio-Signature": sig})
        assert res3.status_code == 200
        assert "unable to hear" in res3.text.lower() or "goodbye" in res3.text.lower()
        assert "<Hangup" in res3.text

        session = db_session.get(ConversationSession, call_sid)
        assert session.is_completed
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# 10. SECURITY & VALIDATION
# ==============================================================================

def test_gather_speech_missing_signature_rejected(
    client: TestClient,
    conversation_test_env: dict[str, Business | Service],
    twilio_mock_service: TwilioService,
) -> None:
    """Verify missing X-Twilio-Signature returns HTTP 403 Forbidden."""
    from app.main import app
    app.dependency_overrides[get_twilio_service] = lambda: twilio_mock_service

    try:
        endpoint = f"{settings.API_V1_STR}/voice/webhooks/gather-speech"
        payload = {"CallSid": "CA_SEC_010", "From": "+15558889999", "To": "+12292523194"}
        res = client.post(endpoint, data=payload)
        assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_gather_speech_invalid_signature_rejected(
    client: TestClient,
    conversation_test_env: dict[str, Business | Service],
    twilio_mock_service: TwilioService,
) -> None:
    """Verify forged X-Twilio-Signature returns HTTP 403 Forbidden."""
    from app.main import app
    app.dependency_overrides[get_twilio_service] = lambda: twilio_mock_service

    try:
        endpoint = f"{settings.API_V1_STR}/voice/webhooks/gather-speech"
        payload = {"CallSid": "CA_SEC_011", "From": "+15558889999", "To": "+12292523194"}
        res = client.post(endpoint, data=payload, headers={"X-Twilio-Signature": "forged_signature_value"})
        assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_gather_speech_missing_call_sid_rejected(
    client: TestClient,
    conversation_test_env: dict[str, Business | Service],
    twilio_mock_service: TwilioService,
) -> None:
    """Verify request missing CallSid returns HTTP 400 Bad Request."""
    from app.main import app
    app.dependency_overrides[get_twilio_service] = lambda: twilio_mock_service

    try:
        endpoint = f"{settings.API_V1_STR}/voice/webhooks/gather-speech"
        url = f"http://testserver{endpoint}"
        payload = {"From": "+15558889999", "To": "+12292523194"}
        sig = compute_sig(url, payload)

        res = client.post(endpoint, data=payload, headers={"X-Twilio-Signature": sig})
        assert res.status_code == 400
        assert "CallSid" in res.json()["detail"]
    finally:
        app.dependency_overrides.clear()
