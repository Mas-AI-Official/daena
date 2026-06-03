"""Add user_quotas table (BILL-001).

Revision ID: 008_add_user_quotas
Revises: 007_connection_v2_registry
Create Date: 2026-06-02

Context
-------
The ``UserQuota`` model (app/models/financial.py) backs CostGuard's
per-user budget enforcement (monthly_credit_usd, spend_this_month_usd,
overage_action, daily_credit_usd, spend_today_usd). In DEV the table is
created by ``Base.metadata.create_all``, but production Postgres is owned
by Alembic and NO prior migration created ``user_quotas``. So on a fresh
production deploy CostGuard's per-user quota path would hit a missing
table at runtime. This migration creates it so prod matches the model.

Idempotency
-----------
Mirrors migrations 003-007: the table create is guarded by
``_table_exists`` so re-running on a partially-applied state is safe.

Cross-dialect
-------------
Uses the model-side GUID decorator so SQLite dev and PostgreSQL prod
produce the same ORM-visible columns. Column types/defaults mirror
app/models/financial.py::UserQuota exactly.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import GUID

# revision identifiers, used by Alembic.
revision: str = "008_add_user_quotas"
down_revision: str | None = "007_connection_v2_registry"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table in inspector.get_table_names()


def upgrade() -> None:
    """Create user_quotas (per-user budget enforcement table)."""
    if _table_exists("user_quotas"):
        return

    op.create_table(
        "user_quotas",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("tenant_id", GUID(), nullable=False),
        sa.Column("user_id", GUID(), nullable=False),
        sa.Column("plan_tier", sa.String(20), nullable=False, server_default="FREE"),
        sa.Column(
            "monthly_credit_usd", sa.Numeric(10, 2),
            nullable=False, server_default="0.50",
        ),
        sa.Column(
            "spend_this_month_usd", sa.Numeric(10, 6),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "daily_credit_usd", sa.Numeric(10, 2),
            nullable=True, server_default="0.10",
        ),
        sa.Column(
            "spend_today_usd", sa.Numeric(10, 6),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "overage_action", sa.String(20),
            nullable=False, server_default="fallback_free",
        ),
        sa.Column(
            "max_tenant_share_pct", sa.Integer,
            nullable=False, server_default="50",
        ),
        sa.Column(
            "admin_override", sa.Boolean,
            nullable=False, server_default=sa.false(),
        ),
        sa.Column(
            "period_start", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=True, onupdate=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_user_quotas"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"],
            name="fk_user_quotas_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_user_quotas_user_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("user_id", name="uq_user_quotas_user_id"),
    )
    op.create_index("ix_user_quotas_tenant_id", "user_quotas", ["tenant_id"])
    op.create_index("ix_user_quotas_user_id", "user_quotas", ["user_id"])


def downgrade() -> None:
    """Drop user_quotas."""
    if _table_exists("user_quotas"):
        op.drop_index("ix_user_quotas_user_id", table_name="user_quotas")
        op.drop_index("ix_user_quotas_tenant_id", table_name="user_quotas")
        op.drop_table("user_quotas")
