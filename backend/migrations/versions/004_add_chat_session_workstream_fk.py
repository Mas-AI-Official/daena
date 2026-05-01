"""Add ``chat_sessions.workstream_id`` FK column.

Revision ID: 004_add_chat_session_workstream_fk
Revises: 003_add_workstreams
Create Date: 2026-04-25

Context
-------
Per the Council R4 Phase 2 hybrid recommendation (Option D gate + reuse
existing session workstream + ``/spawn`` for explicit founder control),
the orchestrator's Stage 7.6 needs to:

1. Look up ``chat_session.workstream_id``;
2. If alive (status NOT IN {COMPLETE, FAILED}), REUSE;
3. Otherwise, create a new ``Workstream`` and store its id on the
   chat session for future turns to find.

This migration adds the nullable FK column + index. Per Daena's
idempotent guard pattern, the column add is wrapped in
``_column_exists`` so re-running is safe. ondelete=SET NULL preserves
both sides' lifecycle (Hard Law #2: never delete, always archive).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004_add_chat_session_workstream_fk"
down_revision: str | None = "003_add_workstreams"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column in [c["name"] for c in inspector.get_columns(table)]


def _index_exists(table: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(ix["name"] == index_name for ix in inspector.get_indexes(table))


def _fk_exists(table: str, name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(fk.get("name") == name for fk in inspector.get_foreign_keys(table))


def upgrade() -> None:
    if not _column_exists("chat_sessions", "workstream_id"):
        # SQLite cannot ADD a column with an FK constraint inline; we
        # rely on Daena's GUID String(36) representation and a separate
        # CREATE INDEX. The Postgres branch could use a true FK; we use
        # a batch op for cross-dialect safety.
        with op.batch_alter_table("chat_sessions") as batch_op:
            batch_op.add_column(
                sa.Column("workstream_id", sa.String(36), nullable=True),
            )

    if not _index_exists("chat_sessions", "ix_chat_sessions_workstream_id"):
        op.create_index(
            "ix_chat_sessions_workstream_id",
            "chat_sessions",
            ["workstream_id"],
        )

    # Add the actual FK constraint on Postgres (skipped on SQLite, which
    # does not support adding FKs to existing tables without a full
    # rebuild). The ORM still works because GUID() is just String(36)
    # underneath; the FK is for prod-side referential integrity.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        if not _fk_exists("chat_sessions", "fk_chat_sessions_workstream_id_workstreams"):
            op.create_foreign_key(
                "fk_chat_sessions_workstream_id_workstreams",
                "chat_sessions",
                "workstreams",
                ["workstream_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        if _fk_exists("chat_sessions", "fk_chat_sessions_workstream_id_workstreams"):
            op.drop_constraint(
                "fk_chat_sessions_workstream_id_workstreams",
                "chat_sessions",
                type_="foreignkey",
            )
    if _index_exists("chat_sessions", "ix_chat_sessions_workstream_id"):
        op.drop_index("ix_chat_sessions_workstream_id", table_name="chat_sessions")
    if _column_exists("chat_sessions", "workstream_id"):
        with op.batch_alter_table("chat_sessions") as batch_op:
            batch_op.drop_column("workstream_id")
