"""Pluggable opportunity discoverer -- Sprint-19 PR-1.

Sources are registered via ``register_source(name, fn)`` where
``fn() -> Iterable[DiscoveredOpportunity]``. Each source returns
PRE-DB rows; the orchestrator dedupes + scores + persists.

Sprint-19 ships ONE source: ``manual_seed`` reading from
``backend/.opportunity_seed.json`` so the operator can drop
opportunities in by hand. Real RSS / HN / Devpost integrations
land in Sprint-19.5+ -- the registry is forward-compatible.

Hard rules:

  * NO scraping behind login.
  * NO browser automation.
  * Sources must be read-only.
  * Each source MUST set ``source_name`` so dedupe + audit can trace.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

from app.core.logging import get_logger
from app.models.business import OPPORTUNITY_TYPES

logger = get_logger(__name__)

_SEED_FILE = Path(__file__).resolve().parents[3] / ".opportunity_seed.json"


@dataclass
class DiscoveredOpportunity:
    """Pre-DB shape returned by source functions."""

    type: str
    title: str
    source_name: str
    description: str | None = None
    source_url: str | None = None
    deadline_at: datetime | None = None
    estimated_value_usd: int | None = None
    effort_hours: int | None = None
    risk_label: str | None = None
    next_action: str | None = None
    raw_metadata: dict = field(default_factory=dict)


# ────────────────────────────────────────────────────────────────────
# Source registry
# ────────────────────────────────────────────────────────────────────


SourceFn = Callable[[], Iterable[DiscoveredOpportunity]]
SOURCE_REGISTRY: dict[str, SourceFn] = {}


def register_source(name: str, fn: SourceFn) -> None:
    """Register a source. Refuses re-registration of the same name
    (caller should `unregister_source` first if intentional)."""
    if name in SOURCE_REGISTRY:
        raise RuntimeError(
            f"source already registered: {name!r}. "
            "Call unregister_source first."
        )
    SOURCE_REGISTRY[name] = fn


def unregister_source(name: str) -> None:
    SOURCE_REGISTRY.pop(name, None)


def registered_sources() -> list[str]:
    return sorted(SOURCE_REGISTRY.keys())


# ────────────────────────────────────────────────────────────────────
# Built-in: manual seed file
# ────────────────────────────────────────────────────────────────────


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


def manual_seed_source() -> Iterable[DiscoveredOpportunity]:
    """Read ``backend/.opportunity_seed.json`` and emit each entry as
    a DiscoveredOpportunity. NEVER raises; missing/malformed file
    returns nothing.
    """
    if not _SEED_FILE.exists():
        return []
    try:
        raw = json.loads(_SEED_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("opportunity.seed.read_failed", error=str(exc))
        return []
    if not isinstance(raw, list):
        return []

    out: list[DiscoveredOpportunity] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        otype = str(entry.get("type", "")).strip()
        title = str(entry.get("title", "")).strip()
        if otype not in OPPORTUNITY_TYPES or not title:
            continue
        out.append(DiscoveredOpportunity(
            type=otype,
            title=title,
            description=entry.get("description"),
            source_name=str(entry.get("source_name", "manual_seed")),
            source_url=entry.get("source_url"),
            deadline_at=_parse_iso(entry.get("deadline_at")),
            estimated_value_usd=_coerce_int(entry.get("estimated_value_usd")),
            effort_hours=_coerce_int(entry.get("effort_hours")),
            risk_label=entry.get("risk_label"),
            next_action=entry.get("next_action"),
            raw_metadata=entry.get("raw_metadata") or {},
        ))
    return out


# Register the manual_seed source on module import. Tests can
# unregister + re-register it for isolation.
register_source("manual_seed", manual_seed_source)


# ────────────────────────────────────────────────────────────────────
# Test helpers
# ────────────────────────────────────────────────────────────────────


def _reset_for_tests() -> None:
    SOURCE_REGISTRY.clear()
    register_source("manual_seed", manual_seed_source)
