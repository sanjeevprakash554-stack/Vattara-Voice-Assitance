"""FastAPI main application entry point.

Configures lifespan events, CORS middleware, centralized routing,
custom error handling, and root endpoints.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.api import api_router
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.schemas.health import RootResponse

# Initialize logging before creating app
setup_logging()
logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle events."""
    logger.info(
        "Starting %s v%s in '%s' environment",
        settings.PROJECT_NAME,
        settings.VERSION,
        settings.ENVIRONMENT,
    )
    # Mask password when logging database URI
    safe_db_target = settings.POSTGRES_SERVER
    logger.info("Configured database host: %s (port %s)", safe_db_target, settings.POSTGRES_PORT)
    yield
    logger.info("Shutting down %s...", settings.PROJECT_NAME)


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Multi-business SaaS platform providing AI-powered voice receptionist capabilities.",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ------------------------------------------------------------------------------
# CORS Middleware
# ------------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------------------
# Global Exception Handlers
# ------------------------------------------------------------------------------
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Standardized handler for HTTPExceptions."""
    logger.warning("HTTPException %d on %s: %s", exc.status_code, request.url.path, exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Standardized handler for schema validation failures."""
    logger.warning("Validation error on %s: %s", request.url.path, exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Request payload validation failed",
            "errors": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unhandled server errors to prevent leaking raw traces."""
    logger.error("Unhandled error processing %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error occurred. Please contact system support."},
    )


# ------------------------------------------------------------------------------
# Root Endpoint
# ------------------------------------------------------------------------------
@app.get(
    "/",
    response_model=RootResponse,
    status_code=status.HTTP_200_OK,
    tags=["Root"],
    summary="Root Endpoint",
    description="Return application name, semantic version, and health status.",
)
def root() -> RootResponse:
    """Root application entry point returning service identification and status."""
    return RootResponse(
        app_name=settings.PROJECT_NAME,
        version=settings.VERSION,
        status="online",
        environment=settings.ENVIRONMENT,
        docs_url="/docs",
    )


# ------------------------------------------------------------------------------
# Central API Router Registration
# ------------------------------------------------------------------------------
app.include_router(api_router, prefix=settings.API_V1_STR)
