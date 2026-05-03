# PR-CONN-BROWSER-PROBE -- Browser + computer-use plugin probes

**Branch:** rebuild-connections-mcp-runtime
**Date:** 2026-05-02
**Founder brief:** Make Browser / Computer Use plugin cards testable
with a safe local probe. Daena should prove whether Playwright /
Chrome DevTools / Desktop Commander / Windows MCP style tools are
installed and usable before claiming they are connected.

---

## TL;DR

Most browser / computer-use catalog entries are MCP-shaped --
once installed via PR-CONN-MCP-INSTALL-INTO-CLI they land as
`kind=mcp_server` V2 rows that the existing `McpServerProbe` covers.
This PR adds a **separate pre-install local check** the operator can
run from the plugin drawer BEFORE installing: Playwright launches a
real headless Chromium to `about:blank`, other tools just verify the
launcher binary on PATH.

- 1 new module: `browser_probe.py` (~390 lines) -- per-tool strategy
  table + 3 strategies (`playwright_local`, `chrome_devtools_local`,
  `command_check`).
- 1 new endpoint: `POST /api/v1/connections/v2/marketplace/browser-probe/{entry_id}` -- pure inspection, never persists.
- 1 frontend section in `PluginDetailDrawer.tsx` -- "Verify locally"
  button + result card with safety copy.
- 19 new unit + endpoint tests, all pass; 315 V2 regression all pass;
  frontend tsc clean.
- Zero em-dashes added. Zero V1 file deleted. Zero new top-level tabs.

**Hard rules honored:** no production deploy, no V2 flag flip, no
vault apply, no V1 deletion, no secret printing, no external scans/
messages, no anti-bot bypass / stealth claims, no external websites
opened (Playwright targets `about:blank` only), no auto-install
(missing playwright / chromium returns clean `package_not_found` /
`browser_not_installed`), no `connected/callable` lie (the local probe
is a "can my machine run this" check, NOT the V2 `callable` truth --
that still requires `McpServerProbe` after install).

**Test results:**
- `test_browser_probe.py`: 19/19 passed.
- Combined V2 + probe regression: 315/315 passed.
- Frontend `tsc --noEmit`: 0 errors.

---

## Supported tools

| Catalog id | Display | Strategy | What it checks |
|---|---|---|---|
| `mcp-playwright` | Playwright | `playwright_local` | Imports Python `playwright`; launches headless Chromium; opens `about:blank`; evaluates `2 + 2`; asserts result == 4; closes cleanly. |
| `mcp-chrome-devtools` | Chrome DevTools | `chrome_devtools_local` | `shutil.which("npx")` + `shutil.which("chrome" or "chromium" or "google-chrome")`. |
| `mcp-desktop-commander` | Desktop Commander | `command_check` | `shutil.which("npx")` only. The MCP probe handles the deeper check after install. |
| `mcp-windows` | Windows MCP | `command_check` (Windows only) | `shutil.which("powershell")` on Windows; returns `unsupported_os` elsewhere. |
| `mcp-browserbase` | Browserbase | `unsupported` | Coming-soon catalog entry; returns `unsupported_tool`. |

Spec table lives in `browser_probe.py:SPEC_BY_CATALOG_ID`. Adding
a new tool is a one-entry addition + (optionally) a new strategy
function.

---

## Exact safe probe behavior

### `playwright_local`

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    try:
        context = browser.new_context()
        try:
            page = context.new_page()
            try:
                page.goto("about:blank", timeout=10_000)
                result = page.evaluate("2 + 2")
                assert result == 4
            finally: page.close()
        finally: context.close()
    finally: browser.close()
