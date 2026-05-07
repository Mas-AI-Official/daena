"""Real-execution tests for ``CronScheduler.check_and_run``.

These tests pin down the honesty fix made on 2026-04-29: cron jobs no
longer write the literal string ``"executed"`` to ``last_result``;
they actually invoke a runtime via the registry, persist a
``CronRun`` row, and enforce a per-run cost cap.

The real ``async_session_factory`` is reused -- but every test sets
up an isolated in-memory SQLite engine with the ORM schema applied,
patches ``app.core.database.async_session_factory`` to point at the
test engine for the duration of the test, and then restores the
original. This keeps the production wiring untouched while letting
us assert on persisted rows.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, time
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import event, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from app.models.base import Base
from app.models.cron_run import CronRun
from app.services.heartbeat import cron_scheduler as cs_module
from app.services.heartbeat.cron_scheduler import (
    CronFrequency,
    CronJob,
    CronScheduler,
    get_cron_scheduler,
    reset_cron_scheduler_singleton,
    set_runtime_registry_resolver,
    start_cron_scheduler,
    stop_cron_scheduler,
)


# ── SQLite compatibility for PostgreSQL types ──────────────────────────

@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):  # noqa: ANN001, ANN201
    return "JSON"


@compiles(PG_UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):  # noqa: ANN001, ANN201
    return "CHAR(36)"


# ── Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
async def patched_session_factory(monkeypatch):
    """Build an isolated in-memory engine and patch the cron module's
    ``async_session_factory`` references to use it for the test."""
    from app.core import database as core_db

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ANN001
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    monkeypatch.setattr(core_db, "async_session_factory", factory)

    yield factory

    await engine.dispose()


@pytest.fixture(autouse=True)
def reset_singletons():
    """Make sure each test starts with a clean module state."""
    reset_cron_scheduler_singleton()
    set_runtime_registry_resolver(lambda: None)
    yield
    reset_cron_scheduler_singleton()
    set_runtime_registry_resolver(lambda: None)


def _due_job(job_id: str, runtime: str = "ollama", cap: float = 1.0) -> CronJob:
    """Build a job that is guaranteed to be due right now."""
    now = datetime.now()
    return CronJob(
        job_id=job_id,
        name=f"Test {job_id}",
        frequency=CronFrequency.DAILY,
        run_at=time(now.hour, now.minute),
        task_prompt="say hello",
        runtime_preference=runtime,
        enabled=True,
        max_cost_usd=cap,
    )


def _make_streaming_adapter(chunks: list[str]):
    """Mock adapter whose ``execute`` yields the supplied chunks."""

    async def _execute(task, context):  # noqa: ANN001, ANN202
        for chunk in chunks:
            yield chunk

    adapter = MagicMock()
    adapter.execute = _execute
    return adapter


def _make_failing_adapter(error: Exception):
    """Mock adapter that raises mid-stream."""

    async def _execute(task, context):  # noqa: ANN001, ANN202
        if False:  # pragma: no cover -- never yields
            yield ""
        raise error

    adapter = MagicMock()
    adapter.execute = _execute
    return adapter


# ── Tests ──────────────────────────────────────────────────────────────

class TestCheckAndRunCallsRuntime:
    @pytest.mark.asyncio
    async def test_due_job_invokes_registry_exactly_once(
        self, patched_session_factory,
    ):
        adapter = _make_streaming_adapter(["hello", " world"])
        registry = MagicMock()
        registry.get_adapter = MagicMock(return_value=adapter)
        set_runtime_registry_resolver(lambda: registry)

        scheduler = CronScheduler()
        scheduler.add_job(_due_job("job-call-once"))

        executed = await scheduler.check_and_run()

        assert "job-call-once" in executed
        registry.get_adapter.assert_called_once_with("ollama")

    @pytest.mark.asyncio
    async def test_cron_run_row_inserted(self, patched_session_factory):
        adapter = _make_streaming_adapter(["chunk-one", "chunk-two"])
        registry = MagicMock()
        registry.get_adapter = MagicMock(return_value=adapter)
        set_runtime_registry_resolver(lambda: registry)

        scheduler = CronScheduler()
        scheduler.add_job(_due_job("job-row"))

        await scheduler.check_and_run()

        async with patched_session_factory() as session:
            rows = (
                await session.execute(
                    select(CronRun).where(CronRun.job_id == "job-row")
                )
            ).scalars().all()

        assert len(rows) == 1
        row = rows[0]
        assert row.runtime == "ollama"
        assert row.started_at is not None
        assert row.finished_at is not None
        assert row.error is None
        assert row.summary is not None
        assert "chunk-one" in (row.full_text or "")


class TestCostCap:
    @pytest.mark.asyncio
    async def test_estimated_cost_over_cap_rejects_run(
        self, patched_session_factory,
    ):
        # claude_code is priced > 0; with a cap of 1e-9 the estimate
        # always exceeds the cap and the runtime must NOT be invoked.
        adapter = _make_streaming_adapter(["should not run"])
        registry = MagicMock()
        registry.get_adapter = MagicMock(return_value=adapter)
        set_runtime_registry_resolver(lambda: registry)

        scheduler = CronScheduler()
        scheduler.add_job(_due_job(
            "job-cap", runtime="claude_code", cap=1e-9,
        ))

        await scheduler.check_and_run()

        # Adapter was never resolved because cap rejected the run.
        registry.get_adapter.assert_not_called()

        async with patched_session_factory() as session:
            row = (
                await session.execute(
                    select(CronRun).where(CronRun.job_id == "job-cap")
                )
            ).scalar_one()
        assert row.error is not None
        assert "cost cap" in row.error.lower()

        job = scheduler._jobs["job-cap"]
        assert job.last_result is not None
        assert "cost cap" in job.last_result.lower()


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_runtime_error_does_not_break_loop(
        self, patched_session_factory,
    ):
        bad_adapter = _make_failing_adapter(RuntimeError("boom"))
        good_adapter = _make_streaming_adapter(["ok"])

        # The registry returns one bad and one good adapter depending
        # on the runtime preference. Two due jobs hit it back-to-back.
        def _resolve(runtime_id):  # noqa: ANN001, ANN202
            return bad_adapter if runtime_id == "ollama" else good_adapter

        registry = MagicMock()
        registry.get_adapter = MagicMock(side_effect=_resolve)
        set_runtime_registry_resolver(lambda: registry)

        scheduler = CronScheduler()
        scheduler.add_job(_due_job("job-bad", runtime="ollama"))
        scheduler.add_job(
            _due_job("job-good", runtime="codex", cap=1.0)
        )

        executed = await scheduler.check_and_run()

        # Both jobs were dispatched. Failure of one did not abort the
        # other -- the loop survives a per-job exception cleanly.
        assert "job-bad" in executed
        assert "job-good" in executed

        async with patched_session_factory() as session:
            bad_row = (
                await session.execute(
                    select(CronRun).where(CronRun.job_id == "job-bad")
                )
            ).scalar_one()
            good_row = (
                await session.execute(
                    select(CronRun).where(CronRun.job_id == "job-good")
                )
            ).scalar_one()

        assert bad_row.error is not None
        assert "boom" in bad_row.error
        assert good_row.error is None


class TestSingletonAndLifecycle:
    def test_get_cron_scheduler_returns_same_instance(self):
        a = get_cron_scheduler()
        b = get_cron_scheduler()
        assert a is b

    @pytest.mark.asyncio
    async def test_start_and_stop_idempotent(self, patched_session_factory):
        # Loop sleeps 60s between cycles, so start + immediate stop is
        # safe and exercises the lifecycle helpers.
        await start_cron_scheduler()
        scheduler = get_cron_scheduler()
        assert scheduler._running is True
        await stop_cron_scheduler()
        # After stop we should be idle again.
        assert scheduler._running is False
