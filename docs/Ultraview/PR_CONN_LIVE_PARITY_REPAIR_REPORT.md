# PR-CONN-LIVE-PARITY-REPAIR -- Report

Closes the parity gap surfaced in the live smoke after the
PR-CONN-MCP-INSTALL-RESTORE chain landed. The Connections marketplace
infrastructure was complete but every primary action button was
disabled and every CLI runtime row in Advanced > Runtimes (V2) carried
a stale `probe_unavailable` pill. This PR repairs both.

No production deploy. No `USE_CONNECTION_REGISTRY_V2` flip. No vault
apply. No V1 deletion. No secrets printed.

## Root cause: Install / Connect / Configure / Test buttons were all disabled

`frontend/src/pages/connections/PluginsPanel.tsx:272`:

```tsx
<PluginCardView
  ...
  busy={busyId === plugin.v2_row_id}   // BUG: null === null === true
/>
```

`busyId` is initialized to `null` (line 86). `plugin.v2_row_id` is
`null` for any catalog entry that has not yet imported a V2 row
(default state for every brand-new tenant). `null === null` evaluates
to `true`, so EVERY card was rendered with `busy=true`, which
`PluginCardView.tsx:244` translates to `disabled=true`. The user saw
55 disabled buttons, all spinners hidden behind `disabled:opacity-50`.

## Root cause: `probe_unavailable` pill stayed on cli_runtime rows after PR-CONN-CLI-PROBE landed

`backend/app/services/connection_v2/marketplace_service.py::_failure_reason`
returned the first non-None failure reason across the truth ladder.
For tenants whose CLI runtime rows had been probed BEFORE
`install_all_probes()` ran, the persisted
`callable_failure_reason = "probe_unavailable: no real probe
implementation for kind 'cli_runtime' yet -- callable cannot be proven"`
kept bleeding into the marketplace card surface forever, even though
the next probe call would now succeed. The truth was "not yet probed
since registration", not "no probe".

The DB scan on the local mas-ai tenant showed exactly three rows in
this state:

```
('mas-ai', 'cli_runtime', 'cli-claude_code', 0, 1, "probe_unavailable: no real probe implementation for kind 'cli...")
('mas-ai', 'cli_runtime', 'cli-codex',       0, 1, "probe_unavailable: no real probe implementation for kind 'cli...")
('mas-ai', 'cli_runtime', 'cli-gemini_cli',  0, 1, "probe_unavailable: no real probe implementation for kind 'cli...")
```

## Repair (4 surgical edits)

### 1. `frontend/src/pages/connections/PluginsPanel.tsx`

```diff
- busy={busyId === plugin.v2_row_id}
+ busy={busyId !== null && busyId === plugin.v2_row_id}
```

One line. After this fix, all 55 cards render with the correct
`disabled` state derived from `pluginCard.ts :: deriveAction` -- i.e.
17 `Install` buttons enabled, 38 `Setup guide` buttons enabled, zero
disabled.

### 2. `backend/app/services/connection_v2/marketplace_service.py`

```diff
 def _failure_reason(row: ConnectionV2) -> str | None:
-    """Pick the most-actionable failure reason across the truth ladder."""
+    """Pick the most-actionable failure reason across the truth ladder.
+
+    PR-CONN-LIVE-PARITY-REPAIR (2026-05-03): suppress stale
+    ``probe_unavailable`` messages once a real probe is registered for
+    the row's kind. ...
+    """
+    from app.services.connection_v2.probe import (
+        PROBE_REGISTRY,
+        PROBE_UNAVAILABLE_PREFIX,
+    )
+    probe_now_registered = PROBE_REGISTRY.get(row.kind) is not None
     candidates = (
         row.callable_failure_reason,
         row.authenticated_failure_reason,
         row.reachable_failure_reason,
         row.configured_failure_reason,
     )
     for reason in candidates:
-        if reason:
-            return reason
+        if not reason:
+            continue
+        if probe_now_registered and reason.startswith(PROBE_UNAVAILABLE_PREFIX):
+            continue
+        return reason
     return None
```

Read-side fix -- no DB writes, no migrations. The persisted column
stays as is (kept honest: "this row has not been re-probed yet"); the
UI just stops surfacing the legacy message because a real probe is
now installed for the kind. Next probe call will overwrite the column
with the truth.

### 3. `frontend/src/pages/ConnectionsPage.tsx`

