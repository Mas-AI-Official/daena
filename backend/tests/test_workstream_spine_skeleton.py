"""PR-5 contract tests for the Workstream Execution Spine skeleton.

Pinned behavior:

* New fields (source_type / source_ref_id / progress_percent /
  artifact_refs / audit_event_refs / notification_refs) persist across
  start + reload.
* ``archive()`` sets ``archived_at`` exactly once (idempotent), removes
  the row from list views, and rejects cross-tenant archive attempts.
* ``update_progress`` clamps to 0..100 and never mutates ``status``.
* ``attach_artifact_ref`` / ``attach_audit_event_ref`` /
  ``attach_notification_ref`` append + dedup without losing prior refs.
* ``create_dev_safe_demo`` produces a populated workstream that ends in
  COMPLETE with progress=100 and at least one entry per ref bucket
  the operator demo expects to see.
* ExecutionService.create_task with ``also_create_workstream=True``
  spawns a Workstream shell with source_type=task pointing back at the
  task; default behavior (flag omitted) does NOT spawn a workstream.

Mirrors the existing ``test_workstream_service.py`` style: ``db_session``
fixture, no external services, no sleeps, no wall-clock assertions.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import Tenant, User
from app.models.organization import Department
from app.models.workstream import (
    Workstream,
    WorkstreamSourceType,
    WorkstreamStatus,
)
from app.services.execution_service import ExecutionService
from app.services.workstream_service import (
    StartParams,
    WorkstreamNotFoundError,
    WorkstreamService,
)


# ── Helpers (mirror existing test_workstream_service.py) ──────────────


async def _seed(
    db: AsyncSession, *, slug: str | None = None,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Seed tenant + user + dept; return (tenant_id, user_id, dept_id)."""
    s = slug or uuid.uuid4().hex[:8]
    t = Tenant(id=uuid.uuid4(), name=f"pr5-tenant-{s}", slug=f"pr5-{s}")
    db.add(t)
    await db.flush()
    u = User(
        id=uuid.uuid4(),
        tenant_id=t.id,
        email=f"pr5-{s}@example.com",
        password_hash="x",
        role="FOUNDER",
    )
    db.add(u)
    await db.flush()
    d = Department(
        id=uuid.uuid4(),
        tenant_id=t.id,
        name=f"Engineering ({s})",
        description="pr5-test",
        sunflower_index=0,
        cell_id=f"hex_0_{s}",
        config={},
        is_active=True,
    )
    db.add(d)
    await db.flush()
    await db.commit()
    return t.id, u.id, d.id


# ── New-field persistence ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_new_fields_default_correctly_on_start(
    db_session: AsyncSession,
) -> None:
    """A start() without explicit source attribution lands MANUAL with
    progress=0 and empty ref containers. This is the legacy-caller
    contract -- existing /workstreams POST consumers must not break.
    """
    tid, uid, did = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws = await svc.start(
        StartParams(
            tenant_id=tid,
            user_id=uid,
            department_id=did,
            goal="default-source workstream",
        ),
    )
    assert ws.source_type == WorkstreamSourceType.MANUAL
    assert ws.source_ref_id is None
    assert ws.progress_percent == 0
    assert ws.artifact_refs == {}
    assert ws.audit_event_refs == []
    assert ws.notification_refs == []


@pytest.mark.asyncio
async def test_new_fields_persist_when_explicitly_set(
    db_session: AsyncSession,
) -> None:
    """A start() with explicit source attribution round-trips through
    the DB unchanged -- including the source_ref_id UUID.
    """
    tid, uid, did = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ref = uuid.uuid4()
    ws = await svc.start(
        StartParams(
            tenant_id=tid,
            user_id=uid,
            department_id=did,
            goal="task-sourced workstream",
            source_type=WorkstreamSourceType.TASK,
            source_ref_id=ref,
        ),
    )
    # Re-fetch to confirm the column actually persisted (not just the
    # in-memory object).
    fetched = await svc.get(ws.id, tenant_id=tid)
    assert fetched.source_type == WorkstreamSourceType.TASK
    assert fetched.source_ref_id == ref


# ── Archive ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_archive_sets_archived_at_and_returns_row(
    db_session: AsyncSession,
) -> None:
    """archive() sets archived_at + archived_by, returns the row."""
    tid, uid, did = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws = await svc.start(
        StartParams(
            tenant_id=tid, user_id=uid, department_id=did, goal="to be archived",
        ),
    )
    assert ws.archived_at is None
    archived = await svc.archive(
        ws.id, tenant_id=tid, archived_by_user_id=uid,
    )
    assert archived.archived_at is not None
    assert archived.archived_by == uid


@pytest.mark.asyncio
async def test_archive_is_idempotent(db_session: AsyncSession) -> None:
    """Re-archiving an already-archived workstream is a no-op (no error)."""
    tid, uid, did = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws = await svc.start(
        StartParams(
            tenant_id=tid, user_id=uid, department_id=did, goal="x",
        ),
    )
    first = await svc.archive(ws.id, tenant_id=tid, archived_by_user_id=uid)
    first_at = first.archived_at
    second = await svc.archive(ws.id, tenant_id=tid, archived_by_user_id=uid)
    # Same archived_at: the second call did not stamp a new timestamp.
    assert second.archived_at == first_at


