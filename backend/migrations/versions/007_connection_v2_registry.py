"""Add connection_v2 + capability + op_lock tables (Phase 4b PR 1).

Revision ID: 007_connection_v2_registry
Revises: 006_secrets_envelope_vault
Create Date: 2026-04-30

Context
-------
Phase 4b PR 1 of the Connections / MCP / Plugins / Runtime rebuild
(per docs/ADR-002-connections-rebuild-locked-decisions.md, decisions
D-001, D-002, D-005, D-007, D-008).

Three tables:

* ``connection_v2`` -- canonical row for all 6 connection kinds
  (CLI runtime, MCP server, provider, plugin, OAuth app, local model).
  Six explicit boolean truth dimensions (detected/configured/imported/
  reachable/authenticated/callable) plus per-dim failure storage so a
  failure on one dim never overwrites another's reason (D-001).

* ``connection_v2_capability`` -- side table for tools/models/commands
  exposed by a connection. Per V2 §5: avoids parent-row churn on
  capability changes; enables cross-connection capability-name lookup.

* ``connection_v2_op_lock`` -- TTL'd in-progress state per (connection_id, op).
  Per D-002: derive_label() reads this table instead of relying on
  brittle booleans on the parent row.

Idempotency
-----------
Mirrors the pattern in migrations 003-006. Each table create + index
is wrapped in a guard so re-running on a partially-applied state is
safe.

Cross-dialect
-------------
Uses model-side decorator types (GUID, JSONBCompat) so SQLite dev and
PostgreSQL prod produce the same ORM-visible columns.

Phase 4b PR 1 ships the schema + service layer behind the
USE_CONNECTION_REGISTRY_V2 feature flag (default False in production).
No live consumers query/write these tables until the flag is flipped on.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import GUID, JSONBCompat

# revision identifiers, used by Alembic.
revision: str = "007_connection_v2_registry"
down_revision: str | None = "006_secrets_envelope_vault"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Idempotency helpers -- mirror migrations 003-006.

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


def _per_dim_columns() -> list[sa.Column]:
    """6 truth dims x 3 fields each = 18 columns of metadata."""
    cols: list[sa.Column] = []
    for dim in ("detected", "configured", "imported", "reachable", "authenticated", "callable"):
        cols.append(sa.Column(dim, sa.Boolean, nullable=False, server_default=sa.false()))
        cols.append(sa.Column(f"{dim}_at", sa.DateTime(timezone=True), nullable=True))
        cols.append(sa.Column(f"{dim}_failure_at", sa.DateTime(timezone=True), nullable=True))
        cols.append(sa.Column(f"{dim}_failure_reason", sa.Text, nullable=True))
    return cols


def upgrade() -> None:
    """Create connection_v2, connection_v2_capability, connection_v2_op_lock."""

    # 1. connection_v2 -- canonical row for all 6 kinds.
    if not _table_exists("connection_v2"):
        op.create_table(
            "connection_v2",
            sa.Column("id", GUID(), nullable=False),
            sa.Column("tenant_id", GUID(), nullable=False),
            sa.Column("kind", sa.String(32), nullable=False),
            sa.Column("slug", sa.String(128), nullable=False),
            sa.Column("display_name", sa.String(256), nullable=False),
            sa.Column("canonical_key", sa.String(64), nullable=False),
            sa.Column("auth_method", sa.String(32), nullable=False),
            sa.Column("trust_tier", sa.String(16), nullable=False, server_default="official"),
            sa.Column("config", JSONBCompat(), nullable=False, server_default="{}"),
            sa.Column("vault_ref", sa.String(256), nullable=True),
            *_per_dim_columns(),
            sa.Column("healthy_call_ratio", sa.Float, nullable=False, server_default="1.0"),
            sa.Column("archived", sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("disabled", sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column(
                "governance_tier", sa.SmallInteger,
                nullable=False, server_default="2",
            ),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                nullable=True, onupdate=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id", name="pk_connection_v2"),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["tenants.id"],
                name="fk_connection_v2_tenant_id",
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint(
                "tenant_id", "kind", "slug",
                name="uq_connection_v2_tenant_kind_slug",
            ),
        )

    if not _index_exists("connection_v2", "ix_connection_v2_tenant_callable"):
        op.create_index(
            "ix_connection_v2_tenant_callable", "connection_v2",
            ["tenant_id", "callable"],
        )
    if not _index_exists("connection_v2", "ix_connection_v2_tenant_kind"):
        op.create_index(
            "ix_connection_v2_tenant_kind", "connection_v2",
            ["tenant_id", "kind"],
        )
    if not _index_exists("connection_v2", "ix_connection_v2_kind"):
        op.create_index("ix_connection_v2_kind", "connection_v2", ["kind"])
    if not _index_exists("connection_v2", "ix_connection_v2_canonical_key"):
        op.create_index(
            "ix_connection_v2_canonical_key", "connection_v2", ["canonical_key"],
        )

    # 2. connection_v2_capability -- side table for tool/model/command discovery.
    if not _table_exists("connection_v2_capability"):
        op.create_table(
            "connection_v2_capability",
            sa.Column("id", GUID(), nullable=False),
            sa.Column("connection_id", GUID(), nullable=False),
            sa.Column("kind", sa.String(32), nullable=False),
            sa.Column("name", sa.String(256), nullable=False),
            sa.Column("spec", JSONBCompat(), nullable=False, server_default="{}"),
            sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id", name="pk_connection_v2_capability"),
            sa.ForeignKeyConstraint(
                ["connection_id"], ["connection_v2.id"],
                name="fk_conn_v2_cap_connection_id",
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint(
                "connection_id", "kind", "name",
                name="uq_conn_v2_cap_conn_kind_name",
            ),
        )

    if not _index_exists("connection_v2_capability", "ix_conn_v2_cap_kind_name"):
        op.create_index(
            "ix_conn_v2_cap_kind_name", "connection_v2_capability",
            ["kind", "name"],
        )

    # 3. connection_v2_op_lock -- in-progress state per ADR-002 D-002.
    if not _table_exists("connection_v2_op_lock"):
        op.create_table(
            "connection_v2_op_lock",
            sa.Column("id", GUID(), nullable=False),
            sa.Column("connection_id", GUID(), nullable=False),
            sa.Column("op", sa.String(32), nullable=False),
            sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("owner_token", sa.String(64), nullable=False),
            sa.PrimaryKeyConstraint("id", name="pk_connection_v2_op_lock"),
            sa.ForeignKeyConstraint(
                ["connection_id"], ["connection_v2.id"],
                name="fk_conn_v2_op_lock_connection_id",
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint(
                "connection_id", "op",
                name="uq_conn_v2_op_lock_conn_op",
            ),
        )

    if not _index_exists("connection_v2_op_lock", "ix_conn_v2_op_lock_expires"):
        op.create_index(
            "ix_conn_v2_op_lock_expires", "connection_v2_op_lock",
            ["expires_at"],
        )


def downgrade() -> None:
    """Reverse: drop op_lock, capability, then connection_v2.

    Per CLAUDE.md hard law #2 (never delete, always archive), production
    downgrade should not run -- the tables are empty pre-Phase-4b-PR-2,
    so leaving them in place is harmless. Provided for dev rollback only.
    """
    for tbl in ("connection_v2_op_lock", "connection_v2_capability", "connection_v2"):
        if _table_exists(tbl):
            op.drop_table(tbl)
