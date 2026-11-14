"""Real-Time Voice Streaming WebSocket and TwiML endpoints.

Endpoints:
- WEBSOCKET /api/v1/voice/stream: Real-time bidirectional Twilio Media Stream WebSocket.
- POST      /api/v1/voice/stream-twiml: Inbound webhook generating <Connect><Stream> TwiML.
- GET       /api/v1/voice/stream-health: Real-time stream telemetry and provider status.
"""

import json
from typing import Any
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.api.routes.voice import resolve_business_by_phone
from app.core.config import settings
from app.core.logging import get_logger
from app.database.connection import get_db
from app.models.business import Business
from app.services.streaming.session_manager import stream_manager
from app.services.streaming.stream_orchestrator import StreamOrchestrator
from app.services.twilio_service import TwilioService, get_twilio_service

logger = get_logger(__name__)
router = APIRouter()


@router.websocket("/stream")
async def handle_voice_media_stream(
    websocket: WebSocket,
    db: Session = Depends(get_db_session),
):
    """Twilio Media Streams bi-directional real-time audio WebSocket endpoint.
    
    Protocol:
    - Receive: 'connected', 'start', 'media', 'mark', 'stop'
    - Send:    'media' (audio frames), 'mark' (tracking), 'clear' (barge-in interrupt)
    """
    await websocket.accept()
    orchestrator = StreamOrchestrator()
    current_stream_sid: str | None = None

    try:
        while True:
            raw_msg = await websocket.receive_text()
            if not raw_msg:
                continue

            try:
                data = json.loads(raw_msg)
            except Exception:
                continue

            event_type = data.get("event")

            if event_type == "connected":
                logger.info("Twilio Media Stream protocol connected: %s", data.get("protocol"))

            elif event_type == "start":
                start_data = data.get("start", {})
                current_stream_sid = data.get("streamSid") or start_data.get("streamSid")
                if current_stream_sid:
                    await orchestrator.handle_start(
                        stream_sid=current_stream_sid,
                        start_payload=start_data,
                        websocket=websocket,
                        db=db,
                    )

            elif event_type == "media":
                stream_sid = data.get("streamSid") or current_stream_sid
                media_data = data.get("media", {})
                if stream_sid:
                    await orchestrator.handle_media(
                        stream_sid=stream_sid,
                        media_payload=media_data,
                        db=db,
                    )

            elif event_type == "mark":
                stream_sid = data.get("streamSid") or current_stream_sid
                mark_data = data.get("mark", {})
                if stream_sid:
                    orchestrator.handle_mark(stream_sid, mark_data)

            elif event_type == "stop":
                stream_sid = data.get("streamSid") or current_stream_sid
                stop_data = data.get("stop", {})
                if stream_sid:
                    await orchestrator.handle_stop(stream_sid, stop_data, db)
                break

    except WebSocketDisconnect:
        logger.info("Telephony WebSocket disconnected for stream %s", current_stream_sid)
    except Exception as exc:
        logger.error("Error in telephony WebSocket loop for stream %s: %s", current_stream_sid, exc, exc_info=True)
    finally:
        if current_stream_sid:
            await stream_manager.unregister(current_stream_sid)


@router.post(
    "/stream-twiml",
    summary="Generate Twilio Real-Time Media Stream TwiML",
    description="Inbound webhook returning <Connect><Stream url='wss://...'> for real-time AI voice streaming.",
    response_class=Response,
    responses={
        200: {"content": {"application/xml": {}}},
    },
)
async def generate_media_stream_twiml(
    request: Request,
    db: Session = Depends(get_db_session),
    twilio_service: TwilioService = Depends(get_twilio_service),
) -> Response:
    """Generate TwiML connecting caller to the real-time WebSocket Media Stream."""
    form_data = dict(await request.form())
    destination_to = form_data.get("To", "")
    caller_from = form_data.get("From", "")
    call_sid = form_data.get("CallSid", "")

    # Resolve business tenant
    business = resolve_business_by_phone(db, destination_to) if destination_to else None
    if not business:
        business = db.scalar(select(Business).where(Business.is_active.is_(True)).limit(1))

    biz_id = business.id if business else "default"

    # Construct public WebSocket URL
    ws_host = request.headers.get("host", "localhost:8000")
    if settings.PUBLIC_BASE_URL:
        clean_base = settings.PUBLIC_BASE_URL.replace("http://", "").replace("https://", "").rstrip("/")
        ws_url = f"wss://{clean_base}{settings.API_V1_STR}/voice/stream"
    else:
        ws_url = f"ws://{ws_host}{settings.API_V1_STR}/voice/stream"

    custom_params = {
        "business_id": biz_id,
        "caller_phone": caller_from,
        "to": destination_to,
        "call_sid": call_sid,
    }

    twiml_xml = twilio_service.build_media_stream_twiml(
        stream_url=ws_url,
        custom_parameters=custom_params,
    )

    logger.info(
        "Generated Media Stream TwiML for call %s (Business: %s) -> %s",
        call_sid,
        biz_id,
        ws_url,
    )

    return Response(content=twiml_xml, media_type="application/xml", status_code=status.HTTP_200_OK)


@router.get(
    "/stream-health",
    summary="Real-Time Audio Streaming Engine Telemetry",
    description="Status report on active WebSocket voice streams, STT, and TTS engines.",
)
def get_stream_engine_health() -> dict[str, Any]:
    """Return health status of the real-time voice streaming subsystem."""
    return {
        "streaming_engine": "operational",
        "protocol": "twilio_media_streams_websocket_v1",
        "audio_format": "audio/x-mulaw (8000 Hz, 8-bit mono)",
        "active_streams": len(stream_manager._connections),
        "stt_provider": settings.STT_PROVIDER,
        "tts_provider": settings.TTS_PROVIDER,
        "barge_in_enabled": settings.ENABLE_BARGE_IN,
        "vad_energy_threshold": settings.VAD_ENERGY_THRESHOLD,
        "silence_timeout_ms": settings.VAD_SILENCE_TIMEOUT_MS,
    }
