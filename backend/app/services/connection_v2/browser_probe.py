"""BrowserToolProbe -- safe pre-install local check for browser /
computer-use catalog entries.

PR-CONN-BROWSER-PROBE (2026-05-02). Browser + computer-use catalog
entries (kind=browser_tool / computer_use) are MCP-shaped: their
``command_template`` is ``npx -y @org/pkg``, and once the operator
installs them via PR-CONN-MCP-INSTALL-INTO-CLI they get a V2 row of
kind=mcp_server which the existing ``McpServerProbe`` handles. This
module adds a SEPARATE pre-install local check the operator can run
BEFORE installing -- it answers "can my machine actually run this
tool?" without writing anything to disk.

For Playwright specifically the check is the most thorough: it
imports the Python ``playwright`` library, launches a headless
Chromium, opens ``about:blank``, evaluates a tiny harmless JS
expression, and closes everything. For other tools we check the
launcher binary (``npx`` / ``chrome`` / ``powershell``) availability
without invoking installs.

Hard rules honored (founder):
  * NEVER auto-installs anything (no ``npm install``, no
    ``playwright install chromium``). Missing packages return a
    ``package_not_found`` / ``browser_not_installed`` failure; the
    operator runs the install command themselves.
  * NEVER opens external websites. Playwright targets ``about:blank``
    and ``data:`` URLs only.
  * NEVER bypasses anti-bot systems, never claims stealth or evasion.
  * NEVER logs / returns local usernames, profile paths, cookies, or
    screenshots. The result payload carries strategy + status + a
    bounded capability list -- nothing from the browser session.
  * Bounded by per-step timeouts so a hanging launch cannot block.

Failure prefixes (frontend matches without parsing free-form text):
  - package_not_found
  - browser_not_installed
  - launch_failed
  - launch_timeout
  - page_test_failed
  - unsupported_tool
  - config_missing
  - permission_required
"""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.services.connection_v2.marketplace_catalog import CatalogEntry

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────────
# Failure prefixes
# ──────────────────────────────────────────────────────────────────


FAIL_PACKAGE_NOT_FOUND = "package_not_found"
FAIL_BROWSER_NOT_INSTALLED = "browser_not_installed"
FAIL_LAUNCH_FAILED = "launch_failed"
FAIL_LAUNCH_TIMEOUT = "launch_timeout"
FAIL_PAGE_TEST_FAILED = "page_test_failed"
FAIL_UNSUPPORTED_TOOL = "unsupported_tool"
FAIL_CONFIG_MISSING = "config_missing"
FAIL_PERMISSION_REQUIRED = "permission_required"
FAIL_UNSUPPORTED_OS = "unsupported_os"


_REASON_PREVIEW = 200


def _reason(prefix: str, detail: str = "") -> str:
    if not detail:
        return prefix
    cleaned = detail.replace("\n", " ").replace("\r", " ").strip()
    if len(cleaned) > _REASON_PREVIEW:
        cleaned = cleaned[:_REASON_PREVIEW] + "..."
    return f"{prefix}: {cleaned}"


# Universal safety copy returned with every report. Operator-facing.
SAFETY_NOTES: tuple[str, ...] = (
    "Browser tools run locally and require explicit permission per call.",
    "Daena does NOT bypass anti-bot systems and never claims stealth or evasion.",
    "Cookies, profile paths, and screenshots are never written to logs.",
)


# ──────────────────────────────────────────────────────────────────
# Per-tool strategy table
# ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ToolSpec:
    """How to probe one browser / computer-use catalog entry."""

    catalog_id: str
    display_name: str
    strategy: str  # 'playwright_local' | 'chrome_devtools_local' | 'command_check' | 'unsupported'
    launcher_binary: str = ""  # e.g. "npx" -- empty when not needed
    extra_binaries: tuple[str, ...] = ()  # e.g. ("chrome",) for chrome-devtools
    safe_capabilities: tuple[str, ...] = ()
    requires_os: tuple[str, ...] = ()


