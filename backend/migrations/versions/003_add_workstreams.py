"""Add workstreams + workstream_events tables.

Revision ID: 003_add_workstreams
Revises: 002_add_pipeline_lost_columns
Create Date: 2026-04-25

Context
-------
Per the Council R3 lock (2026-04-25), Daena's visible unit of autonomy
is the **workstream**: a governed, interruptible thread of work owned by
a department, with goal + decisions + artifacts + blockers + audit
trail. The Workstream + WorkstreamEvent ORM models landed in
``app/models/workstream.py``; this migration creates their tables in
Postgres prod and brings the dev SQLite path into alignment.

Two tables:

* ``workstreams`` — one row per active or archived workstream, with the
  status enum (RUNNING / BLOCKED / WAITING_APPROVAL / COMPLETE / FAILED)
  and the escalation enum (STANDARD / HIGH_EFFORT / COUNCIL /
  QUINTESSENCE / HUMAN_REVIEW). Soft-deleted via the ``archived_at``
  column (per Daena's Hard Law #2 — "never delete, always archive").

* ``workstream_events`` — append-only timeline entries; one row per
  decision / artifact / tool call / approval / sub-agent spawn /
  completeness footer / state transition. The Workstreams Live Console
  renders these as the **Governed Execution Timeline**.

Idempotency
-----------
Daena's pattern: every migration is safe to re-run. We guard each
CREATE with ``_table_exists`` / ``_index_exists`` so dev SQLite (which
already auto-creates via ``Base.metadata.create_all``) doesn't double-
create, and so a partially-applied migration can be retried cleanly.

Enum strategy
-------------
We use ``sa.Enum(*values, name=...)``. On Postgres this creates native
``CREATE TYPE`` ENUM types with the given name; on SQLite it falls back
to VARCHAR with a CHECK constraint. The model declarations
(``SAEnum(WorkstreamStatus, name="workstream_status")``) match these
names so the ORM and the migration agree on the type identity. The
``checkfirst=True`` semantics on enum types in newer SQLAlchemy + Alembic
make repeat upgrades safe; for explicit safety we additionally pre-check
for the type via dialect-specific introspection in upgrade().
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003_add_workstreams"
down_revision: str | None = "002_add_pipeline_lost_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ── Enum value lists (mirrored from app/models/workstream.py) ─────────
# Mirrored here so the migration is self-contained — no model imports
# at migration time (Alembic env loads Base eagerly, but explicit values
# here mean a future model-rename can't silently change the migration).

_STATUS_VALUES = ("RUNNING", "BLOCKED", "WAITING_APPROVAL", "COMPLETE", "FAILED")
_ESCALATION_VALUES = (
    "STANDARD", "HIGH_EFFORT", "COUNCIL", "QUINTESSENCE", "HUMAN_REVIEW",
)
_EVENT_KIND_VALUES = (
    "STARTED", "REDIRECTED", "PAUSED", "RESUMED", "ESCALATED",
    "BLOCKED", "UNBLOCKED",
    "APPROVAL_REQUESTED", "APPROVAL_GRANTED", "APPROVAL_DENIED",
    "DECISION", "ARTIFACT", "TOOL_CALL",
    "SUB_AGENT_SPAWNED", "COMPLETENESS_FOOTER",
    "COMPLETED", "FAILED",
)


# ── Idempotency helpers (Daena pattern, see 002_add_pipeline_lost_columns) ──

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


def _pg_enum_exists(name: str) -> bool:
    """True if a Postgres ENUM TYPE with this name already exists."""
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
    """Create workstreams + workstream_events.

    Order:
      1. Pre-create the enum TYPEs on Postgres (so create_table can
         reference them without re-creation attempts).
      2. Create workstreams.
      3. Create workstream_events.
      4. Create supporting indexes.
    """
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # Enum types — Postgres only. SQLite stores the values as VARCHAR.
    if is_pg:
        if not _pg_enum_exists("workstream_status"):
            op.execute(
                "CREATE TYPE workstream_status AS ENUM ("
                + ", ".join(f"'{v}'" for v in _STATUS_VALUES)
                + ")",
            )
        if not _pg_enum_exists("workstream_escalation_level"):
            op.execute(
                "CREATE TYPE workstream_escalation_level AS ENUM ("
                + ", ".join(f"'{v}'" for v in _ESCALATION_VALUES)
                + ")",
            )
        if not _pg_enum_exists("workstream_event_kind"):
            op.execute(
                "CREATE TYPE workstream_event_kind AS ENUM ("
                + ", ".join(f"'{v}'" for v in _EVENT_KIND_VALUES)
                + ")",
            )

    # Build the enum descriptors AFTER the types exist (Alembic will
    # use the existing type rather than re-creating). On SQLite, these
    # collapse to VARCHAR + CHECK.
    status_enum = sa.Enum(
        *_STATUS_VALUES, name="workstream_status", create_type=False,
    )
    escalation_enum = sa.Enum(
        *_ESCALATION_VALUES, name="workstream_escalation_level", create_type=False,
    )
    event_kind_enum = sa.Enum(
        *_EVENT_KIND_VALUES, name="workstream_event_kind", create_type=False,
    )

    # ── workstreams ──
    if not _table_exists("workstreams"):
        op.create_table(
            "workstreams",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "tenant_id", sa.String(36),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "department_id", sa.String(36),
                sa.ForeignKey("departments.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id", sa.String(36),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("goal", sa.String(500), nullable=False),
            sa.Column(
                "status", status_enum,
                nullable=False, server_default="RUNNING",
            ),
            sa.Column("blocker_text", sa.String(500), nullable=True),
            sa.Column("next_step_text", sa.String(500), nullable=True),
            sa.Column(
                "escalation_level", escalation_enum,
                nullable=False, server_default="STANDARD",
            ),
            sa.Column("context", sa.JSON, nullable=False, server_default="{}"),
            sa.Column("total_tokens", sa.Integer, nullable=False, server_default="0"),
            sa.Column("total_cost_cents", sa.Integer, nullable=False, server_default="0"),
            sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "autopilot_paused", sa.Boolean,
                nullable=False, server_default=sa.false(),
            ),
            sa.Column("notes", sa.Text, nullable=True),
            # Soft-delete (SoftDeleteMixin)
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "archived_by", sa.String(36),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            # Timestamps
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                nullable=True, onupdate=sa.func.now(),
            ),
        )

    # Indexes for the workstreams list-by-tenant + status filter pattern.
    if not _index_exists("workstreams", "ix_workstreams_tenant_id"):
        op.create_index(
            "ix_workstreams_tenant_id", "workstreams", ["tenant_id"],
        )
    if not _index_exists("workstreams", "ix_workstreams_department_id"):
        op.create_index(
            "ix_workstreams_department_id", "workstreams", ["department_id"],
        )
    if not _index_exists("workstreams", "ix_workstreams_user_id"):
        op.create_index(
            "ix_workstreams_user_id", "workstreams", ["user_id"],
        )
    if not _index_exists("workstreams", "ix_workstreams_status"):
        op.create_index(
            "ix_workstreams_status", "workstreams", ["status"],
        )

    # ── workstream_events ──
    if not _table_exists("workstream_events"):
        op.create_table(
            "workstream_events",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "tenant_id", sa.String(36),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "workstream_id", sa.String(36),
                sa.ForeignKey("workstreams.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("kind", event_kind_enum, nullable=False),
            sa.Column("summary", sa.String(500), nullable=False),
            sa.Column("payload", sa.JSON, nullable=False, server_default="{}"),
            sa.Column(
                "occurred_at", sa.DateTime(timezone=True),
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
        )

    if not _index_exists("workstream_events", "ix_workstream_events_workstream_id"):
        op.create_index(
            "ix_workstream_events_workstream_id",
            "workstream_events",
            ["workstream_id"],
        )
    if not _index_exists("workstream_events", "ix_workstream_events_kind"):
        op.create_index(
            "ix_workstream_events_kind", "workstream_events", ["kind"],
        )
    if not _index_exists("workstream_events", "ix_workstream_events_occurred_at"):
        op.create_index(
            "ix_workstream_events_occurred_at",
            "workstream_events",
            ["occurred_at"],
        )
    if not _index_exists("workstream_events", "ix_workstream_events_tenant_id"):
        op.create_index(
            "ix_workstream_events_tenant_id",
            "workstream_events",
            ["tenant_id"],
        )


def downgrade() -> None:
    """Drop in reverse order: events first (FK to workstreams), then
    workstreams, then enum types on Postgres.
    """
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    if _table_exists("workstream_events"):
        op.drop_table("workstream_events")
    if _table_exists("workstreams"):
        op.drop_table("workstreams")

    if is_pg:
        if _pg_enum_exists("workstream_event_kind"):
            op.execute("DROP TYPE workstream_event_kind")
        if _pg_enum_exists("workstream_escalation_level"):
            op.execute("DROP TYPE workstream_escalation_level")
        if _pg_enum_exists("workstream_status"):
            op.execute("DROP TYPE workstream_status")
