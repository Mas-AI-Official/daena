"""Add research_drafts.structured_payload column

Sprint-12 PR-6 reconciliation (2026-05-05): Sprint-11 PR-2 added
``ResearchDraft.structured_payload`` to the model but the matching
migration was never authored. The model has been live in test
suites because pytest re-creates the schema from metadata, but the
dev / staging / prod SQLite + Postgres deployments never gained the
column. This migration fills that gap so live deployments running
Sprint-12 (which calls the column from the enrichment service)
boot cleanly.

Idempotent: skips if the column already exists.

Revision ID: 013_add_research_draft_structured_payload
Revises: 012_add_plugin_policy_overrides
Created: 2026-05-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "013_add_research_draft_structured_payload"
down_revision = "012_add_plugin_policy_overrides"
branch_labels = None
depends_on = None


_TABLE = "research_drafts"
_COLUMN = "structured_payload"


def _has_column(table: str, col: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        names = {c["name"] for c in inspector.get_columns(table)}
    except Exception:
        return False
    return col in names


def upgrade() -> None:
    if _has_column(_TABLE, _COLUMN):
        return
    # JSON column; nullable so existing rows don't need a backfill.
    # SQLite uses TEXT; Postgres uses JSONB. JSONBCompat is the
    # model-side adapter; here we just declare JSON which both
    # dialects accept.
    op.add_column(
        _TABLE,
        sa.Column(_COLUMN, sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    if not _has_column(_TABLE, _COLUMN):
        return
    with op.batch_alter_table(_TABLE) as batch_op:
        batch_op.drop_column(_COLUMN)