_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec(
        catalog_id="mcp-playwright",
        display_name="Playwright",
        strategy="playwright_local",
        launcher_binary="npx",
        safe_capabilities=("open_page", "inspect_dom", "evaluate_script"),
    ),
    ToolSpec(
        catalog_id="mcp-chrome-devtools",
        display_name="Chrome DevTools",
        strategy="chrome_devtools_local",
        launcher_binary="npx",
        extra_binaries=("chrome", "chromium", "google-chrome"),
        safe_capabilities=("inspect_dom", "console_messages", "network_inspection"),
    ),
    ToolSpec(
        catalog_id="mcp-desktop-commander",
        display_name="Desktop Commander",
        strategy="command_check",
        launcher_binary="npx",
        safe_capabilities=("inspect_processes", "read_system_state"),
    ),
    ToolSpec(
        catalog_id="mcp-windows",
        display_name="Windows MCP",
        strategy="command_check",
        launcher_binary="powershell",
        safe_capabilities=("inspect_services", "list_scheduled_tasks"),
        requires_os=("Windows",),
    ),
    ToolSpec(
        catalog_id="mcp-browserbase",
        display_name="Browserbase",
        strategy="unsupported",
        safe_capabilities=(),
    ),
)

SPEC_BY_CATALOG_ID: dict[str, ToolSpec] = {s.catalog_id: s for s in _SPECS}


# Tools the founder spec told us to support; if a catalog entry isn't
# in this set we honestly say so.
SUPPORTED_TOOLS = tuple(s.catalog_id for s in _SPECS)


# ──────────────────────────────────────────────────────────────────
# Result shape
# ──────────────────────────────────────────────────────────────────


@dataclass
class BrowserProbeReport:
    """Outcome of a single browser-tool local check.

    ``capabilities`` is the SAFE capability list for this tool (e.g.
    ``open_page``, ``inspect_dom``) -- not derived from the browser
    session itself, so nothing from the running browser leaks here.
    """

    success: bool
    tool_id: str
    tool_display_name: str
    strategy: str
    package_status: str  # 'installed' | 'not_found' | 'unknown'
    browser_status: str  # 'ready' | 'not_installed' | 'not_required' | 'unknown'
    capabilities: list[str] = field(default_factory=list)
    failure_reason: str | None = None
    safety_notes: tuple[str, ...] = SAFETY_NOTES

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "tool_id": self.tool_id,
            "tool_display_name": self.tool_display_name,
            "strategy": self.strategy,
            "package_status": self.package_status,
            "browser_status": self.browser_status,
            "capabilities": list(self.capabilities),
            "failure_reason": self.failure_reason,
            "safety_notes": list(self.safety_notes),
        }


# ──────────────────────────────────────────────────────────────────
# Public entry point
# ──────────────────────────────────────────────────────────────────


async def probe_browser_tool(
    *, entry: CatalogEntry, launch_timeout: float = 10.0,
) -> BrowserProbeReport:
    """Run the per-tool strategy for a browser / computer-use catalog entry.

    Never raises. Returns a BrowserProbeReport whose failure_reason is
    populated on any non-success branch. The endpoint that calls this
    serializes the report verbatim (no extra fields).
    """
    if entry.kind not in ("browser_tool", "computer_use"):
        return BrowserProbeReport(
            success=False, tool_id=entry.id,
            tool_display_name=entry.display_name,
            strategy="unsupported",
            package_status="unknown", browser_status="unknown",
            failure_reason=_reason(
                FAIL_UNSUPPORTED_TOOL,
                f"entry.kind={entry.kind!r} -- only browser_tool / computer_use supported",
            ),
        )

    spec = SPEC_BY_CATALOG_ID.get(entry.id)
    if spec is None:
        return BrowserProbeReport(
            success=False, tool_id=entry.id,
            tool_display_name=entry.display_name,
            strategy="unsupported",
            package_status="unknown", browser_status="unknown",
            failure_reason=_reason(
                FAIL_UNSUPPORTED_TOOL,
                f"no probe strategy registered for {entry.id!r}",
            ),
        )

    if spec.requires_os and platform.system() not in spec.requires_os:
        return BrowserProbeReport(
            success=False, tool_id=entry.id,
            tool_display_name=spec.display_name,
            strategy=spec.strategy,
            package_status="unknown", browser_status="unknown",
            failure_reason=_reason(
                FAIL_UNSUPPORTED_OS,
                f"requires {','.join(spec.requires_os)}, got {platform.system()}",
            ),
        )

    if spec.strategy == "playwright_local":
        return await _strategy_playwright_local(spec, launch_timeout)
    if spec.strategy == "chrome_devtools_local":
        return await _strategy_chrome_devtools_local(spec)
    if spec.strategy == "command_check":
        return await _strategy_command_check(spec)
    if spec.strategy == "unsupported":
        return BrowserProbeReport(
            success=False, tool_id=entry.id,
            tool_display_name=spec.display_name,
            strategy=spec.strategy,
            package_status="unknown", browser_status="unknown",
            failure_reason=_reason(
                FAIL_UNSUPPORTED_TOOL,
                f"{entry.id} is in catalog but not yet wired for local probe",
            ),
        )

    return BrowserProbeReport(
        success=False, tool_id=entry.id,
        tool_display_name=spec.display_name,
        strategy=spec.strategy,
        package_status="unknown", browser_status="unknown",
        failure_reason=_reason(
            FAIL_UNSUPPORTED_TOOL,
            f"unknown strategy {spec.strategy!r}",
        ),
    )


