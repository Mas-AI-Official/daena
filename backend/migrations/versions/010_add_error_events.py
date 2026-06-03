"""Add error_events table (DEP-007 safe runtime-error sink).

Revision ID: 010_add_error_events
Revises: 009_user_quota_month_anchor
Create Date: 2026-06-02

Context
-------
A durable, safe sink for 5xx / unhandled / streaming-fallback errors so
the founder/operator can review failures after the fact. tenant_id and
user_id are nullable with NO foreign keys on purpose: recording a failure
must never itself fail on an FK violation (see app/models/error_event.py).
SAFE FIELDS ONLY -- no secrets, no raw stack traces.

Idempotency: guarded by _table_exists, mirrors migrations 003-009.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import GUID, JSONBCompat

revision: str = "010_add_error_events"
down_revision: str | None = "009_user_quota_month_anchor"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table in inspector.get_table_names()


def upgrade() -> None:
    """Create error_events (no FKs -- best-effort sink)."""
    if _table_exists("error_events"):
        return

    op.create_table(
        "error_events",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False, server_default="error"),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("route", sa.String(256), nullable=True),
        sa.Column("method", sa.String(8), nullable=True),
        sa.Column("status_code", sa.Integer, nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_type", sa.String(128), nullable=True),
        sa.Column("safe_message", sa.Text, nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        # Nullable, NO ForeignKey (see model docstring).
        sa.Column("user_id", GUID(), nullable=True),
        sa.Column("tenant_id", GUID(), nullable=True),
        sa.Column("run_id", sa.String(64), nullable=True),
        sa.Column("provider", sa.String(32), nullable=True),
        sa.Column("metadata_json", JSONBCompat(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=True, onupdate=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_error_events"),
    )
    op.create_index("ix_error_events_created_at", "error_events", ["created_at"])
    op.create_index("ix_error_events_request_id", "error_events", ["request_id"])


def downgrade() -> None:
    if _table_exists("error_events"):
        op.drop_index("ix_error_events_request_id", table_name="error_events")
        op.drop_index("ix_error_events_created_at", table_name="error_events")
        op.drop_table("error_events")
