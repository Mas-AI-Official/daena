"""Persistence for the singleton heartbeat config (S-02).

Round-trips the daemon's in-process ``HeartbeatConfig`` through the
``heartbeat_config`` table so operator changes survive a restart. The
stored shape is the SAME normalized dict that
``HeartbeatDaemon.configure()`` accepts, so applying a loaded row is a
plain ``configure(row)`` call -- there is no second copy of the apply
logic to drift.

Opens a FRESH session via ``async_session_factory`` (mirrors error_sink),
never reusing a request-scoped session. Every function is best-effort and
fail-open at the daemon call sites: a DB hiccup must not stop the heartbeat
or the configure endpoint.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from app.models.heartbeat_config import SINGLETON_KEY, HeartbeatConfigRow

if TYPE_CHECKING:
    from app.services.heartbeat.heartbeat_config import HeartbeatConfig

logger = structlog.get_logger(__name__)


def extract_persistable(config: HeartbeatConfig) -> dict[str, Any]:
    """Project a HeartbeatConfig down to the normalized configure() update
    dict (the only fields worth persisting -- not runtime state/counters)."""
    return {
        "interval_minutes": config.interval_minutes,
        "autopilot_level": config.autopilot_level.value,
        "active_start": config.active_start.strftime("%H:%M"),
        "active_end": config.active_end.strftime("%H:%M"),
        "reflection_enabled": config.reflection_enabled,
        "max_cost_per_cycle_usd": config.max_cost_per_cycle_usd,
        "max_cost_per_day_usd": config.max_cost_per_day_usd,
        "checks": {c.check_type.value: c.enabled for c in config.checks},
    }


async def load_persisted() -> dict[str, Any] | None:
    """Return the stored normalized config dict, or None if no row exists."""
    from app.core.database import async_session_factory

    async with async_session_factory() as session:
        row = await session.get(HeartbeatConfigRow, SINGLETON_KEY)
        if row is None or not row.config_json:
            return None
        return dict(row.config_json)


async def save_persisted(normalized: dict[str, Any]) -> None:
    """Upsert the single config row with the normalized config dict."""
    from app.core.database import async_session_factory

    async with async_session_factory() as session:
        row = await session.get(HeartbeatConfigRow, SINGLETON_KEY)
        if row is None:
            row = HeartbeatConfigRow(key=SINGLETON_KEY, config_json=normalized)
            session.add(row)
        else:
            row.config_json = normalized
        await session.commit()
