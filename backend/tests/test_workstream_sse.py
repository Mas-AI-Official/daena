"""PR-SPINE-06 contract tests for the Workstream live console SSE.

Pinned behavior:

* ``get_workstream_channel`` returns the same SSEChannel instance for
  the same id (so publishers and subscribers meet on the same queue),
  and a fresh channel for a different id (so workstreams stay isolated).
* ``WorkstreamService.start`` publishes a ``workstream.event`` envelope
  carrying both the new STARTED event and a slim snapshot.
* ``transition`` (and its wrappers ``complete``, ``fail``) publish
  ``workstream.event`` with the destination status visible inside the
  snapshot.
* ``update_progress``, ``attach_audit_event_ref``, and
  ``attach_notification_ref`` publish ``workstream.snapshot`` (no
  ``event`` key, since they do NOT append a timeline entry).
* ``attach_artifact_ref`` publishes a ``workstream.event`` when
  ``emit_event=True`` (the default) and a ``workstream.snapshot`` when
  the caller opted out.
* ``archive`` publishes a snapshot with ``archived_at`` set so a live
  drawer can detach.
* SSE publishing is best-effort: a channel failure does NOT break the
  service contract (workstream still mutates + commits).
* The slim serializers expose the fields the frontend renders without
  leaking immutable plumbing.

No FastAPI client is exercised here -- the SSE route is a thin glue
layer (~30 LOC) over the channel + serializers. The service-level
contract is what actually carries the live-console semantics, and these
tests cover it.

Mirrors the existing ``test_workstream_service.py`` style: ``db_session``
fixture, no external services, no sleeps, no wall-clock assertions.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.sse_channels import (
    SSEChannel,
    get_workstream_channel,
    workstream_channel_count,
)
from app.models.identity import Tenant, User
from app.models.organization import Department
from app.models.workstream import (
    WorkstreamEscalationLevel,
    WorkstreamSourceType,
    WorkstreamStatus,
)
from app.services.workstream_service import (
    StartParams,
    WorkstreamService,
    _slim_event,
    _slim_snapshot,
)


# ── Helpers ───────────────────────────────────────────────────────────


async def _seed(
    db: AsyncSession, *, slug: str | None = None,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Seed tenant + user + dept; return (tenant_id, user_id, dept_id)."""
    s = slug or uuid.uuid4().hex[:8]
    t = Tenant(id=uuid.uuid4(), name=f"sse-tenant-{s}", slug=f"sse-{s}")
    db.add(t)
    await db.flush()
    u = User(
        id=uuid.uuid4(),
        tenant_id=t.id,
        email=f"sse-{s}@example.com",
        password_hash="x",
        role="FOUNDER",
    )
    db.add(u)
    await db.flush()
    d = Department(
        id=uuid.uuid4(),
        tenant_id=t.id,
        name=f"Engineering ({s})",
        description="sse-test",
        sunflower_index=0,
        cell_id=f"hex_0_{s}",
        config={},
        is_active=True,
    )
    db.add(d)
    await db.flush()
    await db.commit()
    return t.id, u.id, d.id


async def _drain_envelopes(
    channel: SSEChannel,
    *,
    count: int,
    timeout: float = 0.5,
    ready: asyncio.Event | None = None,
) -> list[dict]:
    """Subscribe, wait for ``count`` envelopes (skipping pings), return them.

    The channel sends a ``ping`` envelope every 25s of idle time. Tests
    typically receive the publish within ~10ms so we never see a ping;
    this filter is defensive in case a slow CI runner stretches that.

    ``ready`` is set immediately after the subscriber registers its queue
    so the producer side can wait for confirmation instead of guessing
    at how many ``await`` boundaries the consumer needs to traverse.
    """
    received: list[dict] = []
    iterator = channel.subscribe()
    signaled = False

    async def _consume() -> None:
        nonlocal signaled
        async for envelope in iterator:
            if not signaled and ready is not None:
                ready.set()
                signaled = True
            if envelope.get("type") == "ping":
                continue
            received.append(envelope)
            if len(received) >= count:
                return

    try:
        await asyncio.wait_for(_consume(), timeout=timeout)
    except asyncio.TimeoutError:
        # Surface what we got so the assertion failure is informative.
        pass
    finally:
        try:
            await iterator.aclose()
        except Exception:
            pass
    return received


