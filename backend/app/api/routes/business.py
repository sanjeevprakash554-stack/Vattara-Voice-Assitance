"""Business profile, working hours, service categories, and business services routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.api.deps import (
    get_current_active_user,
    get_current_business,
    get_db_session,
    require_business_admin,
    require_staff,
)
from app.core.logging import get_logger
from app.models.business import Business
from app.models.business_service import BusinessService
from app.models.service_category import ServiceCategory
from app.models.user import User
from app.models.working_hours import BusinessWorkingHours
from app.schemas.auth import MessageResponse
from app.schemas.business import (
    BusinessProfileResponse,
    BusinessProfileUpdateRequest,
)
from app.schemas.service import (
    BusinessServiceCreateRequest,
    BusinessServiceResponse,
    BusinessServiceUpdateRequest,
    ServiceCategoryCreateRequest,
    ServiceCategoryResponse,
    ServiceCategoryUpdateRequest,
)
from app.schemas.working_hours import (
    WorkingHoursResponse,
    WorkingHoursUpdateRequest,
)

logger = get_logger(__name__)
router = APIRouter()


# ==============================================================================
# MODULE 1: BUSINESS PROFILE MANAGEMENT
# ==============================================================================

@router.get(
    "/profile",
    response_model=BusinessProfileResponse,
    tags=["Business Profile"],
    summary="Get Business Profile",
    description="Retrieve the authenticated user's organization profile (accessible by Admin and Staff).",
)
def get_business_profile(
    business: Business = Depends(get_current_business),
) -> BusinessProfileResponse:
    """Return the authenticated user's business profile."""
    return BusinessProfileResponse.model_validate(business)


@router.put(
    "/profile",
    response_model=BusinessProfileResponse,
    tags=["Business Profile"],
    summary="Update Business Profile",
    description="Update business details (restricted to Business Admin).",
)
def update_business_profile(
    payload: BusinessProfileUpdateRequest,
    business: Business = Depends(get_current_business),
    current_admin: User = Depends(require_business_admin),
    db: Session = Depends(get_db_session),
) -> BusinessProfileResponse:
    """Update tenant organization profile details."""
    # Check duplicate email if email is being updated
    if payload.email is not None and payload.email != business.email:
        existing = db.query(Business).filter(
            Business.email == payload.email,
            Business.id != business.id,
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A business with this email address is already registered.",
            )
        business.email = payload.email

    if payload.business_name is not None:
        business.business_name = payload.business_name.strip()
    if payload.business_type is not None:
        business.business_type = payload.business_type.strip()
    if payload.phone_number is not None:
        business.phone_number = payload.phone_number.strip()
    if payload.address is not None:
        business.address = payload.address.strip()
    if payload.website is not None:
        business.website = payload.website.strip()
    if payload.description is not None:
        business.description = payload.description.strip()
    if payload.logo_url is not None:
        business.logo_url = payload.logo_url.strip()
    if payload.timezone is not None:
        business.timezone = payload.timezone.strip()

    db.commit()
    db.refresh(business)

    logger.info("Admin ID %d updated business profile for Business ID %d", current_admin.id, business.id)
    return BusinessProfileResponse.model_validate(business)


# ==============================================================================
# MODULE 2: BUSINESS WORKING HOURS
# ==============================================================================

@router.get(
    "/working-hours",
    response_model=list[WorkingHoursResponse],
    tags=["Working Hours"],
    summary="Get Weekly Working Hours",
    description="Retrieve the weekly operating schedule for the authenticated business tenant.",
)
def get_working_hours(
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db_session),
) -> list[WorkingHoursResponse]:
    """Retrieve all working hours for the business ordered by day of week (0=Mon to 6=Sun)."""
    hours = (
        db.query(BusinessWorkingHours)
        .filter(BusinessWorkingHours.business_id == business.id)
        .order_by(BusinessWorkingHours.day_of_week.asc())
        .all()
    )
    return [
        WorkingHoursResponse(
            id=h.id,
            business_id=h.business_id,
            day_of_week=h.day_of_week,
            day_name=h.day_name,
            opening_time=h.opening_time,
            closing_time=h.closing_time,
            is_closed=h.is_closed,
            created_at=h.created_at,
            updated_at=h.updated_at,
        )
        for h in hours
    ]


