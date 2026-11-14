"""Staff and Doctor Management routes for business tenants."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db_session, require_roles
from app.core.logging import get_logger
from app.core.security import get_password_hash
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.staff import StaffMemberCreate, StaffMemberResponse, StaffMemberUpdate

logger = get_logger(__name__)
router = APIRouter()


@router.get("", response_model=list[StaffMemberResponse])
def list_staff(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[StaffMemberResponse]:
    """List all staff members, doctors, and operators for authenticated business tenant."""
    users = db.scalars(
        select(User)
        .where(User.business_id == current_user.business_id)
        .order_by(User.created_at.asc())
    ).all()
    return [StaffMemberResponse.model_validate(u) for u in users]


@router.post("", response_model=StaffMemberResponse, status_code=status.HTTP_201_CREATED)
def create_staff_member(
    payload: StaffMemberCreate,
    current_user: User = Depends(require_roles(["admin", "manager"])),
    db: Session = Depends(get_db_session),
) -> StaffMemberResponse:
    """Create a new staff user (doctor, receptionist, manager) under authenticated tenant."""
    # 1. Enforce unique email check across platform
    existing = db.scalar(select(User).where(User.email == payload.email.strip()))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email '{payload.email}' already exists.",
        )

    # 2. Check tenant staff limit against subscription quota
    sub = db.scalar(select(Subscription).where(Subscription.business_id == current_user.business_id))
    max_staff = sub.max_staff if sub else 5
    current_staff_count = (
        db.scalar(select(func.count(User.id)).where(User.business_id == current_user.business_id)) or 0
    )

    if current_staff_count >= max_staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Staff limit reached ({max_staff} members) for your current plan. Please upgrade to add more team members.",
        )

    role_val = payload.role.lower().strip()
    if role_val not in ("doctor", "manager", "staff", "receptionist", "admin"):
        role_val = "staff"

    new_user = User(
        business_id=current_user.business_id,
        email=payload.email.strip(),
        full_name=payload.full_name.strip(),
        hashed_password=get_password_hash(payload.password),
        role=role_val,
        is_active=payload.is_active,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.info("Admin %s created new staff user %s (%s)", current_user.email, new_user.email, new_user.role)
    return StaffMemberResponse.model_validate(new_user)


@router.put("/{user_id}", response_model=StaffMemberResponse)
def update_staff_member(
    user_id: str,
    payload: StaffMemberUpdate,
    current_user: User = Depends(require_roles(["admin", "manager"])),
    db: Session = Depends(get_db_session),
) -> StaffMemberResponse:
    """Update staff member profile, role, or active status."""
    target_user = db.scalar(
        select(User).where(User.id == user_id, User.business_id == current_user.business_id)
    )
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found.")

    if payload.full_name is not None:
        target_user.full_name = payload.full_name.strip()
    if payload.role is not None:
        target_user.role = payload.role.lower().strip()
    if payload.is_active is not None:
        target_user.is_active = payload.is_active
    if payload.password:
        target_user.hashed_password = get_password_hash(payload.password)

    db.commit()
    db.refresh(target_user)
    return StaffMemberResponse.model_validate(target_user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_staff_member(
    user_id: str,
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db_session),
) -> None:
    """Deactivate or remove a staff member."""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own active administrator account.",
        )

    target_user = db.scalar(
        select(User).where(User.id == user_id, User.business_id == current_user.business_id)
    )
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found.")

    db.delete(target_user)
    db.commit()
