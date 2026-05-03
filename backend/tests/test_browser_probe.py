"""PR-CONN-BROWSER-PROBE tests.

Pins the contract of ``browser_probe`` + the
``/marketplace/browser-probe/{entry_id}`` endpoint:

  1. Spec table covers all four founder-listed tools
  2. Unsupported tool -> unsupported_tool prefix
  3. Wrong catalog kind -> unsupported_tool prefix
  4. Playwright happy path (mocked sync_playwright)
  5. Playwright package missing -> package_not_found
  6. Playwright chromium missing -> browser_not_installed
  7. Playwright launch raises -> launch_failed (no path leak)
  8. Chrome-DevTools npx missing -> package_not_found
  9. Chrome-DevTools chrome binary missing -> browser_not_installed
 10. Desktop Commander npx present -> success + capabilities
 11. Windows MCP on non-Windows -> unsupported_os
 12. Browserbase coming-soon -> unsupported_tool
 13. No-leak: profile paths / usernames / cookies never appear in payload
 14. Endpoint unknown entry -> 404
 15. Endpoint non-browser kind -> 400
 16. Endpoint happy path returns full payload shape
"""

from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from app.models.identity import Tenant
from app.services.connection_v2.browser_probe import (
    FAIL_BROWSER_NOT_INSTALLED,
    FAIL_LAUNCH_FAILED,
    FAIL_PACKAGE_NOT_FOUND,
    FAIL_UNSUPPORTED_OS,
    FAIL_UNSUPPORTED_TOOL,
    SAFETY_NOTES,
    SPEC_BY_CATALOG_ID,
    SUPPORTED_TOOLS,
    BrowserProbeReport,
    probe_browser_tool,
)
from app.services.connection_v2.marketplace_catalog import CATALOG, CatalogEntry


pytestmark = pytest.mark.asyncio


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────


def _entry(entry_id: str) -> CatalogEntry:
    e = next((e for e in CATALOG if e.id == entry_id), None)
    assert e is not None, f"{entry_id} missing from catalog"
    return e


