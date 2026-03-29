"""Authentication request/response schemas.

Extracted from app/api/v1/auth.py for reuse across services and tests.
Includes password policy validation and typed response models.
"""

from __future__ import annotations

import re
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator

from app.schemas._base import DaenaSchema

# --- Requests ---


class RegisterRequest(BaseModel):
    """User registration payload."""

    email: EmailStr
    password: str
    confirm_password: str | None = None
    display_name: str
    tenant_name: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Enforce password policy: min 12 chars, 1 upper, 1 number, 1 special."""
        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character")
        return v

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str | None, info: object) -> str | None:
        """When provided, confirm password must match password."""
        if v is None:
            return v
        data = getattr(info, "data", {})
        if "password" in data and v != data["password"]:
            raise ValueError("Passwords do not match")
        return v


class LoginRequest(BaseModel):
    """Login payload."""

    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    """Forgot password payload — accepts email, always returns success."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Reset password payload — token + new password + confirmation."""

    token: str
    password: str
    confirm_password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Enforce same password policy as registration."""
        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError(
                "Password must contain at least one uppercase letter"
            )
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError(
                "Password must contain at least one special character"
            )
        return v

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info: object) -> str:
        """Confirm password must match password."""
        # info.data contains previously validated fields
        data = getattr(info, "data", {})
        if "password" in data and v != data["password"]:
            raise ValueError("Passwords do not match")
        return v


# --- Responses ---


class UserResponse(DaenaSchema):
    """User data returned in auth responses."""

    user_id: UUID
    email: str
    display_name: str | None = None
    role: str
    tenant_id: UUID
    created_at: str | None = None


class TokenData(DaenaSchema):
    """JWT token payload returned on login."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class RegisterResponse(DaenaSchema):
    """Successful registration response data."""

    user_id: UUID
    email: str
    display_name: str | None = None
    role: str
    tenant_id: UUID
    created_at: str | None = None
