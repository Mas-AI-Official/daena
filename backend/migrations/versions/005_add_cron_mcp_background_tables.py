"""Add cron_runs, mcp_servers, background_tasks tables.

Revision ID: 005_add_cron_mcp_background_tables
Revises: 004_add_chat_session_workstream_fk
Create Date: 2026-04-29

Context
-------
Three new ORM models landed in today's audit-repair pass and need a
real Alembic migration so PostgreSQL production picks them up. SQLite
dev already has them via ``Base.metadata.create_all`` in
``main.py.lifespan``; this migration brings prod into alignment without
disturbing the existing four migrations.

Tables created
--------------
* ``cron_runs`` (system-tenant, no TenantMixin) -- one row per cron
  scheduler ``check_and_run`` firing. Replaces the prior fictional
  ``last_result = "executed"`` literal with a real audit trail of
  runtime / duration / cost / tokens / output / error per attempt.
* ``mcp_servers`` (TenantMixin) -- persistence layer behind
  ``MCPRegistry`` so MCP servers survive a process restart. Identified
  by ``(tenant_id, server_key)`` with the unique constraint named
  ``uq_mcp_servers_tenant_server_key`` to match the model declaration.
  ``created_by_user_id`` FKs ``users.id`` ON DELETE SET NULL.
  ``extra_metadata`` JSONB (or JSON on SQLite via JSONBCompat) holds
  governance overrides + transport hints.
* ``background_tasks`` (TenantMixin) -- crash-safe persistence for the
  autopilot queue. ``status`` and ``session_id`` are indexed because
  the queue lookup hot path filters by them. Matches the in-memory
  dataclass ``id`` so the queue and DB stay in sync without a
  separate mapping layer.

Idempotency
-----------
Following the established Daena pattern (see
``003_add_workstreams.py``): every ``CREATE TABLE`` and ``CREATE
INDEX`` is guarded by ``_table_exists`` / ``_index_exists`` so running
the migration on a SQLite dev DB whose tables were already produced by
``Base.metadata.create_all`` is a no-op. Re-running on a partially-
applied state is also safe.

Cross-dialect
-------------
Column types follow the model declarations: ``GUID`` (String(36) on
SQLite, UUID on Postgres), ``JSONBCompat`` (JSON on SQLite, JSONB on
Postgres). For the migration we use the model-side decorator types
directly via ``app.models.base`` rather than re-declaring them here,
so the migration matches the live schema exactly.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import GUID, JSONBCompat

# revision identifiers, used by Alembic.
revision: str = "005_add_cron_mcp_background_tables"
down_revision: str | None = "004_add_chat_session_workstream_fk"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Idempotency helpers (Daena pattern, see 003_add_workstreams).

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
    """Create cron_runs, mcp_servers, background_tasks (in dependency order)."""

    # cron_runs: system-tenant, no TenantMixin, no FK
    if not _table_exists("cron_runs"):
        op.create_table(
            "cron_runs",
            sa.Column("id", GUID(), nullable=False),
            sa.Column("job_id", sa.String(100), nullable=False),
            sa.Column("runtime", sa.String(50), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("duration_ms", sa.Integer, nullable=True),
            sa.Column("summary", sa.String(500), nullable=True),
            sa.Column("full_text", sa.Text, nullable=True),
            sa.Column("error", sa.Text, nullable=True),
            sa.Column("cost_usd", sa.Float, nullable=False, server_default="0.0"),
            sa.Column("tokens_in", sa.Integer, nullable=False, server_default="0"),
            sa.Column("tokens_out", sa.Integer, nullable=False, server_default="0"),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                nullable=True, onupdate=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id", name="pk_cron_runs"),
        )

    if not _index_exists("cron_runs", "ix_cron_runs_job_id"):
        op.create_index("ix_cron_runs_job_id", "cron_runs", ["job_id"])

    # mcp_servers: TenantMixin, FK to tenants + users, unique(tenant_id, server_key)
    if not _table_exists("mcp_servers"):
        op.create_table(
            "mcp_servers",
            sa.Column("id", GUID(), nullable=False),
            sa.Column("server_key", sa.String(100), nullable=False),
            sa.Column("display_name", sa.String(200), nullable=False),
            sa.Column("description", sa.String(500), nullable=True),
            sa.Column("command", sa.String(500), nullable=True),
            sa.Column(
                "args", JSONBCompat(),
                nullable=False, server_default="[]",
            ),
            sa.Column("package", sa.String(200), nullable=True),
            sa.Column("server_url", sa.String(500), nullable=True),
            sa.Column(
                "status", sa.String(20),
                nullable=False, server_default="DISCOVERED",
            ),
            sa.Column("last_health_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "last_health_ok", sa.Boolean,
                nullable=False, server_default="false",
            ),
            sa.Column("created_by_user_id", GUID(), nullable=True),
            sa.Column(
                "auto_loaded", sa.Boolean,
                nullable=False, server_default="false",
            ),
            sa.Column(
                "extra_metadata", JSONBCompat(),
                nullable=False, server_default="{}",
            ),
            sa.Column("tenant_id", GUID(), nullable=False),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                nullable=True, onupdate=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id", name="pk_mcp_servers"),
            sa.ForeignKeyConstraint(
                ["created_by_user_id"], ["users.id"],
                name="fk_mcp_servers_created_by_user_id_users",
                ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["tenants.id"],
                name="fk_mcp_servers_tenant_id_tenants",
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint(
                "tenant_id", "server_key",
                name="uq_mcp_servers_tenant_server_key",
            ),
        )

    if not _index_exists("mcp_servers", "ix_mcp_servers_server_key"):
        op.create_index(
            "ix_mcp_servers_server_key", "mcp_servers", ["server_key"],
        )
    if not _index_exists("mcp_servers", "ix_mcp_servers_tenant_id"):
        op.create_index(
            "ix_mcp_servers_tenant_id", "mcp_servers", ["tenant_id"],
        )

    # background_tasks: TenantMixin, FK to tenants, indexed status + session_id
    if not _table_exists("background_tasks"):
        op.create_table(
            "background_tasks",
            sa.Column("id", GUID(), nullable=False),
            sa.Column("session_id", sa.String(100), nullable=False),
            sa.Column("description", sa.String(500), nullable=False),
            sa.Column(
                "status", sa.String(20),
                nullable=False, server_default="queued",
            ),
            sa.Column(
                "priority", sa.String(5),
                nullable=False, server_default="P2",
            ),
            sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("result", JSONBCompat(), nullable=True),
            sa.Column("error", sa.String(1000), nullable=True),
            sa.Column("runtime", sa.String(50), nullable=True),
            sa.Column(
                "cost_usd", sa.Float,
                nullable=False, server_default="0.0",
            ),
            sa.Column("parent_request_id", sa.String(100), nullable=True),
            sa.Column("tenant_id", GUID(), nullable=False),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                nullable=True, onupdate=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id", name="pk_background_tasks"),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["tenants.id"],
                name="fk_background_tasks_tenant_id_tenants",
                ondelete="CASCADE",
            ),
        )

    if not _index_exists("background_tasks", "ix_background_tasks_tenant_id"):
        op.create_index(
            "ix_background_tasks_tenant_id", "background_tasks", ["tenant_id"],
        )
    if not _index_exists("background_tasks", "ix_background_tasks_session_id"):
        op.create_index(
            "ix_background_tasks_session_id", "background_tasks", ["session_id"],
        )
    if not _index_exists("background_tasks", "ix_background_tasks_status"):
        op.create_index(
            "ix_background_tasks_status", "background_tasks", ["status"],
        )


def downgrade() -> None:
    """Drop tables and indexes in reverse order.

    Indexes drop first (so a partial state with table-but-no-indexes
    still tears down cleanly), then tables.
    """
    # background_tasks
    if _index_exists("background_tasks", "ix_background_tasks_status"):
        op.drop_index("ix_background_tasks_status", table_name="background_tasks")
    if _index_exists("background_tasks", "ix_background_tasks_session_id"):
        op.drop_index("ix_background_tasks_session_id", table_name="background_tasks")
    if _index_exists("background_tasks", "ix_background_tasks_tenant_id"):
        op.drop_index("ix_background_tasks_tenant_id", table_name="background_tasks")
    if _table_exists("background_tasks"):
        op.drop_table("background_tasks")

    # mcp_servers
    if _index_exists("mcp_servers", "ix_mcp_servers_tenant_id"):
        op.drop_index("ix_mcp_servers_tenant_id", table_name="mcp_servers")
    if _index_exists("mcp_servers", "ix_mcp_servers_server_key"):
        op.drop_index("ix_mcp_servers_server_key", table_name="mcp_servers")
    if _table_exists("mcp_servers"):
        op.drop_table("mcp_servers")

    # cron_runs
    if _index_exists("cron_runs", "ix_cron_runs_job_id"):
        op.drop_index("ix_cron_runs_job_id", table_name="cron_runs")
    if _table_exists("cron_runs"):
        op.drop_table("cron_runs")