@pytest.fixture
async def seeded_tenant(db_session, test_tenant_id):
    """Browser-probe endpoint tests don't actually need a committed
    tenant -- the endpoint runs a per-host LOCAL check and never
    queries the tenants table. We use flush-only (no commit) so this
    fixture rolls back cleanly with db_session and doesn't pollute
    other test files that share the same test_tenant_id.
    """
    from sqlalchemy import select
    existing = (
        await db_session.execute(select(Tenant).where(Tenant.id == test_tenant_id))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    tenant = Tenant(id=test_tenant_id, name="T", slug="t", settings={})
    db_session.add(tenant)
    await db_session.flush()
    return tenant


# ──────────────────────────────────────────────────────────────────
# 1. Spec table covers founder-listed tools
# ──────────────────────────────────────────────────────────────────


class TestSpecTable:
    def test_supported_tools_minimum(self):
        for required in (
            "mcp-playwright", "mcp-chrome-devtools",
            "mcp-desktop-commander", "mcp-windows", "mcp-browserbase",
        ):
            assert required in SPEC_BY_CATALOG_ID, f"missing spec for {required}"
            assert required in SUPPORTED_TOOLS

    def test_each_spec_carries_safe_capabilities_or_marked_unsupported(self):
        for spec in SPEC_BY_CATALOG_ID.values():
            if spec.strategy == "unsupported":
                assert spec.safe_capabilities == ()
            else:
                assert len(spec.safe_capabilities) >= 1, spec.catalog_id


# ──────────────────────────────────────────────────────────────────
# 2-3. Reject unknown / wrong kind
# ──────────────────────────────────────────────────────────────────


class TestRejectsUnknownAndWrongKind:
    async def test_unknown_catalog_id_returns_unsupported_tool(self):
        # Synthesize a fake browser_tool catalog entry not in our spec.
        from app.services.connection_v2.marketplace_catalog import CatalogEntry as CE
        bogus = CE(
            id="mcp-fake-browser", display_name="Fake", vendor="x",
            category="browser", kind="browser_tool",
            short_description="", install_method="npm",
        )
        report = await probe_browser_tool(entry=bogus)
        assert report.success is False
        assert report.failure_reason.startswith(FAIL_UNSUPPORTED_TOOL)

    async def test_non_browser_kind_returns_unsupported_tool(self):
        report = await probe_browser_tool(entry=_entry("cli-claude-code"))
        assert report.success is False
        assert report.failure_reason.startswith(FAIL_UNSUPPORTED_TOOL)


# ──────────────────────────────────────────────────────────────────
# 4-7. Playwright local probe
# ──────────────────────────────────────────────────────────────────


class _FakePlaywright:
    """Mock that mirrors the sync_playwright().__enter__/__exit__ API."""

    def __init__(self, *, eval_result=4, raise_on_launch=None, raise_on_goto=None):
        self.eval_result = eval_result
        self.raise_on_launch = raise_on_launch
        self.raise_on_goto = raise_on_goto

    def __enter__(self):
        return _FakePlaywrightHandle(self)

    def __exit__(self, *_):
        return None


class _FakePlaywrightHandle:
    def __init__(self, parent):
        self.parent = parent
        self.chromium = _FakeChromiumLauncher(parent)


class _FakeChromiumLauncher:
    def __init__(self, parent):
        self.parent = parent

    def launch(self, *, headless=True):
        if self.parent.raise_on_launch is not None:
            raise self.parent.raise_on_launch
        return _FakeBrowser(self.parent)


class _FakeBrowser:
    def __init__(self, parent):
        self.parent = parent

    def new_context(self):
        return _FakeContext(self.parent)

    def close(self):
        pass


class _FakeContext:
    def __init__(self, parent):
        self.parent = parent

    def new_page(self):
        return _FakePage(self.parent)

    def close(self):
        pass


class _FakePage:
    def __init__(self, parent):
        self.parent = parent

    def goto(self, url, *, timeout=0):
        if self.parent.raise_on_goto is not None:
            raise self.parent.raise_on_goto
        assert url == "about:blank", f"probe must only open about:blank, got {url!r}"

    def evaluate(self, expr):
        return self.parent.eval_result

    def close(self):
        pass


def _install_fake_playwright(monkeypatch, *, eval_result=4, raise_on_launch=None, raise_on_goto=None):
    """Install a fake `playwright.sync_api.sync_playwright` into sys.modules."""
    fake_module = MagicMock()
    def sync_playwright():
        return _FakePlaywright(
            eval_result=eval_result,
            raise_on_launch=raise_on_launch,
            raise_on_goto=raise_on_goto,
        )
    fake_module.sync_playwright = sync_playwright
    fake_pkg = MagicMock()
    fake_pkg.sync_api = fake_module
    monkeypatch.setitem(sys.modules, "playwright", fake_pkg)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", fake_module)


class TestPlaywrightHappyPath:
    async def test_launches_about_blank_and_evaluates_two_plus_two(
        self, monkeypatch,
    ):
        _install_fake_playwright(monkeypatch, eval_result=4)
        report = await probe_browser_tool(entry=_entry("mcp-playwright"))

        assert report.success is True, report.failure_reason
        assert report.tool_id == "mcp-playwright"
        assert report.strategy == "playwright_local"
        assert report.package_status == "installed"
        assert report.browser_status == "ready"
        # safe capability list (constant per spec)
        assert "open_page" in report.capabilities
        assert "evaluate_script" in report.capabilities
        assert report.failure_reason is None
        # safety notes always returned
        assert SAFETY_NOTES[0] in report.safety_notes


class TestPlaywrightPackageMissing:
    async def test_no_playwright_module_returns_package_not_found(
        self, monkeypatch,
    ):
        # Force the lazy import to fail.
        monkeypatch.setitem(sys.modules, "playwright", None)
        monkeypatch.setitem(sys.modules, "playwright.sync_api", None)
        report = await probe_browser_tool(entry=_entry("mcp-playwright"))

        assert report.success is False
        assert report.failure_reason.startswith(FAIL_PACKAGE_NOT_FOUND)
        assert report.package_status == "not_found"


class TestPlaywrightChromiumMissing:
    async def test_browser_not_installed_message(self, monkeypatch):
        # Playwright's "Executable doesn't exist" pattern.
        boom = Exception("Executable doesn't exist at /tmp/some-random-path")
        _install_fake_playwright(monkeypatch, raise_on_launch=boom)
        report = await probe_browser_tool(entry=_entry("mcp-playwright"))

        assert report.success is False
        assert report.failure_reason.startswith(FAIL_BROWSER_NOT_INSTALLED)
        assert report.package_status == "installed"
        assert report.browser_status == "not_installed"
        # CRITICAL: the random path from the exception MUST NOT leak.
        assert "/tmp/some-random-path" not in report.failure_reason
        assert "playwright install chromium" in report.failure_reason


class TestPlaywrightLaunchRaises:
    async def test_launch_failed_carries_only_exception_typename(
        self, monkeypatch,
    ):
        boom = RuntimeError("connect ECONNREFUSED 127.0.0.1:9222")
        _install_fake_playwright(monkeypatch, raise_on_launch=boom)
        report = await probe_browser_tool(entry=_entry("mcp-playwright"))

        assert report.success is False
        assert report.failure_reason.startswith(FAIL_LAUNCH_FAILED)
        # No internal IP / port leak.
        assert "127.0.0.1" not in report.failure_reason
        assert "ECONNREFUSED" not in report.failure_reason
        # Type name is carried (RuntimeError) -- safe.
        assert "RuntimeError" in report.failure_reason


# ──────────────────────────────────────────────────────────────────
# 8-9. Chrome DevTools strategy
# ──────────────────────────────────────────────────────────────────


class TestChromeDevToolsStrategy:
    async def test_npx_missing_returns_package_not_found(self, monkeypatch):
        import shutil as sh
        original_which = sh.which
        def fake_which(cmd):
            if cmd == "npx":
                return None
            return original_which(cmd)
        monkeypatch.setattr("app.services.connection_v2.browser_probe.shutil.which", fake_which)
        report = await probe_browser_tool(entry=_entry("mcp-chrome-devtools"))

        assert report.success is False
        assert report.failure_reason.startswith(FAIL_PACKAGE_NOT_FOUND)
        assert report.package_status == "not_found"

    async def test_chrome_missing_returns_browser_not_installed(
        self, monkeypatch,
    ):
        def fake_which(cmd):
            if cmd == "npx":
                return "/usr/bin/npx"
            return None  # no chrome / chromium / google-chrome
        monkeypatch.setattr("app.services.connection_v2.browser_probe.shutil.which", fake_which)
        report = await probe_browser_tool(entry=_entry("mcp-chrome-devtools"))

        assert report.success is False
        assert report.failure_reason.startswith(FAIL_BROWSER_NOT_INSTALLED)
        assert report.package_status == "installed"
        assert report.browser_status == "not_installed"

    async def test_chrome_present_returns_success(self, monkeypatch):
        def fake_which(cmd):
            if cmd in ("npx", "chrome", "chromium", "google-chrome"):
                return f"/usr/bin/{cmd}"
            return None
        monkeypatch.setattr("app.services.connection_v2.browser_probe.shutil.which", fake_which)
        report = await probe_browser_tool(entry=_entry("mcp-chrome-devtools"))

        assert report.success is True, report.failure_reason
        assert report.package_status == "installed"
        assert report.browser_status == "ready"
        assert "inspect_dom" in report.capabilities


# ──────────────────────────────────────────────────────────────────
# 10. Desktop Commander -- command_check happy path
# ──────────────────────────────────────────────────────────────────


class TestDesktopCommander:
    async def test_npx_present_returns_success(self, monkeypatch):
        def fake_which(cmd):
            if cmd == "npx":
                return "/usr/bin/npx"
            return None
        monkeypatch.setattr("app.services.connection_v2.browser_probe.shutil.which", fake_which)
        report = await probe_browser_tool(entry=_entry("mcp-desktop-commander"))

        assert report.success is True, report.failure_reason
        assert report.package_status == "installed"
        # Desktop Commander does not need a browser
        assert report.browser_status == "not_required"
        assert "inspect_processes" in report.capabilities

    async def test_npx_missing_returns_package_not_found(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.connection_v2.browser_probe.shutil.which",
            lambda _cmd: None,
        )
        report = await probe_browser_tool(entry=_entry("mcp-desktop-commander"))
        assert report.success is False
        assert report.failure_reason.startswith(FAIL_PACKAGE_NOT_FOUND)


# ──────────────────────────────────────────────────────────────────
# 11. Windows MCP on non-Windows
# ──────────────────────────────────────────────────────────────────


class TestWindowsMcpOsGate:
    async def test_non_windows_returns_unsupported_os(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.connection_v2.browser_probe.platform.system",
            lambda: "Linux",
        )
        report = await probe_browser_tool(entry=_entry("mcp-windows"))
        assert report.success is False
        assert report.failure_reason.startswith(FAIL_UNSUPPORTED_OS)


# ──────────────────────────────────────────────────────────────────
# 12. Browserbase coming-soon
# ──────────────────────────────────────────────────────────────────


class TestBrowserbaseUnsupported:
    async def test_browserbase_returns_unsupported_tool(self):
        report = await probe_browser_tool(entry=_entry("mcp-browserbase"))
        assert report.success is False
        assert report.failure_reason.startswith(FAIL_UNSUPPORTED_TOOL)


# ──────────────────────────────────────────────────────────────────
# 13. No-leak: paths / usernames / cookies never in payload
# ──────────────────────────────────────────────────────────────────


class TestNoLeak:
    async def test_payload_never_contains_local_user_info(self, monkeypatch):
        # Simulate a Linux env with a sentinel username in PATH.
        monkeypatch.setenv("USER", "leaky-username-do-not-show")
        boom = Exception("ETIMEDOUT to /home/leaky-username-do-not-show/.cache/ms-playwright")
        _install_fake_playwright(monkeypatch, raise_on_launch=boom)
        report = await probe_browser_tool(entry=_entry("mcp-playwright"))

        # Inspect the failure-bearing fields ONLY (safety_notes is
        # documentation copy that legitimately mentions "cookies" /
        # "screenshots" in its warning text). The fields that could
        # carry runtime data are failure_reason + capabilities + the
        # status strings.
        leak_surfaces = json.dumps({
            "failure_reason": report.failure_reason,
            "capabilities": report.capabilities,
            "package_status": report.package_status,
            "browser_status": report.browser_status,
            "tool_id": report.tool_id,
            "tool_display_name": report.tool_display_name,
            "strategy": report.strategy,
        })
        assert "leaky-username-do-not-show" not in leak_surfaces, (
            "PROBE LEAKED local username into response payload"
        )
        assert "/home/" not in leak_surfaces
        assert ".cache" not in leak_surfaces
        # Cookies / profile paths must never appear in the runtime fields
        # (the safety_notes documentation may mention them; that's fine).
        assert "cookie" not in leak_surfaces.lower()
        assert "profile" not in leak_surfaces.lower()


# ──────────────────────────────────────────────────────────────────
# 14-16. /marketplace/browser-probe/{entry_id} endpoint
# ──────────────────────────────────────────────────────────────────


class TestEndpoint:
    async def test_unknown_entry_returns_404(
        self, client, auth_headers, seeded_tenant,
    ):
        res = await client.post(
            "/api/v1/connections/v2/marketplace/browser-probe/mcp-does-not-exist",
            headers=auth_headers,
        )
        assert res.status_code == 404
        assert res.json()["detail"] == "catalog_entry_not_found"

    async def test_non_browser_kind_returns_400(
        self, client, auth_headers, seeded_tenant,
    ):
        res = await client.post(
            "/api/v1/connections/v2/marketplace/browser-probe/cli-claude-code",
            headers=auth_headers,
        )
        assert res.status_code == 400
        assert "browser_probe_unsupported_kind" in res.json()["detail"]

    async def test_endpoint_returns_full_payload_shape(
        self, client, auth_headers, seeded_tenant, monkeypatch,
    ):
        def fake_which(cmd):
            return "/usr/bin/npx" if cmd == "npx" else None
        monkeypatch.setattr(
            "app.services.connection_v2.browser_probe.shutil.which", fake_which,
        )
        res = await client.post(
            "/api/v1/connections/v2/marketplace/browser-probe/mcp-desktop-commander",
            headers=auth_headers,
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["success"] is True
        data = body["data"]
        for key in (
            "tool_id", "tool_display_name", "strategy",
            "package_status", "browser_status", "capabilities",
            "failure_reason", "safety_notes",
        ):
            assert key in data, f"endpoint payload missing {key!r}"
        assert data["tool_id"] == "mcp-desktop-commander"
        assert data["package_status"] == "installed"
        assert data["browser_status"] == "not_required"
        assert isinstance(data["safety_notes"], list)
        assert len(data["safety_notes"]) >= 1