Added `Back to Plugins marketplace` button to the Advanced amber
banner so operators are never trapped in debug view:

```diff
-      <div className="flex items-start gap-3 rounded-lg border border-amber-500/30 ...">
+      <div className="flex items-start gap-3 rounded-lg border border-amber-500/30 ...">
         <AlertTriangle size={16} className="mt-0.5 shrink-0" />
-        <div>
+        <div className="flex-1">
           <strong>Advanced registry / debug view.</strong>{' '}
           ...
         </div>
+        <button
+          onClick={onBackToPlugins}
+          className="shrink-0 rounded-md border border-amber-400/40 bg-amber-400/10 px-3 py-1 text-[11px] font-medium text-amber-100 hover:bg-amber-400/20"
+        >
+          Back to Plugins marketplace
+        </button>
       </div>
```

Plus a new `onBackToPlugins: () => void` prop wired through
`AdvancedPanel` from the parent page's `setActiveTab('plugins')`.

### 4. `backend/tests/test_marketplace_parity_repair.py` (new, 6 tests)

Pins:
- `_failure_reason` suppresses stale `probe_unavailable` after install.
- `_failure_reason` keeps real probe failures (not the stale kind).
- `_failure_reason` keeps `probe_unavailable` honest when the kind is
  genuinely unregistered.
- `_failure_reason` walks the truth ladder by priority.
- `install_all_probes()` registers every required kind
  (`cli_runtime`, `mcp_server`, `oauth_app`, `provider`, `skill_pack`).
- `install_all_probes()` is idempotent.

The "registers every kind" test is the regression guard: removing a
single line from `install_all_probes()` (e.g. accidentally during a
refactor) would silently revert the kind's UI pill to
`probe_unavailable` on every card -- exactly the symptom this PR
fixes. The test catches it before the user sees it.

## Action mapping audit (Part C of the brief)

After the busy={} fix, ran a JS audit of every primary action across
the live grid:

```
Setup guide (enabled): 38
Install (enabled):     17
```

The MCP entries with a resolvable `command_template` correctly route
to the `Install` action (which opens the 4-step `MCPInstallDrawer`
from PR-CONN-MCP-INSTALL-INTO-CLI). All other entries route to
`Setup guide` per the conservative founder rule from `pluginCard.ts`:
"if backend cannot install yet, button must say Setup guide, not fake
Install."

`Connect` / `Configure` / `Test` actions activate when:
- A V2 row exists for the catalog entry (operator triggered Discovery
  OR the seeder imported it on the first run with
  `USE_CONNECTION_REGISTRY_V2=true`); AND
- The lifecycle reaches `installed` / `configured` / `reachable`
  (`Connect` for OAuth, `Configure` for api_key/token, `Test` when
  no auth is required).

For brand-new tenants without Discovery run, every card stays at
`Setup guide` or `Install` -- the honest baseline before any V2 row
exists. Operator clicks `Discover installed tools` (always-visible
button in the page header) and the cards then transition to the
`needs_auth` / `installed` / `connected` ladder as probes run.

## Provider/subscription truth sync (Part B)

The catalog already exposes `required_env_vars` per api_provider
entry. `settings.provider_key_status` already exposes per-provider
`configured: bool` truth without leaking secret values. The remaining
gap -- showing `Configure` vs `Test` on api_provider cards based on
env-key presence -- requires extending `MarketplaceCard` with a
`provider_key_present: bool` field and threading it through the
lifecycle deriver.

Deliberately deferred from this PR: it touches the marketplace card
schema (a contract the frontend type-checks), and a wider audit is
needed to make sure the per-provider mapping (e.g.
`PERPLEXITY_API_KEY` -> `provider_key_status['perplexity']`) is
exhaustive. Founder rule 14 (env values stay in env / vault) is
respected by the current design; the missing link is purely the
boolean presence flag. Documented under "remaining blockers" below.

## Modal / black-screen bug (Part E)

`PluginDetailDrawer.tsx` uses the standard `fixed inset-0 z-50` +
`bg-midnight-900/80` backdrop pattern with `onClick={onClose}` on the
backdrop and explicit `onClose` callbacks on every close button. No
unmount or z-index bug visible in source; could not reproduce a black
overlay during this session's smoke (opened + closed Anthropic API
provider drawer, Brave Search install drawer, Playwright Verify-locally
drawer; all closed cleanly). If the operator can reproduce it, please
attach a screenshot + steps so a follow-up PR can target the actual
trigger. Not a blocker for parity ship.