# ──────────────────────────────────────────────────────────────────
# Strategy: Playwright local launch (real browser, about:blank)
# ──────────────────────────────────────────────────────────────────
#
# Imports playwright lazily so backends without it return a clean
# package_not_found instead of an ImportError at module load time.
# Launch is wrapped in asyncio.to_thread + asyncio.wait_for so a
# hung chromium cannot block the request indefinitely.
#
# Page target: about:blank ONLY. No external network access. The
# JS evaluation is `2 + 2` -- a pure expression with no DOM side
# effects.


async def _strategy_playwright_local(
    spec: ToolSpec, launch_timeout: float,
) -> BrowserProbeReport:
    # Lazy import so missing playwright is not a module-load error.
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        return BrowserProbeReport(
            success=False, tool_id=spec.catalog_id,
            tool_display_name=spec.display_name,
            strategy=spec.strategy,
            package_status="not_found",
            browser_status="unknown",
            failure_reason=_reason(
                FAIL_PACKAGE_NOT_FOUND,
                "playwright Python package not installed -- run "
                "`pip install playwright` then `playwright install chromium`",
            ),
        )

    def _launch_and_test() -> tuple[bool, str | None]:
        """Synchronous launch sequence -- runs in a thread pool.

        Returns (ok, failure_reason). Catches all exceptions; the
        outer wait_for handles timeout. NEVER returns user-identifying
        paths -- only the exception type name.
        """
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    context = browser.new_context()
                    try:
                        page = context.new_page()
                        try:
                            page.goto("about:blank", timeout=int(launch_timeout * 1000))
                            result = page.evaluate("2 + 2")
                            if result != 4:
                                return False, _reason(
                                    FAIL_PAGE_TEST_FAILED,
                                    f"unexpected eval result type={type(result).__name__}",
                                )
                            return True, None
                        finally:
                            try:
                                page.close()
                            except Exception:  # noqa: BLE001
                                pass
                    finally:
                        try:
                            context.close()
                        except Exception:  # noqa: BLE001
                            pass
                finally:
                    try:
                        browser.close()
                    except Exception:  # noqa: BLE001
                        pass
        except Exception as exc:  # noqa: BLE001
            # Detect "Executable doesn't exist" which playwright raises
            # when chromium binary is missing. Message format is stable
            # enough across versions for a substring check; we still
            # never echo the path itself.
            msg = str(exc).lower()
            if "executable doesn't exist" in msg or "browsernotfound" in msg:
                return False, _reason(
                    FAIL_BROWSER_NOT_INSTALLED,
                    "chromium binary missing -- run `playwright install chromium`",
                )
            return False, _reason(
                FAIL_LAUNCH_FAILED, type(exc).__name__,
            )
        return False, _reason(FAIL_LAUNCH_FAILED, "unreachable")

    # Outer timeout covers spawn + connect + page goto + evaluate +
    # cleanup. If the whole sequence exceeds launch_timeout * 2 + 5,
    # we kill it and report launch_timeout.
    try:
        ok, failure = await asyncio.wait_for(
            asyncio.to_thread(_launch_and_test),
            timeout=launch_timeout * 2 + 5.0,
        )
    except asyncio.TimeoutError:
        return BrowserProbeReport(
            success=False, tool_id=spec.catalog_id,
            tool_display_name=spec.display_name,
            strategy=spec.strategy,
            package_status="installed",
            browser_status="unknown",
            failure_reason=_reason(
                FAIL_LAUNCH_TIMEOUT,
                f"playwright launch exceeded {launch_timeout * 2 + 5.0}s",
            ),
        )

    if not ok:
        # Detect which dim of the truth failed for accurate package /
        # browser status fields.
        reason = failure or FAIL_LAUNCH_FAILED
        package_status = "installed"
        browser_status = "not_installed" if reason.startswith(
            FAIL_BROWSER_NOT_INSTALLED,
        ) else "unknown"
        return BrowserProbeReport(
            success=False, tool_id=spec.catalog_id,
            tool_display_name=spec.display_name,
            strategy=spec.strategy,
            package_status=package_status,
            browser_status=browser_status,
            failure_reason=reason,
        )

    return BrowserProbeReport(
        success=True, tool_id=spec.catalog_id,
        tool_display_name=spec.display_name,
        strategy=spec.strategy,
        package_status="installed",
        browser_status="ready",
        capabilities=list(spec.safe_capabilities),
        failure_reason=None,
    )


