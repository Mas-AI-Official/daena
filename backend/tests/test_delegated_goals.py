"""G5 contract: agent-initiated delegated goals with a spend/outreach gate.

Autonomy ceiling (locked): the VP may read + plan + decompose + draft
freely with NO per-step approval. A hard approval gate fires ONLY on:

  (a) spend  -- anything over the free/local tier, and
  (b) outward-facing action -- outreach / send / publish / deploy.

Gated steps write a GoaRequest + PendingApproval row and NEVER
auto-approve; only a human ``ApprovalService.approve()`` unblocks them.
``ExecutionService.run_task`` enforces the gate at dispatch time, so a
gated task cannot flip to RUNNING while its approval is PENDING,
REJECTED, or EXPIRED.

Classification is deliberately conservative on the free side: "Draft an
email" is FREE (drafting is inside the ceiling); only action verbs like
send/publish/deploy classify OUTWARD. False negatives are acceptable
because ``execute_tool``'s gate pipeline remains the tool-time
enforcement backstop (defense in depth).

Shape consistency: checkpoint_data mirrors the Stage 2.85 precedent
(``test_daena_vp_subtask_materialization.py``) with source
"delegated_goal" and a nested "delegation" dict carrying
origin="delegated" (trust_policy DELEGATED origin).
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import select

from app.core.exceptions import ValidationError
from app.models.execution import Task
from app.models.governance import GoaRequest, PendingApproval
from app.models.identity import Tenant, User
from app.models.organization import Department
from app.services.approval import ApprovalService
from app.services.daena_vp import VPPlan, VPSubtask
from app.services.delegated_goals import DelegatedGoalService, classify_step
from app.services.execution_service import ExecutionService


# ── seed helpers (mirrors test_task_workstream_sync._seed) ─────────


async def _seed(db, *, dept_names: tuple[str, ...] = ("Engineering",)):
    """Seed Tenant + FOUNDER User + named active Departments."""
    s = uuid.uuid4().hex[:8]
    t = Tenant(id=uuid.uuid4(), name=f"dg-tenant-{s}", slug=f"dg-{s}")
    db.add(t)
    await db.flush()
    u = User(
        id=uuid.uuid4(),
        tenant_id=t.id,
        email=f"dg-{s}@example.com",
        password_hash="x",
        role="FOUNDER",
    )
    db.add(u)
    await db.flush()
    dept_ids: dict[str, uuid.UUID] = {}
    for i, name in enumerate(dept_names):
        d = Department(
            id=uuid.uuid4(),
            tenant_id=t.id,
            name=name,
            description="dg-test",
            sunflower_index=i,
            cell_id=f"hex_{i}_{s}",
            config={},
            is_active=True,
        )
        db.add(d)
        await db.flush()
        dept_ids[name] = d.id
    await db.commit()
    return t.id, u.id, dept_ids


def _plan(subtasks: list[VPSubtask], goal: str = "test goal") -> VPPlan:
    return VPPlan(user_request=goal, subtasks=subtasks, routing_mode="rule")


async def _tasks_for_tenant(db, tenant_id) -> list[Task]:
    rows = await db.execute(select(Task).where(Task.tenant_id == tenant_id))
    return list(rows.scalars().all())


async def _wait_terminal(db, task_id, timeout: float = 8.0) -> str:
    """Poll until the background runner leaves RUNNING (keeps the event
    loop clean -- run_task spawns a detached asyncio task)."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.3)
        db.expire_all()
        row = (
            await db.execute(select(Task).where(Task.id == task_id))
        ).scalar_one()
        if row.status not in ("RUNNING",):
            return row.status
    return "RUNNING"


@pytest.fixture(autouse=True)
async def _drain_background_runs():
    """Let run_task's detached ``_background_run`` fully finish before
    the test ends.

    The COMPLETED status flip is NOT its last write -- it then emits a
    task_complete notification and commits. A bg task that outlives the
    test interleaves that commit with the next test's table cleanup on
    the shared in-memory StaticPool connection, invalidating it (seen
    as ``no such table: tool_executions`` in the next test's setup).
    """
    yield
    deadline = asyncio.get_event_loop().time() + 12.0
    while asyncio.get_event_loop().time() < deadline:
        pending = [
            t for t in asyncio.all_tasks()
            if not t.done()
            and "_background_run"
            in getattr(t.get_coro(), "__qualname__", "")
        ]
        if not pending:
            return
        await asyncio.sleep(0.1)


