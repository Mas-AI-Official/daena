"""Add lost_at + lost_reason columns to project_pipeline.

Revision ID: 002_add_pipeline_lost_columns
Revises: 001_add_autopilot_think_mode
Create Date: 2026-04-18

Context
-------
``ProjectPipeline`` gained two loss-tracking columns (lost_at + lost_reason)
in the TICKET-S10 commit that wired the 8-stage sales pipeline, but no
migration shipped for it. Dev SQLite DBs and any prod Postgres DB
created before this ran got a ``sqlite3.OperationalError: no such column:
project_pipeline.lost_at`` whenever /api/v1/pipeline/projects was called.

The fix is idempotent (``_column_exists`` guard) so it's safe to re-run
against DBs that already got the column via hot-patch.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_add_pipeline_lost_columns"
down_revision: str | None = "001_add_autopilot_think_mode"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table: str, column: str) -> bool:
    """Check if a column already exists (safe for re-runs)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c["name"] for c in inspector.get_columns(table)]
    return column in columns


def _index_exists(table: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(ix["name"] == index_name for ix in inspector.get_indexes(table))


def upgrade() -> None:
    """Add loss-tracking columns to project_pipeline.

    A deal can be lost from ANY of the 8 stages -- not just the final
    ones -- so these columns are orthogonal to the stage-transition
    timestamps (discovered_at, qualified_at, ..., closed_at).
    """
    if not _column_exists("project_pipeline", "lost_at"):
        op.add_column(
            "project_pipeline",
            sa.Column("lost_at", sa.DateTime(), nullable=True),
        )

    # Index on lost_at so "show me this quarter's losses" queries
    # don't scan the whole table.
    if not _index_exists("project_pipeline", "ix_project_pipeline_lost_at"):
        op.create_index(
            "ix_project_pipeline_lost_at",
            "project_pipeline",
            ["lost_at"],
        )

    if not _column_exists("project_pipeline", "lost_reason"):
        op.add_column(
            "project_pipeline",
            sa.Column("lost_reason", sa.String(200), nullable=True),
        )


def downgrade() -> None:
    if _column_exists("project_pipeline", "lost_reason"):
        op.drop_column("project_pipeline", "lost_reason")
    if _index_exists("project_pipeline", "ix_project_pipeline_lost_at"):
        op.drop_index("ix_project_pipeline_lost_at", table_name="project_pipeline")
    if _column_exists("project_pipeline", "lost_at"):
        op.drop_column("project_pipeline", "lost_at")
