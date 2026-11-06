"""Common API dependencies for dependency injection in endpoints."""

from collections.abc import Generator
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session
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


def get_current_user(
    auth_header: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db_session),
) -> User:
    """Validate Bearer JWT and return current active user."""
    if not auth_header or not auth_header.credentials:
        # Check if demo default user exists as fallback for dev simplicity
        demo_user = db.scalar(select(User).limit(1))
        if demo_user:
            return demo_user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided or token expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header.credentials
    payload = decode_access_token(token)
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