@pytest.fixture(autouse=True)
def _stub_delegated_executor(monkeypatch):
    """The run-to-terminal tests here assert the lifecycle contract
    (gate -> RUNNING -> COMPLETED), not executor behavior. Stub the
    real delegated executor (delegated-llm-v1 needs live providers)
    so the lifecycle stays testable offline. Executor behavior has
    its own suite: tests/test_delegated_executor.py."""
    async def _fake_execute(**kwargs):
        return {
            "summary": f"stub: {kwargs.get('name')}",
            "executor": "stub-delegated",
        }
    monkeypatch.setattr(
        "app.services.delegated_executor.execute_delegated_step",
        _fake_execute,
    )


# ── 1. classify_step: pure, deterministic ──────────────────────────


class TestClassifyStep:
    def test_outward_action_verbs_gate(self):
        for desc in (
            "Send the launch announcement to the partner list",
            "Publish the blog post on the company site",
            "Deploy the new landing page to production",
            "Reach out to the top 10 leads from the conference",
            "Post to LinkedIn about the funding round",
        ):
            st = VPSubtask(description=desc, department="Marketing")
            assert classify_step(st) == "outward", desc

    def test_drafting_stays_free(self):
        # The ceiling says draft freely -- bare nouns must NOT gate.
        for desc in (
            "Draft an email to investors summarizing Q2",
            "Write a post about our launch for review",
            "Prepare a message for the enterprise customers",
            "Compose the deploy runbook documentation",
        ):
            st = VPSubtask(description=desc, department="Marketing")
            assert classify_step(st) == "free", desc

    def test_spend_markers_gate(self):
        for desc in (
            "Buy a domain name for the campaign",
            "Purchase 3 GPU instances for training",
            "Subscribe to the Ahrefs pro tier",
            "Allocate $500 for the ad campaign",
        ):
            st = VPSubtask(description=desc, department="Finance")
            assert classify_step(st) == "spend", desc

    def test_metadata_estimated_cost_gates_spend(self):
        st = VPSubtask(
            description="Run the batch job",
            department="Engineering",
            metadata={"estimated_cost": 12.5},
        )
        assert classify_step(st) == "spend"

    def test_forbidden_tool_metadata_gates_outward(self):
        st = VPSubtask(
            description="Finish the reply thread",
            department="Operations",
            metadata={"tool": "gmail.send_existing_draft"},
        )
        assert classify_step(st) == "outward"

    def test_outward_beats_spend(self):
        # Outward is the stricter gate; a step that both spends and
        # sends classifies outward.
        st = VPSubtask(
            description="Buy and send gift cards to the beta customers",
            department="Operations",
        )
        assert classify_step(st) == "outward"

    def test_internal_work_defaults_free(self):
        for desc in (
            "Research competitor pricing pages",
            "Analyze the churn data from March",
            "Summarize the Q2 board report",
            "Refactor the ingestion pipeline tests",
        ):
            st = VPSubtask(description=desc, department="Engineering")
            assert classify_step(st) == "free", desc


# ── 2. materialize_plan: Task rows + delegation metadata ───────────


@pytest.mark.asyncio
async def test_materialize_plan_creates_pending_tasks_with_metadata(
    db_session,
):
    tid, uid, _depts = await _seed(
        db_session, dept_names=("Engineering", "Marketing")
    )
    plan = _plan(
        [
            VPSubtask(
                description="Analyze the churn data",
                department="Engineering",
            ),
            VPSubtask(
                description="Draft an email to investors",
                department="Marketing",
            ),
        ],
        goal="Understand churn and brief investors",
    )
    svc = DelegatedGoalService(db_session)
    result = await svc.materialize_plan(plan, tenant_id=tid, user_id=uid)

    assert len(result["task_ids"]) == 2
    tasks = await _tasks_for_tenant(db_session, tid)
    assert len(tasks) == 2
    depts_seen = set()
    for t in tasks:
        assert t.status == "PENDING"
        cp = t.checkpoint_data or {}
        assert cp.get("source") == "delegated_goal"
        dg = cp.get("delegation") or {}
        assert dg.get("origin") == "delegated"
        assert dg.get("goal") == "Understand churn and brief investors"
        assert dg.get("classification") == "free"
        assert dg.get("approval_request_id") is None
        depts_seen.add(dg.get("department"))
    assert depts_seen == {"Engineering", "Marketing"}

    # Free steps write ZERO approval rows.
    goas = (
        await db_session.execute(
            select(GoaRequest).where(GoaRequest.tenant_id == tid)
        )
    ).scalars().all()
    assert goas == []


