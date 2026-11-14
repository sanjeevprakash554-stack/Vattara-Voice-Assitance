"""Telephony webhook security, timing-safe authentication, and sensitive-data masking."""

import hmac
import re


def mask_phone(phone: str | None) -> str:
    """Mask telephone number in logs for privacy compliance (e.g., +9198****3210)."""
    if not phone:
        return "N/A"
    s = phone.strip()
    if len(s) <= 5:
        return "****"
    prefix = s[:5] if s.startswith("+") else s[:4]
    suffix = s[-4:]
    return f"{prefix}****{suffix}"


def mask_secret(secret: str | None) -> str:
    """Mask API key or secret token for safe logging."""
    if not secret:
        return "None"
    s = secret.strip()
    if len(s) <= 8:
        return "********"
    return f"{s[:4]}...{s[-4:]}"


def verify_webhook_token(provided_token: str | None, expected_token: str | None) -> bool:
    """Perform constant-time comparison on incoming webhook secret tokens."""
    if not provided_token or not expected_token:
        return False
    return hmac.compare_digest(provided_token.strip(), expected_token.strip())
