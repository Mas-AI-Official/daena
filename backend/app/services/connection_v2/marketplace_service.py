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

    # PR-CONN-PROVIDER-KEY-VISIBILITY (2026-05-03):
    # ``provider_key_present`` is a tri-state for cards whose backing is
    # an API key / endpoint URL the operator configures in settings:
    #   * True  -- ``getattr(settings, key, "")`` returned a non-empty value
    #   * False -- the setting is empty / unset
    #   * None  -- this card kind does not use a settings key (cli_runtime,
    #             oauth_app, mcp_server, browser_tool, computer_use,
    #             skill_pack). Truth lives in the V2 probe instead.
    # The boolean is leak-safe: the value is NEVER read or transmitted,
    # only the presence bit is computed.
    provider_key_present: bool | None = None

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
            "provider_key_present": self.provider_key_present,
            "lifecycle": self.lifecycle,
            "primary_action": self.primary_action,
            "primary_action_label": self.primary_action_label,
        }


# ──────────────────────────────────────────────────────────────────
# Provider-key truth (PR-CONN-PROVIDER-KEY-VISIBILITY)
# ──────────────────────────────────────────────────────────────────


# Maps catalog entry id -> the Settings attribute that holds its
# credential. When the attribute resolves to a truthy value, the
# provider is considered configured. The value itself is never read
# or transmitted -- only the presence bit (bool) leaves this module.
#
# CLI runtimes, OAuth apps, MCP servers, browser/computer-use tools
# and skill packs are NOT in this map: their truth lives in the V2
# probe (binary_check / oauth_token / mcp_initialize) and the OAuth
# token table, not in a settings attribute.
_PROVIDER_KEY_BY_ENTRY_ID: dict[str, str] = {
    # Cloud AI providers (api_key auth)
    "provider-anthropic": "anthropic_api_key",
    "provider-openai": "openai_api_key",
    "provider-google-gemini": "gemini_api_key",
    "provider-perplexity": "perplexity_api_key",
    "provider-groq": "groq_api_key",
    "provider-openrouter": "openrouter_api_key",
    "provider-together": "together_api_key",
    # Local LLM endpoints (URL configuration; defaults exist but the
    # operator can disable Ollama via OLLAMA_ENABLED=false in which case
    # the URL is meaningless. We mirror the model_registry skip rule).
    "local-ollama": "ollama_base_url",
    "local-vllm": "vllm_base_url",
}


def _resolve_provider_key_present(entry: CatalogEntry) -> bool | None:
    """Return tri-state presence of the credential for this entry.

    None when the entry is not credentialed via settings (e.g. OAuth
    apps, CLI runtimes, MCP servers). Otherwise a leak-safe bool.

    Special case: Ollama with OLLAMA_ENABLED=false should report False
    even if the URL has a default. The local llama-server adapter
    (vllm) is the canonical local runtime per project CLAUDE.md.
    """
    settings_attr = _PROVIDER_KEY_BY_ENTRY_ID.get(entry.id)
    if settings_attr is None:
        return None
    settings = get_settings()
    if entry.id == "local-ollama":
        if not getattr(settings, "ollama_enabled", False):
            return False
    value = getattr(settings, settings_attr, "")
    return bool(value)


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
    *,
    provider_key_present: bool | None = None,
) -> tuple[str, str, str]:
    """Return (lifecycle, primary_action, primary_action_label).

    Walks the truth ladder from MOST specific to LEAST specific. Per
    project Rule 17: never advertises callable=True without a probe.

    PR-CONN-PROVIDER-KEY-VISIBILITY (2026-05-03): for cards where
    ``provider_key_present`` is non-None (i.e. api_provider /
    local_model entries credentialed via settings), promote a card with
    a present key but no V2 row yet from "available" -> "configured"
    so the marketplace surfaces a Test action instead of the useless
    Setup Guide. Discovery + first probe will create the V2 row
    momentarily; until then the catalog truth is the honest answer.
    """
    # No V2 row -- catalog only
    if row is None:
        if entry.install_method == "coming-soon":
            return "needs_setup", "setup_guide", "Setup guide"
        if provider_key_present is True:
            # Credential is on disk; discovery hasn't created a V2 row
            # yet. Render as "configured" so the operator sees a Test
            # button rather than a redundant Setup Guide.
            return "configured", "test", "Test"
        if provider_key_present is False and entry.kind == "api_provider":
            # We KNOW this card needs a key and the key is empty.
            # Only api_provider entries route to "configure" -- their
            # missing config is a paste-in API key. local_model entries
            # need an env var (OLLAMA_BASE_URL / VLLM_BASE_URL) which is
            # an operator-side change, so they keep the Setup Guide
            # path with the env-var instructions. This keeps backend
            # primary_action aligned with the frontend pluginCard.ts
            # adapter (see deriveAction comment block).
            return "available", "configure", "Configure"
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

    # PR-CONN-VLLM-BRAIN-PROBE-FIX (2026-05-03):
    # A local_model row whose probe has never run is configured but NOT
    # proven reachable. Falling through to the "configured" branch below
    # causes the frontend's auth_type==none mapping to badge it
    # "Installed" -- the exact "fake online pill" pattern Rule 17 forbids.
    # Truth ladder: we know where the server SHOULD be (configured) but
    # we have not proven anything responds (reachable=False, no failure
    # recorded yet). Surface as "available" + Probe so the operator runs
    # the real LocalModelProbe instead of trusting an env var.
    #
    # After a successful probe, registry.py marks reachable=True AND
    # callable=True simultaneously, so the row jumps directly to the
    # "callable" rung above. After a failed probe, _has_recent_failure
    # already routes to "failed". This guard only catches the never-
    # probed gap.
    if (
        row.kind == "local_model"
        and row.configured
        and not row.reachable
    ):
        return "available", "test", "Probe"

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

            # Compute provider-key presence (None for non-credentialed
            # kinds). Done up front so it can flow into both the card
            # payload AND _derive_lifecycle.
            card.provider_key_present = _resolve_provider_key_present(entry)

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

            lifecycle, action, action_label = _derive_lifecycle(
                entry, row, provider_key_present=card.provider_key_present,
            )
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

    async def diagnostic_summary(self) -> dict[str, Any]:
        """Return a structured diagnostic of WHY connectors aren't callable.

        Sprint-6 PR-2: the operator's "0 of 57 callable" pain point. The
        Overview already shows the count, but doesn't explain WHY zero.
        This summary buckets the catalog into actionable blocker reasons
        + suggested next actions, ranked by count descending.

        The output is deliberately READ-ONLY metadata: counts + small
        example slices (entry_id + display_name only). It NEVER carries
        config blobs, env values, secrets, or token state. Use it to
        render the diagnostic block and a friendly empty-state copy.
        """
        cards = await self.list_cards()
        return build_diagnostic_summary(cards)


