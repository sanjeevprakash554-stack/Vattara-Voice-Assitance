"""AI Voice Assistant Configuration, Services, and FAQs routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db_session
from app.models.assistant import AssistantConfig, FAQ, Service
from app.models.user import User
from app.schemas.assistant import (
    AssistantConfigResponse,
    AssistantConfigUpdate,
    FAQCreate,
    FAQResponse,
    FAQUpdate,
    ServiceCreate,
    ServiceResponse,
    ServiceUpdate,
    ToggleAssistantStatus,
)

router = APIRouter()


# ------------------------------------------------------------------------------
# Assistant Configuration
# ------------------------------------------------------------------------------
@router.get("", response_model=AssistantConfigResponse)
def get_assistant_config(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> AssistantConfigResponse:
    """Retrieve the AI voice assistant configuration for current business."""
    config = db.scalar(
        select(AssistantConfig).where(AssistantConfig.business_id == current_user.business_id)
    )
    if not config:
        # Create default config if missing
        config = AssistantConfig(
            business_id=current_user.business_id,
            assistant_name="Vattara AI",
            language="en-US",
            voice="alloy",
            is_active=True,
        )
        db.add(config)
        db.commit()
        db.refresh(config)

    return AssistantConfigResponse.model_validate(config)


@router.put("", response_model=AssistantConfigResponse)
def update_assistant_config(
    payload: AssistantConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> AssistantConfigResponse:
    """Update AI Voice Assistant settings, persona, instructions, and hours."""
    config = db.scalar(
        select(AssistantConfig).where(AssistantConfig.business_id == current_user.business_id)
    )
    if not config:
        config = AssistantConfig(business_id=current_user.business_id)
        db.add(config)

    config.assistant_name = payload.assistant_name
    config.language = payload.language
    config.voice = payload.voice
    config.system_prompt = payload.system_prompt
    config.business_info = payload.business_info
    config.working_hours = payload.working_hours
    config.is_active = payload.is_active

    db.commit()
    db.refresh(config)
    return AssistantConfigResponse.model_validate(config)


@router.post("/toggle", response_model=AssistantConfigResponse)
def toggle_assistant(
    payload: ToggleAssistantStatus,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> AssistantConfigResponse:
    """Activate or deactivate the AI receptionist."""
    config = db.scalar(
        select(AssistantConfig).where(AssistantConfig.business_id == current_user.business_id)
    )
    if not config:
        config = AssistantConfig(business_id=current_user.business_id)
        db.add(config)

    config.is_active = payload.is_active
    db.commit()
    db.refresh(config)
    return AssistantConfigResponse.model_validate(config)


# ------------------------------------------------------------------------------
# Services Catalog
# ------------------------------------------------------------------------------
@router.get("/services", response_model=list[ServiceResponse])
def list_services(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[ServiceResponse]:
    """List all business services."""
    services = db.scalars(
        select(Service)
        .where(Service.business_id == current_user.business_id)
        .order_by(Service.name.asc())
    ).all()
    return [ServiceResponse.model_validate(s) for s in services]


@router.post("/services", response_model=ServiceResponse, status_code=status.HTTP_201_CREATED)
def create_service(
    payload: ServiceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> ServiceResponse:
    """Create a new service offering."""
    service = Service(
        business_id=current_user.business_id,
        name=payload.name,
        description=payload.description,
        duration_minutes=payload.duration_minutes,
        price=payload.price,
        is_active=payload.is_active,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return ServiceResponse.model_validate(service)


@router.put("/services/{service_id}", response_model=ServiceResponse)
def update_service(
    service_id: str,
    payload: ServiceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> ServiceResponse:
    """Update an existing service offering."""
    service = db.scalar(
        select(Service).where(
            Service.id == service_id, Service.business_id == current_user.business_id
        )
    )
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found.")

    if payload.name is not None:
        service.name = payload.name
    if payload.description is not None:
        service.description = payload.description
    if payload.duration_minutes is not None:
        service.duration_minutes = payload.duration_minutes
    if payload.price is not None:
        service.price = payload.price
    if payload.is_active is not None:
        service.is_active = payload.is_active

    db.commit()
    db.refresh(service)
    return ServiceResponse.model_validate(service)


@router.delete("/services/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service(
    service_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> None:
    """Delete a service offering."""
    service = db.scalar(
        select(Service).where(
            Service.id == service_id, Service.business_id == current_user.business_id
        )
    )
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found.")

    db.delete(service)
    db.commit()


# ------------------------------------------------------------------------------
# FAQs & Knowledge Base
# ------------------------------------------------------------------------------
@router.get("/faqs", response_model=list[FAQResponse])
def list_faqs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[FAQResponse]:
    """List all FAQs for the AI receptionist."""
    faqs = db.scalars(
        select(FAQ)
        .where(FAQ.business_id == current_user.business_id)
        .order_by(FAQ.category.asc())
    ).all()
    return [FAQResponse.model_validate(f) for f in faqs]


@router.post("/faqs", response_model=FAQResponse, status_code=status.HTTP_201_CREATED)
def create_faq(
    payload: FAQCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> FAQResponse:
    """Create a new FAQ entry."""
    faq = FAQ(
        business_id=current_user.business_id,
        category=payload.category,
        question=payload.question,
        answer=payload.answer,
        is_active=payload.is_active,
    )
    db.add(faq)
    db.commit()
    db.refresh(faq)
    return FAQResponse.model_validate(faq)


@router.put("/faqs/{faq_id}", response_model=FAQResponse)
def update_faq(
    faq_id: str,
    payload: FAQUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> FAQResponse:
    """Update an existing FAQ entry."""
    faq = db.scalar(
        select(FAQ).where(FAQ.id == faq_id, FAQ.business_id == current_user.business_id)
    )
    if not faq:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ not found.")

    if payload.category is not None:
        faq.category = payload.category
    if payload.question is not None:
        faq.question = payload.question
    if payload.answer is not None:
        faq.answer = payload.answer
    if payload.is_active is not None:
        faq.is_active = payload.is_active

    db.commit()
    db.refresh(faq)
    return FAQResponse.model_validate(faq)


@router.delete("/faqs/{faq_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_faq(
    faq_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> None:
    """Delete an FAQ entry."""
    faq = db.scalar(
        select(FAQ).where(FAQ.id == faq_id, FAQ.business_id == current_user.business_id)
    )
    if not faq:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ not found.")

    db.delete(faq)
    db.commit()