@pytest.mark.asyncio
async def test_outward_step_writes_pending_approval_never_auto(db_session):
    tid, uid, _depts = await _seed(db_session, dept_names=("Marketing",))
    plan = _plan(
        [
            VPSubtask(
                description="Send the launch announcement to partners",
                department="Marketing",
            )
        ]
    )
    svc = DelegatedGoalService(db_session)
    result = await svc.materialize_plan(plan, tenant_id=tid, user_id=uid)

    task = (await _tasks_for_tenant(db_session, tid))[0]
    dg = (task.checkpoint_data or {}).get("delegation") or {}
    assert dg.get("classification") == "outward"
    approval_id = dg.get("approval_request_id")
    assert approval_id, "gated step must store its approval_request_id"

    goa = (
        await db_session.execute(
            select(GoaRequest).where(GoaRequest.id == uuid.UUID(approval_id))
        )
    ).scalar_one()
    # NEVER auto-approved: born PENDING, only a human flips it.
    assert goa.status == "PENDING"
    pending = (
        await db_session.execute(
            select(PendingApproval).where(
                PendingApproval.request_id == goa.id
            )
        )
    ).scalar_one_or_none()
    assert pending is not None
    assert result["gated"] == 1


# ── 3. run_task gate: PENDING blocks, APPROVED unblocks ────────────


async def _materialize_single_outward(db):
    tid, uid, _ = await _seed(db, dept_names=("Marketing",))
    svc = DelegatedGoalService(db)
    await svc.materialize_plan(
        _plan(
            [
                VPSubtask(
                    description="Send the launch announcement to partners",
                    department="Marketing",
                )
            ]
        ),
        tenant_id=tid,
        user_id=uid,
    )
    task = (await _tasks_for_tenant(db, tid))[0]
    approval_id = uuid.UUID(
        task.checkpoint_data["delegation"]["approval_request_id"]
    )
    return tid, uid, task.id, approval_id


@pytest.mark.asyncio
async def test_run_task_blocks_while_pending_then_runs_after_approve(
    db_session,
):
    tid, uid, task_id, approval_id = await _materialize_single_outward(
        db_session
    )
    exec_svc = ExecutionService(db_session)

    with pytest.raises(ValidationError):
        await exec_svc.run_task(task_id, tid)
    db_session.expire_all()
    row = (
        await db_session.execute(select(Task).where(Task.id == task_id))
    ).scalar_one()
    assert row.status == "PENDING", "gate must not leak a RUNNING flip"

    await ApprovalService(db_session).approve(
        request_id=approval_id, tenant_id=tid, decided_by=uid
    )
    result = await exec_svc.run_task(task_id, tid)
    assert result["status"] == "RUNNING"
    # Drain the detached background runner so it cannot outlive the test.
    assert await _wait_terminal(db_session, task_id) == "COMPLETED"


@pytest.mark.asyncio
async def test_run_task_blocks_rejected(db_session):
    tid, uid, task_id, approval_id = await _materialize_single_outward(
        db_session
    )
    await ApprovalService(db_session).reject(
        request_id=approval_id, tenant_id=tid, decided_by=uid,
        reason="not now",
    )
    with pytest.raises(ValidationError):
        await ExecutionService(db_session).run_task(task_id, tid)


@pytest.mark.asyncio
async def test_free_task_runs_immediately_ungated(db_session):
    tid, uid, _ = await _seed(db_session)
    svc = DelegatedGoalService(db_session)
    await svc.materialize_plan(
        _plan(
            [
                VPSubtask(
                    description="Summarize the Q2 board report",
                    department="Engineering",
                )
            ]
        ),
        tenant_id=tid,
        user_id=uid,
    )
    task = (await _tasks_for_tenant(db_session, tid))[0]
    result = await ExecutionService(db_session).run_task(task.id, tid)
    assert result["status"] == "RUNNING"
    assert await _wait_terminal(db_session, task.id) == "COMPLETED"


# ── 4. delegate(): end-to-end goal -> plan -> materialized tasks ───


@pytest.mark.asyncio
async def test_delegate_goal_materializes_tasks(db_session):
    tid, uid, _ = await _seed(
        db_session, dept_names=("Engineering", "Marketing")
    )
    svc = DelegatedGoalService(db_session)
    result = await svc.delegate(
        goal="Research competitor pricing and draft a comparison brief",
        tenant_id=tid,
        user_id=uid,
    )
    # Rule-router department splits are NOT asserted (router heuristics
    # may evolve); the contract is: at least one task, all carrying the
    # delegation metadata shape.
    assert len(result["task_ids"]) >= 1
    assert result["routing_mode"] in ("rule", "model", "fallback")
    tasks = await _tasks_for_tenant(db_session, tid)
    assert len(tasks) == len(result["task_ids"])
    for t in tasks:
        cp = t.checkpoint_data or {}
        assert cp.get("source") == "delegated_goal"
        dg = cp.get("delegation") or {}
        assert dg.get("origin") == "delegated"
        assert dg.get("classification") in ("free", "spend", "outward")
        assert "step_index" in dg


