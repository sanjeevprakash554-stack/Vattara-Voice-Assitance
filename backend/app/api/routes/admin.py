"""Super Admin platform administration API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.api.deps import get_db_session, require_super_admin
from app.core.logging import get_logger
from app.models.business import Business
from app.models.user import User
from app.schemas.business import (
    BusinessDetailResponse,
    BusinessResponse,
    BusinessStatusUpdateRequest,
)

logger = get_logger(__name__)
router = APIRouter()


@router.get(
    "/businesses",
    response_model=list[BusinessResponse],
    summary="List Registered Businesses (Super Admin Only)",
    description="Retrieve all registered business organizations across the platform.",
)
def list_all_businesses(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    super_admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db_session),
) -> list[BusinessResponse]:
    """List all business tenants with pagination."""
    businesses = (
        db.query(Business)
        .order_by(Business.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [BusinessResponse.model_validate(b) for b in businesses]


@router.get(
    "/businesses/{business_id}",
    response_model=BusinessDetailResponse,
    summary="Get Business Details (Super Admin Only)",
    description="Retrieve complete metadata and resource metrics for a specific business tenant.",
)
def get_business_details(
    business_id: int,
    super_admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db_session),
) -> BusinessDetailResponse:
    """Retrieve deep business tenant details."""
    business = db.get(Business, business_id)
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business organization not found.",
        )

    return BusinessDetailResponse(
        id=business.id,
        business_name=business.business_name,
        business_type=business.business_type,
        email=business.email,
        phone_number=business.phone_number,
        address=business.address,
        is_active=business.is_active,
        created_at=business.created_at,
        users_count=len(business.users),
        customers_count=len(business.customers),
        appointments_count=len(business.appointments),
        call_histories_count=len(business.call_histories),
    )


@router.patch(
    "/businesses/{business_id}/status",
    response_model=BusinessResponse,
    summary="Activate or Deactivate Business (Super Admin Only)",
    description="Toggle operational status for a business tenant. Inactive businesses cannot use services.",
)
def update_business_status(
    business_id: int,
    payload: BusinessStatusUpdateRequest,
    super_admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db_session),
) -> BusinessResponse:
    """Toggle business tenant active status."""
    business = db.get(Business, business_id)
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business organization not found.",
        )

    business.is_active = payload.is_active
    db.commit()
    db.refresh(business)

    status_str = "activated" if business.is_active else "deactivated"
    logger.info(
        "Super Admin ID %d %s Business ID %d ('%s')",
        super_admin.id,
        status_str,
        business.id,
        business.business_name,
    )

    return BusinessResponse.model_validate(business)
