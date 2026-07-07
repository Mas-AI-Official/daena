"""Add experience_log table (PR-7 Cognition Closure).

Revision ID: 017_add_experience_log
Revises: 016_add_run_trace_events
Create Date: 2026-06-14

Context
-------
The OODA-R reflect phase (``app.services.cognition.ooda_engine.OODAEngine``)
used to build an in-memory ``LearningService`` per call and discard it, so its
"learning" never survived the request -- placebo learning. PR-7 makes the loop
durable: ``OODAEngine._store_experience`` writes one ``experience_log`` row per
reflect (best-effort, decoupled from the memory toggle), and
``LearningService.with_experience_history`` rehydrates prior outcomes on the
next request so strategy selection is actually informed by history.

SQLite dev picks the table up automatically via ``Base.metadata.create_all``
in ``main.py.lifespan``. PostgreSQL production has no such fallback -- without
this migration every reflect would raise ``ProgrammingError: relation
"experience_log" does not exist`` (the exact failure mode migration 008 fixed
for notifications). This migration is the production counterpart.

Schema
------
Single table ``experience_log`` matching ``app.models.experience.ExperienceLog``:

* ``id`` GUID PK (uuid4 default)
* ``tenant_id`` GUID NOT NULL FK tenants.id ON DELETE CASCADE (TenantMixin)
* ``user_id`` GUID NOT NULL FK users.id ON DELETE CASCADE
* ``session_id`` GUID NULL FK chat_sessions.id ON DELETE SET NULL
  (a learned lesson outlives the chat session it was learned in)
* ``phase`` String(20) NOT NULL DEFAULT 'reflect'
* ``situation`` / ``decision`` / ``action_taken`` Text NULL (SAFE summaries)
* ``outcome`` String(20) NOT NULL -- 'success' | 'failure'
* ``reward`` Float NULL
* ``meta`` JSONBCompat NULL -- small dict (problem_type, frameworks, cycle, ...)
* ``created_at`` / ``updated_at`` from TimestampMixin

Indexes (4 total)
-----------------
``index=True`` on the model columns (tenant_id via TenantMixin, user_id,
session_id) yields three single-column indexes. A fourth composite index
``ix_experience_log_tenant_id_created_at`` (declared in ``__table_args__``)
serves the history hot query: "give me this tenant's recent experiences,
newest first" (LearningService.with_experience_history).

Idempotency
-----------
Mirrors migrations 003-016. Every CREATE TABLE / CREATE INDEX is guarded by
``_table_exists`` / ``_index_exists`` so re-running on a SQLite dev DB whose
``experience_log`` table was already produced by ``Base.metadata.create_all``
is a no-op.

Cross-dialect
-------------
Uses model-side decorator types ``GUID`` (UUID on Postgres, String(36) on
SQLite) and ``JSONBCompat`` (JSONB on Postgres, JSON on SQLite). Other column
types are stdlib SQLAlchemy and round-trip identically across dialects.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import GUID, JSONBCompat

# revision identifiers, used by Alembic.
revision: str = "017_add_experience_log"
down_revision: str | None = "016_add_run_trace_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Idempotency helpers -- mirror migrations 005-016.

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
    """Create experience_log table + 4 indexes."""

    if not _table_exists("experience_log"):
        op.create_table(
            "experience_log",
            sa.Column("id", GUID(), nullable=False),
            sa.Column("tenant_id", GUID(), nullable=False),
            sa.Column("user_id", GUID(), nullable=False),
            sa.Column("session_id", GUID(), nullable=True),
            sa.Column(
                "phase", sa.String(20),
                nullable=False, server_default="reflect",
            ),
            sa.Column("situation", sa.Text, nullable=True),
            sa.Column("decision", sa.Text, nullable=True),
            sa.Column("action_taken", sa.Text, nullable=True),
            sa.Column("outcome", sa.String(20), nullable=False),
            sa.Column("reward", sa.Float, nullable=True),
            sa.Column("meta", JSONBCompat(), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                nullable=True, onupdate=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id", name="pk_experience_log"),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["tenants.id"],
                name="fk_experience_log_tenant_id_tenants",
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["user_id"], ["users.id"],
                name="fk_experience_log_user_id_users",
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["session_id"], ["chat_sessions.id"],
                name="fk_experience_log_session_id_chat_sessions",
                ondelete="SET NULL",
            ),
        )

    # Single-column indexes from `index=True` on the model columns.
    if not _index_exists("experience_log", "ix_experience_log_tenant_id"):
        op.create_index(
            "ix_experience_log_tenant_id", "experience_log", ["tenant_id"],
        )
    if not _index_exists("experience_log", "ix_experience_log_user_id"):
        op.create_index(
            "ix_experience_log_user_id", "experience_log", ["user_id"],
        )
    if not _index_exists("experience_log", "ix_experience_log_session_id"):
        op.create_index(
            "ix_experience_log_session_id", "experience_log", ["session_id"],
        )

    # Composite index from the model's __table_args__ -- history hot query.
    if not _index_exists(
        "experience_log", "ix_experience_log_tenant_id_created_at",
    ):
        op.create_index(
            "ix_experience_log_tenant_id_created_at", "experience_log",
            ["tenant_id", "created_at"],
        )


def downgrade() -> None:
    """Drop indexes then table.

    Per CLAUDE.md hard law #2 (never delete, always archive), production
    downgrade should not run -- but provided for dev rollback. Indexes drop
    first so a partial state with table-but-no-indexes still tears down cleanly.
    """
    for index_name in (
        "ix_experience_log_tenant_id_created_at",
        "ix_experience_log_session_id",
        "ix_experience_log_user_id",
        "ix_experience_log_tenant_id",
    ):
        if _index_exists("experience_log", index_name):
            op.drop_index(index_name, table_name="experience_log")

    if _table_exists("experience_log"):
        op.drop_table("experience_log")
