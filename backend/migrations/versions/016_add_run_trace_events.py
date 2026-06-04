"""Add run_trace_events table (local run-tracing groundwork).

Revision ID: 016_add_run_trace_events
Revises: 015_add_heartbeat_config
Create Date: 2026-06-03

Context
-------
A queryable span per chat-pipeline step (OpenAI-Agents-SDK-style tracing /
LangGraph run-visibility), stored locally -- no external telemetry SaaS. Spans
are best-effort and SAFE-fields-only (no prompts/credentials/raw errors); see
app/models/run_trace_event.py. tenant_id/user_id/session_id are nullable with
NO foreign keys so emitting a span can never fail on an FK violation.

Idempotency: guarded by _table_exists, mirrors migrations 003-015.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import GUID, JSONBCompat

revision: str = "016_add_run_trace_events"
down_revision: str | None = "015_add_heartbeat_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table in inspector.get_table_names()


def upgrade() -> None:
    """Create run_trace_events (no FKs -- best-effort span sink)."""
    if _table_exists("run_trace_events"):
        return

    op.create_table(
        "run_trace_events",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("run_id", sa.String(64), nullable=True),
        sa.Column("session_id", GUID(), nullable=True),
        sa.Column("tenant_id", GUID(), nullable=True),
        sa.Column("user_id", GUID(), nullable=True),
        sa.Column("event_type", sa.String(48), nullable=False),
        sa.Column("stage", sa.String(48), nullable=True),
        sa.Column("provider", sa.String(32), nullable=True),
        sa.Column("model", sa.String(96), nullable=True),
        sa.Column("governance_mode", sa.String(24), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="ok"),
        sa.Column("safe_summary", sa.Text, nullable=True),
        sa.Column("metadata_json", JSONBCompat(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=True, onupdate=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_run_trace_events"),
    )
    op.create_index("ix_run_trace_events_request_id", "run_trace_events", ["request_id"])
    op.create_index("ix_run_trace_events_run_id", "run_trace_events", ["run_id"])
    op.create_index("ix_run_trace_events_created_at", "run_trace_events", ["created_at"])


def downgrade() -> None:
    if _table_exists("run_trace_events"):
        op.drop_index("ix_run_trace_events_created_at", table_name="run_trace_events")
        op.drop_index("ix_run_trace_events_run_id", table_name="run_trace_events")
        op.drop_index("ix_run_trace_events_request_id", table_name="run_trace_events")
        op.drop_table("run_trace_events")
