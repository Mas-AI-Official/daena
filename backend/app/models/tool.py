"""ToolRecord -- durable, tenant-scoped catalog of tools Daena can use.

This is plan 13.2's ``ToolDefinition`` model. It is named ``ToolRecord`` here
(table ``tool_records``) to avoid colliding with the in-memory
``app.services.tool_lifecycle.tool_registry.ToolDefinition`` dataclass, which is
a SEPARATE LLM-context construct. Per Daena Rule 17 (ADR-001) that in-memory
registry hydrates FROM these rows on startup; two identically named classes in a
projection relationship with different shapes would be a footgun, so the DB model
takes the distinct ``ToolRecord`` name.

One row per (tenant, tool). Seeded from ``TOOL_CATALOG`` on first use so behavior
is identical on day one, then kept live as MCP servers and skills register or
refresh their rows. ``ToolDiscovery.from_db`` reads the enabled rows for the
tenant and falls back to ``TOOL_CATALOG`` only when the tenant has never been
seeded or a read fails (fail-open), so the live cognition path never hard-breaks
on a DB hiccup -- and a tool an operator disables stays disabled (no silent
demo-data fallback).

Column map (plan 13.2):
    name        stable slug (== ToolCandidate.id), unique per tenant
    kind        builtin | mcp | skill
    description human-readable summary
    enabled     operator kill switch (survives re-seed; never overwritten)
    source_ref  origin pointer (mcp registry id / skill id / catalog source)
    schema      tool input JSON schema (empty until a real registrant fills it)
    meta        free-form JSON; holds the full ToolCandidate for lossless round-trip
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, JSONBCompat, TenantMixin, TimestampMixin


class ToolRecord(Base, TenantMixin, TimestampMixin):
    """One durable row per tool available to a tenant (plan 13.2 ToolDefinition)."""

    __tablename__ = "tool_records"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4,
    )
    # tenant_id comes from TenantMixin (FK tenants.id CASCADE, indexed).
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="builtin",
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true",
    )
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    schema: Mapped[dict] = mapped_column(
        JSONBCompat(), nullable=False, default=dict, server_default="{}",
    )
    meta: Mapped[dict] = mapped_column(
        JSONBCompat(), nullable=False, default=dict, server_default="{}",
    )

    # One row per tool name per tenant; discovery filters by tenant + enabled.
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_tool_records_tenant_id_name"),
        Index("ix_tool_records_tenant_id_enabled", "tenant_id", "enabled"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"<ToolRecord id={self.id} tenant={self.tenant_id} "
            f"name={self.name!r} kind={self.kind!r} enabled={self.enabled}>"
        )