# ──────────────────────────────────────────────────────────────────
# Diagnostic summary (Sprint-6 PR-2)
# ──────────────────────────────────────────────────────────────────


# Stable blocker reason taxonomy. The frontend keys off these strings
# for copy + iconography, so renames here are breaking changes.
BLOCKER_REASON_NOT_IMPORTED = "not_imported"
BLOCKER_REASON_COMING_SOON = "coming_soon"
BLOCKER_REASON_NEEDS_API_KEY = "needs_api_key"
BLOCKER_REASON_NEEDS_OAUTH = "needs_oauth"
BLOCKER_REASON_NEEDS_PROBE = "needs_probe"
BLOCKER_REASON_PROBE_FAILED = "probe_failed"
BLOCKER_REASON_DISABLED = "disabled"
BLOCKER_REASON_ARCHIVED = "archived"
BLOCKER_REASON_SKILL_PACK = "skill_pack"


_BLOCKER_LABEL = {
    BLOCKER_REASON_NOT_IMPORTED: "Not imported yet (catalog metadata only)",
    BLOCKER_REASON_COMING_SOON: "Coming soon (no local probe yet)",
    BLOCKER_REASON_NEEDS_API_KEY: "Missing API key",
    BLOCKER_REASON_NEEDS_OAUTH: "Not connected (OAuth flow not started)",
    BLOCKER_REASON_NEEDS_PROBE: "Configured but never probed",
    BLOCKER_REASON_PROBE_FAILED: "Last probe failed",
    BLOCKER_REASON_DISABLED: "Disabled by operator",
    BLOCKER_REASON_ARCHIVED: "Archived",
    BLOCKER_REASON_SKILL_PACK: "Skill pack (not callable on its own)",
}


_BLOCKER_NEXT_ACTION = {
    BLOCKER_REASON_NOT_IMPORTED: (
        "Click Discover installed tools, then Probe to flip callable=true."
    ),
    BLOCKER_REASON_COMING_SOON: (
        "On the roadmap. Daena cannot install or probe this connector yet."
    ),
    BLOCKER_REASON_NEEDS_API_KEY: (
        "Paste the provider API key in Settings > Account > Provider keys."
    ),
    BLOCKER_REASON_NEEDS_OAUTH: (
        "Open the App card and click Connect to start the OAuth flow."
    ),
    BLOCKER_REASON_NEEDS_PROBE: (
        "Open the connector and click Probe to confirm the install works."
    ),
    BLOCKER_REASON_PROBE_FAILED: (
        "Open the connector to see the failure_reason, then Retry probe."
    ),
    BLOCKER_REASON_DISABLED: (
        "Re-enable from the connector card if you still want to use it."
    ),
    BLOCKER_REASON_ARCHIVED: (
        "Restore from the Advanced > Archived view if needed."
    ),
    BLOCKER_REASON_SKILL_PACK: (
        "Skill packs ride on top of other connectors and are never callable alone."
    ),
}


