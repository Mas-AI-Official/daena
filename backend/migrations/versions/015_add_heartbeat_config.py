"""Add heartbeat_config table (S-02 durable daemon config).

Revision ID: 015_add_heartbeat_config
Revises: 014_merge_heads
Create Date: 2026-06-03

Context
-------
The HeartbeatDaemon's operator config (interval, active-hours, autopilot
level, cost-caps, per-check toggles) previously lived only in the in-process
HeartbeatConfig dataclass and reverted to defaults on every restart, so any
/heartbeat/configure change was silently lost. This single-row table
(key="singleton") persists the normalized config dict; the daemon hydrates
it on start and writes it on configure. See app/models/heartbeat_config.py.

Idempotency: guarded by _table_exists, mirrors migrations 003-010.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import JSONBCompat

revision: str = "015_add_heartbeat_config"
down_revision: str | None = "014_merge_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table in inspector.get_table_names()


def upgrade() -> None:
    """Create the single-row heartbeat_config table."""
    if _table_exists("heartbeat_config"):
        return

    op.create_table(
        "heartbeat_config",
        sa.Column("key", sa.String(32), nullable=False),
        sa.Column("config_json", JSONBCompat(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=True, onupdate=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("key", name="pk_heartbeat_config"),
    )


def downgrade() -> None:
    if _table_exists("heartbeat_config"):
        op.drop_table("heartbeat_config")
