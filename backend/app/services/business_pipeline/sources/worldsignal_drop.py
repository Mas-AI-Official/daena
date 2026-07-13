"""WorldSignal file-drop source adapter -- Phase 4 Chunk 3 (2026-07-10).

WorldSignal is a SEPARATE runtime (trading intel). NEVER-7 forbids
merging Daena and WorldSignal runtimes / DBs / queues. So this adapter
reads exactly ONE thing: a local JSON file that WorldSignal *drops* on
disk. It is a one-way, read-only, decoupled handoff -- Daena never
imports WorldSignal code, never touches its database, never reads its
queue, never opens a socket to it. WorldSignal writes a file; Daena
reads that file. That is the entire contract ("Daena reads WS via
adapter only").

Hard rules these adapters MUST honor (verified by tests):

  * FILE only. ``drop_path`` must be a local filesystem path -- any
    URL scheme (``://``) is refused at build time. No network, no
    httpx, no DB session, no queue client.
  * Read-only. The file is opened for read; the adapter never writes,
    moves, or deletes it.
  * Silent failure. A missing / oversize / malformed drop yields zero
    opportunities -- WorldSignal being down never aborts discovery.
  * Bounded. Files larger than ``MAX_BYTES`` are skipped (a runaway
    producer can never OOM discovery). Result count capped at
    ``max_items`` so a noisy drop cannot dominate top-N selection.
  * Every emitted opportunity carries ``source_name`` so dedupe +
    audit can trace it back to the WorldSignal boundary.

Drop file shape (either form accepted -- Postel's law at the seam)::

    [ {entry}, {entry}, ... ]

  or::

    {"schema": "worldsignal.opportunity_drop.v1",
     "opportunities": [ {entry}, ... ]}

Each ``entry`` is a dict::

    {"type": "partnership", "title": "...", "description": "...",
     "source_url": null, "deadline_at": "2026-08-01T00:00:00Z",
     "estimated_value_usd": 5000, "effort_hours": 8,
     "risk_label": "low", "next_action": "...", "raw_metadata": {...}}

``type`` is optional per entry; when absent it falls back to the
builder's ``default_type``. An entry whose explicit ``type`` is not a
known ``OPPORTUNITY_TYPE`` is skipped rather than silently mislabeled.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

from app.core.logging import get_logger
from app.models.business import OPPORTUNITY_TYPES
from app.services.business_pipeline.discoverer import DiscoveredOpportunity

logger = get_logger(__name__)


# Local JSON drop -- generous vs the 256 KiB network cap because a
# structured signal batch is legitimately larger, but still bounded.
MAX_BYTES: int = 2 * 1024 * 1024


def _looks_like_url(path: str) -> bool:
    """True if the path carries a URL scheme. Used to REFUSE network
    fetches -- a WorldSignal drop is always a local file."""
    return "://" in path


def _parse_iso(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _coerce_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_entries(raw: object) -> list[dict]:
    """Normalize the drop payload into a list of entry dicts. Accepts
    a bare list or a ``{"opportunities": [...]}`` wrapper. Any other
    shape yields ``[]``."""
    if isinstance(raw, list):
        return [e for e in raw if isinstance(e, dict)]
    if isinstance(raw, dict):
        inner = raw.get("opportunities")
        if isinstance(inner, list):
            return [e for e in inner if isinstance(e, dict)]
    return []


def build_worldsignal_drop_source(
    *, drop_path: str, default_type: str, source_name: str,
    max_items: int = 20,
):
    """Return a source fn that reads a WorldSignal JSON drop file.

    Refuses URL paths and unknown opportunity types at build time --
    bad config fails fast rather than at discovery time. The returned
    fn is synchronous (pure local file IO, no network) and NEVER
    raises: any read / parse failure yields zero opportunities.
    """
    if _looks_like_url(drop_path):
        raise ValueError(
            f"drop_path must be a local file, not a URL: {drop_path!r}"
        )
    if not drop_path.strip():
        raise ValueError("drop_path must be a non-empty path")
    if default_type not in OPPORTUNITY_TYPES:
        raise ValueError(f"unknown opportunity type {default_type!r}")
    if max_items <= 0 or max_items > 100:
        raise ValueError(f"max_items out of range: {max_items}")

    path = Path(drop_path)

    def _source() -> Iterable[DiscoveredOpportunity]:
        try:
            if not path.is_file():
                return []
            size = path.stat().st_size
            if size > MAX_BYTES:
                logger.warning(
                    "opportunity.worldsignal.drop_too_large",
                    source=source_name, size=size, cap=MAX_BYTES,
                )
                return []
            mtime = path.stat().st_mtime
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                "opportunity.worldsignal.drop_read_failed",
                source=source_name, error=type(exc).__name__,
            )
            return []

        entries = _extract_entries(raw)
        out: list[DiscoveredOpportunity] = []
        for entry in entries[:max_items]:
            otype = str(entry.get("type") or default_type).strip()
            title = str(entry.get("title") or "").strip()
            if otype not in OPPORTUNITY_TYPES or not title:
                continue
            desc = entry.get("description")
            url = entry.get("source_url")
            meta = dict(entry.get("raw_metadata") or {})
            meta.setdefault("drop_path", drop_path)
            meta.setdefault("drop_mtime", mtime)
            out.append(DiscoveredOpportunity(
                type=otype,
                title=title[:500],
                source_name=source_name,
                description=(str(desc)[:1000] if desc else None),
                source_url=(str(url)[:2000] if url else None),
                deadline_at=_parse_iso(entry.get("deadline_at")),
                estimated_value_usd=_coerce_int(
                    entry.get("estimated_value_usd"),
                ),
                effort_hours=_coerce_int(entry.get("effort_hours")),
                risk_label=entry.get("risk_label"),
                next_action=entry.get("next_action"),
                raw_metadata=meta,
            ))
        return out

    _source.__name__ = f"worldsignal_{source_name}"  # type: ignore[attr-defined]
    return _source
