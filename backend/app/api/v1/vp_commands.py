"""VP work chat commands -- Sprint-12 PR-5.

Single endpoint that lets the operator drive Daena's draft +
workstream pipeline from natural English.

  POST /api/v1/vp-commands
  Body: {"text": "review this opportunity"}

The endpoint parses the message via :pyfunc:`vp_work_commands.parse_command`
then runs it via :pyfunc:`vp_work_commands.run_command`. Hard rules:

  * No external action. None of the runners send / submit / post
    anything outside Daena.
  * Tenant + user-scoped. The runner only sees the calling user's
    drafts / workstreams.
  * If the runtime needed by an enrichment / QE call isn't ready,
    the underlying service refuses; the response surfaces the
    readiness ``next_action`` verbatim.
  * Always returns 200 -- even refusals + needs_disambiguation come
    back as a structured payload so the chat UI can render them.
    The endpoint never produces 500 for parser-level inputs.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_role
from app.core.database import get_db
from app.services.delegated_goals import DelegatedGoalService
from app.services.vp_work_commands import (
    CommandResult,
    parse_command,
    run_command,
)


router = APIRouter()


class VPCommandRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    allow_metered: bool = Field(default=False)
    allow_web_grounding: bool = Field(default=False)


class VPCommandResponse(BaseModel):
    success: bool
    intent: str
    summary: str
    needs_disambiguation: bool
    next_action: str | None
    data: dict


class DelegateGoalRequest(BaseModel):
    goal: str = Field(..., min_length=3, max_length=4000)
    session_id: UUID | None = None


class DelegateGoalResponse(BaseModel):
    goal: str
    routing_mode: str
    task_ids: list[str]
    gated: int
    steps: list[dict]


@router.post("/delegate", response_model=DelegateGoalResponse)
async def delegate_goal(
    body: DelegateGoalRequest,
    user: CurrentUser = Depends(require_role("FOUNDER")),
    db: AsyncSession = Depends(get_db),
) -> DelegateGoalResponse:
    """Delegate a multi-step goal to the VP (G5).

    The VP plans + routes the goal, then materializes one PENDING
    Task per subtask. Spend / outward-facing steps get a PENDING
    approval row and cannot run until a human approves -- there is
    no auto-approve path.
    """
    svc = DelegatedGoalService(db)
    result = await svc.delegate(
        goal=body.goal,
        tenant_id=user.tenant_id,
        user_id=user.id,
        session_id=body.session_id,
    )
    return DelegateGoalResponse(
        goal=result["goal"],
        routing_mode=result["routing_mode"],
        task_ids=result["task_ids"],
        gated=result["gated"],
        steps=result["steps"],
    )


@router.post("", response_model=VPCommandResponse)
async def post_vp_command(
    body: VPCommandRequest,
    request: Request,
    user: CurrentUser = Depends(require_role("FOUNDER")),
    db: AsyncSession = Depends(get_db),
) -> VPCommandResponse:
    """Run a VP work command.

    The handler returns ``success=False`` for unrecognized commands +
    runtime-not-ready refusals; HTTP status is 200 in either case.
    """
    parsed = parse_command(body.text)
    registry = getattr(request.app.state, "model_registry", None)
    result: CommandResult = await run_command(
        db, parsed,
        user_id=user.id,
        tenant_id=user.tenant_id,
        actor_role="FOUNDER",
        registry=registry,
        allow_metered=body.allow_metered,
        allow_web_grounding=body.allow_web_grounding,
    )
    return VPCommandResponse(
        success=result.success,
        intent=result.intent,
        summary=result.summary,
        needs_disambiguation=result.needs_disambiguation,
        next_action=result.next_action,
        data=result.data,
    )
