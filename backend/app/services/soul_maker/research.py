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
    1. ``intel_fanout.fan_out_intelligence`` if importable (real production
       path -- governance-aware, tenant-isolated, Shield-respecting).
    2. Fallback: empty list, logged as degraded.
    """
    query = _DOMAIN_RESEARCH_QUERIES.get(department_slug)
    if not query:
        logger.warning("soul_maker.research.unknown_department", slug=department_slug)
        return []

    # Try the real intel fanout first. This keeps the research pass
    # governance-aware (it respects tenant isolation and the Shield).
    # ``fan_out_intelligence`` runs the 6-channel background fan-out and
    # returns an ``IntelligenceBundle``; we flatten its dict-bearing channels
    # into the flat snippet shape refinement expects.
    try:
        from app.services.security.intel_fanout import fan_out_intelligence

        bundle = await fan_out_intelligence(query, phase="orient")
        # Map each bundle channel back to a source-tagged snippet. Items are
        # already normalized to dicts by the fan-out; we only trim + provenance.
        channel_map = (
            ("web_search", bundle.web_insights),
            ("codebase_memory", bundle.source_matches),
            ("nbmf_t3", bundle.historical_patterns),
            ("knowledge_graph", bundle.graph_paths),
        )
        flat: list[dict[str, Any]] = []
        for source, items in channel_map:
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                flat.append({
                    "source": source,
                    "title": str(item.get("title") or item.get("url") or item.get("summary") or "")[:200],
                    "text": str(item.get("text") or item.get("content") or item.get("snippet") or item.get("summary") or "")[:1200],
                    "date": str(item.get("date") or item.get("published_at") or ""),
                })
        logger.info(
            "soul_maker.research.fanout",
            slug=department_slug,
            snippets=len(flat),
            channels_ok=sum(1 for c in bundle.channel_results if c.status == "ok"),
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
