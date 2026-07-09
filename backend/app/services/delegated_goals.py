"""G5: agent-initiated delegated goals with a spend/outreach approval gate.

The VP decomposes a goal into department subtasks (existing DaenaVP
plan -> route -> apply_policies pipeline) and materializes them as Task
rows in the ExecutionService queue -- agent-initiated, not just CMD.

Autonomy ceiling (locked decision): read + plan + decompose + draft
freely with NO per-step approval. A hard approval gate fires ONLY on:

  (a) spend  -- anything over the free/local tier, and
  (b) outward-facing action -- outreach / send / publish / deploy.

Gated steps write a GoaRequest + PendingApproval row via
ApprovalService and NEVER auto-approve; ``ExecutionService.run_task``
refuses to dispatch a gated task until a human approves.

Classification (:func:`classify_step`) is pure and deliberately
conservative on the free side: "Draft an email" stays FREE because
drafting is inside the ceiling; only action verbs (send / publish /
deploy / ...) in verb position classify OUTWARD. False negatives are
acceptable by design -- ``execute_tool``'s full gate pipeline
(LLM_CALL tier resolution, TRUST_FORBIDDEN_TOOLS, SEND_EXTERNAL) is
the tool-time enforcement backstop, and CostGuard.preflight_check
still guards every metered LLM call at execution time. This gate is
the plan-time layer of that defense in depth.

Shape consistency: checkpoint_data mirrors the Stage 2.85 VP
materialization precedent (``{"source": "daena_vp", ...}``) using
source "delegated_goal" and a nested "delegation" dict whose origin
matches ``trust_policy.Origin.DELEGATED``.
"""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.organization import Department
from app.services.approval import ApprovalService
from app.services.daena_vp import DaenaVP, VPPlan, VPSubtask
from app.services.execution_service import ExecutionService
from app.services.trust_policy import TRUST_FORBIDDEN_TOOLS

logger = get_logger(__name__)


# ── step classification (pure, deterministic) ──────────────────────

# A gate verb preceded by a determiner is noun usage ("the deploy
# runbook") and must not gate -- drafting/documentation stays free.
_DETERMINERS = frozenset(
    {"the", "a", "an", "this", "that", "our", "their", "its",
     "his", "her", "my", "your"}
)
_OUTWARD_VERBS = frozenset(
    {"send", "publish", "deploy", "submit", "tweet", "announce",
     "broadcast", "outreach", "invite", "dm"}
)
_OUTWARD_PHRASES = ("post to", "post on", "reach out", "follow up with")
_SPEND_VERBS = frozenset({"buy", "purchase", "pay", "subscribe", "procure"})
_MONEY_RE = re.compile(r"\$\s*\d")
_WORD_RE = re.compile(r"[a-z]+")


def _verb_hit(words: list[str], verbs: frozenset[str]) -> bool:
    for i, w in enumerate(words):
        if w in verbs and (i == 0 or words[i - 1] not in _DETERMINERS):
            return True
    return False


def classify_step(subtask: VPSubtask) -> str:
    """Classify a VP subtask against the autonomy ceiling.

    Returns "outward" | "spend" | "free". Outward wins over spend
    (stricter gate). Pure function -- no I/O, safe to unit test.
    """
    md = subtask.metadata or {}
    text = (subtask.description or "").lower()
    words = _WORD_RE.findall(text)

    tool = str(md.get("tool") or "")
    if tool in TRUST_FORBIDDEN_TOOLS:
        return "outward"
    if any(p in text for p in _OUTWARD_PHRASES) or _verb_hit(
        words, _OUTWARD_VERBS
    ):
        return "outward"

    cost_raw = md.get("estimated_cost", md.get("amount", 0))
    try:
        cost = float(cost_raw or 0)
    except (TypeError, ValueError):
        cost = 0.0
    if cost > 0 or _MONEY_RE.search(text) or _verb_hit(words, _SPEND_VERBS):
        return "spend"
    return "free"


# ── service ─────────────────────────────────────────────────────────


