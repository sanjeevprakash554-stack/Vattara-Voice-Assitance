"""Telephony provider factory for instantiating Plivo, Twilio, or Tata Smartflo adapters."""

from app.core.config import settings
from app.services.telephony.base import BaseTelephonyProvider
from app.services.telephony.plivo_adapter import PlivoAdapter
from app.services.telephony.smartflo_adapter import SmartfloAdapter
from app.services.telephony.twilio_adapter import TwilioAdapter


def get_telephony_provider(provider_name: str | None = None) -> BaseTelephonyProvider:
    """Instantiate telephony provider adapter based on configuration or explicit name."""
    selected = (provider_name or "plivo").lower().strip()

    if selected == "plivo":
        return PlivoAdapter()
    if selected == "smartflo":
        return SmartfloAdapter()
    if selected == "twilio":
        return TwilioAdapter()

    raise ValueError(f"Unsupported telephony provider: '{provider_name}'. Supported: 'plivo', 'twilio', 'smartflo'")
