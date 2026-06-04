"""Bridge to the universal ragx service at http://127.0.0.1:8100.

Used by chat_orchestrator Stage 6.55 to inject grounded citations from the
operator's universal RAG (Daena docs, shared memory, conversation history,
wiki, agents-skills, etc.) into the system prompt alongside Stage 6.5
skill retrieval.

Architecture: this is a thin async HTTP client. ragx owns the storage
(ChromaDB + BM25 + entity graph) and the retrieval pipeline (rerank, MMR,
graph boost). Daena treats it as a black box and consumes the citations.

Fails OPEN: if ragx is unreachable, this returns an empty result and the
orchestrator continues without ragx evidence. Never raises into the chat
pipeline. Per Daena ADR-001: every failure is visible in logs, never
silently swallowed beyond the silent-skip pattern that Stage 6.5 uses.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

RAGX_URL = "http://127.0.0.1:8100"

# Default collections to query in parallel. Tuned for "what is the operator's
# current intent" coverage without flooding the prompt: 1 Daena docs, 1 wiki,
# 1 shared-memory (which now contains conversation summaries too).
DEFAULT_COLLECTIONS: tuple[str, ...] = ("daena-docs", "wiki", "shared-memory")

# Per-query budget. Keep small so the prompt stays focused; rerank already
# orders by relevance.
DEFAULT_K = 4

# Soft cap on time spent. Stage 6.55 cannot delay the user-visible response.
DEFAULT_TIMEOUT_S = 6.0


@dataclass(frozen=True, slots=True)
class RagxCitation:
    """One supporting chunk from ragx."""

    chunk_id: str
    source_path: str
    score: float
    snippet: str
    collection: str


@dataclass(frozen=True, slots=True)
class RagxResult:
    """Aggregated retrieval result across collections."""

    citations: list[RagxCitation] = field(default_factory=list)
    abstained_collections: list[str] = field(default_factory=list)
    elapsed_ms: float = 0.0
    available: bool = True


async def _query_one(
    client: httpx.AsyncClient,
    collection: str,
    query: str,
    k: int,
) -> tuple[str, dict[str, Any] | None]:
    """Hit one collection. Returns (collection, payload) or (collection, None)
    on failure. Uses quick=True so CRAG and NLI are skipped (Stage 6.55 only
    needs citations, not generation)."""
    try:
        r = await client.post(
            f"{RAGX_URL}/query",
            json={
                "collection": collection,
                "q": query,
                "k": k,
                "generate": False,
                "quick": True,
            },
        )
        if r.status_code != 200:
            return collection, None
        return collection, r.json()
    except httpx.RequestError:
        return collection, None
    except (ValueError, KeyError):
        return collection, None


async def query_ragx(
    query: str,
    collections: tuple[str, ...] | list[str] | None = None,
    k: int = DEFAULT_K,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> RagxResult:
    """Query the universal ragx service across one or more collections in
    parallel. Returns aggregated citations.

    The caller (chat_orchestrator) should treat empty results as a soft
    signal: ragx had nothing useful, or the service is down. Either way,
    the chat pipeline continues.
    """
    import time

    targets = list(collections) if collections else list(DEFAULT_COLLECTIONS)
    if not targets or not query.strip():
        return RagxResult(available=False)

    started = time.perf_counter()
    citations: list[RagxCitation] = []
    abstained: list[str] = []
    any_response = False

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            tasks = [_query_one(client, c, query, k) for c in targets]
            results = await asyncio.gather(*tasks, return_exceptions=False)
    except httpx.RequestError:
        return RagxResult(available=False,
                          elapsed_ms=(time.perf_counter() - started) * 1000.0)

    for collection, payload in results:
        if payload is None:
            continue
        any_response = True
        if payload.get("abstained"):
            abstained.append(collection)
            continue
        for c in payload.get("citations", []) or []:
            citations.append(RagxCitation(
                chunk_id=c.get("chunk_id", ""),
                source_path=c.get("source_path", ""),
                score=float(c.get("score") or 0.0),
                snippet=c.get("snippet", ""),
                collection=collection,
            ))

    # Sort by rerank score descending so the highest-confidence chunks land
    # at the top of the system prompt where attention concentrates.
    citations.sort(key=lambda c: -c.score)

    return RagxResult(
        citations=citations,
        abstained_collections=abstained,
        elapsed_ms=(time.perf_counter() - started) * 1000.0,
        available=any_response,
    )


def format_ragx_evidence_block(result: RagxResult, max_citations: int = 8) -> str:
    """Render citations as a compact evidence block for the system prompt.

    Mirrors the shape of `format_evidence_block` from skill_refinery so the
    LLM sees a consistent structure. Returns empty string if no citations
    (caller checks for empty and skips append).
    """
    if not result.citations:
        return ""
    top = result.citations[:max_citations]
    lines: list[str] = [
        "",
        "## Universal RAG citations (mcp__ragx)",
        "Use these grounded sources when the user question touches indexed knowledge.",
        "",
    ]
    for c in top:
        path_short = c.source_path.replace("\\", "/").rsplit("/", 1)[-1]
        snip = c.snippet.replace("\n", " ").strip()
        if len(snip) > 200:
            snip = snip[:197] + "..."
        lines.append(
            f"- [{c.collection}] {path_short} (score {c.score:.2f}, "
            f"chunk_id {c.chunk_id[:10]}): {snip}"
        )
    return "\n".join(lines) + "\n"
