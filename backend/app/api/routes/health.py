"""Health check routes for service monitoring and infrastructure probes."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.core.config import settings
from app.core.logging import get_logger
from app.database.connection import engine, ping_database
from app.schemas.health import DatabaseHealthResponse, HealthResponse

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
    """Return backend operational status."""
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
    responses={
        200: {
            "model": DatabaseHealthResponse,
            "description": "Database connection is healthy and responsive.",
        },
        503: {
            "model": DatabaseHealthResponse,
            "description": "Database connection failed or unreachable.",
        },
    },
    summary="Database Health Status",
    description="Execute a test query against PostgreSQL to verify connectivity.",
)
def get_database_health(
    db: Session = Depends(get_db_session),
) -> DatabaseHealthResponse | JSONResponse:
    """Verify live database connectivity by running a lightweight query."""
    now = datetime.now(timezone.utc)
    dialect_name = engine.dialect.name

    try:
        ping_database(db)
        return DatabaseHealthResponse(
            status="healthy",
            database="connected",
            dialect=dialect_name,
            details="Database ping query succeeded (SELECT 1).",
            timestamp=now,
            error=None,
        )
    except Exception as exc:
        logger.error("Database health check failed: %s", exc, exc_info=True)
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
