"""Domain best-practice research for Soul Maker.

Before the 3-pass refinement runs, we optionally fetch current best
practices, archetypes, and expert patterns for a given department
domain. This is the piece that keeps souls current as the AI/ops
landscape moves -- a soul drafted in April 2026 should know about
techniques that emerged in July 2026.

The default research source is Daena's existing intel_fanout (web
search + NBMF + knowledge graph), which is governance-aware and
respects per-department tool scoping. Falls back to a no-op stub when
the fanout surface is unavailable (e.g. in unit tests), so the
refinement path always progresses.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


# Department -> targeted research query. These queries are designed to
# surface DOMAIN patterns (how experts in that field think) rather than
# vendor-specific tool docs -- souls are personas, not cheatsheets.
_DOMAIN_RESEARCH_QUERIES: dict[str, str] = {
    "engineering": (
        "current best practices for AI-assisted software engineering "
        "workflows code review impact analysis test-first"
    ),
    "product": (
        "modern product management frameworks jobs-to-be-done "
        "continuous discovery product diamond 2026"
    ),
    "marketing": (
        "positioning copy frameworks April Dunford SaaS GTM "
        "distribution-first marketing 2026"
    ),
    "sales": (
        "MEDDPICC qualification framework SaaS outbound personalization "
        "tactical empathy sales 2026"
    ),
    "finance": (
        "startup finance runway calculation unit economics default-alive "
        "scenario modeling 2026"
    ),
    "operations": (
        "operating system for startups async processes DRI theory of "
        "constraints automation 2026"
    ),
    "research": (
        "research methodology source evaluation primary sources AI "
        "literature review 2026"
    ),
    "legal_compliance": (
        "AI product legal review IP contract clauses privacy GDPR "
        "PIPEDA CCPA 2026"
    ),
    "skill_governance": (
        "knowledge management skill tier systems institutional memory "
        "LLM skill library 2026"
    ),
    "security_operations": (
        "security operations triage CVE prioritization exploitability "
        "whitebox blackbox correlation zero-FP 2026"
    ),
}


async def fetch_domain_best_practices(
    department_slug: str,
    *,
    max_snippets: int = 8,
) -> list[dict[str, Any]]:
    """Return a list of evidence snippets for the domain.

    Each snippet: ``{"source": str, "title": str, "text": str, "date": str}``.
    Empty list on failure -- refinement continues without external signal.

    Source priority:
    1. ``intel_fanout.run_multi_source`` if importable (real production path).
    2. Fallback: empty list, logged as degraded.
    """
    query = _DOMAIN_RESEARCH_QUERIES.get(department_slug)
    if not query:
        logger.warning("soul_maker.research.unknown_department", slug=department_slug)
        return []

    # Try the real intel fanout first. This keeps the research pass
    # governance-aware (it respects tenant isolation and the Shield).
    try:
        from app.services.security.intel_fanout import run_multi_source  # type: ignore

        results = await run_multi_source(
            query=query,
            sources=["web_search", "codebase_memory", "nbmf_t3"],
            max_per_source=max(2, max_snippets // 3),
        )
        # Flatten + trim. run_multi_source returns a dict of source-keyed
        # lists; we normalize into a flat list so refinement only sees
        # the interesting text + provenance.
        flat: list[dict[str, Any]] = []
        if isinstance(results, dict):
            for source, items in results.items():
                if not isinstance(items, list):
                    continue
                for item in items[:max_snippets]:
                    if not isinstance(item, dict):
                        continue
                    flat.append({
                        "source": source,
                        "title": str(item.get("title") or item.get("url") or "")[:200],
                        "text": str(item.get("text") or item.get("content") or item.get("snippet") or "")[:1200],
                        "date": str(item.get("date") or item.get("published_at") or ""),
                    })
        logger.info(
            "soul_maker.research.fanout",
            slug=department_slug,
            snippets=len(flat),
        )
        return flat[:max_snippets]
    except ImportError:
        logger.info("soul_maker.research.fanout_unavailable", slug=department_slug)
    except Exception as exc:
        logger.warning(
            "soul_maker.research.fanout_failed",
            slug=department_slug,
            error=str(exc),
        )

    # Soft-fail path: return empty evidence. Refinement still runs using
    # just the existing soul text + LLM general knowledge.
    return []
