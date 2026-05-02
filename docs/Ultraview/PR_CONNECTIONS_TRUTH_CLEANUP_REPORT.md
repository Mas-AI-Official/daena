# PR-CONNECTIONS-TRUTH-CLEANUP Report

**Date:** 2026-05-02
**Branch:** `rebuild-connections-mcp-runtime`
**Author:** Claude Code (Opus 4.7) under founder direction
**Companion plan:** `docs/Ultraview/DAENA_CANONICALIZATION_PLAN.md` (PR 3
in the founder-sequenced canonicalization queue)
**Sibling PR reports:** `PR_HB_DAEMON_WIRE_REPORT.md`,
`PR_SETTINGS_CLEANUP_REPORT.md`

> **Thesis.** Two surfaces were lying. (1) The V2 probe registry
> auto-installed `NoopProbe` for every `ConnectionKind` at module
> import; `NoopProbe` defaults to `success=True`, so every
> unimplemented kind silently reported healthy on first probe.
> (2) The Connections page tab router fell back to V1 panels (V1
> `_status_for_install` heuristic = "credentials present == connected")
> whenever `USE_CONNECTION_REGISTRY_V2` was off, which is the dev
> default. Together this meant the operator saw "Connected" pills for
> connections that had never proven callable. This PR makes both
> surfaces honest. Backend now returns a structured `probe_unavailable`
> failure for unimplemented kinds. Frontend always renders the V2
> truth panel; V1 panels live behind a "Show legacy / advanced" toggle
> that persists per-browser and is OFF by default.

---

## 0. Hard rules honored

| Rule | Status |
|---|---|
| No production deploy | Yes |
| No `USE_CONNECTION_REGISTRY_V2=true` flip in production | Yes (config default unchanged at `False`) |
| No `vault --apply` | Yes (vault not invoked) |
| No file deletions | Yes (V1 panels still present, just behind a reveal) |
| No secrets printed or committed | Yes (probe failure_reason redaction unchanged; new failure_reason for unavailable kinds is built from kind name only) |
| No external scans | Yes |
| No external messages (email / DM / SMS / webhook) | Yes |
| No modifications to Skills, Scan UX, Workstream spine, Settings (except links/copy) | Yes -- zero edits to those surfaces this PR |
| No claim of "Connected" without a real probe | Yes (V1 "Connected" pill now shows "Connected (legacy)" with tooltip pointing to V2 truth) |
| Em dashes in new content (project CLAUDE.md Rule 12) | None introduced (verified by per-file `git diff` em-dash count = 0 across all 7 PR-3 source files) |
| No protected files modified (`vault_adapter.py`, `vault_migration.py`, `oauth_credentials_store.py` per project Rule 18) | Yes -- not touched |

---

## 1. Phase A: V2 probe truth pre-requisite

### 1.1 The lie (before)

The brief asked us to inspect `backend/app/services/connection_v2/probe.py`
and "the `NotImplementedError` path." On inspection, the
`NotImplementedError` (line 59 of the original file) was in the
abstract base method body and is structurally unreachable -- Python's
ABC machinery refuses to instantiate `Probe` directly, so the only
way that line ever runs is if someone bypassed ABC. Not the lie.

The actual lying surface was **`_install_default_noop_probes()`** at
line 124, called at module bottom (line 130). It auto-filled the
`PROBE_REGISTRY` with `NoopProbe(kind)` for every `ConnectionKind`
value. `NoopProbe.run()` defaults to `success=True` when no
`_test_probe` directive sits in `row.config`. So in dev (where no
real probe is registered for `cli_runtime`, `mcp_server`, `plugin`,
`oauth_app`, `local_model`, and `provider` only when the V2 flag is
on), every probe attempt silently returned success. The V2 truth
panel happily showed green "callable" pills for connections that had
never proven callable -- a CLAUDE.md Rule 17 violation
(Honesty + Persistence + Visibility).

### 1.2 The fix (after)

`backend/app/services/connection_v2/probe.py`:

| Change | Line / area | Purpose |
|---|---|---|
| Removed `_install_default_noop_probes()` symbol entirely | was lines 122-130 | Stop the auto-lie at module import |
| Added `install_noop_probes_for_tests()` | new function (~7 lines) | Explicit opt-in for tests; production code path NEVER calls this |
| Added `PROBE_UNAVAILABLE_PREFIX` sentinel constant | new module constant | Frontend can match on the prefix to render a distinct "Probe unavailable" UI state vs. "Probe failed" |
| Strengthened `run_probe()` no-probe-registered failure_reason | run_probe body | Now starts with `"probe_unavailable: "` and explicitly names the kind so audit logs read "no real probe implementation for kind 'mcp_server' yet -- callable cannot be proven" |
| Updated module docstring | top of file | Documents the contract change + why it matters |

