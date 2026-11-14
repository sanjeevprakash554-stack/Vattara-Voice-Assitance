"""Pydantic schemas for Telephony Integration settings and masked credentials."""

from pydantic import BaseModel, ConfigDict, Field


class IntegrationSettingsResponse(BaseModel):
    business_id: str
    primary_provider: str  # twilio, plivo, smartflo, exotel
    plivo_configured: bool = False
    plivo_phone_number: str | None = None
    plivo_auth_id_masked: str | None = None
    is_plivo_verified: bool = False
    twilio_configured: bool
    twilio_phone_number: str | None = None
    twilio_account_sid_masked: str | None = None
    is_twilio_verified: bool = False
    smartflo_configured: bool
    smartflo_caller_id: str | None = None
    smartflo_api_key_masked: str | None = None
    is_smartflo_verified: bool = False
    exotel_configured: bool
    exotel_caller_id: str | None = None
    is_exotel_verified: bool = False
    inbound_webhook_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UpdateIntegrationRequest(BaseModel):
    primary_provider: str | None = Field(default=None, description="twilio, plivo, smartflo, or exotel")
    plivo_auth_id: str | None = None
    plivo_auth_token: str | None = None
    plivo_phone_number: str | None = None
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_phone_number: str | None = None
    smartflo_caller_id: str | None = None
    smartflo_api_key: str | None = None
    exotel_caller_id: str | None = None
    exotel_sid: str | None = None
    exotel_api_key: str | None = None


class TestConnectionRequest(BaseModel):
    provider: str = Field(..., description="twilio, plivo, or smartflo")


class TestConnectionResponse(BaseModel):
    provider: str
    is_connected: bool
    status: str = "connected"
    message: str
    latency_ms: int = 150
