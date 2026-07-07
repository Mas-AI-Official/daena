"""Cognitive Knowledge Graph (CKG) -- tenant-scoped DB persistence.

Phase 3 item 8 (Doc/DAENA_VP_UPGRADE_PLAN_20260701.md, G3): the CKG's learned
insights and their cross-domain transfer edges used to live ONLY in a single
global ``graph.json`` file rewritten in full on every write (see
``app/services/cognition/knowledge_graph.py``). That path has two production
defects this table pair fixes:

  1. Multi-tenant leak (Daena Rule 9): a global JSON file has no tenant scope,
     so tenant A's chat turns would read tenant B's learned patterns. These
     rows carry a real ``tenant_id`` FK (CASCADE) so recall is isolated.
  2. Concurrency corruption: full-file JSON rewrites with no lock race under
     concurrent per-turn writes. A relational row with a per-tenant unique
     dedup key (``insight_hash``) upserts safely instead.

These are the same persisted fields as the ``Insight`` / ``TransferEdge``
dataclasses in ``knowledge_graph.py``, ported to the cross-dialect Base
(GUID + JSONBCompat) so connections survive restart in the real DB rather than
a side-car file. The legacy JSON class is retained UNTOUCHED for the security
scan engine (which is tenant-agnostic and cannot cheaply migrate); the governed
chat path reads/writes through ``CkgStore`` against these tables instead.

Domain enum values are stored as their ``.value`` strings (e.g. "security") for
dialect portability and human-readable audit; ``CkgStore`` maps them back to the
``Domain`` enum on read.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, JSONBCompat, TenantMixin, TimestampMixin


class CkgInsight(Base, TenantMixin, TimestampMixin):
    """One learned, domain-abstracted pattern -- the atom of Daena's cross-domain intelligence.

    Dedup identity within a tenant is ``insight_hash`` (sha256[:16] of the
    abstracted pattern), matching the legacy dataclass ``Insight.id``. Reinforce
    = bump ``evidence_count`` / ``confidence`` and expand ``applicable_domains``
    on the existing row; ``updated_at`` (TimestampMixin) doubles as the
    last-validated timestamp for recency scoring.
    """

    __tablename__ = "ckg_insight"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4,
    )
    # tenant_id comes from TenantMixin (FK tenants.id CASCADE, indexed).
    # Stable content identity == legacy Insight.id (sha256 of abstracted pattern).
    insight_hash: Mapped[str] = mapped_column(String(16), nullable=False, index=True)

    raw_observation: Mapped[str] = mapped_column(Text, nullable=False)
    abstracted_pattern: Mapped[str] = mapped_column(Text, nullable=False)
    origin_domain: Mapped[str] = mapped_column(String(32), nullable=False)
    # list[str] of Domain values this pattern transfers to.
    applicable_domains: Mapped[list] = mapped_column(
        JSONBCompat(), nullable=False, default=list,
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # list[str] of trace IDs that reinforced this insight.
    evidence_sources: Mapped[list] = mapped_column(
        JSONBCompat(), nullable=False, default=list,
    )
    nbmf_tier: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tags: Mapped[list] = mapped_column(JSONBCompat(), nullable=False, default=list)
    transfer_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    __table_args__ = (
        # Per-tenant dedup: reinforce collapses onto the same (tenant, hash) row.
        UniqueConstraint("tenant_id", "insight_hash", name="uq_ckg_insight_tenant_hash"),
        # Query hot path: WHERE tenant_id = ? AND origin_domain = ? (+ applicable).
        Index("ix_ckg_insight_tenant_domain", "tenant_id", "origin_domain"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"<CkgInsight hash={self.insight_hash} tenant={self.tenant_id} "
            f"domain={self.origin_domain!r} conf={self.confidence:.2f} "
            f"tier={self.nbmf_tier}>"
        )


class CkgTransferEdge(Base, TenantMixin, TimestampMixin):
    """A structural-similarity connection between two insights across domains.

    Edges reference insights by ``insight_hash`` (stable content identity),
    matching the legacy ``TransferEdge.source_id`` / ``target_id`` semantics.
    Scoped per tenant so transfer graphs never cross tenant boundaries.
    """

    __tablename__ = "ckg_transfer_edge"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4,
    )
    # tenant_id comes from TenantMixin (FK tenants.id CASCADE, indexed).
    source_hash: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    target_hash: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    source_domain: Mapped[str] = mapped_column(String(32), nullable=False)
    target_domain: Mapped[str] = mapped_column(String(32), nullable=False)
    similarity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    validated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "source_hash", "target_hash",
            name="uq_ckg_edge_tenant_src_tgt",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"<CkgTransferEdge {self.source_hash}->{self.target_hash} "
            f"tenant={self.tenant_id} sim={self.similarity:.2f}>"
        )