@router.put(
    "/working-hours",
    response_model=list[WorkingHoursResponse],
    tags=["Working Hours"],
    summary="Create or Update Working Hours",
    description="Set or update the operating schedule for days of the week (restricted to Business Admin).",
)
def update_working_hours(
    payload: WorkingHoursUpdateRequest,
    business: Business = Depends(get_current_business),
    current_admin: User = Depends(require_business_admin),
    db: Session = Depends(get_db_session),
) -> list[WorkingHoursResponse]:
    """Create or update working hours for each specified day."""
    for item in payload.hours:
        record = (
            db.query(BusinessWorkingHours)
            .filter(
                BusinessWorkingHours.business_id == business.id,
                BusinessWorkingHours.day_of_week == item.day_of_week,
            )
            .first()
        )
        if record:
            record.opening_time = item.opening_time if not item.is_closed else None
            record.closing_time = item.closing_time if not item.is_closed else None
            record.is_closed = item.is_closed
        else:
            record = BusinessWorkingHours(
                business_id=business.id,
                day_of_week=item.day_of_week,
                opening_time=item.opening_time if not item.is_closed else None,
                closing_time=item.closing_time if not item.is_closed else None,
                is_closed=item.is_closed,
            )
            db.add(record)

    db.commit()
    logger.info("Admin ID %d updated working hours for Business ID %d", current_admin.id, business.id)
    return get_working_hours(business=business, db=db)


# ==============================================================================
# MODULE 3: BUSINESS SERVICE CATEGORIES
# ==============================================================================

@router.post(
    "/categories",
    response_model=ServiceCategoryResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Service Categories"],
    summary="Create Service Category",
    description="Create a new service grouping category (restricted to Business Admin).",
)
def create_service_category(
    payload: ServiceCategoryCreateRequest,
    business: Business = Depends(get_current_business),
    current_admin: User = Depends(require_business_admin),
    db: Session = Depends(get_db_session),
) -> ServiceCategoryResponse:
    """Create a new service category within the authenticated tenant."""
    # Prevent duplicate active category names within the same business
    clean_name = payload.category_name.strip()
    existing = (
        db.query(ServiceCategory)
        .filter(
            ServiceCategory.business_id == business.id,
            ServiceCategory.category_name.ilike(clean_name),
            ServiceCategory.is_active.is_(True),
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An active service category named '{clean_name}' already exists in your business.",
        )

    category = ServiceCategory(
        business_id=business.id,
        category_name=clean_name,
        description=payload.description.strip() if payload.description else None,
        is_active=True,
    )
    db.add(category)
    db.commit()
    db.refresh(category)

    logger.info("Created category '%s' (ID %d) in Business ID %d", category.category_name, category.id, business.id)
    return ServiceCategoryResponse.model_validate(category)


@router.get(
    "/categories",
    response_model=list[ServiceCategoryResponse],
    tags=["Service Categories"],
    summary="List Service Categories",
    description="Retrieve all service categories belonging to the business tenant.",
)
def list_service_categories(
    is_active: bool | None = Query(default=None, description="Optional active status filter"),
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db_session),
) -> list[ServiceCategoryResponse]:
    """List service categories for the current business tenant."""
    query = db.query(ServiceCategory).filter(ServiceCategory.business_id == business.id)
    if is_active is not None:
        query = query.filter(ServiceCategory.is_active == is_active)

    categories = query.order_by(ServiceCategory.category_name.asc()).all()
    return [ServiceCategoryResponse.model_validate(c) for c in categories]


@router.get(
    "/categories/{category_id}",
    response_model=ServiceCategoryResponse,
    tags=["Service Categories"],
    summary="Get Service Category",
    description="Retrieve details of a specific service category.",
)
def get_service_category(
    category_id: int,
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db_session),
) -> ServiceCategoryResponse:
    """Retrieve a single category ensuring strict tenant boundary isolation."""
    category = (
        db.query(ServiceCategory)
        .filter(ServiceCategory.id == category_id, ServiceCategory.business_id == business.id)
        .first()
    )
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service category not found in your business organization.",
        )
    return ServiceCategoryResponse.model_validate(category)


