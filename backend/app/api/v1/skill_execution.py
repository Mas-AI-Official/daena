"""Phase 2 read-only skill execution API.

PR-CONN-PLUGIN-SKILLS-EXECUTION-PHASE2-READONLY (2026-05-03).

Public endpoints:
  GET  /api/v1/connections/v2/skills/allowlist
       -> Display-safe Phase 2 allowlist (which (plugin, skill) pairs
          can be executed at all). Lets the frontend decide whether to
          show the "Run read-only skill" button.

  POST /api/v1/connections/v2/skills/execute
       Body: { plugin_id, skill_id, operator_inputs }
       -> SkillExecutionResult shape (accepted, status, summary,
          audit_event_id, required_inputs, tool_calls, result_preview,
          blocked_reason). NEVER returns secret values.

Auth: ADMIN+ role (re-uses ``require_role("ADMIN")`` from existing
account API endpoints). Phase 2 is operator-only -- not invokable
by background tasks or sub-agents in this PR.

Honesty (project Rule 17):
  * Every response includes the audit_event_id so the operator can
    correlate the skill request with the governance audit trail.
  * No tool actually fires in Phase 2 -- status is always one of
    {planned, blocked, needs_connection, needs_inputs, unsupported}.
    The "executed" status is reserved for follow-up PRs.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_db, require_role
from app.core.logging import get_logger
from app.services.connection_v2.skill_executor import (
    SkillExecutor,
    list_allowlist_for_api,
)

logger = get_logger(__name__)

router = APIRouter()


# ──────────────────────────────────────────────────────────────────
# Request / response schemas
# ──────────────────────────────────────────────────────────────────


class ExecuteSkillRequest(BaseModel):
    """Body for POST /skills/execute.

    ``operator_inputs`` is a flat string->string map. Values are NEVER
    logged as values -- only their KEY NAMES land in the audit row.
    The frontend confirmation modal collects these inputs from the
    operator before submitting.
    """

    plugin_id: str = Field(..., min_length=1, max_length=128)
    skill_id: str = Field(..., min_length=1, max_length=128)
    operator_inputs: dict[str, str] = Field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────


@router.get("/allowlist")
async def get_phase2_allowlist(
    user: CurrentUser = Depends(require_role("ADMIN")),
) -> dict:
    """Display-safe Phase 2 allowlist.

    Used by the frontend to decide whether to surface the "Run
    read-only skill" affordance for a given (plugin, skill) chip.
    Returns metadata only -- no MCP credentials, no OAuth tokens,
    no plugin instance internals.
    """
    return {
        "phase": "phase2_readonly",
        "execution_mode_default": "planned_only",
        "entries": list_allowlist_for_api(),
    }


@router.post("/execute")
async def execute_skill(
    body: ExecuteSkillRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_role("ADMIN")),
) -> dict:
    """Run the Phase 2 spine for one skill request.

    Returns the typed ``SkillExecutionResult`` as a dict. Never raises
    for invariant violations -- those return as statuses so the
    operator + audit row capture intent honestly.

    Hard rules enforced inside the executor:
      * Skill must be in PHASE2_ALLOWLIST.
      * Skill must be marked read_only=True.
      * Plugin's V2 row must be callable.
      * required_inputs must be supplied.
      * No actual tool invocation in Phase 2 -- always returns
        status="planned".
    """
    executor = SkillExecutor(db)
    result = await executor.execute(
        plugin_id=body.plugin_id,
        skill_id=body.skill_id,
        tenant_id=user.tenant_id,
        user_id=user.id,
        operator_inputs=body.operator_inputs,
    )
    # Audit row is committed by executor; commit the session so the
    # caller sees it persisted. (AuditService uses flush, not commit.)
    await db.commit()

    logger.info(
        "skill_execution.attempt",
        plugin_id=body.plugin_id,
        skill_id=body.skill_id,
        status=result.status,
        accepted=result.accepted,
        # NEVER log operator_inputs values.
    )

    return result.to_dict()