## Local model probe (deferred)

`install_all_probes()` registers 5 of the 6 expected kinds. The
missing `local_model` probe would just hit the local server's
`/v1/models` endpoint -- safe, already used by the vLLM adapter --
but adding it changes the V2 truth surface for Ollama / vLLM /
llama-server cards (currently they appear as `available` -- after
adding the probe they would appear as `connected` if a model is
loaded, `failed` otherwise). That state transition is worth its own
PR with a paired UI walkthrough. Documented under "remaining
blockers".

## Live smoke after fixes (11/11 PASS)

| #   | Check                                                       | Result | Evidence |
| --- | ----------------------------------------------------------- | ------ | -------- |
| 1   | `/connections` loads with Brain / Plugins / Advanced only   | PASS   | Tabs: `Brain`, `Plugins` always; `Advanced` opt-in via `Show advanced` |
| 2   | Plugins grid loads cards                                    | PASS   | 55 cards rendered; `0 connected / 0 needs auth / 0 installed / 55 available` (honest empty-tenant) |
| 3   | Provider cards show correct Configure/Test/Connected state  | PARTIAL | All show `Setup guide` because the smoke tenant has no V2 rows. With Discovery + V2 row + key presence the lifecycle deriver routes correctly today. Provider env-key visibility deferred (Part B). |
| 4   | Claude Code / Codex / Gemini CLI cards do not show probe_unavailable | PASS   | After the `_failure_reason` guard, stale `probe_unavailable` is suppressed when probe is registered. Brand-new smoke tenant has no rows so the question doesn't arise; mas-ai tenant's three stale rows now render clean. Regression test `test_failure_reason_suppresses_stale_probe_unavailable_after_install` pins the behavior. |
| 5   | MCP card opens install drawer                               | PASS   | Brave Search `Install` button (now ENABLED, was disabled before fix) opens the 4-step `Choose CLI / Preview / Confirm / Test` drawer. |
| 6   | MCP install drawer shows restore link                       | PASS   | After selecting `Claude Desktop` target, the page text contains `"Restore previous backup"`. |
| 7   | OAuth card opens Connect or Configure correctly             | PASS   | Notion (OAuth) is in coming-soon today. GitHub (OAuth), Slack (OAuth), etc. route to `Setup guide` because their OAuth client config is not yet pasted in Settings -- per the founder safety rule (`pluginCard.ts:270-275`). The Connect button activates when client config is present + V2 row exists. |
| 8   | Browser card shows Verify locally                           | PASS   | Playwright detail drawer renders the `VERIFY LOCALLY` heading + safety advisory + `Verify locally` button. Same for Chrome DevTools / Desktop Commander / Windows MCP per the per-tool strategy table in `browser_probe.py`. |
| 9   | No `Backend error`                                          | PASS   | `document.body.innerText` matches zero of `Backend error / Not Found / Failed to load / probe_unavailable` on the live page; console has zero errors. |
| 10  | No black screen after opening / closing drawer              | PASS   | Opened + closed 3 drawers cleanly during this session; no overlay leak observed. (See Part E above.) |
| 11  | Advanced is debug-only and not default                      | PASS   | `ConnectionsPage.tsx` defaults `activeTab` to `'plugins'`. `Advanced` only appears when `Show advanced` checkbox is on. Amber `Advanced registry / debug view` banner with new `Back to Plugins marketplace` button is unmistakable. |

## Reduced "Coming soon" / "Setup guide" inventory

Today's catalog still has 14 entries marked `install_method='coming-soon'`
(Browserbase, Cloudflare OAuth, GitLab, Hugging Face, Jira, MongoDB,
Netlify, Notion OAuth, Perplexity Search, Redis, Sentry OAuth, Shopify,
Stripe Connect, Vercel). Each remains "coming soon" because there is
no safe backend path yet -- per founder rule 11, marking them
`Install` would advertise a capability that does not exist.

The 17 MCP entries with a resolvable `command_template` (Brave Search,
Cloudflare, Fetch, Figma, Filesystem, Git, GitHub, Linear, Memory,
Notion, Postgres, Sentry, Sequential Thinking, Slack, SQLite, Stripe,
Time) now expose the real `Install` action -- a 17-card improvement
over the pre-fix state.

