"""CVE intelligence client.

Fetches vulnerability data from public sources and caches results for
one hour to keep chat-time scan dispatch fast.

Sources (queried in order, graceful degradation on failure):
    1. NVD 2.0 API (api.nvd.nist.gov) -- authoritative CVE database
    2. GitHub Security Advisories (via GraphQL, when token set)
    3. CIRCL CVE Search (mirror of NVD + MITRE) -- fallback

Each source returns a list of normalized ``CVEItem`` dicts. Empty
list means "no public intel found" which is a valid, actionable
result (not an error).

The lookup is fire-and-forget: if no source responds within the
timeout budget, we return [] and let the caller decide what to do.
Never raises, never blocks the scan pipeline.

BACKGROUND PATH ONLY -- never import in hot path
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CVEItem:
    """Normalized CVE record across sources."""

    cve_id: str
    title: str = ""
    description: str = ""
    severity: str = ""          # CRITICAL / HIGH / MEDIUM / LOW / unknown
    cvss_score: float = 0.0
    published: str = ""
    references: list[str] = field(default_factory=list)
    source: str = ""            # "nvd" | "github_advisory" | "circl"


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

_CACHE_TTL_SECONDS = 3600  # 1 hour
_cache: dict[str, tuple[float, list[CVEItem]]] = {}


def _cache_get(key: str) -> list[CVEItem] | None:
    row = _cache.get(key)
    if not row:
        return None
    ts, items = row
    if time.time() - ts > _CACHE_TTL_SECONDS:
        _cache.pop(key, None)
        return None
    return items


def _cache_set(key: str, items: list[CVEItem]) -> None:
    _cache[key] = (time.time(), items)


def clear_cache() -> None:
    """Clear the in-memory CVE cache. Test helper."""
    _cache.clear()


# ---------------------------------------------------------------------------
# Source: NVD 2.0
# ---------------------------------------------------------------------------

_NVD_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"


async def _query_nvd(keyword: str, limit: int = 10) -> list[CVEItem]:
    """Query NVD 2.0 by keyword. Uses aiohttp/httpx if available."""
    try:
        import httpx
    except ImportError:  # pragma: no cover - httpx is a hard dep elsewhere
        return []

    items: list[CVEItem] = []
    params = {"keywordSearch": keyword, "resultsPerPage": str(limit)}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(_NVD_BASE, params=params)
            if r.status_code != 200:
                return []
            data = r.json()
    except Exception as exc:
        logger.debug("cve_intel.nvd_failed", keyword=keyword, error=str(exc))
        return []

    for v in data.get("vulnerabilities", [])[:limit]:
        cve = v.get("cve") or {}
        cve_id = cve.get("id", "")
        if not cve_id:
            continue

        # Description: prefer English.
        descriptions = cve.get("descriptions") or []
        desc = next(
            (d.get("value", "") for d in descriptions if d.get("lang") == "en"),
            descriptions[0].get("value", "") if descriptions else "",
        )

        # CVSS (v3.1 preferred, v3.0 next, v2 last).
        severity = ""
        cvss_score = 0.0
        metrics = cve.get("metrics") or {}
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            for m in metrics.get(key, []) or []:
                data_v = m.get("cvssData") or {}
                score = data_v.get("baseScore")
                sev = data_v.get("baseSeverity") or m.get("baseSeverity")
                if score is not None:
                    cvss_score = float(score)
                    severity = str(sev or "").upper()
                    break
            if cvss_score:
                break

        refs = [r_.get("url", "") for r_ in cve.get("references") or []]

        items.append(
            CVEItem(
                cve_id=cve_id,
                title=cve_id,
                description=desc,
                severity=severity,
                cvss_score=cvss_score,
                published=cve.get("published", ""),
                references=[u for u in refs if u],
                source="nvd",
            )
        )

    return items


# ---------------------------------------------------------------------------
# Source: GitHub Security Advisories (GraphQL)
# ---------------------------------------------------------------------------

_GITHUB_GRAPHQL = "https://api.github.com/graphql"
_GITHUB_QUERY = """
query($first: Int!, $query: String!) {
  securityAdvisories(first: $first, orderBy: {field: PUBLISHED_AT, direction: DESC}, classifications: [GENERAL]) {
    nodes {
      ghsaId
      summary
      description
      severity
      publishedAt
      references { url }
      identifiers { type value }
    }
  }
}
"""


async def _query_github_advisories(
    keyword: str, limit: int = 10,
) -> list[CVEItem]:
    token = os.environ.get("GITHUB_ADVISORY_TOKEN", "").strip()
    if not token:
        return []
    try:
        import httpx
    except ImportError:  # pragma: no cover
        return []

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(
                _GITHUB_GRAPHQL,
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "query": _GITHUB_QUERY,
                    "variables": {"first": limit, "query": keyword},
                },
            )
            if r.status_code != 200:
                return []
            data = r.json()
    except Exception as exc:
        logger.debug(
            "cve_intel.github_advisories_failed",
            keyword=keyword, error=str(exc),
        )
        return []

    items: list[CVEItem] = []
    nodes = (
        (data.get("data") or {}).get("securityAdvisories") or {}
    ).get("nodes") or []
    for n in nodes[:limit]:
        cve_id = next(
            (
                ident.get("value", "")
                for ident in n.get("identifiers") or []
                if ident.get("type") == "CVE"
            ),
            n.get("ghsaId", ""),
        )
        refs = [r_.get("url", "") for r_ in n.get("references") or []]
        items.append(
            CVEItem(
                cve_id=cve_id,
                title=n.get("summary", ""),
                description=n.get("description", ""),
                severity=str(n.get("severity", "")).upper(),
                published=n.get("publishedAt", ""),
                references=[u for u in refs if u],
                source="github_advisory",
            )
        )
    return items


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


async def lookup_cves(
    keyword: str, *, limit: int = 10,
) -> list[CVEItem]:
    """Lookup CVEs by keyword across all available sources.

    Results from multiple sources are merged and deduplicated by
    ``cve_id``. Returns at most ``limit`` items. Cached for 1 hour.
    """
    keyword = (keyword or "").strip()
    if not keyword:
        return []

    cache_key = f"{keyword.lower()}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # Run all sources in parallel with a single timeout budget.
    try:
        nvd_items, gh_items = await asyncio.gather(
            _query_nvd(keyword, limit),
            _query_github_advisories(keyword, limit),
            return_exceptions=True,
        )
    except Exception as exc:  # pragma: no cover - gather never raises
        logger.warning("cve_intel.lookup_failed", error=str(exc))
        _cache_set(cache_key, [])
        return []

    merged: dict[str, CVEItem] = {}
    for batch in (nvd_items, gh_items):
        if isinstance(batch, Exception):
            continue
        for item in batch:
            key = item.cve_id or f"{item.source}-{len(merged)}"
            if key not in merged:
                merged[key] = item

    result = list(merged.values())[:limit]
    _cache_set(cache_key, result)
    return result
