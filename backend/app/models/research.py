"""ResearchDraft -- local-only artifact produced by Sprint-10 research flows.

PR-CAREEROPS-READONLY-RESEARCH-FLOW (Sprint-10 PR-3, 2026-05-05).
PR-CONTENTOPS-READONLY-RESEARCH-FLOW (Sprint-10 PR-4, 2026-05-05).

A ResearchDraft is the strict output shape of:

  source URL -> ScrapeGraphAI extraction -> LLM summary -> persist.

The brief explicitly forbids any external action on the back of a
research draft: NO submit, NO email, NO post, NO LinkedIn / Indeed
automation. The draft is always a local artifact -- the operator
reads + curates + decides what to do next.

Fields:

  * ``kind``   -- 'career' | 'content'. Future kinds (e.g. 'company')
    arrive in their own PRs; the column is a string to stay
    extensible without a schema change.
  * ``source_url`` -- the URL the operator scraped. Stored verbatim
    so the operator can re-open it. NEVER include credentials or
    bearer tokens in this value (validated at write).
  * ``source_host`` -- scheme://host[:port] precomputed for the
    audit + draft-list view. Avoids re-parsing the URL per render.
  * ``goal``   -- the operator's natural-language extraction prompt.
  * ``summary`` -- the LLM's compact summary (capped). What the
    operator reads in the draft list.
  * ``raw_extract`` -- the full ScrapeGraphAI output (also capped).
    Surfaced in the draft detail view for transparency.
  * ``status`` -- 'DRAFT' | 'ARCHIVED'. No SENT / SUBMITTED / POSTED
    states -- those would imply external action.
  * ``audit_event_id`` -- foreign reference to the
    plugin.skill_invocation row that produced this draft. Lets the
    audit viewer link from a row to the draft.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, GUID, TenantMixin, TimestampMixin


class ResearchDraft(Base, TenantMixin, TimestampMixin):
    """Local artifact produced by a Sprint-10 research flow.

    NEVER auto-published, NEVER submitted, NEVER emailed. The
    operator owns what happens next.
    """

    __tablename__ = "research_drafts"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    kind: Mapped[str] = mapped_column(
        String(32), nullable=False,
        comment="'career' | 'content' (extensible)",
    )
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    source_host: Mapped[str] = mapped_column(String(256), nullable=False)
    goal: Mapped[str] = mapped_column(String(2000), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    raw_extract: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="DRAFT",
    )
    audit_event_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
    )
