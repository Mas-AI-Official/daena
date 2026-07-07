"""Shared FastAPI dependencies for route handlers.

Provides common dependencies like authenticated user extraction,
tenant context, and role-based access control.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.constants import UserRole
from app.core.entitlements import (
    PLAN_RANK,
    Feature,
    min_plan_for_feature,
    plan_has_feature,
    plan_satisfies,
    resolve_effective_plan,
)
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

    Uses UserRole.has_access() for hierarchical comparison instead
    of duplicating the role-level mapping.

    Usage:
        @router.get("/admin", dependencies=[Depends(require_role("ADMIN"))])
    """
    required = UserRole(min_role)

    async def check_role(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        try:
            user_role = UserRole(user.role)
        except ValueError:
            raise InsufficientRoleError(
                f"Unknown role '{user.role}'. Minimum required: '{min_role}'"
            )

        if not user_role.has_access(required):
            raise InsufficientRoleError(
                f"Role '{user.role}' insufficient. Minimum required: '{min_role}'"
            )
        return user

    return check_role


# Payment-required (HTTP 402) is used for tier/feature gates rather than the RBAC
# InsufficientRoleError (403): "you lack permission" and "your plan does not include this"
# are different product signals, and 402 lets the frontend route the user to an upgrade
# flow instead of an access-denied screen. No custom exception / handler wiring is needed
# because HTTPException already carries the status code and structured detail body.
_UPGRADE_URL = "/account/billing"


def require_tier(min_plan: str):
    """Dependency factory: require the tenant's effective plan to be at least `min_plan`.

    Mirrors require_role, but compares subscription tier instead of RBAC role. FOUNDER
    users always pass (resolve_effective_plan short-circuits them to the top tier).

    Usage:
        @router.post("/premium", dependencies=[Depends(require_tier("PRO"))])

    Raises:
        HTTPException(402): if the effective plan ranks below `min_plan`.
    """
    required = min_plan.upper()
    if required not in PLAN_RANK:
        raise ValueError(f"Unknown plan tier '{min_plan}'")

    async def check_tier(
        user: CurrentUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> CurrentUser:
        plan = await resolve_effective_plan(db, role=user.role, tenant_id=user.tenant_id)
        if not plan_satisfies(plan, required):
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "upgrade_required",
                    "current_plan": plan,
                    "required_plan": required,
                    "upgrade_url": _UPGRADE_URL,
                },
            )
        return user

    return check_tier


def require_feature(feature: Feature):
    """Dependency factory: require the tenant's effective plan to include `feature`.

    Sugar over require_tier that resolves the minimum plan from the entitlement map, so
    callers gate by capability ("council_routing") rather than hard-coding a tier name.

    Usage:
        @router.post("/council", dependencies=[Depends(require_feature(Feature.COUNCIL_ROUTING))])

    Raises:
        HTTPException(402): if the effective plan does not unlock `feature`.
    """

    async def check_feature(
        user: CurrentUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> CurrentUser:
        plan = await resolve_effective_plan(db, role=user.role, tenant_id=user.tenant_id)
        if not plan_has_feature(plan, feature):
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "upgrade_required",
                    "feature": feature.value,
                    "current_plan": plan,
                    "required_plan": min_plan_for_feature(feature),
                    "upgrade_url": _UPGRADE_URL,
                },
            )
        return user

    return check_feature
