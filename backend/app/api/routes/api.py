"""Central API Router for v1 endpoints.

All functional domain routes (auth, dashboard, assistant, calls, appointments,
customers, reminders, reports) are aggregated here under the /api/v1 prefix.
"""

from fastapi import APIRouter
from app.api.routes import (
    appointments,
    assistant,
    auth,
    calls,
    customers,
    dashboard,
    health,
    reminders,
    reports,
)

api_router = APIRouter()

# Register domain routers
api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(assistant.router, prefix="/assistant", tags=["AI Assistant"])
api_router.include_router(calls.router, prefix="/calls", tags=["Calls"])
api_router.include_router(appointments.router, prefix="/appointments", tags=["Appointments"])
api_router.include_router(customers.router, prefix="/customers", tags=["Customers"])
api_router.include_router(reminders.router, prefix="/reminders", tags=["Reminders"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports & Analytics"])
