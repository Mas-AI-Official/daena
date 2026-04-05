"""Speculative Pre-Computation (SPC) engine for Laevateinn.

Mythos computes on-demand.  Laevateinn computes ahead of demand.

After answering a query, SPC predicts likely follow-ups and launches
background asyncio tasks to pre-compute answers.  When the user asks
the follow-up the answer is already cached -- perceived latency
approaches zero for predictable conversational flows.

Predictions come from the Persistent Knowledge Graph (PKG) when
available, falling back to heuristic what/how/why progression patterns.
Only the fastest local model is used for speculative compute (the
result is a warm hint, not a critical answer).
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.services.llm_service import LLMService

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class CachedAnswer:
    """A pre-computed speculative answer stored in the SPC cache."""

    query: str
    answer: str
    confidence: float
    model_id: str
    computed_at: float
    ttl_seconds: int = 300  # 5 min default TTL
    hit_count: int = 0


@dataclass(slots=True)
class SpeculationResult:
    """Summary returned after a speculate() call."""

    predicted_queries: list[str]
    tasks_launched: int
    cache_size: int


# ---------------------------------------------------------------------------
# Core engine
# ---------------------------------------------------------------------------


class SpeculativePrecomputer:
    """Predict follow-up queries and pre-compute answers in background tasks.

    * In-memory TTL + LRU cache (no external deps).
    * Background ``asyncio.Task`` management with automatic cleanup.
    * PKG-enhanced prediction when a knowledge graph is available.
    """

    def __init__(
        self,
        llm_service: LLMService | None = None,
        knowledge_graph: Any | None = None,
        max_cache_size: int = 50,
    ) -> None:
        self._cache: dict[str, CachedAnswer] = {}
        self._llm: LLMService | None = llm_service
        self._pkg: Any | None = knowledge_graph  # PersistentKnowledgeGraph
        self._tasks: set[asyncio.Task[None]] = set()
        self._max_cache_size = max_cache_size
        self._total_hits = 0
        self._total_misses = 0

    # ── Public API ─────────────────────────────────────────────

    async def speculate(
        self,
        query: str,
        answer: str,
        *,
        model_id: str = "",
    ) -> SpeculationResult:
        """Predict follow-ups and launch background pre-computation tasks.

        Args:
            query: The query that was just answered.
            answer: The answer that was returned to the user.
            model_id: Model used for the answer (informational).

        Returns:
            SpeculationResult with predicted queries and task counts.
        """
        self._evict_expired()

        predicted = self._predict_followups(query, answer)
        launched = 0

        for pq in predicted:
            # Skip if already cached and still valid
            if self._lookup_exact(pq) is not None:
                continue
            task = asyncio.create_task(
                self._background_compute(pq, model_id),
                name=f"spc:{pq[:40]}",
            )
            task.add_done_callback(self._task_done)
            self._tasks.add(task)
            launched += 1

        logger.info(
            "spc_speculate",
            query=query[:80],
            predicted=len(predicted),
            launched=launched,
            cache_size=len(self._cache),
        )

        return SpeculationResult(
            predicted_queries=predicted,
            tasks_launched=launched,
            cache_size=len(self._cache),
        )

    async def check_cache(
        self,
        query: str,
        *,
        threshold: float = 0.8,
    ) -> CachedAnswer | None:
        """Check if a similar query was pre-computed.

        Uses token-overlap Jaccard similarity against all cached entries.
        Returns the best match above *threshold*, or ``None``.
        """
        self._evict_expired()

        best_entry: CachedAnswer | None = None
        best_sim = 0.0

        for entry in self._cache.values():
            sim = self._similarity(query, entry.query)
            if sim > best_sim:
                best_sim = sim
                best_entry = entry

        if best_entry is not None and best_sim >= threshold:
            best_entry.hit_count += 1
            self._total_hits += 1
            logger.info(
                "spc_cache_hit",
                query=query[:80],
                matched=best_entry.query[:80],
                similarity=round(best_sim, 3),
                hit_count=best_entry.hit_count,
            )
            return best_entry

        self._total_misses += 1
        return None

    # ── Background compute ─────────────────────────────────────

    async def _background_compute(self, query: str, model_id: str) -> None:
        """Run a lightweight LLM call in the background and cache the result.

        Uses the fastest available local model.  If no LLM service is
        wired, stores a placeholder so we at least record the prediction.
        """
        start = time.time()

        if self._llm is None:
            # No LLM wired -- store a stub so check_cache can still match
            self._store(
                query=query,
                answer="[speculative -- awaiting LLM service]",
                confidence=0.0,
                model_id="none",
            )
            return

        try:
            # Build a minimal generate request for the fastest local model.
            # Import here to avoid coupling at module level.
            from app.services.llm_service import GenerateRequest

            request = GenerateRequest(
                messages=[
                    {"role": "system", "content": "Answer concisely in 2-3 sentences."},
                    {"role": "user", "content": query},
                ],
                model="auto",
                max_tokens=256,
                temperature=0.3,
            )

            # Use a short timeout -- speculative work is best-effort
            response = await asyncio.wait_for(
                self._llm.generate(request, decision=None),  # type: ignore[arg-type]
                timeout=15.0,
            )

            elapsed = time.time() - start
            self._store(
                query=query,
                answer=response.content if hasattr(response, "content") else str(response),
                confidence=0.7,
                model_id=getattr(response, "model_id", model_id) or model_id,
            )

            logger.debug(
                "spc_background_done",
                query=query[:80],
                elapsed_s=round(elapsed, 2),
            )

        except asyncio.TimeoutError:
            logger.warning("spc_background_timeout", query=query[:80])
        except Exception:
            logger.exception("spc_background_error", query=query[:80])

    # ── Prediction ─────────────────────────────────────────────

    def _predict_followups(self, query: str, answer: str) -> list[str]:
        """Predict the 3 most likely follow-up questions.

        Uses PKG when available for graph-informed predictions.
        Falls back to heuristic what/how/why progression patterns.
        """
        # Attempt PKG-based prediction first
        if self._pkg is not None:
            try:
                pkg_predictions: list[str] = self._pkg.predict_followups(
                    query, answer, limit=3,
                )
                if pkg_predictions:
                    return pkg_predictions[:3]
            except Exception:
                logger.debug("spc_pkg_fallback", reason="predict_followups failed")

        # Heuristic prediction
        query_lower = query.lower().strip()

        # Pattern: "What is X?" -> practical use, alternatives, pitfalls
        m = re.search(r"\bwhat\s+(?:is|are)\s+(.+)", query_lower)
        if m:
            topic = m.group(1).rstrip("? .")
            return [
                f"How do I use {topic} in practice?",
                f"What are the alternatives to {topic}?",
                f"What are common mistakes when using {topic}?",
            ]

        # Pattern: "How to/do/can X?" -> failure modes, best practices, examples
        m = re.search(r"\bhow\s+(?:do|can|to|should)\s+(?:I\s+)?(.+)", query_lower)
        if m:
            topic = m.group(1).rstrip("? .")
            return [
                f"What if {topic} fails?",
                f"What are best practices for {topic}?",
                f"Can you show an example of {topic}?",
            ]

        # Pattern: "Why X?" -> deeper mechanism, implications, exceptions
        m = re.search(r"\bwhy\s+(?:does?|is|are|did|do)\s+(.+)", query_lower)
        if m:
            topic = m.group(1).rstrip("? .")
            return [
                f"What are the implications of {topic}?",
                f"Are there exceptions where {topic} does not apply?",
                f"How can I take advantage of {topic}?",
            ]

        # Pattern: fix/debug/error -> prevention, monitoring, related issues
        if re.search(r"\bfix\b|\bdebug\b|\berror\b|\bbug\b|\bfail", query_lower):
            return [
                "How do I prevent this issue in the future?",
                "What monitoring should I set up?",
                "Are there related issues I should check?",
            ]

        # Pattern: compare/vs/difference -> when to use each, migration, cost
        if re.search(r"\bcompare\b|\bvs\.?\b|\bdifference\b", query_lower):
            return [
                "When should I use one over the other?",
                "How hard is it to migrate between them?",
                "What are the cost implications?",
            ]

        # Generic: example, trade-offs, next step
        return [
            "Can you give me a practical example?",
            "What are the trade-offs to consider?",
            "What should I do next?",
        ]

    # ── Similarity ─────────────────────────────────────────────

    def _similarity(self, a: str, b: str) -> float:
        """Jaccard similarity on lowercased word token sets."""
        tokens_a = set(a.lower().split())
        tokens_b = set(b.lower().split())
        if not tokens_a or not tokens_b:
            return 0.0
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        return len(intersection) / len(union)

    # ── Cache management ───────────────────────────────────────

    def _store(
        self,
        query: str,
        answer: str,
        confidence: float,
        model_id: str,
    ) -> None:
        """Store a computed answer, evicting if necessary."""
        if len(self._cache) >= self._max_cache_size:
            self._evict_lru()

        self._cache[query.lower().strip()] = CachedAnswer(
            query=query,
            answer=answer,
            confidence=confidence,
            model_id=model_id,
            computed_at=time.time(),
        )

    def _lookup_exact(self, query: str) -> CachedAnswer | None:
        """Exact key lookup (case-insensitive, stripped)."""
        entry = self._cache.get(query.lower().strip())
        if entry is None:
            return None
        if time.time() - entry.computed_at > entry.ttl_seconds:
            del self._cache[query.lower().strip()]
            return None
        return entry

    def _evict_expired(self) -> None:
        """Remove all entries whose TTL has elapsed."""
        now = time.time()
        expired = [
            key
            for key, entry in self._cache.items()
            if now - entry.computed_at > entry.ttl_seconds
        ]
        for key in expired:
            del self._cache[key]
        if expired:
            logger.debug("spc_evict_expired", count=len(expired))

    def _evict_lru(self) -> None:
        """Remove the least-recently-used entry (lowest hit_count, oldest)."""
        if not self._cache:
            return
        # Sort by (hit_count ASC, computed_at ASC) -- evict least useful first
        victim_key = min(
            self._cache,
            key=lambda k: (self._cache[k].hit_count, self._cache[k].computed_at),
        )
        del self._cache[victim_key]
        logger.debug("spc_evict_lru", evicted=victim_key[:60])

    # ── Task cleanup ───────────────────────────────────────────

    def _task_done(self, task: asyncio.Task[None]) -> None:
        """Callback to discard completed background tasks."""
        self._tasks.discard(task)
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.warning("spc_task_failed", error=str(exc))

    # ── Stats ──────────────────────────────────────────────────

    @property
    def stats(self) -> dict[str, Any]:
        """Current SPC engine statistics."""
        total_lookups = self._total_hits + self._total_misses
        return {
            "cache_size": len(self._cache),
            "max_cache_size": self._max_cache_size,
            "active_tasks": len(self._tasks),
            "total_hits": self._total_hits,
            "total_misses": self._total_misses,
            "hit_rate": (
                round(self._total_hits / total_lookups, 3)
                if total_lookups > 0
                else 0.0
            ),
        }
