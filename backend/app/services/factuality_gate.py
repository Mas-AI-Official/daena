"""FactualityGate -- grounded-retrieval verification layer.

Sits in the chat pipeline beside SecurityGate. SecurityGate stops prompt
injection; FactualityGate stops hallucination. Both run in all governance
modes (UNLEASHED also benefits from grounded answers).

Backed by ragx, the universal RAG + anti-hallucination service running at
http://127.0.0.1:8100 (separate process, owned by D:/Ideas/_tools/rag-core).

Per ADR-001 (Honesty + Persistence + Visibility): when ragx is offline the
gate returns `available=False`. It does NOT silently pass the answer
through as if verified. The orchestrator decides whether to surface the
unverified state to the operator.

Usage::

    from app.services.factuality_gate import FactualityGate

    verdict = await FactualityGate.verify(
        query="How does Shield enforce policies?",
        candidate_answer=model_answer,
        collections=["daena-code", "daena-docs"],
    )
    if verdict.available and verdict.abstain:
        # ragx says evidence is too weak. Replace answer + log.
        ...
    elif verdict.available and not verdict.abstain:
        # Pass through with citations attached.
        ...
    else:
        # ragx offline. Audit-log the gap; let governance decide.
        ...

The gate is intentionally thin. Daena's audit pipeline owns the decision
(surface or suppress, retry or escalate). FactualityGate just supplies
the grounded signal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import get_settings


# Sourced from Settings so RAGX_BASE_URL in .env flows through (shared with
# ragx_bridge.py). Name preserved -- consumed as a module global below.
RAGX_URL = get_settings().ragx_base_url

# Per-collection defaults Daena trusts. Override at call sites when narrowing.
DEFAULT_COLLECTIONS: tuple[str, ...] = (
    "daena-code",
    "daena-docs",
    "daena-memory",
)


@dataclass(frozen=True, slots=True)
class Citation:
    chunk_id: str
    source_path: str
    score: float
    snippet: str


@dataclass(frozen=True, slots=True)
class FactualityVerdict:
    """The structured signal Daena's pipeline acts on.

    Fields:
        available     : ragx was reachable and answered.
        abstain       : ragx says evidence is too weak to support an answer.
        confidence    : 0 to 1, top rerank score across the searched collections.
        citations     : supporting chunks (may be empty if abstained).
        reasons       : per-collection abstention reasons (only when abstain=True).
        candidate     : the answer Daena sent in (echoed for downstream logging).
        latency_ms    : total wall-clock spent in this verify call.
    """
    available: bool
    abstain: bool
    confidence: float
    citations: list[Citation] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    candidate: str = ""
    latency_ms: float = 0.0


class FactualityGate:
    """Stateless grounded-retrieval verifier. Always-on in all governance modes."""

    timeout_seconds: float = 30.0

    @classmethod
    async def verify(
        cls,
        query: str,
        candidate_answer: str,
        collections: tuple[str, ...] | list[str] | None = None,
        k: int = 8,
    ) -> FactualityVerdict:
        """Retrieve grounded evidence across the configured collections.

        Returns a `FactualityVerdict` the orchestrator can act on. Does NOT
        modify `candidate_answer`. Does NOT raise on ragx outage; the
        verdict's `available` field signals that path.
        """
        # Distinguish None (use defaults) from explicit [] (caller chose nothing).
        if collections is None:
            targets = list(DEFAULT_COLLECTIONS)
        else:
            targets = list(collections)
        if not targets:
            return FactualityVerdict(
                available=False,
                abstain=True,
                confidence=0.0,
                reasons=["no collections configured"],
                candidate=candidate_answer,
            )

        import time
        t0 = time.perf_counter()

        all_citations: list[Citation] = []
        reasons: list[str] = []
        best_confidence = 0.0
        any_response = False

        try:
            async with httpx.AsyncClient(timeout=cls.timeout_seconds) as client:
                for coll in targets:
                    try:
                        r = await client.post(
                            f"{RAGX_URL}/query",
                            json={
                                "collection": coll,
                                "q": query,
                                "k": k,
                                "generate": False,
                            },
                        )
                    except httpx.RequestError:
                        continue
                    if r.status_code != 200:
                        continue
                    any_response = True
                    data = r.json()
                    best_confidence = max(best_confidence, float(data.get("confidence") or 0.0))
                    if data.get("abstained"):
                        reasons.append(f"{coll}: {data.get('reason') or 'abstained'}")
                    for c in data.get("citations", []) or []:
                        all_citations.append(Citation(
                            chunk_id=c["chunk_id"],
                            source_path=c["source_path"],
                            score=float(c.get("score") or 0.0),
                            snippet=c.get("snippet", ""),
                        ))
        except httpx.RequestError:
            any_response = False

        latency_ms = (time.perf_counter() - t0) * 1000.0

        if not any_response:
            return FactualityVerdict(
                available=False,
                abstain=True,
                confidence=0.0,
                reasons=["ragx unreachable at " + RAGX_URL],
                candidate=candidate_answer,
                latency_ms=latency_ms,
            )

        abstain = (not all_citations) or (len(reasons) == len(targets))
        return FactualityVerdict(
            available=True,
            abstain=abstain,
            confidence=best_confidence,
            citations=all_citations,
            reasons=reasons,
            candidate=candidate_answer,
            latency_ms=latency_ms,
        )

    @classmethod
    async def health(cls) -> bool:
        """True iff ragx /health responds 200."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(f"{RAGX_URL}/health")
                return r.status_code == 200
        except httpx.RequestError:
            return False
