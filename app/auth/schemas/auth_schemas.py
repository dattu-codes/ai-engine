from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from typing import Optional

class UserSignupRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    password: str = Field(..., min_length=6, max_length=100, description="Password must be at least 6 characters")
    role: Optional[str] = Field("user", description="Default user role")

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if value not in ("user", "admin"):
            raise ValueError("Role must be 'user' or 'admin'")
        return value


class UserLoginRequest(BaseModel):
    username: str = Field(...)
    password: str = Field(...)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 900  # 15 minutes in seconds


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class UserProfileResponse(BaseModel):
    username: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class ForgotPasswordRequest(BaseModel):
    username: str = Field(..., description="Username to trigger password reset")


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., description="Reset token received via email")
    new_password: str = Field(..., min_length=6, description="New password")


class VerifyEmailRequest(BaseModel):
    token: str = Field(..., description="Verification token received via email")
