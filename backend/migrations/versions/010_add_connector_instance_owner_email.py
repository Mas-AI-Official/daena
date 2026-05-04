"""Add owner_email to connector_instances + relax unique constraint.

Revision ID: 010_add_connector_instance_owner_email
Revises: 009_add_workstream_spine_fields
Create Date: 2026-05-03

Context
-------
PR-CONN-GMAIL-DRIVE-PRODUCTION-ALEMBIC (Sprint-5 PR-3, 2026-05-03):
Sprint-4 PR-3 + Sprint-5 PR-1 added two model-side changes that dev
SQLite picked up via ``create_all`` but production Postgres does NOT:

  1. ``connector_instances.owner_email`` (String 254, nullable, indexed)
     -- the operator-visible email a Google ConnectorInstance authenticates
     as.
  2. The unique constraint relaxed from
     ``(tenant_id, connector_id, user_id)`` to
     ``(tenant_id, connector_id, user_id, owner_email)`` so a single
     operator can hold multiple Gmail / Drive ConnectorInstances --
     one per Google account profile.

This migration brings production into parity. WITHOUT it, a Postgres
deploy would:

  * Fail to query / insert with the new ``owner_email`` field
    (column does not exist).
  * Block the second Gmail account with a UniqueViolation on the
    original ``(tenant, connector, user)`` triple.

Both failures would silently break the Sprint-5 picker UI (PR-2) for
any production tenant.

Idempotency
-----------
Mirrors migrations 002 / 008 / 009 patterns:

  * ``_column_exists`` / ``_index_exists`` / ``_constraint_exists`` guard
    each ALTER so re-running on a partially-applied or freshly-built
    schema (dev SQLite via ``create_all``) is safe.
  * Batch-alter wrapper used on SQLite (which cannot ALTER existing
    constraints in place; Alembic's batch mode recreates the table).

Cross-dialect
-------------
* Postgres: native ``ALTER TABLE ... ADD COLUMN`` + ``DROP CONSTRAINT``
  + ``ADD CONSTRAINT``.
* SQLite: ``op.batch_alter_table`` is the canonical Alembic affordance
  for schema changes that touch constraints. Inside the batch context
  Alembic creates a new table, copies data, drops the old, renames --
  all transparent to the rest of the migration.

Data preservation
-----------------
* Existing rows survive: the new column is nullable, no UPDATE forced.
* Existing constraint is dropped before the new one is added, so any
  rows that were unique under the old triple stay unique under the
  new quad (NULL owner_email + same triple = same uniqueness behavior
  per SQL NULL-equality semantics).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "010_add_connector_instance_owner_email"
down_revision: str | None = "009_add_workstream_spine_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ──────────────────────────────────────────────────────────────────
# Idempotency helpers (Daena migration pattern -- mirrors 002/008/009)
# ──────────────────────────────────────────────────────────────────


_TABLE = "connector_instances"
_NEW_CONSTRAINT = "uq_connector_instances_tenant_connector_user_email"
# The old constraint may exist under an SQLAlchemy-auto-named identifier
# OR a Postgres-auto-named one. We try BOTH plus a couple of likely
# variants. If none match, the constraint either was never created or
# is already gone -- safe either way.
_OLD_CONSTRAINT_CANDIDATES = (
    "uq_connector_instances_tenant_connector_user",
    "connector_instances_tenant_id_connector_id_user_id_key",
)


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return column in [c["name"] for c in inspector.get_columns(table)]


def _index_exists(table: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return any(ix["name"] == index_name for ix in inspector.get_indexes(table))


def _constraint_exists(table: str, name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    try:
        for uq in inspector.get_unique_constraints(table):
            if uq.get("name") == name:
                return True
    except Exception:
        # Some dialects (notably SQLite via SQLAlchemy older versions)
        # may not enumerate unnamed constraints reliably. Treat as
        # absent and rely on the batch_alter_table to do the right
        # thing during table recreation.
        pass
    return False


# ──────────────────────────────────────────────────────────────────
# Schema operations
# ──────────────────────────────────────────────────────────────────


def upgrade() -> None:
    """Add owner_email column + index + relaxed unique constraint.

    Order:
      1. ADD COLUMN owner_email (nullable, no backfill needed -- pre-PR-1
         rows simply remain NULL).
      2. CREATE INDEX on owner_email for the picker UI's per-provider
         account lookup.
      3. DROP the OLD unique constraint (tenant_id, connector_id,
         user_id) -- guarded so a missing constraint is fine.
      4. ADD the NEW unique constraint (tenant_id, connector_id,
         user_id, owner_email).
    """
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    # PROBE all required state up front (one inspector pass). After any
    # DDL the inspector cache may go stale; consolidating reads avoids
    # surprises like "no such column" when create_index runs after a
    # batch_alter_table that just added the column.
    need_col = not _column_exists(_TABLE, "owner_email")
    need_index = not _index_exists(
        _TABLE, "ix_connector_instances_owner_email",
    )
    drops_needed = [
        name for name in _OLD_CONSTRAINT_CANDIDATES
        if _constraint_exists(_TABLE, name)
    ]
    need_new_constraint = not _constraint_exists(_TABLE, _NEW_CONSTRAINT)

    if is_sqlite:
        # Single batch_alter_table -- everything in one table-recreate
        # transaction so the inspector cache cannot make any decision
        # against stale schema.
        if need_col or need_index or drops_needed or need_new_constraint:
            with op.batch_alter_table(_TABLE) as batch_op:
                if need_col:
                    batch_op.add_column(
                        sa.Column("owner_email", sa.String(254), nullable=True),
                    )
                if need_index:
                    batch_op.create_index(
                        "ix_connector_instances_owner_email", ["owner_email"],
                    )
                for name in drops_needed:
                    batch_op.drop_constraint(name, type_="unique")
                if need_new_constraint:
                    batch_op.create_unique_constraint(
                        _NEW_CONSTRAINT,
                        ["tenant_id", "connector_id", "user_id", "owner_email"],
                    )
    else:
        # Postgres: native ALTER statements.
        if need_col:
            op.add_column(
                _TABLE,
                sa.Column("owner_email", sa.String(254), nullable=True),
            )
        if need_index:
            op.create_index(
                "ix_connector_instances_owner_email", _TABLE, ["owner_email"],
            )
        for name in drops_needed:
            op.drop_constraint(name, _TABLE, type_="unique")
        if need_new_constraint:
            op.create_unique_constraint(
                _NEW_CONSTRAINT,
                _TABLE,
                ["tenant_id", "connector_id", "user_id", "owner_email"],
            )


def downgrade() -> None:
    """Reverse: drop new unique constraint + index + column.

    Per CLAUDE.md hard law #2 (never delete in production), this is dev
    rollback only. The original constraint is NOT recreated automatically
    -- doing so would risk a UniqueViolation if multi-account rows
    were created during the upgraded period. Operator must reconcile
    duplicates first then re-run upgrade.
    """
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    drop_constraint = _constraint_exists(_TABLE, _NEW_CONSTRAINT)
    drop_index = _index_exists(_TABLE, "ix_connector_instances_owner_email")
    drop_col = _column_exists(_TABLE, "owner_email")

    if is_sqlite:
        # Order matters: index drop MUST be in the same batch as the
        # column drop. ``batch_alter_table`` table-recreates and copies
        # ALL indexes onto the new table; if the index referencing
        # owner_email survives the batch boundary while the column
        # disappears, the recreated index errors with "no such column".
        if drop_constraint or drop_index or drop_col:
            with op.batch_alter_table(_TABLE) as batch_op:
                if drop_index:
                    batch_op.drop_index(
                        "ix_connector_instances_owner_email",
                    )
                if drop_constraint:
                    batch_op.drop_constraint(_NEW_CONSTRAINT, type_="unique")
                if drop_col:
                    batch_op.drop_column("owner_email")
    else:
        if drop_constraint:
            op.drop_constraint(_NEW_CONSTRAINT, _TABLE, type_="unique")
        if drop_index:
            op.drop_index(
                "ix_connector_instances_owner_email", table_name=_TABLE,
            )
        if drop_col:
            op.drop_column(_TABLE, "owner_email")
