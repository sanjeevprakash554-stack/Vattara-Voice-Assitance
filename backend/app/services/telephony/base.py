"""Provider-independent abstractions for cloud telephony providers (Twilio, Tata Smartflo, etc.)."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class CallDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallStatus(str, Enum):
    INITIATED = "initiated"
    RINGING = "ringing"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    MISSED = "missed"
    FAILED = "failed"
    BUSY = "busy"


class InboundCallEvent(BaseModel):
    """Normalized inbound call initiation event across telephony providers."""

    provider: str  # "twilio", "smartflo", etc.
    call_id: str
    caller_phone: str
    destination_phone: str
    business_id: str | None = None
    customer_name: str | None = None
    custom_identifier: dict[str, Any] = Field(default_factory=dict)
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class CallStatusEvent(BaseModel):
    """Normalized call lifecycle status event (answered, completed, hangup, missed)."""

    provider: str
    call_id: str
    status: CallStatus
    duration_seconds: int = 0
    recording_url: str | None = None
    hangup_cause_code: int | None = None
    hangup_cause_description: str | None = None
    custom_identifier: dict[str, Any] = Field(default_factory=dict)
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class OutboundCallRequest(BaseModel):
    """Normalized outbound call trigger request."""

    destination_phone: str
    caller_id: str
    business_id: str
    agent_phone: str | None = None
    timeout_seconds: int = 300
    custom_identifier: dict[str, Any] = Field(default_factory=dict)


class OutboundCallResponse(BaseModel):
    """Normalized response for an outbound call initiation request."""

    success: bool
    provider: str
    call_id: str | None = None
    reference_id: str | None = None
    message: str = "Call initiated"
    raw_response: dict[str, Any] = Field(default_factory=dict)


class BaseTelephonyProvider(ABC):
    """Abstract interface defining required telephony capabilities."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the telephony provider (e.g., 'twilio', 'smartflo')."""
        pass

    @abstractmethod
    def validate_webhook(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
        request_url: str,
    ) -> bool:
        """Verify the authenticity of an incoming webhook from the provider."""
        pass

    @abstractmethod
    def parse_inbound_call(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> InboundCallEvent:
        """Normalize an incoming call event into an InboundCallEvent."""
        pass

    @abstractmethod
    def parse_status_callback(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> CallStatusEvent:
        """Normalize a status callback into a CallStatusEvent."""
        pass

    @abstractmethod
    def initiate_outbound_call(
        self,
        request: OutboundCallRequest,
    ) -> OutboundCallResponse:
        """Trigger an outbound call through the provider's API."""
        pass
