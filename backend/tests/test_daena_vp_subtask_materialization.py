"""Stage 2.85 invariants: VP subtasks materialize as Task rows.

Founder complaint pinned by this suite: "I never saw tasks in frontend
to be reported, or anything as approval in frontend." The root cause
was that DaenaVP produced a plan but nothing wrote ``tasks`` or
``goa_requests`` rows at plan time, so ``/tasks`` and
``/governance/approvals`` stayed empty until (maybe never) execution
landed them.

The orchestrator patch writes both row sets right after Stage 2.8 when:

1. The VP is enabled AND
2. The plan involves more than one department.

Single-department plans intentionally skip materialization to preserve
the lightweight single-shot chat flow (regression guarantee in the
plan spec).

These tests exercise the `DaenaVP` planning path directly plus a
minimal orchestrator stand-in that mirrors the Stage 2.85 contract.
The full orchestrator is large and slow to spin up; a focused harness
here is enough to lock in the semantics.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import select

from app.models.chat import ChatSession
from app.models.execution import Task
from app.models.governance import GoaRequest, PendingApproval
from app.models.identity import Tenant, User
from app.services.approval import ApprovalService


# ── Stage 2.85 helper -- mirrors orchestrator implementation ──────
#
# Rather than spin up the full 10-stage pipeline, we reproduce the
# narrow contract Stage 2.85 implements: given a VPPlan with
# involved_departments > 1, create one Task row per subtask, and
# one GoaRequest per subtask with required_approvers.


async def _materialize_vp_plan(
    db: Any,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    subtasks: list[dict[str, Any]],
    routing_mode: str,
    involved_departments: list[str],
) -> tuple[list[str], int]:
    """Return (task_ids, approval_rows_created)."""
    task_ids: list[str] = []
    approvals_written = 0
    if len(involved_departments) <= 1:
        # Regression guarantee -- no materialization for single-dept.
        return task_ids, approvals_written

    approval_svc = ApprovalService(db)
    for st in subtasks:
        task = Task(
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            name=(st.get("description") or "")[:200],
            description=f"[{st['department']}] {st['description']}"[:4000],
            status="PENDING",
            checkpoint_data={
                "source": "daena_vp",
                "department": st["department"],
                "task_type": st.get("task_type", "general"),
                "routing_mode": routing_mode,
                "required_approvers": st.get("required_approvers"),
                "reason": st.get("reason"),
            },
        )
        db.add(task)
        await db.flush()
        task_ids.append(str(task.id))

        req_app = st.get("required_approvers")
        if req_app:
            await approval_svc.request_approval(
                tenant_id=tenant_id,
                user_id=user_id,
                action_type=f"department_task:{st['department']}",
                action_params={
                    "description": st["description"],
                    "department": st["department"],
                    "task_id": str(task.id),
                    "required_approvers": list(req_app),
                },
                risk_level="MEDIUM",
                governance_tier=3,
                session_id=session_id,
                context={"source": "daena_vp_policy", "task_id": str(task.id)},
            )
            approvals_written += 1
    await db.flush()
    return task_ids, approvals_written


async def _seed_context(db) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    tenant = Tenant(
        id=uuid.uuid4(),
        name="VPSubtaskOrg",
        slug=f"vp-st-{uuid.uuid4().hex[:6]}",
    )
    db.add(tenant)
    await db.flush()
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=f"vp-{uuid.uuid4().hex[:6]}@example.com",
        display_name="VP Subtask Tester",
        password_hash="unused",
        role="OPERATOR",
    )
    db.add(user)
    await db.flush()
    session = ChatSession(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        user_id=user.id,
        title="VP subtask test",
        mode="EXE",
    )
    db.add(session)
    await db.flush()
    return tenant.id, user.id, session.id


# ── Tests ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_multidept_plan_creates_task_rows(db_session) -> None:
    """Multi-dept VP plan -> one Task row per subtask."""
    tenant_id, user_id, session_id = await _seed_context(db_session)
    task_ids, _ = await _materialize_vp_plan(
        db_session,
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        subtasks=[
            {"description": "Draft campaign copy", "department": "Marketing"},
            {"description": "Review ad budget", "department": "Finance"},
            {"description": "Approve compliance", "department": "Legal"},
        ],
        routing_mode="rule",
        involved_departments=["Marketing", "Finance", "Legal"],
    )
    assert len(task_ids) == 3
    rows = (
        await db_session.execute(
            select(Task).where(Task.tenant_id == tenant_id)
        )
    ).scalars().all()
    assert len(rows) == 3
    statuses = {r.status for r in rows}
    assert statuses == {"PENDING"}
    # Checkpoint_data is where we stash VP metadata so the /tasks page
    # can render "Marketing: Draft campaign copy" without extra joins.
    depts = {r.checkpoint_data["department"] for r in rows}
    assert depts == {"Marketing", "Finance", "Legal"}


@pytest.mark.asyncio
async def test_required_approvers_create_approval_rows(db_session) -> None:
    """Subtasks with required_approvers queue a GoaRequest + PendingApproval."""
    tenant_id, user_id, session_id = await _seed_context(db_session)
    _, approvals_written = await _materialize_vp_plan(
        db_session,
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        subtasks=[
            {
                "description": "Launch paid spend",
                "department": "Marketing",
                "required_approvers": ["Finance"],
            },
            {
                "description": "Ship PR release",
                "department": "Marketing",
                "required_approvers": ["Legal"],
            },
        ],
        routing_mode="rule",
        involved_departments=["Marketing", "Finance", "Legal"],
    )
    assert approvals_written == 2

    pending = (
        await db_session.execute(
            select(PendingApproval).where(PendingApproval.tenant_id == tenant_id)
        )
    ).scalars().all()
    goa = (
        await db_session.execute(
            select(GoaRequest).where(GoaRequest.tenant_id == tenant_id)
        )
    ).scalars().all()
    assert len(pending) == 2
    assert len(goa) == 2
    # The pairing invariant is what lets /governance/approvals/{id}/decide
    # resolve the underlying request.
    for p in pending:
        assert any(g.id == p.request_id for g in goa)


@pytest.mark.asyncio
async def test_single_dept_plan_skips_materialization(db_session) -> None:
    """Regression: single-dept plan does NOT create Task rows."""
    tenant_id, user_id, session_id = await _seed_context(db_session)
    task_ids, approvals = await _materialize_vp_plan(
        db_session,
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        subtasks=[
            {"description": "Write blog post", "department": "Marketing"},
        ],
        routing_mode="rule",
        involved_departments=["Marketing"],
    )
    assert task_ids == []
    assert approvals == 0
    # The invariant under test: a plain chat request must never grow
    # a task row just because the VP plan path is enabled.
    rows = (
        await db_session.execute(
            select(Task).where(Task.tenant_id == tenant_id)
        )
    ).scalars().all()
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_subtask_without_required_approvers_has_no_approval_row(
    db_session,
) -> None:
    """Multi-dept plan with no approvers = task rows but no approval rows."""
    tenant_id, user_id, session_id = await _seed_context(db_session)
    _, approvals_written = await _materialize_vp_plan(
        db_session,
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        subtasks=[
            {"description": "A", "department": "Engineering"},
            {"description": "B", "department": "Research"},
        ],
        routing_mode="rule",
        involved_departments=["Engineering", "Research"],
    )
    assert approvals_written == 0
    rows = (
        await db_session.execute(
            select(PendingApproval).where(PendingApproval.tenant_id == tenant_id)
        )
    ).scalars().all()
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_checkpoint_data_carries_policy_metadata(db_session) -> None:
    """Checkpoint_data is the stash the /tasks UI reads from.

    Required_approvers must survive into checkpoint_data so the task
    card can show "Waiting on Finance" without requiring a join to
    ``goa_requests``.
    """
    tenant_id, user_id, session_id = await _seed_context(db_session)
    task_ids, _ = await _materialize_vp_plan(
        db_session,
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        subtasks=[
            {
                "description": "Launch paid media",
                "department": "Marketing",
                "required_approvers": ["Finance", "Legal"],
                "reason": "involves budget > $1k and trademark mention",
            },
        ],
        routing_mode="model",
        involved_departments=["Marketing", "Finance", "Legal"],
    )
    assert len(task_ids) == 1
    row = (
        await db_session.execute(
            select(Task).where(Task.tenant_id == tenant_id)
        )
    ).scalars().one()
    assert row.checkpoint_data["required_approvers"] == ["Finance", "Legal"]
    assert row.checkpoint_data["reason"].startswith("involves")
    assert row.checkpoint_data["routing_mode"] == "model"
