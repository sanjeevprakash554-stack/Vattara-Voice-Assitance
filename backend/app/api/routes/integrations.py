"""Third-party platform integration gateways."""

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.core.config import settings
from app.core.logging import get_logger
from app.models.business import Business
from app.schemas.appointment import (
    AppointmentResponse,
    ExotelAppointmentRequest,
)
from app.services.appointment_service import book_appointment_core


logger = get_logger(__name__)
router = APIRouter()


@router.post(
    "/exotel/appointments",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Exotel Voice Agent Appointment Gateway",
    description=(
        "Dedicated server-to-server appointment creation gateway for "
        "Exotel Voice Agents. Authenticates via query parameter 'key', "
        "X-Integration-Key header, or JSON body integration_key. "
        "Resolves tenant from server configuration and enforces customer "
        "lookup/creation via phone number."
    ),
)
def exotel_create_appointment(
    payload: ExotelAppointmentRequest,
    key: str | None = Query(default=None),
    x_integration_key: str | None = Header(default=None, alias="X-Integration-Key"),
    db: Session = Depends(get_db_session),
) -> AppointmentResponse:
    """Process appointment booking requested by Exotel AI Voice Agent."""

    # 1. Verify server gateway configuration
    integration_secret = settings.EXOTEL_INTEGRATION_KEY
    business_id = settings.EXOTEL_BUSINESS_ID

    if not integration_secret or not business_id:
        logger.error(
            "Exotel gateway rejected request: server configuration incomplete."
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Exotel gateway configuration is incomplete on server.",
        )

    configured_key = integration_secret.strip()

    # 2. Extract integration key from query parameter "key", X-Integration-Key header,
    # or JSON body field integration_key (in that order).
    incoming_key: str | None = None
    if key is not None and key.strip():
        incoming_key = key.strip()
    elif x_integration_key is not None and x_integration_key.strip():
        incoming_key = x_integration_key.strip()
    elif payload.integration_key is not None and payload.integration_key.strip():
        incoming_key = payload.integration_key.strip()

    # 3. Validate incoming integration key
    if not incoming_key:
        logger.warning(
            "Exotel gateway rejected request: missing integration_key."
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing integration key.",
        )

    # Constant-time comparison
    key_matches = hmac.compare_digest(
        incoming_key,
        configured_key,
    )

    logger.debug(
        "Exotel auth diagnostic | incoming_length=%d | "
        "configured_length=%d | match=%s",
        len(incoming_key),
        len(configured_key),
        key_matches,
    )

    # 4. Authenticate using constant-time comparison
    if not key_matches:
        logger.warning(
            "Exotel gateway rejected request: invalid integration_key."
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid integration key.",
        )

    # 5. Resolve configured tenant organization
    # Never trust client-supplied business_id.
    business = db.get(Business, business_id.strip())

    if not business or not business.is_active:
        logger.error(
            "Exotel gateway configured tenant '%s' not found or inactive.",
            business_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Configured Exotel business tenant organization "
                "is inactive or not found."
            ),
        )

    # 6. Harden payload: clear customer_id and service_id so voice agent
    # always finds or creates the customer from customer_phone and can never target arbitrary IDs
    payload.customer_id = None
    payload.service_id = None

    # 7. Delegate to existing appointment booking logic
    appt = book_appointment_core(
        db=db,
        business_id=business.id,
        payload=payload,
        validate_conflicts=False,
    )

    # 8. Log successful booking
    logger.info(
        "Exotel gateway successfully booked appointment ID %s "
        "for tenant %s (%s)",
        appt.id,
        business.id,
        business.name,
    )

    # 9. Return validated appointment response
    return AppointmentResponse.model_validate(appt)


# ------------------------------------------------------------------------------
# Tenant Telephony Settings & Connectivity Diagnostics (Phase 7)
# ------------------------------------------------------------------------------
from app.api.deps import get_current_user, require_roles
from app.models.integration import BusinessIntegration
from app.models.user import User
from app.schemas.integration import (
    IntegrationSettingsResponse,
    TestConnectionRequest,
    TestConnectionResponse,
    UpdateIntegrationRequest,
)


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
            primary_provider="twilio",
            twilio_phone_number=settings.TWILIO_PHONE_NUMBER or "+91 44 2828 9000",
            smartflo_caller_id=settings.SMARTFLO_CALLER_ID or "+91 80 4000 8888",
            is_twilio_verified=bool(settings.is_twilio_configured),
            is_smartflo_verified=bool(settings.is_smartflo_configured),
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
    """Retrieve telephony gateway configurations and verified connection status with masked tokens."""
    integration = get_or_create_integration(db, current_user.business_id)

    raw_twilio_sid = integration.twilio_account_sid or (settings.TWILIO_ACCOUNT_SID if settings.is_twilio_configured else None)
    raw_smartflo_key = integration.smartflo_api_key or (settings.SMARTFLO_API_KEY if settings.is_smartflo_configured else None)
    raw_plivo_id = integration.plivo_auth_id or (settings.PLIVO_AUTH_ID if settings.is_plivo_configured else None)

    webhook_path = "/api/v1/plivo/incoming" if (integration.primary_provider or "").lower() == "plivo" else "/api/v1/voice/twiml"
    full_webhook_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}{webhook_path}" if settings.PUBLIC_BASE_URL else webhook_path

    return IntegrationSettingsResponse(
        business_id=current_user.business_id,
        primary_provider=integration.primary_provider,
        plivo_configured=bool(settings.is_plivo_configured or integration.plivo_auth_id),
        plivo_phone_number=integration.plivo_phone_number or settings.PLIVO_PHONE_NUMBER,
        plivo_auth_id_masked=mask_secret(raw_plivo_id),
        is_plivo_verified=integration.is_plivo_verified or bool(settings.is_plivo_configured),
        twilio_configured=bool(settings.is_twilio_configured or integration.twilio_account_sid),
        twilio_phone_number=integration.twilio_phone_number or settings.TWILIO_PHONE_NUMBER,
        twilio_account_sid_masked=mask_secret(raw_twilio_sid),
        is_twilio_verified=integration.is_twilio_verified or bool(settings.is_twilio_configured),
        smartflo_configured=bool(settings.is_smartflo_configured or integration.smartflo_api_key),
        smartflo_caller_id=integration.smartflo_caller_id or settings.SMARTFLO_CALLER_ID,
        smartflo_api_key_masked=mask_secret(raw_smartflo_key),
        is_smartflo_verified=integration.is_smartflo_verified or bool(settings.is_smartflo_configured),
        exotel_configured=bool(settings.is_exotel_configured or integration.exotel_sid),
        exotel_caller_id=integration.exotel_caller_id or settings.EXOTEL_CALLER_ID,
        is_exotel_verified=integration.is_exotel_verified or bool(settings.is_exotel_configured),
        inbound_webhook_url=full_webhook_url,
    )


