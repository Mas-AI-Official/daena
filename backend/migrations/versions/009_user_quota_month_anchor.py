"""Add user_quotas.month_period_start monthly anchor (BILL-002).

Revision ID: 009_user_quota_month_anchor
Revises: 008_add_user_quotas
Create Date: 2026-06-02

Context
-------
UserQuota.period_start is reset on every DAILY rollover, so it cannot
detect a month change -- spend_this_month_usd accumulated forever and a
user's monthly quota looked permanently exhausted after their first
month. This adds ``month_period_start`` as the separate monthly anchor;
CostGuard resets spend_this_month_usd when its month/year differs from
now.

Idempotency
-----------
Guarded by a column-exists check so re-running is safe. ALTER TABLE ADD
COLUMN works on both SQLite (dev) and PostgreSQL (prod).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "009_user_quota_month_anchor"
down_revision: str | None = "008_add_user_quotas"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    """Add the monthly anchor column (nullable; lazy backfill in CostGuard)."""
    if _column_exists("user_quotas", "month_period_start"):
        return
    op.add_column(
        "user_quotas",
        sa.Column(
            "month_period_start", sa.DateTime(timezone=True),
            nullable=True, server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    if _column_exists("user_quotas", "month_period_start"):
        op.drop_column("user_quotas", "month_period_start")
