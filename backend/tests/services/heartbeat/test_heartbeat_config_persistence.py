"""S-02: heartbeat config survives a restart.

Before S-02 the daemon's operator config lived only in-process and reverted
to defaults on restart, so any /heartbeat/configure change was silently lost.
These tests prove the round-trip: a configured daemon persists, and a FRESH
daemon instance (simulating a process restart) hydrates the persisted values
instead of the defaults.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.heartbeat.heartbeat_config import AutopilotLevel, CheckType
from app.services.heartbeat.heartbeat_config_store import (
    extract_persistable,
    save_persisted,
)
from app.services.heartbeat.heartbeat_daemon import HeartbeatDaemon


def _factory(test_engine):
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.mark.asyncio
async def test_config_survives_restart(test_engine) -> None:
    """Configure one daemon, persist, then a fresh daemon hydrates the values."""
    factory = _factory(test_engine)
    with patch("app.core.database.async_session_factory", factory):
        # Operator changes config via the API path (configure + persist).
        d1 = HeartbeatDaemon()
        d1.configure(
            {
                "interval_minutes": 99,
                "autopilot_level": "off",
                "active_start": "08:30",
                "active_end": "21:45",
                "max_cost_per_day_usd": 5.0,
                "checks": {CheckType.RUNTIME_HEALTH.value: False},
            }
        )
        await save_persisted(extract_persistable(d1.config))

        # Simulate a restart: a brand-new daemon starts at defaults, then
        # hydrate_from_db() must overwrite them with the persisted values.
        d2 = HeartbeatDaemon()
        assert d2.config.interval_minutes == 30  # default before hydrate
        await d2.hydrate_from_db()

    assert d2.config.interval_minutes == 99
    assert d2.config.autopilot_level is AutopilotLevel.OFF
    assert d2.config.active_start.strftime("%H:%M") == "08:30"
    assert d2.config.active_end.strftime("%H:%M") == "21:45"
    assert d2.config.max_cost_per_day_usd == 5.0
    runtime_check = next(
        c for c in d2.config.checks if c.check_type is CheckType.RUNTIME_HEALTH
    )
    assert runtime_check.enabled is False


@pytest.mark.asyncio
async def test_hydrate_no_row_keeps_defaults(test_engine) -> None:
    """With no persisted row, hydrate is a no-op and defaults remain."""
    factory = _factory(test_engine)
    with patch("app.core.database.async_session_factory", factory):
        d = HeartbeatDaemon()
        await d.hydrate_from_db()
    assert d.config.interval_minutes == 30
    assert d.config.autopilot_level is AutopilotLevel.ON


@pytest.mark.asyncio
async def test_hydrate_fail_open_when_db_broken() -> None:
    """A storage error during hydrate must not raise -- defaults stand."""
    def _boom():
        raise RuntimeError("db down")

    with patch("app.core.database.async_session_factory", _boom):
        d = HeartbeatDaemon()
        await d.hydrate_from_db()  # must swallow
    assert d.config.interval_minutes == 30
