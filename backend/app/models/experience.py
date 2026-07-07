"""ExperienceLog -- durable record of every OODA-R reflect outcome.

The cognitive engine's reflect phase used to construct an in-memory
``LearningService`` per call and discard it, so nothing it "learned" survived
the request (placebo learning). This table is the durable substrate: one row
per reflect, written best-effort and decoupled from the memory toggle, so
``LearningService.with_experience_history()`` can rehydrate prior outcomes on
the next request and actually steer strategy selection.

SAFE-fields-only: ``situation`` / ``decision`` / ``action_taken`` are truncated
free-text summaries, never raw prompts or credentials. ``meta`` is a small JSON
dict (problem_type, frameworks, cycle, root_causes) -- NOT the full cognitive
state. ``tenant_id`` / ``user_id`` are real FKs so a deleted tenant/user
cascades; ``session_id`` is SET NULL because a learned lesson outlives the
chat session it was learned in.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, JSONBCompat, TenantMixin, TimestampMixin


class ExperienceLog(Base, TenantMixin, TimestampMixin):
    """One durable row per cognitive reflect outcome (success or failure)."""

    __tablename__ = "experience_log"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4,
    )
    # tenant_id comes from TenantMixin (FK tenants.id CASCADE, indexed).
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("chat_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    phase: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="reflect",
    )
    situation: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_taken: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    reward: Mapped[float | None] = mapped_column(Float, nullable=True)
    meta: Mapped[dict] = mapped_column(JSONBCompat(), nullable=True, default=dict)

    # History hot query: WHERE tenant_id = ? ORDER BY created_at DESC LIMIT n.
    __table_args__ = (
        Index("ix_experience_log_tenant_id_created_at", "tenant_id", "created_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"<ExperienceLog id={self.id} tenant={self.tenant_id} "
            f"outcome={self.outcome!r} phase={self.phase!r}>"
        )
