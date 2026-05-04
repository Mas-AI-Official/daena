"""PR-CONN-FIRST-CALLABLE-PLUGIN-WIZARD (Sprint-7 PR-3) tests.

Pins the wizard <-> catalog contract:

  1. ``mcp-filesystem`` is still in the marketplace catalog and is
     still classified as the easy first-run pick (install_method=npm,
     auth_type=none, command starts with ``npx``).
  2. The exact install command the FRONTEND wizard renders matches
     the catalog's ``command_template`` (modulo the placeholder).
  3. The wizard component file:
       - lives at the expected path
       - never invokes anything that would auto-install
         npm/pip/docker
       - carries the data-testid hooks the integration smoke
         expects.
  4. The OverviewPanel only renders the wizard when callable === 0
     (so once a single plugin is callable, the wizard auto-hides).

These tests are static-only (no live backend or browser required).
"""

from __future__ import annotations

from pathlib import Path

from app.services.connection_v2.marketplace_catalog import CATALOG


REPO_ROOT = Path(__file__).resolve().parents[2]
WIZARD = (
    REPO_ROOT / "frontend" / "src" / "pages" / "connections"
    / "FirstCallableWizard.tsx"
)
OVERVIEW = (
    REPO_ROOT / "frontend" / "src" / "pages" / "connections"
    / "OverviewPanel.tsx"
)


# ──────────────────────────────────────────────────────────────────
# 1. mcp-filesystem still the right first-run pick
# ──────────────────────────────────────────────────────────────────


def test_filesystem_mcp_is_in_catalog():
    catalog = list(CATALOG)
    fs_entries = [e for e in catalog if e.id == "mcp-filesystem"]
    assert len(fs_entries) == 1, (
        f"mcp-filesystem must be in catalog exactly once; found {len(fs_entries)}"
    )


def test_filesystem_mcp_is_easy_first_pick():
    """The wizard's whole pitch is 'no OAuth, no cloud account, no
    native install'. Pin the catalog properties that make that pitch
    true."""
    catalog = list(CATALOG)
    fs = next(e for e in catalog if e.id == "mcp-filesystem")

    assert fs.install_method == "npm", (
        "wizard claims `npx` install -- catalog must agree"
    )
    assert fs.auth_type == "none", (
        "wizard claims no OAuth -- catalog must agree"
    )
    assert fs.required_env_vars == (), (
        "wizard claims zero env vars -- catalog must agree"
    )
    assert fs.command_template.startswith("npx"), (
        "wizard renders an `npx` command -- catalog must start with it"
    )


# ──────────────────────────────────────────────────────────────────
# 2. Wizard renders the exact catalog command
# ──────────────────────────────────────────────────────────────────


def test_wizard_install_command_matches_catalog():
    """If the catalog renames the package, the wizard's hard-coded
    command MUST be updated in the same PR. This test fires loudly
    when the two drift."""
    catalog = list(CATALOG)
    fs = next(e for e in catalog if e.id == "mcp-filesystem")
    catalog_cmd = fs.command_template  # e.g. "npx -y @.../<ALLOWED_ROOT>"

    wizard_src = WIZARD.read_text(encoding="utf-8")
    pkg = "@modelcontextprotocol/server-filesystem"
    assert pkg in catalog_cmd, "catalog command must reference the MCP filesystem package"
    assert pkg in wizard_src, (
        "FirstCallableWizard.tsx must render the same package name "
        "as the catalog -- if the catalog renames, the wizard must too"
    )


# ──────────────────────────────────────────────────────────────────
# 3. Wizard does NOT auto-install
# ──────────────────────────────────────────────────────────────────


def test_wizard_does_not_auto_install():
    """Hard-stop in the Sprint-7 brief: do not auto-run npm/pip/docker
    unless an existing safe install path supports it. The wizard is
    INFORMATIONAL -- the actual install goes through MCPInstallDrawer."""
    src = WIZARD.read_text(encoding="utf-8")
    forbidden = (
        "child_process",
        "spawn(",
        "execvp",
        "execSync",
        "fetch('http",
        'fetch("http',
        "api.post(",
        "api.get(",
    )
    for needle in forbidden:
        assert needle not in src, (
            f"FirstCallableWizard.tsx contains forbidden pattern: {needle!r}"
        )


def test_wizard_carries_test_ids():
    src = WIZARD.read_text(encoding="utf-8")
    assert 'data-testid="first-callable-wizard"' in src
    assert 'data-testid="first-callable-install-cmd"' in src
    assert 'data-testid="first-callable-copy-button"' in src
    assert 'data-testid="first-callable-go-mcp"' in src


# ──────────────────────────────────────────────────────────────────
# 4. OverviewPanel renders the wizard only when callable === 0
# ──────────────────────────────────────────────────────────────────


def test_overview_panel_shows_wizard_only_at_zero_callable():
    """A wizard that lingers after the user has connected something is
    just clutter."""
    src = OVERVIEW.read_text(encoding="utf-8")
    assert "<FirstCallableWizard" in src, (
        "OverviewPanel must render FirstCallableWizard"
    )
    assert "summary.callable === 0" in src, (
        "OverviewPanel must guard FirstCallableWizard on callable===0"
    )
