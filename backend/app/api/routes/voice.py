"""Voice telephony API routes for Twilio webhook processing and conversational assistant."""

import re
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from app.api.deps import get_db_session
from app.core.config import settings
from app.core.logging import get_logger
from app.models.business import Business
from app.models.call import Call
from app.models.conversation_session import ConversationSession
from app.models.customer import Customer
from app.services.dashboard_events import dashboard_event_manager
from app.services.twilio_service import TwilioService, get_twilio_service
from app.services.voice_assistant_service import (
    get_or_create_conversation_session,
    process_conversational_turn,
)

logger = get_logger(__name__)
router = APIRouter()


def clean_phone_digits(phone: str | None) -> str:
    """Strip all non-numeric characters from a phone number for relaxed matching."""
    if not phone:
        return ""
    return re.sub(r"\D", "", phone)


def resolve_business_by_phone(db: Session, destination_phone: str) -> Business | None:
    """Identify the business tenant associated with the incoming destination phone number."""
    clean_to = destination_phone.strip()
    to_digits = clean_phone_digits(clean_to)

    # 1. Direct exact match on Business.phone
    business = db.scalar(
        select(Business).where(Business.phone == clean_to, Business.is_active.is_(True))
    )
    if business:
        return business

    # 2. Relaxed digit-only comparison against active businesses
    if to_digits:
        active_businesses = db.scalars(
            select(Business).where(Business.is_active.is_(True), Business.phone.isnot(None))
        ).all()
        for b in active_businesses:
            if b.phone and clean_phone_digits(b.phone) == to_digits:
                return b

    # 3. Check BusinessIntegration phone numbers (Plivo / Twilio / Smartflo)
    try:
        from app.models.integration import BusinessIntegration
        integrations = db.scalars(select(BusinessIntegration)).all()
        for integ in integrations:
            candidate_phones = [
                getattr(integ, "plivo_phone_number", None),
                getattr(integ, "twilio_phone_number", None),
                getattr(integ, "smartflo_caller_id", None),
            ]
            for cp in candidate_phones:
                if cp and (cp == clean_to or (to_digits and clean_phone_digits(cp) == to_digits)):
                    biz = db.get(Business, integ.business_id)
                    if biz and biz.is_active:
                        return biz
    except Exception:
        pass

    # 4. Check if destination phone matches global platform PLIVO_PHONE_NUMBER or TWILIO_PHONE_NUMBER
    configured_global_numbers = [
        getattr(settings, "PLIVO_PHONE_NUMBER", None),
        getattr(settings, "TWILIO_PHONE_NUMBER", None),
    ]
    for gn in configured_global_numbers:
        if gn and to_digits and clean_phone_digits(gn) == to_digits:
            matched_biz = db.scalar(
                select(Business).where(
                    Business.phone == gn, Business.is_active.is_(True)
                )
            )
            if matched_biz:
                return matched_biz

            # Fallback to the primary active business if only one tenant is deployed
            primary_biz = db.scalar(select(Business).where(Business.is_active.is_(True)).limit(1))
            if primary_biz:
                return primary_biz

    return None