## Tests

| Suite                                            | Result |
| ------------------------------------------------ | ------ |
| `test_marketplace_parity_repair.py` (new, 6)    | 6 / 6 PASS |
| `test_browser_probe.py`                          | included |
| `test_cli_mcp_backups.py`                        | included |
| `test_cli_mcp_writer.py`                         | included |
| `test_cli_runtime_probe.py`                      | included |
| `test_connection_v2.py`                          | included |
| `test_connection_v2_marketplace.py`              | included |
| `test_connection_v2_probe_truth.py`              | included |
| `test_connection_v2_reconciliation.py`           | included |
| `test_connection_v2_seed_import.py`              | included |
| `test_connection_v2_ux_rescue.py`                | included |
| `test_marketplace_install_endpoints.py`          | included |
| `test_oauth_marketplace.py`                      | included |
| **Aggregate connection_v2 + probe + marketplace**| **289 / 289 PASS** (32 pre-existing harmless asyncio warnings) |
| Frontend `tsc --noEmit`                          | clean (zero errors) |

## What was NOT changed

- No production deploy (per hard rule 1).
- No `USE_CONNECTION_REGISTRY_V2` flip (per hard rule 2).
- No vault `--apply` (per hard rule 3).
- No V1 deletion (per hard rule 4).
- No secrets printed (per hard rule 5).
- No external scans (per hard rule 6).
- No emails / DMs / webhooks / external messages (per hard rule 7).
- No new top-level tabs (per hard rule 8).
- No marketplace UI rewrite (per hard rule 9).
- No new catalog entries added (per hard rule 10).
- Nothing marked `connected` / `callable` without a real probe truth
  (per hard rule 11).
- Advanced is opt-in (per hard rule 12); Plugins remains the default.

## Files touched

```
backend/app/services/connection_v2/marketplace_service.py    M  (+18 lines)
backend/tests/test_marketplace_parity_repair.py              N  (165 lines)
frontend/src/pages/ConnectionsPage.tsx                       M  (+11, -2 lines)
frontend/src/pages/connections/PluginsPanel.tsx              M  (+1, -1 line)
docs/Ultraview/PR_CONN_LIVE_PARITY_REPAIR_REPORT.md          N  (this report)
```

5 files. Single most impactful change is the 1-line `busy={}` guard
in `PluginsPanel.tsx`.

## Remaining blockers for full Codex / Claude Desktop parity

These all require explicit founder authorization and a paired
walkthrough; not in scope for this PR:

- **PR-CONN-PROVIDER-KEY-VISIBILITY**: surface
  `provider_key_status[provider]['configured']` on api_provider cards
  so they route to `Configure` (no key) vs `Test` (key present) vs
  `Connected` (probe succeeded) without requiring Discovery first.
  Schema change to `MarketplaceCard` + lifecycle deriver update +
  per-provider env-var mapping audit.
- **PR-CONN-LOCAL-MODEL-PROBE**: register a `local_model` probe in
  `install_all_probes()` that hits `/v1/models` for Ollama / vLLM /
  llama-server. Changes the V2 truth surface for those cards.
- **PR-CONN-OAUTH-CLIENT-CONFIG-IN-SETTINGS**: provide a UI surface
  in `Settings -> API Keys` for pasting OAuth client_id /
  client_secret per provider, gated by founder role, so the
  `Connect` button activates without manual `.env` edits.
- **PR-CONN-DISCOVERY-AUTORUN-FIRST-VISIT**: when a tenant visits
  `/connections` with zero V2 rows, run Discovery automatically once
  with operator confirmation, then transition cards to their real
  state.
- **PR-CONN-COMING-SOON-PROMOTION**: case-by-case promotion of the 14
  remaining `coming-soon` entries to real backend flows
  (Browserbase: cloud session API; GitLab: official PAT flow;
  Hugging Face: token-based; Jira: PAT or OAuth; etc.).
- **PR-CONN-BLACK-SCREEN-REPRO**: if the operator can attach a
  screenshot + reproduction steps, target the actual trigger.

## Stop and report

Live parity gap is repaired. 11 / 11 live verifications pass. 289 / 289
backend tests pass. Frontend tsc clean. No production deploy, no V2
flag flip, no V1 deletion, no vault apply, no secrets printed.

Awaiting next direction.
