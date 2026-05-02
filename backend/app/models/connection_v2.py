"""ConnectionV2 + Capability + OpLock models (Phase 4b PR 1).

Per ADR-002 D-001 + V2 spec §4. One table covers all 6 connection
kinds (CLI runtime, MCP server, provider, plugin, OAuth app, local
model). 6 truth dimensions are explicit boolean columns. Per-dim
failure storage (D-001): each dim has its own _at + _failure_at +
_failure_reason fields. In-progress state lives in the side table
``connection_v2_op_lock`` (D-002), NOT in booleans on the main row.

Behavior gates per founder rule:
- Live consumers ONLY query/write these tables when
  settings.use_connection_registry_v2 is True (default False).
- Until then, the legacy ConnectorInstance + RuntimeRegistry +
  MCPRegistry remain authoritative.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, JSONBCompat, TenantMixin, TimestampMixin


# ──────────────────────────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────────────────────────


class ConnectionKind(str, enum.Enum):
    """One row per kind. Discriminator for per-kind config validation.

    PR-CONN-V2-SEED-IMPORT (2026-05-02): added SKILL_PACK for
    capability/instruction bundles that are NOT callable by themselves.
    Probes for SKILL_PACK rows return a structured "not a callable
    surface" failure rather than ever flipping callable=true. Frontend
    renders these with a distinct "Skill pack only" badge so the
    operator never confuses a packaged-doc row with a real connector.
    """

    CLI_RUNTIME = "cli_runtime"
    MCP_SERVER = "mcp_server"
    PROVIDER = "provider"
    PLUGIN = "plugin"
    OAUTH_APP = "oauth_app"
    LOCAL_MODEL = "local_model"
    SKILL_PACK = "skill_pack"


class AuthMethod(str, enum.Enum):
    """Authentication method. NONE = skill-pack-only, no install."""

    NONE = "none"
    API_TOKEN = "api_token"
    OAUTH_MANAGED = "oauth_managed"
    MCP_REMOTE_OAUTH = "mcp_remote_oauth"
    SUBSCRIPTION = "subscription"


class TrustTier(str, enum.Enum):
    """Plugin trust tier. UNVERIFIED requires founder gate in ALL modes."""

    OFFICIAL = "official"
    COMMUNITY = "community"
    UNVERIFIED = "unverified"


class OpKind(str, enum.Enum):
    """Operation kinds tracked in connection_v2_op_lock."""

    AUTHENTICATE = "authenticate"
    PROBE = "probe"
    INSTALL = "install"
    OAUTH_CALLBACK = "oauth_callback"


# ──────────────────────────────────────────────────────────────────
# Main row
# ──────────────────────────────────────────────────────────────────


class ConnectionV2(Base, TenantMixin, TimestampMixin):
    """Canonical connection row for all 6 kinds.

    Per ADR-002 D-001: 6 truth dims are explicit booleans; per-dim
    failure storage. Per ADR-002 D-007: imported=True only when row
    is durably persisted (NOT for in-memory hydration).
    """

    __tablename__ = "connection_v2"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)

    # Identity (slug is canonical; display_name is human-friendly).
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    canonical_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Auth + trust + per-kind config.
    auth_method: Mapped[str] = mapped_column(String(32), nullable=False)
    trust_tier: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=TrustTier.OFFICIAL.value,
    )
    config: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, server_default="{}")
    vault_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # 6 truth dimensions (ADR-002 D-001).
    detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    configured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    imported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    reachable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    authenticated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    callable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    # Per-dim "set true at" timestamps.
    detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    configured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reachable_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    authenticated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    callable_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Per-dim failure metadata. Failure on one dim NEVER overwrites another's
    # reason (per ADR-002 D-001).
    detected_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    detected_failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    configured_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    configured_failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    imported_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    imported_failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reachable_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reachable_failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    authenticated_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    authenticated_failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    callable_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    callable_failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Healthy-call ratio for derive_label (degraded vs healthy split).
    # Rolling window updated by probe service. Defaults to 1.0 = healthy.
    healthy_call_ratio: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0, server_default="1.0",
    )

    # Soft-delete + governance.
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    governance_tier: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="2")

    __table_args__ = (
        UniqueConstraint("tenant_id", "kind", "slug", name="uq_connection_v2_tenant_kind_slug"),
        Index("ix_connection_v2_tenant_callable", "tenant_id", "callable"),
        Index("ix_connection_v2_tenant_kind", "tenant_id", "kind"),
    )

    def __repr__(self) -> str:  # pragma: no cover -- debug only
        return (
            f"<ConnectionV2 tenant={self.tenant_id} kind={self.kind} "
            f"slug={self.slug} callable={self.callable}>"
        )


# ──────────────────────────────────────────────────────────────────
# Capability side table (mcp_tool / provider_model / cli_command)
# ──────────────────────────────────────────────────────────────────


class ConnectionV2Capability(Base):
    """One row per capability discovered on a connection.

    Per V2 §5: kept in a side table so capability churn doesn't
    rewrite the parent row, and so cross-connection capability lookup
    by name is a simple indexed query.
    """

    __tablename__ = "connection_v2_capability"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("connection_v2.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # mcp_tool|provider_model|cli_command
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    spec: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, server_default="{}")
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("connection_id", "kind", "name", name="uq_conn_v2_cap_conn_kind_name"),
        Index("ix_conn_v2_cap_kind_name", "kind", "name"),
    )


# ──────────────────────────────────────────────────────────────────
# Op-lock table (in-progress state)
# ──────────────────────────────────────────────────────────────────


class ConnectionV2OpLock(Base):
    """TTL'd lock per (connection_id, op).

    Per ADR-002 D-002: derive_label() reads this table to know whether
    a probe / authenticate / install / oauth_callback is in progress.
    No booleans on the main row; that prevents stale state when a
    worker crashes mid-operation.
    """

    __tablename__ = "connection_v2_op_lock"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("connection_v2.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    op: Mapped[str] = mapped_column(String(32), nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    owner_token: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint("connection_id", "op", name="uq_conn_v2_op_lock_conn_op"),
        Index("ix_conn_v2_op_lock_expires", "expires_at"),
    )