def resolve_or_create_customer(db: Session, business_id: str, caller_phone: str) -> Customer:
    """Find existing customer by phone number within the tenant, or create a new customer record."""
    clean_from = caller_phone.strip()
    from_digits = clean_phone_digits(clean_from)

    # 1. Exact match within tenant
    customer = db.scalar(
        select(Customer).where(
            Customer.business_id == business_id, Customer.phone == clean_from
        )
    )
    if customer:
        customer.total_calls = (customer.total_calls or 0) + 1
        db.commit()
        db.refresh(customer)
        return customer

    # 2. Relaxed digit match within tenant
    if from_digits:
        tenant_customers = db.scalars(
            select(Customer).where(Customer.business_id == business_id)
        ).all()
        for c in tenant_customers:
            if c.phone and clean_phone_digits(c.phone) == from_digits:
                c.total_calls = (c.total_calls or 0) + 1
                db.commit()
                db.refresh(c)
                return c

    # 3. Customer does not exist; create new customer
    customer = Customer(
        business_id=business_id,
        name=f"Caller {clean_from}",
        phone=clean_from,
        notes="Auto-created from incoming voice receptionist call.",
        total_calls=1,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    logger.info(
        "Created new customer ID %s for caller %s in Business ID %s",
        customer.id,
        clean_from,
        business_id,
    )
    return customer


@router.post(
    "/webhooks/incoming",
    summary="Incoming Twilio Voice Call Webhook",
    description="Receive Twilio voice call webhook, authenticate signature, identify business/customer, log call session, and return TwiML with speech gather.",
    response_class=Response,
    responses={
        200: {
            "description": "TwiML XML response with speech gather and welcome greeting.",
            "content": {"application/xml": {}},
        },
        400: {"description": "Missing required Twilio call parameters."},
        403: {"description": "Invalid or missing Twilio signature."},
    },
)
async def handle_incoming_call(
    request: Request,
    x_twilio_signature: str | None = Header(default=None, alias="X-Twilio-Signature"),
    db: Session = Depends(get_db_session),
    twilio_service: TwilioService = Depends(get_twilio_service),
) -> Response:
    """Process incoming voice webhook from Twilio."""
    # 1. Parse form parameters sent by Twilio
    form_data = dict(await request.form())

    # 2. Validate Twilio request signature
    url = str(request.url)
    fallback_uris: list[str] = []

    if settings.PUBLIC_BASE_URL:
        public_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}{request.url.path}"
        if request.url.query:
            public_url = f"{public_url}?{request.url.query}"
        fallback_uris.append(public_url)

    # Support scheme mismatches behind reverse proxies (http vs https)
    if url.startswith("http://"):
        fallback_uris.append(url.replace("http://", "https://", 1))
    elif url.startswith("https://"):
        fallback_uris.append(url.replace("https://", "http://", 1))

    is_valid = twilio_service.validate_request_signature(
        uri=url,
        params=form_data,
        signature=x_twilio_signature,
        fallback_uris=fallback_uris,
    )

    if not is_valid:
        logger.warning(
            "Rejected Twilio voice webhook with invalid signature. URL: %s, Signature: %s",
            url,
            x_twilio_signature,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Twilio signature.",
        )

    # 3. Extract core call parameters
    call_sid = form_data.get("CallSid")
    caller_from = form_data.get("From")
    destination_to = form_data.get("To")
    call_status = form_data.get("CallStatus", "ringing")
    direction = form_data.get("Direction", "inbound")

    if not call_sid or not caller_from or not destination_to:
        logger.error("Missing mandatory Twilio webhook fields. Data: %s", form_data)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required Twilio call parameters (CallSid, From, To).",
        )

    # 4. Identify the destination business organization
    business = resolve_business_by_phone(db, destination_to)
    if not business:
        logger.warning(
            "Call received for unmapped destination number '%s' (CallSid: %s).",
            destination_to,
            call_sid,
        )
        unknown_twiml = twilio_service.build_unknown_number_twiml()
        return Response(content=unknown_twiml, media_type="application/xml", status_code=status.HTTP_200_OK)

    # 5. Identify or register the caller as a customer
    customer = resolve_or_create_customer(db, business.id, caller_from)

    # 6. Save or update Call record (idempotency check)
    mapped_status = "in_progress" if call_status in ("ringing", "in-progress", "queued") else call_status
    existing_call = db.scalar(
        select(Call).where(
            or_(
                Call.id == call_sid,
                Call.summary.like(f"%{call_sid}%"),
            )
        )
    )

    if existing_call:
        existing_call.status = mapped_status
        db.commit()
        logger.info(
            "Updated existing call session record for CallSid: %s (Status: %s)",
            call_sid,
            mapped_status,
        )
    else:
        call_id = call_sid if len(call_sid) <= 36 else str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        call_record = Call(
            id=call_id,
            business_id=business.id,
            customer_id=customer.id,
            caller_name=customer.name,
            caller_phone=caller_from.strip(),
            call_type="incoming",
            status=mapped_status,
            duration_seconds=0,
            summary=f"Incoming voice call via Twilio (CallSid: {call_sid})",
            transcript=f"AI: Thank you for calling {business.name}. How can we assist you today?",
            recording_url=None,
            initiated_at=now,
        )
        db.add(call_record)
        db.commit()
        logger.info(
            "Logged incoming call session (ID %s, CallSid: %s) for Business '%s' (ID %s)",
            call_record.id,
            call_sid,
            business.name,
            business.id,
        )

    # 7. Initialize persistent conversation session
    gather_action_url = f"{settings.API_V1_STR}/voice/webhooks/gather-speech"
    session = get_or_create_conversation_session(
        db=db,
        call_sid=call_sid,
        business_id=business.id,
        caller_phone=caller_from.strip(),
    )

    # 8. Generate TwiML welcome greeting with <Gather input="speech">
    twiml_content = twilio_service.build_welcome_twiml(
        business_name=business.name,
        action_url=gather_action_url,
        language=session.language,
    )

    dashboard_event_manager.dispatch(
        business_id=business.id,
        event_type="CALL_STARTED",
        data={
            "call_id": call_sid,
            "caller_phone": caller_from.strip(),
            "caller_name": customer.name if customer else f"Caller {caller_from}",
            "status": mapped_status,
            "call_type": "incoming",
            "language": session.language,
            "started_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    return Response(content=twiml_content, media_type="application/xml", status_code=status.HTTP_200_OK)


@router.post(
    "/webhooks/gather-speech",
    summary="Twilio Speech Result Webhook",
    description="Receive speech transcription from Twilio <Gather input='speech'>, advance conversation state, and return conversational TwiML.",
    response_class=Response,
    responses={
        200: {
            "description": "TwiML XML response with next speech question or confirmation.",
            "content": {"application/xml": {}},
        },
        400: {"description": "Missing required call parameters."},
        403: {"description": "Invalid or missing Twilio signature."},
    },
)
async def handle_gather_speech(
    request: Request,
    x_twilio_signature: str | None = Header(default=None, alias="X-Twilio-Signature"),
    db: Session = Depends(get_db_session),
    twilio_service: TwilioService = Depends(get_twilio_service),
) -> Response:
    """Process speech recognition result from Twilio Gather and advance conversation."""
    form_data = dict(await request.form())

    # Validate Twilio signature
    url = str(request.url)
    fallback_uris: list[str] = []

    if settings.PUBLIC_BASE_URL:
        public_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}{request.url.path}"
        if request.url.query:
            public_url = f"{public_url}?{request.url.query}"
        fallback_uris.append(public_url)

    if url.startswith("http://"):
        fallback_uris.append(url.replace("http://", "https://", 1))
    elif url.startswith("https://"):
        fallback_uris.append(url.replace("https://", "http://", 1))

    is_valid = twilio_service.validate_request_signature(
        uri=url,
        params=form_data,
        signature=x_twilio_signature,
        fallback_uris=fallback_uris,
    )
    if not is_valid:
        logger.warning("Rejected gather-speech webhook with invalid signature: %s", x_twilio_signature)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Twilio signature.",
        )

    call_sid = form_data.get("CallSid")
    destination_to = form_data.get("To", "")
    caller_from = form_data.get("From", "")
    speech_result = form_data.get("SpeechResult")

    if not call_sid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing CallSid in request.",
        )

    # Identify business tenant
    business = resolve_business_by_phone(db, destination_to) if destination_to else None
    if not business:
        existing_session = db.get(ConversationSession, call_sid)
        if existing_session:
            business = db.get(Business, existing_session.business_id)

    if not business:
        business = db.scalar(select(Business).where(Business.is_active.is_(True)).limit(1))

    if not business:
        unknown_twiml = twilio_service.build_unknown_number_twiml()
        return Response(content=unknown_twiml, media_type="application/xml", status_code=status.HTTP_200_OK)

    # Retrieve or create persistent conversation session
    session = get_or_create_conversation_session(
        db=db,
        call_sid=call_sid,
        business_id=business.id,
        caller_phone=caller_from or "+10000000000",
    )

    # Advance conversation
    if speech_result:
        dashboard_event_manager.dispatch(
            business_id=business.id,
            event_type="TRANSCRIPT_RECEIVED",
            data={
                "call_id": call_sid,
                "speaker": "caller",
                "text": speech_result,
                "language": session.language,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    prompt_or_confirmation, should_gather = process_conversational_turn(
        db=db,
        session=session,
        speech_text=speech_result,
        business=business,
    )

    dashboard_event_manager.dispatch(
        business_id=business.id,
        event_type="AI_RESPONSE_GENERATED",
        data={
            "call_id": call_sid,
            "speaker": "assistant",
            "text": prompt_or_confirmation,
            "language": session.language,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )

    if not should_gather:
        dashboard_event_manager.dispatch(
            business_id=business.id,
            event_type="CALL_COMPLETED",
            data={
                "call_id": call_sid,
                "status": "completed",
                "ended_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    gather_action_url = f"{settings.API_V1_STR}/voice/webhooks/gather-speech"
    if should_gather:
        twiml_xml = twilio_service.build_gather_speech_twiml(
            prompt=prompt_or_confirmation,
            action_url=gather_action_url,
            language=session.language,
        )
    else:
        twiml_xml = twilio_service.build_speech_confirmation_twiml(
            message=prompt_or_confirmation,
            language=session.language,
        )

    return Response(content=twiml_xml, media_type="application/xml", status_code=status.HTTP_200_OK)
