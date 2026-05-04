"""PluginPolicyOverride: per-tenant overrides over the static
governance preset table.

PR-CONN-PER-TENANT-POLICY-OVERRIDES (Sprint-6 PR-6, 2026-05-04).

The static preset table at
``app.services.connection_v2.plugin_governance_presets`` ships
vendor-recommended ALLOW / ASK / DENY tiers per (plugin, skill_class).
Operators can now override a single (plugin, skill_class) tier with
their own choice; the override wins on read. The base preset table
remains the source of truth for "what does the vendor recommend?".

Schema is intentionally minimal:

  * id (PK)
  * tenant_id (TenantMixin -- enforces isolation)
  * plugin_id (str)
  * skill_class (str -- raw enum value)
  * tier (str -- raw enum value)
  * rationale (str -- operator-supplied notes)
  * updated_by (FK to users.id, nullable for system-set rows)
  * created_at / updated_at (TimestampMixin)

A unique constraint on (tenant_id, plugin_id, skill_class) enforces
"one override per cell" -- a PUT for an existing cell updates the
existing row instead of creating a duplicate.

NEVER stores: token values, secrets, operator inputs, or any
execution payload. The override is metadata only.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TenantMixin, TimestampMixin


class PluginPolicyOverride(Base, TenantMixin, TimestampMixin):
    """One row per (tenant, plugin, skill_class) cell that the
    operator has overridden. Cells without a row fall back to the
    static preset table at read time."""

    __tablename__ = "plugin_policy_overrides"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "plugin_id", "skill_class",
            name="uq_plugin_policy_overrides_tenant_plugin_class",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    plugin_id: Mapped[str] = mapped_column(String(120), nullable=False)
    skill_class: Mapped[str] = mapped_column(String(50), nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    rationale: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
