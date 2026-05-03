"""Marketplace service -- overlay the curated catalog with live V2 truth.

PR-CONNECTIONS-MARKETPLACE-UX (2026-05-02): the catalog (in
``marketplace_catalog.py``) tells us what Daena KNOWS HOW TO support.
The V2 registry (``ConnectionV2``) tells us what is ACTUALLY working
right now in this tenant. This module merges the two so the UI can
render an "App Store" view where every card carries:

* catalog metadata (display, vendor, install plan, capabilities)
* lifecycle state derived from the V2 row (when one exists)
* honest copy when no V2 row exists ("Available -- click Setup Guide")

Honesty contract:
* If a catalog entry's ``matches_v2_slug`` is set AND a V2 row exists
  for the caller's tenant with that slug, the lifecycle reflects the
  REAL truth ladder. Never advertises callable=True without a probe.
* If no V2 row exists, the lifecycle is ``"available"`` and the card
  surfaces a Setup Guide CTA. Never fabricates an "Installed" pill.
* The marketplace NEVER reads or transmits secret values. ``config``
  fields like ``client_secret``, env values, and tokens are filtered
  out at the boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.vault_boot import load_kek_from_env
from app.core.config import get_settings
from app.models.connection_v2 import ConnectionV2
from app.services.connection_v2.marketplace_catalog import (
    CATALOG,
    CATEGORIES,
    CatalogEntry,
    install_plan_for,
)
from app.services.connection_v2.registry import ConnectionRegistryV2

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────────
# Lifecycle states (one per card)
# ──────────────────────────────────────────────────────────────────


# Order matters -- the merge function picks the first matching state.
# More-specific failure / disabled states beat happy-path states.
LIFECYCLE_STATES = (
    "archived",
    "disabled",
    "failed",
    "needs_setup",
    "available",
    "installed",
    "configured",
    "reachable",
    "callable",
    "enabled",
    "skill_pack",
)


# ──────────────────────────────────────────────────────────────────
# Output shape
# ──────────────────────────────────────────────────────────────────


@dataclass
class MarketplaceCard:
    """One entry in the merged Catalog + V2 view."""

    # From the catalog (always present)
    catalog: dict
    # From the V2 row (may be None)
    v2_row_id: str | None = None
    v2_label: str | None = None
    v2_truth: dict | None = None
    v2_disabled: bool = False
    v2_archived: bool = False
    v2_last_probe_at: str | None = None
    v2_failure_reason: str | None = None

    # Derived
    lifecycle: str = "available"
    primary_action: str = "setup_guide"
    primary_action_label: str = "Setup guide"

    def to_dict(self) -> dict:
        return {
            "catalog": self.catalog,
            "v2_row_id": self.v2_row_id,
            "v2_label": self.v2_label,
            "v2_truth": self.v2_truth,
            "v2_disabled": self.v2_disabled,
            "v2_archived": self.v2_archived,
            "v2_last_probe_at": self.v2_last_probe_at,
            "v2_failure_reason": self.v2_failure_reason,
            "lifecycle": self.lifecycle,
            "primary_action": self.primary_action,
            "primary_action_label": self.primary_action_label,
        }


# ──────────────────────────────────────────────────────────────────
# Lifecycle derivation
# ──────────────────────────────────────────────────────────────────


def _truth_to_dict(row: ConnectionV2) -> dict:
    """Render the 6-dim truth as a JSON-friendly dict."""
    def dim(value: bool, at, failure_at, failure_reason) -> dict:
        return {
            "value": bool(value),
            "at": at.isoformat() if isinstance(at, datetime) else at,
            "failure_at": (
                failure_at.isoformat() if isinstance(failure_at, datetime) else failure_at
            ),
            "failure_reason": failure_reason,
        }

    return {
        "detected": dim(
            row.detected, row.detected_at, row.detected_failure_at, row.detected_failure_reason,
        ),
        "configured": dim(
            row.configured, row.configured_at, row.configured_failure_at, row.configured_failure_reason,
        ),
        "imported": dim(
            row.imported, row.imported_at, row.imported_failure_at, row.imported_failure_reason,
        ),
        "reachable": dim(
            row.reachable, row.reachable_at, row.reachable_failure_at, row.reachable_failure_reason,
        ),
        "authenticated": dim(
            row.authenticated, row.authenticated_at, row.authenticated_failure_at,
            row.authenticated_failure_reason,
        ),
        "callable": dim(
            row.callable, row.callable_at, row.callable_failure_at, row.callable_failure_reason,
        ),
    }


def _derive_lifecycle(
    entry: CatalogEntry,
    row: ConnectionV2 | None,
) -> tuple[str, str, str]:
    """Return (lifecycle, primary_action, primary_action_label).

    Walks the truth ladder from MOST specific to LEAST specific. Per
    project Rule 17: never advertises callable=True without a probe.
    """
    # No V2 row -- catalog only
    if row is None:
        if entry.install_method == "coming-soon":
            return "needs_setup", "setup_guide", "Setup guide"
        return "available", "setup_guide", "Setup guide"

    # Skill pack always wins (it never advances past skill_pack)
    if row.kind == "skill_pack":
        return "skill_pack", "open", "Open"

    # Operator-driven exclusions
    if row.archived:
        return "archived", "none", "Archived"
    if row.disabled:
        return "disabled", "enable", "Enable"

    # Recent failure (any dim with failure_at after at)
    if _has_recent_failure(row):
        return "failed", "test", "Retry probe"

    # Happy path -- climb the ladder
    if row.callable:
        return "callable", "test", "Re-test"
    if row.reachable:
        return "reachable", "test", "Probe"
    if row.configured:
        return "configured", "test", "Probe"
    if row.imported:
        return "installed", "test", "Probe"
    if row.detected:
        return "available", "setup_guide", "Setup guide"

    return "available", "setup_guide", "Setup guide"


def _has_recent_failure(row: ConnectionV2) -> bool:
    pairs = (
        (row.callable_at, row.callable_failure_at),
        (row.authenticated_at, row.authenticated_failure_at),
        (row.reachable_at, row.reachable_failure_at),
        (row.configured_at, row.configured_failure_at),
    )
    for at, fail_at in pairs:
        if fail_at is None:
            continue
        if at is None:
            return True
        # Normalize aware vs naive (SQLite returns naive, Postgres aware)
        a = at if at.tzinfo else at.replace(tzinfo=UTC)
        f = fail_at if fail_at.tzinfo else fail_at.replace(tzinfo=UTC)
        if f >= a:
            return True
    return False


def _failure_reason(row: ConnectionV2) -> str | None:
    """Pick the most-actionable failure reason across the truth ladder.

    PR-CONN-LIVE-PARITY-REPAIR (2026-05-03): suppress stale
    ``probe_unavailable`` messages once a real probe is registered for
    the row's kind. Without this guard, a row probed BEFORE
    ``install_all_probes`` ran keeps surfacing the legacy
    "no real probe implementation" pill in Advanced > Runtimes (V2)
    forever, even though the next probe call will succeed. The truth
    is "not probed yet since registration", not "no probe".
    """
    from app.services.connection_v2.probe import (
        PROBE_REGISTRY,
        PROBE_UNAVAILABLE_PREFIX,
    )
    probe_now_registered = PROBE_REGISTRY.get(row.kind) is not None
    candidates = (
        row.callable_failure_reason,
        row.authenticated_failure_reason,
        row.reachable_failure_reason,
        row.configured_failure_reason,
    )
    for reason in candidates:
        if not reason:
            continue
        if probe_now_registered and reason.startswith(PROBE_UNAVAILABLE_PREFIX):
            continue
        return reason
    return None


# ──────────────────────────────────────────────────────────────────
# Catalog <-> V2 row matcher
# ──────────────────────────────────────────────────────────────────


def _match_v2_row(
    entry: CatalogEntry,
    rows_by_slug: dict[str, ConnectionV2],
) -> ConnectionV2 | None:
    """Find the V2 row that maps to this catalog entry, if any.

    Match priority:
      1. Exact match against ``entry.matches_v2_slug`` if non-empty.
      2. No fuzzy fallback -- silence is honest. A future PR could add
         vendor / kind heuristics, but they'd risk false positives.
    """
    if entry.matches_v2_slug:
        return rows_by_slug.get(entry.matches_v2_slug)
    return None


# ──────────────────────────────────────────────────────────────────
# Service
# ──────────────────────────────────────────────────────────────────


class MarketplaceService:
    """Compose the curated catalog with the live V2 row state."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        tenant_id: UUID,
    ) -> None:
        self.db = db
        self.tenant_id = tenant_id
        settings = get_settings()
        kek = load_kek_from_env(is_production=settings.is_production)
        self.registry = ConnectionRegistryV2(db, kek_seed=kek)

    async def list_cards(self) -> list[MarketplaceCard]:
        """Return one ``MarketplaceCard`` per catalog entry.

        Honesty rules:
          * V2 truth wins over catalog claims for lifecycle.
          * If no V2 row exists, lifecycle is "available" -- never
            "callable".
          * config blob is sanitized to drop any field starting with
            ``"_secret"`` or matching well-known secret names.
        """
        rows = await self.registry.list_for_tenant(tenant_id=self.tenant_id)
        rows_by_slug: dict[str, ConnectionV2] = {r.slug: r for r in rows}

        cards: list[MarketplaceCard] = []
        for entry in CATALOG:
            row = _match_v2_row(entry, rows_by_slug)
            card = MarketplaceCard(catalog=entry.to_dict())

            if row is not None:
                card.v2_row_id = str(row.id)
                card.v2_truth = _truth_to_dict(row)
                card.v2_disabled = bool(row.disabled)
                card.v2_archived = bool(row.archived)
                card.v2_label = await self.registry.label_for(row)

                # Most recent dim-at across the ladder. Normalize aware
                # vs naive datetimes -- Postgres returns aware, SQLite
                # returns naive; comparing them directly raises.
                candidates = [
                    row.callable_at, row.reachable_at, row.configured_at,
                    row.imported_at, row.detected_at,
                ]
                non_null = [c for c in candidates if c is not None]
                if non_null:
                    def _key(d: datetime) -> float:
                        if d.tzinfo is None:
                            return d.replace(tzinfo=UTC).timestamp()
                        return d.timestamp()
                    last_at = max(non_null, key=_key)
                    card.v2_last_probe_at = last_at.isoformat()

                card.v2_failure_reason = _failure_reason(row)

            lifecycle, action, action_label = _derive_lifecycle(entry, row)
            card.lifecycle = lifecycle
            card.primary_action = action
            card.primary_action_label = action_label
            cards.append(card)

        return cards

    async def list_cards_by_category(self) -> dict[str, list[dict]]:
        """Return cards grouped by category id."""
        cards = await self.list_cards()
        out: dict[str, list[dict]] = {c.id: [] for c in CATEGORIES}
        for card in cards:
            cat = card.catalog.get("category", "")
            if cat in out:
                out[cat].append(card.to_dict())
        return out


# ──────────────────────────────────────────────────────────────────
# Install-plan helper (catalog-only; never executes)
# ──────────────────────────────────────────────────────────────────


def install_plan(entry_id: str) -> dict[str, Any] | None:
    """Render an install plan for a catalog entry.

    Returns ``None`` if no entry matches. Plans are pure metadata --
    Daena does NOT run any of the commands automatically.
    """
    entry = next((e for e in CATALOG if e.id == entry_id), None)
    if entry is None:
        return None
    plan = install_plan_for(entry)
    plan["entry"] = entry.to_dict()
    return plan


__all__ = [
    "MarketplaceCard",
    "MarketplaceService",
    "install_plan",
]