class DelegatedGoalService:
    """Materialize a delegated goal into gated ExecutionService tasks.

    Usage::

        svc = DelegatedGoalService(db)
        result = await svc.delegate(
            goal="Research competitors and draft a brief",
            tenant_id=tenant_id, user_id=user_id,
        )
        # result: {"goal", "routing_mode", "task_ids", "steps", "gated"}
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def delegate(
        self,
        *,
        goal: str,
        tenant_id: UUID,
        user_id: UUID,
        session_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Plan a goal via DaenaVP and materialize it as Task rows."""
        from app.services.department_state_service import (
            DepartmentStateService,
        )

        vp = DaenaVP(state_service=DepartmentStateService(self.db))
        plan = await vp.plan(goal, tenant_id=tenant_id)
        plan = await vp.route(plan, tenant_id=tenant_id)
        plan = await vp.apply_policies(plan, tenant_id=tenant_id)

        result = await self.materialize_plan(
            plan, tenant_id=tenant_id, user_id=user_id,
            session_id=session_id,
        )
        result["goal"] = goal

        # Autopilot kicker: dispatch every FREE step immediately so a
        # delegated goal actually starts running without a human POST
        # /run. Gated (spend/outward) steps are NEVER kicked -- they
        # stay PENDING behind their approval, and run_task's G5 gate
        # refuses them anyway (defense in depth). Best-effort: a kick
        # that raises is logged and skipped so one bad step never aborts
        # the whole delegation.
        exec_svc = ExecutionService(self.db)
        kicked: list[str] = []
        for step in result["steps"]:
            if step["classification"] != "free":
                continue
            try:
                await exec_svc.run_task(UUID(step["task_id"]), tenant_id)
                kicked.append(step["task_id"])
            except Exception:  # noqa: BLE001 - best-effort autopilot kick
                logger.warning(
                    "delegated_goal.kick_failed",
                    task_id=step["task_id"],
                    exc_info=True,
                )
        result["kicked"] = kicked

        logger.info(
            "delegated_goal.materialized",
            tenant_id=str(tenant_id),
            tasks=len(result["task_ids"]),
            gated=result["gated"],
            kicked=len(kicked),
            routing_mode=result["routing_mode"],
        )
        return result

    async def materialize_plan(
        self,
        plan: VPPlan,
        *,
        tenant_id: UUID,
        user_id: UUID,
        session_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Create one PENDING Task per subtask; gate spend/outward steps.

        Public seam so tests can hand-build deterministic VPPlans
        without the router. Gated steps get a GoaRequest (born PENDING,
        never auto-approved) whose id is stored in
        ``checkpoint_data["delegation"]["approval_request_id"]`` --
        run_task enforces it at dispatch time.
        """
        exec_svc = ExecutionService(self.db)
        approval_svc = ApprovalService(self.db)
        task_ids: list[str] = []
        steps: list[dict[str, Any]] = []
        gated = 0

        for idx, st in enumerate(plan.subtasks):
            classification = classify_step(st)
            dept_id = await self._resolve_department_id(
                st.department, tenant_id
            )

            approval_id: str | None = None
            if classification in ("spend", "outward"):
                approval = await approval_svc.request_approval(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    action_type=f"delegated_step:{classification}",
                    action_params={
                        "description": st.description[:500],
                        "department": st.department,
                    },
                    risk_level=(
                        "HIGH" if classification == "outward" else "MEDIUM"
                    ),
                    governance_tier=3,
                    session_id=session_id,
                    context={
                        "source": "delegated_goal",
                        "goal": plan.user_request[:500],
                        "step_index": idx,
                    },
                )
                approval_id = str(approval["id"])
                gated += 1

            delegation = {
                "origin": "delegated",
                "goal": plan.user_request,
                "department": st.department,
                "classification": classification,
                "approval_request_id": approval_id,
                "required_approvers": list(
                    (st.metadata or {}).get("required_approvers") or []
                ),
                "step_index": idx,
                "routing_mode": plan.routing_mode,
            }
            created = await exec_svc.create_task(
                name=st.description[:200],
                description=f"[{st.department}] {st.description}"[:4000],
                user_id=user_id,
                tenant_id=tenant_id,
                session_id=session_id,
                also_create_workstream=True,
                department_id=dept_id,
                checkpoint_data={
                    "source": "delegated_goal",
                    "delegation": delegation,
                },
            )
            task_ids.append(created["id"])
            steps.append(
                {
                    "task_id": created["id"],
                    "department": st.department,
                    "classification": classification,
                    "approval_request_id": approval_id,
                }
            )

        return {
            "task_ids": task_ids,
            "steps": steps,
            "gated": gated,
            "routing_mode": plan.routing_mode,
        }

    async def _resolve_department_id(
        self, name: str, tenant_id: UUID
    ) -> UUID | None:
        """Resolve a VP department NAME to its id (tenant-scoped).

        Returns None when no active match exists; create_task then
        falls back to the tenant's first active department.
        """
        if not name:
            return None
        stmt = select(Department).where(
            Department.tenant_id == tenant_id,
            Department.name == name,
            Department.is_active.is_(True),
        )
        row = (await self.db.execute(stmt)).scalar_one_or_none()
        return row.id if row is not None else None