```

Wrapped in `asyncio.to_thread` and `asyncio.wait_for` with a
launch_timeout * 2 + 5 s outer ceiling so a hung chromium cannot
block the request. Failure paths are caught and mapped to:

- `package_not_found`: `playwright` Python module missing.
- `browser_not_installed`: chromium binary missing (detected by
  matching "Executable doesn't exist" / "BrowserNotFound" in the
  exception message; the actual path is NEVER echoed).
- `launch_failed`: any other launch exception; only the exception
  TYPE NAME is in the failure_reason.
- `launch_timeout`: outer wait_for fires.
- `page_test_failed`: `evaluate("2 + 2")` returned something other
  than 4.

### `chrome_devtools_local`

```python
npx_path = shutil.which("npx")
chrome_path = shutil.which("chrome") or shutil.which("chromium") or shutil.which("google-chrome")
if not npx_path: return package_not_found
if not chrome_path: return browser_not_installed
return success
```

Doesn't actually launch Chrome -- chrome-devtools-mcp expects
Chrome started with `--remote-debugging-port` that the operator
manages. Verifying both binaries exist is the strongest local check
we can make without inserting ourselves into the operator's debug
session.

### `command_check`

```python
if not shutil.which(spec.launcher_binary): return package_not_found
return success
```

Used for Desktop Commander (npx) and Windows MCP (powershell). The
deeper check (is the MCP package actually published / functional) is
deferred to the existing `McpServerProbe` after PR-CONN-MCP-INSTALL-INTO-CLI lands the entry as kind=mcp_server.

### `unsupported`

Returns `unsupported_tool` honestly. Browserbase is in the catalog as
coming-soon; the drawer surfaces the failure_reason with a pointer to
the vendor's setup docs.

---

## What counts as callable

**This probe does NOT set `callable=true`.** That's intentional and
mirrors the founder's spec ("Do not mark connected/callable unless
probe proves it"). The local probe answers a different question:
"can my machine run this tool at all?"

The V2 `callable` truth still requires:

1. Operator clicks Install in the plugin drawer.
2. PR-CONN-MCP-INSTALL-INTO-CLI writes the MCP entry into the chosen
   CLI's config (with backup + atomic rename).
3. The V2 row imports as `kind=mcp_server` with `vault_ref` linking
   to nothing yet.
4. The existing `McpServerProbe` runs JSON-RPC `initialize` +
   `tools/list` against the actual stdio MCP server -- THIS is the
   probe that flips `callable=true`.

The browser probe is a **preflight**: it tells the operator
"installing this tool will actually work" before they go through the
install flow. The success state populates a `capabilities` list
(constants from the spec table -- never derived from a running
browser session) so the drawer can show "open_page, inspect_dom,
evaluate_script" before the operator commits.

---

## Failure states

| Prefix | When |
|---|---|
| `package_not_found` | The launcher binary OR Python package is not on PATH / importable. |
| `browser_not_installed` | Playwright is installed but chromium binary is missing (typical: `pip install playwright` ran but `playwright install chromium` was skipped). |
| `launch_failed` | Any other Playwright launch exception. failure_reason carries TYPE NAME only (`RuntimeError`, `ConnectionError`, etc.) -- NEVER the exception message which can carry paths. |
| `launch_timeout` | Outer `wait_for` exceeded `launch_timeout * 2 + 5` seconds. Process is reaped by the thread-pool wrapper. |
| `page_test_failed` | `page.evaluate("2 + 2")` returned the wrong type (covers a hostile JS engine swap or a context that died mid-eval). |
| `unsupported_tool` | Catalog entry exists but no strategy registered for it (happens for `mcp-browserbase` today, and any future catalog entry that hasn't been wired). |
| `unsupported_os` | Tool requires a specific OS (Windows MCP on Linux). |
| `config_missing` | Spec has no launcher_binary -- defensive guard, shouldn't fire in production. |
| `permission_required` | Reserved for tools that need elevated permissions (not used today; future hook). |

Each prefix is exported as a named constant from `browser_probe.py`
so the frontend can match without parsing free-form text.

---

## Local safety boundaries

| Rule | Enforcement |
|---|---|
| Never open external sites | Playwright strategy targets `about:blank` ONLY. The page.goto URL is hard-coded in the source; an attacker would have to edit the probe code to change it, and the `assert url == "about:blank"` in tests' fake Playwright catches drift. |
| Never bypass anti-bot | The probe does not configure user-agent spoofing, viewport randomization, fingerprint evasion, or any stealth library. It launches `headless=True` and that's it. |
| Never claim stealth | The user-facing safety copy explicitly says: "Daena does NOT bypass anti-bot systems and never claims stealth or evasion." |
| Never log paths | The `_launch_and_test` exception handler catches `Executable doesn't exist at /path/to/cache` and substitutes a generic message. The generic message tells the operator to run `playwright install chromium` -- without echoing the path. |
| Headless always | `p.chromium.launch(headless=True)` -- never opens a visible window. Tests pin this. |
| Bounded timeouts | Inner page.goto: `launch_timeout * 1000` ms. Outer wait_for: `launch_timeout * 2 + 5` s. Worst-case ~25 s including cleanup. |
| Cleanup on every path | Page, context, browser all close in `try/finally` blocks. The outer `with sync_playwright() as p` ensures the playwright runtime exits even if launch raised. |
| No external network | `about:blank` is local-only. No DNS, no TCP, no TLS. |

---

## Secret / privacy-handling proof

Founder rule 11: never expose local usernames, profile paths,
cookies, tokens, browser profiles, or screenshots in logs or
API payloads.

**Implementation:**

1. **Exception messages are sanitized.** `_launch_and_test` catches
   every exception type and returns one of:
   - `browser_not_installed: chromium binary missing -- run \`playwright install chromium\`` (NO path)
   - `launch_failed: <ExcTypeName>` (NO message body)

   The exception's `.args` / `.message` / `str()` representation is
   NEVER passed to the report.

