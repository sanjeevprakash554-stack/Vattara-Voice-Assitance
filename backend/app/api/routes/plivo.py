"""Plivo Programmable Voice Telephony Routes.

Endpoints:
- POST      /api/v1/plivo/incoming: Inbound Answer URL webhook generating bidirectional <Stream> XML.
- WEBSOCKET /api/v1/plivo/stream: Real-time bidirectional WebSocket audio stream.
- POST      /api/v1/plivo/status: Hangup and call lifecycle status callback webhook.
- GET       /api/v1/plivo/status: Telephony configuration and connectivity status probe.
"""

import asyncio
from datetime import datetime, timezone
import json
from typing import Any
import uuid
from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
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
from app.services.plivo_service import PlivoService, get_plivo_service
from app.services.streaming.session_manager import stream_manager
from app.services.streaming.stream_orchestrator import StreamOrchestrator
from app.services.telephony.phone_utils import normalize_indian_mobile_number
from app.services.voice_assistant_service import get_or_create_conversation_session

logger = get_logger(__name__)
router = APIRouter()


@router.post(
    "/incoming",
    summary="Plivo Inbound Voice Webhook (Answer URL)",
    description="Receive incoming call from Plivo, authenticate V3 signature, resolve business and customer, log call session, and return Plivo XML with bidirectional <Stream>.",
    response_class=Response,
    responses={
        200: {"content": {"application/xml": {}}},
        400: {"description": "Missing required call parameters."},
        403: {"description": "Invalid Plivo signature."},
    },
)
async def handle_plivo_incoming_call(
    request: Request,
    x_plivo_signature_v3: str | None = Header(default=None, alias="X-Plivo-Signature-V3"),
    x_plivo_signature_v3_nonce: str | None = Header(default=None, alias="X-Plivo-Signature-V3-Nonce"),
    db: Session = Depends(get_db_session),
    plivo_service: PlivoService = Depends(get_plivo_service),
) -> Response:
    """Process incoming voice call from Plivo carrier."""
    # 1. Parse payload (supports application/x-www-form-urlencoded or JSON)
    form_data: dict[str, Any] = {}
    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        try:
            body = await request.json()
            if isinstance(body, dict):
                form_data = body
        except Exception:
            pass
    if not form_data:
        try:
            form = await request.form()
            form_data = dict(form)
        except Exception:
            pass

    # 2. Extract Plivo headers (support standard V3, Main Account V3, and legacy headers)
    sig = (
        x_plivo_signature_v3
        or request.headers.get("x-plivo-signature-v3")
        or request.headers.get("x-plivo-signature-ma-v3")
        or request.headers.get("x-plivo-signature")
    )
    nonce = (
        x_plivo_signature_v3_nonce
        or request.headers.get("x-plivo-signature-v3-nonce")
        or request.headers.get("x-plivo-signature-v2-nonce")
    )

    # 3. Validate Plivo V3 Request Signature with reverse-proxy aware URI candidates
    url = str(request.url)
    fallback_uris: list[str] = []

    # Check reverse-proxy forwarded headers (ngrok, Nginx, ALB)
    fwd_proto = request.headers.get("x-forwarded-proto") or request.url.scheme or "https"
    fwd_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if fwd_host:
        fwd_url = f"{fwd_proto}://{fwd_host}{request.url.path}"
        if request.url.query:
            fwd_url = f"{fwd_url}?{request.url.query}"
        fallback_uris.append(fwd_url)

    if settings.PUBLIC_BASE_URL:
        clean_base = settings.PUBLIC_BASE_URL.rstrip("/")
        pub_url = f"{clean_base}{request.url.path}"
        if request.url.query:
            pub_url = f"{pub_url}?{request.url.query}"
        fallback_uris.append(pub_url)

    if url.startswith("http://"):
        fallback_uris.append(url.replace("http://", "https://", 1))
    elif url.startswith("https://"):
        fallback_uris.append(url.replace("https://", "http://", 1))

    is_valid = plivo_service.validate_v3_signature(
        uri=url,
        nonce=nonce,
        signature=sig,
        method=request.method,
        params=form_data,
        fallback_uris=fallback_uris,
    )

    if not is_valid:
        logger.warning(
            "Rejected Plivo voice webhook: invalid V3 signature. URL: %s, Signature: %s",
            url,
            sig,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Plivo V3 signature.",
        )

    # 3. Extract core call identifiers
    call_uuid = (
        form_data.get("CallUUID")
        or form_data.get("call_uuid")
        or form_data.get("CallId")
        or str(uuid.uuid4())
    )
    caller_from = form_data.get("From") or form_data.get("from") or ""
    destination_to = form_data.get("To") or form_data.get("to") or ""
    call_status = form_data.get("CallStatus") or form_data.get("call_status") or "ringing"

    if not caller_from or not destination_to:
        logger.error("Missing mandatory Plivo call fields (From, To). Received: %s", form_data)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required Plivo call parameters (From, To).",
        )

    # 4. Resolve business tenant organization
    business = resolve_business_by_phone(db, destination_to)
    if not business:
        logger.warning(
            "Plivo call received for unmapped destination '%s' (CallUUID: %s).",
            destination_to,
            call_uuid,
        )
        unknown_xml = plivo_service.build_unknown_number_xml()
        return Response(content=unknown_xml, media_type="application/xml", status_code=status.HTTP_200_OK)

    # Normalize caller number to E.164 (+91 followed by 10 digits)
    norm_caller_from = normalize_indian_mobile_number(caller_from) or caller_from.strip()

    # 5. Resolve or create customer within the tenant
    customer = resolve_or_create_customer(db, business.id, norm_caller_from)

    # 6. Idempotently log or update Call record
    mapped_status = "in_progress" if call_status in ("ringing", "in-progress", "queued", "initiated") else call_status
    existing_call = db.scalar(
        select(Call).where(or_(Call.id == call_uuid, Call.summary.like(f"%{call_uuid}%")))
    )

    if existing_call:
        existing_call.status = mapped_status
        db.commit()
    else:
        now = datetime.now(timezone.utc)
        call_id = call_uuid if len(call_uuid) <= 36 else str(call_uuid[:36])
        call_record = Call(
            id=call_id,
            business_id=business.id,
            customer_id=customer.id,
            caller_name=customer.name,
            caller_phone=norm_caller_from,
            call_type="incoming",
            status=mapped_status,
            duration_seconds=0,
            summary=f"Incoming voice call via Plivo (CallUUID: {call_uuid})",
            transcript=f"AI: Thank you for calling {business.name}. How can we assist you today?",
            initiated_at=now,
        )
        db.add(call_record)
        db.commit()
        logger.info(
            "Logged incoming Plivo call (ID: %s, CallUUID: %s) for Business '%s' (ID: %s)",
            call_record.id,
            call_uuid,
            business.name,
            business.id,
        )

    # 7. Initialize persistent conversation session
    get_or_create_conversation_session(
        db=db,
        call_sid=call_uuid,
        business_id=business.id,
        caller_phone=norm_caller_from,
    )

    # 8. Construct WebSocket URL with tenant parameters encoded in query string
    ws_host = request.headers.get("host", "localhost:8000")
    if settings.PUBLIC_BASE_URL:
        clean_base = settings.PUBLIC_BASE_URL.replace("http://", "").replace("https://", "").rstrip("/")
        ws_url = f"wss://{clean_base}{settings.API_V1_STR}/plivo/stream"
    else:
        ws_url = f"ws://{ws_host}{settings.API_V1_STR}/plivo/stream"

    ws_url_with_params = (
        f"{ws_url}?business_id={business.id}&call_uuid={call_uuid}"
        f"&caller_phone={norm_caller_from}&to={destination_to}"
    )

    # 9. Return Plivo XML with bidirectional <Stream>
    stream_xml = plivo_service.build_stream_xml(
        stream_url=ws_url_with_params,
        bidirectional=True,
        keep_call_alive=True,
        content_type="audio/x-mulaw;rate=8000",
    )

    logger.info(
        "Returned Plivo bidirectional Stream XML for CallUUID %s -> %s",
        call_uuid,
        ws_url,
    )
    return Response(content=stream_xml, media_type="application/xml", status_code=status.HTTP_200_OK)


