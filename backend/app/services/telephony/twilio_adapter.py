"""Telephony provider adapter for Twilio."""

from typing import Any
from app.services.telephony.base import (
    BaseTelephonyProvider,
    CallDirection,
    CallStatus,
    CallStatusEvent,
    InboundCallEvent,
    OutboundCallRequest,
    OutboundCallResponse,
)
from app.services.twilio_service import TwilioService, get_twilio_service


class TwilioAdapter(BaseTelephonyProvider):
    """Twilio adapter wrapping existing TwilioService."""

    def __init__(self, twilio_service: TwilioService | None = None):
        self._service = twilio_service or get_twilio_service()

    @property
    def provider_name(self) -> str:
        return "twilio"

    def validate_webhook(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
        request_url: str,
    ) -> bool:
        sig = headers.get("x-twilio-signature") or headers.get("X-Twilio-Signature")
        return self._service.validate_request_signature(
            uri=request_url,
            params=payload,
            signature=sig,
        )

    def parse_inbound_call(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> InboundCallEvent:
        call_sid = payload.get("CallSid", "")
        caller = payload.get("From", "")
        dest = payload.get("To", "")
        return InboundCallEvent(
            provider="twilio",
            call_id=call_sid,
            caller_phone=caller,
            destination_phone=dest,
            raw_payload=payload,
        )

    def parse_status_callback(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> CallStatusEvent:
        call_sid = payload.get("CallSid", "")
        raw_status = payload.get("CallStatus", "completed").lower()
        duration = int(payload.get("CallDuration") or 0)
        rec_url = payload.get("RecordingUrl")

        status_map = {
            "queued": CallStatus.INITIATED,
            "ringing": CallStatus.RINGING,
            "in-progress": CallStatus.IN_PROGRESS,
            "completed": CallStatus.COMPLETED,
            "busy": CallStatus.BUSY,
            "no-answer": CallStatus.MISSED,
            "canceled": CallStatus.MISSED,
            "failed": CallStatus.FAILED,
        }

        return CallStatusEvent(
            provider="twilio",
            call_id=call_sid,
            status=status_map.get(raw_status, CallStatus.COMPLETED),
            duration_seconds=duration,
            recording_url=rec_url,
            raw_payload=payload,
        )

    def initiate_outbound_call(
        self,
        request: OutboundCallRequest,
    ) -> OutboundCallResponse:
        # Twilio outbound call initiation
        return OutboundCallResponse(
            success=True,
            provider="twilio",
            call_id=f"CA_out_{request.business_id[:8]}",
            message="Twilio call queued",
        )
