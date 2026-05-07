"""Workstream service contract tests.

Council R6 (2026-04-26) split: deterministic contracts live here so CI
catches regressions; the narrative end-to-end smoke stays at
``backend/scripts/smoke_workstream_service.py`` for operator-driven
sanity checks.

Covered contracts:

  - State machine: legal transitions per ``LEGAL_TRANSITIONS`` table.
  - Illegal transitions raise ``WorkstreamTransitionError``.
  - Terminal states (COMPLETE / FAILED) accept no outgoing transitions.
  - Escalation ladder rejects downward moves.
  - Redirect mutation appends ``redirect_history`` to context.
  - Event log captures the expected kinds in order.
  - Pause/resume toggles ``autopilot_paused`` without changing status.

Uses the existing ``db_session`` fixture from ``conftest.py`` (in-memory
SQLite, transactional rollback per test). No external services. No
sleeps. No wall-clock dependencies.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import Tenant, User
from app.models.organization import Department
from app.models.workstream import (
    WorkstreamEscalationLevel,
    WorkstreamEventKind,
    WorkstreamStatus,
)
from app.services.workstream_service import (
    LEGAL_TRANSITIONS,
    StartParams,
    WorkstreamService,
    WorkstreamTransitionError,
)


# ── Helpers ───────────────────────────────────────────────────────────


async def _seed(db: AsyncSession) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Insert tenant + user + dept; return their ids.

    Matches the smoke script's seed pattern but rolled back per test
    via ``db_session`` fixture transaction.
    """
    slug = uuid.uuid4().hex[:8]
    t = Tenant(
        id=uuid.uuid4(),
        name=f"test-tenant-{slug}",
        slug=f"test-{slug}",
    )
    db.add(t)
    await db.flush()
    u = User(
        id=uuid.uuid4(),
        tenant_id=t.id,
        email=f"test-{slug}@example.com",
        password_hash="x",
        role="FOUNDER",
    )
    db.add(u)
    await db.flush()
    d = Department(
        id=uuid.uuid4(),
        tenant_id=t.id,
        name=f"Engineering ({slug})",
        description="contract-test",
        sunflower_index=0,
        cell_id="hex_0",
        config={},
        is_active=True,
    )
    db.add(d)
    await db.flush()
    await db.commit()
    return t.id, u.id, d.id


async def _start(svc: WorkstreamService, tid, uid, did, goal="contract test"):
    """Start a workstream with sensible defaults."""
    return await svc.start(
        StartParams(
            tenant_id=tid,
            user_id=uid,
            department_id=did,
            goal=goal,
        ),
    )


# ── Tests ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_start_creates_running_workstream(db_session: AsyncSession) -> None:
    """A new workstream starts in RUNNING with STANDARD escalation."""
    tid, uid, did = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws = await _start(svc, tid, uid, did, goal="ship the contract test")
    assert ws.status == WorkstreamStatus.RUNNING
    assert ws.escalation_level == WorkstreamEscalationLevel.STANDARD
    assert ws.goal == "ship the contract test"
    assert ws.autopilot_paused is False


@pytest.mark.asyncio
async def test_legal_transition_table_consistency(db_session: AsyncSession) -> None:
    """Every state has either an outgoing transition set OR is terminal.

    Terminal contract: COMPLETE and FAILED have empty transition sets.
    """
    assert LEGAL_TRANSITIONS[WorkstreamStatus.COMPLETE] == set()
    assert LEGAL_TRANSITIONS[WorkstreamStatus.FAILED] == set()
    assert WorkstreamStatus.RUNNING in LEGAL_TRANSITIONS
    assert WorkstreamStatus.BLOCKED in LEGAL_TRANSITIONS
    assert WorkstreamStatus.WAITING_APPROVAL in LEGAL_TRANSITIONS


