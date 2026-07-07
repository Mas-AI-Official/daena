"""Memory (NBMF) models: MemoryEntry, LearningLog.

Implements the Neural-Backed Memory Fabric (patent-pending).
Tiers: WORKING(0) -> SHORT_TERM(1) -> LONG_TERM(2) -> CORE(3) -> IMMUTABLE(4).

Agent experience types (stored in content_type):
    FACT / PREFERENCE / LEARNING / POLICY / DIRECTIVE  -- user-facing
    INTERACTION  -- raw Q&A pairs from chat pipeline
    AGENT_DECISION  -- what an agent decided and why
    SKILL_OUTCOME   -- result of a skill execution
    PATTERN_LEARNED -- recurring successful reasoning chain
    APPROACH_FAILED -- failed approach with reason (anti-pattern)

Quarantine: is_quarantined=True means the entry is in L2Q (not yet trusted).
Trust score: 0.0 (untrusted) to 1.0 (fully validated).
Content hash: SHA-256 for CAS deduplication.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, JSONBCompat, TenantMixin, TimestampMixin

# Semantic recall is delegated to the external ragx service (embeddings +
# CRAG + NLI live there, per-tenant collections), NOT to this DB tier. The
# NBMF T0-T4 store below is deliberately keyword-token retrieval: fast,
# local, no embedding column to keep in sync. This probe stays only as a
# forward-compat capability flag -- if a future phase adds an on-DB embedding
# column it can gate on HAS_PGVECTOR -- but nothing reads it today, so do not
# assume the DB does vector search. It does not.
try:
    from pgvector.sqlalchemy import Vector  # noqa: F401  (probe only; unused today)
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False


class MemoryEntry(Base, TenantMixin, TimestampMixin):
    """A single memory entry in the NBMF system.

    Memories have a tier (0-4), TTL-based expiration for lower tiers,
    quarantine gating, trust scoring, and content-hash deduplication.
    Retrieval here is keyword-token over content/summary/tags; semantic
    (vector) recall is served by the external ragx service, not this table.
    """

    __tablename__ = "memory_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), nullable=True, index=True,
    )
    tier: Mapped[int] = mapped_column(SmallInteger, nullable=False, index=True)
    content_type: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tags: Mapped[list] = mapped_column(JSONBCompat, nullable=False, server_default="[]")
    source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.5")
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_accessed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── NBMF extensions: quarantine + trust + dedup ──
    is_quarantined: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="0",
    )
    trust_score: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="0.0",
    )
    content_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True,
    )
    skill_id: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
    )
    success_flag: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True,
    )

    # ── Dream Engine extensions ──
    is_sensitive: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="0",
    )
    encoding_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="semantic",
    )
    contradiction: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="0",
    )

    verification_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="UNVERIFIED"
    )
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONBCompat, nullable=False, server_default="{}"
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LearningLog(Base, TenantMixin):
    """Audit log for memory tier changes (promotions, demotions, verifications)."""

    __tablename__ = "learning_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,

    )
    memory_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("memory_entries.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    from_tier: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    to_tier: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
