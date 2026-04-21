"""Whitebox-to-blackbox correlator.

When a scan target maps to a repository Daena has indexed (via the
codebase-memory MCP), read the source first, then attack the running
app, correlate each black-box finding back to a source file + line.
Inspired by Shannon's white-box + black-box hybrid that scored
96.15% on XBOW.

Returns ``SourceCorrelation`` records that downstream report_generator
can use to populate ``SecurityFinding.fix_code`` and reasoning_chain.

Graceful degradation: if no repo match, if codebase-memory is not
reachable, or if the finding lacks a location, returns None and the
report degrades to blackbox-only.

BACKGROUND PATH ONLY -- never import in hot path
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SourceCorrelation:
    """Mapping of a black-box finding to a source location."""

    finding_id: str
    source_file: str
    source_line: int = 0
    symbol_name: str = ""
    fix_suggestion: str = ""
    confidence: float = 0.0      # 0.0 - 1.0
    project: str = ""


async def correlate_finding_to_source(
    finding: dict[str, Any],
    target_project: str | None = None,
) -> SourceCorrelation | None:
    """Map a black-box finding to a source code location.

    Strategy:
        1. Extract identifying signal from the finding (endpoint path,
           parameter name, vulnerability class).
        2. Query codebase-memory search_code for the signal.
        3. If a hit maps to a project file, return a SourceCorrelation
           with the file, line, and a heuristic fix suggestion.
        4. Otherwise return None (report stays blackbox-only).

    Args:
        finding: A raw finding dict with at least ``id`` and one of
                 ``location`` / ``endpoint`` / ``http_response.url``.
        target_project: Optional project hint for codebase-memory scope.

    Returns:
        SourceCorrelation on match, None otherwise.
    """
    finding_id = str(finding.get("id", ""))
    if not finding_id:
        return None

    # Build a search query from the most specific signal available.
    query_parts: list[str] = []
    loc = finding.get("location")
    if isinstance(loc, str) and loc:
        query_parts.append(loc.split(":", 1)[0])
    endpoint = finding.get("endpoint") or finding.get("path")
    if isinstance(endpoint, str) and endpoint:
        query_parts.append(endpoint)
    if finding.get("title"):
        query_parts.append(str(finding["title"]))

    query = " ".join(query_parts).strip()
    if not query:
        return None

    try:
        from app.services.daenabot.mcp_agent import MCPAgent
    except Exception as exc:  # pragma: no cover - dep missing
        logger.debug("source_correlator.mcp_unavailable", error=str(exc))
        return None

    try:
        agent = MCPAgent()
        params = {"query": query, "limit": 1}
        if target_project:
            params["project"] = target_project
        hit = await agent.call_tool(  # type: ignore[attr-defined]
            tool="search_code", params=params,
        )
    except Exception as exc:
        logger.debug(
            "source_correlator.search_failed",
            finding_id=finding_id, error=str(exc),
        )
        return None

    if not hit:
        return None

    # Normalize the hit into SourceCorrelation. search_code response
    # shapes vary across gitnexus versions; we defensively pull common
    # fields without assuming a rigid schema.
    if isinstance(hit, list) and hit:
        hit = hit[0]
    if not isinstance(hit, dict):
        return None

    source_file = str(
        hit.get("file") or hit.get("path") or hit.get("source_file") or ""
    )
    if not source_file:
        return None

    try:
        line = int(hit.get("line") or hit.get("line_number") or 0)
    except (TypeError, ValueError):
        line = 0

    symbol = str(hit.get("symbol") or hit.get("name") or "")
    confidence = float(hit.get("confidence") or 0.6)

    fix = _heuristic_fix_suggestion(finding)

    return SourceCorrelation(
        finding_id=finding_id,
        source_file=source_file,
        source_line=line,
        symbol_name=symbol,
        fix_suggestion=fix,
        confidence=confidence,
        project=target_project or str(hit.get("project", "")),
    )


async def correlate_all(
    findings: list[dict[str, Any]],
    target_project: str | None = None,
) -> list[SourceCorrelation]:
    """Correlate a batch of findings. Returns only non-None results."""
    import asyncio

    tasks = [
        correlate_finding_to_source(f, target_project=target_project)
        for f in findings
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out: list[SourceCorrelation] = []
    for r in results:
        if isinstance(r, Exception):
            continue
        if r is not None:
            out.append(r)
    return out


def _heuristic_fix_suggestion(finding: dict[str, Any]) -> str:
    """Generate a concise fix suggestion from finding class.

    Keeps the suggestion small: downstream Operator-tier reports
    consume this and the LLM expands it. Without finding-class
    specificity, we fall back to a generic "add input validation".
    """
    title = str(finding.get("title", "")).lower()
    if "sql" in title or "injection" in title:
        return "Use parameterized queries or an ORM query builder. Never concatenate user input into SQL."
    if "xss" in title or "cross-site" in title:
        return "Escape or sanitize user-controlled output. Apply Content-Security-Policy."
    if "csrf" in title:
        return "Add CSRF token middleware or use SameSite=strict cookies."
    if "ssrf" in title:
        return "Validate the target host against an allow-list; reject private IP ranges."
    if "idor" in title or "authorization" in title:
        return "Enforce per-object authorization checks in the handler before returning data."
    if "debug" in title:
        return "Set DEBUG=False in production config; gate via env var."
    if "hardcoded" in title or "secret" in title or "credential" in title:
        return "Move the secret to a vault or environment variable; rotate the exposed value."
    if "header" in title or "disclosure" in title:
        return "Strip or generalize verbose response headers in production."
    return "Validate and sanitize all user-controlled input; apply least-privilege by default."
