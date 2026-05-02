"""Add workstream spine skeleton fields (PR-5).

Revision ID: 009_add_workstream_spine_fields
Revises: 008_add_notifications
Create Date: 2026-05-02

Context
-------
PR-5 (Canonicalization: Workstream Execution Spine Skeleton) extends
the existing ``workstreams`` table with the six fields the Execution
Spine PRD requires for one-visible-lifecycle parity:

* ``source_type`` -- closed enum naming where the workstream came from
  (chat / scan / task / department / company_mode / manual / dev_demo).
  Drives the source badge in the WorkstreamsPage card. Defaults to
  ``manual`` so the existing ``POST /workstreams`` callers (which never
  declared a source) keep working unchanged.
* ``source_ref_id`` -- opaque GUID-shaped ref to the upstream artifact
  (task.id, scan_job.id, chat_message.id). NOT a FK because the target
  table varies per source_type; the frontend resolves the link.
* ``progress_percent`` -- SmallInteger 0..100. Informational hint; the
  state machine still owns lifecycle.
* ``artifact_refs`` -- JSON dict grouping side-effect artifact ids
  (scan_report_ids, draft_ids, file_ids, task_ids, approval_ids) so the
  detail drawer renders "Artifacts produced" with one-click navigation.
* ``audit_event_refs`` -- JSON list of ``audit_events.id`` strings the
  workstream emitted; surfaces the "View N audit events" link.
* ``notification_refs`` -- JSON list of ``notifications.id`` strings the
  workstream emitted; cross-links the bell.

All six are additive. No existing column is modified. No data is
backfilled (the column server_default handles new and existing rows).

Idempotency
-----------
Per the established Daena pattern (002_add_pipeline_lost_columns,
008_add_notifications), every CREATE / ALTER guards on
``_column_exists`` / ``_index_exists`` / ``_pg_enum_exists`` so the
migration is safe to re-run against a SQLite dev DB whose schema was
auto-built by ``Base.metadata.create_all``.

Cross-dialect
-------------
The ``workstream_source_type`` enum is created as a native Postgres
ENUM TYPE (one CREATE TYPE pre-step) then referenced with
``create_type=False`` on the column. On SQLite the same ``sa.Enum(...)``
falls back to VARCHAR + CHECK. JSON columns are ``sa.JSON`` (the
project-wide cross-dialect alias matched by the model's ``JSONBCompat``).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "009_add_workstream_spine_fields"
down_revision: str | None = "008_add_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ── Enum value list (mirrored from app/models/workstream.py) ──────────
# Mirrored here so the migration is self-contained -- a future model
# rename cannot silently change what the migration records.
_SOURCE_TYPE_VALUES = (
    "chat",
    "scan",
    "task",
    "department",
    "company_mode",
    "manual",
    "dev_demo",
)


# ── Idempotency helpers (Daena pattern) ───────────────────────────────


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c["name"] for c in inspector.get_columns(table)]
    return column in columns


def _index_exists(table: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(ix["name"] == index_name for ix in inspector.get_indexes(table))


def _pg_enum_exists(name: str) -> bool:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return False
    res = bind.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = :n"),
        {"n": name},
    ).scalar()
    return bool(res)


# ── Schema operations ─────────────────────────────────────────────────


def upgrade() -> None:
    """Add the six PR-5 fields to ``workstreams``.

    Order:
      1. Pre-create ``workstream_source_type`` enum on Postgres so the
         column add can reference it without re-creation.
      2. ALTER TABLE ... ADD COLUMN for each new column, guarded by
         ``_column_exists`` so re-runs are safe.
      3. Create supporting index on ``source_type`` (filtered list views
         like "all task-sourced workstreams").
    """
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # 1. Postgres-only enum TYPE pre-create.
    if is_pg and not _pg_enum_exists("workstream_source_type"):
        op.execute(
            "CREATE TYPE workstream_source_type AS ENUM ("
            + ", ".join(f"'{v}'" for v in _SOURCE_TYPE_VALUES)
            + ")",
        )

    source_enum = sa.Enum(
        *_SOURCE_TYPE_VALUES,
        name="workstream_source_type",
        create_type=False,
    )

    # 2. ADD COLUMN (idempotent per column).
    if not _column_exists("workstreams", "source_type"):
        op.add_column(
            "workstreams",
            sa.Column(
                "source_type", source_enum,
                nullable=False, server_default="manual",
            ),
        )

    if not _column_exists("workstreams", "source_ref_id"):
        op.add_column(
            "workstreams",
            sa.Column("source_ref_id", sa.String(36), nullable=True),
        )

    if not _column_exists("workstreams", "progress_percent"):
        op.add_column(
            "workstreams",
            sa.Column(
                "progress_percent", sa.SmallInteger,
                nullable=False, server_default="0",
            ),
        )

    if not _column_exists("workstreams", "artifact_refs"):
        op.add_column(
            "workstreams",
            sa.Column(
                "artifact_refs", sa.JSON,
                nullable=False, server_default="{}",
            ),
        )

    if not _column_exists("workstreams", "audit_event_refs"):
        op.add_column(
            "workstreams",
            sa.Column(
                "audit_event_refs", sa.JSON,
                nullable=False, server_default="[]",
            ),
        )

    if not _column_exists("workstreams", "notification_refs"):
        op.add_column(
            "workstreams",
            sa.Column(
                "notification_refs", sa.JSON,
                nullable=False, server_default="[]",
            ),
        )

    # 3. Source-type filter index. The other JSON columns are not indexed
    # because they are read by id-equality only inside the detail drawer.
    if not _index_exists("workstreams", "ix_workstreams_source_type"):
        op.create_index(
            "ix_workstreams_source_type", "workstreams", ["source_type"],
        )


def downgrade() -> None:
    """Reverse the upgrade in dependency order.

    Per CLAUDE.md hard law #2 (never delete in production), this is dev
    rollback only. Drop index first, then columns, then enum type.
    """
    if _index_exists("workstreams", "ix_workstreams_source_type"):
        op.drop_index("ix_workstreams_source_type", table_name="workstreams")

    for col in (
        "notification_refs",
        "audit_event_refs",
        "artifact_refs",
        "progress_percent",
        "source_ref_id",
        "source_type",
    ):
        if _column_exists("workstreams", col):
            op.drop_column("workstreams", col)

    bind = op.get_bind()
    if bind.dialect.name == "postgresql" and _pg_enum_exists(
        "workstream_source_type",
    ):
        op.execute("DROP TYPE workstream_source_type")
