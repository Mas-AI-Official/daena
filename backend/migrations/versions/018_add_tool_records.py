"""Add tool_records table (PR-8 Tool Registry).

Revision ID: 018_add_tool_records
Revises: 017_add_experience_log
Create Date: 2026-06-15

Context
-------
Tool discovery (``app.services.tool_lifecycle.tool_discovery.ToolDiscovery``)
used to read a hardcoded in-code ``TOOL_CATALOG`` constant only -- there was no
way for an operator to disable a tool, and nothing MCP servers or skills
registered at runtime ever persisted. PR-8 (plan 13.2) makes the catalog durable
and tenant-scoped: ``ToolDiscovery.from_db`` reads enabled ``tool_records`` rows
for the tenant, seeding once from ``TOOL_CATALOG`` on a fresh tenant and falling
back to the constant only if a read fails (fail-open, Rule 17).

SQLite dev picks the table up automatically via ``Base.metadata.create_all`` in
``main.py.lifespan``. PostgreSQL production has no such fallback -- without this
migration the first ``from_db`` would raise ``ProgrammingError: relation
"tool_records" does not exist`` (the failure mode migration 008 fixed for
notifications). This is the production counterpart, matching
``app.models.tool.ToolRecord`` (plan 13.2's ``ToolDefinition``).

Schema
------
Single table ``tool_records``:

* ``id`` GUID PK (uuid4 default)
* ``tenant_id`` GUID NOT NULL FK tenants.id ON DELETE CASCADE (TenantMixin)
* ``name`` String(100) NOT NULL -- stable slug, unique per tenant
* ``kind`` String(16) NOT NULL DEFAULT 'builtin' -- builtin | mcp | skill
* ``description`` Text NULL
* ``enabled`` Boolean NOT NULL DEFAULT true -- operator kill switch
* ``source_ref`` String(255) NULL -- mcp server id / skill id / catalog source
* ``schema`` JSONBCompat NOT NULL DEFAULT '{}' -- tool input schema
* ``meta`` JSONBCompat NOT NULL DEFAULT '{}' -- full ToolCandidate round-trip
* ``created_at`` / ``updated_at`` from TimestampMixin

Constraints / indexes
---------------------
* ``uq_tool_records_tenant_id_name`` unique (tenant_id, name) -- one row per tool
* ``ix_tool_records_tenant_id`` (from TenantMixin index=True)
* ``ix_tool_records_tenant_id_enabled`` (from __table_args__) -- discovery hot query

Idempotency
-----------
Mirrors migrations 003-017. Every CREATE TABLE / CREATE INDEX is guarded by
``_table_exists`` / ``_index_exists`` so re-running on a SQLite dev DB whose
``tool_records`` table was already produced by ``Base.metadata.create_all`` is a
no-op.

Cross-dialect
-------------
Uses model-side decorator types ``GUID`` (UUID on Postgres, String(36) on
SQLite) and ``JSONBCompat`` (JSONB on Postgres, JSON on SQLite). Other column
types are stdlib SQLAlchemy and round-trip identically across dialects.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import GUID, JSONBCompat

# revision identifiers, used by Alembic.
revision: str = "018_add_tool_records"
down_revision: str | None = "017_add_experience_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Idempotency helpers -- mirror migrations 005-017.

def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table in inspector.get_table_names()


def _index_exists(table: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(table):
        return False
    return any(ix["name"] == index_name for ix in inspector.get_indexes(table))


def upgrade() -> None:
    """Create tool_records table + 2 indexes."""

    if not _table_exists("tool_records"):
        op.create_table(
            "tool_records",
            sa.Column("id", GUID(), nullable=False),
            sa.Column("tenant_id", GUID(), nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column(
                "kind", sa.String(16),
                nullable=False, server_default="builtin",
            ),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column(
                "enabled", sa.Boolean,
                nullable=False, server_default="true",
            ),
            sa.Column("source_ref", sa.String(255), nullable=True),
            sa.Column(
                "schema", JSONBCompat(),
                nullable=False, server_default="{}",
            ),
            sa.Column(
                "meta", JSONBCompat(),
                nullable=False, server_default="{}",
            ),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                nullable=True, onupdate=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id", name="pk_tool_records"),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["tenants.id"],
                name="fk_tool_records_tenant_id_tenants",
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint(
                "tenant_id", "name", name="uq_tool_records_tenant_id_name",
            ),
        )

    # Single-column index from `index=True` on TenantMixin.tenant_id.
    if not _index_exists("tool_records", "ix_tool_records_tenant_id"):
        op.create_index(
            "ix_tool_records_tenant_id", "tool_records", ["tenant_id"],
        )

    # Composite index from the model's __table_args__ -- discovery hot query
    # (WHERE tenant_id = ? AND enabled = true).
    if not _index_exists("tool_records", "ix_tool_records_tenant_id_enabled"):
        op.create_index(
            "ix_tool_records_tenant_id_enabled", "tool_records",
            ["tenant_id", "enabled"],
        )


def downgrade() -> None:
    """Drop indexes then table.

    Per CLAUDE.md hard law #2 (never delete, always archive), production
    downgrade should not run -- but provided for dev rollback. Indexes drop
    first so a partial state with table-but-no-indexes still tears down cleanly.
    """
    for index_name in (
        "ix_tool_records_tenant_id_enabled",
        "ix_tool_records_tenant_id",
    ):
        if _index_exists("tool_records", index_name):
            op.drop_index(index_name, table_name="tool_records")

    if _table_exists("tool_records"):
        op.drop_table("tool_records")
