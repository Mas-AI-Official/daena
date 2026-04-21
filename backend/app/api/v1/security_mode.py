"""Elevated security mode API.

Wraps the internal ``evilbob_mode`` singleton with a neutrally-named
REST surface so the hidden activation command (known only to the
founder) can trigger the activation flow from the chat or settings UI
without exposing the command name in any user-visible string.

Endpoints:
    POST /api/v1/security/mode/activate    {key: str}  FOUNDER only
    POST /api/v1/security/mode/deactivate                FOUNDER only
    GET  /api/v1/security/mode/state                     any authenticated user

Response payloads never include the internal codename in any
user-facing field. The router talks about "elevated mode" only.

Per CLAUDE.md rule 12: no em dashes in comments or strings.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, get_current_user, require_role
from app.core.logging import get_logger
from app.services.security import evilbob_mode

logger = get_logger(__name__)

router = APIRouter()


# ----------------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------------


class ActivateRequest(BaseModel):
    """Payload for activating elevated mode."""

    key: str = Field(..., min_length=1, description="Activation key")


class ModeStateResponse(BaseModel):
    """Current elevated mode state.

    Neutrally named. No reference to the hidden command codename.
    """

    active: bool
    environment: str = ""
    capabilities: list[str] = []
    activated_at: str = ""
    activated_by: str = ""
    reason_denied: str = ""


def _serialize_state(state: evilbob_mode.EvilBobState) -> ModeStateResponse:
    """Render internal state as a neutrally-named response."""
    return ModeStateResponse(
        active=state.active,
        environment=state.environment,
        capabilities=list(state.capabilities),
        activated_at=state.activated_at,
        activated_by=state.activated_by,
        reason_denied=state.reason_denied,
    )


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------


@router.post(
    "/activate",
    response_model=ModeStateResponse,
    dependencies=[Depends(require_role("FOUNDER"))],
)
async def activate_elevated_mode(
    body: ActivateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> ModeStateResponse:
    """Activate elevated security mode (founder only).

    Internally calls ``evilbob_mode.activate`` which enforces three
    gates: local environment, matching activation key, founder role.
    """
    state = evilbob_mode.activate(
        key=body.key,
        user_id=str(user.id),
    )
    logger.info(
        "security_mode.activate_request",
        active=state.active,
        environment=state.environment,
        user=str(user.id),
        reason=state.reason_denied if not state.active else "ok",
    )
    if not state.active:
        # Return the failure payload with a 400 so the UI can surface
        # the reason without leaking the internal codename via trace.
        raise HTTPException(
            status_code=400,
            detail={
                "active": False,
                "environment": state.environment,
                "reason_denied": state.reason_denied,
            },
        )
    return _serialize_state(state)


@router.post(
    "/deactivate",
    response_model=ModeStateResponse,
    dependencies=[Depends(require_role("FOUNDER"))],
)
async def deactivate_elevated_mode(
    user: CurrentUser = Depends(get_current_user),
) -> ModeStateResponse:
    """Deactivate elevated security mode (founder only).

    Returns to defensive-only operation.
    """
    state = evilbob_mode.deactivate()
    logger.info(
        "security_mode.deactivate_request",
        user=str(user.id),
    )
    return _serialize_state(state)


@router.get("/state", response_model=ModeStateResponse)
async def get_mode_state(
    user: CurrentUser = Depends(get_current_user),
) -> ModeStateResponse:
    """Get current elevated mode state.

    Available to any authenticated user so the navbar badge and
    governance UI can reflect the current state. Non-founder users
    see the public fields (active flag, environment, capabilities
    list) but never learn the hidden command.
    """
    state = evilbob_mode.get_state()
    return _serialize_state(state)
