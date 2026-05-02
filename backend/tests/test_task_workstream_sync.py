"""PR-SPINE-04 contract tests for task -> workstream status sync.

Pinned behavior:

* When a task with a linked Workstream (via PR-5
  ``source_type=TASK + source_ref_id=task.id`` OR PR-SCAN-WS-01
  ``source_type=SCAN + artifact_refs.task_ids contains task.id``)
  transitions status, the Workstream lifecycle mirrors the change:
  - RUNNING  -> Workstream stays RUNNING with progress >= 25
  - COMPLETED -> Workstream COMPLETE with progress = 100
  - FAILED  / CANCELLED -> Workstream FAILED
  - PENDING / PAUSED -> no transition; only timeline event
* A task without any linked Workstream is unaffected by sync (no-op).
* Cross-tenant isolation: a task in tenant A does not affect a Workstream
  in tenant B even if their ids collide structurally.
* Terminal Workstreams (COMPLETE / FAILED) are NOT re-flipped by a
  later task status change. Idempotent.
* The DECISION timeline event is emitted on every status change (even
  PENDING/PAUSED no-ops) with payload.kind=task_status_changed so the
  operator can see the cause regardless of state outcome.
* The lookup helper covers BOTH link shapes: direct TASK source and
  SCAN-sourced via artifact_refs.task_ids.

Mirrors the existing sync test fixture style (db_session + _seed
helper). No external services. No sleeps. No SSE assertions yet -
PR-SPINE-04+ adds the SSE channel; this PR is refresh-only.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import TaskStatus
from app.models.identity import Tenant, User
from app.models.organization import Department
from app.models.workstream import (
    WorkstreamEventKind,
    WorkstreamSourceType,
    WorkstreamStatus,
)
from app.services.execution_service import ExecutionService
from app.services.workstream_service import (
    StartParams,
    WorkstreamService,
    find_workstream_linked_to_task,
)


# ── Helpers ───────────────────────────────────────────────────────────


async def _seed(
    db: AsyncSession, *, slug: str | None = None,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Seed tenant + user + dept. Slugs prefixed so cross-test commits
    do not collide on the unique tenants.slug constraint.
    """
    s = slug or uuid.uuid4().hex[:8]
    t = Tenant(id=uuid.uuid4(), name=f"sync-tenant-{s}", slug=f"sync-{s}")
    db.add(t)
    await db.flush()
    u = User(
        id=uuid.uuid4(),
        tenant_id=t.id,
        email=f"sync-{s}@example.com",
        password_hash="x",
        role="FOUNDER",
    )
    db.add(u)
    await db.flush()
    d = Department(
        id=uuid.uuid4(),
        tenant_id=t.id,
        name=f"Engineering ({s})",
        description="sync-test",
        sunflower_index=0,
        cell_id=f"hex_0_{s}",
        config={},
        is_active=True,
    )
    db.add(d)
    await db.flush()
    await db.commit()
    return t.id, u.id, d.id


async def _create_task_with_ws(
    db: AsyncSession, tid: uuid.UUID, uid: uuid.UUID, did: uuid.UUID,
    name: str = "linked task",
) -> tuple[uuid.UUID, uuid.UUID]:
    """Create a Task with also_create_workstream=True. Returns (task_id, ws_id)."""
    svc = ExecutionService(db)
    result = await svc.create_task(
        name=name,
        user_id=uid,
        tenant_id=tid,
        also_create_workstream=True,
        department_id=did,
    )
    assert "workstream_id" in result, "spawn must produce a workstream"
    return uuid.UUID(result["id"]), uuid.UUID(result["workstream_id"])


# ── find_workstream_linked_to_task ────────────────────────────────────


@pytest.mark.asyncio
async def test_find_linked_workstream_via_direct_task_source(
    db_session: AsyncSession,
) -> None:
    """The direct TASK -> Workstream link (PR-5) is found by source_ref_id."""
    tid, uid, did = await _seed(db_session)
    task_id, ws_id = await _create_task_with_ws(db_session, tid, uid, did)
    found = await find_workstream_linked_to_task(
        db_session, tenant_id=tid, task_id=task_id,
    )
    assert found is not None
    assert found.id == ws_id
    assert found.source_type == WorkstreamSourceType.TASK


