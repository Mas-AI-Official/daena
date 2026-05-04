"""PR-CONN-COMING-SOON-AND-UNSUPPORTED-UX-CLEANUP (Sprint-6 PR-3,
2026-05-04) tests.

Pins the contract: coming-soon catalog entries are classified as
``coming_soon`` regardless of lifecycle, V2 row state, or stale probe
failure_reason. This guarantees the operator never sees a red
"Failed" pill on a connector they cannot actually advance (e.g.
Browserbase, whose browser_probe legitimately returns
``unsupported_tool``).
"""

from __future__ import annotations

import pytest

from app.services.connection_v2.marketplace_service import (
    BLOCKER_REASON_COMING_SOON,
    BLOCKER_REASON_NEEDS_PROBE,
    BLOCKER_REASON_PROBE_FAILED,
    MarketplaceCard,
    _classify_card_blocker,
)


pytestmark = pytest.mark.asyncio


def _coming_soon_card(
    *, has_v2_row: bool = False, lifecycle: str = "needs_setup",
) -> MarketplaceCard:
    catalog = {
        "id": "mcp-browserbase",
        "display_name": "Browserbase",
        "kind": "browser_tool",
        "install_method": "coming-soon",
    }
    card = MarketplaceCard(catalog=catalog)
    card.lifecycle = lifecycle
    if has_v2_row:
        card.v2_row_id = "00000000-0000-0000-0000-000000000099"
    return card


async def test_coming_soon_no_v2_row_classifies_as_coming_soon():
    c = _coming_soon_card(has_v2_row=False)
    assert _classify_card_blocker(c) == BLOCKER_REASON_COMING_SOON


async def test_coming_soon_with_v2_row_still_coming_soon():
    """PR-3 fix: even after a manual import + probe, a coming-soon
    entry stays classified as coming-soon. The catalog says we don't
    have a real install/probe pathway -- a forced V2 row doesn't
    change that."""
    c = _coming_soon_card(has_v2_row=True, lifecycle="configured")
    assert _classify_card_blocker(c) == BLOCKER_REASON_COMING_SOON


async def test_coming_soon_with_failed_lifecycle_still_coming_soon():
    """PR-3 fix: Browserbase's browser_probe returns ``unsupported_tool``
    which currently records a failure_reason on the V2 row. Without
    this guard the operator saw a red "probe_failed" pill on a
    connector they cannot fix locally."""
    c = _coming_soon_card(has_v2_row=True, lifecycle="failed")
    assert _classify_card_blocker(c) == BLOCKER_REASON_COMING_SOON


async def test_non_coming_soon_failure_still_probe_failed():
    """Sanity: regression check. A real installable connector that
    fails its probe still classifies as probe_failed so the operator
    knows to retry."""
    catalog = {
        "id": "mcp-filesystem",
        "display_name": "Filesystem",
        "kind": "mcp_server",
        "install_method": "npm",
    }
    card = MarketplaceCard(catalog=catalog)
    card.lifecycle = "failed"
    card.v2_row_id = "00000000-0000-0000-0000-000000000001"
    assert _classify_card_blocker(card) == BLOCKER_REASON_PROBE_FAILED


async def test_non_coming_soon_configured_still_needs_probe():
    """Sanity: regression check. Configured non-coming-soon connector
    still routes to needs_probe so the diagnostic shows the right
    next-action button."""
    catalog = {
        "id": "mcp-github",
        "display_name": "GitHub",
        "kind": "mcp_server",
        "install_method": "npm",
    }
    card = MarketplaceCard(catalog=catalog)
    card.lifecycle = "configured"
    card.v2_row_id = "00000000-0000-0000-0000-000000000002"
    assert _classify_card_blocker(card) == BLOCKER_REASON_NEEDS_PROBE
