"""Add plugin_policy_overrides table.

Revision ID: 012_add_plugin_policy_overrides
Revises: 011_add_consent_grants
Create Date: 2026-05-04

Context
-------
PR-CONN-PER-TENANT-POLICY-OVERRIDES (Sprint-6 PR-6, 2026-05-04):
operator-editable per-tenant override of the static governance
preset table. The override wins on read; the static preset remains
the baseline for cells without a row.

Schema:

  * id (UUID PK)
  * tenant_id (TenantMixin -- FK + index)
  * plugin_id (str)
  * skill_class (str -- raw enum value)
  * tier (str -- raw enum value)
  * rationale (str, nullable)
  * updated_by (FK to users.id, nullable)
  * created_at / updated_at (TimestampMixin)
  * unique (tenant_id, plugin_id, skill_class)

Idempotent in the same pattern as 011: guarded CREATE TABLE +
guarded indexes.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "012_add_plugin_policy_overrides"
down_revision: str | None = "011_add_consent_grants"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_TABLE = "plugin_policy_overrides"
_INDEX_TENANT = "ix_plugin_policy_overrides_tenant_id"
_UNIQUE_NAME = "uq_plugin_policy_overrides_tenant_plugin_class"


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table in inspector.get_table_names()


def _index_exists(table: str, name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return any(ix["name"] == name for ix in inspector.get_indexes(table))


def upgrade() -> None:
    if not _table_exists(_TABLE):
        op.create_table(
            _TABLE,
            sa.Column("id", sa.String(36), primary_key=True, nullable=False),
            sa.Column(
                "tenant_id", sa.String(36),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("plugin_id", sa.String(120), nullable=False),
            sa.Column("skill_class", sa.String(50), nullable=False),
            sa.Column("tier", sa.String(20), nullable=False),
            sa.Column("rationale", sa.String(500), nullable=True),
            sa.Column(
                "updated_by", sa.String(36),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                server_default=sa.func.now(), nullable=False,
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True), nullable=True,
            ),
            sa.UniqueConstraint(
                "tenant_id", "plugin_id", "skill_class",
                name=_UNIQUE_NAME,
            ),
        )

    if not _index_exists(_TABLE, _INDEX_TENANT):
        op.create_index(_INDEX_TENANT, _TABLE, ["tenant_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _TABLE in inspector.get_table_names():
        if _index_exists(_TABLE, _INDEX_TENANT):
            op.drop_index(_INDEX_TENANT, table_name=_TABLE)
        op.drop_table(_TABLE)