@pytest.mark.asyncio
async def test_find_linked_workstream_via_scan_artifact_refs(
    db_session: AsyncSession,
) -> None:
    """The PR-SCAN-WS-01 indirect link via artifact_refs.task_ids is found."""
    tid, uid, did = await _seed(db_session)
    # Create a Workstream as if it were spawned by scan remediation:
    # source_type=SCAN, artifact_refs.task_ids containing a task id.
    ws_svc = WorkstreamService(db_session)
    ws = await ws_svc.start(
        StartParams(
            tenant_id=tid, user_id=uid, department_id=did,
            goal="scan remediation",
            source_type=WorkstreamSourceType.SCAN,
            source_ref_id=None,  # scan_id is a string, not UUID
        ),
    )
    fake_task_id = uuid.uuid4()
    await ws_svc.attach_artifact_ref(
        ws.id, tenant_id=tid,
        kind="task_ids", ref_id=str(fake_task_id), emit_event=False,
    )
    # Now the lookup should find it via artifact_refs path.
    found = await find_workstream_linked_to_task(
        db_session, tenant_id=tid, task_id=fake_task_id,
    )
    assert found is not None
    assert found.id == ws.id


@pytest.mark.asyncio
async def test_find_linked_workstream_returns_none_when_unlinked(
    db_session: AsyncSession,
) -> None:
    """A task with no linked Workstream returns None (not an error)."""
    tid, _, _ = await _seed(db_session)
    found = await find_workstream_linked_to_task(
        db_session, tenant_id=tid, task_id=uuid.uuid4(),
    )
    assert found is None


@pytest.mark.asyncio
async def test_find_linked_workstream_skips_archived(
    db_session: AsyncSession,
) -> None:
    """Archived workstreams must NOT be returned. A soft-deleted spine
    artifact should not silently come back to life when the task that
    used to live in it finally completes.
    """
    tid, uid, did = await _seed(db_session)
    task_id, ws_id = await _create_task_with_ws(db_session, tid, uid, did)
    ws_svc = WorkstreamService(db_session)
    await ws_svc.archive(ws_id, tenant_id=tid, archived_by_user_id=uid)
    found = await find_workstream_linked_to_task(
        db_session, tenant_id=tid, task_id=task_id,
    )
    assert found is None


# ── Status sync via update_task_status ────────────────────────────────


@pytest.mark.asyncio
async def test_task_completed_flips_workstream_complete(
    db_session: AsyncSession,
) -> None:
    """Task COMPLETED -> Workstream COMPLETE with progress=100 + timeline."""
    tid, uid, did = await _seed(db_session)
    task_id, ws_id = await _create_task_with_ws(db_session, tid, uid, did)
    svc = ExecutionService(db_session)
    await svc.update_task_status(
        task_id, tid, status=TaskStatus.COMPLETED.value,
    )
    ws_svc = WorkstreamService(db_session)
    ws = await ws_svc.get(ws_id, tenant_id=tid)
    assert ws.status == WorkstreamStatus.COMPLETE
    assert ws.progress_percent == 100


@pytest.mark.asyncio
async def test_task_failed_flips_workstream_failed(
    db_session: AsyncSession,
) -> None:
    """Task FAILED -> Workstream FAILED with the reason carried through."""
    tid, uid, did = await _seed(db_session)
    task_id, ws_id = await _create_task_with_ws(db_session, tid, uid, did)
    svc = ExecutionService(db_session)
    await svc.update_task_status(
        task_id, tid,
        status=TaskStatus.FAILED.value,
        error="provider returned 503",
    )
    ws_svc = WorkstreamService(db_session)
    ws = await ws_svc.get(ws_id, tenant_id=tid)
    assert ws.status == WorkstreamStatus.FAILED
    # Look for the FAILED transition event with the reason text.
    events = await ws_svc.list_events(ws_id, tenant_id=tid)
    failed_events = [
        e for e in events if e.kind == WorkstreamEventKind.FAILED
    ]
    assert len(failed_events) >= 1
    assert "provider returned 503" in failed_events[-1].summary