async def _wait_subscribed(
    channel: SSEChannel, *, timeout: float = 0.5,
) -> None:
    """Spin until ``channel.subscriber_count()`` >= 1 or timeout.

    Cheaper than threading a ready-event everywhere; the channel exposes
    its subscriber count synchronously so we can poll without a lock.
    """
    deadline = asyncio.get_event_loop().time() + timeout
    while channel.subscriber_count() == 0:
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError("subscriber never registered")
        await asyncio.sleep(0.005)


# ── Channel registry contracts ────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_workstream_channel_returns_same_instance_for_same_id():
    """Two callers asking for the same workstream id share a channel."""
    ws_id = str(uuid.uuid4())
    a = await get_workstream_channel(ws_id)
    b = await get_workstream_channel(ws_id)
    assert a is b
    assert a.name == f"workstream:{ws_id}"


@pytest.mark.asyncio
async def test_get_workstream_channel_returns_distinct_for_distinct_ids():
    """Different workstreams get isolated channels."""
    id_a, id_b = str(uuid.uuid4()), str(uuid.uuid4())
    a = await get_workstream_channel(id_a)
    b = await get_workstream_channel(id_b)
    assert a is not b
    assert a.name != b.name


@pytest.mark.asyncio
async def test_get_workstream_channel_concurrent_creation_is_safe():
    """Race between two concurrent first-misses on the same id resolves
    to a single channel; the loser's would-be orphan is prevented by the
    re-check inside the lock."""
    ws_id = str(uuid.uuid4())
    results = await asyncio.gather(
        get_workstream_channel(ws_id),
        get_workstream_channel(ws_id),
        get_workstream_channel(ws_id),
        get_workstream_channel(ws_id),
    )
    assert all(r is results[0] for r in results)


@pytest.mark.asyncio
async def test_workstream_channel_count_grows_with_unique_ids():
    """Sanity check on the introspection helper."""
    before = workstream_channel_count()
    await get_workstream_channel(str(uuid.uuid4()))
    await get_workstream_channel(str(uuid.uuid4()))
    after = workstream_channel_count()
    assert after >= before + 2


# ── Slim serializer contracts ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_slim_snapshot_exposes_mutable_fields(db_session: AsyncSession):
    """The slim snapshot ships the fields the frontend updates live."""
    tenant_id, user_id, dept_id = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws = await svc.start(
        StartParams(
            tenant_id=tenant_id, user_id=user_id, department_id=dept_id,
            goal="slim snapshot test",
        ),
    )
    snap = _slim_snapshot(ws)
    expected_keys = {
        "id", "status", "escalation_level", "progress_percent",
        "blocker_text", "next_step_text", "autopilot_paused",
        "last_activity_at", "archived_at", "artifact_refs",
        "audit_event_refs", "notification_refs", "total_tokens",
        "total_cost_cents", "goal",
    }
    assert expected_keys.issubset(snap.keys())
    assert snap["status"] == WorkstreamStatus.RUNNING.value
    assert snap["progress_percent"] == 0
    assert snap["archived_at"] is None
    assert snap["goal"] == "slim snapshot test"


@pytest.mark.asyncio
async def test_slim_event_renders_id_kind_summary_payload(
    db_session: AsyncSession,
):
    """The slim event matches what the timeline render expects."""
    tenant_id, user_id, dept_id = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws = await svc.start(
        StartParams(
            tenant_id=tenant_id, user_id=user_id, department_id=dept_id,
            goal="slim event test",
        ),
    )
    events = await svc.list_events(ws.id, tenant_id=tenant_id)
    assert events, "start() must emit a STARTED timeline event"
    slim = _slim_event(events[0])
    assert set(slim.keys()) == {"id", "kind", "summary", "payload", "occurred_at"}
    assert slim["kind"] == "STARTED"
    assert "slim event test" in slim["summary"]


