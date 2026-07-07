"""Memory service: Neural-Backed Memory Fabric (NBMF) management.

Implements store, recall, promote, demote, and search across NBMF tiers:
    WORKING(0) -> SHORT_TERM(1) -> LONG_TERM(2) -> CORE(3) -> IMMUTABLE(4)

NBMF extensions:
    - CAS deduplication via SHA-256 content hashing
    - L2Q quarantine gating (is_quarantined flag)
    - Trust scoring (0.0 to 1.0, promotion requires >= TRUST_PROMOTE_THRESHOLD)
    - Agent experience types (AGENT_DECISION, SKILL_OUTCOME, etc.)
    - Experience read/write hooks for agent learning

Tier-based TTL:
    - WORKING: 30 minutes
    - SHORT_TERM: 24 hours
    - LONG_TERM+: No expiration

Patent-pending: NBMF Architecture.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from datetime import datetime, timedelta
from typing import ClassVar
from uuid import UUID

from sqlalchemy import func, select

from app.core.constants import NBMFTier
from app.core.exceptions import ValidationError
from app.models.identity import User
from app.models.memory import LearningLog, MemoryEntry
from app.services._base import BaseService

_log = logging.getLogger(__name__)

# Trust threshold: quarantined items must reach this score to be promoted
TRUST_PROMOTE_THRESHOLD = 0.7

# Agent experience content types (stored via store_experience, excluded from user recall)
EXPERIENCE_TYPES = frozenset({
    "AGENT_DECISION", "SKILL_OUTCOME", "PATTERN_LEARNED", "APPROACH_FAILED",
})

# Stopwords stripped during keyword extraction (common English words that
# add noise to relevance scoring).  Kept minimal on purpose -- overly
# aggressive stripping removes domain terms.
_STOPWORDS: frozenset[str] = frozenset(
    {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "dare", "ought",
        "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
        "into", "through", "during", "before", "after", "above", "below",
        "between", "out", "off", "over", "under", "again", "further", "then",
        "once", "here", "there", "when", "where", "why", "how", "all", "any",
        "both", "each", "few", "more", "most", "other", "some", "such", "no",
        "nor", "not", "only", "own", "same", "so", "than", "too", "very",
        "just", "because", "but", "and", "or", "if", "while", "about", "up",
        "it", "its", "i", "me", "my", "we", "our", "you", "your", "he",
        "him", "his", "she", "her", "they", "them", "their", "what", "which",
        "who", "whom", "this", "that", "these", "those", "am",
    }
)

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*", re.ASCII)


def _tokenize(text: str) -> set[str]:
    """Extract lowercase keyword tokens, stripping stopwords."""
    return {w for w in _TOKEN_RE.findall(text.lower()) if w not in _STOPWORDS and len(w) > 1}

# TTL per tier (None = no expiration)
_TIER_TTL: dict[int, timedelta | None] = {
    NBMFTier.WORKING.value: timedelta(minutes=30),
    NBMFTier.SHORT_TERM.value: timedelta(hours=24),
    NBMFTier.LONG_TERM.value: None,
    NBMFTier.CORE.value: None,
    NBMFTier.IMMUTABLE.value: None,
}

# Max tier a user can directly store into (CORE and IMMUTABLE require promotion)
_MAX_DIRECT_STORE_TIER = NBMFTier.LONG_TERM.value
_MEMORY_SCOPES = frozenset({"USER", "SESSION", "TENANT"})


def _content_hash(content: str) -> str:
    """SHA-256 hash for CAS deduplication."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class MemoryService(BaseService):
    """CRUD + promotion/demotion for NBMF memory entries.

    Usage::

        svc = MemoryService(db)
        entry = await svc.store(
            tenant_id=tid, user_id=uid,
            content="User prefers dark mode",
            content_type="PREFERENCE",
        )
        results = await svc.recall(tenant_id=tid, query="dark mode")
    """

    # Phase 11 PR-S1: process-lifetime set of user_ids we have already
    # warned/audited about a privacy block. Prevents log+audit-row spam
    # when a user with memory_generation=false sends a long chat session
    # (every message would otherwise emit a write-block event).
    _privacy_blocked_warned: ClassVar[set[UUID]] = set()

    async def _user_allows_memory_writes(self, user_id: UUID | None) -> bool:
        """Return True unless ``users.settings.memory_generation`` is False.

        Phase 11 PR-S1 privacy gate: if the user has explicitly toggled
        Settings -> Privacy -> "Generate memories from conversations"
        OFF, refuse new memory writes for that user. Default behavior is
        unchanged when the setting is unset (returns True).

        Fail-open on any read error per the brief's rule "Preserve
        existing behavior when settings are unset" — better to record a
        memory than to silently drop one because of a transient DB hiccup.
        """
        if user_id is None:
            return True  # Anonymous / system writes pass through.
        try:
            result = await self.db.execute(
                select(User.settings).where(User.id == user_id)
            )
            row = result.scalar_one_or_none()
            if row is None:
                return True
            settings = row if isinstance(row, dict) else {}
            return settings.get("memory_generation") is not False
        except Exception:  # noqa: BLE001
            # Fail-open: never let a privacy-check error silently drop
            # memory rows. Log at debug; observers can grep for it.
            _log.debug("memory.privacy_check_failed user=%s", user_id, exc_info=True)
            return True

    async def _emit_privacy_block_once(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        action: str,
    ) -> None:
        """Best-effort audit emit + log for the first block per user-process.

        Subsequent blocks for the same user_id within this process are
        silently dropped so a long chat session doesn't fill the audit
        ledger / logs with identical privacy-block rows.
        """
        if user_id in self._privacy_blocked_warned:
            return
        self._privacy_blocked_warned.add(user_id)
        _log.info(
            "memory.privacy_blocked action=%s user_id=%s "
            "reason=memory_generation_false",
            action, user_id,
        )
        try:
            from app.services.audit import AuditService
            await AuditService(self.db).log_decision(
                tenant_id=tenant_id,
                actor_id=user_id,
                actor_type="USER",
                action_type="privacy.memory_write_blocked",
                action_params={"action": action, "reason": "memory_generation=false"},
                result="BLOCKED",
                risk_level="LOW",
                governance_tier=1,
            )
        except Exception as exc:  # noqa: BLE001
            # Audit emit is best-effort. Do not raise — the user-facing
            # privacy decision is "no write happens", which is the
            # promise we need to keep regardless of audit success.
            _log.warning(
                "memory.privacy_block_audit_failed user=%s err=%s", user_id, exc,
            )

    async def store(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        content: str,
        content_type: str = "FACT",
        summary: str | None = None,
        tags: list[str] | None = None,
        source: str | None = None,
        confidence: float = 0.5,
        tier: int = 0,
        scope: str = "USER",
        session_id: UUID | None = None,
        agent_id: UUID | None = None,
        skill_id: str | None = None,
        success_flag: bool | None = None,
        metadata: dict | None = None,
    ) -> dict:
        """Store a new memory entry with CAS dedup and optional quarantine.

        New entries with experience content types (AGENT_DECISION, SKILL_OUTCOME,
        PATTERN_LEARNED, APPROACH_FAILED) are auto-quarantined with trust_score=0.0.
        CAS dedup: if content_hash already exists for this tenant, returns existing
        entry instead of creating a duplicate.

        Returns:
            Dict with stored memory details. When the user has set
            ``users.settings.memory_generation=False``, returns a
            ``{"blocked_by_privacy": True, "reason": ..., "id": None}``
            sentinel instead of writing — callers do not currently read
            this dict, so the sentinel is safe.

        Raises:
            ValueError: If tier > MAX_DIRECT_STORE_TIER.
        """
        if tier > _MAX_DIRECT_STORE_TIER:
            msg = (
                f"Cannot directly store at tier {tier}. "
                f"Max direct store tier is {_MAX_DIRECT_STORE_TIER}. "
                "Use promote() to reach higher tiers."
            )
            raise ValidationError(msg)

        # Phase 11 PR-S1: privacy gate. If the user explicitly set
        # ``users.settings.memory_generation=false`` in /settings/privacy,
        # refuse to write a new memory row. Audit + log once per user
        # per process so a long session doesn't spam the ledger.
        if not await self._user_allows_memory_writes(user_id):
            await self._emit_privacy_block_once(
                tenant_id=tenant_id, user_id=user_id, action="store",
            )
            return {
                "blocked_by_privacy": True,
                "reason": "memory_generation=false",
                "id": None,
                "content": None,
                "content_type": content_type,
                "tier": tier,
            }

        # CAS deduplication: check for exact content match
        c_hash = _content_hash(content)
        existing_stmt = (
            select(MemoryEntry)
            .where(
                MemoryEntry.tenant_id == tenant_id,
                MemoryEntry.content_hash == c_hash,
                MemoryEntry.archived_at.is_(None),
            )
            .limit(1)
        )
        existing_result = await self.db.execute(existing_stmt)
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            # Bump access count on dedup hit instead of creating duplicate
            existing.access_count += 1
            existing.last_accessed = datetime.utcnow()
            await self.db.flush()
            await self.db.refresh(existing)
            return self._entry_to_dict(existing)

        normalized_scope = self._normalize_scope(scope)
        normalized_metadata = dict(metadata or {})
        normalized_metadata["scope"] = normalized_scope
        if normalized_scope == "SESSION":
            if session_id is None:
                msg = "SESSION-scoped memories require session_id"
                raise ValidationError(msg)
            normalized_metadata["session_id"] = str(session_id)
        else:
            normalized_metadata.pop("session_id", None)

        # Auto-quarantine agent experience types
        is_experience = content_type in EXPERIENCE_TYPES
        is_quarantined = is_experience
        trust_score = 0.0 if is_quarantined else 0.5

        # Compute TTL-based expiration
        ttl = _TIER_TTL.get(tier)
        now = datetime.utcnow()
        expires_at = (now + ttl) if ttl else None

        entry = MemoryEntry(
            tenant_id=tenant_id,
            user_id=user_id,
            agent_id=agent_id,
            tier=tier,
            content_type=content_type,
            content=content,
            summary=summary,
            tags=tags or [],
            source=source,
            confidence=confidence,
            access_count=0,
            expires_at=expires_at,
            is_quarantined=is_quarantined,
            trust_score=trust_score,
            content_hash=c_hash,
            skill_id=skill_id,
            success_flag=success_flag,
            metadata_=normalized_metadata,
        )
        self.db.add(entry)
        await self.db.flush()
        await self.db.refresh(entry)

        # Log creation
        log = LearningLog(
            tenant_id=tenant_id,
            memory_id=entry.id,
            action="CREATED",
            from_tier=None,
            to_tier=tier,
            reason="Initial storage",
            actor_id=user_id,
            created_at=now,
        )
        self.db.add(log)
        await self.db.flush()

        return self._entry_to_dict(entry)

    async def recall(
        self,
        *,
        tenant_id: UUID,
        memory_id: UUID | None = None,
        content_type: str | None = None,
        tier: int | None = None,
        tags: list[str] | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """Recall memories matching filters.

        If memory_id is provided, returns that single memory.
        Otherwise, filters by content_type, tier, tags with pagination.

        Args:
            tenant_id: Tenant UUID.
            memory_id: Optional specific memory to recall.
            content_type: Optional content type filter.
            tier: Optional tier filter.
            tags: Optional tag filter (any match).
            page: Page number (1-based).
            page_size: Items per page.

        Returns:
            Dict with data (list of memories) and pagination.
        """
        if memory_id is not None:
            entry = await self._get_memory(memory_id, tenant_id)
            # Update access tracking
            entry.access_count += 1
            entry.last_accessed = datetime.utcnow()
            await self.db.flush()
            await self.db.refresh(entry)
            return {"data": [self._entry_to_dict(entry)], "pagination": None}

        stmt = (
            select(MemoryEntry)
            .where(
                MemoryEntry.tenant_id == tenant_id,
                MemoryEntry.archived_at.is_(None),
            )
            .order_by(MemoryEntry.created_at.desc())
        )

        # Filter out expired entries
        now = datetime.utcnow()
        stmt = stmt.where(
            (MemoryEntry.expires_at.is_(None)) | (MemoryEntry.expires_at > now)
        )

        if content_type is not None:
            stmt = stmt.where(MemoryEntry.content_type == content_type)
        if tier is not None:
            stmt = stmt.where(MemoryEntry.tier == tier)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # Paginate
        offset = (page - 1) * page_size
        paginated = stmt.offset(offset).limit(page_size)
        result = await self.db.execute(paginated)
        items = list(result.scalars().all())

        return {
            "data": [self._entry_to_dict(e) for e in items],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": max(1, math.ceil(total / page_size)),
            },
        }

    async def recall_for_chat(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        session_id: UUID,
        query: str | None = None,
        tier: int = NBMFTier.LONG_TERM.value,
        page_size: int = 5,
    ) -> dict:
        """Recall chat-relevant memories with keyword relevance ranking.

        When *query* is provided, memories are scored by keyword overlap
        with the user's message, blended with tier, confidence, and
        recency signals.  When *query* is ``None``, falls back to the
        original deterministic sort (scope > tier > confidence > recency).

        Scoring formula (when query is provided):
            final = 0.50 * relevance
                  + 0.20 * tier_norm      (tier / 4)
                  + 0.20 * confidence     (0.0-1.0)
                  + 0.10 * recency_norm   (sigmoid decay over 7 days)
        """
        now = datetime.utcnow()
        stmt = (
            select(MemoryEntry)
            .where(
                MemoryEntry.tenant_id == tenant_id,
                MemoryEntry.archived_at.is_(None),
                MemoryEntry.is_quarantined.is_(False),  # Never recall quarantined
                ((MemoryEntry.expires_at.is_(None)) | (MemoryEntry.expires_at > now)),
                MemoryEntry.tier >= tier,
            )
            .order_by(MemoryEntry.created_at.desc())
        )

        result = await self.db.execute(stmt)
        entries = list(result.scalars().all())
        session_id_str = str(session_id)

        query_tokens = _tokenize(query) if query else set()
        use_relevance = bool(query_tokens)

        scored: list[tuple[float, int, MemoryEntry]] = []

        for entry in entries:
            scope = self._entry_scope(entry)
            entry_session_id = self._entry_session_id(entry)

            if scope == "SESSION":
                if entry_session_id != session_id_str:
                    continue
                priority = 0
            elif scope == "USER":
                if entry.user_id != user_id:
                    continue
                priority = 1
            elif scope == "TENANT":
                priority = 2
            else:
                continue

            if use_relevance:
                score = self._blended_score(entry, query_tokens, now)
            else:
                # Deterministic fallback: higher is better
                tier_norm = entry.tier / 4.0
                conf = entry.confidence or 0.0
                ts = entry.created_at.timestamp() if entry.created_at else 0.0
                score = tier_norm * 0.4 + conf * 0.3 + (ts / 1e10) * 0.3

            scored.append((score, priority, entry))

        if use_relevance:
            # Sort by score descending (relevance dominates), break ties by priority
            scored.sort(key=lambda item: (-item[0], item[1]))
        else:
            # Original sort: priority first, then score descending
            scored.sort(key=lambda item: (item[1], -item[0]))

        chosen_entries = [entry for _score, _priority, entry in scored[:page_size]]
        for entry in chosen_entries:
            entry.access_count += 1
            entry.last_accessed = now

        if chosen_entries:
            await self.db.flush()
            for entry in chosen_entries:
                await self.db.refresh(entry)

        return {
            "data": [self._entry_to_dict(entry) for entry in chosen_entries],
            "pagination": None,
        }

    @staticmethod
    def _blended_score(
        entry: MemoryEntry,
        query_tokens: set[str],
        now: datetime,
    ) -> float:
        """Compute blended relevance score for a memory entry.

        Components:
            relevance (0.50): Jaccard-like keyword overlap across content,
                              summary, and tags.
            tier_norm (0.20): tier / 4 (IMMUTABLE = 1.0).
            confidence (0.20): entry confidence score.
            recency   (0.10): sigmoid decay -- 1.0 for today, ~0.5 at 7 days,
                              ~0.12 at 30 days.
        """
        # Keyword relevance
        entry_text = entry.content or ""
        if entry.summary:
            entry_text += " " + entry.summary
        if entry.tags:
            entry_text += " " + " ".join(entry.tags)

        entry_tokens = _tokenize(entry_text)
        if not entry_tokens:
            relevance = 0.0
        else:
            overlap = len(query_tokens & entry_tokens)
            # Weighted Jaccard: penalize large memory text less
            denom = (
                len(query_tokens) + 0.5 * len(entry_tokens) - 0.5 * overlap
            )
            relevance = (overlap / denom) if denom > 0 else 0.0
            relevance = min(relevance, 1.0)

        # Tier normalization (0-4 -> 0.0-1.0)
        tier_norm = min(entry.tier / 4.0, 1.0)

        # Confidence (already 0.0-1.0)
        confidence = entry.confidence or 0.0

        # Recency: sigmoid decay centered at 7 days
        if entry.created_at:
            age_days = (now - entry.created_at).total_seconds() / 86400.0
            recency = 1.0 / (1.0 + math.exp((age_days - 7.0) / 3.0))
        else:
            recency = 0.0

        return 0.50 * relevance + 0.20 * tier_norm + 0.20 * confidence + 0.10 * recency

    async def promote(
        self,
        *,
        memory_id: UUID,
        tenant_id: UUID,
        actor_id: UUID,
        reason: str,
    ) -> dict:
        """Promote a memory entry to the next tier.

        Args:
            memory_id: Memory to promote.
            tenant_id: Tenant UUID.
            actor_id: User performing the promotion.
            reason: Justification for promotion.

        Returns:
            Dict with updated memory details.

        Raises:
            ValueError: If memory is already at IMMUTABLE tier.
        """
        entry = await self._get_memory(memory_id, tenant_id)
        old_tier = entry.tier

        if old_tier >= NBMFTier.IMMUTABLE.value:
            msg = "Cannot promote beyond IMMUTABLE tier"
            raise ValidationError(msg)

        new_tier = old_tier + 1
        entry.tier = new_tier

        # Update TTL for new tier
        ttl = _TIER_TTL.get(new_tier)
        entry.expires_at = (datetime.utcnow() + ttl) if ttl else None

        # Log the promotion
        log = LearningLog(
            tenant_id=tenant_id,
            memory_id=entry.id,
            action="PROMOTED",
            from_tier=old_tier,
            to_tier=new_tier,
            reason=reason,
            actor_id=actor_id,
            created_at=datetime.utcnow(),
        )
        self.db.add(log)
        await self.db.flush()
        await self.db.refresh(entry)

        return self._entry_to_dict(entry)

    async def demote(
        self,
        *,
        memory_id: UUID,
        tenant_id: UUID,
        actor_id: UUID,
        reason: str,
    ) -> dict:
        """Demote a memory entry to the previous tier.

        Args:
            memory_id: Memory to demote.
            tenant_id: Tenant UUID.
            actor_id: User performing the demotion.
            reason: Justification for demotion.

        Returns:
            Dict with updated memory details.

        Raises:
            ValueError: If memory is at WORKING (0) or IMMUTABLE (4) tier.
        """
        entry = await self._get_memory(memory_id, tenant_id)
        old_tier = entry.tier

        if old_tier >= NBMFTier.IMMUTABLE.value:
            msg = "Cannot demote IMMUTABLE memories"
            raise ValidationError(msg)
        if old_tier <= NBMFTier.WORKING.value:
            msg = "Cannot demote below WORKING tier"
            raise ValidationError(msg)

        new_tier = old_tier - 1
        entry.tier = new_tier

        # Update TTL for new tier
        ttl = _TIER_TTL.get(new_tier)
        entry.expires_at = (datetime.utcnow() + ttl) if ttl else None

        # Log the demotion
        log = LearningLog(
            tenant_id=tenant_id,
            memory_id=entry.id,
            action="DEMOTED",
            from_tier=old_tier,
            to_tier=new_tier,
            reason=reason,
            actor_id=actor_id,
            created_at=datetime.utcnow(),
        )
        self.db.add(log)
        await self.db.flush()
        await self.db.refresh(entry)

        return self._entry_to_dict(entry)

    async def get_history(
        self,
        *,
        memory_id: UUID,
        tenant_id: UUID,
    ) -> list[dict]:
        """Get the learning log (tier change history) for a memory.

        Args:
            memory_id: Memory UUID.
            tenant_id: Tenant UUID.

        Returns:
            List of learning log dicts, newest first.
        """
        # Verify memory exists and belongs to tenant
        await self._get_memory(memory_id, tenant_id)

        stmt = (
            select(LearningLog)
            .where(
                LearningLog.memory_id == memory_id,
                LearningLog.tenant_id == tenant_id,
            )
            .order_by(LearningLog.created_at.desc())
        )
        result = await self.db.execute(stmt)
        logs = list(result.scalars().all())

        return [self._log_to_dict(lg) for lg in logs]

    async def clear_ephemeral(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
    ) -> dict:
        """Archive WORKING and SHORT_TERM memories for the current user."""
        now = datetime.utcnow()
        stmt = (
            select(MemoryEntry)
            .where(
                MemoryEntry.tenant_id == tenant_id,
                MemoryEntry.user_id == user_id,
                MemoryEntry.archived_at.is_(None),
                MemoryEntry.tier.in_([NBMFTier.WORKING.value, NBMFTier.SHORT_TERM.value]),
            )
        )
        result = await self.db.execute(stmt)
        entries = list(result.scalars().all())

        for entry in entries:
            entry.archived_at = now

        if entries:
            await self.db.flush()

        return {
            "archived_count": len(entries),
            "tiers": [NBMFTier.WORKING.value, NBMFTier.SHORT_TERM.value],
        }

    async def _get_memory(self, memory_id: UUID, tenant_id: UUID) -> MemoryEntry:
        """Fetch a memory entry scoped to a tenant.

        Args:
            memory_id: Memory UUID.
            tenant_id: Tenant UUID.

        Returns:
            MemoryEntry ORM instance.

        Raises:
            NotFoundError: If memory doesn't exist or wrong tenant.
        """
        return await self._get_or_404(
            MemoryEntry,
            memory_id,
            tenant_id=tenant_id,
        )

    @staticmethod
    def _entry_to_dict(entry: MemoryEntry) -> dict:
        """Convert MemoryEntry model to response dict.

        Args:
            entry: MemoryEntry ORM instance.

        Returns:
            Serializable dict.
        """
        metadata = dict(entry.metadata_ or {})
        metadata.pop("scope", None)
        metadata.pop("session_id", None)

        return {
            "id": str(entry.id),
            "tenant_id": str(entry.tenant_id),
            "user_id": str(entry.user_id) if entry.user_id else None,
            "agent_id": str(entry.agent_id) if entry.agent_id else None,
            "tier": entry.tier,
            "content_type": entry.content_type,
            "content": entry.content,
            "summary": entry.summary,
            "tags": entry.tags or [],
            "source": entry.source,
            "confidence": float(entry.confidence),
            "scope": MemoryService._entry_scope(entry),
            "session_id": MemoryService._entry_session_id(entry),
            "access_count": entry.access_count,
            "last_accessed": (
                entry.last_accessed.isoformat() if entry.last_accessed else None
            ),
            "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
            "is_quarantined": bool(entry.is_quarantined),
            "trust_score": float(entry.trust_score),
            "content_hash": entry.content_hash,
            "skill_id": entry.skill_id,
            "success_flag": entry.success_flag,
            "verification_status": entry.verification_status,
            "verified_by": str(entry.verified_by) if entry.verified_by else None,
            "metadata": metadata,
            "archived_at": (
                entry.archived_at.isoformat() if entry.archived_at else None
            ),
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
            "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
        }

    @staticmethod
    def _normalize_scope(scope: str | None) -> str:
        normalized = (scope or "USER").strip().upper()
        if normalized not in _MEMORY_SCOPES:
            msg = f"Invalid memory scope '{scope}'. Expected one of: USER, SESSION, TENANT."
            raise ValidationError(msg)
        return normalized

    @staticmethod
    def _entry_scope(entry: MemoryEntry) -> str:
        metadata = entry.metadata_ or {}
        scope = metadata.get("scope")
        if isinstance(scope, str) and scope.strip():
            normalized = scope.strip().upper()
            if normalized in _MEMORY_SCOPES:
                return normalized
        return "USER"

    @staticmethod
    def _entry_session_id(entry: MemoryEntry) -> str | None:
        metadata = entry.metadata_ or {}
        session_id = metadata.get("session_id")
        return str(session_id) if session_id else None

    @staticmethod
    def _log_to_dict(log: LearningLog) -> dict:
        """Convert LearningLog model to response dict.

        Args:
            log: LearningLog ORM instance.

        Returns:
            Serializable dict.
        """
        return {
            "id": str(log.id),
            "memory_id": str(log.memory_id),
            "action": log.action,
            "from_tier": log.from_tier,
            "to_tier": log.to_tier,
            "reason": log.reason,
            "actor_id": str(log.actor_id) if log.actor_id else None,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }

    # ── Agent Experience Methods ──────────────────────────────

    async def store_experience(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        agent_id: UUID,
        content: str,
        content_type: str = "AGENT_DECISION",
        summary: str | None = None,
        skill_id: str | None = None,
        success_flag: bool | None = None,
        confidence: float = 0.5,
        tags: list[str] | None = None,
        metadata: dict | None = None,
    ) -> dict:
        """Store an agent experience in quarantine (L2Q).

        Write path:
            1. Sensitivity scanner runs FIRST (PII, financial, legal, medical, creds)
            2. If sensitive: force lossless encoding, flag as SENSITIVE
            3. CAS dedup (in store())
            4. L2Q quarantine (auto in store() for experience types)

        IMPORTANT: This stores AGENT experiences (decisions, skill outcomes,
        patterns), never user message content or tenant data.
        """
        if content_type not in EXPERIENCE_TYPES:
            content_type = "AGENT_DECISION"

        # ── Step 1: Sensitivity scan BEFORE storing ──
        from app.services.dream_engine import is_sensitive

        scan_text = content
        if summary:
            scan_text += " " + summary
        sensitive, categories = is_sensitive(scan_text)

        enriched_metadata = dict(metadata or {})
        if sensitive:
            enriched_metadata["is_sensitive"] = True
            enriched_metadata["sensitive_categories"] = categories
            enriched_metadata["encoding_mode"] = "lossless"

        result = await self.store(
            tenant_id=tenant_id,
            user_id=user_id,
            content=content,
            content_type=content_type,
            summary=summary,
            tags=tags or [content_type.lower()],
            source="agent_experience",
            confidence=confidence,
            tier=0,  # WORKING tier; quarantine flag controls visibility
            scope="TENANT",  # Agent experiences are org-wide
            agent_id=agent_id,
            skill_id=skill_id,
            success_flag=success_flag,
            metadata=enriched_metadata,
        )

        # ── Step 1b: If sensitive, update model columns too ──
        if sensitive and result.get("id"):
            try:
                entry = await self._get_memory(
                    __import__("uuid").UUID(result["id"]), tenant_id
                )
                entry.is_sensitive = True
                entry.encoding_mode = "lossless"
                await self.db.flush()
                await self.db.refresh(entry)
            except Exception:
                pass  # Non-critical; metadata already has the flag

        return result

    async def recall_experiences(
        self,
        *,
        tenant_id: UUID,
        agent_id: UUID | None = None,
        skill_id: str | None = None,
        query: str | None = None,
        top_k: int = 5,
    ) -> list[dict]:
        """Recall validated (non-quarantined) agent experiences.

        Only returns experiences that have passed quarantine
        (is_quarantined=False, trust_score >= TRUST_PROMOTE_THRESHOLD).
        Never returns quarantined or unvalidated experiences.

        Results are scored by keyword relevance, trust, confidence, and recency.
        """
        now = datetime.utcnow()
        stmt = (
            select(MemoryEntry)
            .where(
                MemoryEntry.tenant_id == tenant_id,
                MemoryEntry.content_type.in_(EXPERIENCE_TYPES),
                MemoryEntry.is_quarantined.is_(False),
                MemoryEntry.trust_score >= TRUST_PROMOTE_THRESHOLD,
                MemoryEntry.archived_at.is_(None),
                ((MemoryEntry.expires_at.is_(None)) | (MemoryEntry.expires_at > now)),
            )
            .order_by(MemoryEntry.trust_score.desc(), MemoryEntry.created_at.desc())
        )

        if agent_id is not None:
            stmt = stmt.where(MemoryEntry.agent_id == agent_id)
        if skill_id is not None:
            stmt = stmt.where(MemoryEntry.skill_id == skill_id)

        result = await self.db.execute(stmt)
        entries = list(result.scalars().all())

        query_tokens = _tokenize(query) if query else set()
        if query_tokens:
            scored = [
                (self._blended_score(e, query_tokens, now), e)
                for e in entries
            ]
            scored.sort(key=lambda x: -x[0])
            entries = [e for _, e in scored[:top_k]]
        else:
            entries = entries[:top_k]

        # Bump access counts
        for entry in entries:
            entry.access_count += 1
            entry.last_accessed = now
        if entries:
            await self.db.flush()
            for entry in entries:
                await self.db.refresh(entry)

        return [self._entry_to_dict(e) for e in entries]

    async def validate_quarantined(
        self,
        *,
        tenant_id: UUID,
        batch_size: int = 50,
    ) -> dict:
        """Background promotion: validate quarantined experiences.

        Promotion rules:
        - If same content_hash appears 3+ times with success_flag=True,
          promote to trusted (is_quarantined=False, trust_score=0.8).
        - If success_flag=False consistently (3+ times), demote (archive).
        - Otherwise, increment trust_score by 0.1 per successful duplicate.

        Returns summary of promotions and demotions.
        """
        now = datetime.utcnow()
        stmt = (
            select(MemoryEntry)
            .where(
                MemoryEntry.tenant_id == tenant_id,
                MemoryEntry.content_type.in_(EXPERIENCE_TYPES),
                MemoryEntry.is_quarantined.is_(True),
                MemoryEntry.archived_at.is_(None),
            )
            .order_by(MemoryEntry.created_at.asc())
            .limit(batch_size)
        )
        result = await self.db.execute(stmt)
        quarantined = list(result.scalars().all())

        promoted_count = 0
        demoted_count = 0
        # Plain-value tuples for experiences promoted THIS batch that are safe to
        # feed to ragx (non-sensitive only). Captured at promotion time -- see the
        # ragx feed block after flush() for why we copy scalars instead of passing
        # the ORM row.
        to_ingest: list[tuple] = []

        for entry in quarantined:
            # Count siblings with same content hash
            if entry.content_hash:
                sibling_stmt = select(func.count()).where(
                    MemoryEntry.tenant_id == tenant_id,
                    MemoryEntry.content_hash == entry.content_hash,
                    MemoryEntry.archived_at.is_(None),
                )
                sibling_result = await self.db.execute(sibling_stmt)
                sibling_count = sibling_result.scalar() or 0
            else:
                sibling_count = 1

            if entry.success_flag is True and sibling_count >= 3:
                # Repeated success: promote
                entry.is_quarantined = False
                entry.trust_score = 0.8
                entry.tier = max(entry.tier, NBMFTier.SHORT_TERM.value)
                promoted_count += 1
                if not entry.is_sensitive:
                    to_ingest.append((
                        entry.id, entry.content, entry.summary,
                        list(entry.tags or []), entry.created_at,
                    ))

                log = LearningLog(
                    tenant_id=tenant_id,
                    memory_id=entry.id,
                    action="TRUST_PROMOTED",
                    from_tier=0,
                    to_tier=entry.tier,
                    reason=f"Repeated success ({sibling_count}x), trust validated",
                    created_at=now,
                )
                self.db.add(log)

            elif entry.success_flag is False and sibling_count >= 3:
                # Repeated failure: archive as anti-pattern
                entry.archived_at = now
                entry.trust_score = 0.0
                demoted_count += 1

                log = LearningLog(
                    tenant_id=tenant_id,
                    memory_id=entry.id,
                    action="TRUST_DEMOTED",
                    from_tier=entry.tier,
                    to_tier=None,
                    reason=f"Repeated failure ({sibling_count}x), archived",
                    created_at=now,
                )
                self.db.add(log)

            elif entry.success_flag is True:
                # Single success: bump trust
                entry.trust_score = min(entry.trust_score + 0.1, 1.0)
                if entry.trust_score >= TRUST_PROMOTE_THRESHOLD:
                    entry.is_quarantined = False
                    promoted_count += 1
                    if not entry.is_sensitive:
                        to_ingest.append((
                            entry.id, entry.content, entry.summary,
                            list(entry.tags or []), entry.created_at,
                        ))

        if quarantined:
            await self.db.flush()

        # Feed newly-promoted, non-sensitive experiences into the tenant's ragx
        # collection so Stage 6.1 recalls them semantically (Phase 3 item 9, G2).
        # Fire-and-forget with PLAIN values captured above: promotion only flushed
        # (not committed), so a task that re-read the row could race the uncommitted
        # is_quarantined flip -- passing scalars removes any DB dependency. Lazy
        # import keeps this module httpx-free. Fails open: never breaks promotion.
        if to_ingest:
            try:
                from app.services.experience_ingest import schedule_experience_ingest

                for exp_id, content, summary, tags, created_at in to_ingest:
                    schedule_experience_ingest(
                        tenant_id=tenant_id,
                        experience_id=exp_id,
                        content=content,
                        summary=summary,
                        tags=tags,
                        created_at=created_at,
                    )
            except Exception:
                _log.debug("memory.experience_ingest_schedule_failed", exc_info=True)

        return {
            "reviewed": len(quarantined),
            "promoted": promoted_count,
            "demoted": demoted_count,
        }

    # ── Dream Engine Methods ──────────────────────────────────

    async def get_all_entries(self, *, tenant_id: UUID | str) -> list[dict]:
        """Return all non-archived memory entries as list of dicts.

        Used by Dream Engine for consolidation scans.
        """
        stmt = (
            select(MemoryEntry)
            .where(
                MemoryEntry.tenant_id == str(tenant_id),
                MemoryEntry.archived_at.is_(None),
            )
            .order_by(MemoryEntry.created_at.desc())
        )
        result = await self.db.execute(stmt)
        entries = list(result.scalars().all())
        out = []
        for e in entries:
            d = self._entry_to_dict(e)
            # Add model fields Dream Engine needs
            d["is_sensitive"] = bool(getattr(e, "is_sensitive", False))
            d["contradiction"] = bool(getattr(e, "contradiction", False))
            out.append(d)
        return out

    async def dream_mark_sensitive(
        self,
        *,
        entry_id: str,
        categories: list[str],
        tenant_id: str,
    ) -> None:
        """Mark an entry as sensitive and force lossless encoding."""
        from uuid import UUID as _UUID
        entry = await self._get_memory(_UUID(entry_id), _UUID(tenant_id))
        entry.is_sensitive = True
        entry.encoding_mode = "lossless"
        meta = dict(entry.metadata_ or {})
        meta["sensitive_categories"] = categories
        entry.metadata_ = meta
        log = LearningLog(
            tenant_id=entry.tenant_id,
            memory_id=entry.id,
            action="SENSITIVE_FLAGGED",
            from_tier=entry.tier,
            to_tier=entry.tier,
            reason=f"Dream Engine: {', '.join(categories)}",
            created_at=datetime.utcnow(),
        )
        self.db.add(log)
        await self.db.flush()

    async def dream_promote_entry(
        self,
        *,
        entry_id: str,
        new_trust: float,
        tenant_id: str,
        reason: str = "dream_promotion",
    ) -> None:
        """Promote a quarantined entry (unquarantine + set trust)."""
        from uuid import UUID as _UUID
        entry = await self._get_memory(_UUID(entry_id), _UUID(tenant_id))
        old_tier = entry.tier
        entry.is_quarantined = False
        entry.trust_score = new_trust
        entry.tier = max(entry.tier, 1)  # At least SHORT_TERM
        log = LearningLog(
            tenant_id=entry.tenant_id,
            memory_id=entry.id,
            action="DREAM_PROMOTED",
            from_tier=old_tier,
            to_tier=entry.tier,
            reason=reason,
            created_at=datetime.utcnow(),
        )
        self.db.add(log)
        await self.db.flush()

    async def dream_archive_entry(self, entry_id: str, tenant_id: str) -> None:
        """Archive an entry (set archived_at)."""
        from uuid import UUID as _UUID
        entry = await self._get_memory(_UUID(entry_id), _UUID(tenant_id))
        entry.archived_at = datetime.utcnow()
        log = LearningLog(
            tenant_id=entry.tenant_id,
            memory_id=entry.id,
            action="DREAM_ARCHIVED",
            from_tier=entry.tier,
            to_tier=None,
            reason="Dream Engine: decay/merge archive",
            created_at=datetime.utcnow(),
        )
        self.db.add(log)
        await self.db.flush()

    async def dream_demote_tier(
        self, entry_id: str, new_tier: int, tenant_id: str
    ) -> None:
        """Demote an entry to a lower tier."""
        from uuid import UUID as _UUID
        entry = await self._get_memory(_UUID(entry_id), _UUID(tenant_id))
        old_tier = entry.tier
        entry.tier = new_tier
        log = LearningLog(
            tenant_id=entry.tenant_id,
            memory_id=entry.id,
            action="DREAM_DEMOTED",
            from_tier=old_tier,
            to_tier=new_tier,
            reason="Dream Engine: decay demotion",
            created_at=datetime.utcnow(),
        )
        self.db.add(log)
        await self.db.flush()

    async def dream_update_trust(
        self, entry_id: str, new_trust: float, tenant_id: str
    ) -> None:
        """Update trust score for an entry."""
        from uuid import UUID as _UUID
        entry = await self._get_memory(_UUID(entry_id), _UUID(tenant_id))
        entry.trust_score = new_trust
        await self.db.flush()

    async def dream_flag_contradiction(
        self,
        *,
        entry_ids: list[str],
        tenant_id: str,
    ) -> None:
        """Flag entries as contradictory and reduce trust by 0.15."""
        from uuid import UUID as _UUID
        for eid in entry_ids:
            entry = await self._get_memory(_UUID(eid), _UUID(tenant_id))
            entry.contradiction = True
            entry.trust_score = max(0.0, entry.trust_score - 0.15)
        log = LearningLog(
            tenant_id=_UUID(tenant_id),
            memory_id=_UUID(entry_ids[0]),
            action="CONTRADICTION_FLAGGED",
            reason=f"Dream Engine: entries {entry_ids} have opposing outcomes",
            created_at=datetime.utcnow(),
        )
        self.db.add(log)
        await self.db.flush()

    async def dream_store_pattern(
        self,
        *,
        content: str,
        trust_score: float,
        tenant_id: str,
        metadata: dict | None = None,
    ) -> str:
        """Store a Dream Engine-generated pattern (trusted, not quarantined).

        Returns the new entry ID as string.
        """
        c_hash = _content_hash(content)
        now = datetime.utcnow()
        entry = MemoryEntry(
            tenant_id=tenant_id,
            tier=1,  # SHORT_TERM
            content_type="PATTERN_LEARNED",
            content=content,
            tags=["dream_engine", "pattern_learned"],
            source="dream_engine",
            confidence=trust_score,
            is_quarantined=False,
            trust_score=trust_score,
            content_hash=c_hash,
            metadata_=metadata or {},
        )
        self.db.add(entry)
        await self.db.flush()
        await self.db.refresh(entry)

        log = LearningLog(
            tenant_id=entry.tenant_id,
            memory_id=entry.id,
            action="DREAM_CREATED",
            from_tier=None,
            to_tier=1,
            reason="Dream Engine: synthesized pattern",
            created_at=now,
        )
        self.db.add(log)
        await self.db.flush()
        return str(entry.id)

    async def get_experience_stats(
        self,
        *,
        tenant_id: UUID,
    ) -> dict:
        """Get experience memory statistics: counts by type, quarantine, trust."""
        # Total experiences
        exp_stmt = select(func.count()).where(
            MemoryEntry.tenant_id == tenant_id,
            MemoryEntry.content_type.in_(EXPERIENCE_TYPES),
            MemoryEntry.archived_at.is_(None),
        )
        exp_result = await self.db.execute(exp_stmt)
        experience_count = exp_result.scalar() or 0

        # Quarantined count
        q_stmt = select(func.count()).where(
            MemoryEntry.tenant_id == tenant_id,
            MemoryEntry.is_quarantined.is_(True),
            MemoryEntry.archived_at.is_(None),
        )
        q_result = await self.db.execute(q_stmt)
        quarantined_count = q_result.scalar() or 0

        # Average trust score of non-quarantined experiences
        avg_stmt = select(func.avg(MemoryEntry.trust_score)).where(
            MemoryEntry.tenant_id == tenant_id,
            MemoryEntry.content_type.in_(EXPERIENCE_TYPES),
            MemoryEntry.is_quarantined.is_(False),
            MemoryEntry.archived_at.is_(None),
        )
        avg_result = await self.db.execute(avg_stmt)
        avg_trust = avg_result.scalar() or 0.0

        return {
            "experience_count": experience_count,
            "quarantined_count": quarantined_count,
            "avg_trust_score": round(float(avg_trust), 3),
        }
