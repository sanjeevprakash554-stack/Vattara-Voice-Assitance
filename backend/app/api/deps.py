"""API dependency injection components for database sessions, authentication, and RBAC."""

from collections.abc import Generator
from typing import Callable
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import decode_access_token
from app.database.connection import get_db
from app.models.business import Business
from app.models.user import User, UserRole

# OAuth2 scheme configured with the platform's login endpoint for Swagger UI authorization
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=True,
)


def get_db_session() -> Generator[Session, None, None]:
    """Yield database session for API routes."""
    yield from get_db()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db_session),
) -> User:
    """Validate JWT access token and return the authenticated User model.

    Raises:
        HTTPException: 401 if token is invalid, expired, or user not found.
    """
    payload = decode_access_token(token)
    user_id_str: str | None = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token subject invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token subject identifier",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> User:
    """Ensure user account and parent business are both active.

    Multi-tenant rule: If a business is deactivated by a Super Admin,
    none of its users can access protected business operations.

    Raises:
        HTTPException: 403 if user or tenant is deactivated.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    # Super Admins operate globally without a bound tenant
    if current_user.role == UserRole.SUPER_ADMIN.value or current_user.role == "SUPER_ADMIN":
        return current_user

    # Tenant-bound user validation
    if current_user.business_id:
        business = db.get(Business, current_user.business_id)
        if not business or not business.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Business account is inactive. Please contact platform support.",
            )

    return current_user


def require_roles(*allowed_roles: UserRole) -> Callable[[User], User]:
    """Reusable role-based access control (RBAC) dependency factory."""

    def role_verifier(current_user: User = Depends(get_current_active_user)) -> User:
        user_role_normalized = str(current_user.role).upper()
        allowed_values = [r.value.upper() for r in allowed_roles]

        if user_role_normalized not in allowed_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this operation.",
            )
        return current_user

    return role_verifier


# Common role dependencies
require_super_admin = require_roles(UserRole.SUPER_ADMIN)
require_business_admin = require_roles(UserRole.SUPER_ADMIN, UserRole.BUSINESS_ADMIN)
require_staff = require_roles(UserRole.SUPER_ADMIN, UserRole.BUSINESS_ADMIN, UserRole.STAFF)


def get_current_business(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
) -> Business:
    """Return the active Business tenant for the authenticated session.

    Enforces that tenant operations always bind to the user's authentic business_id.
    """
    if not current_user.business_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current operation requires an associated business tenant context.",
        )

    business = db.get(Business, current_user.business_id)
    if not business or not business.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Associated business tenant is inactive.",
        )

    return business
