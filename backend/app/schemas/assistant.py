"""Pydantic schemas for AI Assistant configuration, Services, and FAQs."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class AssistantConfigBase(BaseModel):
    """Base schema for AI Voice Assistant configuration."""

    assistant_name: str = Field(default="Vattara AI", min_length=2, max_length=100)
    language: str = Field(default="en-US")
    voice: str = Field(default="alloy")
    system_prompt: str | None = None
    business_info: str | None = None
    working_hours: str | None = None
    is_active: bool = True


class AssistantConfigUpdate(AssistantConfigBase):
    """Schema for updating assistant configuration."""

    pass


class AssistantConfigResponse(AssistantConfigBase):
    """Schema for returning assistant configuration."""

    id: str
    business_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ToggleAssistantStatus(BaseModel):
    """Schema for activating or deactivating assistant."""

    is_active: bool


# Service Schemas
class ServiceCreate(BaseModel):
    """Schema to create a business service."""

    name: str = Field(..., min_length=2, max_length=150)
    description: str | None = None
    duration_minutes: int = Field(default=30, ge=5, le=480)
    price: float = Field(default=0.0, ge=0)
    is_active: bool = True


class ServiceUpdate(BaseModel):
    """Schema to update a business service."""

    name: str | None = None
    description: str | None = None
    duration_minutes: int | None = None
    price: float | None = None
    is_active: bool | None = None


class ServiceResponse(ServiceCreate):
    """Schema for returning a service."""

    id: str
    business_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# FAQ Schemas
class FAQCreate(BaseModel):
    """Schema to create an FAQ entry."""

    category: str = Field(default="General", max_length=100)
    question: str = Field(..., min_length=3)
    answer: str = Field(..., min_length=2)
    is_active: bool = True


class FAQUpdate(BaseModel):
    """Schema to update an FAQ entry."""

    category: str | None = None
    question: str | None = None
    answer: str | None = None
    is_active: bool | None = None


class FAQResponse(FAQCreate):
    """Schema for returning an FAQ."""

    id: str
    business_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

