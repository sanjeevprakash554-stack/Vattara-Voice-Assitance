"""Pydantic schemas for authentication, registration, token generation, and password change."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
from app.schemas.business import BusinessResponse
from app.schemas.user import UserProfileResponse, UserResponse


class BusinessRegisterRequest(BaseModel):
    """Payload for multi-tenant business registration with initial admin account."""

    # Business Information
    business_name: str = Field(..., min_length=2, max_length=255, description="Legal or trading business name")
    business_type: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Industry vertical (hospital, hotel, salon, automobile, real_estate, etc.)",
    )
    business_email: EmailStr = Field(..., description="Unique organization contact email")
    business_phone_number: str | None = Field(default=None, max_length=50)
    business_address: str | None = Field(default=None, description="Physical address or headquarters")

    # Admin Account Information
    admin_full_name: str = Field(..., min_length=2, max_length=255, description="Full name of the business administrator")
    admin_email: EmailStr = Field(..., description="Login email for the business administrator")
    admin_password: str = Field(..., min_length=8, description="Strong password meeting complexity policy")
    confirm_password: str = Field(..., min_length=8, description="Password confirmation")

    @model_validator(mode="after")
    def verify_password_match(self) -> "BusinessRegisterRequest":
        if self.admin_password != self.confirm_password:
            raise ValueError("Admin password and confirm password do not match.")
        return self


class BusinessRegisterResponse(BaseModel):
    """Response returned upon successful business and admin registration."""

    business: BusinessResponse
    admin_user: UserResponse
    message: str = "Business and administrator account registered successfully."


class LoginRequest(BaseModel):
    """JSON login request payload."""

    email: EmailStr = Field(..., description="Registered user email")
    password: str = Field(..., description="User password")


class TokenResponse(BaseModel):
    """OAuth2-compatible Bearer token response payload."""

    access_token: str = Field(..., description="Cryptographically signed JWT access token")
    token_type: str = Field(default="bearer", description="Bearer token type")
    expires_in: int = Field(..., description="Token lifespan in seconds")
    user: UserProfileResponse = Field(..., description="Authenticated user profile")


class ChangePasswordRequest(BaseModel):
    """Payload for securely changing user password."""

    current_password: str = Field(..., description="Current password for verification")
    new_password: str = Field(..., min_length=8, description="New strong password")
    confirm_new_password: str = Field(..., min_length=8, description="New password confirmation")

    @model_validator(mode="after")
    def verify_new_password_match(self) -> "ChangePasswordRequest":
        if self.new_password != self.confirm_new_password:
            raise ValueError("New password and confirm password do not match.")
        return self


class MessageResponse(BaseModel):
    """Generic status and confirmation response."""

    message: str
