"""Staff and User Management routes for Business Administrators."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.api.deps import get_db_session, require_business_admin
from app.core.logging import get_logger
from app.core.security import get_password_hash, validate_password_strength
from app.models.user import User, UserRole
from app.schemas.auth import MessageResponse
from app.schemas.user import UserCreateRequest, UserResponse, UserUpdateRequest

logger = get_logger(__name__)
router = APIRouter()


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Staff Member",
    description="Create a new staff or manager user bound strictly to the administrator's business tenant.",
)
def create_staff_user(
    payload: UserCreateRequest,
    current_admin: User = Depends(require_business_admin),
    db: Session = Depends(get_db_session),
) -> UserResponse:
    """Create a new staff member within the current tenant."""
    if not current_admin.business_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current admin does not belong to a business tenant.",
        )

    # 1. Prohibit elevating users to Super Admin through tenant endpoints
    if payload.role == UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Business Administrators cannot create Super Admin accounts.",
        )

    # 2. Check password complexity
    is_strong, reason = validate_password_strength(payload.password)
    if not is_strong:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Weak password: {reason}",
        )

    # 3. Check for unique email across platform
    existing_user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address is already registered.",
        )

    # 4. Create staff user bound strictly to admin's business_id
    new_user = User(
        business_id=current_admin.business_id,
        full_name=payload.full_name.strip(),
        email=payload.email.lower().strip(),
        password_hash=get_password_hash(payload.password),
        role=payload.role.value,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.info(
        "Admin ID %d created staff user '%s' (ID %d) in Business ID %d",
        current_admin.id,
        new_user.email,
        new_user.id,
        current_admin.business_id,
    )

    return UserResponse.model_validate(new_user)


@router.get(
    "",
    response_model=list[UserResponse],
    summary="List Business Staff",
    description="Retrieve all staff accounts belonging to the authenticated business tenant.",
)
def list_business_staff(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_admin: User = Depends(require_business_admin),
    db: Session = Depends(get_db_session),
) -> list[UserResponse]:
    """List staff belonging to current business tenant with pagination."""
    users = (
        db.query(User)
        .filter(User.business_id == current_admin.business_id)
        .order_by(User.id.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [UserResponse.model_validate(u) for u in users]


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get Staff Member Details",
    description="Retrieve details of a staff member belonging to the authenticated business.",
)
def get_staff_user(
    user_id: int,
    current_admin: User = Depends(require_business_admin),
    db: Session = Depends(get_db_session),
) -> UserResponse:
    """Retrieve details of a specific staff member within the tenant."""
    # Multi-tenant scoping: must match user_id AND business_id
    user = (
        db.query(User)
        .filter(User.id == user_id, User.business_id == current_admin.business_id)
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff user not found in this business organization.",
        )
    return UserResponse.model_validate(user)


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update Staff Member Details",
    description="Update permitted details (full name, role, active status) of a tenant staff member.",
)
def update_staff_user(
    user_id: int,
    payload: UserUpdateRequest,
    current_admin: User = Depends(require_business_admin),
    db: Session = Depends(get_db_session),
) -> UserResponse:
    """Update staff member details."""
    user = (
        db.query(User)
        .filter(User.id == user_id, User.business_id == current_admin.business_id)
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff user not found in this business organization.",
        )

    # Prohibit privilege escalation to Super Admin
    if payload.role == UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot assign Super Admin role.",
        )

    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()
    if payload.role is not None:
        user.role = payload.role.value
    if payload.is_active is not None:
        # Prevent admin deactivating self through staff update endpoint
        if user.id == current_admin.id and not payload.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Administrators cannot deactivate their own account.",
            )
        user.is_active = payload.is_active

    db.commit()
    db.refresh(user)

    logger.info("Admin ID %d updated staff user ID %d", current_admin.id, user.id)
    return UserResponse.model_validate(user)


@router.delete(
    "/{user_id}",
    response_model=MessageResponse,
    summary="Deactivate Staff Member",
    description="Deactivate a staff member account (soft deactivation).",
)
def deactivate_staff_user(
    user_id: int,
    current_admin: User = Depends(require_business_admin),
    db: Session = Depends(get_db_session),
) -> MessageResponse:
    """Deactivate a staff account within the tenant."""
    if user_id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own administrator account.",
        )

    user = (
        db.query(User)
        .filter(User.id == user_id, User.business_id == current_admin.business_id)
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff user not found in this business organization.",
        )

    user.is_active = False
    db.commit()

    logger.info("Admin ID %d deactivated staff user ID %d", current_admin.id, user.id)
    return MessageResponse(message=f"Staff user '{user.email}' has been successfully deactivated.")
