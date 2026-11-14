"""Tata Smartflo Cloud Telephony Integration Routes.

Endpoints:
- POST /api/v1/integrations/smartflo/webhook: Status milestone callbacks (ringing, answered, completed, missed).
- POST /api/v1/integrations/smartflo/dialplan: Inbound API Dialplan routing webhooks.
- POST /api/v1/integrations/smartflo/outbound-call: Outbound Click-to-Call initiation.
- GET  /api/v1/integrations/smartflo/status: Telephony integration configuration status.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db_session
from app.api.routes.voice import (
    clean_phone_digits,
    resolve_business_by_phone,
    resolve_or_create_customer,
)
from app.core.config import settings
from app.core.logging import get_logger
from app.models.business import Business
from app.models.call import Call
from app.models.conversation_session import ConversationSession
from app.models.user import User
from app.services.telephony.base import CallStatus, OutboundCallRequest
from app.services.telephony.security import mask_phone, mask_secret, verify_webhook_token
from app.services.telephony.smartflo_adapter import SmartfloAdapter
from app.services.voice_assistant_service import get_or_create_conversation_session

logger = get_logger(__name__)
router = APIRouter()


class SmartfloOutboundCallPayload(BaseModel):
    """Payload to trigger an outbound call via Tata Smartflo."""

    destination_phone: str = Field(..., description="Target customer phone number (E.164 or 10-digit)")
    caller_id: str | None = Field(default=None, description="Smartflo DID caller ID override")
    agent_phone: str | None = Field(default=None, description="Agent phone number to connect")
    timeout_seconds: int = Field(default=300, ge=30, le=900)
    custom_identifier: dict[str, Any] = Field(default_factory=dict)


async def _extract_request_payload(request: Request) -> dict[str, Any]:
    """Safely extract payload whether delivered as JSON or application/x-www-form-urlencoded."""
    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        try:
            body = await request.json()
            return body if isinstance(body, dict) else {}
        except Exception:
            return {}
    try:
        form = await request.form()
        return dict(form)
    except Exception:
        try:
            body = await request.json()
            return body if isinstance(body, dict) else {}
        except Exception:
            return {}


def _authenticate_smartflo_webhook(
    headers: dict[str, str],
    query_token: str | None,
    payload: dict[str, Any],
) -> None:
    """Validate incoming Smartflo webhook authenticity using constant-time comparison."""
    if not settings.SMARTFLO_WEBHOOK_TOKEN:
        # If no webhook secret is configured on the server, allow requests (e.g. dev/unconfigured)
        return

    # Extract token candidate from headers, query, or payload
    provided_token: str | None = (
        headers.get("x-smartflo-token")
        or headers.get("X-Smartflo-Token")
        or headers.get("x-webhook-token")
        or headers.get("X-Webhook-Token")
    )

    auth_header = headers.get("authorization") or headers.get("Authorization")
    if not provided_token and auth_header and auth_header.startswith("Bearer "):
        provided_token = auth_header[7:].strip()

    if not provided_token and query_token:
        provided_token = query_token.strip()

    if not provided_token and "token" in payload:
        provided_token = str(payload["token"]).strip()

    if not provided_token or not verify_webhook_token(provided_token, settings.SMARTFLO_WEBHOOK_TOKEN):
        logger.warning(
            "Rejected Tata Smartflo webhook: invalid or missing token (%s)",
            mask_secret(provided_token),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Smartflo webhook token.",
        )


@router.get(
    "/status",
    summary="Tata Smartflo Integration Status",
    description="Check whether Tata Smartflo credentials and webhooks are configured.",
)
def get_smartflo_status() -> dict[str, Any]:
    """Return Smartflo configuration health status."""
    return {
        "provider": "smartflo",
        "configured": settings.is_smartflo_configured,
        "base_url": settings.SMARTFLO_BASE_URL,
        "caller_id": mask_phone(settings.SMARTFLO_CALLER_ID),
        "webhook_token_configured": bool(settings.SMARTFLO_WEBHOOK_TOKEN),
        "did_mapping_count": len(settings.get_smartflo_did_map()),
    }


@router.post(
    "/webhook",
    summary="Tata Smartflo Call Status Webhook",
    description=(
        "Receive call milestone callbacks (ringing, answered, completed, missed) "
        "from Tata Smartflo. Idempotently updates or records call history."
    ),
)
async def handle_smartflo_webhook(
    request: Request,
    token: str | None = Query(default=None),
    x_smartflo_token: str | None = Header(default=None, alias="X-Smartflo-Token"),
    x_webhook_token: str | None = Header(default=None, alias="X-Webhook-Token"),
    db: Session = Depends(get_db_session),
) -> dict[str, Any]:
    """Process Smartflo call milestone event callbacks."""
    headers = dict(request.headers)
    payload = await _extract_request_payload(request)

    # 1. Authenticate webhook
    _authenticate_smartflo_webhook(headers, token, payload)

    # 2. Parse status event
    adapter = SmartfloAdapter()
    event = adapter.parse_status_callback(payload, headers)
    call_id = event.call_id

    if not call_id:
        logger.warning("Smartflo webhook received without uuid/call_id/ref_id")
        return {"status": "ignored", "reason": "Missing call identifier"}

    logger.info(
        "Smartflo webhook event | call_id=%s | status=%s | duration=%ds",
        call_id,
        event.status.value,
        event.duration_seconds,
    )

    # 3. Idempotency check: Search for existing Call record
    call_record = db.scalar(
        select(Call).where(
            or_(
                Call.id == call_id,
                Call.summary.like(f"%{call_id}%"),
            )
        )
    )

    now = datetime.now(timezone.utc)

    if call_record:
        # Update existing record
        call_record.status = event.status.value
        if event.duration_seconds > call_record.duration_seconds:
            call_record.duration_seconds = event.duration_seconds
        if event.recording_url:
            call_record.recording_url = event.recording_url
        if event.status in (CallStatus.COMPLETED, CallStatus.MISSED, CallStatus.FAILED, CallStatus.BUSY):
            if not call_record.ended_at:
                call_record.ended_at = now
        db.commit()
        logger.info(
            "Updated existing call session ID %s to status %s",
            call_record.id,
            call_record.status,
        )
    else:
        # Resolve business tenant from custom_identifier, DID mapping, or phone
        business_id = event.custom_identifier.get("business_id")
        destination_phone = str(payload.get("call_to_number") or payload.get("to") or payload.get("caller_id") or "")
        caller_phone = str(payload.get("caller_id_number") or payload.get("from") or payload.get("customer_number") or "+910000000000")

        if not business_id and destination_phone:
            did_map = settings.get_smartflo_did_map()
            clean_dest = destination_phone.replace("+", "").strip()
            business_id = did_map.get(clean_dest) or did_map.get(destination_phone)

        business: Business | None = None
        if business_id:
            business = db.get(Business, business_id)
        if not business and destination_phone:
            business = resolve_business_by_phone(db, destination_phone)
        if not business:
            business = db.scalar(select(Business).where(Business.is_active.is_(True)).limit(1))

        if business:
            customer = resolve_or_create_customer(db, business.id, caller_phone)
            call_db_id = call_id if len(call_id) <= 36 else str(uuid.uuid4())
            new_call = Call(
                id=call_db_id,
                business_id=business.id,
                customer_id=customer.id if customer else None,
                caller_name=customer.name if customer else None,
                caller_phone=caller_phone,
                call_type="incoming",
                status=event.status.value,
                duration_seconds=event.duration_seconds,
                summary=f"Tata Smartflo Call (UUID: {call_id})",
                transcript=None,
                recording_url=event.recording_url,
                initiated_at=now,
                ended_at=now if event.status in (CallStatus.COMPLETED, CallStatus.MISSED, CallStatus.FAILED, CallStatus.BUSY) else None,
            )
            db.add(new_call)
            db.commit()
            logger.info(
                "Created new call record ID %s for Smartflo Call %s (Business: %s)",
                new_call.id,
                call_id,
                business.id,
            )

    return {
        "status": "ok",
        "provider": "smartflo",
        "call_id": call_id,
        "call_status": event.status.value,
    }


@router.post(
    "/dialplan",
    summary="Tata Smartflo Inbound API Dialplan Webhook",
    description=(
        "Handle inbound call events from Smartflo API Dialplan and return "
        "JSON action routing instructions (e.g. transfer to agent)."
    ),
)
async def handle_smartflo_dialplan(
    request: Request,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """Process inbound call dialplan request and return JSON routing actions."""
    headers = dict(request.headers)
    payload = await _extract_request_payload(request)

    # 1. Authenticate webhook
    _authenticate_smartflo_webhook(headers, token, payload)

    # 2. Parse inbound call
    adapter = SmartfloAdapter()
    inbound = adapter.parse_inbound_call(payload, headers)

    # 3. Resolve destination business tenant
    business_id = inbound.business_id
    business: Business | None = None
    if business_id:
        business = db.get(Business, business_id)

    if not business and inbound.destination_phone:
        business = resolve_business_by_phone(db, inbound.destination_phone)

    if not business:
        business = db.scalar(select(Business).where(Business.is_active.is_(True)).limit(1))

    if not business or not business.is_active:
        logger.warning(
            "Smartflo dialplan request could not resolve active business for destination %s",
            inbound.destination_phone,
        )
        return []

    # 4. Resolve or register caller customer
    customer = resolve_or_create_customer(db, business.id, inbound.caller_phone)

    # 5. Pre-register conversation session
    if inbound.call_id:
        get_or_create_conversation_session(
            db=db,
            call_sid=inbound.call_id,
            business_id=business.id,
            caller_phone=inbound.caller_phone,
        )

    # 6. Idempotently register Call record
    if inbound.call_id:
        existing = db.scalar(
            select(Call).where(
                or_(
                    Call.id == inbound.call_id,
                    Call.summary.like(f"%{inbound.call_id}%"),
                )
            )
        )
        if not existing:
            now = datetime.now(timezone.utc)
            call_db_id = inbound.call_id if len(inbound.call_id) <= 36 else str(uuid.uuid4())
            new_call = Call(
                id=call_db_id,
                business_id=business.id,
                customer_id=customer.id if customer else None,
                caller_name=customer.name if customer else None,
                caller_phone=inbound.caller_phone,
                call_type="incoming",
                status="ringing",
                duration_seconds=0,
                summary=f"Inbound Tata Smartflo Call (UUID: {inbound.call_id})",
                transcript=f"Incoming call routed to {business.name}",
                initiated_at=now,
            )
            db.add(new_call)
            db.commit()

    # 7. Generate Smartflo transfer action to business phone or agent
    transfer_agent = business.phone or settings.SMARTFLO_CALLER_ID or "0"
    actions = adapter.build_dialplan_transfer_response(
        agent_number=transfer_agent,
        business_id=business.id,
        custom_parameter_1=customer.name if customer else None,
    )

    logger.info(
        "Returned Smartflo dialplan actions for call %s -> transfer to %s",
        inbound.call_id,
        mask_phone(transfer_agent),
    )

    return actions


@router.post(
    "/outbound-call",
    summary="Initiate Tata Smartflo Outbound Call",
    description="Trigger an outbound Click-to-Call request via Tata Smartflo for the authenticated tenant.",
)
def trigger_smartflo_outbound_call(
    payload: SmartfloOutboundCallPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> dict[str, Any]:
    """Trigger an outbound call using Smartflo Click-to-Call REST API."""
    # Enforce multi-tenant isolation
    business_id = current_user.business_id

    caller_id = payload.caller_id or settings.SMARTFLO_CALLER_ID
    if not caller_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Caller ID (DID) is required. Set SMARTFLO_CALLER_ID in configuration or pass in request.",
        )

    adapter = SmartfloAdapter()
    req = OutboundCallRequest(
        destination_phone=payload.destination_phone,
        caller_id=caller_id,
        business_id=business_id,
        agent_phone=payload.agent_phone,
        timeout_seconds=payload.timeout_seconds,
        custom_identifier=payload.custom_identifier,
    )

    response = adapter.initiate_outbound_call(req)

    if not response.success:
        logger.error(
            "Smartflo outbound call failed for tenant %s: %s",
            business_id,
            response.message,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Smartflo outbound call failed: {response.message}",
        )

    # Persist outbound Call record
    now = datetime.now(timezone.utc)
    call_id = response.call_id if (response.call_id and len(response.call_id) <= 36) else str(uuid.uuid4())
    call_record = Call(
        id=call_id,
        business_id=business_id,
        caller_name=None,
        caller_phone=payload.destination_phone,
        call_type="outgoing",
        status="in_progress",
        duration_seconds=0,
        summary=f"Outbound Smartflo call (Ref: {response.reference_id})",
        transcript=None,
        initiated_at=now,
    )
    db.add(call_record)
    db.commit()

    logger.info(
        "Initiated outbound Smartflo call ID %s (Ref: %s) for tenant %s",
        call_record.id,
        response.reference_id,
        business_id,
    )

    return {
        "success": True,
        "provider": "smartflo",
        "call_id": call_record.id,
        "reference_id": response.reference_id,
        "message": response.message,
    }