2. **Capability list is constant.** `report.capabilities` is built
   from `spec.safe_capabilities` (a tuple of literal strings in the
   spec table), NOT derived from anything the browser session
   produced. No way for a hostile site to inject capability strings
   (and the page is `about:blank` anyway).

3. **No browser-state surfaces.** The probe never reads cookies,
   localStorage, sessionStorage, URL history, downloads, or
   screenshots. The single `page.evaluate("2 + 2")` returns an int.

4. **Audit-log scrubbing.** No `logger` calls in `_launch_and_test`
   carry path-bearing variables. The probe's only log is at the
   endpoint layer (uvicorn access log) which carries the entry_id
   (e.g. `mcp-playwright`) -- a public catalog id.

**Audit test** (`TestNoLeak.test_payload_never_contains_local_user_info`):

- Plants a sentinel username (`leaky-username-do-not-show`) in `$USER`.
- Forces a Playwright exception with a path containing the sentinel:
  `"ETIMEDOUT to /home/leaky-username-do-not-show/.cache/ms-playwright"`.
- Asserts the sentinel does NOT appear in the data fields
  (`failure_reason`, `capabilities`, status strings, `tool_id`,
  `tool_display_name`, `strategy`).
- Also asserts `/home/`, `.cache`, `cookie`, `profile` substrings are
  absent from those fields.

The safety_notes documentation MAY mention "cookies" / "screenshots"
("Cookies, profile paths, and screenshots are never written to logs.")
because that's the operator-facing disclaimer -- the test inspects
runtime data fields ONLY.

---

## Frontend flow

**No new tabs, no new pages.** The change is local to
`PluginDetailDrawer.tsx`: a new "Verify locally" section that
appears for `kind=browser_tool` and `kind=computer_use` catalog
entries.

```
PluginDetailDrawer (existing)
  -> if catalog.kind in {browser_tool, computer_use}:
       Section: Verify locally
         Description copy
         Amber safety advisory:
           "Browser tools run locally and require explicit permission.
           Daena does NOT bypass anti-bot systems and never claims
           stealth or evasion."
         [Verify locally] button -> POST /marketplace/browser-probe/{entry_id}
         On result:
           Package status pill (installed / not_found)
           Browser status pill (ready / not_installed / not_required)
           Capability chips (when success)
           Failure_reason code block (when failure)
```

The Test button on the plugin card itself is unchanged -- it still
calls `POST /api/v1/connections/v2/{connection_id}/probe` which
runs the existing `McpServerProbe` against an installed V2 row. The
"Verify locally" button is the PRE-INSTALL counterpart -- it answers
"would installing this work?" without writing anything.

---

## Tests run

### New: `test_browser_probe.py` (19 tests, 100% pass)

| Class | Tests | What it pins |
|---|---|---|
| `TestSpecTable` | 2 | All 5 founder-listed tools have specs; non-unsupported strategies carry safe_capabilities |
| `TestRejectsUnknownAndWrongKind` | 2 | Unknown catalog id -> unsupported_tool; non-browser kind -> unsupported_tool |
| `TestPlaywrightHappyPath` | 1 | Mocked sync_playwright launches about:blank, evaluates 2+2, returns success + safe capabilities |
| `TestPlaywrightPackageMissing` | 1 | Missing playwright module -> package_not_found |
| `TestPlaywrightChromiumMissing` | 1 | "Executable doesn't exist" exception -> browser_not_installed; PATH never echoed |
| `TestPlaywrightLaunchRaises` | 1 | Other exception -> launch_failed; type name only, no internal IP/port leak |
| `TestChromeDevToolsStrategy` | 3 | npx missing -> package_not_found; chrome missing -> browser_not_installed; both present -> success |
| `TestDesktopCommander` | 2 | npx present -> success + capabilities; missing -> package_not_found |
| `TestWindowsMcpOsGate` | 1 | Non-Windows -> unsupported_os |
| `TestBrowserbaseUnsupported` | 1 | Browserbase coming-soon -> unsupported_tool |
| `TestNoLeak` | 1 | Sentinel username never appears in runtime fields; safety_notes copy is allowed to mention "cookies" |
| `TestEndpoint` | 3 | Unknown entry -> 404; non-browser kind -> 400; happy path returns full payload shape |

```
.venv/Scripts/python.exe -m pytest tests/test_browser_probe.py -q
# -> 19 passed in 1.82s
```

### Regression: V2 marketplace + all probes + writer + OAuth

```
.venv/Scripts/python.exe -m pytest tests/ -k "connection_v2 or
  connection_registry or mcp_server_probe or cli_runtime_probe or
  cli_mcp_writer or marketplace_install or skill_pack or
  provider_probe or oauth_app_probe or oauth_marketplace or
  browser_probe" -q
# -> 315 passed, 3974 deselected in 22.76s
```