# ── State-change publishing contracts ─────────────────────────────────


@pytest.mark.asyncio
async def test_start_publishes_workstream_event(
    db_session: AsyncSession, monkeypatch,
):
    """Creating a workstream emits a ``workstream.event`` with snapshot.

    The lifecycle race (workstream id is unknown until ``start`` returns,
    but ``start`` publishes immediately after commit) means a normal
    subscriber would miss the very first event. We solve this in the
    route via the ``workstream.bootstrap`` envelope; here we record the
    publish via a monkey-patched channel factory so the test does not
    depend on subscriber timing at all.
    """
    tenant_id, user_id, dept_id = await _seed(db_session)
    captured: list[tuple[str, str, dict]] = []

    class _RecorderChannel:
        async def publish(self, event_type: str, data: dict) -> None:
            captured.append((self._ws_id, event_type, data))

        def __init__(self, ws_id: str) -> None:
            self._ws_id = ws_id

    async def _make_channel(workstream_id: str):
        return _RecorderChannel(workstream_id)

    from app.services import workstream_service as ws_module
    monkeypatch.setattr(ws_module, "get_workstream_channel", _make_channel)

    svc = WorkstreamService(db_session)
    ws = await svc.start(
        StartParams(
            tenant_id=tenant_id, user_id=user_id, department_id=dept_id,
            goal="publish on start",
        ),
    )

    # Exactly one publish from start(): the workstream.event for STARTED.
    assert len(captured) == 1
    ws_id, event_type, payload = captured[0]
    assert ws_id == str(ws.id)
    assert event_type == "workstream.event"
    assert payload["workstream_id"] == str(ws.id)
    assert payload["event"]["kind"] == "STARTED"
    assert payload["snapshot"]["status"] == WorkstreamStatus.RUNNING.value
    assert payload["snapshot"]["progress_percent"] == 0


@pytest.mark.asyncio
async def test_transition_publishes_workstream_event_with_new_status(
    db_session: AsyncSession,
):
    """A real transition through the service publishes the new status."""
    tenant_id, user_id, dept_id = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws = await svc.start(
        StartParams(
            tenant_id=tenant_id, user_id=user_id, department_id=dept_id,
            goal="transition publish test",
        ),
    )
    channel = await get_workstream_channel(str(ws.id))
    consumer = asyncio.create_task(
        _drain_envelopes(channel, count=1, timeout=1.0),
    )
    await _wait_subscribed(channel)

    await svc.complete(
        ws.id, tenant_id=tenant_id, summary="done by test",
    )

    envelopes = await consumer
    assert len(envelopes) == 1
    env = envelopes[0]
    assert env["type"] == "workstream.event"
    assert env["data"]["snapshot"]["status"] == WorkstreamStatus.COMPLETE.value
    assert env["data"]["event"]["kind"] == "COMPLETED"
    assert "done by test" in env["data"]["event"]["summary"]


@pytest.mark.asyncio
async def test_update_progress_publishes_snapshot_only(
    db_session: AsyncSession,
):
    """Informational progress bump emits ``workstream.snapshot`` (no event)."""
    tenant_id, user_id, dept_id = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws = await svc.start(
        StartParams(
            tenant_id=tenant_id, user_id=user_id, department_id=dept_id,
            goal="progress snapshot test",
        ),
    )
    channel = await get_workstream_channel(str(ws.id))
    consumer = asyncio.create_task(
        _drain_envelopes(channel, count=1, timeout=1.0),
    )
    await _wait_subscribed(channel)

    await svc.update_progress(ws.id, tenant_id=tenant_id, percent=42)

    envelopes = await consumer
    assert len(envelopes) == 1
    env = envelopes[0]
    assert env["type"] == "workstream.snapshot"
    # snapshot envelopes never include the ``event`` key
    assert "event" not in env["data"]
    assert env["data"]["snapshot"]["progress_percent"] == 42


