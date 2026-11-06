"""Central API Router for v1 endpoints.

Aggregates all functional domain routes under the /api/v1 prefix with clean Swagger categorization.
"""

from fastapi import APIRouter
from app.api.routes import admin, auth, business, customers, health, users

api_router = APIRouter()

# 1. Authentication & Profile Routes
api_router.include_router(auth.router, prefix="/auth")

# 2. Business Profile, Working Hours, Categories & Services Routes
api_router.include_router(business.router, prefix="/business")

# 3. Customer Management & Customer Interaction History Routes
api_router.include_router(customers.router, prefix="/customers")

# 4. Staff & User Management Routes
api_router.include_router(users.router, prefix="/users", tags=["Users"])

# 5. Super Admin Platform Management Routes
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])

# 6. System Health Check Routes
api_router.include_router(health.router, prefix="/health", tags=["Health"])
