"""FormDraft + FormDraftField -- Sprint-11 PR-3.

Local-only artifact representing a form Daena prepared answers for.
The operator reviews + edits + submits manually (or pastes back into
the original form). Daena NEVER submits.

Hard rules baked into the data model:

    * No ``submitted`` / ``sent`` / ``applied`` status. Only DRAFT,
      ARCHIVED. Status transitions never trigger external dispatch.
    * Field types include explicit ``blocked_payment`` and
      ``blocked_sensitive`` categories. The service classifier maps
      payment / SSN / SIN / immigration / passport labels into those
      types so the UI can grey them out and ensure no LLM-suggested
      value is auto-populated for them.
    * No foreign key into the integrations / connector tables --
      FormDraft cannot be linked to a "submit through this Gmail"
      action. There is no submit path.

Per CLAUDE.md Rule 2, this is a separate model because the audit
identified no existing FormDraft surface. It is *not* a duplicate of
ResearchDraft -- ResearchDraft holds research extracts; FormDraft
holds the operator's prepared form responses.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime, Float, ForeignKey, Integer, String, Text, Boolean,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, JSONBCompat, TenantMixin, TimestampMixin


class FormDraft(Base, TenantMixin, TimestampMixin):
    """A locally-prepared set of form answers awaiting operator review.

    NEVER submitted by Daena -- the operator clicks the original form's
    submit button after copy-pasting the approved answers (or after a
    future PR adds an explicit Approval Queue + manual-only submit
    helper).
    """

    __tablename__ = "form_drafts"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    # 'questions' (operator pasted Q list) | 'html' (operator pasted
    # form HTML) | 'url' (Daena scraped a URL and extracted questions)
    source_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    source_url: Mapped[str | None] = mapped_column(
        String(2048), nullable=True,
    )
    source_host: Mapped[str | None] = mapped_column(
        String(256), nullable=True,
    )
    # The operator-supplied free-text goal (e.g. "fill this AI-engineer
    # application using my CV and the company brief from research draft
    # X"). Stored verbatim; never logged with PII redaction beyond the
    # standard log allowlist.
    goal: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="DRAFT",
    )
    audit_event_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
    )
    # Optional: the ResearchDraft that informed this form draft (e.g.
    # the OpportunityDraft we extracted from a job posting). Stored as
    # a string id rather than a FK so a deleted research draft does
    # not cascade-delete the form draft the operator might still be
    # working on.
    research_draft_ref: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
    )

    fields: Mapped[list["FormDraftField"]] = relationship(
        back_populates="draft",
        cascade="all, delete-orphan",
        order_by="FormDraftField.order",
    )


class FormDraftField(Base, TenantMixin, TimestampMixin):
    """One question / answer pair inside a FormDraft.

    ``field_type`` constrains how the UI renders + whether the LLM is
    allowed to suggest a value. ``blocked_payment`` and
    ``blocked_sensitive`` types are operator-fill-only -- Daena never
    populates ``suggested_value`` for them.
    """

    __tablename__ = "form_draft_fields"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4,
    )
    draft_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("form_drafts.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    # Free-form, never used to drive auto-submit. The frontend treats
    # this as the editable answer cell.
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_type: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="text",
    )
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
    )
    needs_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
    )
    # Optional list[str] for selects, JSONB-compat. NULL for
    # text/textarea fields.
    options: Mapped[list | None] = mapped_column(JSONBCompat, nullable=True)
    # Operator-facing rationale or missing-info hint. Surfaced as a
    # tooltip / inline note in the UI.
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    draft: Mapped[FormDraft] = relationship(back_populates="fields")
