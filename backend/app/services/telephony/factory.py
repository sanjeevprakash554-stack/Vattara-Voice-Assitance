"""Telephony provider factory for instantiating Plivo adapter."""

from app.core.config import settings
from app.services.telephony.base import BaseTelephonyProvider
from app.services.telephony.plivo_adapter import PlivoAdapter


def get_telephony_provider(provider_name: str | None = None) -> BaseTelephonyProvider:
    """Instantiate telephony provider adapter based on configuration or explicit name."""
    selected = (provider_name or "plivo").lower().strip()

    if selected == "plivo":
        return PlivoAdapter()

    raise ValueError(f"Unsupported telephony provider: '{provider_name}'. Supported: 'plivo'")
