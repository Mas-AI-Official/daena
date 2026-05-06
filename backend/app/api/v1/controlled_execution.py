"""Controlled Execution Dispatch API -- Sprint-14 PR-1 (2026-05-06).

POST /api/v1/integrations/controlled-execution/dispatch

The single Phase 3 write surface. Every external action goes
through this endpoint (or it does not happen at all). PR-1 ships
the endpoint + every gate; PR-2 onward registers the actual tool
handlers.

The endpoint is FOUNDER-only. The gates are enforced even for the
founder -- approval + consent + payload_hash + Asset Shield +
policy + audit chain are mandatory regardless of role.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_db, require_role
from app.core.logging import get_logger
from app.services.controlled_execution_design import (
    ControlledExecutionRequest,
)
from app.services.controlled_execution_dispatch import (
    ControlledExecutionRefused,
    dispatch_controlled_execution,
    registered_tool_ids,
)

logger = get_logger(__name__)
router = APIRouter()


class DispatchRequest(BaseModel):
    """Request body for /controlled-execution/dispatch.

    Every PR-8 contract field is required. ``payload`` is the
    tool-specific body whose sha256 must match ``payload_hash``.
    """

    approval_id: str = Field(..., min_length=1, max_length=128)
    consent_grant_id: str = Field(..., min_length=1, max_length=128)
    payload_hash: str = Field(..., min_length=64, max_length=64)
    tool_id: str = Field(..., min_length=1, max_length=128)
    owner_email: str | None = Field(default=None, max_length=320)
    asset_shield_pass: bool
    policy_allowlist_pass: bool
    audit_preflight_row_id: str = Field(..., min_length=1, max_length=128)
    audit_result_row_id: str | None = None
    rollback_or_undo_instruction: str | None = Field(
        default=None, max_length=2000,
    )
    payload: dict[str, Any]


class DispatchResponse(BaseModel):
    success: bool
    tool_id: str
    result: dict[str, Any]


@router.post("/dispatch", response_model=DispatchResponse)
async def post_dispatch(
    body: DispatchRequest,
    user: CurrentUser = Depends(require_role("FOUNDER")),
    db: AsyncSession = Depends(get_db),
) -> DispatchResponse:
    """Dispatch one approved external action.

    The endpoint never bypasses any gate. A request that has
    asset_shield_pass=False or policy_allowlist_pass=False refuses
    here, even though those booleans are computed by the caller --
    the caller cannot lie its way past the design contract.
    """

    request = ControlledExecutionRequest(
        approval_id=body.approval_id,
        consent_grant_id=body.consent_grant_id,
        payload_hash=body.payload_hash,
        tool_id=body.tool_id,
        owner_email=body.owner_email,
        asset_shield_pass=body.asset_shield_pass,
        policy_allowlist_pass=body.policy_allowlist_pass,
        audit_preflight_row_id=body.audit_preflight_row_id,
        audit_result_row_id=body.audit_result_row_id,
        rollback_or_undo_instruction=body.rollback_or_undo_instruction,
    )

    try:
        result = await dispatch_controlled_execution(
            db,
            request=request,
            payload=body.payload,
            tenant_id=user.tenant_id,
            user_id=user.id,
        )
    except ControlledExecutionRefused as exc:
        logger.info(
            "controlled_execution.refused",
            code=exc.code,
            tool_id=body.tool_id,
        )
        raise HTTPException(
            status_code=403,
            detail={"code": exc.code, "message": str(exc)},
        )

    return DispatchResponse(
        success=True,
        tool_id=body.tool_id,
        result=result,
    )


class RegisteredToolsResponse(BaseModel):
    tools: list[str]


@router.get("/registered-tools", response_model=RegisteredToolsResponse)
async def get_registered_tools(
    user: CurrentUser = Depends(require_role("FOUNDER")),
) -> RegisteredToolsResponse:
    """Inspector for the operator + tests. Returns the list of
    tool_ids with a registered runtime handler. PR-1 returns []."""
    return RegisteredToolsResponse(tools=registered_tool_ids())
