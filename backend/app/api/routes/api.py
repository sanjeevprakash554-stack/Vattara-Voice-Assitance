"""Central API Router for v1 endpoints.

Aggregates all functional domain routes under the /api/v1 prefix with clean Swagger categorization.
"""

from fastapi import APIRouter
from app.api.routes import admin, auth, health, users

api_router = APIRouter()

# 1. Authentication & Profile Routes
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# 2. Staff & User Management Routes
api_router.include_router(users.router, prefix="/users", tags=["Users"])

# 3. Super Admin Platform Management Routes
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])

# 4. System Health Check Routes
api_router.include_router(health.router, prefix="/health", tags=["Health"])
