"""Tests for the DB-backed BackgroundQueue (2026-04-29 audit fix).

These tests own the persistence + restart-recovery contract added to
``app.services.autopilot.background_queue``. They use a fresh in-memory
SQLite engine per test so each scenario has a clean ``background_tasks``
table.

Scope:
    * enqueue inserts a row
    * the run flow walks queued -> running -> complete
    * restore_queue_from_db re-enqueues queued, marks running as
      failed_due_to_restart
    * tenant isolation in cancel_all
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import event, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.compiler import compiles

# Import the model BEFORE Base.metadata.create_all so SQLAlchemy registers
# the table on the metadata. We touch the import to keep linters happy.
from app.models.background_task import BackgroundTask as BackgroundTaskRow  # noqa: F401
from app.models.base import Base
from app.services.autopilot.background_queue import (
    BackgroundQueue,
    BackgroundTask,
)


# ── SQLite compatibility for PG types (mirrors backend/tests/conftest.py) ──


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(PG_UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    return "CHAR(36)"


# ── Fixtures ──


@pytest.fixture
async def engine_factory():
    """Per-test engine + session_factory pair.

    Returns the factory directly so tests can pass it into
    ``BackgroundQueue(db_session_factory=...)``.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    @asynccontextmanager
    async def _wrapped() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as s:
            yield s

    yield _wrapped, engine, factory

    await engine.dispose()


@pytest.fixture
async def tenant_id(engine_factory) -> str:
    """Create a tenant row so FK constraints succeed and return its id."""
    _wrapped, _engine, factory = engine_factory
    from app.models.identity import Tenant

    tid = uuid.uuid4()
    async with factory() as session:
        session.add(Tenant(id=tid, name="Test", slug=f"test-{tid.hex[:8]}"))
        await session.commit()
    return str(tid)


def _make_task(tenant_id: str, *, status: str = "queued", priority: str = "P2") -> BackgroundTask:
    return BackgroundTask(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        session_id=f"sess-{uuid.uuid4().hex[:6]}",
        description="Persistence smoke test task",
        priority=priority,
        status=status,
    )


# ── Tests ──


class TestEnqueuePersists:
    @pytest.mark.asyncio
    async def test_enqueue_inserts_row(self, engine_factory, tenant_id):
        wrapped, _engine, factory = engine_factory

        queue = BackgroundQueue(db_session_factory=wrapped)
        task = _make_task(tenant_id)
        await queue.enqueue(task)

        async with factory() as session:
            stmt = select(BackgroundTaskRow).where(BackgroundTaskRow.id == uuid.UUID(task.id))
            row = (await session.execute(stmt)).scalar_one()

        assert row is not None
        assert row.session_id == task.session_id
        assert row.status == "queued"
        assert row.priority == "P2"
        assert str(row.tenant_id) == tenant_id


class TestProcessFlow:
    @pytest.mark.asyncio
    async def test_process_walks_queued_to_complete(self, engine_factory, tenant_id):
        wrapped, _engine, factory = engine_factory

        async def fake_executor(task: BackgroundTask) -> dict:
            return {"ok": True, "session": task.session_id}

        queue = BackgroundQueue(
            max_concurrent=1,
            db_session_factory=wrapped,
            executor=fake_executor,
        )

        worker = asyncio.create_task(queue.start_worker())
        try:
            task = _make_task(tenant_id)
            await queue.enqueue(task)

            # Poll the row until terminal state or timeout.
            terminal_status: str | None = None
            for _ in range(40):
                await asyncio.sleep(0.05)
                async with factory() as session:
                    stmt = select(BackgroundTaskRow.status).where(
                        BackgroundTaskRow.id == uuid.UUID(task.id),
                    )
                    terminal_status = (await session.execute(stmt)).scalar_one()
                if terminal_status in ("complete", "failed", "cancelled"):
                    break

            assert terminal_status == "complete"

            async with factory() as session:
                row = (
                    await session.execute(
                        select(BackgroundTaskRow).where(
                            BackgroundTaskRow.id == uuid.UUID(task.id),
                        ),
                    )
                ).scalar_one()
            assert row.started_at is not None
            assert row.finished_at is not None
            assert row.result == {"ok": True, "session": task.session_id}
        finally:
            queue.stop()
            worker.cancel()
            try:
                await worker
            except asyncio.CancelledError:
                pass


