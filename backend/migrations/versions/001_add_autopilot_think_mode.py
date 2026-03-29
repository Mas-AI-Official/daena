"""Add autopilot and think_mode columns to chat_sessions.

Revision ID: 001_add_autopilot_think_mode
Revises: None (first migration — schema was bootstrapped via create_all)
Create Date: 2026-03-13
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_add_autopilot_think_mode"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table: str, column: str) -> bool:
    """Check if a column already exists (safe for re-runs on SQLite/Postgres)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c["name"] for c in inspector.get_columns(table)]
    return column in columns


def upgrade() -> None:
    """Add autopilot and think_mode boolean columns to chat_sessions."""
    if not _column_exists("chat_sessions", "autopilot"):
        op.add_column(
            "chat_sessions",
            sa.Column(
                "autopilot",
                sa.Boolean(),
                nullable=False,
                server_default="false",
            ),
        )

    if not _column_exists("chat_sessions", "think_mode"):
        op.add_column(
            "chat_sessions",
            sa.Column(
                "think_mode",
                sa.Boolean(),
                nullable=False,
                server_default="false",
            ),
        )


def downgrade() -> None:
    """Remove autopilot and think_mode columns from chat_sessions."""
    if _column_exists("chat_sessions", "think_mode"):
        op.drop_column("chat_sessions", "think_mode")

    if _column_exists("chat_sessions", "autopilot"):
        op.drop_column("chat_sessions", "autopilot")
