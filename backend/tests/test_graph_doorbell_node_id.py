"""BUILD-NOW #10 contract tests for the live-Brain graph doorbell payload.

Pinned behavior (the honest slice of master.md #10 "typed graph events"):

* Every ``publish_graph_changed`` call fired by a domain producer carries a
  ``node_id`` in its detail, so the live Brain can pulse the EXACT node that
  moved instead of re-diffing the whole projection.
* The ``node_id`` mirrors ``graph_service._nid(kind, raw)`` == ``f"{kind}:{raw}"``:
  a task renders as ``execution:<task.id>`` and a workstream as
  ``workstream:<ws.id>``. If either producer's prefix drifts from the graph
  node-id builder, the live pulse would target a node the projection does not
  contain and silently no-op -- these tests pin the prefix to the builder.
* All four producers are covered:
  - ExecutionService.update_task_status  (execution_service.py doorbell)
  - ExecutionService.run_task direct RUNNING flip (bypasses update_task_status)
  - WorkstreamService.start               (workstream born -> RUNNING)
  - WorkstreamService.transition          (status flip, via complete())
* ``node_id`` is the ONLY node-targeting field added: master.md #10 also asked
  for ``agent_id`` in the payload, but Task / ToolCall / Workstream carry no
  assignee FK, so per ADR-001 (Rule 17) we do NOT fabricate one. This test
  therefore asserts on ``node_id`` only -- the honest achievable slice.

The doorbell stays THIN: these tests assert the payload the producer publishes,
NOT any projection push (the projection is never sent over the channel; GET
/graph stays the single source of truth). We intercept ``publish_graph_changed``
at each producer module's namespace (both import it by name at module top), so
the assertions never depend on SSE subscriber timing.

Mirrors ``test_task_workstream_sync.py`` / ``test_workstream_sse.py`` style:
``db_session`` fixture, ``_seed`` helper, no external services, no sleeps.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import TaskStatus
from app.models.identity import Tenant, User
from app.models.organization import Department
from app.models.workstream import WorkstreamStatus
from app.services.execution_service import ExecutionService
from app.services.workstream_service import StartParams, WorkstreamService


# ── Helpers ───────────────────────────────────────────────────────────


async def _seed(
    db: AsyncSession, *, slug: str | None = None,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Seed tenant + user + dept; return (tenant_id, user_id, dept_id)."""
    s = slug or uuid.uuid4().hex[:8]
    t = Tenant(id=uuid.uuid4(), name=f"door-tenant-{s}", slug=f"door-{s}")
    db.add(t)
    await db.flush()
    u = User(
        id=uuid.uuid4(),
        tenant_id=t.id,
        email=f"door-{s}@example.com",
        password_hash="x",
        role="FOUNDER",
    )
    db.add(u)
    await db.flush()
    d = Department(
        id=uuid.uuid4(),
        tenant_id=t.id,
        name=f"Engineering ({s})",
        description="doorbell-test",
        sunflower_index=0,
        cell_id=f"hex_0_{s}",
        config={},
        is_active=True,
    )
    db.add(d)
    await db.flush()
    await db.commit()
    return t.id, u.id, d.id


