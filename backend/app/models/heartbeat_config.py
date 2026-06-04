"""HeartbeatConfig model -- durable single-row heartbeat daemon config (S-02).

The HeartbeatDaemon is a single process-wide operator tool, not per-user
state, so its configuration is a singleton row (key="singleton") rather
than a tenant/user-scoped table. Before this table the daemon's
interval / active-hours / autopilot-level / cost-caps / per-check toggles
lived only in the in-process ``HeartbeatConfig`` dataclass and reverted to
defaults on every restart, so any operator change made via
``/heartbeat/configure`` was silently lost (an ADR-001 honesty gap: the
Settings UI implied persistence).

Design choices
--------------
* Single JSON blob (``config_json``) rather than one column per setting.
  Heartbeat config is operator preference, not analytic data -- it is read
  as a whole on daemon start and written as a whole on configure, exactly
  like ``user.settings``. A blob also means new config fields need no new
  migration. The stored shape is the SAME normalized dict that
  ``HeartbeatDaemon.configure()`` already accepts, so hydrate is a plain
  ``configure(stored)`` call with zero apply-logic drift.
* ``state`` and ``daily_cost_accumulated`` are deliberately NOT persisted:
  they are runtime values, not config. A restarted daemon should come up
  STOPPED with a fresh daily counter, then be started by the lifespan hook.
"""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JSONBCompat, TimestampMixin

# The single config row's primary key. The daemon is process-wide, so there
# is exactly one row.
SINGLETON_KEY = "singleton"


class HeartbeatConfigRow(Base, TimestampMixin):
    """The persisted heartbeat configuration (one row, key=SINGLETON_KEY)."""

    __tablename__ = "heartbeat_config"

    key: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=SINGLETON_KEY,
    )
    # Normalized config dict in HeartbeatDaemon.configure() update shape:
    # {interval_minutes, autopilot_level, active_start "HH:MM", active_end,
    #  reflection_enabled, max_cost_per_cycle_usd, max_cost_per_day_usd,
    #  checks: {check_type: enabled}}. No secrets -- pure operator settings.
    config_json: Mapped[dict | None] = mapped_column(JSONBCompat(), nullable=True)
