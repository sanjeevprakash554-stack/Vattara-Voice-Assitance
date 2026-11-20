"""Pydantic schemas for Telephony Integration settings and masked credentials."""

from pydantic import BaseModel, ConfigDict, Field


class IntegrationSettingsResponse(BaseModel):
    business_id: str
    primary_provider: str = "plivo"
    plivo_configured: bool = False
    plivo_phone_number: str | None = None
    plivo_auth_id_masked: str | None = None
    is_plivo_verified: bool = False
    inbound_webhook_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UpdateIntegrationRequest(BaseModel):
    primary_provider: str | None = Field(default="plivo", description="Exclusive telephony provider: plivo")
    plivo_auth_id: str | None = None
    plivo_auth_token: str | None = None
    plivo_phone_number: str | None = None


class TestConnectionRequest(BaseModel):
    provider: str = Field(default="plivo", description="Telephony provider to test: plivo")


class TestConnectionResponse(BaseModel):
    provider: str
    is_connected: bool
    status: str = "connected"
    message: str
    latency_ms: int = 0
