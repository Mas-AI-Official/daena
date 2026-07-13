"""Public opportunity source adapters -- Sprint-20 PR-2 (2026-05-06).

Hard rules these adapters MUST honor (verified by tests):

  * HTTP/HTTPS public URLs only. No login walls, no cookies, no auth
    headers, no User-Agent strings that pretend to be a logged-in
    browser.
  * Per-source timeout (default 8s) and per-source response size cap
    (256 KiB) so a slow / hostile feed can never block discovery.
  * Per-source result cap (default 20) so a noisy feed cannot dominate
    the top-N selection.
  * Source failures are SILENT to the orchestrator: an exception or
    bad payload yields zero opportunities, never aborts discovery.
  * Every emitted opportunity carries ``source_url`` AND
    ``source_name`` so the operator can verify the evidence.

Configuration is read from ``backend/.opportunity_sources.json``
(gitignored). The file declares lists of feeds and URLs the operator
trusts. If the file is missing, no public adapter registers and the
manual_seed source remains the only fallback.

Codex-aligned cuts (2026-05-06): HN public API was considered and
demoted -- noisy signal for a small surface. RSS + URL-list cover the
real wins (program announcements, accelerator blogs, grant
newsletters) without scraping or login.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.services.business_pipeline.discoverer import (
    register_source,
    unregister_source,
)
from app.services.business_pipeline.sources.rss import (
    build_rss_atom_source,
)
from app.services.business_pipeline.sources.url_list import (
    build_url_list_source,
)
from app.services.business_pipeline.sources.worldsignal_drop import (
    build_worldsignal_drop_source,
)

logger = get_logger(__name__)


_CONFIG_FILE = Path(__file__).resolve().parents[4] / ".opportunity_sources.json"


def _safe_load_config() -> dict[str, Any]:
    """Read the gitignored config file. Missing / malformed files
    return an empty dict -- discovery still runs with manual_seed."""
    if not _CONFIG_FILE.exists():
        return {}
    try:
        raw = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("opportunity.sources.config_read_failed", error=str(exc))
        return {}
    return raw if isinstance(raw, dict) else {}


def register_public_sources_from_config() -> list[str]:
    """Register adapters defined in ``.opportunity_sources.json``.

    Returns the list of source names registered. Idempotent: existing
    sources with the same name are unregistered first.

    Config shape (all keys optional)::

        {
          "rss_feeds": [
            {"url": "https://...", "type": "grant",
             "source_name": "X grants RSS", "max_items": 20}
          ],
          "url_pages": [
            {"url": "https://...", "type": "accelerator",
             "source_name": "Y accelerator"}
          ],
          "worldsignal_drops": [
            {"path": "var/worldsignal/opportunity_drop.json",
             "type": "partnership", "source_name": "WorldSignal drop",
             "max_items": 20}
          ]
        }
    """
    cfg = _safe_load_config()
    registered: list[str] = []

    for feed in cfg.get("rss_feeds", []) or []:
        if not isinstance(feed, dict):
            continue
        name = str(feed.get("source_name") or "").strip()
        url = str(feed.get("url") or "").strip()
        otype = str(feed.get("type") or "").strip()
        if not name or not url or not otype:
            continue
        max_items = int(feed.get("max_items") or 20)
        try:
            unregister_source(name)
            register_source(name, build_rss_atom_source(
                feed_url=url, default_type=otype,
                source_name=name, max_items=max_items,
            ))
            registered.append(name)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "opportunity.sources.register_rss_failed",
                source=name, error=str(exc),
            )

    for page in cfg.get("url_pages", []) or []:
        if not isinstance(page, dict):
            continue
        name = str(page.get("source_name") or "").strip()
        url = str(page.get("url") or "").strip()
        otype = str(page.get("type") or "").strip()
        if not name or not url or not otype:
            continue
        try:
            unregister_source(name)
            register_source(name, build_url_list_source(
                page_url=url, default_type=otype, source_name=name,
            ))
            registered.append(name)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "opportunity.sources.register_url_failed",
                source=name, error=str(exc),
            )

    # WorldSignal drops -- NEVER-7 boundary. WorldSignal writes a local
    # JSON file; Daena reads it via adapter only. No DB / queue / runtime
    # link to the WorldSignal process.
    for drop in cfg.get("worldsignal_drops", []) or []:
        if not isinstance(drop, dict):
            continue
        name = str(drop.get("source_name") or "").strip()
        path = str(drop.get("path") or "").strip()
        otype = str(drop.get("type") or "").strip()
        if not name or not path or not otype:
            continue
        try:
            max_items = int(drop.get("max_items") or 20)
            unregister_source(name)
            register_source(name, build_worldsignal_drop_source(
                drop_path=path, default_type=otype,
                source_name=name, max_items=max_items,
            ))
            registered.append(name)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "opportunity.sources.register_worldsignal_failed",
                source=name, error=str(exc),
            )

    if registered:
        logger.info(
            "opportunity.sources.registered",
            count=len(registered), names=registered,
        )
    return registered


__all__ = [
    "register_public_sources_from_config",
    "build_rss_atom_source",
    "build_url_list_source",
    "build_worldsignal_drop_source",
]
