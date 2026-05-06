"""Business pipeline models -- Sprint-19 PR-1 (2026-05-06).

Two tables:

  * ``Opportunity`` -- a discovered business opportunity (lead,
    grant, hackathon, freelance gig, etc). Has a deterministic
    score, a structured type, an optional deadline, evidence URL.
  * ``OutreachDraft`` -- a local outreach draft generated from
    an opportunity. Carries payload_hash, recipient_email, body.
    Has FK to ``GoaRequest`` once approval is queued, and to
    Gmail draft_id once the controlled bridge runs.

Both are tenant-scoped. Both go through the existing approval
queue. Neither has a "send" or "submit" path of its own -- the
write path goes through the controlled execution dispatcher
(Sprint-14 spine) using only the already-allowlisted Gmail tools.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, JSONBCompat, TenantMixin, TimestampMixin


# ────────────────────────────────────────────────────────────────────
# Locked enum-ish strings (UI + tests match these verbatim)
# ────────────────────────────────────────────────────────────────────

OPPORTUNITY_TYPES: tuple[str, ...] = (
    "customer_lead",
    "grant",
    "accelerator",
    "hackathon",
    "freelance_project",
    "partnership",
    "bug_bounty_program",
    "content_opportunity",
)

OPPORTUNITY_STATUSES: tuple[str, ...] = (
    "discovered",
    "drafted",
    "queued",
    "approved",
    "sent",
    "rejected",
    "archived",
)

OUTREACH_DRAFT_KINDS: tuple[str, ...] = (
    "customer_cold_email",
    "grant_inquiry_email",
    "accelerator_intro_email",
    "hackathon_application_inquiry",
    "partnership_email",
    "security_program_inquiry",
)

OUTREACH_DRAFT_STATUSES: tuple[str, ...] = (
    "drafted",
    "queued_create_draft",
    "gmail_draft_created",
    "queued_send",
    "sent",
    "rejected",
    "rate_limited",
    "blocked_recipient",
)


class Opportunity(Base, TenantMixin, TimestampMixin):
    """A discovered business opportunity. Read-only research output."""

    __tablename__ = "opportunities"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4,
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deadline_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    estimated_value_usd: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    effort_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_label: Mapped[str | None] = mapped_column(String(20), nullable=True)
    next_action: Mapped[str | None] = mapped_column(String(500), nullable=True)
    assigned_department: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="discovered",
    )
    raw_metadata: Mapped[dict | None] = mapped_column(JSONBCompat, nullable=True)

    # Idempotency: dedupe key (e.g. source_url + title hash)
    dedupe_key: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True,
    )


class BizOutreachDraft(Base, TenantMixin, TimestampMixin):
    """A local outreach draft from an Opportunity. Carries
    payload_hash + recipient + body. Distinct from
    ``crm.OutreachDraft`` (which is contact-pipeline-scoped); this
    one is opportunity-scoped and integrates with the controlled
    execution dispatcher (Sprint-14 spine).

    Lifecycle:
      drafted          (factory created it)
      queued_create_draft  (operator approved -> Gmail bridge dispatching)
      gmail_draft_created  (gmail.create_draft handler done)
      queued_send      (second approval queued)
      sent             (gmail.send_existing_draft done)
      rejected         (operator rejected at any step)
      rate_limited     (send refused due to per-day cap)
      blocked_recipient (recipient safety failed)
    """

    __tablename__ = "biz_outreach_drafts"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("opportunities.id", ondelete="SET NULL"),
        nullable=True,
    )

    draft_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    payload_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True,
    )
    needs_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
    )
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="drafted", index=True,
    )

    # Linkage to controlled-execution artifacts
    create_draft_approval_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("goa_requests.id", ondelete="SET NULL"),
        nullable=True,
    )
    send_approval_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("goa_requests.id", ondelete="SET NULL"),
        nullable=True,
    )
    gmail_draft_id: Mapped[str | None] = mapped_column(
        String(120), nullable=True,
    )
    gmail_message_id: Mapped[str | None] = mapped_column(
        String(120), nullable=True,
    )

    blocked_reason: Mapped[str | None] = mapped_column(
        String(120), nullable=True,
    )