@pytest.mark.asyncio
async def test_running_to_waiting_approval_then_back(db_session: AsyncSession) -> None:
    """Standard flow: RUNNING -> WAITING_APPROVAL (granted) -> RUNNING."""
    tid, uid, did = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws = await _start(svc, tid, uid, did)
    ws2 = await svc.transition(
        ws.id, WorkstreamStatus.WAITING_APPROVAL,
        tenant_id=tid, reason="tier 3 tool call queued",
    )
    assert ws2.status == WorkstreamStatus.WAITING_APPROVAL
    ws3 = await svc.transition(
        ws.id, WorkstreamStatus.RUNNING,
        tenant_id=tid, reason="approval granted",
    )
    assert ws3.status == WorkstreamStatus.RUNNING


@pytest.mark.asyncio
async def test_terminal_states_refuse_outgoing_transitions(db_session: AsyncSession) -> None:
    """COMPLETE -> RUNNING must raise WorkstreamTransitionError.

    Council R3 lock: terminal states are terminal. The illegal-block
    guard is the safety net for runaway autopilot loops.
    """
    tid, uid, did = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws = await _start(svc, tid, uid, did)
    await svc.complete(ws.id, tenant_id=tid, summary="done")
    with pytest.raises(WorkstreamTransitionError):
        await svc.transition(
            ws.id, WorkstreamStatus.RUNNING,
            tenant_id=tid, reason="should be refused",
        )


@pytest.mark.asyncio
async def test_escalate_only_moves_up_the_ladder(db_session: AsyncSession) -> None:
    """Escalate raises on attempts to lower the level.

    STANDARD -> COUNCIL is allowed (skipping HIGH_EFFORT — explicit jump).
    COUNCIL -> STANDARD is refused (use a separate downgrade path when
    that's implemented).
    """
    tid, uid, did = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws = await _start(svc, tid, uid, did)
    ws2 = await svc.escalate(
        ws.id, tenant_id=tid,
        new_level=WorkstreamEscalationLevel.COUNCIL,
        reason="founder asked",
    )
    assert ws2.escalation_level == WorkstreamEscalationLevel.COUNCIL
    with pytest.raises(WorkstreamTransitionError):
        await svc.escalate(
            ws.id, tenant_id=tid,
            new_level=WorkstreamEscalationLevel.STANDARD,
            reason="downgrade not allowed via escalate()",
        )


@pytest.mark.asyncio
async def test_pause_resume_toggles_flag_without_status_change(db_session: AsyncSession) -> None:
    """autopilot_paused is independent of status.

    The Council R3 lock distinguishes "is this workstream healthy" (status)
    from "is the system autonomously continuing it" (autopilot_paused).
    """
    tid, uid, did = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws = await _start(svc, tid, uid, did)
    assert ws.autopilot_paused is False
    paused = await svc.pause_autopilot(ws.id, tenant_id=tid)
    assert paused.autopilot_paused is True
    assert paused.status == WorkstreamStatus.RUNNING  # status unchanged
    resumed = await svc.resume_autopilot(ws.id, tenant_id=tid)
    assert resumed.autopilot_paused is False
    assert resumed.status == WorkstreamStatus.RUNNING


@pytest.mark.asyncio
async def test_redirect_appends_history_to_context(db_session: AsyncSession) -> None:
    """Redirect must append a structured entry to context.redirect_history.

    Append-only history is what makes the Workstreams Live Console
    timeline trustworthy — never mutate, always append.
    """
    tid, uid, did = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws = await _start(svc, tid, uid, did, goal="original goal")
    await svc.redirect(
        ws.id, tenant_id=tid,
        new_goal="new goal",
        scope_constraints=["only python files", "skip tests"],
        raw_instruction="make it about python only and skip tests",
    )
    # Re-fetch to get committed state.
    ws2 = await svc.get(ws.id, tenant_id=tid)
    assert ws2.goal == "new goal"
    history = ws2.context.get("redirect_history") or []
    assert len(history) == 1
    assert history[0]["from_goal"] == "original goal"
    assert history[0]["to_goal"] == "new goal"
    assert "only python files" in history[0]["scope_constraints"]


