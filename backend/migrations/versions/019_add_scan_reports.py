"""Add scan_reports table (PR-9 Klyntar Hardening).

Revision ID: 019_add_scan_reports
Revises: 018_add_tool_records
Create Date: 2026-06-15

Context
-------
Completed security scans persisted to disk JSON only
(``ScanWorkflow._persist_report`` -> ``{SECURITY_REPORTS_DIR}/{job_id}.json``).
Rule 17 (ADR-001) requires a database answer to "where does this persist?";
a disk loss or container rebuild wiped every historic report. This additive,
tenant-scoped table is the durable mirror, matching
``app.models.scan_report.ScanReportRecord``.

SQLite dev picks the table up automatically via ``Base.metadata.create_all`` in
``main.py.lifespan``. PostgreSQL production has no such fallback -- without this
migration the first durable-mirror write would raise ``ProgrammingError:
relation "scan_reports" does not exist``. The mirror write is fail-safe so that
error would be swallowed, silently losing durability; this migration is the
production counterpart that keeps it working.

Schema
------
Single table ``scan_reports``:

* ``id`` GUID PK (uuid4 default)
* ``tenant_id`` GUID NOT NULL FK tenants.id ON DELETE CASCADE (TenantMixin)
* ``job_id`` String(64) NOT NULL -- scan job id, unique per tenant
* ``target`` String(512) NULL -- scanned target
* ``tier`` String(32) NOT NULL DEFAULT 'scout' -- report tier
* ``status`` String(32) NOT NULL DEFAULT 'complete'
* ``summary`` Text NULL
* ``findings`` JSONBCompat NOT NULL DEFAULT '[]' -- full finding list
* ``severity_counts`` JSONBCompat NOT NULL DEFAULT '{}'
* ``cost_usd`` Float NOT NULL DEFAULT 0
* ``duration_secs`` Float NOT NULL DEFAULT 0
* ``report_pdf_path`` String(512) NULL
* ``created_at`` / ``updated_at`` from TimestampMixin

Constraints / indexes
---------------------
* ``uq_scan_reports_tenant_id_job_id`` unique (tenant_id, job_id)
* ``ix_scan_reports_tenant_id`` (from TenantMixin index=True)
* ``ix_scan_reports_tenant_id_created_at`` (from __table_args__) -- recent-scans query

Idempotency
-----------
Mirrors migrations 003-018. Every CREATE TABLE / CREATE INDEX is guarded by
``_table_exists`` / ``_index_exists`` so re-running on a SQLite dev DB whose
``scan_reports`` table was already produced by ``Base.metadata.create_all`` is a
no-op.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import GUID, JSONBCompat

# revision identifiers, used by Alembic.
revision: str = "019_add_scan_reports"
down_revision: str | None = "018_add_tool_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Idempotency helpers -- mirror migrations 005-018.

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
    """Create scan_reports table + 2 indexes."""

    if not _table_exists("scan_reports"):
        op.create_table(
            "scan_reports",
            sa.Column("id", GUID(), nullable=False),
            sa.Column("tenant_id", GUID(), nullable=False),
            sa.Column("job_id", sa.String(64), nullable=False),
            sa.Column("target", sa.String(512), nullable=True),
            sa.Column(
                "tier", sa.String(32),
                nullable=False, server_default="scout",
            ),
            sa.Column(
                "status", sa.String(32),
                nullable=False, server_default="complete",
            ),
            sa.Column("summary", sa.Text, nullable=True),
            sa.Column(
                "findings", JSONBCompat(),
                nullable=False, server_default="[]",
            ),
            sa.Column(
                "severity_counts", JSONBCompat(),
                nullable=False, server_default="{}",
            ),
            sa.Column(
                "cost_usd", sa.Float,
                nullable=False, server_default="0",
            ),
            sa.Column(
                "duration_secs", sa.Float,
                nullable=False, server_default="0",
            ),
            sa.Column("report_pdf_path", sa.String(512), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                nullable=True, onupdate=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id", name="pk_scan_reports"),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["tenants.id"],
                name="fk_scan_reports_tenant_id_tenants",
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint(
                "tenant_id", "job_id", name="uq_scan_reports_tenant_id_job_id",
            ),
        )

    # Single-column index from `index=True` on TenantMixin.tenant_id.
    if not _index_exists("scan_reports", "ix_scan_reports_tenant_id"):
        op.create_index(
            "ix_scan_reports_tenant_id", "scan_reports", ["tenant_id"],
        )

    # Composite index from the model's __table_args__ -- recent-scans query
    # (WHERE tenant_id = ? ORDER BY created_at DESC).
    if not _index_exists("scan_reports", "ix_scan_reports_tenant_id_created_at"):
        op.create_index(
            "ix_scan_reports_tenant_id_created_at", "scan_reports",
            ["tenant_id", "created_at"],
        )


def downgrade() -> None:
    """Drop indexes then table.

    Per CLAUDE.md hard law #2 (never delete, always archive), production
    downgrade should not run -- but provided for dev rollback. Indexes drop
    first so a partial state with table-but-no-indexes still tears down cleanly.
    """
    for index_name in (
        "ix_scan_reports_tenant_id_created_at",
        "ix_scan_reports_tenant_id",
    ):
        if _index_exists("scan_reports", index_name):
            op.drop_index(index_name, table_name="scan_reports")

    if _table_exists("scan_reports"):
        op.drop_table("scan_reports")
