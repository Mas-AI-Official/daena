"""CRM models: Account, Contact, Deal.

Phase H of Roadmap V2. Minimal schema so SalesAgent and MarketingAgent
can persist the prospects they discover and the drafts they author.
All rows are tenant-scoped; no cross-tenant leakage is possible.

Why a dedicated module instead of piggy-backing on identity.py
--------------------------------------------------------------
Contacts and Accounts are business-layer concepts, not tenancy
primitives. They evolve at a different cadence (deal stages, enrichment
providers, activity log) so isolating them keeps migrations focused
and lets the Sales department iterate without touching auth tables.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, JSONBCompat, TenantMixin, TimestampMixin


class Account(Base, TenantMixin, TimestampMixin):
    """A company being sold into. Accounts hold Contacts."""

    __tablename__ = "crm_accounts"
    __table_args__ = (
        Index("ix_crm_accounts_tenant_domain", "tenant_id", "domain"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    employee_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # ICP match score 0.0-1.0. Set by SalesAgent.qualify().
    icp_score: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    # Freeform enrichment payload from OSINT layer (breach exposure,
    # tech stack, hiring signals, etc.). Avoids schema churn while
    # Layer-3 enrichment providers evolve.
    enrichment: Mapped[dict | None] = mapped_column(JSONBCompat, nullable=True)
    # ICP source description (e.g., "mid-market fintech with SOC 2 gap")
    source_icp: Mapped[str | None] = mapped_column(String(500), nullable=True)


class Contact(Base, TenantMixin, TimestampMixin):
    """A person inside an Account."""

    __tablename__ = "crm_contacts"
    __table_args__ = (
        Index("ix_crm_contacts_tenant_account", "tenant_id", "account_id"),
        Index("ix_crm_contacts_tenant_email", "tenant_id", "email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4,
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("crm_accounts.id", ondelete="SET NULL"), nullable=True,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Lifecycle: NEW -> QUALIFIED -> CONTACTED -> MEETING -> CUSTOMER -> LOST
    stage: Mapped[str] = mapped_column(String(32), nullable=False, server_default="NEW")
    # Who sourced this contact (OSINT provider or channel).
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    enrichment: Mapped[dict | None] = mapped_column(JSONBCompat, nullable=True)
    last_touched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )


class Deal(Base, TenantMixin, TimestampMixin):
    """A sales opportunity."""

    __tablename__ = "crm_deals"
    __table_args__ = (
        Index("ix_crm_deals_tenant_stage", "tenant_id", "stage"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("crm_accounts.id", ondelete="CASCADE"), nullable=False,
    )
    primary_contact_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("crm_contacts.id", ondelete="SET NULL"), nullable=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Lifecycle: PROSPECT -> QUALIFIED -> PROPOSAL -> NEGOTIATION -> CLOSED_WON -> CLOSED_LOST
    stage: Mapped[str] = mapped_column(String(32), nullable=False, server_default="PROSPECT")
    amount_usd: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    close_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class OutreachDraft(Base, TenantMixin, TimestampMixin):
    """A Marketing-authored outreach draft awaiting Sales approval + send.

    Keeps drafts out of the Deal table until they are dispatched so the
    pipeline view stays clean.
    """

    __tablename__ = "crm_outreach_drafts"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4,
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("crm_contacts.id", ondelete="CASCADE"), nullable=False,
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)  # email | linkedin | voice
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # DRAFT -> APPROVED -> SENT -> REPLIED -> BOUNCED
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="DRAFT")
    # Optional template id for variant telemetry
    template_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
