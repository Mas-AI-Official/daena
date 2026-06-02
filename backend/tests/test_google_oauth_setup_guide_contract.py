"""PR-CONN-GOOGLE-OAUTH-SETUP-CLARITY (Sprint-7 PR-5) tests.

The guide is a frontend informational component. It must NEVER:

  * Start an OAuth flow.
  * Ask the operator to paste credentials.
  * Make API calls to Google or to Daena's backend.
  * Reference real client secrets or tokens.

It MUST:

  * Surface the two-account split (masoud.masoori@mas-ai.co for the
    founder/operator, daena@mas-ai.co for the agent voice).
  * Carry a "Manual step required" status callout.
  * Live in the AppsPanel above the search bar so the operator sees
    the guidance BEFORE they pick a row to Connect.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
GUIDE = (
    REPO_ROOT / "frontend" / "src" / "pages" / "connections"
    / "GoogleAccountSetupGuide.tsx"
)
# PR-CONNECTIONS-F1 (2026-05-06) moved the guide out of AppsStorePanel
# into PluginsPanel (the canonical surface operators land on) to keep a
# single source of truth.
PLUGINS_PANEL = (
    REPO_ROOT / "frontend" / "src" / "pages" / "connections"
    / "PluginsPanel.tsx"
)


def test_guide_exists():
    assert GUIDE.is_file(), f"missing setup guide component: {GUIDE}"


def test_guide_names_both_account_roles():
    src = GUIDE.read_text(encoding="utf-8")
    assert "masoud.masoori@mas-ai.co" in src, (
        "guide must name the founder/operator account"
    )
    assert "daena@mas-ai.co" in src, (
        "guide must name the Daena agent-voice account"
    )


def test_guide_carries_manual_step_callout():
    src = GUIDE.read_text(encoding="utf-8").lower()
    assert "manual step required" in src, (
        "guide must surface that this is a manual step (not auto-OAuth)"
    )


def test_guide_does_not_start_oauth_flow():
    """The Sprint-7 brief: 'Do not start OAuth flow automatically.
    Do not require credentials.'"""
    src = GUIDE.read_text(encoding="utf-8")
    forbidden = (
        "api.post(",
        "api.get(",
        "fetch('http",
        'fetch("http',
        # No client-side OAuth library use:
        "google.accounts.oauth2",
        # No password prompts:
        "type=\"password\"",
        "type='password'",
        # No client_secret or token references in the guide itself:
        "client_secret",
        "access_token",
        "refresh_token",
        # No window.location redirect to an OAuth URL on mount:
        "window.location =",
        "window.location.href =",
        "window.location.replace(",
    )
    for needle in forbidden:
        assert needle not in src, (
            f"GoogleAccountSetupGuide.tsx contains forbidden pattern: {needle!r}"
        )


def test_guide_carries_test_ids():
    # V3 Phase 1 (2026-05-07) collapsed the two role cards into status
    # rows: data-testid google-role-{founder,agent} -> google-step-{...}.
    # The section wrapper is a literal data-testid; the per-row ids are
    # passed via SetupRow's `testid` prop (rendered as data-testid). Match
    # the source form: `testid="..."` is a substring of both.
    src = GUIDE.read_text(encoding="utf-8")
    assert 'data-testid="google-account-setup-guide"' in src
    assert 'testid="google-step-founder"' in src
    assert 'testid="google-step-agent"' in src


def test_plugins_panel_renders_the_guide():
    # PR-CONNECTIONS-F1 (2026-05-06) moved the guide into PluginsPanel.
    # Contract preserved: the guide renders BEFORE the search input so the
    # operator sees the two-account split before they pick a row to Connect.
    src = PLUGINS_PANEL.read_text(encoding="utf-8")
    assert "import GoogleAccountSetupGuide" in src
    assert "<GoogleAccountSetupGuide" in src
    guide_idx = src.find("<GoogleAccountSetupGuide")
    search_idx = src.find('placeholder="Search plugins')
    assert guide_idx > 0, "guide not rendered"
    assert guide_idx < search_idx, (
        "guide must render BEFORE the Search input, so the operator sees the "
        "two-account split before they pick a row to Connect"
    )