@pytest.mark.asyncio
async def test_task_running_bumps_workstream_progress(
    db_session: AsyncSession,
) -> None:
    """Task RUNNING -> Workstream stays RUNNING but progress hits >=25.

    The workstream was spawned in RUNNING by ``create_task``, so this
    sync path never re-transitions; it only bumps progress to give the
    operator a visible "the task started" signal.
    """
    tid, uid, did = await _seed(db_session)
    task_id, ws_id = await _create_task_with_ws(db_session, tid, uid, did)
    ws_svc = WorkstreamService(db_session)
    ws_before = await ws_svc.get(ws_id, tenant_id=tid)
    assert ws_before.progress_percent == 0  # nothing has happened yet

    svc = ExecutionService(db_session)
    await svc.update_task_status(
        task_id, tid, status=TaskStatus.RUNNING.value,
    )
    ws_after = await ws_svc.get(ws_id, tenant_id=tid)
    assert ws_after.status == WorkstreamStatus.RUNNING  # unchanged
    assert ws_after.progress_percent >= 25


@pytest.mark.asyncio
async def test_task_paused_emits_timeline_no_transition(
    db_session: AsyncSession,
) -> None:
    """Task PAUSED -> Workstream status untouched but a DECISION event
    lands so the operator sees the cause on the timeline.
    """
    tid, uid, did = await _seed(db_session)
    task_id, ws_id = await _create_task_with_ws(db_session, tid, uid, did)
    svc = ExecutionService(db_session)
    await svc.update_task_status(
        task_id, tid, status=TaskStatus.PAUSED.value,
    )
    ws_svc = WorkstreamService(db_session)
    ws = await ws_svc.get(ws_id, tenant_id=tid)
    assert ws.status == WorkstreamStatus.RUNNING  # NOT transitioned
    events = await ws_svc.list_events(ws_id, tenant_id=tid)
    decisions = [
        e for e in events
        if e.kind == WorkstreamEventKind.DECISION
        and e.payload.get("kind") == "task_status_changed"
    ]
    assert len(decisions) == 1
    assert decisions[0].payload["to_status"] == "PAUSED"


# ── No-op + idempotency paths ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_task_without_workstream_unaffected(
    db_session: AsyncSession,
) -> None:
    """Default create_task (also_create_workstream=False) leaves no link;
    subsequent status changes touch nothing on the workstream side.
    """
    tid, uid, _ = await _seed(db_session)
    svc = ExecutionService(db_session)
    result = await svc.create_task(
        name="lone task", user_id=uid, tenant_id=tid,
    )
    assert "workstream_id" not in result
    task_id = uuid.UUID(result["id"])

    # Cycle through a full lifecycle. Each call would have raised if
    # the sync helper didn't gracefully handle "no linked workstream".
    await svc.update_task_status(task_id, tid, status=TaskStatus.RUNNING.value)
    await svc.update_task_status(task_id, tid, status=TaskStatus.COMPLETED.value)

    # Confirm: zero workstreams exist for this tenant.
    ws_svc = WorkstreamService(db_session)
    items = await ws_svc.list_for_tenant(tid)
    assert items == []


@pytest.mark.asyncio
async def test_terminal_workstream_not_retransitioned(
    db_session: AsyncSession,
) -> None:
    """Once a workstream has reached COMPLETE / FAILED, a later task
    status change must NOT raise and must NOT re-flip the workstream.
    """
    tid, uid, did = await _seed(db_session)
    task_id, ws_id = await _create_task_with_ws(db_session, tid, uid, did)
    svc = ExecutionService(db_session)

    # First flip the task to COMPLETED so the workstream is COMPLETE.
    await svc.update_task_status(task_id, tid, status=TaskStatus.COMPLETED.value)
    ws_svc = WorkstreamService(db_session)
    ws = await ws_svc.get(ws_id, tenant_id=tid)
    assert ws.status == WorkstreamStatus.COMPLETE

    # Now flip the task to FAILED. The workstream is terminal; sync must
    # not raise WorkstreamTransitionError into the task path.
    await svc.update_task_status(task_id, tid, status=TaskStatus.FAILED.value)
    ws_after = await ws_svc.get(ws_id, tenant_id=tid)
    # Workstream remains COMPLETE; the task's terminal status is its own.
    assert ws_after.status == WorkstreamStatus.COMPLETE


