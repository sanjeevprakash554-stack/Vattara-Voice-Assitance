"""Common API dependencies for dependency injection in endpoints."""

import hmac
from collections.abc import Generator
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import decode_access_token
from app.database.connection import get_db
from app.models.business import Business
from app.models.user import User

logger = get_logger(__name__)
security = HTTPBearer(auto_error=False)


def get_db_session() -> Generator[Session, None, None]:
    """Yield database session for API routes."""
    yield from get_db()


def resolve_business_by_api_key(api_key: str, db: Session) -> Business | None:
    """Resolve active business tenant from an authenticated API key or return None."""
    if not api_key:
        return None

    clean_key = api_key.strip()

    # 1. Check multi-tenant business key map from settings (key:business_id) using constant-time comparison
    key_map = settings.get_exotel_key_map()
    for configured_key, target_biz_id in key_map.items():
        if hmac.compare_digest(clean_key, configured_key):
            return db.scalar(
                select(Business).where(Business.id == target_biz_id, Business.is_active.is_(True))
            )

    # 2. Check platform/default EXOTEL_API_KEY using constant-time comparison
    if settings.EXOTEL_API_KEY and hmac.compare_digest(clean_key, settings.EXOTEL_API_KEY):
        return db.scalar(select(Business).where(Business.is_active.is_(True)).limit(1))

    return None


def get_current_user(
    auth_header: HTTPAuthorizationCredentials | None = Depends(security),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db_session),
) -> User:
    """Validate Bearer JWT or Server-to-Server API Key and return current active user."""
    raw_token: str | None = None

    if auth_header and auth_header.credentials:
        raw_token = auth_header.credentials.strip()
    elif x_api_key:
        raw_token = x_api_key.strip()

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided or token expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # --------------------------------------------------------------------------
    # Check for Server-to-Server API Key (Exotel)
    # --------------------------------------------------------------------------
    key_map = settings.get_exotel_key_map()
    is_api_key = (
        any(hmac.compare_digest(raw_token, k) for k in key_map.keys())
        or bool(settings.EXOTEL_API_KEY and hmac.compare_digest(raw_token, settings.EXOTEL_API_KEY))
        or (raw_token.startswith("vat_") and raw_token.count(".") != 2)
    )

    if is_api_key:
        business = resolve_business_by_api_key(raw_token, db)
        if not business:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key or unauthorized business tenant.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Resolve primary active user for this tenant to represent server session
        tenant_user = db.scalar(
            select(User)
            .where(User.business_id == business.id, User.is_active.is_(True))
            .order_by(User.created_at.asc())
            .limit(1)
        )
        if not tenant_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No active user found for this business organization.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return tenant_user

    # --------------------------------------------------------------------------
    # Standard User JWT Authentication (Dashboard)
    # --------------------------------------------------------------------------
    payload = decode_access_token(raw_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload is missing subject.",
        )

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or deactivated.",
        )

    return user


def get_current_business(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> Business:
    """Return business entity for the authenticated user's organization."""
    business = db.get(Business, current_user.business_id)
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business organization not found.",
        )
    return business


def get_current_super_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure authenticated caller has platform-level super_admin role."""
    if current_user.role != "super_admin":
        logger.warning(
            "Access denied to super-admin resource for user %s with role '%s'",
            current_user.id,
            current_user.role,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform Super-Administrator privileges required.",
        )
    return current_user


def require_roles(allowed_roles: list[str]):
    """Factory dependency to enforce role-based access control (RBAC)."""

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role == "super_admin" or current_user.role in allowed_roles:
            return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Requires one of roles: {', '.join(allowed_roles)}",
        )

    return role_checker
