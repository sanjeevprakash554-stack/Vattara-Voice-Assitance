"""Security architecture and authentication utilities.

This module provides the architectural foundation for:
- JWT (JSON Web Token) creation and decoding.
- Password hashing and verification.
- Role-Based Access Control (RBAC) and multi-tenant authorization.

Full authentication handlers will be connected in subsequent phases.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def create_access_token(
    subject: str | Any,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Generate a JWT access token for authentication.

    Args:
        subject: The subject of the token (typically user ID or business UUID).
        expires_delta: Optional custom duration before expiration.
        extra_claims: Additional claims (e.g., tenant_id, role, permissions).

    Returns:
        Encoded JWT token string (placeholder interface until auth phase).
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    claims: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_claims:
        claims.update(extra_claims)

    logger.debug("Token claims prepared for subject %s (auth module pending)", subject)
    # Placeholder token string; cryptographic signing will be active in the auth phase
    return f"mock_jwt_token_for_{subject}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify that a plain-text password matches a hashed password."""
    # Placeholder: Will use passlib/bcrypt or argon2 in auth implementation
    return plain_password == hashed_password


def get_password_hash(password: str) -> str:
    """Generate a secure cryptographic hash for user passwords."""
    # Placeholder: Will use bcrypt/argon2 hashing in auth implementation
    return f"hashed_{password}"
