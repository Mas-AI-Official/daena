"""DEP-007: the safe runtime-error sink.

Verifies record_error_event (1) persists a safe row, (2) coerces a bad
id to NULL instead of failing (no FK = best-effort), and (3) NEVER raises
into its caller even when the DB layer is broken.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.error_event import ErrorEvent
from app.services.error_sink import record_error_event


@pytest.mark.asyncio
async def test_record_error_event_persists_safe_row(test_engine) -> None:
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    with patch("app.core.database.async_session_factory", factory):
        await record_error_event(
            source="exception_handler",
            severity="error",
            route="/api/v1/chat/messages/stream",
            method="POST",
            status_code=500,
            error_code="INTERNAL_ERROR",
            error_type="ValueError",
            safe_message="Something went wrong. Please try again.",
            request_id="req-abc-123",
            user_id="not-a-uuid",  # bad id -> coerced to NULL, not an error
        )

    async with factory() as s:
        rows = (
            await s.execute(
                select(ErrorEvent).where(ErrorEvent.request_id == "req-abc-123")
            )
        ).scalars().all()

    assert len(rows) == 1
    row = rows[0]
    assert row.source == "exception_handler"
    assert row.status_code == 500
    assert row.error_type == "ValueError"
    assert row.safe_message == "Something went wrong. Please try again."
    # Bad user_id coerced to NULL (best-effort sink, no FK violation).
    assert row.user_id is None
    # The sink stores only what it was given -- the generic safe_message,
    # never a raw exception string.
    assert "Traceback" not in (row.safe_message or "")


@pytest.mark.asyncio
async def test_record_error_event_never_raises_when_db_broken() -> None:
    """If the DB layer fails, the sink must swallow it (already-failing path)."""
    def _boom():
        raise RuntimeError("db down")

    with patch("app.core.database.async_session_factory", _boom):
        # Must return None without propagating -- a failure-to-record must
        # never turn a handled 500 into an unhandled one.
        result = await record_error_event(
            source="exception_handler", safe_message="x", request_id="req-x"
        )
    assert result is None