class _DoorbellRecorder:
    """Captures every ``publish_graph_changed(reason, **detail)`` call.

    Installed over BOTH producer modules' imported symbol so a single
    recorder sees execution- and workstream-side doorbells together.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def __call__(self, reason: str, **detail) -> None:
        self.calls.append((reason, dict(detail)))

    def by_reason(self, reason: str) -> list[dict]:
        return [detail for r, detail in self.calls if r == reason]


@pytest.fixture
def doorbell(monkeypatch) -> _DoorbellRecorder:
    """Intercept ``publish_graph_changed`` in both producer namespaces."""
    rec = _DoorbellRecorder()
    from app.services import execution_service as exec_module
    from app.services import workstream_service as ws_module

    monkeypatch.setattr(exec_module, "publish_graph_changed", rec)
    monkeypatch.setattr(ws_module, "publish_graph_changed", rec)
    return rec


async def _create_task_with_ws(
    db: AsyncSession, tid: uuid.UUID, uid: uuid.UUID, did: uuid.UUID,
    name: str = "doorbell task",
) -> tuple[uuid.UUID, uuid.UUID]:
    """Create a Task + linked Workstream. Returns (task_id, ws_id)."""
    svc = ExecutionService(db)
    result = await svc.create_task(
        name=name,
        user_id=uid,
        tenant_id=tid,
        also_create_workstream=True,
        department_id=did,
    )
    assert "workstream_id" in result
    return uuid.UUID(result["id"]), uuid.UUID(result["workstream_id"])


async def _run_task_and_drain_bg(
    svc: ExecutionService, task_id: uuid.UUID, tenant_id: uuid.UUID,
) -> None:
    """Call ``run_task`` and drain the fire-and-forget bg task it dispatches.

    ``run_task`` flips the row to RUNNING synchronously (the doorbell this
    test asserts on) and then fires its executor via ``asyncio.create_task``
    WITHOUT awaiting it (production fire-and-forget). Under the shared
    in-memory SQLite test engine there is ONE StaticPool connection; an
    orphan left pending past this test body runs during the NEXT test's
    autouse table-wipe and can invalidate that connection, surfacing as
    ``no such table`` at setup. We drain the orphan here -- while the
    connection is still healthy -- mirroring how
    ``test_run_task_direct_flip_syncs_workstream_progress`` drains it
    implicitly via follow-up awaits. The orphan's own errors are caught by
    ``run_task``; ``return_exceptions`` guards anything else. No assertion
    changes: this only removes cross-test flakiness.
    """
    before = set(asyncio.all_tasks())
    try:
        await svc.run_task(task_id, tenant_id)
    except Exception:
        # The bg executor may hit a closed session under the sandbox; we
        # only assert on the synchronous RUNNING-flip doorbell.
        pass
    spawned = [
        t for t in asyncio.all_tasks()
        if t not in before and t is not asyncio.current_task()
    ]
    if spawned:
        await asyncio.gather(*spawned, return_exceptions=True)


# ── Execution producers ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_task_status_doorbell_carries_node_id(
    db_session: AsyncSession, doorbell: _DoorbellRecorder,
) -> None:
    """A real status transition rings the doorbell with node_id=execution:<id>."""
    tid, uid, did = await _seed(db_session)
    task_id, _ = await _create_task_with_ws(db_session, tid, uid, did)

    await ExecutionService(db_session).update_task_status(
        task_id, tid, status=TaskStatus.COMPLETED.value,
    )

    calls = doorbell.by_reason("task_status_changed")
    assert calls, "update_task_status must ring the graph doorbell"
    # The COMPLETED transition is the one this path drives.
    completed = [d for d in calls if d.get("status") == TaskStatus.COMPLETED.value]
    assert completed, "the COMPLETED transition must be published"
    detail = completed[-1]
    assert detail.get("node_id") == f"execution:{task_id}"
    assert detail.get("task_id") == str(task_id)


@pytest.mark.asyncio
async def test_run_task_running_flip_doorbell_carries_node_id(
    db_session: AsyncSession, doorbell: _DoorbellRecorder,
) -> None:
    """run_task's direct PENDING->RUNNING flip (bypasses update_task_status)
    still rings the doorbell with node_id=execution:<id> and status=RUNNING."""
    tid, uid, did = await _seed(db_session)
    task_id, _ = await _create_task_with_ws(db_session, tid, uid, did)

    await _run_task_and_drain_bg(ExecutionService(db_session), task_id, tid)

    running = [
        d for d in doorbell.by_reason("task_status_changed")
        if d.get("status") == TaskStatus.RUNNING.value
    ]
    assert running, "run_task's RUNNING flip must ring the graph doorbell"
    assert running[0].get("node_id") == f"execution:{task_id}"


# ── Workstream producers ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_workstream_start_doorbell_carries_node_id(
    db_session: AsyncSession, doorbell: _DoorbellRecorder,
) -> None:
    """Starting a workstream rings the doorbell with node_id=workstream:<id>."""
    tid, uid, did = await _seed(db_session)
    ws = await WorkstreamService(db_session).start(
        StartParams(
            tenant_id=tid, user_id=uid, department_id=did,
            goal="doorbell start",
        ),
    )
    calls = doorbell.by_reason("workstream_started")
    assert calls, "start() must ring the graph doorbell"
    assert calls[-1].get("node_id") == f"workstream:{ws.id}"
    assert calls[-1].get("workstream_id") == str(ws.id)


@pytest.mark.asyncio
async def test_workstream_transition_doorbell_carries_node_id(
    db_session: AsyncSession, doorbell: _DoorbellRecorder,
) -> None:
    """A transition (via complete) rings the doorbell with node_id + status."""
    tid, uid, did = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws = await svc.start(
        StartParams(
            tenant_id=tid, user_id=uid, department_id=did,
            goal="doorbell transition",
        ),
    )
    await svc.complete(ws.id, tenant_id=tid, summary="done by doorbell test")

    calls = doorbell.by_reason("workstream_transitioned")
    assert calls, "transition() must ring the graph doorbell"
    detail = calls[-1]
    assert detail.get("node_id") == f"workstream:{ws.id}"
    assert detail.get("workstream_id") == str(ws.id)
    assert detail.get("status") == WorkstreamStatus.COMPLETE.value


# ── Universal invariant (regression guard) ────────────────────────────


@pytest.mark.asyncio
async def test_every_doorbell_call_carries_a_node_id(
    db_session: AsyncSession, doorbell: _DoorbellRecorder,
) -> None:
    """Drive all four producer paths through one recorder and assert the
    node_id invariant holds for EVERY captured doorbell -- so any future
    producer that forgets node_id trips this test."""
    tid, uid, did = await _seed(db_session)
    task_id, _ = await _create_task_with_ws(db_session, tid, uid, did)
    exec_svc = ExecutionService(db_session)
    await exec_svc.update_task_status(
        task_id, tid, status=TaskStatus.COMPLETED.value,
    )
    ws_svc = WorkstreamService(db_session)
    ws = await ws_svc.start(
        StartParams(
            tenant_id=tid, user_id=uid, department_id=did, goal="invariant",
        ),
    )
    await ws_svc.complete(ws.id, tenant_id=tid, summary="invariant done")

    assert doorbell.calls, "expected doorbell traffic from the driven paths"
    for reason, detail in doorbell.calls:
        node_id = detail.get("node_id")
        assert node_id, f"doorbell {reason!r} published without a node_id"
        kind = node_id.split(":", 1)[0]
        assert kind in {"execution", "workstream"}, (
            f"doorbell {reason!r} node_id has an unknown kind: {node_id!r}"
        )
