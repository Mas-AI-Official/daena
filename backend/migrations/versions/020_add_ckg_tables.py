"""Add ckg_insight + ckg_transfer_edge tables (Phase 3 item 8, G3).

Revision ID: 020_add_ckg_tables
Revises: 019_add_scan_reports
Create Date: 2026-07-02

Context
-------
The Cognitive Knowledge Graph used to persist ONLY to a single global
``graph.json`` side-car (``app.services.cognition.knowledge_graph``), which has
no tenant scope (Rule 9 leak) and races under concurrent writes (full-file JSON
rewrites, no lock). The governed chat flow now reads/writes through
``app.services.cognition.ckg_store.CkgStore`` against these two relational
tables instead. The legacy JSON class is retained UNTOUCHED for the
tenant-agnostic security scan engine (P2 follow-up: migrate that path too).

SQLite dev picks these tables up automatically via ``Base.metadata.create_all``
in ``main.py.lifespan``; PostgreSQL production needs this migration (same
rationale as 008/017). Every DDL step is guarded for idempotency so re-running
on a dev DB that already has the tables is a no-op.

Schema
------
``ckg_insight`` -- one learned, domain-abstracted pattern per (tenant, hash):
  * id GUID PK; tenant_id GUID NOT NULL FK tenants.id CASCADE (TenantMixin)
  * insight_hash String(16) NOT NULL -- sha256[:16] of the abstracted pattern
  * raw_observation / abstracted_pattern Text NOT NULL
  * origin_domain String(32) NOT NULL
  * applicable_domains / evidence_sources / tags JSONBCompat NOT NULL (lists)
  * confidence Float; evidence_count Integer; nbmf_tier Integer; transfer_score Float
  * created_at / updated_at (TimestampMixin; updated_at doubles as last-validated)
  * UNIQUE (tenant_id, insight_hash) -- reinforce collapses onto one row

``ckg_transfer_edge`` -- structural-similarity link between two insights:
  * id GUID PK; tenant_id GUID NOT NULL FK tenants.id CASCADE
  * source_hash / target_hash String(16) NOT NULL -- reference insights by hash
  * source_domain / target_domain String(32) NOT NULL
  * similarity Float; validated Boolean
  * UNIQUE (tenant_id, source_hash, target_hash)

Cross-dialect via ``GUID`` / ``JSONBCompat`` decorators (Postgres vs SQLite).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import GUID, JSONBCompat

# revision identifiers, used by Alembic.
revision: str = "020_add_ckg_tables"
down_revision: str | None = "019_add_scan_reports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Idempotency helpers -- mirror migrations 005-019.

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
    """Create ckg_insight + ckg_transfer_edge tables and their indexes."""

    if not _table_exists("ckg_insight"):
        op.create_table(
            "ckg_insight",
            sa.Column("id", GUID(), nullable=False),
            sa.Column("tenant_id", GUID(), nullable=False),
            sa.Column("insight_hash", sa.String(16), nullable=False),
            sa.Column("raw_observation", sa.Text, nullable=False),
            sa.Column("abstracted_pattern", sa.Text, nullable=False),
            sa.Column("origin_domain", sa.String(32), nullable=False),
            sa.Column("applicable_domains", JSONBCompat(), nullable=False),
            sa.Column("confidence", sa.Float, nullable=False),
            sa.Column("evidence_count", sa.Integer, nullable=False),
            sa.Column("evidence_sources", JSONBCompat(), nullable=False),
            sa.Column("nbmf_tier", sa.Integer, nullable=False),
            sa.Column("tags", JSONBCompat(), nullable=False),
            sa.Column("transfer_score", sa.Float, nullable=False),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                nullable=True, onupdate=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id", name="pk_ckg_insight"),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["tenants.id"],
                name="fk_ckg_insight_tenant_id_tenants",
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint(
                "tenant_id", "insight_hash",
                name="uq_ckg_insight_tenant_hash",
            ),
        )

    if not _index_exists("ckg_insight", "ix_ckg_insight_tenant_id"):
        op.create_index(
            "ix_ckg_insight_tenant_id", "ckg_insight", ["tenant_id"],
        )
    if not _index_exists("ckg_insight", "ix_ckg_insight_insight_hash"):
        op.create_index(
            "ix_ckg_insight_insight_hash", "ckg_insight", ["insight_hash"],
        )
    if not _index_exists("ckg_insight", "ix_ckg_insight_tenant_domain"):
        op.create_index(
            "ix_ckg_insight_tenant_domain", "ckg_insight",
            ["tenant_id", "origin_domain"],
        )

    if not _table_exists("ckg_transfer_edge"):
        op.create_table(
            "ckg_transfer_edge",
            sa.Column("id", GUID(), nullable=False),
            sa.Column("tenant_id", GUID(), nullable=False),
            sa.Column("source_hash", sa.String(16), nullable=False),
            sa.Column("target_hash", sa.String(16), nullable=False),
            sa.Column("source_domain", sa.String(32), nullable=False),
            sa.Column("target_domain", sa.String(32), nullable=False),
            sa.Column("similarity", sa.Float, nullable=False),
            sa.Column("validated", sa.Boolean, nullable=False),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                nullable=True, onupdate=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id", name="pk_ckg_transfer_edge"),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["tenants.id"],
                name="fk_ckg_transfer_edge_tenant_id_tenants",
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint(
                "tenant_id", "source_hash", "target_hash",
                name="uq_ckg_edge_tenant_src_tgt",
            ),
        )

    if not _index_exists("ckg_transfer_edge", "ix_ckg_transfer_edge_tenant_id"):
        op.create_index(
            "ix_ckg_transfer_edge_tenant_id", "ckg_transfer_edge", ["tenant_id"],
        )
    if not _index_exists("ckg_transfer_edge", "ix_ckg_transfer_edge_source_hash"):
        op.create_index(
            "ix_ckg_transfer_edge_source_hash", "ckg_transfer_edge",
            ["source_hash"],
        )
    if not _index_exists("ckg_transfer_edge", "ix_ckg_transfer_edge_target_hash"):
        op.create_index(
            "ix_ckg_transfer_edge_target_hash", "ckg_transfer_edge",
            ["target_hash"],
        )


def downgrade() -> None:
    """Drop indexes then tables (dev rollback only; prod archives, never drops)."""
    for index_name in (
        "ix_ckg_transfer_edge_target_hash",
        "ix_ckg_transfer_edge_source_hash",
        "ix_ckg_transfer_edge_tenant_id",
    ):
        if _index_exists("ckg_transfer_edge", index_name):
            op.drop_index(index_name, table_name="ckg_transfer_edge")
    if _table_exists("ckg_transfer_edge"):
        op.drop_table("ckg_transfer_edge")

    for index_name in (
        "ix_ckg_insight_tenant_domain",
        "ix_ckg_insight_insight_hash",
        "ix_ckg_insight_tenant_id",
    ):
        if _index_exists("ckg_insight", index_name):
            op.drop_index(index_name, table_name="ckg_insight")
    if _table_exists("ckg_insight"):
        op.drop_table("ckg_insight")
