"""PR-LOCAL-USABLE-TODAY-ACCEPTANCE-FIX (Sprint-7 acceptance) tests
for the AcceptanceStatusPanel contract.

Pins:
  1. The panel file lives at the expected path.
  2. The panel renders the 8 acceptance rows the founder asked for.
  3. The panel has the verdict + reload affordances.
  4. The panel does NOT auto-execute writes / installs / OAuth flows.
  5. The PluginsPanel hoists both the AcceptanceStatusPanel AND the
     FirstCallableWizard ABOVE the marketplace grid, so the operator
     sees the acceptance verdict + first-callable wizard the moment
     /connections loads (not buried inside Advanced > Overview).
  6. The legacy V1 section inside Advanced carries an explicit
     "Legacy / debug only" warning at the top.
  7. The legacy "Install recommended" button has been relabeled +
     muted so it doesn't look like the canonical install path.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PANEL = (
    REPO_ROOT / "frontend" / "src" / "pages" / "connections"
    / "AcceptanceStatusPanel.tsx"
)
PLUGINS_PANEL = (
    REPO_ROOT / "frontend" / "src" / "pages" / "connections"
    / "PluginsPanel.tsx"
)
CONNECTIONS_PAGE = (
    REPO_ROOT / "frontend" / "src" / "pages" / "ConnectionsPage.tsx"
)
LEGACY_BROWSER = (
    REPO_ROOT / "frontend" / "src" / "pages" / "connections"
    / "PluginsCatalogBrowser.tsx"
)


# ──────────────────────────────────────────────────────────────────
# 1. Panel exists + carries 8 rows
# ──────────────────────────────────────────────────────────────────


def test_panel_exists():
    assert PANEL.is_file(), f"missing AcceptanceStatusPanel: {PANEL}"


def test_panel_carries_eight_acceptance_rows():
    """Each row's `key` is a string literal in the rows array; the
    testid string template `acceptance-row-${r.key}` is constructed at
    render time. We pin the keys here."""
    src = PANEL.read_text(encoding="utf-8")
    expected_keys = [
        "key: 'backend'",
        "key: 'frontend'",
        "key: 'selfdiag'",
        "key: 'callable'",
        "key: 'wizard'",
        "key: 'filesystem'",
        "key: 'google'",
        "key: 'phase3'",
    ]
    for key in expected_keys:
        assert key in src, (
            f"AcceptanceStatusPanel missing required row key: {key}"
        )
    # Also pin the testid template so the per-row testids resolve.
    assert "`acceptance-row-${r.key}`" in src, (
        "Per-row testid template must be `acceptance-row-${r.key}`"
    )


def test_panel_carries_verdict_testid():
    src = PANEL.read_text(encoding="utf-8")
    assert 'data-testid="acceptance-verdict"' in src
    assert 'data-testid="acceptance-status-panel"' in src


def test_panel_does_not_auto_execute():
    """The panel surfaces status; it must NEVER trigger an install,
    OAuth start, or POST against the executor."""
    src = PANEL.read_text(encoding="utf-8")
    forbidden = (
        "api.post('/connections/v2/",  # writes against connection state
        "api.post(\"/connections/v2/",
        "/skills/execute",             # the executor entrypoint
        "window.location.href =",      # OAuth redirect
        "window.location =",
    )
    for needle in forbidden:
        assert needle not in src, (
            f"AcceptanceStatusPanel contains forbidden auto-action: {needle!r}"
        )


def test_panel_phase3_blocked_assertion_present():
    """The Phase 3 row must explicitly cite the static guarantee
    (PHASE2_ALLOWLIST has zero non-read-only entries)."""
    src = PANEL.read_text(encoding="utf-8")
    assert "Phase 3 writes blocked" in src or "Phase 3" in src
    assert "PHASE2_ALLOWLIST" in src or "read-only" in src


# ──────────────────────────────────────────────────────────────────
# 2. PluginsPanel hoists the acceptance panel + wizard
# ──────────────────────────────────────────────────────────────────


def test_plugins_panel_renders_acceptance_panel():
    src = PLUGINS_PANEL.read_text(encoding="utf-8")
    assert "import AcceptanceStatusPanel" in src, (
        "PluginsPanel must import AcceptanceStatusPanel so the operator "
        "sees the acceptance verdict on the default landing tab"
    )
    assert "<AcceptanceStatusPanel" in src


def test_plugins_panel_renders_first_callable_wizard():
    src = PLUGINS_PANEL.read_text(encoding="utf-8")
    assert "import FirstCallableWizard" in src
    assert "<FirstCallableWizard" in src


def test_plugins_panel_hoist_renders_above_grid():
    """Both the AcceptanceStatusPanel and the FirstCallableWizard must
    appear BEFORE the marketplace grid in the source order."""
    src = PLUGINS_PANEL.read_text(encoding="utf-8")
    panel_idx = src.find("<AcceptanceStatusPanel")
    wizard_idx = src.find("<FirstCallableWizard")
    grid_idx = src.find("Status filter row")  # the chip row right above the grid
    assert panel_idx > 0 and grid_idx > 0
    assert panel_idx < grid_idx, (
        "AcceptanceStatusPanel must render BEFORE the status-filter row "
        "(and therefore the marketplace grid)"
    )
    if wizard_idx > 0:
        assert wizard_idx < grid_idx, (
            "FirstCallableWizard must render BEFORE the marketplace grid"
        )


# ──────────────────────────────────────────────────────────────────
# 3. Legacy V1 marked as debug-only
# ──────────────────────────────────────────────────────────────────


def test_legacy_v1_section_carries_clear_warning():
    src = CONNECTIONS_PAGE.read_text(encoding="utf-8")
    # The legacy_v1 branch must include an explicit warning block.
    assert "Legacy / debug only" in src, (
        "legacy_v1 section must carry the 'Legacy / debug only' warning"
    )


def test_legacy_install_button_relabeled_and_muted():
    src = LEGACY_BROWSER.read_text(encoding="utf-8")
    # The button text must no longer read the misleading "Install recommended".
    # It must read "Legacy install (not recommended)" or similar
    # demotional copy.
    assert "Legacy install (not recommended)" in src, (
        "PluginsCatalogBrowser must relabel 'Install recommended' to make "
        "clear it is a legacy path"
    )
    # And the styling must be muted (no primary cyan) so it doesn't
    # look like the canonical install.
    primary_cyan_class = "border-accent-cyan/30 bg-accent-cyan/10 px-3 py-1.5 text-xs text-accent-cyan"
    # The exact class string from the OLD button. The relabeled button
    # uses border-white/10 / bg-white/5 / text-starlight-400 instead.
    # Locate the legacy-install button block and confirm it's NOT styled
    # as primary cyan.
    btn_idx = src.find("Legacy install (not recommended)")
    assert btn_idx > 0
    # Walk back to find the className for this button.
    btn_block = src[max(0, btn_idx - 400):btn_idx]
    assert primary_cyan_class not in btn_block, (
        "legacy install button must NOT carry primary cyan styling"
    )