@pytest.mark.asyncio
async def test_attach_artifact_with_event_publishes_event(
    db_session: AsyncSession,
):
    """Artifact attach (default emit_event=True) publishes a workstream.event."""
    tenant_id, user_id, dept_id = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws = await svc.start(
        StartParams(
            tenant_id=tenant_id, user_id=user_id, department_id=dept_id,
            goal="artifact attach test",
        ),
    )
    channel = await get_workstream_channel(str(ws.id))
    consumer = asyncio.create_task(
        _drain_envelopes(channel, count=1, timeout=1.0),
    )
    await _wait_subscribed(channel)

    await svc.attach_artifact_ref(
        ws.id, tenant_id=tenant_id, kind="file_ids", ref_id="probe-file",
    )

    envelopes = await consumer
    assert len(envelopes) == 1
    env = envelopes[0]
    assert env["type"] == "workstream.event"
    assert env["data"]["event"]["kind"] == "ARTIFACT"
    assert env["data"]["snapshot"]["artifact_refs"]["file_ids"] == ["probe-file"]


@pytest.mark.asyncio
async def test_attach_artifact_silent_publishes_snapshot(
    db_session: AsyncSession,
):
    """Artifact attach with emit_event=False publishes a workstream.snapshot."""
    tenant_id, user_id, dept_id = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws = await svc.start(
        StartParams(
            tenant_id=tenant_id, user_id=user_id, department_id=dept_id,
            goal="silent artifact test",
        ),
    )
    channel = await get_workstream_channel(str(ws.id))
    consumer = asyncio.create_task(
        _drain_envelopes(channel, count=1, timeout=1.0),
    )
    await _wait_subscribed(channel)

    await svc.attach_artifact_ref(
        ws.id, tenant_id=tenant_id, kind="file_ids", ref_id="silent",
        emit_event=False,
    )

    envelopes = await consumer
    assert len(envelopes) == 1
    env = envelopes[0]
    assert env["type"] == "workstream.snapshot"
    assert "event" not in env["data"]
    assert env["data"]["snapshot"]["artifact_refs"]["file_ids"] == ["silent"]


@pytest.mark.asyncio
async def test_attach_audit_ref_publishes_snapshot(
    db_session: AsyncSession,
):
    """Audit ref attach emits snapshot only (anti-flood; no timeline entry)."""
    tenant_id, user_id, dept_id = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws = await svc.start(
        StartParams(
            tenant_id=tenant_id, user_id=user_id, department_id=dept_id,
            goal="audit ref test",
        ),
    )
    channel = await get_workstream_channel(str(ws.id))
    consumer = asyncio.create_task(
        _drain_envelopes(channel, count=1, timeout=1.0),
    )
    await _wait_subscribed(channel)

    await svc.attach_audit_event_ref(
        ws.id, tenant_id=tenant_id, audit_event_id="audit-123",
    )

    envelopes = await consumer
    assert len(envelopes) == 1
    env = envelopes[0]
    assert env["type"] == "workstream.snapshot"
    assert env["data"]["snapshot"]["audit_event_refs"] == ["audit-123"]


@pytest.mark.asyncio
async def test_archive_publishes_snapshot_with_archived_at(
    db_session: AsyncSession,
):
    """Archive emits a snapshot whose archived_at is set so the drawer detaches."""
    tenant_id, user_id, dept_id = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws = await svc.start(
        StartParams(
            tenant_id=tenant_id, user_id=user_id, department_id=dept_id,
            goal="archive snapshot test",
        ),
    )
    channel = await get_workstream_channel(str(ws.id))
    consumer = asyncio.create_task(
        _drain_envelopes(channel, count=1, timeout=1.0),
    )
    await _wait_subscribed(channel)

    await svc.archive(ws.id, tenant_id=tenant_id, archived_by_user_id=user_id)

    envelopes = await consumer
    assert len(envelopes) == 1
    env = envelopes[0]
    assert env["type"] == "workstream.snapshot"
    assert env["data"]["snapshot"]["archived_at"] is not None


