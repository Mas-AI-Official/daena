# PR-CONN-FIRST-CALLABLE-PLUGIN-WIZARD -- Report

**Branch:** `rebuild-connections-mcp-runtime`
**Date:** 2026-05-04
**Sprint:** DAENA-LAPTOP-USABLE-TODAY-SPRINT-7 (PR-3 of 7)

---

## 1. Goal

Walk Masoud from "0 of N callable" to "1 callable plugin" in the
smallest possible number of clicks. Filesystem MCP is the preferred
first plugin because it needs no OAuth, no cloud account login, and
runs locally as an `npx` package.

---

## 2. Hard rules -- all honored

| Rule | Enforced? |
|---|---|
| No auto-install of npm / pip / docker | YES -- pinned by `test_wizard_does_not_auto_install` (forbids child_process / fetch http / api.post / api.get). The wizard is the INFORMATIONAL surface; install goes through the existing safe MCPInstallDrawer |
| Wizard auto-hides once any plugin is callable | YES -- pinned by `test_overview_panel_shows_wizard_only_at_zero_callable` (renders only when `summary.callable === 0`) |
| Catalog ↔ wizard parity | YES -- pinned by `test_wizard_install_command_matches_catalog` (both reference `@modelcontextprotocol/server-filesystem`) |
| No external network from the wizard | YES -- the wizard contains no `fetch()` calls and no `api.*` calls |
| Read the spec link is real, not Daena-hosted | YES -- links to `github.com/modelcontextprotocol/servers/...` only |
| No misleading "Daena will install for you" copy | YES -- copy explicitly says "Daena does NOT run this for you" |

---

## 3. Surface area

### Frontend

#### `frontend/src/pages/connections/FirstCallableWizard.tsx` (NEW)

A self-contained inline wizard with three blocks:

* **What Filesystem can do** -- 4 capability bullets (list directory,
  read file, search, sandbox guarantee).
* **Install command (copy + paste)** -- the exact catalog
  `command_template` rendered in a `<pre>` with a copy-to-clipboard
  button. Replaces `<ALLOWED_ROOT>` with a placeholder so the
  operator never blindly runs a command pointed at a folder they
  don't intend.
* **Next steps** (5-step ordered list) -- (1) optional shell run to
  confirm npx pulls cleanly, (2) open MCP Store tab, (3) click
  Install (delegates to existing safe MCPInstallDrawer with atomic
  CLI config writes), (4) click Probe, (5) run the first read-only
  skill.

Two CTAs at the bottom:
* "Continue in MCP Store" -- calls `onNavigateTab('mcp')`.
* "Read the spec" -- external link to the official MCP filesystem
  README.

`data-testid` hooks: `first-callable-wizard`, `first-callable-install-cmd`,
`first-callable-copy-button`, `first-callable-go-mcp`.

#### `frontend/src/pages/connections/OverviewPanel.tsx` (MODIFIED, +9 LOC)

* Imports `FirstCallableWizard`.
* Renders the wizard at the top of the Overview surface ONLY when
  `summary.callable === 0 && summary.total > 0`.
* Auto-hides the moment any plugin flips to callable. No state, no
  "I dismissed this" cookie -- the empty-state IS the trigger.

### Tests

#### `backend/tests/test_first_callable_wizard_contract.py` (NEW, 6 tests)

1. **`test_filesystem_mcp_is_in_catalog`** -- mcp-filesystem present
   exactly once.
2. **`test_filesystem_mcp_is_easy_first_pick`** -- install_method=npm,
   auth_type=none, zero env vars, command starts with `npx`.
3. **`test_wizard_install_command_matches_catalog`** -- the package
   name `@modelcontextprotocol/server-filesystem` must appear in
   BOTH the catalog command and the wizard source.
4. **`test_wizard_does_not_auto_install`** -- forbidden patterns
   (`child_process`, `spawn`, `execvp`, `execSync`, `fetch('http`,
   `api.post(`, `api.get(`) NEVER appear in the wizard source.
5. **`test_wizard_carries_test_ids`** -- 4 stable testids exist for
   future browser smoke.
6. **`test_overview_panel_shows_wizard_only_at_zero_callable`** --
   the OverviewPanel guards the wizard on `summary.callable === 0`.

---

## 4. Test result

```
$ .venv/Scripts/python.exe -m pytest tests/test_first_callable_wizard_contract.py -q
......                                                                   [100%]
6 passed in 0.08s

$ npx tsc --noEmit
EXIT=0
```

**Sprint progression:** PR-2 ended at 296 in scope.
PR-3 adds 6 tests = **302 in scope**.

---

## 5. Smoke (manual, tomorrow)

1. Open `http://127.0.0.1:5173/connections`.
2. With no plugins callable, the Overview tab shows the wizard at
   top: "Make your first plugin callable", capability list, copy
   button, and 5-step Next steps.
3. Click "Copy" on the install command -- clipboard receives
   `npx -y @modelcontextprotocol/server-filesystem <ALLOWED_ROOT>`.
4. Click "Continue in MCP Store" -- the page switches to the MCP
   Store tab where the operator finds Filesystem and clicks Install
   via the existing MCPInstallDrawer.
5. After the existing install + probe flow flips Filesystem to
   callable, return to Overview -- the wizard is GONE (auto-hidden).

---

## 6. What did NOT change

* MCPInstallDrawer behavior -- untouched. The wizard delegates to it.
* Catalog entries -- untouched.
* Connector probe / install API -- untouched.
* Phase 3 writes -- still impossible.

---

## 7. Follow-up PRs

1. **`PR-CONN-WIZARD-INTEGRATED-INSTALL`** -- when the operator clicks
   "Continue in MCP Store" we currently switch tabs and let them
   click Install. A future PR could open the MCPInstallDrawer
   directly with `mcp-filesystem` pre-selected. Defer until operator
   confirms 2 clicks is too many.
2. **`PR-CONN-WIZARD-DISMISSAL-MEMORY`** -- if the operator clicks
   Skip for now and leaves the page with `callable === 0` still true,
   the wizard re-renders on next visit. A user-preference key could
   suppress it for that session. Defer until someone says it's noise.
3. **`PR-CONN-WIZARD-PROBE-PROGRESS-IN-LINE`** -- after install, show
   probe state inline in the wizard so the operator doesn't have to
   navigate back. Defer until first-run feedback is available.