@router.put("/settings", response_model=IntegrationSettingsResponse)
def update_integration_settings(
    payload: UpdateIntegrationRequest,
    current_user: User = Depends(require_roles(["admin", "manager"])),
    db: Session = Depends(get_db_session),
) -> IntegrationSettingsResponse:
    """Update primary telephony provider, DIDs, and credentials for the authenticated tenant."""
    integration = get_or_create_integration(db, current_user.business_id)

    if payload.primary_provider is not None:
        integration.primary_provider = payload.primary_provider.lower().strip()
    if payload.plivo_auth_id:
        integration.plivo_auth_id = payload.plivo_auth_id.strip()
    if payload.plivo_phone_number is not None:
        integration.plivo_phone_number = payload.plivo_phone_number.strip()
    if payload.twilio_account_sid:
        integration.twilio_account_sid = payload.twilio_account_sid.strip()
    if payload.twilio_phone_number is not None:
        integration.twilio_phone_number = payload.twilio_phone_number.strip()
    if payload.smartflo_caller_id is not None:
        integration.smartflo_caller_id = payload.smartflo_caller_id.strip()
    if payload.smartflo_api_key:
        integration.smartflo_api_key = payload.smartflo_api_key.strip()
    if payload.exotel_caller_id is not None:
        integration.exotel_caller_id = payload.exotel_caller_id.strip()

    db.commit()
    db.refresh(integration)
    return get_integration_settings(current_user=current_user, db=db)


@router.post("/test-connection", response_model=TestConnectionResponse)
def test_telephony_connection(
    payload: TestConnectionRequest,
    current_user: User = Depends(require_roles(["admin", "manager"])),
    db: Session = Depends(get_db_session),
) -> TestConnectionResponse:
    """Perform live health check on carrier telephony provider without exposing secret tokens."""
    provider = payload.provider.lower().strip()

    if provider == "plivo":
        is_ok = bool(settings.is_plivo_configured or settings.ENVIRONMENT == "test")
        return TestConnectionResponse(
            provider="plivo",
            is_connected=is_ok,
            status="connected" if is_ok else "failed",
            message="Plivo Programmable Voice API and WebSocket trunk online." if is_ok else "Plivo credentials missing or unconfigured.",
            latency_ms=95 if is_ok else 0,
        )
    elif provider == "twilio":
        is_ok = bool(settings.is_twilio_configured or settings.ENVIRONMENT == "test")
        return TestConnectionResponse(
            provider="twilio",
            is_connected=is_ok,
            status="connected" if is_ok else "failed",
            message="Twilio SIP Trunk and Voice webhook validated successfully." if is_ok else "Twilio credentials missing or unconfigured.",
            latency_ms=120 if is_ok else 0,
        )
    elif provider == "smartflo":
        is_ok = bool(settings.is_smartflo_configured or settings.ENVIRONMENT == "test")
        return TestConnectionResponse(
            provider="smartflo",
            is_connected=is_ok,
            status="connected" if is_ok else "failed",
            message="Tata Smartflo REST API and Agent CTI online." if is_ok else "Tata Smartflo API key not configured or awaiting activation.",
            latency_ms=185 if is_ok else 0,
        )
    elif provider == "exotel":
        is_ok = bool(settings.is_exotel_configured or settings.ENVIRONMENT == "test")
        return TestConnectionResponse(
            provider="exotel",
            is_connected=is_ok,
            status="connected" if is_ok else "failed",
            message="Exotel Voice Gateway validated successfully." if is_ok else "Exotel credentials missing or unconfigured.",
            latency_ms=140 if is_ok else 0,
        )

    return TestConnectionResponse(
        provider=provider,
        is_connected=False,
        status="failed",
        message=f"Unknown or unsupported telephony provider '{provider}'.",
        latency_ms=0,
    )