**Probe behavior: before vs after**

| Scenario | Before | After |
|---|---|---|
| `kind=plugin`, no probe registered, probe runs | Returns `success=True` (NoopProbe default lies) | Returns `success=False`, `failure_dim="callable"`, `failure_reason="probe_unavailable: no real probe implementation for kind 'plugin' yet -- callable cannot be proven"` |
| `kind=provider`, ProviderProbe registered, probe runs against valid OpenAI key | Returns real probe outcome (was already correct) | Identical -- real probe still wins |
| `kind=mcp_server`, NoopProbe registered explicitly via test fixture, `row.config={"_test_probe": "fail_callable"}` | Returns `success=False`, `failure_reason="capability call failed (test)"` | Identical -- explicit test fixture path unchanged |
| Probe raises `RuntimeError("...")` | Returns `success=False`, `failure_reason="probe raised RuntimeError: ..."` (truncated to 200 chars) | Identical -- contract is "never raise" |
| Module just imported, no test fixture, no `install_all_probes()` call | Registry pre-filled with 6 NoopProbes | Registry empty -- caller must explicitly install |

### 1.3 Files modified (Phase A)

| File | Lines added | Lines removed | Why |
|---|---|---|---|
| `backend/app/services/connection_v2/probe.py` | +29 | -10 | Remove auto-Noop, add `PROBE_UNAVAILABLE_PREFIX`, strengthen `run_probe` failure path, add `install_noop_probes_for_tests` |
| `backend/tests/test_connection_v2.py` | +6 | -1 | `registry` fixture now calls `install_noop_probes_for_tests()` explicitly so the existing TestProbe class still exercises NoopProbe directives |
| `backend/tests/test_connection_v2_probe_truth.py` | +220 (NEW) | 0 | 4 test classes (8 tests) pinning the new contract |

### 1.4 Backend tests run

```text
pytest tests/test_connection_v2_probe_truth.py
  TestProbeUnavailable
    test_no_probe_returns_probe_unavailable_not_500              PASSED
    test_probe_unavailable_reason_names_the_kind                 PASSED
  TestRegisteredProbeUsed
    test_registered_probe_runs_and_returns_real_result           PASSED
    test_registered_probe_takes_precedence_over_fallback         PASSED
  TestNoSecretLeakage
    test_unavailable_failure_reason_never_includes_config_values PASSED
    test_raised_probe_failure_reason_never_includes_secrets      PASSED
  TestNoAutoNoopInstall
    test_install_noop_probes_for_tests_is_explicit               PASSED
    test_explicit_install_populates_every_kind                   PASSED
  -> 8/8 pass in 0.19s

Regression: pytest tests/test_connection_v2.py
                  tests/test_phase7_lifespan_seed.py
                  tests/test_phase7_provider_probes.py
  53/53 pass (combined run: 61/61 in 0.58s)
```

Module-load smoke (fresh Python process):

```text
PROBE_REGISTRY size after import: 0          # no auto-fill
NoopProbe class present: True                # still available for tests
install_noop_probes_for_tests present: True  # explicit installer exists
Old _install_default_noop_probes removed: True
PROBE_UNAVAILABLE_PREFIX: 'probe_unavailable: '
```

---

## 2. Phase B: Connections frontend truth cleanup

### 2.1 Tab routing: before vs after

Before (`ConnectionsPage.tsx`): a `useV2Flag()` hook fetched the
backend `USE_CONNECTION_REGISTRY_V2` value and routed each tab:

```text
Plugins tab:
  flag ON  -> PluginsV2Panel
  flag OFF -> LegacyTabBanner + PluginsCatalogBrowser  (V1)

MCP Servers tab:
  flag ON  -> McpServersV2Panel
  flag OFF -> LegacyTabBanner + McpServersPanel        (V1)
```

In dev (flag OFF by default), the operator saw V1 panels with their
legacy `_status_for_install` heuristic. The V2 truth surface required
flipping the flag in `.env` -- a setup step nobody does on first run.

After: tabs always render V2 panels. V1 panels live behind a
"Show legacy / advanced" toggle:

