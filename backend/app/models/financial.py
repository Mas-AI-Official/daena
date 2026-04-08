"""Financial models: UsageLedger, VaultSecret, Subscription.

Cost tracking, encrypted secrets storage, and subscription management.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, JSONBCompat, TenantMixin, TimestampMixin


class UsageLedger(Base, TenantMixin):
    """Per-request cost tracking for LLM usage."""

    __tablename__ = "usage_ledger"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,

    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    tokens_input: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    tokens_output: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class VaultSecret(Base, TenantMixin, TimestampMixin):
    """Double-encrypted secrets storage (API keys, OAuth tokens)."""

    __tablename__ = "vault_secrets"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,

    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    secret_type: Mapped[str] = mapped_column(String(20), nullable=False)
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONBCompat, nullable=False, server_default="{}"
    )


class Subscription(Base, TenantMixin, TimestampMixin):
    """Tenant subscription for billing."""

    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,

    )
    plan: Mapped[str] = mapped_column(String(20), nullable=False, server_default="FREE")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="ACTIVE")
    stripe_customer_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    current_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    monthly_budget_usd: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    spend_this_month_usd: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, server_default="0"
    )


class UserQuota(Base, TenantMixin, TimestampMixin):
    """Per-user usage quota within a tenant's budget."""

    __tablename__ = "user_quotas"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    plan_tier: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="FREE"
    )
    monthly_credit_usd: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, server_default="0.50"
    )
    spend_this_month_usd: Mapped[float] = mapped_column(
        Numeric(10, 6), nullable=False, server_default="0"
    )
    daily_credit_usd: Mapped[float | None] = mapped_column(
        Numeric(10, 2), nullable=True, server_default="0.10"
    )
    spend_today_usd: Mapped[float] = mapped_column(
        Numeric(10, 6), nullable=False, server_default="0"
    )
    overage_action: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="fallback_free"
    )
    max_tenant_share_pct: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="50"
    )
    admin_override: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