def _classify_card_blocker(card: MarketplaceCard) -> str | None:
    """Return the blocker reason for a card, or None if it is callable.

    The classification reflects the lifecycle truth ladder:
      * lifecycle in {callable, enabled} -> None (no blocker)
      * archived / disabled / skill_pack / failed -> direct mapping
      * coming-soon catalog entries that have no V2 row -> COMING_SOON
      * api_provider missing key -> NEEDS_API_KEY
      * oauth_app with no V2 row or unauthenticated -> NEEDS_OAUTH
      * configured / installed / reachable but not callable -> NEEDS_PROBE
      * available + no V2 row + not coming-soon -> NOT_IMPORTED
    """
    lifecycle = card.lifecycle
    if lifecycle in ("callable", "enabled"):
        return None

    catalog = card.catalog or {}
    install_method = catalog.get("install_method", "")
    kind = catalog.get("kind", "")
    has_v2_row = card.v2_row_id is not None

    # Sprint-6 PR-3 defensive: coming-soon entries always classify as
    # COMING_SOON regardless of lifecycle. If a stale probe registered
    # a failure on one (e.g. browser_probe returning unsupported_tool),
    # the operator still sees "coming_soon" rather than "probe_failed"
    # -- there is nothing they can locally do to advance state and a
    # red "Failed" pill misleads them into expecting a fix path.
    if install_method == "coming-soon":
        return BLOCKER_REASON_COMING_SOON

    if lifecycle == "archived":
        return BLOCKER_REASON_ARCHIVED
    if lifecycle == "disabled":
        return BLOCKER_REASON_DISABLED
    if lifecycle == "skill_pack":
        return BLOCKER_REASON_SKILL_PACK
    if lifecycle == "failed":
        return BLOCKER_REASON_PROBE_FAILED

    if kind == "api_provider" and card.provider_key_present is False:
        return BLOCKER_REASON_NEEDS_API_KEY

    if kind == "oauth_app":
        if not has_v2_row:
            return BLOCKER_REASON_NEEDS_OAUTH
        truth = card.v2_truth or {}
        auth_dim = truth.get("authenticated") or {}
        if not auth_dim.get("value"):
            return BLOCKER_REASON_NEEDS_OAUTH

    if lifecycle in ("configured", "installed", "reachable"):
        return BLOCKER_REASON_NEEDS_PROBE

    if lifecycle == "available" and not has_v2_row:
        return BLOCKER_REASON_NOT_IMPORTED

    # Catch-all: configured/intermediate state without a clear blocker
    return BLOCKER_REASON_NEEDS_PROBE


def build_diagnostic_summary(
    cards: list[MarketplaceCard],
    *,
    examples_per_blocker: int = 3,
) -> dict[str, Any]:
    """Build the diagnostic summary dict from a list of marketplace cards.

    Output shape (stable; frontend pins these keys):

        {
          "totals": {
            "catalog": int,        # total cards
            "callable": int,       # lifecycle in {callable, enabled}
            "configured": int,     # lifecycle in {configured, reachable, installed}
            "failed": int,         # lifecycle == failed
            "skill_packs": int,    # lifecycle == skill_pack
            "coming_soon": int,    # install_method == coming-soon
            "available": int,      # lifecycle == available (no V2 row)
            "blocked": int,        # catalog - callable
          },
          "top_blockers": [
            {
              "reason": str,              # one of BLOCKER_REASON_* constants
              "label": str,               # operator-facing
              "next_action": str,         # operator-facing
              "count": int,
              "examples": [ {entry_id, display_name}, ... ]
            },
            ...
          ]
        }
    """
    totals = {
        "catalog": len(cards),
        "callable": 0,
        "configured": 0,
        "failed": 0,
        "skill_packs": 0,
        "coming_soon": 0,
        "available": 0,
        "blocked": 0,
    }
    blocker_groups: dict[str, list[MarketplaceCard]] = {}

    for card in cards:
        lifecycle = card.lifecycle
        if lifecycle in ("callable", "enabled"):
            totals["callable"] += 1
        if lifecycle in ("configured", "installed", "reachable"):
            totals["configured"] += 1
        if lifecycle == "failed":
            totals["failed"] += 1
        if lifecycle == "skill_pack":
            totals["skill_packs"] += 1
        if (card.catalog or {}).get("install_method") == "coming-soon":
            totals["coming_soon"] += 1
        if lifecycle == "available":
            totals["available"] += 1

        reason = _classify_card_blocker(card)
        if reason is not None:
            blocker_groups.setdefault(reason, []).append(card)

    totals["blocked"] = totals["catalog"] - totals["callable"]

    blockers_out = []
    for reason, group in blocker_groups.items():
        examples = [
            {
                "entry_id": (c.catalog or {}).get("id", ""),
                "display_name": (c.catalog or {}).get("display_name", ""),
            }
            for c in group[:examples_per_blocker]
        ]
        blockers_out.append({
            "reason": reason,
            "label": _BLOCKER_LABEL.get(reason, reason),
            "next_action": _BLOCKER_NEXT_ACTION.get(reason, ""),
            "count": len(group),
            "examples": examples,
        })

    blockers_out.sort(key=lambda b: (-b["count"], b["reason"]))

    return {
        "totals": totals,
        "top_blockers": blockers_out,
    }


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
