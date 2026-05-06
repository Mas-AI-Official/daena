"""URL-list source adapter -- Sprint-20 PR-2 (2026-05-06).

For accelerator / grant program homepages that don't publish an RSS
feed. Fetches a single page (HEAD-followed-GET, capped body), pulls
the document title and meta description, emits ONE
DiscoveredOpportunity per registered URL.

Strict rules:
  * One URL = one source registration = one opportunity per cycle.
  * No link-following. No iframe parsing. No JS execution.
  * Capped body, capped timeout, no auth headers, no cookies.
  * Empty / parse-failed pages return zero opportunities.
"""

from __future__ import annotations

import re
from html import unescape
from typing import Iterable

import httpx

from app.core.logging import get_logger
from app.models.business import OPPORTUNITY_TYPES
from app.services.business_pipeline.discoverer import DiscoveredOpportunity

logger = get_logger(__name__)


TIMEOUT_S: float = 8.0
MAX_BYTES: int = 256 * 1024
USER_AGENT: str = "Daena-Discovery/1.0 (+https://daena.mas-ai.co)"


def _http_or_https(url: str) -> bool:
    return url.lower().startswith(("http://", "https://"))


_TITLE_RE = re.compile(
    r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL,
)
_META_DESC_RE = re.compile(
    r"<meta[^>]+(?:name|property)=[\"']"
    r"(?:description|og:description)[\"'][^>]*"
    r"content=[\"']([^\"']{1,1000})[\"']",
    re.IGNORECASE,
)


def parse_page_html(html: str) -> tuple[str | None, str | None]:
    """Return (title, description) extracted from raw HTML.

    Tolerant: regex-based, case-insensitive. Empty / unparseable HTML
    yields (None, None). NEVER raises.
    """
    if not html:
        return (None, None)
    title_m = _TITLE_RE.search(html)
    title = unescape((title_m.group(1) or "").strip()) if title_m else None
    title = re.sub(r"\s+", " ", title).strip() if title else None
    title = title or None

    desc_m = _META_DESC_RE.search(html)
    description = unescape((desc_m.group(1) or "").strip()) if desc_m else None
    description = (
        re.sub(r"\s+", " ", description).strip() if description else None
    )
    description = description or None

    return (title, description)


def build_url_list_source(
    *, page_url: str, default_type: str, source_name: str,
):
    """Return an async source fn for a single public page URL."""
    if not _http_or_https(page_url):
        raise ValueError(f"page_url must be http/https: {page_url!r}")
    if default_type not in OPPORTUNITY_TYPES:
        raise ValueError(f"unknown opportunity type {default_type!r}")

    async def _source() -> Iterable[DiscoveredOpportunity]:
        try:
            async with httpx.AsyncClient(
                timeout=TIMEOUT_S, follow_redirects=True,
            ) as client:
                resp = await client.get(
                    page_url,
                    headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
                )
        except httpx.RequestError as exc:
            logger.warning(
                "opportunity.urlpage.fetch_failed",
                source=source_name, error=type(exc).__name__,
            )
            return []

        if resp.status_code != 200:
            logger.warning(
                "opportunity.urlpage.bad_status",
                source=source_name, status=resp.status_code,
            )
            return []

        body = resp.content[:MAX_BYTES]
        try:
            html = body.decode("utf-8", errors="replace")
        except UnicodeDecodeError:
            html = body.decode("latin-1", errors="replace")
        title, description = parse_page_html(html)
        if not title:
            return []
        return [DiscoveredOpportunity(
            type=default_type,
            title=title[:500],
            source_name=source_name,
            description=description[:1000] if description else None,
            source_url=page_url[:2000],
            raw_metadata={"page_url": page_url},
        )]

    _source.__name__ = f"url_{source_name}"  # type: ignore[attr-defined]
    return _source
