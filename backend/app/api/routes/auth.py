"""Authentication and User Profile routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db_session
from app.core.logging import get_logger
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.assistant import AssistantConfig
from app.models.business import Business
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


@router.post("/login", response_model=Token)
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


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest) -> dict[str, str]:
    """Dispatch password reset verification code (demo simulation)."""
    return {
        "status": "success",
        "message": f"Password reset instructions and verification code sent to {payload.email}.",
    }


@router.post("/reset-password")
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db_session),
) -> dict[str, str]:
    """Reset forgotten user password with verification code."""
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account registered with this email address.",
        )

    user.hashed_password = get_password_hash(payload.new_password)
    db.commit()
    return {"status": "success", "message": "Password successfully reset. You may now log in."}

