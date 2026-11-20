"""Third-party platform telephony integrations and carrier settings."""

import time
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db_session, require_roles
from app.core.config import settings
from app.core.logging import get_logger
from app.models.integration import BusinessIntegration
from app.models.user import User
from app.schemas.integration import (
    IntegrationSettingsResponse,
    TestConnectionRequest,
    TestConnectionResponse,
    UpdateIntegrationRequest,
)
from app.services.plivo_service import PlivoService, get_plivo_service

logger = get_logger(__name__)
router = APIRouter()


def mask_secret(secret: str | None) -> str | None:
    """Mask sensitive tokens and keys, exposing only first 4 and last 4 characters."""
    if not secret:
        return None
    s = secret.strip()
    if len(s) <= 8:
        return "••••" + s[-2:]
    return s[:4] + "••••••••" + s[-4:]


def get_or_create_integration(db: Session, business_id: str) -> BusinessIntegration:
    """Resolve or initialize tenant telephony integration record."""
    integration = db.scalar(
        select(BusinessIntegration).where(BusinessIntegration.business_id == business_id)
    )
    if not integration:
        integration = BusinessIntegration(
            business_id=business_id,
            primary_provider="plivo",
            plivo_phone_number=settings.PLIVO_PHONE_NUMBER or "+918040008888",
            is_plivo_verified=bool(settings.is_plivo_configured),
        )
        db.add(integration)
        db.commit()
        db.refresh(integration)
    return integration


@router.get("/settings", response_model=IntegrationSettingsResponse)
def get_integration_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> IntegrationSettingsResponse:
    """Retrieve Plivo telephony gateway configurations and verified connection status with masked tokens."""
    integration = get_or_create_integration(db, current_user.business_id)

    raw_plivo_id = integration.plivo_auth_id or (settings.PLIVO_AUTH_ID if settings.is_plivo_configured else None)
    webhook_path = "/api/v1/plivo/incoming"
    full_webhook_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}{webhook_path}" if settings.PUBLIC_BASE_URL else webhook_path

    return IntegrationSettingsResponse(
        business_id=current_user.business_id,
        primary_provider="plivo",
        plivo_configured=bool(settings.is_plivo_configured or integration.plivo_auth_id),
        plivo_phone_number=integration.plivo_phone_number or settings.PLIVO_PHONE_NUMBER,
        plivo_auth_id_masked=mask_secret(raw_plivo_id),
        is_plivo_verified=integration.is_plivo_verified or bool(settings.is_plivo_configured),
        inbound_webhook_url=full_webhook_url,
    )


@router.put("/settings", response_model=IntegrationSettingsResponse)
def update_integration_settings(
    payload: UpdateIntegrationRequest,
    current_user: User = Depends(require_roles(["admin", "manager"])),
    db: Session = Depends(get_db_session),
) -> IntegrationSettingsResponse:
    """Update Plivo telephony provider credentials and phone number for the authenticated tenant."""
    integration = get_or_create_integration(db, current_user.business_id)

    integration.primary_provider = "plivo"
    if payload.plivo_auth_id is not None:
        integration.plivo_auth_id = payload.plivo_auth_id.strip()
    if payload.plivo_phone_number is not None:
        integration.plivo_phone_number = payload.plivo_phone_number.strip()

    db.commit()
    db.refresh(integration)
    return get_integration_settings(current_user=current_user, db=db)


@router.post("/test-connection", response_model=TestConnectionResponse)
def test_telephony_connection(
    payload: TestConnectionRequest,
    current_user: User = Depends(require_roles(["admin", "manager"])),
    plivo_service: PlivoService = Depends(get_plivo_service),
) -> TestConnectionResponse:
    """Perform live health check on carrier telephony provider without exposing secret tokens."""
    provider = payload.provider.lower().strip()

    if provider == "plivo":
        start_time = time.perf_counter()
        result = plivo_service.check_connection()
        latency_ms = max(1, int((time.perf_counter() - start_time) * 1000))

        is_connected = result.get("status") == "connected"
        return TestConnectionResponse(
            provider="plivo",
            is_connected=is_connected,
            status="connected" if is_connected else "failed",
            message=result.get("message") or ("Plivo API connected" if is_connected else "Plivo connection failed"),
            latency_ms=latency_ms if is_connected else 0,
        )

    return TestConnectionResponse(
        provider=provider,
        is_connected=False,
        status="failed",
        message=f"Unsupported telephony carrier '{provider}'. Plivo is the exclusive supported provider.",
        latency_ms=0,
    )
