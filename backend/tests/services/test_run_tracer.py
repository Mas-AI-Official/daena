"""Local run tracer: safe, fail-open, flag-gated chat-run spans.

Verifies the recorder (1) writes a safe row when TRACE_ENABLED, (2) is a no-op
when disabled, (3) never persists secret-looking metadata, (4) never raises when
the DB is broken (it runs on the hot chat path), (5) coerces bad ids to NULL.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.run_trace_event import RunTraceEvent
from app.services import run_tracer


def _factory(test_engine):
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.mark.asyncio
async def test_records_safe_span_when_enabled(test_engine) -> None:
    factory = _factory(test_engine)
    with patch.object(run_tracer, "_TRACE_ENABLED", True), patch(
        "app.core.database.async_session_factory", factory
    ):
        await run_tracer.record_trace_event(
            event_type="provider.selected",
            request_id="req-trace-1",
            run_id="run-1",
            stage="6_model_router",
            provider="anthropic",
            model="claude-opus-4-8",
            governance_mode="GOVERNED",
            status="ok",
            safe_summary="primary brain selected",
            user_id="not-a-uuid",  # bad id -> NULL, no crash
        )

    async with factory() as s:
        rows = (
            await s.execute(
                select(RunTraceEvent).where(RunTraceEvent.request_id == "req-trace-1")
            )
        ).scalars().all()

    assert len(rows) == 1
    r = rows[0]
    assert r.event_type == "provider.selected"
    assert r.provider == "anthropic"
    assert r.model == "claude-opus-4-8"
    assert r.governance_mode == "GOVERNED"
    assert r.user_id is None  # bad id coerced


@pytest.mark.asyncio
async def test_noop_when_disabled(test_engine) -> None:
    factory = _factory(test_engine)
    with patch.object(run_tracer, "_TRACE_ENABLED", False), patch(
        "app.core.database.async_session_factory", factory
    ):
        await run_tracer.record_trace_event(
            event_type="chat.start", request_id="req-off-1"
        )

    async with factory() as s:
        count = (
            await s.execute(select(func.count()).select_from(RunTraceEvent))
        ).scalar_one()
    assert count == 0  # nothing written when the flag is off


@pytest.mark.asyncio
async def test_secret_metadata_is_stripped(test_engine) -> None:
    factory = _factory(test_engine)
    with patch.object(run_tracer, "_TRACE_ENABLED", True), patch(
        "app.core.database.async_session_factory", factory
    ):
        await run_tracer.record_trace_event(
            event_type="chat.start",
            request_id="req-secret-1",
            metadata={
                "api_key": "sk-SHOULD-NOT-PERSIST",
                "prompt": "the user's private prompt text",
                "tries": 3,  # safe -> kept
            },
        )

    async with factory() as s:
        row = (
            await s.execute(
                select(RunTraceEvent).where(RunTraceEvent.request_id == "req-secret-1")
            )
        ).scalars().one()

    meta = row.metadata_json or {}
    assert "api_key" not in meta
    assert "prompt" not in meta
    assert meta.get("tries") == 3
    # the secret value must not appear anywhere in the stored row
    assert "SHOULD-NOT-PERSIST" not in str(row.metadata_json)


@pytest.mark.asyncio
async def test_never_raises_when_db_broken() -> None:
    def _boom():
        raise RuntimeError("db down")

    with patch.object(run_tracer, "_TRACE_ENABLED", True), patch(
        "app.core.database.async_session_factory", _boom
    ):
        # Must swallow -- a tracing failure must never break a chat turn.
        result = await run_tracer.record_trace_event(
            event_type="chat.end", request_id="req-boom"
        )
    assert result is None
