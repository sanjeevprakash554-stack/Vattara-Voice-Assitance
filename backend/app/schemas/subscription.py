"""Pydantic schemas for SaaS Subscription, Plans, and Invoices."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class PlanFeature(BaseModel):
    name: str
    included: bool


class SubscriptionPlan(BaseModel):
    id: str
    name: str
    tagline: str
    monthly_price: float
    annual_price: float
    monthly_minutes: int
    max_assistants: int
    max_staff: int
    is_popular: bool = False
    features: list[str]


class SubscriptionResponse(BaseModel):
    id: str
    business_id: str
    plan_name: str
    billing_cycle: str
    status: str
    trial_ends_at: datetime | None = None
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    monthly_call_minutes_limit: int
    used_call_minutes: int
    max_assistants: int
    max_staff: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChangePlanRequest(BaseModel):
    plan_name: str = Field(..., description="starter, professional, enterprise")
    billing_cycle: str = Field(default="monthly", description="monthly or annual")


class ConfirmPaymentRequest(BaseModel):
    payment_id: str = Field(..., description="Payment gateway transaction ID, e.g. pay_xyz or manual reference")
    payment_method: str = Field(default="gateway", description="card, upi, netbanking, or manual")


class InvoiceResponse(BaseModel):
    id: str
    business_id: str
    subscription_id: str
    invoice_number: str
    amount: float
    currency: str
    status: str
    billing_date: datetime
    paid_at: datetime | None = None
    pdf_url: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
