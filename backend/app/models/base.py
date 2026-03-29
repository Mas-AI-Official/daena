"""Base model class, shared mixins, and cross-dialect column types.

All Daena ORM models inherit from Base. Mixins provide
timestamp tracking, tenant scoping, and soft-delete behavior.

The GUID and JSONBCompat types ensure models work on both
PostgreSQL (production) and SQLite (development).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON as SA_JSON
from sqlalchemy import DateTime, ForeignKey, MetaData, String, func
from sqlalchemy import types as sa_types
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# ---------------------------------------------------------------------------
# Cross-dialect column types  (Postgres ↔ SQLite)
# ---------------------------------------------------------------------------

class GUID(sa_types.TypeDecorator):
    """UUID type that works on both PostgreSQL and SQLite.

    On PostgreSQL: stores as native UUID.
    On SQLite: stores as CHAR(36) string.
    """

    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):  # noqa: ANN001, ANN201
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID as PG_UUID
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):  # noqa: ANN001, ANN201
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(value)
        return str(value)

    def process_result_value(self, value, dialect):  # noqa: ANN001, ANN201
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)


class JSONBCompat(sa_types.TypeDecorator):
    """JSONB type that falls back to JSON on SQLite.

    On PostgreSQL: native JSONB (indexable, binary storage).
    On SQLite: plain JSON (text storage, no indexing).
    """

    impl = SA_JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):  # noqa: ANN001, ANN201
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import JSONB
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(SA_JSON())


# Convenience alias matching old import name
PG_UUID = GUID

# Auto-naming convention for constraints (Alembic-friendly)
convention = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base for all Daena ORM models."""

    metadata = MetaData(naming_convention=convention)


class TimestampMixin:
    """Mixin that adds created_at and updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )


class TenantMixin:
    """Mixin that adds tenant_id FK for multi-tenant isolation."""

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


class SoftDeleteMixin:
    """Mixin for archive-based soft deletion (Hard Law #6)."""

    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
    archived_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