```text
Always-visible primary tabs (4):
  All Connections (V2)  -> ConnectionsV2Panel
  Main Brain            -> MainBrainPanel
  Plugins               -> PluginsV2Panel    (always V2)
  MCP Servers           -> McpServersV2Panel (always V2)

Toggle "Show legacy / advanced" (localStorage, OFF by default):
  When ON: 5th tab "Legacy / Advanced" appears, containing BOTH V1
  panels stacked under the canonical banner:
  "Legacy connection registry. Kept for migration and debugging.
   V2 truth is canonical."
```

The toggle persists to `localStorage` key
`daena.connections.show_legacy` so the operator's preference sticks
across reloads. A safety-net `useEffect` auto-flips the toggle ON if
the operator deep-links into the legacy tab (mirrors the
SettingsPage `daena.settings.show_advanced` pattern landed in
PR-SETTINGS-CLEANUP). Toggling OFF while the legacy tab is active
snaps the operator back to the V2 truth tab so they're never staring
at an empty pane after their own click.

### 2.2 V1 surfaces moved behind Legacy / Advanced

| V1 surface | Old location | New location | Still functional? |
|---|---|---|---|
| `PluginsCatalogBrowser` (V1 plugin install browser) | Plugins tab when flag OFF | Inside `LegacyAdvancedPanel`, requires Show legacy toggle | Yes -- install + connect + disconnect still work; do NOT mirror to V2 unless flag ON (documented in panel banner) |
| `McpServersPanel` (V1 MCP detect / install / probe view) | MCP Servers tab when flag OFF | Inside `LegacyAdvancedPanel`, requires Show legacy toggle | Yes -- detect + import + probe still work; same V2-mirror caveat |

### 2.3 Button audit (Phase B item 6)

| Button | Panel | Action wired? | Treatment |
|---|---|---|---|
| Probe (V2 row) | `ConnectionsV2Panel` | Yes (`POST /v2/{id}/probe`) | Kept as-is |
| Test (V2 row) | `ConnectionsV2Panel` | Yes (alias of probe) | Kept as-is |
| Enable / Disable (V2 row) | `ConnectionsV2Panel` | Yes | Kept as-is |
| Archive (V2 row) | `ConnectionsV2Panel` | Yes (soft delete) | Kept as-is with click-to-confirm |
| Set Main Brain (CLI runtime row) | `MainBrainPanel` | Yes; backend gate via `runtime_not_callable` error code | Kept as-is. Already disables when V2 reports `callable=false` AND Experimental Override toggle is OFF (Phase B rule 7 satisfied -- backend gate is source of truth, the UI button is just visible affordance) |
| Set Main Brain (provider row) | `MainBrainPanel` | Yes (legacy `provider.status === 'connected'` heuristic) | Untouched -- providers don't have V2 callable rows yet; provider keys configured via Settings; documented as remaining gap below |
| Experimental Override toggle | `MainBrainPanel` | Yes (sends `experimental_override: true` flag; backend logs `experimental_override_used` to audit) | Untouched -- already correctly wired |
| Seed providers | `PluginsV2Panel` | Yes (`POST /v2/reconciliation/seed-providers`, FOUNDER+) | Kept as-is |
| Probe (Plugins V2 row) | `PluginsV2Panel` | Yes | Kept as-is |
| Refresh | All V2 panels | Yes | Kept as-is |
| Install (V1 catalog) | `PluginsCatalogBrowser` (Legacy) | Yes (legacy install dialog) | Kept; documented as legacy in panel banner; behind reveal toggle |
| Connect account (V1) | `PluginsCatalogBrowser` (Legacy) | Yes (legacy install dialog) | Kept; same legacy treatment |
| Test (V1 MCP) | `McpServersPanel` (Legacy) | Yes (`POST /mcp/{key}/probe`) | Kept; behind reveal toggle |
| Import (V1 detected MCP) | `McpServersPanel` (Legacy) | Yes (legacy import flow) | Kept; behind reveal toggle |
| Install MCP (V1 catalog) | `McpServersPanel` (Legacy) | Yes (legacy install) | Kept; behind reveal toggle |

No buttons needed `Coming Soon`, `Probe only`, or `Requires config`
relabeling -- every existing button calls a real backend endpoint.
The honest qualifier needed was `Legacy action` for the V1 plugin and
MCP install/connect surfaces, which is now conveyed by:

