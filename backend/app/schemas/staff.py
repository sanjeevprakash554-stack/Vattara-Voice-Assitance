"""Pydantic schemas for Staff and Doctor Management."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class StaffMemberBase(BaseModel):
    full_name: str
    email: EmailStr
    role: str = Field(default="staff", description="doctor, manager, staff, receptionist")
    is_active: bool = True


class StaffMemberCreate(StaffMemberBase):
    password: str = Field(min_length=6, description="Initial login password")


class StaffMemberUpdate(BaseModel):
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None
    password: str | None = None


class StaffMemberResponse(StaffMemberBase):
    id: str
    business_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