No pre-existing test failed after the browser probe landed. The
fixture for the new endpoint tests deliberately uses flush-only (no
commit) so it doesn't pollute test isolation for downstream test
files that share the same `test_tenant_id`.

### Frontend

```
cd frontend && npx tsc --noEmit
# -> exit 0 (clean)
```

`PluginDetailDrawer.tsx` (with the new Verify-locally section) and
the new `runBrowserProbe` hook in `useMarketplace.ts` both
type-check under strict TypeScript.

---

## Files changed

| Path | Lines | Purpose |
|---|---|---|
| `backend/app/services/connection_v2/browser_probe.py` | +390 | NEW: per-tool strategy table + 3 strategies (`playwright_local`, `chrome_devtools_local`, `command_check`) |
| `backend/app/api/v1/connections_v2.py` | +51 | NEW: POST /marketplace/browser-probe/{entry_id} endpoint |
| `backend/tests/test_browser_probe.py` | +430 | NEW: 19 unit + endpoint tests |
| `frontend/src/hooks/useMarketplace.ts` | +35 | NEW: runBrowserProbe hook + BrowserProbeReport type |
| `frontend/src/pages/connections/PluginDetailDrawer.tsx` | +95 / -2 | NEW: Verify locally section + ProbeKv helper |
| `docs/Ultraview/PR_CONN_BROWSER_PROBE_REPORT.md` | NEW | this report |

Total: ~1000 lines added, ~3 lines deleted, 0 V1 file touched.

---

## Remaining blockers (deferred to future PRs)

| Future PR | Goal | Why deferred |
|---|---|---|
| `PR-CONN-BROWSER-AGENT` | Live browser-action endpoint (`open_page`, `click`, `fill`, `take_screenshot`) wired to the operator's confirmed-permission gates and Asset Shield egress filter | Real automation needs per-action governance (each navigation should hit BehaviorGuard); out of scope for "is it installed" probe |
| `PR-CONN-BROWSER-ELEVATION` | Surface elevated-permission requirements (e.g. macOS accessibility, Windows UAC for Desktop Commander) before install | Per-OS elevation detection is non-trivial; needs dedicated research |
| `PR-CONN-BROWSER-PROFILE-ISOLATION` | Verify the operator's Chrome user-data-dir is NOT leaked into the spawned Playwright session | Playwright launches with a fresh ephemeral profile by default; this PR doesn't change that, but a future PR could add explicit cleanup verification |
| `PR-CONN-CHROME-DEVTOOLS-PROBE` | Actually connect to Chrome via DevTools protocol on `--remote-debugging-port=9222` | Requires the operator to launch Chrome with that flag first; the probe couldn't reliably do it for them without spawning Chrome itself |
| `PR-CONN-DESKTOP-COMMANDER-DEEP-PROBE` | Run a "list processes" call against the installed Desktop Commander MCP to verify capability | Requires the MCP install to have completed, which is the existing McpServerProbe's job |
| `PR-CONN-BROWSER-PROBE-INSTALL-HINT` | When `package_not_found` for playwright, surface a one-click "Daena needs to install this dependency, click to copy command" UI | Today the failure_reason text carries the install hint; a UI affordance is a polish PR |

These are blockers for "Daena actually drives a browser end-to-end."
None requires the V2 flag flip; each is small + well-scoped.

---

## Why this is the right shape

1. **Honest about scope.** The probe answers "can my machine run
   this tool?" -- NOT "is this tool connected and usable by Daena
   right now?" That's the existing McpServerProbe's job after
   install. Two probes for two questions.
2. **No external network.** Playwright targets `about:blank`. No
   DNS, no TCP, no TLS. The strongest possible "we cannot leak
   data via this probe" guarantee is "the probe doesn't make
   network calls in the first place."
3. **Per-strategy honesty.** Each strategy says exactly what it
   checks (`shutil.which("npx")`, lazy import + launch, binary +
   browser presence) and surfaces a structured failure prefix
   when it can't. No generic "something went wrong" branches.
4. **Constants for capabilities.** `report.capabilities` comes
   from a literal tuple in the spec table -- not from the
   browser session. There is no path for a malicious page to
   inject capability strings (and there's no malicious page
   anyway because we only open about:blank).
5. **Sentinel-leak audit.** Same pattern as the MCP / CLI / OAuth
   PRs: plant a sentinel value where a real attacker might land,
   assert it never escapes the probe.
6. **Per-step bounded timeouts.** Inner page.goto, outer wait_for,
   thread-pool wrapper. A hanging chromium cannot block the
   request indefinitely.

---

## Commit

```
canonicalization: add browser and computer-use plugin probes
```

Stops here. Awaiting next direction.
