"""Shared FastAPI dependencies for route handlers.

Provides common dependencies like authenticated user extraction,
tenant context, and role-based access control.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import jwt
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import AuthenticationError, InsufficientRoleError, TokenExpiredError
from app.core.security import decode_access_token


@dataclass
class CurrentUser:
    """Authenticated user context available in route handlers."""
    id: UUID
    tenant_id: UUID
    email: str
    role: str
    display_name: str | None = None


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """Extract and validate the current user from JWT.

    Args:
        request: FastAPI request object.
        db: Database session.

    Returns:
        CurrentUser with user identity and tenant context.

    Raises:
        AuthenticationError: If token is missing or invalid.
        TokenExpiredError: If token has expired.
    """
    settings = get_settings()

    # Dev bypass
    if settings.disable_auth and not settings.is_production:
        return CurrentUser(
            id=UUID("00000000-0000-0000-0000-000000000000"),
            tenant_id=UUID("00000000-0000-0000-0000-000000000000"),
            email="dev@daena.local",
            role="FOUNDER",
            display_name="Dev User",
        )

    # Extract token: prefer X-Daena-Auth (for Cloud Run where GCP identity
    # token occupies Authorization), fall back to standard Authorization header.
    auth_header = (
        request.headers.get("X-Daena-Auth")
        or request.headers.get("Authorization")
    )
    if not auth_header or not auth_header.startswith("Bearer "):
        raise AuthenticationError("Missing or invalid Authorization header")

    token = auth_header.split(" ", 1)[1]

    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError("Access token has expired") from exc
    except jwt.InvalidTokenError as exc:
        # If Authorization held a GCP identity token (not a Daena JWT),
        # the decode fails. Check if X-Daena-Auth was already tried.
        if request.headers.get("X-Daena-Auth"):
            raise AuthenticationError("Invalid access token") from exc
        raise AuthenticationError(
            "Invalid access token. When behind Cloud Run IAM, "
            "send Daena JWT via X-Daena-Auth header."
        ) from exc

    return CurrentUser(
        id=UUID(payload["sub"]),
        tenant_id=UUID(payload["tenant_id"]),
        email=payload.get("email", ""),
        role=payload["role"],
    )


def require_role(min_role: str):
    """Dependency factory: require minimum RBAC role.

    Usage:
        @router.get("/admin", dependencies=[Depends(require_role("ADMIN"))])
    """
    role_levels = {
        "AUDITOR": 1, "VIEWER": 2, "OPERATOR": 3,
        "MANAGER": 4, "ADMIN": 5, "FOUNDER": 6,
    }

    async def check_role(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        user_level = role_levels.get(user.role, 0)
        required_level = role_levels.get(min_role, 999)

        if user_level < required_level:
            raise InsufficientRoleError(
                f"Role '{user.role}' insufficient. Minimum required: '{min_role}'"
            )
        return user

    return check_role