@pytest.mark.asyncio
async def test_status_unchanged_does_not_emit_sync_event(
    db_session: AsyncSession,
) -> None:
    """Calling update_task_status with the same status that the task is
    already in should NOT emit a sync event (no change, no marker).
    """
    tid, uid, did = await _seed(db_session)
    task_id, ws_id = await _create_task_with_ws(db_session, tid, uid, did)
    svc = ExecutionService(db_session)
    ws_svc = WorkstreamService(db_session)
    events_before = await ws_svc.list_events(ws_id, tenant_id=tid)
    sync_events_before = [
        e for e in events_before
        if e.payload.get("kind") == "task_status_changed"
    ]
    # Re-write the same PENDING -> PENDING (idempotent).
    await svc.update_task_status(task_id, tid, status=TaskStatus.PENDING.value)
    events_after = await ws_svc.list_events(ws_id, tenant_id=tid)
    sync_events_after = [
        e for e in events_after
        if e.payload.get("kind") == "task_status_changed"
    ]
    assert len(sync_events_after) == len(sync_events_before)


# ── Tenant isolation ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cross_tenant_task_does_not_sync_other_tenants_workstream(
    db_session: AsyncSession,
) -> None:
    """A task in tenant A whose id collides with a SCAN-sourced
    workstream's artifact_refs.task_ids in tenant B does NOT sync the
    tenant-B workstream. The lookup is tenant-scoped.
    """
    tid_a, uid_a, did_a = await _seed(db_session, slug="syncA")
    tid_b, uid_b, did_b = await _seed(db_session, slug="syncB")

    # Create a real Task in tenant A.
    svc_a = ExecutionService(db_session)
    task_dict = await svc_a.create_task(
        name="A's task", user_id=uid_a, tenant_id=tid_a,
        also_create_workstream=False,  # no workstream
    )
    task_id = uuid.UUID(task_dict["id"])

    # Create a SCAN-sourced workstream in tenant B that erroneously
    # references A's task id in its artifact_refs.
    ws_svc = WorkstreamService(db_session)
    ws_b = await ws_svc.start(
        StartParams(
            tenant_id=tid_b, user_id=uid_b, department_id=did_b,
            goal="B's scan remediation",
            source_type=WorkstreamSourceType.SCAN,
        ),
    )
    await ws_svc.attach_artifact_ref(
        ws_b.id, tenant_id=tid_b,
        kind="task_ids", ref_id=str(task_id), emit_event=False,
    )

    # Tenant-A task transitions COMPLETED. Tenant-B workstream MUST NOT
    # flip.
    await svc_a.update_task_status(
        task_id, tid_a, status=TaskStatus.COMPLETED.value,
    )
    ws_b_after = await ws_svc.get(ws_b.id, tenant_id=tid_b)
    assert ws_b_after.status == WorkstreamStatus.RUNNING


# ── Run-task path (direct RUNNING flip bypasses update_task_status) ──


@pytest.mark.asyncio
async def test_run_task_direct_flip_syncs_workstream_progress(
    db_session: AsyncSession,
) -> None:
    """ExecutionService.run_task does the initial RUNNING flip directly
    on the ORM (bypassing update_task_status) and then dispatches a bg
    task that uses update_task_status. The PR-SPINE-04 wiring must hook
    that direct flip too so the linked workstream's progress >= 25 after
    a synchronous run_task() call (the bg task may not have completed
    yet under test).
    """
    tid, uid, did = await _seed(db_session)
    task_id, ws_id = await _create_task_with_ws(db_session, tid, uid, did)
    svc = ExecutionService(db_session)

    # Synchronous part of run_task: flips task to RUNNING + sync.
    # The bg simulator fires asyncio.create_task which is not awaited
    # synchronously here; we only assert on the post-flip workstream
    # state.
    try:
        await svc.run_task(task_id, tid)
    except Exception:
        # The bg task may try to use a closed session in the test
        # sandbox; we only care about the synchronous side effects
        # (task flipped to RUNNING + workstream progress synced).
        pass
    ws_svc = WorkstreamService(db_session)
    ws = await ws_svc.get(ws_id, tenant_id=tid)
    assert ws.status == WorkstreamStatus.RUNNING
    assert ws.progress_percent >= 25