@pytest.mark.asyncio
async def test_archived_workstream_drops_from_list(
    db_session: AsyncSession,
) -> None:
    """list_for_tenant filters out archived rows so the UI surface stays clean."""
    tid, uid, did = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws_keep = await svc.start(
        StartParams(
            tenant_id=tid, user_id=uid, department_id=did, goal="keep me",
        ),
    )
    ws_archive = await svc.start(
        StartParams(
            tenant_id=tid, user_id=uid, department_id=did, goal="archive me",
        ),
    )
    await svc.archive(ws_archive.id, tenant_id=tid, archived_by_user_id=uid)

    items = await svc.list_for_tenant(tid)
    visible_ids = {w.id for w in items}
    assert ws_keep.id in visible_ids
    assert ws_archive.id not in visible_ids


@pytest.mark.asyncio
async def test_archive_cross_tenant_raises_not_found(
    db_session: AsyncSession,
) -> None:
    """Tenant A cannot archive tenant B's workstream.

    Critical isolation guarantee -- the multi-tenant contract is the
    floor that everything else stands on.
    """
    tid_a, uid_a, did_a = await _seed(db_session, slug="tenantA")
    tid_b, _, _ = await _seed(db_session, slug="tenantB")
    svc = WorkstreamService(db_session)
    ws = await svc.start(
        StartParams(
            tenant_id=tid_a, user_id=uid_a, department_id=did_a, goal="A's ws",
        ),
    )
    with pytest.raises(WorkstreamNotFoundError):
        await svc.archive(ws.id, tenant_id=tid_b, archived_by_user_id=uid_a)


# ── Progress + ref helpers ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_progress_clamps_high(
    db_session: AsyncSession,
) -> None:
    """update_progress(150) clamps to 100 (not raise, not store >100)."""
    tid, uid, did = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws = await svc.start(
        StartParams(tenant_id=tid, user_id=uid, department_id=did, goal="x"),
    )
    out = await svc.update_progress(ws.id, tenant_id=tid, percent=150)
    assert out.progress_percent == 100


@pytest.mark.asyncio
async def test_update_progress_clamps_low(
    db_session: AsyncSession,
) -> None:
    """update_progress(-5) clamps to 0."""
    tid, uid, did = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws = await svc.start(
        StartParams(tenant_id=tid, user_id=uid, department_id=did, goal="x"),
    )
    out = await svc.update_progress(ws.id, tenant_id=tid, percent=-5)
    assert out.progress_percent == 0


@pytest.mark.asyncio
async def test_update_progress_does_not_change_status(
    db_session: AsyncSession,
) -> None:
    """progress is informational; the state machine still owns lifecycle."""
    tid, uid, did = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws = await svc.start(
        StartParams(tenant_id=tid, user_id=uid, department_id=did, goal="x"),
    )
    assert ws.status == WorkstreamStatus.RUNNING
    out = await svc.update_progress(ws.id, tenant_id=tid, percent=99)
    assert out.status == WorkstreamStatus.RUNNING


@pytest.mark.asyncio
async def test_attach_artifact_ref_appends_and_dedupes(
    db_session: AsyncSession,
) -> None:
    """attach_artifact_ref appends per kind + dedupes duplicates."""
    tid, uid, did = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws = await svc.start(
        StartParams(tenant_id=tid, user_id=uid, department_id=did, goal="x"),
    )
    await svc.attach_artifact_ref(
        ws.id, tenant_id=tid, kind="file_ids", ref_id="file-1",
    )
    await svc.attach_artifact_ref(
        ws.id, tenant_id=tid, kind="file_ids", ref_id="file-2",
    )
    # Duplicate -- expect single entry.
    await svc.attach_artifact_ref(
        ws.id, tenant_id=tid, kind="file_ids", ref_id="file-1",
    )
    await svc.attach_artifact_ref(
        ws.id, tenant_id=tid, kind="draft_ids", ref_id="draft-1",
    )
    fetched = await svc.get(ws.id, tenant_id=tid)
    assert fetched.artifact_refs["file_ids"] == ["file-1", "file-2"]
    assert fetched.artifact_refs["draft_ids"] == ["draft-1"]


@pytest.mark.asyncio
async def test_attach_audit_event_ref_dedupes(
    db_session: AsyncSession,
) -> None:
    """audit_event_refs appends + dedupes."""
    tid, uid, did = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws = await svc.start(
        StartParams(tenant_id=tid, user_id=uid, department_id=did, goal="x"),
    )
    await svc.attach_audit_event_ref(
        ws.id, tenant_id=tid, audit_event_id="audit-1",
    )
    await svc.attach_audit_event_ref(
        ws.id, tenant_id=tid, audit_event_id="audit-1",
    )
    await svc.attach_audit_event_ref(
        ws.id, tenant_id=tid, audit_event_id="audit-2",
    )
    fetched = await svc.get(ws.id, tenant_id=tid)
    assert fetched.audit_event_refs == ["audit-1", "audit-2"]


