"""Connection models: Connector, ConnectorInstance, ConnectorPermission.

CMP (Connector Management Protocol) - Daena's equivalent of MCP for external integrations.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import GUID, Base, JSONBCompat, TenantMixin, TimestampMixin


class Connector(Base, TimestampMixin):
    """Connector definition (template). Tenant-independent catalog."""

    __tablename__ = "connectors"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,

    )
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    auth_type: Mapped[str] = mapped_column(String(20), nullable=False)
    config_schema: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, server_default="{}")
    tools: Mapped[list] = mapped_column(JSONBCompat, nullable=False, server_default="[]")
    icon_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)


class ConnectorInstance(Base, TenantMixin, TimestampMixin):
    """A user's connection to a specific connector.

    PR-CONN-GOOGLE-ACCOUNT-PROFILES (Sprint-4 PR-3, 2026-05-03):
    added ``owner_email`` so a single user can hold multiple
    ConnectorInstance rows for the same provider -- one per account
    profile (e.g. masoud.masoori@... personal Gmail vs daena@...
    company Gmail). The relaxed unique constraint
    ``(tenant_id, connector_id, user_id, owner_email)`` permits this
    without losing the intent of the original
    ``(tenant_id, connector_id, user_id)`` rule (which prevented
    duplicates accidentally; that intent is preserved per-profile).

    For non-Google providers (GitHub, Sentry, Slack, ...) ``owner_email``
    stays NULL; SQL NULL-equality semantics mean two NULLs do NOT
    violate the constraint, so application-level dedup in
    ``connection_service.connect_user_to_connector`` is what prevents
    duplicate non-Google instances per user. That dedup pre-dates this
    PR -- we do not regress it here.

    PRODUCTION MIGRATION NOTE: dev SQLite picks up the new column on
    a fresh ``create_all``. Existing dev DB rows survive because the
    column is nullable. Production deployment must add an Alembic
    migration before this lands; that is OUT OF SCOPE for the
    foundation PR.
    """

    __tablename__ = "connector_instances"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "connector_id", "user_id", "owner_email",
            name="uq_connector_instances_tenant_connector_user_email",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,

    )
    connector_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("connectors.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="DISCONNECTED")
    credentials: Mapped[dict | None] = mapped_column(JSONBCompat, nullable=True)
    last_used: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # PR-CONN-GOOGLE-ACCOUNT-PROFILES (Sprint-4 PR-3, 2026-05-03):
    # the account identifier this instance authenticates as. NULL for
    # non-Google providers (kept for back-compat). For Google
    # providers the OAuth callback should populate this from the
    # provider's userinfo endpoint -- a follow-up PR wires that
    # capture path. Until then the executor reads from
    # ``credentials._owner_email`` as a fallback for instances
    # created before the column existed.
    owner_email: Mapped[str | None] = mapped_column(
        String(254), nullable=True, index=True,
    )

    # Relationships
    connector: Mapped[Connector] = relationship()
    permissions: Mapped[list[ConnectorPermission]] = relationship(
        back_populates="instance", cascade="all, delete-orphan"
    )


class ConnectorPermission(Base, TenantMixin, TimestampMixin):
    """Per-tool permission within a connector instance."""

    __tablename__ = "connector_permissions"
    __table_args__ = (
        UniqueConstraint(
            "instance_id", "tool_name",
            name="uq_connector_permissions_instance_tool",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,

    )
    instance_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("connector_instances.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    tool_name: Mapped[str] = mapped_column(String(200), nullable=False)
    permission_level: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="ASK_EACH_TIME"
    )

    # Relationships
    instance: Mapped[ConnectorInstance] = relationship(back_populates="permissions")