@pytest.mark.asyncio
async def test_event_timeline_in_order(db_session: AsyncSession) -> None:
    """Event log captures the expected kinds in chronological order.

    Smoke script's 7-event timeline contract — promoted to pytest per
    Council R6 #3 conclusion (Option C).
    """
    tid, uid, did = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws = await _start(svc, tid, uid, did)
    await svc.transition(
        ws.id, WorkstreamStatus.WAITING_APPROVAL,
        tenant_id=tid, reason="tier 3",
    )
    await svc.transition(
        ws.id, WorkstreamStatus.RUNNING,
        tenant_id=tid, reason="approved",
    )
    await svc.escalate(
        ws.id, tenant_id=tid,
        new_level=WorkstreamEscalationLevel.COUNCIL,
        reason="founder asked",
    )
    await svc.redirect(
        ws.id, tenant_id=tid,
        new_goal=None,
        scope_constraints=["narrowed"],
        raw_instruction="only narrow",
    )
    await svc.pause_autopilot(ws.id, tenant_id=tid)
    await svc.complete(ws.id, tenant_id=tid, summary="done")

    events = await svc.list_events(ws.id, tenant_id=tid)
    kinds = [e.kind for e in events]
    expected = [
        WorkstreamEventKind.STARTED,
        WorkstreamEventKind.APPROVAL_REQUESTED,
        WorkstreamEventKind.UNBLOCKED,         # WAITING_APPROVAL -> RUNNING
        WorkstreamEventKind.ESCALATED,
        WorkstreamEventKind.REDIRECTED,
        WorkstreamEventKind.PAUSED,
        WorkstreamEventKind.COMPLETED,
    ]
    for k in expected:
        assert k in kinds, f"missing event kind: {k.value}; got {[x.value for x in kinds]}"
    # Ordering: STARTED first, COMPLETED last.
    assert kinds[0] == WorkstreamEventKind.STARTED
    assert kinds[-1] == WorkstreamEventKind.COMPLETED


@pytest.mark.asyncio
async def test_redirect_parser_validates_conflicts(db_session: AsyncSession) -> None:
    """The redirect parser's deterministic validation layer (Council R5)
    catches conflicting actions and emits a clarification.

    This test exercises the validator directly rather than the LLM call,
    so it works without a live LLM provider in the test sandbox.
    """
    from app.services.workstream_redirect_parser import (
        RedirectAction,
        RedirectActionKind,
        _build_clarification_for_errors,
        _validate_actions,
    )
    actions = [
        RedirectAction(kind=RedirectActionKind.PAUSE_AUTOPILOT),
        RedirectAction(kind=RedirectActionKind.RESUME_AUTOPILOT),
    ]
    errs = _validate_actions(actions)
    assert any("conflict" in e for e in errs), f"expected conflict; got {errs}"
    msg = _build_clarification_for_errors(actions, errs, "pause and resume")
    assert "PAUSE_AUTOPILOT" in msg or "RESUME_AUTOPILOT" in msg


@pytest.mark.asyncio
async def test_redirect_parser_validates_cancel_solo(db_session: AsyncSession) -> None:
    """CANCEL combined with another action triggers risk gating.

    Council R5 / R6: CANCEL is terminal + irreversible; never apply on
    LLM strength alone.
    """
    from app.services.workstream_redirect_parser import (
        RedirectAction,
        RedirectActionKind,
        _validate_actions,
    )
    actions = [
        RedirectAction(kind=RedirectActionKind.CANCEL),
        RedirectAction(kind=RedirectActionKind.NARROW_SCOPE,
                       payload={"constraint": "x"}),
    ]
    errs = _validate_actions(actions)
    assert any("risk" in e for e in errs), f"expected risk error; got {errs}"


@pytest.mark.asyncio
async def test_redirect_parser_schema_missing_constraint(db_session: AsyncSession) -> None:
    """NARROW_SCOPE without `constraint` payload fails schema validation."""
    from app.services.workstream_redirect_parser import (
        RedirectAction,
        RedirectActionKind,
        _validate_actions,
    )
    actions = [RedirectAction(kind=RedirectActionKind.NARROW_SCOPE, payload={})]
    errs = _validate_actions(actions)
    assert any("schema" in e for e in errs), f"expected schema error; got {errs}"
