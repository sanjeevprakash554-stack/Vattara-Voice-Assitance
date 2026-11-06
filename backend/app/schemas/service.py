"""Pydantic schemas for Service Categories and Business Services."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ServiceCategoryCreateRequest(BaseModel):
    """Payload to create a service category."""

    category_name: str = Field(..., min_length=1, max_length=255, description="Category name (e.g. Dentistry, Haircut, Diagnostics)")
    description: str | None = Field(default=None, description="Detailed category summary")


class ServiceCategoryUpdateRequest(BaseModel):
    """Payload to update an existing service category."""

    category_name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    is_active: bool | None = None


class ServiceCategoryResponse(BaseModel):
    """Public representation of a ServiceCategory."""

    id: int
    business_id: int
    category_name: str
    description: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BusinessServiceCreateRequest(BaseModel):
    """Payload to create a commercial service offered by the business."""

    category_id: int | None = Field(default=None, description="Optional foreign key to a ServiceCategory")
    service_name: str = Field(..., min_length=1, max_length=255, description="Commercial name of the service")
    description: str | None = None
    duration_minutes: int = Field(..., gt=0, description="Duration in minutes (must be > 0)")
    price: float = Field(..., ge=0, description="Price of the service (must be >= 0)")
    currency: str = Field(default="USD", min_length=1, max_length=10, description="Currency code (USD, EUR, INR, etc.)")


class BusinessServiceUpdateRequest(BaseModel):
    """Payload to update an existing service."""

    category_id: int | None = None
    service_name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    price: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=1, max_length=10)
    is_active: bool | None = None


class BusinessServiceResponse(BaseModel):
    """Public representation of a BusinessService."""

    id: int
    business_id: int
    category_id: int | None = None
    category_name: str | None = None
    service_name: str
    description: str | None = None
    duration_minutes: int
    price: float
    currency: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
