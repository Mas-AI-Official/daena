"""Add secrets table + tenants.dek_wrapped column (envelope vault).

Revision ID: 006_secrets_envelope_vault
Revises: 005_add_cron_mcp_background_tables
Create Date: 2026-04-30

Context
-------
Phase 4a-2 of the Connections / MCP / Plugins / Runtime rebuild
(per docs/ADR-002-connections-rebuild-locked-decisions.md, decision
D-003 -- vault rewrite split into Phase 4a + 4b).

This migration lands the persistence side of the new envelope-encrypted
vault::

    DAENA_KEK (env, 32B)
        -> per-tenant KEK = HKDF-SHA256(KEK_seed, salt=tenant_id, info)
        -> per-tenant DEK = 32B random, stored in tenants.dek_wrapped
                            (AES-GCM under per-tenant KEK)
        -> secret_blob   = AES-256-GCM(plaintext, key=DEK,
                                       nonce=random_96b,
                                       aad=class || tenant_id || bound_to)

Two changes
-----------

1. ``secrets`` table -- one row per encrypted secret, keyed by
   (tenant_id, secret_class, bound_to). Maps directly onto the wire
   shape produced by ``app.core.vault_v2.encrypt_secret()``.

2. ``tenants.dek_wrapped`` column (nullable JSONB) -- holds the
   per-tenant Data Encryption Key wrapped under the per-tenant KEK.
   Populated lazily by the Phase 4b registry rewrite when a tenant
   first writes a secret. Existing tenants get NULL until then;
   ``app.core.vault_v2.unwrap_dek`` raises if called on NULL so the
   caller knows to provision a DEK first.

Idempotency
-----------
Both changes use ``_table_exists`` / ``_column_exists`` guards so the
migration is safe to re-run on a partially-applied state.

Cross-dialect
-------------
Uses model-side decorator types (``GUID``, ``JSONBCompat``,
``LargeBinary``) so SQLite dev and PostgreSQL prod produce the same
ORM-visible columns. The Phase 4a-2 lifespan ESSENTIALS step does NOT
read or write rows here -- it only validates that DAENA_KEK is loadable.
Row-level reads/writes start in Phase 4b.

Phase 4a-2 does NOT migrate any existing
``ConnectorInstance.credentials_encrypted`` rows. Those stay in the
legacy single-key vault format until Phase 4b ships
``scripts/migrate_vault_to_v2.py``. Until then, the legacy vault is
the production source of truth.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import GUID, JSONBCompat

# revision identifiers, used by Alembic.
revision: str = "006_secrets_envelope_vault"
down_revision: str | None = "005_add_cron_mcp_background_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Idempotency helpers -- mirror the pattern in migrations 003 / 004 / 005.

def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table in inspector.get_table_names()


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(table):
        return False
    return any(col["name"] == column for col in inspector.get_columns(table))


def _index_exists(table: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(table):
        return False
    return any(ix["name"] == index_name for ix in inspector.get_indexes(table))


def upgrade() -> None:
    """Create secrets table + tenants.dek_wrapped column."""

    # 1. tenants.dek_wrapped column -- nullable JSONB, populated lazily
    # by Phase 4b. NULL means "tenant has no DEK yet"; vault_v2.unwrap_dek
    # raises MalformedCiphertextError on a NULL/empty record so callers
    # know to provision one.
    if not _column_exists("tenants", "dek_wrapped"):
        op.add_column(
            "tenants",
            sa.Column("dek_wrapped", JSONBCompat(), nullable=True),
        )

    # 2. secrets table -- envelope-encrypted secret blobs.
    if not _table_exists("secrets"):
        op.create_table(
            "secrets",
            sa.Column("id", GUID(), nullable=False),
            sa.Column("tenant_id", GUID(), nullable=False),
            # AAD-bound identity: (tenant_id, secret_class, bound_to)
            # is unique. secret_class corresponds to vault_v2.SecretClass
            # enum values; bound_to is the row-level binding (e.g.
            # "connection_v2:01926e7f-..."). Both are stored plaintext
            # for indexing AND mixed into AES-GCM AAD so a row replant
            # across tenants/classes/bindings fails the GCM tag check.
            sa.Column("secret_class", sa.String(64), nullable=False),
            sa.Column("bound_to", sa.String(256), nullable=False),
            # GCM ciphertext + nonce + tag. Stored as BYTEA on Postgres,
            # BLOB on SQLite. Matches vault_v2.encrypt_secret wire shape
            # after base64 decode at the persistence layer.
            sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
            sa.Column("nonce", sa.LargeBinary(12), nullable=False),
            sa.Column("tag", sa.LargeBinary(16), nullable=False),
            # Versioning -- bumped on KEK rotation (kek_version), DEK
            # rotation (dek_version), or wire-format evolution
            # (format_version). Phase 4a-2 ships v1/v1/v2.
            sa.Column(
                "dek_version", sa.Integer,
                nullable=False, server_default="1",
            ),
            sa.Column(
                "kek_version", sa.Integer,
                nullable=False, server_default="1",
            ),
            sa.Column(
                "format_version", sa.Integer,
                nullable=False, server_default="2",
            ),
            # Wall-clock of last rotation; NULL until first rotated.
            # Distinct from ``updated_at`` which tracks any UPDATE.
            sa.Column(
                "rotated_at", sa.DateTime(timezone=True), nullable=True,
            ),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                nullable=True, onupdate=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id", name="pk_secrets"),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["tenants.id"],
                name="fk_secrets_tenant_id",
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint(
                "tenant_id", "secret_class", "bound_to",
                name="uq_secrets_tenant_class_bound",
            ),
        )

    if not _index_exists("secrets", "ix_secrets_tenant_class"):
        op.create_index(
            "ix_secrets_tenant_class", "secrets", ["tenant_id", "secret_class"],
        )


def downgrade() -> None:
    """Reverse: drop secrets table + tenants.dek_wrapped column.

    Per CLAUDE.md hard law #2 (never delete, always archive), production
    downgrade should not run -- the column is nullable and the table is
    empty pre-Phase-4b, so leaving them in place is harmless. This
    downgrade is provided for dev rollback only.
    """
    if _table_exists("secrets"):
        if _index_exists("secrets", "ix_secrets_tenant_class"):
            op.drop_index("ix_secrets_tenant_class", table_name="secrets")
        op.drop_table("secrets")

    if _column_exists("tenants", "dek_wrapped"):
        op.drop_column("tenants", "dek_wrapped")
