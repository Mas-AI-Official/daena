"""Add push_subscriptions table (Phase 4 item 12, G6).

Revision ID: 021_add_push_subscriptions
Revises: 020_add_ckg_tables
Create Date: 2026-07-02

Context
-------
G6 mirrors push-worthy founder notifications (task_complete,
budget_alert, governance_rejection, runtime_disconnect,
privacy_blocked) to Web Push (VAPID, RFC 8030/8292) via the
NotificationChannel seam in ``app.services.notification_channels``.
The in-app ``notifications`` row stays the source of truth; push is a
best-effort one-way mirror, default OFF (``push_alerts_enabled``).

One row per browser/device subscription. Endpoints are globally
unique per browser profile, so ``endpoint`` carries a UNIQUE
constraint and subscribe upserts on it (device reassignment updates
ownership in place). Rows are soft-revoked via ``revoked_at``
(NULL = active) rather than deleted (Rule 2); a 404/410 from the push
service also sets ``revoked_at`` so dead endpoints stop being paid for.

SQLite dev picks the table up automatically via
``Base.metadata.create_all`` in ``main.py.lifespan``; PostgreSQL
production needs this migration. Every DDL step is guarded for
idempotency so re-running on a dev DB that already has the table is a
no-op.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import GUID

# revision identifiers, used by Alembic.
revision: str = "021_add_push_subscriptions"
down_revision: str | None = "020_add_ckg_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Idempotency helpers -- mirror migrations 005-020.

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
    """Create the push_subscriptions table and its indexes."""

    if not _table_exists("push_subscriptions"):
        op.create_table(
            "push_subscriptions",
            sa.Column("id", GUID(), nullable=False),
            sa.Column("tenant_id", GUID(), nullable=False),
            sa.Column("user_id", GUID(), nullable=False),
            sa.Column("endpoint", sa.String(1024), nullable=False),
            sa.Column("p256dh", sa.String(200), nullable=False),
            sa.Column("auth", sa.String(100), nullable=False),
            sa.Column("user_agent", sa.String(200), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                nullable=True, onupdate=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id", name="pk_push_subscriptions"),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["tenants.id"],
                name="fk_push_subscriptions_tenant_id_tenants",
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["user_id"], ["users.id"],
                name="fk_push_subscriptions_user_id_users",
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint(
                "endpoint",
                name="uq_push_subscriptions_endpoint",
            ),
        )

    if not _index_exists("push_subscriptions", "ix_push_subscriptions_tenant_id"):
        op.create_index(
            "ix_push_subscriptions_tenant_id", "push_subscriptions", ["tenant_id"],
        )
    if not _index_exists("push_subscriptions", "ix_push_subscriptions_user_id"):
        op.create_index(
            "ix_push_subscriptions_user_id", "push_subscriptions", ["user_id"],
        )
    if not _index_exists(
        "push_subscriptions", "ix_push_subscriptions_user_id_revoked_at",
    ):
        op.create_index(
            "ix_push_subscriptions_user_id_revoked_at", "push_subscriptions",
            ["user_id", "revoked_at"],
        )


def downgrade() -> None:
    """Drop indexes then table (dev rollback only; prod archives, never drops)."""
    for index_name in (
        "ix_push_subscriptions_user_id_revoked_at",
        "ix_push_subscriptions_user_id",
        "ix_push_subscriptions_tenant_id",
    ):
        if _index_exists("push_subscriptions", index_name):
            op.drop_index(index_name, table_name="push_subscriptions")
    if _table_exists("push_subscriptions"):
        op.drop_table("push_subscriptions")