# ── 5. autopilot kicker: free steps run, gated steps stay PENDING ──


class _FakeVP:
    """Deterministic VP stub so delegate() materializes a KNOWN mixed
    plan (one free + one outward) without the live rule/model router.

    __init__ swallows ``state_service=`` (delegate constructs a real
    DepartmentStateService and passes it in); the pipeline methods are
    pass-through so classify_step sees our hand-built subtasks verbatim.
    """

    _PLAN = _plan(
        [
            VPSubtask(
                description="Analyze the churn data", department="Engineering"
            ),
            VPSubtask(
                description="Send the launch announcement to partners",
                department="Marketing",
            ),
        ],
        goal="Launch the Q3 growth push",
    )

    def __init__(self, **_kw):
        pass

    async def plan(self, goal, *, tenant_id):
        return self._PLAN

    async def route(self, plan, *, tenant_id):
        return plan

    async def apply_policies(self, plan, *, tenant_id):
        return plan


@pytest.mark.asyncio
async def test_delegate_kicks_free_steps_leaves_gated_pending(
    db_session, monkeypatch
):
    """The autopilot kicker: after delegate() materializes a plan, every
    FREE step is dispatched (leaves PENDING with NO manual POST /run),
    while every gated (spend/outward) step stays PENDING behind its
    approval. Mirrors master.md #4 gate: "approves a plan, asserts task
    leaves PENDING without POST /run"."""
    monkeypatch.setattr(
        "app.services.delegated_goals.DaenaVP", _FakeVP
    )
    tid, uid, _ = await _seed(
        db_session, dept_names=("Engineering", "Marketing")
    )
    svc = DelegatedGoalService(db_session)

    result = await svc.delegate(
        goal="Launch the Q3 growth push", tenant_id=tid, user_id=uid
    )

    by_class = {s["classification"]: s for s in result["steps"]}
    assert set(by_class) == {"free", "outward"}
    free_id = by_class["free"]["task_id"]
    outward_id = by_class["outward"]["task_id"]

    # Exactly the outward step is gated; only the free step was kicked.
    assert result["gated"] == 1
    assert free_id in result["kicked"]
    assert outward_id not in result["kicked"]

    db_session.expire_all()
    tasks = {
        str(t.id): t for t in await _tasks_for_tenant(db_session, tid)
    }
    # Free step left PENDING under autopilot (no explicit run_task call).
    assert tasks[free_id].status != "PENDING"
    # Gated step is untouched -- approval must gate it, never autopilot.
    assert tasks[outward_id].status == "PENDING"

    # And the kick actually drove the free step to a real terminal state.
    assert (
        await _wait_terminal(db_session, uuid.UUID(free_id)) == "COMPLETED"
    )
    db_session.expire_all()
    still_gated = (
        await db_session.execute(
            select(Task).where(Task.id == uuid.UUID(outward_id))
        )
    ).scalar_one()
    assert still_gated.status == "PENDING"


@pytest.mark.asyncio
async def test_sweep_stale_running_marks_failed_on_restart(db_session):
    """Boot recovery: a Task stuck in RUNNING across a process restart is
    swept to FAILED with a truthful error -- never left as a phantom
    RUNNING and never auto-retried (Rule 17 / ADR-001, mirrors the
    BackgroundTask failed_due_to_restart precedent). master.md #4 gate:
    "restart-sim asserts RUNNING -> FAILED(interrupted by restart)"."""
    tid, uid, _ = await _seed(db_session)
    task_id = uuid.uuid4()
    db_session.add(
        Task(
            id=task_id,
            tenant_id=tid,
            user_id=uid,
            name="Interrupted mid-flight",
            description="Was RUNNING when the process died",
            status="RUNNING",
            progress=42,
        )
    )
    await db_session.commit()

    swept = await ExecutionService(db_session).sweep_stale_running_tasks()

    assert swept == 1
    db_session.expire_all()
    row = (
        await db_session.execute(select(Task).where(Task.id == task_id))
    ).scalar_one()
    assert row.status == "FAILED"
    assert row.error == "interrupted by restart"
    assert row.completed_at is not None
