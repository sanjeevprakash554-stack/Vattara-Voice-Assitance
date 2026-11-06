"""Pydantic schemas package exports."""

from app.schemas.health import (
    DatabaseHealthResponse,
    HealthResponse,
    RootResponse,
)
from app.schemas.auth import (
    BusinessResponse,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterBusinessRequest,
    ResetPasswordRequest,
    Token,
    UpdateProfileRequest,
    UserProfileResponse,
    UserResponse,
)
from app.schemas.assistant import (
    AssistantConfigResponse,
    AssistantConfigUpdate,
    FAQCreate,
    FAQResponse,
    FAQUpdate,
    ServiceCreate,
    ServiceResponse,
    ServiceUpdate,
    ToggleAssistantStatus,
)
from app.schemas.customer import (
    CustomerCreate,
    CustomerDetailResponse,
    CustomerResponse,
    CustomerUpdate,
)
from app.schemas.call import (
    CallCreate,
    CallResponse,
    CallSimulateRequest,
)
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentUpdate,
)
from app.schemas.reminder import (
    ReminderCreate,
    ReminderResponse,
    ReminderUpdate,
)
from app.schemas.dashboard import (
    ActivityItem,
    AnalyticsOverview,
    AppointmentStatusDistribution,
    CallDurationReport,
    CallTrendPoint,
    DashboardStats,
)

__all__ = [
    "DatabaseHealthResponse",
    "HealthResponse",
    "RootResponse",
    "BusinessResponse",
    "ForgotPasswordRequest",
    "LoginRequest",
    "RegisterBusinessRequest",
    "ResetPasswordRequest",
    "Token",
    "UpdateProfileRequest",
    "UserProfileResponse",
    "UserResponse",
    "AssistantConfigResponse",
    "AssistantConfigUpdate",
    "FAQCreate",
    "FAQResponse",
    "FAQUpdate",
    "ServiceCreate",
    "ServiceResponse",
    "ServiceUpdate",
    "ToggleAssistantStatus",
    "CustomerCreate",
    "CustomerDetailResponse",
    "CustomerResponse",
    "CustomerUpdate",
    "CallCreate",
    "CallResponse",
    "CallSimulateRequest",
    "AppointmentCreate",
    "AppointmentResponse",
    "AppointmentUpdate",
    "ReminderCreate",
    "ReminderResponse",
    "ReminderUpdate",
    "ActivityItem",
    "AnalyticsOverview",
    "AppointmentStatusDistribution",
    "CallDurationReport",
    "CallTrendPoint",
    "DashboardStats",
]
