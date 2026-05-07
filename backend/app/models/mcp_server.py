"""MCP Server model: tenant-scoped persistence for MCP server registrations.

Backs the in-process :class:`app.services.mcp_registry.MCPRegistry` so
that MCP servers added through the UI (or auto-discovered on startup)
survive a process restart. Without this, every restart wipes everything
the user added since the last reboot, which surfaced as the bug
"installed MCPs disappear on restart".

Multi-tenancy
-------------
Every row is scoped by ``tenant_id`` (TenantMixin). The bootstrap path
(``mcp_bootstrap.bootstrap_installed_mcps``) reads the operator's
``claude_desktop_config.json`` and assigns those entries to the
synthetic ``"system"`` tenant so they stay visible on a fresh install
without manual seeding.

Soft-delete
-----------
Status is a string, not an Enum, to keep the column re-shapeable
without a migration when new lifecycle states are added (e.g. a
``QUARANTINED`` tier from the install scanner). Removing an MCP from
the UI sets ``status="DISABLED"`` rather than deleting the row, so
audit trails stay intact (Hard Law 6).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, JSONBCompat, TenantMixin, TimestampMixin


# Status values stored as plain strings (not Enum) so we can extend
# without a schema migration. Treat as a closed set in app code:
STATUS_DISCOVERED = "DISCOVERED"
STATUS_ACTIVE = "ACTIVE"
STATUS_FAILED = "FAILED"
STATUS_DISABLED = "DISABLED"


class McpServer(Base, TenantMixin, TimestampMixin):
    """A persisted MCP server registration owned by one tenant.

    Identified by ``(tenant_id, server_key)``. The runtime cache in
    :class:`MCPRegistry` mirrors these rows after ``hydrate_from_db``
    runs at app startup. Adding a new server through the UI calls
    ``persist_addition`` which upserts a row and updates the cache so
    the next chat turn sees it without a restart.
    """

    __tablename__ = "mcp_servers"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "server_key",
            name="uq_mcp_servers_tenant_server_key",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Identity within a tenant. ``server_key`` matches the key used in
    # ``claude_desktop_config.json`` (e.g. "filesystem", "github") so a
    # bootstrapped row maps 1:1 to the desktop config entry.
    server_key: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True,
    )
    display_name: Mapped[str] = mapped_column(
        String(200), nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
    )

    # Subprocess command for stdio MCPs (e.g. "npx", "uvx", "node").
    command: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
    )
    args: Mapped[list] = mapped_column(
        JSONBCompat, nullable=False, server_default="[]", default=list,
    )
    package: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
    )
    # HTTP MCPs use ``server_url`` instead of ``command``+``args``.
    server_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
    )

    # Lifecycle. Default ``DISCOVERED`` so a freshly-imported entry is
    # visible in the UI before its first health check completes.
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=STATUS_DISCOVERED,
        default=STATUS_DISCOVERED,
    )
    last_health_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    last_health_ok: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False,
    )

    # Provenance. ``created_by_user_id`` is nullable so bootstrapped
    # entries (no human author) round-trip cleanly. Cascading on user
    # delete is intentionally SET NULL: a tenant's MCPs outlive the
    # specific user who added them.
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    auto_loaded: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False,
    )

    # Free-form extension point. Used today for governance overrides
    # (e.g. ``{"min_governance_tier": 3}``) and tomorrow for transport
    # hints (sse vs stdio vs websocket). Named ``extra_metadata`` to
    # avoid clashing with SQLAlchemy's reserved ``metadata`` attribute.
    extra_metadata: Mapped[dict] = mapped_column(
        JSONBCompat, nullable=False, server_default="{}", default=dict,
    )