class TestRestoreFromDB:
    @pytest.mark.asyncio
    async def test_restore_reenqueues_queued_and_marks_running_failed(
        self, engine_factory, tenant_id,
    ):
        wrapped, _engine, factory = engine_factory

        # Pre-seed two rows: one queued, one running.
        queued_id = uuid.uuid4()
        running_id = uuid.uuid4()
        async with factory() as session:
            session.add(
                BackgroundTaskRow(
                    id=queued_id,
                    tenant_id=uuid.UUID(tenant_id),
                    session_id="sess-restore-q",
                    description="Survives restart",
                    status="queued",
                    priority="P1",
                ),
            )
            session.add(
                BackgroundTaskRow(
                    id=running_id,
                    tenant_id=uuid.UUID(tenant_id),
                    session_id="sess-restore-r",
                    description="Orphaned by restart",
                    status="running",
                    priority="P0",
                ),
            )
            await session.commit()

        # Fresh queue boots, runs recovery.
        queue = BackgroundQueue(db_session_factory=wrapped)
        result = await queue.restore_queue_from_db()

        assert result == {"restored_queued": 1, "marked_failed": 1}
        assert queue.queued_count == 1

        async with factory() as session:
            running_row = (
                await session.execute(
                    select(BackgroundTaskRow).where(BackgroundTaskRow.id == running_id),
                )
            ).scalar_one()
            queued_row = (
                await session.execute(
                    select(BackgroundTaskRow).where(BackgroundTaskRow.id == queued_id),
                )
            ).scalar_one()

        assert running_row.status == "failed_due_to_restart"
        assert running_row.finished_at is not None
        assert "restarted" in (running_row.error or "")
        # Queued row stays queued (we re-enqueued in memory; DB row is unchanged).
        assert queued_row.status == "queued"

    @pytest.mark.asyncio
    async def test_restore_no_db_returns_zero(self):
        queue = BackgroundQueue()
        result = await queue.restore_queue_from_db()
        assert result == {"restored_queued": 0, "marked_failed": 0}


class TestTenantIsolation:
    @pytest.mark.asyncio
    async def test_cancel_all_affects_only_session_tasks(self, engine_factory, tenant_id):
        wrapped, _engine, factory = engine_factory

        # Build a second tenant so we can prove cross-tenant rows survive.
        from app.models.identity import Tenant

        other_tid = uuid.uuid4()
        async with factory() as session:
            session.add(
                Tenant(id=other_tid, name="Other", slug=f"other-{other_tid.hex[:8]}"),
            )
            await session.commit()

        queue = BackgroundQueue(db_session_factory=wrapped)

        # Two tasks for tenant A session "S", one task for tenant B session "T".
        task_a1 = _make_task(tenant_id)
        task_a1.session_id = "S"
        task_a2 = _make_task(tenant_id)
        task_a2.session_id = "S"
        task_b = _make_task(str(other_tid))
        task_b.session_id = "T"

        for t in (task_a1, task_a2, task_b):
            await queue.enqueue(t)
            # Promote to active so cancel_all can flip them.
            queue._active[t.id] = t

        cancelled = await queue.cancel_all("S")
        assert cancelled == 2

        async with factory() as session:
            stmt = select(BackgroundTaskRow).order_by(BackgroundTaskRow.queued_at)
            rows = (await session.execute(stmt)).scalars().all()
            by_id = {str(r.id): r for r in rows}

        assert by_id[task_a1.id].status == "cancelled"
        assert by_id[task_a2.id].status == "cancelled"
        assert by_id[task_b.id].status == "queued"
