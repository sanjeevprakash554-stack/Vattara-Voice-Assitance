"""Health check routes for service monitoring and infrastructure probes."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.core.config import settings
from app.core.logging import get_logger
from app.database.connection import engine, ping_database
from app.schemas.health import (
    DatabaseHealthResponse,
    HealthResponse,
    PlivoHealthResponse,
)
from app.services.plivo_service import PlivoService, get_plivo_service

logger = get_logger(__name__)
router = APIRouter()


@router.get(
    "",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Backend Health Status",
    description="Check whether the backend service is running and responsive.",
)
def get_health() -> HealthResponse:
    """Return backend liveness and basic runtime metadata."""
    return HealthResponse(
        status="healthy",
        app_name=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc),
    )


@router.get(
    "/live",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Kubernetes Liveness Probe",
    description="Quick check confirming the FastAPI process is alive and receiving HTTP traffic.",
)
def get_liveness() -> HealthResponse:
    """Lightweight probe verifying the event loop is active."""
    return HealthResponse(
        status="healthy",
        app_name=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc),
    )


@router.get(
    "/database",
    response_model=DatabaseHealthResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "model": DatabaseHealthResponse,
            "description": "Database connection verified successfully.",
        },
        503: {
            "model": DatabaseHealthResponse,
            "description": "Database connection failed or timed out.",
        },
    },
    summary="Database Connectivity Health Check",
    description="Actively ping the configured PostgreSQL/SQLite database with 'SELECT 1'.",
)
def get_database_health(
    db: Session = Depends(get_db_session),
) -> DatabaseHealthResponse | JSONResponse:
    """Verify database connection pool and execute active probe query."""
    now = datetime.now(timezone.utc)
    dialect_name = engine.dialect.name

    try:
        ping_database(db)
        return DatabaseHealthResponse(
            status="healthy",
            database="connected",
            dialect=dialect_name,
            details=f"Successfully pinged {dialect_name} database.",
            timestamp=now,
            error=None,
        )
    except Exception as exc:
        logger.error("Database health check failed: %s", exc)
        failure_payload = DatabaseHealthResponse(
            status="unhealthy",
            database="disconnected",
            dialect=dialect_name,
            details="Database ping query failed.",
            timestamp=now,
            error=str(exc),
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=failure_payload.model_dump(mode="json"),
        )


@router.get(
    "/plivo",
    response_model=PlivoHealthResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "model": PlivoHealthResponse,
            "description": "Plivo configuration and connectivity status retrieved.",
        },
        503: {
            "model": PlivoHealthResponse,
            "description": "Plivo credentials configured but connection failed or invalid.",
        },
    },
    summary="Plivo Health & Configuration Status",
    description="Verify Plivo credentials, Auth ID authentication, and configured phone numbers.",
)
def get_plivo_health(
    plivo_service: PlivoService = Depends(get_plivo_service),
) -> PlivoHealthResponse | JSONResponse:
    """Verify Plivo telephony credentials and API connectivity."""
    result = plivo_service.check_connection()
    now = datetime.now(timezone.utc)

    response_payload = PlivoHealthResponse(
        status=result["status"],
        configured=result["configured"],
        auth_id_masked=result.get("auth_id_masked"),
        account_name=result.get("account_name"),
        phone_number=result.get("phone_number"),
        public_base_url=settings.PUBLIC_BASE_URL,
        details=result.get("message") or "Plivo status checked.",
        timestamp=now,
        error=result.get("error"),
    )

    if result["status"] == "failed":
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=response_payload.model_dump(mode="json"),
        )

    return response_payload
