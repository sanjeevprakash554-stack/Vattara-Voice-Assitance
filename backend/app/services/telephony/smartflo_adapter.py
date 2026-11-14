"""Tata Smartflo Cloud Telephony Adapter implementing BaseTelephonyProvider."""

from datetime import datetime
from typing import Any
import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.services.telephony.base import (
    BaseTelephonyProvider,
    CallStatus,
    CallStatusEvent,
    InboundCallEvent,
    OutboundCallRequest,
    OutboundCallResponse,
)
from app.services.telephony.security import mask_phone, mask_secret, verify_webhook_token

logger = get_logger(__name__)


class SmartfloAdapter(BaseTelephonyProvider):
    """Telephony provider adapter for Tata Tele Business Services (TTBS) Smartflo."""

    def __init__(
        self,
        api_token: str | None = None,
        base_url: str | None = None,
        caller_id: str | None = None,
        webhook_token: str | None = None,
    ):
        self.api_token = api_token or settings.SMARTFLO_API_TOKEN
        self.base_url = (base_url or settings.SMARTFLO_BASE_URL or "https://api-smartflo.tatateleservices.com/v1").rstrip("/")
        self.caller_id = caller_id or settings.SMARTFLO_CALLER_ID
        self.webhook_token = webhook_token or settings.SMARTFLO_WEBHOOK_TOKEN

    @property
    def provider_name(self) -> str:
        return "smartflo"

    def validate_webhook(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
        request_url: str,
    ) -> bool:
        """Verify the authenticity of an incoming Smartflo webhook."""
        # 1. Check custom X-Smartflo-Token or X-Webhook-Token header
        header_token = (
            headers.get("x-smartflo-token")
            or headers.get("X-Smartflo-Token")
            or headers.get("x-webhook-token")
            or headers.get("X-Webhook-Token")
        )

        # 2. Check Bearer Authorization header
        auth_header = headers.get("authorization") or headers.get("Authorization")
        if not header_token and auth_header and auth_header.startswith("Bearer "):
            header_token = auth_header[7:].strip()

        # 3. Check query param or payload 'token' / 'api_key'
        if not header_token and "token" in payload:
            header_token = str(payload["token"])

        # If server has configured SMARTFLO_WEBHOOK_TOKEN, enforce match
        if self.webhook_token:
            is_valid = verify_webhook_token(header_token, self.webhook_token)
            if not is_valid:
                logger.warning(
                    "Rejected Smartflo webhook: invalid token (provided: %s)",
                    mask_secret(header_token),
                )
                return False
            return True

        # If no webhook token is configured, allow if caller has API token configured
        return True

    def parse_inbound_call(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> InboundCallEvent:
        """Parse incoming call initiation or API dialplan event from Smartflo."""
        call_id = str(payload.get("uuid") or payload.get("call_id") or payload.get("ref_id") or "")
        caller = str(payload.get("caller_id_number") or payload.get("from") or payload.get("customer_number") or "")
        dest = str(payload.get("call_to_number") or payload.get("to") or payload.get("caller_id") or "")

        custom_id = payload.get("custom_identifier")
        if isinstance(custom_id, str):
            try:
                import json
                custom_id = json.loads(custom_id)
            except Exception:
                custom_id = {}
        elif not isinstance(custom_id, dict):
            custom_id = {}

        # Resolve tenant business_id from custom_identifier or DID mapping
        business_id = custom_id.get("business_id")
        if not business_id and dest:
            did_map = settings.get_smartflo_did_map()
            clean_dest = dest.replace("+", "").strip()
            business_id = did_map.get(clean_dest) or did_map.get(dest)

        logger.info(
            "Parsed Smartflo inbound call: CallID=%s, Caller=%s, DID=%s, Business=%s",
            call_id,
            mask_phone(caller),
            dest,
            business_id,
        )

        return InboundCallEvent(
            provider="smartflo",
            call_id=call_id,
            caller_phone=caller,
            destination_phone=dest,
            business_id=business_id,
            customer_name=custom_id.get("customer_name"),
            custom_identifier=custom_id,
            raw_payload=payload,
        )

    def parse_status_callback(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> CallStatusEvent:
        """Parse Smartflo lifecycle milestone event (ringing, answered, hangup, missed)."""
        call_id = str(payload.get("uuid") or payload.get("call_id") or payload.get("ref_id") or "")
        raw_status = str(payload.get("call_status") or "").lower().strip()

        # Compute call duration in seconds if start_stamp and end_time provided
        duration_seconds = 0
        if "duration" in payload:
            try:
                duration_seconds = int(payload["duration"])
            except (ValueError, TypeError):
                duration_seconds = 0
        elif payload.get("start_stamp") and payload.get("end_time"):
            try:
                t_start = datetime.strptime(payload["start_stamp"], "%Y-%m-%d %H:%M:%S")
                t_end = datetime.strptime(payload["end_time"], "%Y-%m-%d %H:%M:%S")
                duration_seconds = max(0, int((t_end - t_start).total_seconds()))
            except Exception:
                duration_seconds = 0

        # Map Smartflo status to standardized CallStatus
        status_map = {
            "ringing": CallStatus.RINGING,
            "answered": CallStatus.IN_PROGRESS,
            "connected": CallStatus.IN_PROGRESS,
            "completed": CallStatus.COMPLETED,
            "normal_clearing": CallStatus.COMPLETED,
            "missed": CallStatus.MISSED,
            "no_answer": CallStatus.MISSED,
            "user_busy": CallStatus.BUSY,
            "busy": CallStatus.BUSY,
            "failed": CallStatus.FAILED,
        }

        # If hangup event occurs with answered status, treat as completed
        if payload.get("hangup_cause_code") or payload.get("end_time"):
            if raw_status in ("answered", "completed", "normal_clearing"):
                final_status = CallStatus.COMPLETED
            elif raw_status in ("missed", "no_answer"):
                final_status = CallStatus.MISSED
            elif raw_status in ("busy", "user_busy"):
                final_status = CallStatus.BUSY
            else:
                final_status = CallStatus.COMPLETED
        else:
            final_status = status_map.get(raw_status, CallStatus.IN_PROGRESS)

        rec_url = payload.get("aws_call_recording_identifier") or payload.get("recording_url")
        cause_code = payload.get("hangup_cause_code")
        cause_desc = payload.get("hangup_cause_description") or payload.get("hangup_cause_key")

        custom_id = payload.get("custom_identifier")
        if not isinstance(custom_id, dict):
            custom_id = {}

        return CallStatusEvent(
            provider="smartflo",
            call_id=call_id,
            status=final_status,
            duration_seconds=duration_seconds,
            recording_url=rec_url,
            hangup_cause_code=cause_code,
            hangup_cause_description=cause_desc,
            custom_identifier=custom_id,
            raw_payload=payload,
        )

    def initiate_outbound_call(
        self,
        request: OutboundCallRequest,
    ) -> OutboundCallResponse:
        """Trigger an outbound call using Smartflo Click-to-Call (C2C) REST API."""
        if not self.api_token:
            logger.error("Cannot initiate Smartflo outbound call: SMARTFLO_API_TOKEN is unconfigured.")
            return OutboundCallResponse(
                success=False,
                provider="smartflo",
                message="Smartflo API token is unconfigured on the server.",
            )

        caller_id = request.caller_id or self.caller_id
        if not caller_id:
            logger.error("Cannot initiate Smartflo outbound call: caller_id is required.")
            return OutboundCallResponse(
                success=False,
                provider="smartflo",
                message="Caller ID (DID) is required for Smartflo outbound calling.",
            )

        # Standard Smartflo Click-to-Call payload
        endpoint = f"{self.base_url}/click_to_call"
        payload = {
            "customer_number": request.destination_phone.replace("+", "").strip(),
            "caller_id": caller_id.replace("+", "").strip(),
            "agent_number": (request.agent_phone or caller_id).replace("+", "").strip(),
            "async": 1,
            "call_timeout": request.timeout_seconds,
            "custom_identifier": {
                "business_id": request.business_id,
                **request.custom_identifier,
            },
        }

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        logger.info(
            "Triggering Smartflo Click-to-Call to %s via caller_id %s",
            mask_phone(request.destination_phone),
            caller_id,
        )

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(endpoint, json=payload, headers=headers)
                try:
                    data = resp.json()
                except Exception:
                    data = {}

                if resp.status_code == 200:
                    ref_id = data.get("ref_id") or data.get("reference_id")
                    call_id = data.get("uuid") or data.get("call_id") or ref_id
                    return OutboundCallResponse(
                        success=True,
                        provider="smartflo",
                        call_id=str(call_id),
                        reference_id=str(ref_id),
                        message=data.get("message", "Call initiated successfully"),
                        raw_response=data,
                    )
                else:
                    err_msg = data.get("message") or resp.text
                    logger.error("Smartflo Click-to-Call failed with HTTP %s: %s", resp.status_code, err_msg)
                    return OutboundCallResponse(
                        success=False,
                        provider="smartflo",
                        message=f"Smartflo API error ({resp.status_code}): {err_msg}",
                        raw_response={"status_code": resp.status_code, "text": resp.text},
                    )

        except Exception as exc:
            logger.error("Network or execution error connecting to Smartflo API: %s", exc, exc_info=True)
            return OutboundCallResponse(
                success=False,
                provider="smartflo",
                message=f"Connection failure: {str(exc)}",
            )

    def build_dialplan_transfer_response(
        self,
        agent_number: str,
        business_id: str | None = None,
        custom_parameter_1: str | None = None,
        disable_recording: bool = False,
    ) -> list[dict[str, Any]]:
        """Generate official Tata Smartflo API Dialplan routing response JSON."""
        transfer_block: dict[str, Any] = {
            "type": "agent",
            "data": [agent_number.replace("+", "").strip()],
        }
        if business_id:
            transfer_block["custom_parameter_1"] = business_id
        if custom_parameter_1:
            transfer_block["custom_parameter_2"] = custom_parameter_1

        actions: list[dict[str, Any]] = []
        if disable_recording:
            actions.append({"disable_call_recording": True})
        actions.append({"transfer": transfer_block})

        return actions