@pytest.mark.asyncio
async def test_attach_notification_ref_dedupes(
    db_session: AsyncSession,
) -> None:
    """notification_refs appends + dedupes."""
    tid, uid, did = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws = await svc.start(
        StartParams(tenant_id=tid, user_id=uid, department_id=did, goal="x"),
    )
    await svc.attach_notification_ref(
        ws.id, tenant_id=tid, notification_id="notif-1",
    )
    await svc.attach_notification_ref(
        ws.id, tenant_id=tid, notification_id="notif-1",
    )
    fetched = await svc.get(ws.id, tenant_id=tid)
    assert fetched.notification_refs == ["notif-1"]


# ── Dev-safe demo ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dev_safe_demo_lands_complete_with_progress_100(
    db_session: AsyncSession,
) -> None:
    """create_dev_safe_demo ends in COMPLETE with progress=100.

    The terminal status proves the spine traversal really finished;
    progress=100 proves the runtime helpers wired up correctly.
    """
    tid, uid, did = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws = await svc.create_dev_safe_demo(
        tenant_id=tid, user_id=uid, department_id=did,
    )
    assert ws.status == WorkstreamStatus.COMPLETE
    assert ws.progress_percent == 100


@pytest.mark.asyncio
async def test_dev_safe_demo_uses_dev_demo_source_type(
    db_session: AsyncSession,
) -> None:
    """source_type=DEV_DEMO so the demo is visually distinct in the list."""
    tid, uid, did = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws = await svc.create_dev_safe_demo(
        tenant_id=tid, user_id=uid, department_id=did,
    )
    assert ws.source_type == WorkstreamSourceType.DEV_DEMO


@pytest.mark.asyncio
async def test_dev_safe_demo_populates_artifact_refs(
    db_session: AsyncSession,
) -> None:
    """Demo emits at least one artifact ref so the detail drawer has
    something to render in the artifacts panel."""
    tid, uid, did = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws = await svc.create_dev_safe_demo(
        tenant_id=tid, user_id=uid, department_id=did,
    )
    fetched = await svc.get(ws.id, tenant_id=tid)
    refs = fetched.artifact_refs or {}
    total = sum(len(v) for v in refs.values() if isinstance(v, list))
    assert total >= 1, f"expected at least one artifact ref; got {refs!r}"


# ── Task -> Workstream wiring (PR-5 source) ───────────────────────────


@pytest.mark.asyncio
async def test_task_create_default_does_not_spawn_workstream(
    db_session: AsyncSession,
) -> None:
    """The default create_task call (no flag) leaves workstreams empty.

    Backwards compatibility: every existing /execution/tasks caller
    keeps the legacy behavior.
    """
    tid, uid, did = await _seed(db_session)  # noqa: F841 -- dept seed required even though did unused
    svc = ExecutionService(db_session)
    result = await svc.create_task(
        name="default task",
        user_id=uid,
        tenant_id=tid,
    )
    assert "workstream_id" not in result

    # Confirm the workstreams table actually has nothing.
    rows = (
        await db_session.execute(
            select(Workstream).where(Workstream.tenant_id == tid),
        )
    ).scalars().all()
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_task_create_with_flag_spawns_workstream(
    db_session: AsyncSession,
) -> None:
    """create_task(also_create_workstream=True) spawns a Workstream shell
    pointing back at the task via source_type=TASK + source_ref_id."""
    tid, uid, did = await _seed(db_session)
    svc = ExecutionService(db_session)
    result = await svc.create_task(
        name="task with ws",
        description="should spawn a workstream",
        user_id=uid,
        tenant_id=tid,
        also_create_workstream=True,
        department_id=did,
    )
    assert "workstream_id" in result
    ws_id = uuid.UUID(result["workstream_id"])

    ws_svc = WorkstreamService(db_session)
    ws = await ws_svc.get(ws_id, tenant_id=tid)
    assert ws.source_type == WorkstreamSourceType.TASK
    assert ws.source_ref_id is not None
    # source_ref_id == task.id
    assert str(ws.source_ref_id) == result["id"]
    # Goal mirrors task name; next_step_text mirrors description.
    assert ws.goal == "task with ws"
    assert ws.next_step_text == "should spawn a workstream"


@pytest.mark.asyncio
async def test_task_create_with_flag_falls_back_to_first_active_dept(
    db_session: AsyncSession,
) -> None:
    """When department_id is omitted but flag is True, the spawn falls
    back to the tenant's first active department by sunflower_index.
    """
    tid, uid, did = await _seed(db_session)
    svc = ExecutionService(db_session)
    result = await svc.create_task(
        name="task without dept",
        user_id=uid,
        tenant_id=tid,
        also_create_workstream=True,
        department_id=None,
    )
    assert "workstream_id" in result
    ws_id = uuid.UUID(result["workstream_id"])
    ws_svc = WorkstreamService(db_session)
    ws = await ws_svc.get(ws_id, tenant_id=tid)
    assert ws.department_id == did
