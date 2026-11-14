"""Authentication and User Profile routes."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db_session
from app.core.config import settings
from app.core.logging import get_logger
from app.core.rate_limiter import SlidingWindowRateLimiter
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.assistant import AssistantConfig
from app.models.business import Business
from app.models.password_reset import PasswordReset
from app.models.user import User
from app.schemas.auth import (
    BusinessResponse,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterBusinessRequest,
    ResetPasswordRequest,
    Token,
    UpdateProfileRequest,
    UserProfileResponse,
    UserResponse,
)

logger = get_logger(__name__)
router = APIRouter()

login_rate_limiter = SlidingWindowRateLimiter(
    times=settings.RATE_LIMIT_LOGIN_PER_MINUTE,
    seconds=60,
    name="auth_login",
)

forgot_password_rate_limiter = SlidingWindowRateLimiter(
    times=settings.RATE_LIMIT_FORGOT_PASSWORD_PER_MINUTE,
    seconds=60,
    name="auth_forgot_password",
)

reset_password_rate_limiter = SlidingWindowRateLimiter(
    times=settings.RATE_LIMIT_RESET_PASSWORD_PER_MINUTE,
    seconds=60,
    name="auth_reset_password",
)


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register_business(
    payload: RegisterBusinessRequest,
    db: Session = Depends(get_db_session),
) -> Token:
    """Register a new business organization and its primary administrator."""
    # Check if user email or business email already registered
    existing_user = db.scalar(select(User).where(User.email == payload.admin_email))
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this admin email address already exists.",
        )

    # Create Business
    business = Business(
        name=payload.business_name,
        vertical=payload.vertical,
        phone=payload.business_phone,
        email=payload.business_email,
        timezone=payload.timezone,
        address=payload.address,
        is_active=True,
    )
    db.add(business)
    db.flush()

    # Create Admin User
    user = User(
        business_id=business.id,
        email=payload.admin_email,
        full_name=payload.admin_name,
        hashed_password=get_password_hash(payload.admin_password),
        role="admin",
        is_active=True,
    )
    db.add(user)
    db.flush()

    # Create Default Assistant Configuration
    assistant_config = AssistantConfig(
        business_id=business.id,
        assistant_name=f"{payload.business_name} AI",
        language="en-US",
        voice="alloy",
        system_prompt=f"You are the voice assistant for {payload.business_name}.",
        business_info=f"Official voice receptionist for {payload.business_name} ({payload.vertical}).",
        is_active=True,
    )
    db.add(assistant_config)
    db.commit()
    db.refresh(user)
    db.refresh(business)

    access_token = create_access_token(
        subject=user.id,
        extra_claims={"business_id": business.id, "role": user.role},
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
        business=BusinessResponse.model_validate(business),
    )


@router.post("/login", response_model=Token, dependencies=[Depends(login_rate_limiter)])
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db_session),
) -> Token:
    """Authenticate with email and password to receive a JWT access token."""
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email credentials or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This user account has been deactivated.",
        )

    business = db.get(Business, user.business_id)
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business tenant organization not found.",
        )

    access_token = create_access_token(
        subject=user.id,
        extra_claims={"business_id": business.id, "role": user.role},
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
        business=BusinessResponse.model_validate(business),
    )


@router.get("/me", response_model=UserProfileResponse)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> UserProfileResponse:
    """Return profile details of the currently authenticated user and business."""
    business = db.get(Business, current_user.business_id)
    return UserProfileResponse(
        user=UserResponse.model_validate(current_user),
        business=BusinessResponse.model_validate(business),
    )


@router.put("/profile", response_model=UserProfileResponse)
def update_profile(
    payload: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> UserProfileResponse:
    """Update profile details and optional password for current user/business."""
    if payload.full_name:
        current_user.full_name = payload.full_name

    business = db.get(Business, current_user.business_id)
    if business:
        if payload.business_name:
            business.name = payload.business_name
        if payload.phone:
            business.phone = payload.phone
        if payload.address:
            business.address = payload.address

    if payload.new_password:
        if payload.current_password and not verify_password(
            payload.current_password, current_user.hashed_password
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password verification failed.",
            )
        current_user.hashed_password = get_password_hash(payload.new_password)

    db.commit()
    db.refresh(current_user)
    if business:
        db.refresh(business)

    return UserProfileResponse(
        user=UserResponse.model_validate(current_user),
        business=BusinessResponse.model_validate(business),
    )


@router.post("/forgot-password", dependencies=[Depends(forgot_password_rate_limiter)])
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db_session),
) -> dict[str, Any]:
    """Generate and record a secure, time-limited password reset verification code."""
    user = db.scalar(select(User).where(User.email == payload.email, User.is_active.is_(True)))

    # Generic user-facing message to prevent email enumeration
    response_msg = f"If an active account exists for {payload.email}, password reset instructions have been dispatched."

    if not user:
        return {"status": "success", "message": response_msg}

    # Invalidate any existing unused reset codes for this user
    existing_resets = db.scalars(
        select(PasswordReset).where(
            PasswordReset.user_id == user.id,
            PasswordReset.is_used.is_(False),
        )
    ).all()
    for r in existing_resets:
        r.is_used = True

    # Generate cryptographically secure 6-digit verification code
    reset_code = f"{secrets.randbelow(900000) + 100000}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

    reset_record = PasswordReset(
        user_id=user.id,
        email=user.email,
        code_hash=get_password_hash(reset_code),
        expires_at=expires_at,
        is_used=False,
    )
    db.add(reset_record)
    db.commit()

    logger.info("Generated secure password reset code for user %s (expires in 15 mins)", user.email)

    result: dict[str, Any] = {"status": "success", "message": response_msg}
    # In non-production environments, expose reset_code in response to assist development & testing
    if settings.ENVIRONMENT != "production":
        result["reset_code"] = reset_code

    return result


@router.post("/reset-password", dependencies=[Depends(reset_password_rate_limiter)])
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db_session),
) -> dict[str, str]:
    """Reset forgotten user password after verifying time-limited code."""
    if not payload.reset_code or not payload.reset_code.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code is required.",
        )

    user = db.scalar(select(User).where(User.email == payload.email, User.is_active.is_(True)))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active account registered with this email address.",
        )

    now = datetime.now(timezone.utc)
    # Find most recent valid, unexpired, unused reset record for this user
    reset_record = db.scalar(
        select(PasswordReset)
        .where(
            PasswordReset.user_id == user.id,
            PasswordReset.is_used.is_(False),
            PasswordReset.expires_at >= now,
        )
        .order_by(PasswordReset.created_at.desc())
        .limit(1)
    )

    if not reset_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset code has expired or was not requested.",
        )

    # Verify code using PBKDF2 hash verification
    if not verify_password(payload.reset_code.strip(), reset_record.code_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset verification code.",
        )

    # Invalidate code upon successful use
    reset_record.is_used = True

    # Update user password with secure hash
    user.hashed_password = get_password_hash(payload.new_password)
    db.commit()
    logger.info("Password successfully reset for user %s", user.email)

    return {"status": "success", "message": "Password successfully reset. You may now log in."}

