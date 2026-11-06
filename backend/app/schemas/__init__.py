"""Pydantic schemas package for request/response serialization and validation."""

from app.schemas.auth import (
    BusinessRegisterRequest,
    BusinessRegisterResponse,
    ChangePasswordRequest,
    LoginRequest,
    MessageResponse,
    TokenResponse,
)
from app.schemas.business import (
    BusinessDetailResponse,
    BusinessProfileResponse,
    BusinessProfileUpdateRequest,
    BusinessResponse,
    BusinessStatusUpdateRequest,
)
from app.schemas.customer import (
    CustomerAppointmentHistoryItem,
    CustomerCallHistoryItem,
    CustomerCreateRequest,
    CustomerHistoryResponse,
    CustomerResponse,
    CustomerUpdateRequest,
)
from app.schemas.health import (
    DatabaseHealthResponse,
    HealthResponse,
    RootResponse,
)
from app.schemas.service import (
    BusinessServiceCreateRequest,
    BusinessServiceResponse,
    BusinessServiceUpdateRequest,
    ServiceCategoryCreateRequest,
    ServiceCategoryResponse,
    ServiceCategoryUpdateRequest,
)
from app.schemas.user import (
    UserCreateRequest,
    UserProfileResponse,
    UserProfileUpdateRequest,
    UserResponse,
    UserUpdateRequest,
)
from app.schemas.working_hours import (
    WorkingHoursItem,
    WorkingHoursResponse,
    WorkingHoursUpdateRequest,
)

__all__ = [
    "BusinessDetailResponse",
    "BusinessProfileResponse",
    "BusinessProfileUpdateRequest",
    "BusinessRegisterRequest",
    "BusinessRegisterResponse",
    "BusinessResponse",
    "BusinessServiceCreateRequest",
    "BusinessServiceResponse",
    "BusinessServiceUpdateRequest",
    "BusinessStatusUpdateRequest",
    "ChangePasswordRequest",
    "CustomerAppointmentHistoryItem",
    "CustomerCallHistoryItem",
    "CustomerCreateRequest",
    "CustomerHistoryResponse",
    "CustomerResponse",
    "CustomerUpdateRequest",
    "DatabaseHealthResponse",
    "HealthResponse",
    "LoginRequest",
    "MessageResponse",
    "RootResponse",
    "ServiceCategoryCreateRequest",
    "ServiceCategoryResponse",
    "ServiceCategoryUpdateRequest",
    "TokenResponse",
    "UserCreateRequest",
    "UserProfileResponse",
    "UserProfileUpdateRequest",
    "UserResponse",
    "UserUpdateRequest",
    "WorkingHoursItem",
    "WorkingHoursResponse",
    "WorkingHoursUpdateRequest",
]
