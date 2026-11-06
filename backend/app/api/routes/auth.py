"""Authentication and profile management API routes."""

from typing import Annotated
from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.api.deps import get_current_active_user, get_db_session
from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    get_password_hash,
    validate_password_strength,
    verify_password,
)
from app.models.business import Business
from app.models.user import User, UserRole
from app.schemas.auth import (
    BusinessRegisterRequest,
    BusinessRegisterResponse,
    ChangePasswordRequest,
    LoginRequest,
    MessageResponse,
    TokenResponse,
)
from app.schemas.business import BusinessResponse
from app.schemas.user import UserProfileResponse, UserResponse

logger = get_logger(__name__)
router = APIRouter()


@router.post(
    "/register",
    response_model=BusinessRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Business & Administrator Account",
    description="Atomic registration creating a new tenant organization and its primary Business Admin user.",
)
def register_business(
    payload: BusinessRegisterRequest,
    db: Session = Depends(get_db_session),
) -> BusinessRegisterResponse:
    """Register a new business organization with its initial administrator."""
    # 1. Enforce password complexity
    is_strong, reason = validate_password_strength(payload.admin_password)
    if not is_strong:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Weak password: {reason}",
        )

    # 2. Check for duplicate business email
    existing_business = db.query(Business).filter(Business.email == payload.business_email).first()
    if existing_business:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A business with this email address is already registered.",
        )

    # 3. Check for duplicate administrator email
    existing_user = db.query(User).filter(User.email == payload.admin_email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this administrator email address already exists.",
        )

    # 4. Atomic transaction creating Business and Admin User
    try:
        new_business = Business(
            business_name=payload.business_name.strip(),
            business_type=payload.business_type.strip(),
            email=payload.business_email.lower().strip(),
            phone_number=payload.business_phone_number.strip() if payload.business_phone_number else None,
            address=payload.business_address.strip() if payload.business_address else None,
            is_active=True,
        )
        db.add(new_business)
        db.flush()  # Acquire generated business.id

        admin_user = User(
            business_id=new_business.id,
            full_name=payload.admin_full_name.strip(),
            email=payload.admin_email.lower().strip(),
            password_hash=get_password_hash(payload.admin_password),
            role=UserRole.BUSINESS_ADMIN.value,
            is_active=True,
        )
        db.add(admin_user)
        db.commit()

        db.refresh(new_business)
        db.refresh(admin_user)

        logger.info(
            "Registered new business '%s' (ID %d) with admin '%s'",
            new_business.business_name,
            new_business.id,
            admin_user.email,
        )

        return BusinessRegisterResponse(
            business=BusinessResponse.model_validate(new_business),
            admin_user=UserResponse.model_validate(admin_user),
            message="Business and administrator account registered successfully.",
        )
    except Exception as exc:
        db.rollback()
        logger.error("Transaction error during business registration: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed due to an unexpected internal error.",
        )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User Login (OAuth2 Compatible)",
    description="Authenticate via email and password (supports both form data and JSON body).",
)
async def login(
    request: Request,
    db: Session = Depends(get_db_session),
) -> TokenResponse:
    """Authenticate user credentials and generate a signed JWT bearer token."""
    email: str = ""
    password: str = ""

    # Check whether request is sent as standard form-urlencoded (Swagger UI) or JSON
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        email = body.get("email", "").strip()
        password = body.get("password", "")
    else:
        form = await request.form()
        # OAuth2 standard form fields: 'username' represents the email
        email = str(form.get("username", "") or form.get("email", "")).strip()
        password = str(form.get("password", ""))

    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and password are required.",
        )

    # Lookup user
    user = db.query(User).filter(User.email == email.lower()).first()

    # Constant-time-like generic error to prevent user enumeration
    if not user or not verify_password(password, user.password_hash):
        logger.warning("Failed login attempt for email: %s", email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check account active status
    if not user.is_active:
        logger.warning("Deactivated user login attempted: %s", email)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Please contact support.",
        )

    # Multi-tenant status check for non-Super Admins
    business = None
    if user.business_id:
        business = db.get(Business, user.business_id)
        if not business or not business.is_active:
            logger.warning("Inactive business login attempted by user: %s", email)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your business account is inactive. Please contact support.",
            )

    # Generate JWT Token with user claims
    access_token = create_access_token(
        subject=user.id,
        business_id=user.business_id,
        role=user.role,
    )

    profile = UserProfileResponse(
        id=user.id,
        business_id=user.business_id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        business_name=business.business_name if business else None,
        business_type=business.business_type if business else None,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=profile,
    )


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get Current User Profile",
    description="Retrieve the authenticated user's profile and business details.",
)
def get_current_user_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
) -> UserProfileResponse:
    """Return authenticated user profile."""
    business_name = None
    business_type = None

    if current_user.business_id:
        business = db.get(Business, current_user.business_id)
        if business:
            business_name = business.business_name
            business_type = business.business_type

    return UserProfileResponse(
        id=current_user.id,
        business_id=current_user.business_id,
        full_name=current_user.full_name,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        business_name=business_name,
        business_type=business_type,
    )


@router.put(
    "/me",
    response_model=UserProfileResponse,
    summary="Update Current User Profile",
    description="Update permitted profile fields (display name). Role and tenant cannot be changed.",
)
def update_current_user_profile(
    payload: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
) -> UserProfileResponse:
    """Update authenticated user profile information."""
    if "full_name" in payload and payload["full_name"]:
        full_name_clean = str(payload["full_name"]).strip()
        if len(full_name_clean) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Full name must be at least 2 characters.",
            )
        current_user.full_name = full_name_clean

    db.commit()
    db.refresh(current_user)

    return get_current_user_profile(current_user=current_user, db=db)


@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="Change User Password",
    description="Securely change password after verifying current credentials and complexity policy.",
)
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
) -> MessageResponse:
    """Change user password with Argon2 hashing and complexity validation."""
    # 1. Verify current password
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password.",
        )

    # 2. Prevent reusing identical password
    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password.",
        )

    # 3. Validate new password strength
    is_strong, reason = validate_password_strength(payload.new_password)
    if not is_strong:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Weak new password: {reason}",
        )

    # 4. Hash and persist
    current_user.password_hash = get_password_hash(payload.new_password)
    db.commit()

    logger.info("Password successfully changed for user ID %d", current_user.id)
    return MessageResponse(message="Password changed successfully.")
