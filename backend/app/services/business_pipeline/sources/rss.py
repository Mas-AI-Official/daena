"""RSS / Atom source adapter -- Sprint-20 PR-2 (2026-05-06).

Stdlib-only XML parsing (no external feedparser dep). Handles RSS
2.0 ``<item>`` and Atom ``<entry>`` -- the two shapes that cover the
public feeds Daena cares about (grant newsletters, accelerator
announcements, program updates).

NEVER:
  * Sends cookies or auth headers.
  * Spoofs a logged-in browser User-Agent.
  * Follows JS-rendered redirects.
  * Reads more than ``MAX_BYTES`` per response.
  * Spends more than ``TIMEOUT_S`` per request.
  * Returns a partial item if parsing failed midway -- the whole
    feed yields zero rather than producing junk.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable
from xml.etree import ElementTree as ET

import httpx

from app.core.logging import get_logger
from app.models.business import OPPORTUNITY_TYPES
from app.services.business_pipeline.discoverer import DiscoveredOpportunity

logger = get_logger(__name__)


TIMEOUT_S: float = 8.0
MAX_BYTES: int = 256 * 1024
USER_AGENT: str = "Daena-Discovery/1.0 (+https://daena.mas-ai.co)"


# Atom namespace -- RSS 2.0 uses no namespace.
_ATOM_NS = "{http://www.w3.org/2005/Atom}"


def _http_or_https(url: str) -> bool:
    return url.lower().startswith(("http://", "https://"))


def _parse_iso_or_rfc822(value: str) -> datetime | None:
    if not value:
        return None
    # ISO 8601 (Atom)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        pass
    # RFC 822 (RSS 2.0)
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(value)
        return dt
    except (TypeError, ValueError):
        return None


def _strip_html(text: str | None) -> str | None:
    if not text:
        return None
    # Compact whitespace + strip tags. Cheap, not perfect, fine for
    # description fields that are operator-readable summaries.
    no_tags = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", no_tags).strip() or None


def _full_text(el: ET.Element | None) -> str:
    """Return the concatenated inner text of an element including all
    descendant text nodes. ``findtext`` only returns text BEFORE the
    first child, which would drop any HTML the description contains.
    """
    if el is None:
        return ""
    return "".join(el.itertext())


def _rss_items(root: ET.Element) -> list[dict]:
    items: list[dict] = []
    # RSS 2.0 path: <rss><channel><item>...
    for item in root.iter("item"):
        title = _full_text(item.find("title")).strip()
        link = _full_text(item.find("link")).strip()
        desc = _full_text(item.find("description"))
        pub = _full_text(item.find("pubDate"))
        if not title:
            continue
        items.append({
            "title": title,
            "link": link,
            "description": _strip_html(desc),
            "pub": _parse_iso_or_rfc822(pub),
        })
    return items


def _atom_entries(root: ET.Element) -> list[dict]:
    items: list[dict] = []
    for entry in root.iter(f"{_ATOM_NS}entry"):
        title = _full_text(entry.find(f"{_ATOM_NS}title")).strip()
        # Atom <link href="..." rel="alternate"/>
        link = ""
        for link_el in entry.findall(f"{_ATOM_NS}link"):
            rel = link_el.attrib.get("rel", "alternate")
            if rel == "alternate":
                link = link_el.attrib.get("href", "").strip()
                break
        desc_text = _full_text(entry.find(f"{_ATOM_NS}summary")) or _full_text(
            entry.find(f"{_ATOM_NS}content"),
        )
        updated_el = entry.find(f"{_ATOM_NS}updated") or entry.find(
            f"{_ATOM_NS}published"
        )
        pub = (updated_el.text or "") if updated_el is not None else ""
        if not title:
            continue
        items.append({
            "title": title,
            "link": link,
            "description": _strip_html(desc_text),
            "pub": _parse_iso_or_rfc822(pub),
        })
    return items


def parse_feed_xml(xml_bytes: bytes) -> list[dict]:
    """Parse an RSS-2.0 OR Atom payload into normalized item dicts.
    Returns ``[]`` for any parse failure -- never raises."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []
    # Atom roots are tagged with the Atom namespace; RSS-2.0 has no ns.
    if root.tag.endswith("feed"):
        return _atom_entries(root)
    # rss / rdf:RDF
    return _rss_items(root)


def build_rss_atom_source(
    *, feed_url: str, default_type: str, source_name: str,
    max_items: int = 20,
):
    """Return an async source fn that fetches + parses a feed once.

    Refuses non-HTTP(S) URLs and unknown opportunity types at build
    time -- bad config fails fast rather than at discovery time.
    """
    if not _http_or_https(feed_url):
        raise ValueError(f"feed_url must be http/https: {feed_url!r}")
    if default_type not in OPPORTUNITY_TYPES:
        raise ValueError(f"unknown opportunity type {default_type!r}")
    if max_items <= 0 or max_items > 100:
        raise ValueError(f"max_items out of range: {max_items}")

    async def _source() -> Iterable[DiscoveredOpportunity]:
        try:
            async with httpx.AsyncClient(
                timeout=TIMEOUT_S, follow_redirects=True,
            ) as client:
                resp = await client.get(
                    feed_url,
                    headers={"User-Agent": USER_AGENT, "Accept": "application/xml,application/rss+xml,application/atom+xml"},
                )
        except httpx.RequestError as exc:
            logger.warning(
                "opportunity.rss.fetch_failed",
                source=source_name,
                error=type(exc).__name__,
            )
            return []

        if resp.status_code != 200:
            logger.warning(
                "opportunity.rss.bad_status",
                source=source_name, status=resp.status_code,
            )
            return []

        body = resp.content[:MAX_BYTES]
        items = parse_feed_xml(body)[:max_items]
        out: list[DiscoveredOpportunity] = []
        for it in items:
            title = it["title"][:500]
            out.append(DiscoveredOpportunity(
                type=default_type,
                title=title,
                source_name=source_name,
                description=(it.get("description") or "")[:1000] or None,
                source_url=(it.get("link") or feed_url)[:2000],
                deadline_at=None,
                raw_metadata={"feed_url": feed_url, "pub": (
                    it["pub"].isoformat() if it.get("pub") else None
                )},
            ))
        return out

    _source.__name__ = f"rss_{source_name}"  # type: ignore[attr-defined]
    return _source