@router.put(
    "/categories/{category_id}",
    response_model=ServiceCategoryResponse,
    tags=["Service Categories"],
    summary="Update Service Category",
    description="Update a service category (restricted to Business Admin).",
)
def update_service_category(
    category_id: int,
    payload: ServiceCategoryUpdateRequest,
    business: Business = Depends(get_current_business),
    current_admin: User = Depends(require_business_admin),
    db: Session = Depends(get_db_session),
) -> ServiceCategoryResponse:
    """Update service category name, description, or active status."""
    category = (
        db.query(ServiceCategory)
        .filter(ServiceCategory.id == category_id, ServiceCategory.business_id == business.id)
        .first()
    )
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service category not found in your business organization.",
        )

    if payload.category_name is not None:
        clean_name = payload.category_name.strip()
        existing = (
            db.query(ServiceCategory)
            .filter(
                ServiceCategory.business_id == business.id,
                ServiceCategory.category_name.ilike(clean_name),
                ServiceCategory.id != category.id,
                ServiceCategory.is_active.is_(True),
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"An active service category named '{clean_name}' already exists in your business.",
            )
        category.category_name = clean_name

    if payload.description is not None:
        category.description = payload.description.strip()
    if payload.is_active is not None:
        category.is_active = payload.is_active

    db.commit()
    db.refresh(category)
    return ServiceCategoryResponse.model_validate(category)


@router.delete(
    "/categories/{category_id}",
    response_model=MessageResponse,
    tags=["Service Categories"],
    summary="Deactivate Service Category",
    description="Soft-deactivate a service category (restricted to Business Admin).",
)
def delete_service_category(
    category_id: int,
    business: Business = Depends(get_current_business),
    current_admin: User = Depends(require_business_admin),
    db: Session = Depends(get_db_session),
) -> MessageResponse:
    """Soft deactivation of service category."""
    category = (
        db.query(ServiceCategory)
        .filter(ServiceCategory.id == category_id, ServiceCategory.business_id == business.id)
        .first()
    )
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service category not found in your business organization.",
        )

    category.is_active = False
    db.commit()

    logger.info("Admin ID %d soft-deactivated category ID %d in Business ID %d", current_admin.id, category.id, business.id)
    return MessageResponse(message="Service category successfully deactivated.")


# ==============================================================================
# MODULE 4: BUSINESS SERVICES MANAGEMENT
# ==============================================================================

@router.post(
    "/services",
    response_model=BusinessServiceResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Business Services"],
    summary="Create Business Service",
    description="Create a commercial service, session, or treatment (restricted to Business Admin).",
)
def create_business_service(
    payload: BusinessServiceCreateRequest,
    business: Business = Depends(get_current_business),
    current_admin: User = Depends(require_business_admin),
    db: Session = Depends(get_db_session),
) -> BusinessServiceResponse:
    """Create a new service offering."""
    # 1. Validate category ownership if category_id provided
    category_name = None
    if payload.category_id is not None:
        category = (
            db.query(ServiceCategory)
            .filter(ServiceCategory.id == payload.category_id, ServiceCategory.business_id == business.id)
            .first()
        )
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assigned category does not belong to your business.",
            )
        category_name = category.category_name

    # 2. Prevent duplicate active service names within the business
    clean_name = payload.service_name.strip()
    existing = (
        db.query(BusinessService)
        .filter(
            BusinessService.business_id == business.id,
            BusinessService.service_name.ilike(clean_name),
            BusinessService.is_active.is_(True),
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An active service named '{clean_name}' already exists in your business.",
        )

    service = BusinessService(
        business_id=business.id,
        category_id=payload.category_id,
        service_name=clean_name,
        description=payload.description.strip() if payload.description else None,
        duration_minutes=payload.duration_minutes,
        price=payload.price,
        currency=payload.currency.upper().strip(),
        is_active=True,
    )
    db.add(service)
    db.commit()
    db.refresh(service)

    logger.info("Admin ID %d created service '%s' (ID %d)", current_admin.id, service.service_name, service.id)

    res = BusinessServiceResponse.model_validate(service)
    res.category_name = category_name
    return res


@router.get(
    "/services",
    response_model=list[BusinessServiceResponse],
    tags=["Business Services"],
    summary="List Business Services",
    description="Retrieve services with optional category filtering, text search, active filtering, and pagination.",
)
def list_business_services(
    category_id: int | None = Query(default=None, description="Filter by category ID"),
    search: str | None = Query(default=None, description="Search term for service name or description"),
    is_active: bool | None = Query(default=None, description="Filter by active status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db_session),
) -> list[BusinessServiceResponse]:
    """List business services with search, filtering, and pagination."""
    query = db.query(BusinessService).filter(BusinessService.business_id == business.id)

    if category_id is not None:
        query = query.filter(BusinessService.category_id == category_id)

    if is_active is not None:
        query = query.filter(BusinessService.is_active == is_active)

    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                BusinessService.service_name.ilike(search_pattern),
                BusinessService.description.ilike(search_pattern),
            )
        )

    services = query.order_by(BusinessService.service_name.asc()).offset(skip).limit(limit).all()

    # Pre-fetch category names map
    cat_ids = {s.category_id for s in services if s.category_id}
    cat_map = {}
    if cat_ids:
        cats = db.query(ServiceCategory.id, ServiceCategory.category_name).filter(ServiceCategory.id.in_(cat_ids)).all()
        cat_map = {c.id: c.category_name for c in cats}

    output = []
    for s in services:
        item = BusinessServiceResponse.model_validate(s)
        item.category_name = cat_map.get(s.category_id)
        output.append(item)
    return output