@router.websocket("/stream")
async def handle_plivo_voice_stream(
    websocket: WebSocket,
    db: Session = Depends(get_db_session),
):
    """Plivo Bidirectional Real-Time Audio Streaming WebSocket Endpoint.
    
    Protocol:
    - Inbound Events:
      - 'start': Stream connected with session and call identifiers.
      - 'media': Raw audio frame (8000Hz 8-bit mu-law base64).
      - 'stop': Stream ended.
    - Outbound Events:
      - 'playAudio': Stream synthesized audio frame chunks to caller.
      - 'clearAudio': Immediately clear playback buffer on caller barge-in.
    """
    # Read context from URL query string
    query_params = dict(websocket.query_params)
    query_biz_id = query_params.get("business_id")
    query_call_uuid = query_params.get("call_uuid")
    query_caller = query_params.get("caller_phone")
    query_dest = query_params.get("to")

    client_host = getattr(websocket.client, "host", "unknown") if websocket.client else "unknown"
    client_port = getattr(websocket.client, "port", "") if websocket.client else ""

    logger.info(
        "Plivo WebSocket connection initiated from %s:%s (call_uuid=%s, business_id=%s, caller=%s)",
        client_host,
        client_port,
        query_call_uuid,
        query_biz_id,
        query_caller,
    )

    await websocket.accept()
    logger.info("Plivo WebSocket connection accepted for call_uuid=%s", query_call_uuid)

    orchestrator = StreamOrchestrator()
    current_stream_id: str | None = None
    keepalive_task: asyncio.Task | None = None

    async def _run_ws_keepalive() -> None:
        """Send periodic application-level keepalive pings to prevent proxy/carrier timeouts."""
        try:
            interval = getattr(settings, "WS_HEARTBEAT_INTERVAL_SEC", 15.0)
            while True:
                await asyncio.sleep(interval)
                if not current_stream_id:
                    continue
                session = stream_manager.get_session(current_stream_id)
                if not session:
                    break
                try:
                    await websocket.send_text(
                        json.dumps({
                            "event": "ping",
                            "streamId": current_stream_id,
                            "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                        })
                    )
                except Exception as ping_err:
                    logger.debug("Plivo WS keepalive ping error for %s: %s", current_stream_id, ping_err)
                    break
        except asyncio.CancelledError:
            pass

    try:
        keepalive_task = asyncio.create_task(_run_ws_keepalive())

        while True:
            raw_msg = await websocket.receive_text()
            if not raw_msg:
                continue

            try:
                data = json.loads(raw_msg)
            except Exception:
                continue

            event_type = data.get("event")

            if event_type == "start":
                start_data = data.get("start", {})
                current_stream_id = (
                    data.get("streamId")
                    or start_data.get("streamId")
                    or (f"plivo_{query_call_uuid}" if query_call_uuid else f"stream_{uuid.uuid4().hex[:12]}")
                )

                # Merge query string context into start parameters
                merged_custom = {
                    "business_id": query_biz_id,
                    "caller_phone": query_caller,
                    "to": query_dest,
                    "callSid": query_call_uuid or start_data.get("callId"),
                }
                start_data["customParameters"] = merged_custom
                start_data["callSid"] = query_call_uuid or start_data.get("callId") or current_stream_id

                logger.info(
                    "Plivo Audio Stream started: streamId=%s, callUUID=%s",
                    current_stream_id,
                    query_call_uuid,
                )

                await orchestrator.handle_start(
                    stream_sid=current_stream_id,
                    start_payload=start_data,
                    websocket=websocket,
                    db=db,
                    provider="plivo",
                )

            elif event_type == "media":
                stream_id = data.get("streamId") or current_stream_id
                media_data = data.get("media", {})
                if stream_id:
                    await orchestrator.handle_media(
                        stream_sid=stream_id,
                        media_payload=media_data,
                        db=db,
                    )

            elif event_type == "ping":
                stream_id = data.get("streamId") or current_stream_id
                try:
                    await websocket.send_text(
                        json.dumps({
                            "event": "pong",
                            "streamId": stream_id,
                            "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                        })
                    )
                except Exception as e:
                    logger.debug("Failed to send pong to Plivo for stream %s: %s", stream_id, e)

            elif event_type == "pong":
                logger.debug("Received pong from Plivo for stream %s", current_stream_id)

            elif event_type == "playedStream":
                logger.debug("Plivo playedStream event received for stream %s", current_stream_id)

            elif event_type == "clearedAudio":
                logger.debug("Plivo clearedAudio event received for stream %s", current_stream_id)

            elif event_type == "dtmf":
                digits = data.get("dtmf", {}).get("digit") or data.get("digit")
                logger.info("Plivo DTMF received on stream %s: %s", current_stream_id, digits)

            elif event_type == "stop":
                stream_id = data.get("streamId") or current_stream_id
                stop_data = data.get("stop", {})
                if stream_id:
                    await orchestrator.handle_stop(stream_id, stop_data, db)
                break

    except WebSocketDisconnect as ws_disc:
        logger.info(
            "Plivo Telephony WebSocket disconnected normally for call_uuid=%s, stream=%s (code=%s)",
            query_call_uuid,
            current_stream_id,
            getattr(ws_disc, "code", "unknown"),
        )
    except Exception as exc:
        logger.error(
            "Error in Plivo WebSocket streaming loop for call_uuid=%s, stream=%s: %s",
            query_call_uuid,
            current_stream_id,
            exc,
            exc_info=True,
        )
    finally:
        if keepalive_task and not keepalive_task.done():
            keepalive_task.cancel()
        logger.info(
            "Plivo Telephony WebSocket connection cleaned up for call_uuid=%s, stream=%s",
            query_call_uuid,
            current_stream_id,
        )
        if current_stream_id:
            active_sess = stream_manager.get_session(current_stream_id)
            if active_sess:
                active_sess.playback_cancellation_reason = "websocket_closed"
                if active_sess.current_playback_task and not active_sess.current_playback_task.done():
                    active_sess.current_playback_task.cancel()
            await stream_manager.unregister(current_stream_id)


@router.post(
    "/status",
    summary="Plivo Call Status & Hangup Callback Webhook",
    description="Receive post-call metrics (duration, hangup cause) and finalize database call record.",
    response_class=Response,
)
async def handle_plivo_call_status(
    request: Request,
    x_plivo_signature_v3: str | None = Header(default=None, alias="X-Plivo-Signature-V3"),
    x_plivo_signature_v3_nonce: str | None = Header(default=None, alias="X-Plivo-Signature-V3-Nonce"),
    db: Session = Depends(get_db_session),
    plivo_service: PlivoService = Depends(get_plivo_service),
) -> Response:
    """Handle Plivo call hangup / status callback."""
    form_data: dict[str, Any] = {}
    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        try:
            body = await request.json()
            if isinstance(body, dict):
                form_data = body
        except Exception:
            pass
    if not form_data:
        try:
            form = await request.form()
            form_data = dict(form)
        except Exception:
            pass

    # Validate signature
    sig = (
        x_plivo_signature_v3
        or request.headers.get("x-plivo-signature-v3")
        or request.headers.get("x-plivo-signature-ma-v3")
        or request.headers.get("x-plivo-signature")
    )
    nonce = (
        x_plivo_signature_v3_nonce
        or request.headers.get("x-plivo-signature-v3-nonce")
        or request.headers.get("x-plivo-signature-v2-nonce")
    )

    url = str(request.url)
    fallback_uris: list[str] = []

    fwd_proto = request.headers.get("x-forwarded-proto") or request.url.scheme or "https"
    fwd_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if fwd_host:
        fwd_url = f"{fwd_proto}://{fwd_host}{request.url.path}"
        if request.url.query:
            fwd_url = f"{fwd_url}?{request.url.query}"
        fallback_uris.append(fwd_url)

    if settings.PUBLIC_BASE_URL:
        clean_base = settings.PUBLIC_BASE_URL.rstrip("/")
        pub_url = f"{clean_base}{request.url.path}"
        if request.url.query:
            pub_url = f"{pub_url}?{request.url.query}"
        fallback_uris.append(pub_url)

    plivo_service.validate_v3_signature(
        uri=url,
        nonce=nonce,
        signature=sig,
        method=request.method,
        params=form_data,
        fallback_uris=fallback_uris,
    )

    call_uuid = form_data.get("CallUUID") or form_data.get("call_uuid") or ""
    duration = int(form_data.get("Duration") or form_data.get("BillDuration") or 0)
    raw_status = (form_data.get("CallStatus") or form_data.get("Status") or "completed").lower()
    rec_url = form_data.get("RecordUrl") or form_data.get("RecordingUrl")

    status_map = {
        "completed": "completed",
        "busy": "busy",
        "no-answer": "missed",
        "timeout": "missed",
        "canceled": "missed",
        "failed": "failed",
    }
    final_status = status_map.get(raw_status, "completed")

    call_record = db.scalar(
        select(Call).where(or_(Call.id == call_uuid, Call.summary.like(f"%{call_uuid}%")))
    )
    if call_record:
        call_record.status = final_status
        call_record.duration_seconds = max(call_record.duration_seconds, duration)
        call_record.ended_at = datetime.now(timezone.utc)
        if rec_url:
            call_record.recording_url = str(rec_url)
        db.commit()
        logger.info(
            "Finalized Plivo call %s: status=%s, duration=%ds",
            call_uuid,
            final_status,
            duration,
        )

    # Mark conversation session completed
    conv_session = db.get(ConversationSession, call_uuid)
    if conv_session:
        conv_session.is_completed = True
        db.commit()

    return Response(content="<Response/>", media_type="application/xml", status_code=status.HTTP_200_OK)


@router.get(
    "/status",
    summary="Plivo Telephony Status Probe",
    description="Check connectivity and configuration status with Plivo Voice API.",
)
def get_plivo_telephony_status(
    plivo_service: PlivoService = Depends(get_plivo_service),
) -> dict[str, Any]:
    """Return health and credential status of Plivo Programmable Voice."""
    return plivo_service.check_connection()
