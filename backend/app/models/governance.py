"""Governance models: GoaRequest, GoaPolicyState, GoaAuditEvent, PendingApproval, RoutingPolicy.

The governance subsystem: approval workflows, policy state,
tamper-evident audit trail (Hard Law #1, #9), and founder
routing policy overrides.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, JSONBCompat, TenantMixin, TimestampMixin


class GoaRequest(Base, TenantMixin, TimestampMixin):
    """Governance approval request. Created when action exceeds threshold."""

    __tablename__ = "goa_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,

    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    action_params: Mapped[dict | None] = mapped_column(JSONBCompat, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    governance_tier: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True
    )


class GoaPolicyState(Base, TenantMixin, TimestampMixin):
    """Governance policy state per action type per slider position."""

    __tablename__ = "goa_policy_states"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,

    )
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    slider_position: Mapped[str] = mapped_column(String(20), nullable=False)
    min_tier: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    config: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, server_default="{}")


class GoaAuditEvent(Base, TenantMixin):
    """Tamper-evident audit log entry (Hard Law #1, #9).

    Append-only. Each entry includes a hash chain linking to the previous.
    No updated_at — these are immutable once created.
    """

    __tablename__ = "goa_audit_events"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,

    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    action_params: Mapped[dict | None] = mapped_column(JSONBCompat, nullable=True)
    result: Mapped[str] = mapped_column(String(50), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    governance_tier: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PendingApproval(Base, TenantMixin, TimestampMixin):
    """Pending human approval for a governance request."""

    __tablename__ = "pending_approvals"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,

    )
    request_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("goa_requests.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    context: Mapped[dict | None] = mapped_column(JSONBCompat, nullable=True)


class RoutingPolicy(Base, TenantMixin, TimestampMixin):
    """Founder-defined routing policy overrides.

    One row per tenant.  Stores the full policy as JSONB so the
    founder can atomically read/update the entire config.

    Policy fields (all optional, absent = use system default):
        preferred_models  -- intent -> model_id map
        provider_priority -- ordered list of preferred providers
        cost_ceiling      -- max USD per single LLM request
        blocked_models    -- model_ids that must never be selected
        blocked_providers -- provider names that must never be selected
        default_model     -- override the global default fallback model
        enforce_local_only -- if true, only Ollama local models allowed
    """

    __tablename__ = "routing_policies"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_routing_policies_tenant"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    policy: Mapped[dict] = mapped_column(
        JSONBCompat, nullable=False, server_default="{}",
    )