# ──────────────────────────────────────────────────────────────────
# Strategy: Chrome DevTools local check
# ──────────────────────────────────────────────────────────────────


async def _strategy_chrome_devtools_local(spec: ToolSpec) -> BrowserProbeReport:
    """Chrome DevTools MCP needs (a) npx + (b) Chrome binary on PATH
    with --remote-debugging-port. We can only verify (a) and (b)
    presence here -- launching Chrome is the operator's job.
    """
    npx_path = shutil.which(spec.launcher_binary)
    if not npx_path:
        return BrowserProbeReport(
            success=False, tool_id=spec.catalog_id,
            tool_display_name=spec.display_name,
            strategy=spec.strategy,
            package_status="not_found",
            browser_status="unknown",
            failure_reason=_reason(
                FAIL_PACKAGE_NOT_FOUND,
                f"{spec.launcher_binary} not on PATH -- install Node.js "
                "to enable npx-based MCP launches",
            ),
        )

    # Look for any Chrome-family binary on PATH.
    chrome_path = ""
    for candidate in spec.extra_binaries:
        found = shutil.which(candidate)
        if found:
            chrome_path = found
            break

    if not chrome_path:
        return BrowserProbeReport(
            success=False, tool_id=spec.catalog_id,
            tool_display_name=spec.display_name,
            strategy=spec.strategy,
            package_status="installed",
            browser_status="not_installed",
            failure_reason=_reason(
                FAIL_BROWSER_NOT_INSTALLED,
                "no chrome / chromium / google-chrome binary on PATH",
            ),
        )

    return BrowserProbeReport(
        success=True, tool_id=spec.catalog_id,
        tool_display_name=spec.display_name,
        strategy=spec.strategy,
        package_status="installed",
        browser_status="ready",
        capabilities=list(spec.safe_capabilities),
        failure_reason=None,
    )


# ──────────────────────────────────────────────────────────────────
# Strategy: command launcher availability check
# ──────────────────────────────────────────────────────────────────


async def _strategy_command_check(spec: ToolSpec) -> BrowserProbeReport:
    """Verify the launcher binary (npx, powershell) is on PATH.

    The deeper check (is the MCP package installable / installed) is
    deferred to the existing McpServerProbe after the operator
    completes PR-CONN-MCP-INSTALL-INTO-CLI.
    """
    binary = spec.launcher_binary
    if not binary:
        return BrowserProbeReport(
            success=False, tool_id=spec.catalog_id,
            tool_display_name=spec.display_name,
            strategy=spec.strategy,
            package_status="unknown", browser_status="unknown",
            failure_reason=_reason(FAIL_CONFIG_MISSING, "no launcher_binary in spec"),
        )
    found = shutil.which(binary)
    if not found:
        return BrowserProbeReport(
            success=False, tool_id=spec.catalog_id,
            tool_display_name=spec.display_name,
            strategy=spec.strategy,
            package_status="not_found",
            browser_status="not_required",
            failure_reason=_reason(
                FAIL_PACKAGE_NOT_FOUND,
                f"{binary} not on PATH",
            ),
        )

    return BrowserProbeReport(
        success=True, tool_id=spec.catalog_id,
        tool_display_name=spec.display_name,
        strategy=spec.strategy,
        package_status="installed",
        browser_status="not_required",
        capabilities=list(spec.safe_capabilities),
        failure_reason=None,
    )


__all__ = [
    "FAIL_BROWSER_NOT_INSTALLED",
    "FAIL_CONFIG_MISSING",
    "FAIL_LAUNCH_FAILED",
    "FAIL_LAUNCH_TIMEOUT",
    "FAIL_PACKAGE_NOT_FOUND",
    "FAIL_PAGE_TEST_FAILED",
    "FAIL_PERMISSION_REQUIRED",
    "FAIL_UNSUPPORTED_OS",
    "FAIL_UNSUPPORTED_TOOL",
    "SAFETY_NOTES",
    "SPEC_BY_CATALOG_ID",
    "SUPPORTED_TOOLS",
    "BrowserProbeReport",
    "ToolSpec",
    "probe_browser_tool",
]
