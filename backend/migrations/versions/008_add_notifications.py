"""Add notifications table (Phase 11 PR-S2 + PR-S2.1).

Revision ID: 008_add_notifications
Revises: 007_connection_v2_registry
Create Date: 2026-05-01

Context
-------
Phase 11 PR-S2 (commit 2e414cf) introduced ``app.models.notification.Notification``
and the ``NotificationService`` that writes one row per emitted in-app
notification. Phase 11 PR-S2.1 (commit f71892c) retrofitted three core
services to call ``NotificationService.emit(...)``:

* ``execution_service`` -- ``task_complete`` after a background task ends
* ``cost_guard`` -- ``budget_alert`` from the warn-tier preflight branch
  (deduped 60min per user)
* ``approval`` -- ``governance_rejection`` to the requester (not approver)

SQLite dev picked up the table automatically via
``Base.metadata.create_all`` in ``main.py.lifespan``. PostgreSQL
production has no such fallback -- every emit would raise
``sqlalchemy.exc.ProgrammingError: relation "notifications" does not
exist``. The DAENA Backend Blind-Spot Inventory (2026-05-01) flagged
this as the sole P0 production blocker.

Schema
------
Single table ``notifications`` matching ``Notification`` exactly:

* ``id`` GUID PK (uuid4 default)
* ``tenant_id`` GUID NOT NULL FK tenants.id ON DELETE CASCADE
* ``user_id`` GUID NOT NULL FK users.id ON DELETE CASCADE
* ``type`` String(40) NOT NULL -- event taxonomy (see _NOTIF_TYPES)
* ``title`` String(200) NOT NULL
* ``message`` Text NOT NULL
* ``severity`` String(20) NOT NULL DEFAULT 'info' -- info/success/warning/error
* ``source`` String(100) NULL -- attribution (e.g. "cost_guard.preflight")
* ``read_at`` DateTime(tz=True) NULL -- NULL = unread
* ``created_at`` / ``updated_at`` from TimestampMixin

Indexes (4 total)
-----------------
The Notification model declares ``index=True`` on three columns
(tenant_id, user_id, type) which translates to single-column indexes
``ix_notifications_<col>``. A fourth composite index
``ix_notifications_user_id_created_at`` is declared via ``__table_args__``
to support the bell hot-query: "give me my recent notifications,
newest first" (NotificationService.list_recent).

Idempotency
-----------
Mirrors migrations 003-007. Every CREATE TABLE and CREATE INDEX is
guarded by ``_table_exists`` / ``_index_exists`` so re-running on a
SQLite dev DB whose ``notifications`` table was already produced by
``Base.metadata.create_all`` is a no-op.

Cross-dialect
-------------
Uses model-side decorator type ``GUID`` (UUID on Postgres, String(36)
on SQLite). Other column types are stdlib SQLAlchemy and round-trip
identically across dialects.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import GUID

# revision identifiers, used by Alembic.
revision: str = "008_add_notifications"
down_revision: str | None = "007_connection_v2_registry"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Idempotency helpers -- mirror migrations 005-007.

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
    """Create notifications table + 4 indexes."""

    if not _table_exists("notifications"):
        op.create_table(
            "notifications",
            sa.Column("id", GUID(), nullable=False),
            sa.Column("tenant_id", GUID(), nullable=False),
            sa.Column("user_id", GUID(), nullable=False),
            sa.Column("type", sa.String(40), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("message", sa.Text, nullable=False),
            sa.Column(
                "severity", sa.String(20),
                nullable=False, server_default="info",
            ),
            sa.Column("source", sa.String(100), nullable=True),
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                nullable=True, onupdate=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id", name="pk_notifications"),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["tenants.id"],
                name="fk_notifications_tenant_id_tenants",
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["user_id"], ["users.id"],
                name="fk_notifications_user_id_users",
                ondelete="CASCADE",
            ),
        )

    # 3 single-column indexes from `index=True` on the model columns.
    if not _index_exists("notifications", "ix_notifications_tenant_id"):
        op.create_index(
            "ix_notifications_tenant_id", "notifications", ["tenant_id"],
        )
    if not _index_exists("notifications", "ix_notifications_user_id"):
        op.create_index(
            "ix_notifications_user_id", "notifications", ["user_id"],
        )
    if not _index_exists("notifications", "ix_notifications_type"):
        op.create_index(
            "ix_notifications_type", "notifications", ["type"],
        )

    # Composite index from the model's __table_args__ -- bell hot query.
    if not _index_exists(
        "notifications", "ix_notifications_user_id_created_at",
    ):
        op.create_index(
            "ix_notifications_user_id_created_at", "notifications",
            ["user_id", "created_at"],
        )


def downgrade() -> None:
    """Drop indexes then table.

    Per CLAUDE.md hard law #2 (never delete, always archive), production
    downgrade should not run -- but provided for dev rollback. Indexes
    drop first so a partial state with table-but-no-indexes still tears
    down cleanly.
    """
    for index_name in (
        "ix_notifications_user_id_created_at",
        "ix_notifications_type",
        "ix_notifications_user_id",
        "ix_notifications_tenant_id",
    ):
        if _index_exists("notifications", index_name):
            op.drop_index(index_name, table_name="notifications")

    if _table_exists("notifications"):
        op.drop_table("notifications")