@pytest.mark.asyncio
async def test_publish_failure_does_not_break_service_contract(
    db_session: AsyncSession, monkeypatch,
):
    """A broken SSE channel must not raise out of WorkstreamService."""
    tenant_id, user_id, dept_id = await _seed(db_session)
    svc = WorkstreamService(db_session)

    # Force every publish to raise. The service must absorb the failure.
    from app.services import workstream_service as ws_module

    async def _exploding_channel(_workstream_id: str):
        class _Boom:
            async def publish(self, *args, **kwargs):
                raise RuntimeError("simulated SSE outage")
        return _Boom()

    monkeypatch.setattr(
        ws_module, "get_workstream_channel", _exploding_channel,
    )

    # The contract: start() still returns a workstream and commits.
    ws = await svc.start(
        StartParams(
            tenant_id=tenant_id, user_id=user_id, department_id=dept_id,
            goal="publish failure isolation",
        ),
    )
    assert ws.id is not None
    assert ws.status == WorkstreamStatus.RUNNING

    # ...and a subsequent transition still mutates state.
    ws_after = await svc.complete(
        ws.id, tenant_id=tenant_id, summary="completed despite SSE break",
    )
    assert ws_after.status == WorkstreamStatus.COMPLETE


@pytest.mark.asyncio
async def test_two_subscribers_both_receive_published_event(
    db_session: AsyncSession,
):
    """Multiple subscribers on the same workstream id fan out the event."""
    tenant_id, user_id, dept_id = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws = await svc.start(
        StartParams(
            tenant_id=tenant_id, user_id=user_id, department_id=dept_id,
            goal="fanout test",
        ),
    )
    channel = await get_workstream_channel(str(ws.id))
    consumer_a = asyncio.create_task(
        _drain_envelopes(channel, count=1, timeout=1.0),
    )
    consumer_b = asyncio.create_task(
        _drain_envelopes(channel, count=1, timeout=1.0),
    )
    await _wait_subscribed(channel)

    await svc.update_progress(ws.id, tenant_id=tenant_id, percent=80)

    a, b = await asyncio.gather(consumer_a, consumer_b)
    assert len(a) == 1
    assert len(b) == 1
    assert a[0]["data"]["snapshot"]["progress_percent"] == 80
    assert b[0]["data"]["snapshot"]["progress_percent"] == 80


@pytest.mark.asyncio
async def test_other_workstream_channel_does_not_receive_unrelated_event(
    db_session: AsyncSession,
):
    """Per-id isolation: subscriber on workstream A does not see B's events."""
    tenant_id, user_id, dept_id = await _seed(db_session)
    svc = WorkstreamService(db_session)
    ws_a = await svc.start(
        StartParams(
            tenant_id=tenant_id, user_id=user_id, department_id=dept_id,
            goal="ws A",
        ),
    )
    ws_b = await svc.start(
        StartParams(
            tenant_id=tenant_id, user_id=user_id, department_id=dept_id,
            goal="ws B",
        ),
    )
    channel_a = await get_workstream_channel(str(ws_a.id))

    consumer_a = asyncio.create_task(
        _drain_envelopes(channel_a, count=1, timeout=0.3),
    )
    await _wait_subscribed(channel_a)

    # Mutating ws_b should NOT enqueue anything on ws_a's channel.
    await svc.update_progress(ws_b.id, tenant_id=tenant_id, percent=50)

    received = await consumer_a
    assert received == []  # timeout drained nothing -> A truly isolated