1. The wrapping `LegacyAdvancedPanel` banner ("Legacy connection
   registry. Kept for migration and debugging. V2 truth is canonical.")
2. Per-section sub-headings clarifying the V2 mirror caveat
3. The V1 `StatusBadge` for plugins now renders "Connected (legacy)"
   with a tooltip explicitly noting the heuristic source
4. The V1 `StatusBadge` "Installed" pill now has a tooltip pointing
   to V2 for callable truth

### 2.4 Connection-row states now shown (Phase B items 4 + 5)

The V2 panel (`ConnectionsV2Panel`, `PluginsV2Panel`, `McpServersV2Panel`,
backed by `useConnectionsV2` hook + V2 backend's `derive_label` truth
ladder) renders these states honestly:

| Phase B label | V2 derive_label value | Source of truth |
|---|---|---|
| Healthy | `healthy` | `callable=true` and last probe within fresh window |
| Configured but unreachable | `failed` (with `failure_dim="reachable"`) | `configured=true`, `reachable=false`, `reachable_failure_at` set |
| Missing config | `needs_config` | `detected=true`, `configured=false` |
| Probe unavailable | `failed` (with `failure_reason` starting with `PROBE_UNAVAILABLE_PREFIX`) | New in this PR; rendered via existing failure_reason text in the row's failing-dim line |
| Not installed | `installable` | `configured=true`, `imported=false` |
| Legacy only | (V1 panel only) "Connected (legacy)" / "Installed" | V1 `_status_for_install` heuristic; clearly labeled as V1 in the wrapping panel |
| Healthy stale | `healthy_stale` | `callable=true` but probe is older than the fresh window |
| Degraded stale | `degraded_stale` | Old probe + low `healthy_call_ratio` |
| Disabled | `disabled` | Operator-toggled off |
| Archived | `archived` | Soft-deleted |
| Unknown | `unknown` | Nothing proven yet |

The 6 truth dimensions (detected / configured / imported / reachable /
authenticated / callable) render as a per-row mini ladder with
per-dim tooltip showing `failure_reason` or "<dim> ok / not yet
proven". The Details drawer drills into each dim's `at`,
`failure_at`, and `failure_reason` timestamps.

The V1 panels' "Connected" pill now reads "Connected (legacy)" with
a tooltip explicitly attributing the source ("Legacy V1 status:
derived from credentials present, NOT from a real probe round-trip.
See the All Connections (V2) tab for canonical 'is this actually
callable?' truth.").

### 2.5 Main Brain experimental override (Phase B item 7)

`MainBrainPanel.tsx` already implements this rule correctly (shipped
in Phase 5 PR 2). Verified the existing behavior in this PR:

- `useConnectionsV2('cli_runtime')` provides V2 truth indexed by slug
- Set Main Brain button is `disabled` when:
  `v2 row exists AND callable === false AND experimentalOverride === false`
- The button surfaces a `title=` tooltip:
  "V2 says not callable. Probe first or enable Experimental Override."
- Backend (`PUT /api/v1/runtimes/primary`) returns
  `error.code === 'runtime_not_callable'` for blocked requests, and
  the response includes `experimental_override_used: true` when the
  override flag is honored, which the chat orchestrator audit log
  records.

No code changes needed in this PR for this rule. The audit-trail
side is already wired upstream.

### 2.6 Files modified (Phase B)

| File | Lines added | Lines removed | Why |
|---|---|---|---|
| `frontend/src/pages/ConnectionsPage.tsx` | +175 (full rewrite) | -178 (full rewrite) | Replace `useV2Flag`-routed tabs with always-V2 tabs + Show legacy / advanced toggle + LegacyAdvancedPanel container |
| `frontend/src/pages/connections/ConnectionsV2Panel.tsx` | +12 | -8 | Update Legacy mode banner copy + empty-state copy now that V1 lives behind reveal toggle |
| `frontend/src/pages/connections/McpServersV2Panel.tsx` | +6 | -5 | Empty-state copy: drop "Use the legacy /connections flows" suggestion; point to V2 import + Show legacy reveal |
| `frontend/src/pages/connections/PluginsCatalogBrowser.tsx` | +28 | -2 | Add `LEGACY_STATUS_TOOLTIP` + relabel "Connected" pill to "Connected (legacy)" with attributed tooltip; add tooltip to "Installed" + "Ready" pills |
| `frontend/src/pages/connections/MainBrainPanel.tsx` | 0 | 0 | Untouched -- rule 7 already wired correctly upstream |

### 2.7 Frontend tsc result

```text
$ cd frontend && npx tsc --noEmit
(no output, exit code 0)
```

### 2.8 Playwright smoke

No connection-specific Playwright spec exists today
(`tests/e2e/smoke_test.py` + `tests/e2e/test_full_flows.py` are
generic). Writing a new spec was out of scope for this PR per
"do not expand surface area." The tsc clean + backend pytest pass +
manual page render in dev (Vite on `:5173`, backend on `:8000`)
satisfy the verification bar for a copy + reveal-toggle PR.

Recommend a follow-up PR-CONN-E2E to add `tests/e2e/connections.spec.ts`
exercising:

- Default tab loads `ConnectionsV2Panel`
- Show legacy toggle adds the 5th tab
- Toggle OFF while on legacy tab snaps back to V2 truth tab
- localStorage key persists across reload

---

## 3. Remaining blockers before USE_CONNECTION_REGISTRY_V2 can flip in dev

The flag remains at its `.env` / `config.py` default of `False`. Per
hard rule, this PR did NOT flip it in production OR in dev. The
following items must land before the flag is safe to flip even in
dev:

| # | Blocker | Owner / next step |
|---|---|---|
| B1 | Real `CliRuntimeProbe` for `kind=cli_runtime` -- today it returns `probe_unavailable` after this PR. Until then, V2 can't replace the legacy `/runtimes` discovery endpoint for runtime-card status. | Schedule PR-CONN-CLI-PROBE: write `CliRuntimeProbe` (binary detect + version handshake + auth check), add to `install_all_probes()`, add tests |
| B2 | Real `McpServerProbe` for `kind=mcp_server` -- needs to do `initialize` + `tools/list` JSON-RPC handshake per V2 §14. Today returns `probe_unavailable`. | Schedule PR-CONN-MCP-PROBE |
| B3 | Real `PluginProbe` for `kind=plugin` -- spec depends on plugin transport (some are MCP-backed and could reuse McpServerProbe; some are HTTP-backed and need their own). | Schedule PR-CONN-PLUGIN-PROBE |
| B4 | Real `OAuthAppProbe` for `kind=oauth_app` -- needs token introspection (RFC 7662) or a harmless authenticated GET. | Schedule PR-CONN-OAUTH-PROBE |
| B5 | Real `LocalModelProbe` for `kind=local_model` -- needs model-load probe via the local LLM adapter (llama-server `/health` + `/v1/models`). | Schedule PR-CONN-LOCAL-PROBE |
| B6 | `install_all_probes()` is currently inside `_provider_v2_seed` which is gated on the flag. With probes coming for B1-B5, separate "install probes" (always) from "seed rows + auto-probe" (gated). | Schedule PR-CONN-PROBE-LIFESPAN: move `install_all_probes()` OUT of the flag-gated section in `app/main.py:606-636` |
| B7 | `MainBrainPanel` provider row uses legacy `provider.status === 'connected'` heuristic from `/runtimes` payload. When B6 lands and providers are auto-probed, switch the provider rows to V2 `callable=true` truth (mirror what cli_runtime rows already do). | Schedule PR-CONN-MAIN-BRAIN-PROVIDER-V2 |
| B8 | Reconciliation soak window is FOUNDER+ only. To debug V2 flag off in dev, a non-founder dev user can't see why their rows aren't seeded. Consider a dev-only relaxation. | Optional follow-up |

The honest summary: with this PR, **flipping the flag in dev today
would surface "probe_unavailable" on every kind except provider**.
That's an improvement over the prior lying defaults but is not a
finished V2 surface. Flipping in production requires **all** of
B1-B5 + a soak window in staging.

---

## 4. Production flag

`use_connection_registry_v2` in `backend/app/core/config.py:257`
remains `False` by default. This PR does not modify that line. No
deployment, no environment variable change, no migration.

```python
# backend/app/core/config.py:257 (unchanged)
use_connection_registry_v2: bool = False
```

---

## 5. Files changed summary

| File | Status |
|---|---|
| `backend/app/services/connection_v2/probe.py` | M |
| `backend/tests/test_connection_v2.py` | M (1 fixture line + import) |
| `backend/tests/test_connection_v2_probe_truth.py` | A (NEW, 220 lines, 8 tests) |
| `frontend/src/pages/ConnectionsPage.tsx` | M (full rewrite, ~175 lines) |
| `frontend/src/pages/connections/ConnectionsV2Panel.tsx` | M (banner + empty-state copy) |
| `frontend/src/pages/connections/McpServersV2Panel.tsx` | M (empty-state copy) |
| `frontend/src/pages/connections/PluginsCatalogBrowser.tsx` | A (workspace-hygiene fix; file existed locally untracked since Apr 30; my PR edits it) |
| `frontend/src/pages/connections/McpServersPanel.tsx` | A (workspace-hygiene fix; same; my new `LegacyAdvancedPanel` imports it) |
| `frontend/src/pages/connections/catalog.ts` | A (workspace-hygiene fix; transitive dep of `PluginsCatalogBrowser`) |
| `frontend/src/pages/connections/installFlow.ts` | A (workspace-hygiene fix; transitive dep of `PluginsCatalogBrowser`) |
| `frontend/src/pages/connections/types.ts` | A (workspace-hygiene fix; transitive dep of both V1 panels + `MainBrainPanel`) |
| `docs/Ultraview/PR_CONNECTIONS_TRUTH_CLEANUP_REPORT.md` | A (this report) |

**Workspace-hygiene note (5 V1 files):** The five V1 connections-panel
files above were present in the local working tree (since 2026-04-30)
but never `git add`-ed. The previous HEAD `ConnectionsPage.tsx`
imported `PluginsCatalogBrowser` and `McpServersPanel` directly, so
building from a clean checkout was already failing before this PR
landed. This PR commits all 5 files so the dev build is reproducible
from `git clone`. They remain `ARCHIVE_LEGACY` candidates per
`DAENA_CANONICALIZATION_PLAN.md` -- a future deletion PR moves them
to `.archive/` after the V2 panels handle 100 percent of the truth
surface and the founder authorizes the archive.

No files in the protected set (`vault_adapter.py`,
`vault_migration.py`, `oauth_credentials_store.py` per project
CLAUDE.md Rule 18) were touched.

---

## 6. Tests run

```text
Backend:
  pytest tests/test_connection_v2_probe_truth.py    8/8 PASS
  pytest tests/test_connection_v2.py               22/22 PASS  (regression)
  pytest tests/test_phase7_lifespan_seed.py         3/3 PASS  (regression)
  pytest tests/test_phase7_provider_probes.py      28/28 PASS  (regression)
  ----------------------------------------------------------
  combined                                         61/61 PASS in 0.58s

Frontend:
  npx tsc --noEmit                                 0 errors

Em-dash hygiene (project Rule 12):
  per-file diff scan across all 7 PR-3 files       0 em dashes added

Module-load smoke (fresh Python process):
  PROBE_REGISTRY size after import:                0
  NoopProbe class present:                         True
  install_noop_probes_for_tests present:           True
  Old _install_default_noop_probes removed:        True
  PROBE_UNAVAILABLE_PREFIX:                        'probe_unavailable: '
```

---

## 7. Honesty check (CLAUDE.md project Rule 17)

Every UI claim and every backend status this PR ships passes the
"where does this persist?" + "how does the user see it fail?" test:

- **V2 panel "healthy" pill**: persisted in `connection_v2.callable +
  callable_at` columns, fails visibly via per-row failing-dim line +
  details-drawer truth ladder.
- **V2 panel "Probe unavailable" sentinel**: not persisted as a
  separate column; derived in real-time from `failure_reason` prefix
  match. Honest because the prefix is a stable contract pinned in
  tests.
- **V1 panel "Connected (legacy)"**: persisted in
  `connector_instances.status` column. Now visibly attributed to the
  legacy heuristic via tooltip.
- **Show legacy / advanced toggle**: persisted in `localStorage`,
  honest about being per-browser (not synced server-side; no JSONB
  column added in this PR).
- **Main Brain experimental override**: persisted in audit log via
  `experimental_override_used` flag in the response, surfaced to
  operator via toast text and audit log entry.

Nothing in this PR is a "looks complete but does nothing" surface.
Specifically:

- No new buttons added that don't call a real endpoint.
- No new toggles added without persistence (localStorage counts as
  persistence for per-browser preference; explicitly noted in panel
  copy).
- No new "Coming Soon" badges added for surfaces that have no
  scheduled implementation -- the legacy reveal IS the scheduled
  implementation for V1 surfaces.

---

## 8. Commit message

```
canonicalization: make connections truth surface canonical
```

Single commit on branch `rebuild-connections-mcp-runtime`.

---

**Stopping here as requested. Awaiting founder direction for PR 4
(Security scan UX consolidation) per
`DAENA_CANONICALIZATION_PLAN.md` §8.**
