"""Security engagements REST endpoints.

Phase G of Roadmap V2. Surfaces the SecurityOperationsAgent to the
frontend so an operator can:

* POST ``/api/v1/engagements`` -- start a new scan against a scoped target.
* GET ``/api/v1/engagements`` -- list all engagements for the tenant.
* GET ``/api/v1/engagements/{job_id}`` -- poll status + progress.
* GET ``/api/v1/engagements/{job_id}/report`` -- fetch the completed
  report once the job finishes.

All writes go through :class:`SecurityOperationsAgent`, which applies
tenant isolation and governance-tier escalation (T4 Architect / T5
engagements pause in GOVERNED mode until a human approves them via the
existing ``/governance/approvals`` endpoint).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.services.approval import ApprovalService
from app.services.departments.security_operations_agent import (
    EngagementApprovalRequired,
    create_security_ops_agent,
)
from app.services.security.yellow_runtime_gate import (
    load_authorized_scope,
    target_matches_scope,
)

logger = get_logger(__name__)

router = APIRouter()


# ── Request + response models ────────────────────────────────────


class StartEngagementRequest(BaseModel):
    """Body for POST /engagements."""

    target: str = Field(..., min_length=3, max_length=2048)
    tier: str = Field(
        default="SCOUT",
        description="T1 Scout | T2 Analyst | T3 Operator | T4 Architect | T5 (founder-gated)",
    )
    options: dict | None = None


# ── Endpoints ────────────────────────────────────────────────────


@router.post("", status_code=status.HTTP_201_CREATED)
async def start_engagement(
    body: StartEngagementRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Kick off a new security engagement.

    High-risk tiers (T4 Architect and T5) persist a PendingApproval row
    and return a structured ``approval_required=True`` payload when
    governance mode is GOVERNED. The row makes the Sidebar approvals
    badge increment immediately; the frontend routes the user to
    ``/governance/approvals`` to grant approval, then retry.
    """
    # Phase 10 commit-1: enforce authorized-scope gate at REST boundary.
    # The agent may also enforce internally (HANDS-OFF list — not refactoring),
    # but the REST boundary IS the security boundary; defense-in-depth.
    scope = load_authorized_scope(user.tenant_id)
    if not target_matches_scope(body.target, scope):
        logger.warning(
            "security.engagement.scope_blocked",
            user_id=user.id,
            tenant_id=user.tenant_id,
            target=body.target,
            tier=body.tier,
        )
        raise HTTPException(
            status_code=403,
            detail={
                "code": "target_not_in_scope",
                "target": body.target,
                "hint": "Add this target to /security/scope before launching an engagement.",
            },
        )

    agent = create_security_ops_agent(
        tenant_id=user.tenant_id,
        user_id=user.id,
        governance_mode=getattr(user, "governance_mode", "BALANCED"),
    )
    try:
        result = await agent.start_engagement(
            target=body.target,
            tier=body.tier,
            options=body.options,
        )
    except EngagementApprovalRequired as exc:
        # Persist the approval row directly so the frontend sees it the
        # moment the banner shows up. Previously this only returned a
        # structured body; Masoud's Sidebar badge never incremented
        # until the user re-tried via the chat path (which is where
        # ExecutionService.execute_tool creates rows).
        approval_request_id: str | None = None
        try:
            approval_svc = ApprovalService(db)
            approval = await approval_svc.request_approval(
                tenant_id=user.tenant_id,
                user_id=user.id,
                action_type="SECURITY_ENGAGEMENT",
                action_params={
                    "target": exc.target,
                    "tier": exc.tier,
                    "options": body.options or {},
                },
                risk_level="HIGH" if exc.tier == "ARCHITECT" else "CRITICAL",
                governance_tier=3 if exc.tier == "ARCHITECT" else 4,
                session_id=None,
                context={
                    "reason": exc.reason,
                    "department": "Security Operations",
                },
            )
            approval_request_id = approval["id"]
            await db.commit()
            logger.info(
                "engagement.approval_persisted",
                request_id=approval_request_id,
                tier=exc.tier,
                target=exc.target,
            )
        except Exception as persist_exc:
            # Persistence failure must not swallow the gate; the UI still
            # needs to tell the user the engagement was blocked.
            logger.warning(
                "engagement.approval_persist_failed",
                tier=exc.tier,
                error=str(persist_exc),
            )

        return {
            "success": False,
            "approval_required": True,
            "reason": exc.reason,
            "tier": exc.tier,
            "target": exc.target,
            "approval_request_id": approval_request_id,
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"success": True, "data": result}


@router.get("")
async def list_engagements(
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """List all engagements visible to the tenant."""
    agent = create_security_ops_agent(
        tenant_id=user.tenant_id,
        user_id=user.id,
        governance_mode=getattr(user, "governance_mode", "BALANCED"),
    )
    jobs = agent.list_engagements()
    return {"success": True, "data": jobs}


def _t5_wire_value() -> str:
    try:
        from app.services.security.report_tiers import ReportTier
        return ReportTier.EVILBOB.value
    except Exception:
        return ""


@router.get("/shield-status")
async def shield_status(
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Whether the T5 full-spectrum tier is currently unlocked.

    Unlocks via the founder secret command in chat (see
    ``/3vilbob`` fast-path handler in chat_orchestrator). Local-only
    activation; cloud deployments cannot unlock. The frontend
    EngagementConsolePage reads this and conditionally shows the T5
    tier option in its dropdown.

    Defined BEFORE the ``/{job_id}`` parametric route so FastAPI
    matches this static path first.
    """
    try:
        from app.services.security.evilbob_mode import is_active
        unlocked = bool(is_active())
    except Exception:
        unlocked = False
    return {
        "success": True,
        "data": {
            "t5_unlocked": unlocked,
            # Wire value the frontend posts when T5 is selected. Pulled
            # from the pre-existing ReportTier enum so the legacy
            # identifier never appears as a literal in this module.
            "t5_wire_value": _t5_wire_value(),
        },
    }


@router.get("/{job_id}")
async def get_engagement_status(
    job_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Poll status for an engagement."""
    agent = create_security_ops_agent(
        tenant_id=user.tenant_id,
        user_id=user.id,
        governance_mode=getattr(user, "governance_mode", "BALANCED"),
    )
    try:
        status_dict = await agent.get_status(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "data": status_dict}


@router.get("/{job_id}/report")
async def get_engagement_report(
    job_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Fetch the completed report for a finished engagement."""
    agent = create_security_ops_agent(
        tenant_id=user.tenant_id,
        user_id=user.id,
        governance_mode=getattr(user, "governance_mode", "BALANCED"),
    )
    try:
        report = await agent.get_report(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "data": report}