@router.get(
    "/services/{service_id}",
    response_model=BusinessServiceResponse,
    tags=["Business Services"],
    summary="Get Business Service Details",
    description="Retrieve details of a specific service offering.",
)
def get_business_service(
    service_id: int,
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db_session),
) -> BusinessServiceResponse:
    """Retrieve service details with cross-tenant isolation check."""
    service = (
        db.query(BusinessService)
        .filter(BusinessService.id == service_id, BusinessService.business_id == business.id)
        .first()
    )
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business service not found in your business organization.",
        )

    res = BusinessServiceResponse.model_validate(service)
    if service.category_id:
        cat = db.get(ServiceCategory, service.category_id)
        res.category_name = cat.category_name if cat else None
    return res


@router.put(
    "/services/{service_id}",
    response_model=BusinessServiceResponse,
    tags=["Business Services"],
    summary="Update Business Service",
    description="Update a business service (restricted to Business Admin).",
)
def update_business_service(
    service_id: int,
    payload: BusinessServiceUpdateRequest,
    business: Business = Depends(get_current_business),
    current_admin: User = Depends(require_business_admin),
    db: Session = Depends(get_db_session),
) -> BusinessServiceResponse:
    """Update service offering parameters."""
    service = (
        db.query(BusinessService)
        .filter(BusinessService.id == service_id, BusinessService.business_id == business.id)
        .first()
    )
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business service not found in your business organization.",
        )

    # Validate category ownership if category_id updated
    if payload.category_id is not None:
        category = (
            db.query(ServiceCategory)
            .filter(ServiceCategory.id == payload.category_id, ServiceCategory.business_id == business.id)
            .first()
        )
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assigned category does not belong to your business.",
            )
        service.category_id = payload.category_id

    if payload.service_name is not None:
        clean_name = payload.service_name.strip()
        existing = (
            db.query(BusinessService)
            .filter(
                BusinessService.business_id == business.id,
                BusinessService.service_name.ilike(clean_name),
                BusinessService.id != service.id,
                BusinessService.is_active.is_(True),
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"An active service named '{clean_name}' already exists in your business.",
            )
        service.service_name = clean_name

    if payload.description is not None:
        service.description = payload.description.strip()
    if payload.duration_minutes is not None:
        service.duration_minutes = payload.duration_minutes
    if payload.price is not None:
        service.price = payload.price
    if payload.currency is not None:
        service.currency = payload.currency.upper().strip()
    if payload.is_active is not None:
        service.is_active = payload.is_active

    db.commit()
    db.refresh(service)

    res = BusinessServiceResponse.model_validate(service)
    if service.category_id:
        cat = db.get(ServiceCategory, service.category_id)
        res.category_name = cat.category_name if cat else None
    return res


@router.delete(
    "/services/{service_id}",
    response_model=MessageResponse,
    tags=["Business Services"],
    summary="Deactivate Business Service",
    description="Soft-deactivate a business service (restricted to Business Admin).",
)
def delete_business_service(
    service_id: int,
    business: Business = Depends(get_current_business),
    current_admin: User = Depends(require_business_admin),
    db: Session = Depends(get_db_session),
) -> MessageResponse:
    """Soft deactivation of service offering."""
    service = (
        db.query(BusinessService)
        .filter(BusinessService.id == service_id, BusinessService.business_id == business.id)
        .first()
    )
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business service not found in your business organization.",
        )

    service.is_active = False
    db.commit()

    logger.info("Admin ID %d soft-deactivated service ID %d in Business ID %d", current_admin.id, service.id, business.id)
    return MessageResponse(message="Business service successfully deactivated.")
