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
    """A user's connection to a specific connector."""

    __tablename__ = "connector_instances"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "connector_id", "user_id",
            name="uq_connector_instances_tenant_connector_user",
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
