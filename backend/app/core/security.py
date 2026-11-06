"""Security, password hashing (Argon2), and JWT authentication utilities.

Provides cryptographic verification, token generation, decoding, and password strength checks.
"""

from datetime import datetime, timedelta, timezone
import re
from typing import Any
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
import bcrypt
from fastapi import HTTPException, status
import jwt
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Argon2 PasswordHasher instance
_argon2_hasher = PasswordHasher()


def validate_password_strength(password: str) -> tuple[bool, str]:
    """Validate that password satisfies enterprise security policy.

    Rules:
        - Minimum 8 characters
        - At least 1 uppercase letter
        - At least 1 lowercase letter
        - At least 1 numeric digit
        - At least 1 special character

    Returns:
        tuple[bool, str]: (is_valid, failure_reason)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>\-_+=\[\]]", password):
        return False, "Password must contain at least one special character."
    return True, ""


def get_password_hash(password: str) -> str:
    """Generate a secure cryptographic Argon2id hash for user passwords."""
    return _argon2_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify that a plain-text password matches a hashed password.

    Supports Argon2id hashes, with fallback to bcrypt for backwards compatibility.
    """
    if hashed_password.startswith("$argon2"):
        try:
            return _argon2_hasher.verify(hashed_password, plain_password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False
    elif hashed_password.startswith(("$2b$", "$2a$")):
        try:
            return bcrypt.checkpw(
                plain_password.encode("utf-8"),
                hashed_password.encode("utf-8"),
            )
        except Exception:
            return False
    return False


def create_access_token(
    subject: str | Any,
    business_id: int | None = None,
    role: str | None = None,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Generate a signed JWT access token for authentication.

    Args:
        subject: Subject identifier (typically user ID).
        business_id: Organization/Tenant ID the user belongs to (None for Super Admin).
        role: User role (SUPER_ADMIN, BUSINESS_ADMIN, STAFF).
        expires_delta: Optional custom duration before token expiration.
        extra_claims: Additional metadata claims.

    Returns:
        str: Encoded and signed JWT token.
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    claims: dict[str, Any] = {
        "sub": str(subject),
        "business_id": business_id,
        "role": str(role) if role else None,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_claims:
        claims.update(extra_claims)

    return jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token.

    Args:
        token: Bearer JWT string.

    Returns:
        dict[str, Any]: Token payload claims.

    Raises:
        HTTPException: 401 if expired or invalid.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Expired JWT token encountered")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (jwt.InvalidTokenError, Exception) as exc:
        logger.warning("Invalid JWT token encountered: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
