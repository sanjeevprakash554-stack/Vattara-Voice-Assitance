"""Central API Router for v1 endpoints.

All functional domain routes (auth, dashboard, assistant, calls, appointments,
customers, reminders, reports, plivo, integrations) are aggregated here under the /api/v1 prefix.
"""

from fastapi import APIRouter
from app.api.routes import (
    appointments,
    assistant,
    auth,
    availability,
    calls,
    customers,
    dashboard,
    health,
    integrations,
    plivo,
    reminders,
    reports,
    staff,
    subscriptions,
    super_admin,
)

api_router = APIRouter()

# Register domain routers
api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(assistant.router, prefix="/assistant", tags=["AI Assistant"])
api_router.include_router(availability.router, prefix="/availability", tags=["Availability Management"])
api_router.include_router(calls.router, prefix="/calls", tags=["Calls"])
api_router.include_router(appointments.router, prefix="/appointments", tags=["Appointments"])
api_router.include_router(customers.router, prefix="/customers", tags=["Customers"])
api_router.include_router(reminders.router, prefix="/reminders", tags=["Reminders"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports & Analytics"])
api_router.include_router(plivo.router, prefix="/plivo", tags=["Plivo Programmable Voice"])
api_router.include_router(plivo.router, prefix="/integrations/plivo", tags=["Plivo Programmable Voice"])
api_router.include_router(integrations.router, prefix="/integrations", tags=["Integrations"])
api_router.include_router(staff.router, prefix="/staff", tags=["Staff Management"])
api_router.include_router(subscriptions.router, prefix="/subscriptions", tags=["Subscriptions & Billing"])
api_router.include_router(super_admin.router, prefix="/super-admin", tags=["Super Admin Platform"])
