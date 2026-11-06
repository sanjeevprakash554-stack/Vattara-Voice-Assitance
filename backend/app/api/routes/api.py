"""Central API Router for v1 endpoints.

All functional domain routes (auth, businesses, appointments, calls, etc.)
are aggregated here under the /api/v1 prefix.
"""

from fastapi import APIRouter
from app.api.routes import health

api_router = APIRouter()

# Health endpoints mounted at /api/v1/health
api_router.include_router(health.router, prefix="/health", tags=["Health"])
