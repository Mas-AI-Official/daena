"""Tenant-scoped, DB-backed Cognitive Knowledge Graph store (Phase 3 item 8, G3).

This is the production write/read path for the CKG. It replaces the global
``graph.json`` side-car used by :class:`CognitiveKnowledgeGraph` for the governed
chat flow, fixing two defects (see ``app/models/cognition.py``):

  1. Multi-tenant leak (Daena Rule 9): rows carry a real ``tenant_id`` so one
     tenant never reads another's learned patterns.
  2. Concurrency corruption: relational upsert on ``(tenant_id, insight_hash)``
     replaces racy full-file JSON rewrites.

Design contract
---------------
* The *taxonomy* is imported, never duplicated: ``Domain`` and
  ``STRUCTURAL_CATEGORIES`` come straight from ``knowledge_graph.py`` (single
  source of truth). Only the pure, side-effect-free logic (keyword abstraction,
  domain inference, hashing, similarity, NBMF promotion, relevance scoring) is
  reimplemented here to operate on DB rows instead of in-memory dataclasses.
* The legacy :class:`CognitiveKnowledgeGraph` and its JSON persistence are left
  UNTOUCHED for the tenant-agnostic security scan engine.
* Anti-noise gate: unlike the legacy ``learn`` (which persists even
  un-abstractable fallbacks), :meth:`learn` skips observations that match no
  structural category. A per-turn chat write path must not flood a tenant's
  graph with near-duplicate echoes of raw prompt text; only genuinely abstracted
  cross-domain patterns are persisted so Stage 6.2 injection stays meaningful.
* Async only; safe to call from the post-turn background writeback (never the
  hot path -- Daena Rule 4).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cognition import CkgInsight, CkgTransferEdge
from app.services.cognition.knowledge_graph import (
    STRUCTURAL_CATEGORIES,
    Domain,
)

logger = structlog.get_logger(__name__)

# Number of domains -- used to normalise transfer_score, matching the legacy
# ``len(Domain)`` denominator so scores stay comparable across both paths.
_DOMAIN_COUNT = len(Domain)

# Department display-name -> CKG Domain. Single source for both the post-turn
# write path and the orchestrator's Stage 6.2 read, so the two never drift.
_DEPT_TO_DOMAIN: dict[str, Domain] = {
    "engineering": Domain.ENGINEERING,
    "product": Domain.PRODUCT,
    "marketing": Domain.MARKETING,
    "sales": Domain.SALES,
    "finance": Domain.FINANCE,
    "operations": Domain.OPERATIONS,
    "research": Domain.RESEARCH,
    "legal": Domain.LEGAL,
    "skill governance": Domain.SKILL_GOVERNANCE,
    "security": Domain.SECURITY,
    "security operations": Domain.SECURITY,
}


def domain_for_department(dept_name: str | None) -> Domain:
    """Map a department display name to its CKG domain (default REASONING)."""
    return _DEPT_TO_DOMAIN.get((dept_name or "").lower(), Domain.REASONING)


class CkgStore:
    """Async, tenant-scoped accessor for CKG insights + transfer edges."""

    def __init__(self, db: AsyncSession, tenant_id: UUID) -> None:
        self._db = db
        self._tenant_id = tenant_id

    # ── Pure helpers (ported from knowledge_graph.py, DB-agnostic) ──

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    @staticmethod
    def _abstract(raw: str, domain: Domain) -> tuple[str, str]:
        """Keyword-tier abstraction -- deterministic, zero-cost, no LLM.

        Returns ``(category_name, abstracted_description)``. Category is empty
        when no structural pattern matches (the caller treats that as a skip).
        The LLM tier of the legacy engine is intentionally omitted here: the
        write path runs per turn and must stay token-free (Rule 4 / token
        discipline); LLM abstraction remains a background concern of the scan
        engine's own path.
        """
        raw_lower = raw.lower()
        for cat_name, cat_info in STRUCTURAL_CATEGORIES.items():
            keywords = cat_name.replace("_", " ").split()
            matches = sum(1 for kw in keywords if kw in raw_lower)
            if matches >= 2 or (matches >= 1 and domain in cat_info["domains"]):
                return cat_name, f"{cat_info['description']} (from {domain.value}: {raw[:100]})"
        return "", f"[{domain.value}] {raw[:200]}"

    @staticmethod
    def _infer_domains(category: str, origin: Domain) -> list[Domain]:
        """Which domains a pattern transfers to, from its structural category."""
        if category in STRUCTURAL_CATEGORIES:
            domains = list(STRUCTURAL_CATEGORIES[category]["domains"])
            if origin not in domains:
                domains.append(origin)
            return domains
        return [origin]

    @staticmethod
    def _maybe_promote(row: CkgInsight) -> None:
        """Bump NBMF tier by evidence/confidence/breadth (legacy thresholds)."""
        n_domains = len(row.applicable_domains or [])
        if row.evidence_count >= 25 and row.confidence >= 0.85 and n_domains >= 3:
            if row.nbmf_tier < 3:
                row.nbmf_tier = 3
                logger.info("ckg.promoted", insight_hash=row.insight_hash, tier=3)
        elif row.evidence_count >= 10 and row.confidence >= 0.7 and n_domains >= 2:
            if row.nbmf_tier < 2:
                row.nbmf_tier = 2
                logger.info("ckg.promoted", insight_hash=row.insight_hash, tier=2)
        elif row.evidence_count >= 3 and row.confidence >= 0.5:
            if row.nbmf_tier < 1:
                row.nbmf_tier = 1

    @staticmethod
    def _recency(updated_at: datetime | None) -> float:
        """Legacy recency factor: 1 / (1 + age_in_days). Robust to naive TZ."""
        if updated_at is None:
            return 1.0
        ref = updated_at
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - ref).total_seconds() / 86400.0
        if age_days < 0:
            age_days = 0.0
        return 1.0 / (1.0 + age_days)

    # ── Write path ──────────────────────────────────────────────

    async def learn(
        self,
        raw_observation: str,
        origin_domain: Domain,
        evidence_source: str | None = None,
    ) -> CkgInsight | None:
        """Abstract an observation and upsert it as a tenant-scoped insight.

        Returns the persisted row, or ``None`` when the observation matched no
        structural category (anti-noise gate). Caller is responsible for the
        surrounding transaction commit.
        """
        category, abstracted = self._abstract(raw_observation, origin_domain)
        if not category:
            # No structural pattern -- do not persist raw-text echoes.
            return None

        insight_hash = self._hash(abstracted)

        existing = (
            await self._db.execute(
                select(CkgInsight).where(
                    CkgInsight.tenant_id == self._tenant_id,
                    CkgInsight.insight_hash == insight_hash,
                )
            )
        ).scalar_one_or_none()

        if existing is not None:
            # Reinforce (reassign JSON lists so the ORM flushes the mutation).
            existing.evidence_count += 1
            existing.confidence = min(
                0.99, existing.confidence + (1 - existing.confidence) * 0.1
            )
            if evidence_source:
                existing.evidence_sources = list(existing.evidence_sources or []) + [
                    evidence_source
                ]
            if origin_domain.value not in (existing.applicable_domains or []):
                existing.applicable_domains = list(existing.applicable_domains or []) + [
                    origin_domain.value
                ]
                existing.transfer_score = (
                    len(existing.applicable_domains) / _DOMAIN_COUNT
                )
            self._maybe_promote(existing)
            return existing

        applicable = self._infer_domains(category, origin_domain)
        row = CkgInsight(
            tenant_id=self._tenant_id,
            insight_hash=insight_hash,
            raw_observation=raw_observation,
            abstracted_pattern=abstracted,
            origin_domain=origin_domain.value,
            applicable_domains=[d.value for d in applicable],
            confidence=0.5,
            evidence_count=1,
            evidence_sources=[evidence_source] if evidence_source else [],
            nbmf_tier=0,
            tags=[category],
            transfer_score=len(applicable) / _DOMAIN_COUNT,
        )
        self._db.add(row)
        await self._db.flush()  # assign PK before connecting edges

        await self._connect(row)
        logger.info(
            "ckg.learned",
            insight_hash=insight_hash,
            category=category,
            domains=len(applicable),
        )
        return row

    async def _connect(self, new_row: CkgInsight) -> None:
        """Create transfer edges from a new insight to existing tenant insights."""
        others = (
            await self._db.execute(
                select(CkgInsight).where(
                    CkgInsight.tenant_id == self._tenant_id,
                    CkgInsight.insight_hash != new_row.insight_hash,
                )
            )
        ).scalars().all()

        new_tags = set(new_row.tags or [])
        new_domains = set(new_row.applicable_domains or [])
        for other in others:
            shared_tags = new_tags & set(other.tags or [])
            if shared_tags:
                similarity = 0.8
            else:
                other_domains = set(other.applicable_domains or [])
                shared_domains = new_domains & other_domains
                if not shared_domains:
                    continue
                similarity = len(shared_domains) / max(
                    len(new_domains), len(other_domains)
                )
            if similarity >= 0.3:
                self._db.add(
                    CkgTransferEdge(
                        tenant_id=self._tenant_id,
                        source_hash=new_row.insight_hash,
                        target_hash=other.insight_hash,
                        source_domain=new_row.origin_domain,
                        target_domain=other.origin_domain,
                        similarity=similarity,
                        validated=False,
                    )
                )

    # ── Read path ───────────────────────────────────────────────

    async def query(
        self,
        domain: Domain,
        context: str = "",
        limit: int = 10,
        min_confidence: float = 0.3,
    ) -> list[CkgInsight]:
        """Ranked insights applicable to ``domain`` (confidence*recency*transfer)."""
        rows = (
            await self._db.execute(
                select(CkgInsight).where(
                    CkgInsight.tenant_id == self._tenant_id,
                    CkgInsight.confidence >= min_confidence,
                )
            )
        ).scalars().all()

        candidates: list[tuple[float, CkgInsight]] = []
        for row in rows:
            if domain.value not in (row.applicable_domains or []):
                continue
            recency = self._recency(row.updated_at)
            score = row.confidence * 0.5 + recency * 0.3 + row.transfer_score * 0.2
            candidates.append((score, row))

        candidates.sort(key=lambda x: x[0], reverse=True)

        if context:
            context_words = set(context.lower().split())
            rescored: list[tuple[float, CkgInsight]] = []
            for score, row in candidates:
                pattern_words = set(row.abstracted_pattern.lower().split())
                overlap = len(context_words & pattern_words)
                rescored.append((score + overlap * 0.1, row))
            rescored.sort(key=lambda x: x[0], reverse=True)
            return [row for _, row in rescored[:limit]]

        return [row for _, row in candidates[:limit]]

    async def semantic_query(
        self,
        query_text: str,
        max_results: int = 5,
        min_confidence: float = 0.3,
    ) -> list[CkgInsight]:
        """Cross-domain search by word overlap against every applicable domain."""
        rows = (
            await self._db.execute(
                select(CkgInsight).where(
                    CkgInsight.tenant_id == self._tenant_id,
                    CkgInsight.confidence >= min_confidence,
                )
            )
        ).scalars().all()

        query_words = set(query_text.lower().split())
        scored: list[tuple[float, CkgInsight]] = []
        for row in rows:
            pattern_words = set(row.abstracted_pattern.lower().split())
            overlap = len(query_words & pattern_words)
            if overlap == 0:
                continue
            recency = self._recency(row.updated_at)
            score = (
                overlap * 0.4
                + row.confidence * 0.3
                + recency * 0.2
                + row.transfer_score * 0.1
            )
            scored.append((score, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [row for _, row in scored[:max_results]]
