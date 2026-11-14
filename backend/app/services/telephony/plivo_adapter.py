"""Telephony provider adapter for Plivo Programmable Voice."""

from typing import Any
from app.services.plivo_service import PlivoService, get_plivo_service
from app.services.telephony.base import (
    BaseTelephonyProvider,
    CallDirection,
    CallStatus,
    CallStatusEvent,
    InboundCallEvent,
    OutboundCallRequest,
    OutboundCallResponse,
)


class PlivoAdapter(BaseTelephonyProvider):
    """Plivo Programmable Voice adapter wrapping PlivoService."""

    def __init__(self, plivo_service: PlivoService | None = None):
        self._service = plivo_service or get_plivo_service()

    @property
    def provider_name(self) -> str:
        return "plivo"

    def validate_webhook(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
        request_url: str,
    ) -> bool:
        """Validate Plivo V3 signature from request headers."""
        sig = headers.get("x-plivo-signature-v3") or headers.get("X-Plivo-Signature-V3")
        nonce = headers.get("x-plivo-signature-v3-nonce") or headers.get("X-Plivo-Signature-V3-Nonce")
        method = headers.get("method", "POST")
        return self._service.validate_v3_signature(
            uri=request_url,
            nonce=nonce,
            signature=sig,
            method=method,
            params=payload,
        )

    def parse_inbound_call(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> InboundCallEvent:
        """Normalize Plivo incoming call event parameters."""
        call_uuid = (
            payload.get("CallUUID")
            or payload.get("call_uuid")
            or payload.get("CallId")
            or ""
        )
        caller = payload.get("From") or payload.get("from") or ""
        dest = payload.get("To") or payload.get("to") or ""

        return InboundCallEvent(
            provider="plivo",
            call_id=call_uuid,
            caller_phone=caller,
            destination_phone=dest,
            raw_payload=payload,
        )

    def parse_status_callback(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> CallStatusEvent:
        """Normalize Plivo call status callback into a CallStatusEvent."""
        call_uuid = (
            payload.get("CallUUID")
            or payload.get("call_uuid")
            or payload.get("CallId")
            or ""
        )
        raw_status = (
            payload.get("CallStatus")
            or payload.get("call_status")
            or payload.get("Status")
            or "completed"
        ).lower()

        duration = int(
            payload.get("Duration")
            or payload.get("duration")
            or payload.get("BillDuration")
            or 0
        )
        rec_url = payload.get("RecordUrl") or payload.get("RecordingUrl")
        hangup_cause = payload.get("HangupCause") or payload.get("hangup_cause")

        status_map = {
            "queued": CallStatus.INITIATED,
            "initiated": CallStatus.INITIATED,
            "ringing": CallStatus.RINGING,
            "in-progress": CallStatus.IN_PROGRESS,
            "completed": CallStatus.COMPLETED,
            "busy": CallStatus.BUSY,
            "no-answer": CallStatus.MISSED,
            "timeout": CallStatus.MISSED,
            "canceled": CallStatus.MISSED,
            "failed": CallStatus.FAILED,
        }

        return CallStatusEvent(
            provider="plivo",
            call_id=call_uuid,
            status=status_map.get(raw_status, CallStatus.COMPLETED),
            duration_seconds=duration,
            recording_url=rec_url,
            hangup_cause_description=str(hangup_cause) if hangup_cause else None,
            raw_payload=payload,
        )

    def initiate_outbound_call(
        self,
        request: OutboundCallRequest,
    ) -> OutboundCallResponse:
        """Initiate outbound call through Plivo Voice API."""
        try:
            res = self._service.initiate_outbound_call(
                from_number=request.caller_id,
                to_number=request.destination_phone,
                answer_url=request.custom_identifier.get("answer_url", ""),
            )
            return OutboundCallResponse(
                success=True,
                provider="plivo",
                call_id=res.get("request_uuid") or res.get("call_uuid"),
                message="Plivo call queued successfully",
                raw_response=res,
            )
        except Exception as exc:
            return OutboundCallResponse(
                success=False,
                provider="plivo",
                message=f"Failed to initiate Plivo call: {str(exc)}",
            )
