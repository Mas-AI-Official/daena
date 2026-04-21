"""External intelligence fan-out for security scans.

Single entrypoint that queries N external-to-the-LLM sources in
parallel and returns a normalized ``IntelligenceBundle``. This is
where Daena "thinks outside the LLM": each source is a primitive the
LLM could not have seen in training (live CVE DBs, codebase graph of
the operator's own repos, prior engagement patterns from NBMF,
knowledge graph paths), fused into a single evidence block the
Council / Quintessence synthesizer then reasons over.

Per-channel failure is isolated: a missing network source does not
break the bundle; partial results surface with a ``status`` per
channel so downstream code can decide whether to proceed.

Channels (all optional, any combination fires):
    * web_search        -- resource_finder.search_web (DDG-distilled)
    * cve_intel         -- NVD + GitHub Advisories
    * codebase_memory   -- gitnexus / codebase-memory MCP (when target
                           matches an indexed project)
    * knowledge_graph   -- in-process knowledge graph (Daena memory)
    * knowledge_hunter  -- deep targeted lookup
    * nbmf_t3           -- cross-engagement patterns from institutional
                           memory (when a memory service is available)

BACKGROUND PATH ONLY -- never import in hot path
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ChannelResult:
    """Result for a single intel channel."""

    name: str
    status: str = "ok"          # "ok" | "empty" | "error" | "skipped"
    payload: Any = None
    error: str = ""


@dataclass
class IntelligenceBundle:
    """Aggregated intel from all enabled channels.

    Consumed by CognitiveScanEngine ORIENT phase and by Council
    synthesis as evidence block (not just a prompt).
    """

    target: str
    phase: str
    web_insights: list[dict[str, Any]] = field(default_factory=list)
    cves: list[dict[str, Any]] = field(default_factory=list)
    source_matches: list[dict[str, Any]] = field(default_factory=list)
    historical_patterns: list[dict[str, Any]] = field(default_factory=list)
    graph_paths: list[dict[str, Any]] = field(default_factory=list)
    channel_results: list[ChannelResult] = field(default_factory=list)

    @property
    def confidence_weighted_summary(self) -> str:
        """Compact human-readable summary, used in Council evidence."""
        lines: list[str] = []
        if self.cves:
            sev_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
            ordered = sorted(
                self.cves,
                key=lambda c: sev_order.get(str(c.get("severity", "")).upper(), 99),
            )
            top = ordered[:5]
            cve_str = ", ".join(
                f"{c.get('cve_id', '?')}({c.get('severity','?')})"
                for c in top
            )
            lines.append(f"Known CVEs: {cve_str}")
        if self.web_insights:
            lines.append(f"Web intel: {len(self.web_insights)} signal(s)")
        if self.source_matches:
            lines.append(f"Source-code matches: {len(self.source_matches)}")
        if self.historical_patterns:
            lines.append(f"Prior patterns: {len(self.historical_patterns)}")
        if self.graph_paths:
            lines.append(f"KG paths: {len(self.graph_paths)}")
        if not lines:
            return f"No external intel found for {self.target}"
        return "; ".join(lines)


# ---------------------------------------------------------------------------
# Channel implementations (each returns a ChannelResult)
# ---------------------------------------------------------------------------


async def _channel_web(target: str, phase: str) -> ChannelResult:
    try:
        from app.services.cognition.resource_finder import search_web
    except Exception as exc:  # pragma: no cover - import error
        return ChannelResult("web_search", status="error", error=str(exc))

    query = f"{target} security vulnerabilities {phase}".strip()
    try:
        result = search_web(query) if hasattr(search_web, "__call__") else None
        if asyncio.iscoroutine(result):
            result = await result  # type: ignore[assignment]
        if not result:
            return ChannelResult("web_search", status="empty", payload=[])
        return ChannelResult(
            "web_search",
            status="ok",
            payload=result if isinstance(result, list) else [result],
        )
    except Exception as exc:
        return ChannelResult("web_search", status="error", error=str(exc))


async def _channel_cve(target: str) -> ChannelResult:
    from app.services.security.cve_intel import lookup_cves

    try:
        items = await lookup_cves(target, limit=10)
    except Exception as exc:
        return ChannelResult("cve_intel", status="error", error=str(exc))

    if not items:
        return ChannelResult("cve_intel", status="empty", payload=[])

    payload = [
        {
            "cve_id": i.cve_id,
            "title": i.title,
            "severity": i.severity,
            "cvss_score": i.cvss_score,
            "source": i.source,
            "published": i.published,
            "references": i.references[:3],
        }
        for i in items
    ]
    return ChannelResult("cve_intel", status="ok", payload=payload)


async def _channel_codebase_memory(target: str) -> ChannelResult:
    """Call the codebase-memory MCP if the target looks like a repo.

    When the target is a github/gitlab URL or a bare org/repo path,
    delegate to the MCPAgent-wrapped codebase-memory.search_code.
    Otherwise return skipped so callers know no match was possible.
    """
    looks_like_repo = (
        "github.com/" in target.lower()
        or "gitlab.com/" in target.lower()
        or target.count("/") == 1  # "org/repo"
    )
    if not looks_like_repo:
        return ChannelResult("codebase_memory", status="skipped")

    try:
        from app.services.daenabot.mcp_agent import MCPAgent

        agent = MCPAgent()
        # Best-effort: MCPAgent.call signature varies across revisions.
        # We use the search_code tool name defined by the codebase-memory
        # MCP server. Any failure is absorbed into "error".
        result = await agent.call_tool(  # type: ignore[attr-defined]
            tool="search_code",
            params={"query": target, "project": "auto"},
        )
        return ChannelResult("codebase_memory", status="ok", payload=result)
    except Exception as exc:
        return ChannelResult("codebase_memory", status="error", error=str(exc))


async def _channel_knowledge_graph(target: str) -> ChannelResult:
    """In-process Daena knowledge graph."""
    try:
        from app.services.cognition.knowledge_graph import KnowledgeGraph
    except Exception as exc:  # pragma: no cover
        return ChannelResult("knowledge_graph", status="error", error=str(exc))

    try:
        kg = KnowledgeGraph()
        query_fn = getattr(kg, "query", None) or getattr(kg, "knowledge_query", None)
        if query_fn is None:
            return ChannelResult("knowledge_graph", status="skipped")
        result = query_fn(target) if callable(query_fn) else None
        if asyncio.iscoroutine(result):
            result = await result  # type: ignore[assignment]
        if not result:
            return ChannelResult("knowledge_graph", status="empty", payload=[])
        return ChannelResult(
            "knowledge_graph",
            status="ok",
            payload=result if isinstance(result, list) else [result],
        )
    except Exception as exc:
        return ChannelResult("knowledge_graph", status="error", error=str(exc))


async def _channel_knowledge_hunter(target: str) -> ChannelResult:
    try:
        from app.services.cognition.knowledge_hunter import KnowledgeHunter
    except Exception as exc:  # pragma: no cover
        return ChannelResult("knowledge_hunter", status="error", error=str(exc))

    try:
        hunter = KnowledgeHunter()
        hunt_fn = getattr(hunter, "hunt", None)
        if hunt_fn is None:
            return ChannelResult("knowledge_hunter", status="skipped")
        result = hunt_fn(target) if callable(hunt_fn) else None
        if asyncio.iscoroutine(result):
            result = await result  # type: ignore[assignment]
        if not result:
            return ChannelResult(
                "knowledge_hunter", status="empty", payload=[]
            )
        return ChannelResult(
            "knowledge_hunter",
            status="ok",
            payload=result if isinstance(result, list) else [result],
        )
    except Exception as exc:
        return ChannelResult("knowledge_hunter", status="error", error=str(exc))


async def _channel_nbmf_t3(target: str, phase: str) -> ChannelResult:
    """Pull cross-engagement patterns from NBMF T3 (institutional).

    Best-effort: the memory service API surface varies. If the call
    shape does not match, return ``skipped`` so the bundle still
    reports the channel status.
    """
    try:
        # Try the most common service names across this codebase.
        try:
            from app.services.memory_service import MemoryService  # type: ignore
        except ImportError:
            return ChannelResult("nbmf_t3", status="skipped")
    except Exception as exc:  # pragma: no cover
        return ChannelResult("nbmf_t3", status="error", error=str(exc))

    try:
        service = MemoryService()
        search_fn = getattr(service, "search", None)
        if search_fn is None:
            return ChannelResult("nbmf_t3", status="skipped")
        result = search_fn(  # type: ignore[misc]
            query=f"{target} {phase}",
            tier="T3",
            limit=10,
        )
        if asyncio.iscoroutine(result):
            result = await result  # type: ignore[assignment]
        if not result:
            return ChannelResult("nbmf_t3", status="empty", payload=[])
        return ChannelResult(
            "nbmf_t3",
            status="ok",
            payload=result if isinstance(result, list) else [result],
        )
    except Exception as exc:
        return ChannelResult("nbmf_t3", status="error", error=str(exc))


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


async def fan_out_intelligence(
    target: str,
    phase: str = "orient",
    *,
    timeout_seconds: float = 6.0,
) -> IntelligenceBundle:
    """Query all external-intel channels in parallel.

    Returns an ``IntelligenceBundle`` with per-channel payloads + a
    ``channel_results`` trace so callers can see which channels
    contributed (ok), which were dormant (empty / skipped), and which
    errored (error with reason).
    """
    target = (target or "").strip()
    bundle = IntelligenceBundle(target=target, phase=phase)

    if not target:
        return bundle

    tasks = [
        _channel_web(target, phase),
        _channel_cve(target),
        _channel_codebase_memory(target),
        _channel_knowledge_graph(target),
        _channel_knowledge_hunter(target),
        _channel_nbmf_t3(target, phase),
    ]

    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "intel_fanout.timeout",
            target=target, phase=phase, timeout_s=timeout_seconds,
        )
        return bundle

    for r in results:
        if isinstance(r, Exception):
            bundle.channel_results.append(
                ChannelResult("unknown", status="error", error=str(r))
            )
            continue
        bundle.channel_results.append(r)

        if r.status != "ok" or not r.payload:
            continue

        if r.name == "web_search":
            payload = r.payload if isinstance(r.payload, list) else [r.payload]
            bundle.web_insights = [
                p if isinstance(p, dict) else {"summary": str(p)}
                for p in payload
            ]
        elif r.name == "cve_intel":
            bundle.cves = r.payload if isinstance(r.payload, list) else []
        elif r.name == "codebase_memory":
            payload = r.payload if isinstance(r.payload, list) else [r.payload]
            bundle.source_matches = [
                p if isinstance(p, dict) else {"summary": str(p)}
                for p in payload
            ]
        elif r.name == "nbmf_t3":
            payload = r.payload if isinstance(r.payload, list) else [r.payload]
            bundle.historical_patterns = [
                p if isinstance(p, dict) else {"summary": str(p)}
                for p in payload
            ]
        elif r.name in ("knowledge_graph", "knowledge_hunter"):
            payload = r.payload if isinstance(r.payload, list) else [r.payload]
            bundle.graph_paths.extend(
                p if isinstance(p, dict) else {"summary": str(p)}
                for p in payload
            )

    logger.info(
        "intel_fanout.complete",
        target=target,
        phase=phase,
        ok=sum(1 for c in bundle.channel_results if c.status == "ok"),
        empty=sum(1 for c in bundle.channel_results if c.status == "empty"),
        errors=sum(1 for c in bundle.channel_results if c.status == "error"),
        skipped=sum(1 for c in bundle.channel_results if c.status == "skipped"),
    )

    return bundle
