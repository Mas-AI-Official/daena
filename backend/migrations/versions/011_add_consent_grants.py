"""Add consent_grants table.

Revision ID: 011_add_consent_grants
Revises: 010_add_connector_instance_owner_email
Create Date: 2026-05-04

Context
-------
PR-CONN-CONSENT-DB-PERSISTENCE (Sprint-6 PR-5, 2026-05-04):
Sprint-4 + Sprint-5 shipped the Asset Shield consent gate with an
in-memory ``ConsentStore`` that survives only the lifetime of one
FastAPI process. This migration creates the persistent table that
backs the new ``DBConsentStore`` so grants survive restarts and
multi-instance deploy.

The schema is intentionally minimal:

  * id (UUID PK)
  * tenant_id (TenantMixin -- FK + index)
  * user_id (nullable; audit only -- match contract is tenant_id)
  * plugin_id (str)
  * skill_id (str)
  * category (str -- raw enum value)
  * expires_at (timestamp with TZ; indexed for GC)
  * consumed_at (nullable timestamp; the single-use marker)
  * created_at / updated_at (TimestampMixin)

NEVER stores: token values, operator inputs, tool args, response
previews, or any execution payload. The grant is metadata only.

Idempotency
-----------
Mirrors migrations 002 / 008 / 009 / 010 patterns:

  * Table creation guarded by ``_table_exists``.
  * Indexes guarded individually so re-running on a partially-applied
    schema is safe.
  * Batch_alter_table NOT needed: this is a CREATE TABLE only, no
    ALTER on existing tables.

Cross-dialect
-------------
* Postgres: native CREATE TABLE + CREATE INDEX.
* SQLite: identical statements; no batch_alter required for create.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "011_add_consent_grants"
down_revision: str | None = "010_add_connector_instance_owner_email"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_TABLE = "consent_grants"
_INDEX_MATCH = "ix_consent_grants_match_lookup"
_INDEX_EXPIRES = "ix_consent_grants_expires_at"
_INDEX_TENANT = "ix_consent_grants_tenant_id"


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
            sa.Column(
                "user_id", sa.String(36),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("plugin_id", sa.String(120), nullable=False),
            sa.Column("skill_id", sa.String(120), nullable=False),
            sa.Column("category", sa.String(50), nullable=False),
            sa.Column(
                "expires_at", sa.DateTime(timezone=True), nullable=False,
            ),
            sa.Column(
                "consumed_at", sa.DateTime(timezone=True), nullable=True,
            ),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                server_default=sa.func.now(), nullable=False,
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True), nullable=True,
            ),
        )

    # Indexes (each guarded so partial-state is safe).
    if not _index_exists(_TABLE, _INDEX_MATCH):
        op.create_index(
            _INDEX_MATCH, _TABLE,
            ["tenant_id", "plugin_id", "skill_id", "category"],
        )
    if not _index_exists(_TABLE, _INDEX_EXPIRES):
        op.create_index(_INDEX_EXPIRES, _TABLE, ["expires_at"])
    if not _index_exists(_TABLE, _INDEX_TENANT):
        op.create_index(_INDEX_TENANT, _TABLE, ["tenant_id"])


def downgrade() -> None:
    """Drop the consent_grants table.

    Per CLAUDE.md hard law #2 (never delete in production), this is
    dev rollback only.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _TABLE in inspector.get_table_names():
        for name in (_INDEX_MATCH, _INDEX_EXPIRES, _INDEX_TENANT):
            if _index_exists(_TABLE, name):
                op.drop_index(name, table_name=_TABLE)
        op.drop_table(_TABLE)
