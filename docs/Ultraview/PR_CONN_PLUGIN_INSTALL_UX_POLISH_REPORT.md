# PR-CONN-PLUGIN-INSTALL-UX-POLISH -- Report

**Branch:** `rebuild-connections-mcp-runtime`
**Commit:** (to be pinned)
**Date:** 2026-05-03
**Sprint:** DAENA-LOCAL-USABILITY-SPRINT-3 (PR-2 of 5)

---

## 1. Goal

Polish the install/test feedback loop in plugin drawers and cards so
the operator never has to read badge color or DOM mutations to know what
just happened.

---

## 2. Hard rules -- all honored

| Rule | Enforced? |
|---|---|
| Auto-refresh discovery/marketplace state after Install | YES (existing `daena:retry-pending` event) |
| Show "Next step" hint after install succeeds | YES (toast on `onComplete` carries env-var hint or "click Test") |
| Test button shows clear running/success/failure feedback | YES (button label flips to "Probing...", outcome toasts on success + failure) |
| Refresh card state if test succeeds | YES (existing `refresh()` in handleProbe) |
| Show exact failure reason + setup hint if test fails | YES (toast carries `failure_dim` + `failure_reason`) |
| Do not auto-install packages beyond operator-confirmed flow | YES (no install endpoint changes) |
| No new tabs | YES (toasts only, no new routes) |

---

## 3. Surface area (4 files, FE-only)

### `frontend/src/pages/connections/PluginsPanel.tsx`

* Imported `toast` from `@/stores/toastStore`.
* `handleProbe(rowId)` -- looked up the plugin name by rowId, then matches
  the structured probe result:
  * `ok && outcome.success` -> green "<Plugin> probe succeeded. Skills are ready..."
  * `ok && !outcome.success` -> red "<Plugin> probe failed at <dim>: <reason>"
  * `!ok` -> red "<Plugin> probe could not run: <error>"
* `handleEnable(rowId)` -- same pattern: success -> "<Plugin> enabled.
  Probe it next..." / failure -> "Could not enable <Plugin>: <error>".

### `frontend/src/pages/connections/PluginCardView.tsx`

* Imported `toast`.
* The Test button label now reads **"Probing..."** while `busy=true`
  (the only path to busy on the card is the probe action; Configure /
  Install / Connect open drawers without flipping busy).
* `MCPInstallDrawer.onComplete` now consumes the apply result and toasts:
  * post-apply probe succeeded -> green "<Plugin> installed and probe
    succeeded. Skills are ready."
  * post-apply probe did NOT succeed but env vars are required -> info
    "<Plugin> installed. Next step: Set env vars (X, Y) and click Test
    on the card."
  * otherwise -> info "<Plugin> installed. Next step: Click Test on the
    card to probe it."
* `OAuthConnectDrawer.onComplete` toasts green "<Plugin> connected.
  Click Test on the card to verify the token." (hand-off hint).

### Why these toasts are honest

* They carry the EXACT `failure_dim` + `failure_reason` from the probe
  outcome -- no rewording, no marketing copy.
* The "Next step" lines reference real follow-up actions (Test button,
  env-var copy) the operator can immediately do.
* Success toasts say "Skills are ready" only when the probe actually
  flipped `callable=true` (the existing PR-CONN-PLUGIN-SKILLS-UX-WIRING
  drawer already showed this; the toast just makes it asynchronous-safe
  for an operator who looked away).

---

## 4. Test result

```
$ .venv/Scripts/python.exe -m pytest tests/test_connection_v2_marketplace.py
98 passed in 5.86s

$ .venv/Scripts/python.exe -m pytest tests/test_connections.py tests/test_skill_executor_phase2.py
83 passed in 51.03s

$ npx tsc --noEmit
(no output)
```

PR-2 is frontend-only -- no backend tests modified or added (no logic
changed; toasts are presentation layer). The marketplace + connections
+ phase2 invariants from prior sprints all stay green.

---

## 5. What did NOT change

* No changes to any backend service or endpoint.
* No new dependencies, no install, no production deploy.
* No changes to Brain tab / Connections page layout / drawer information
  density. Only the post-action surfaces (button label, toasts).
* Failure-reason rendering INSIDE the card (line 247-252) and INSIDE the
  drawer's `TestStep` block are untouched -- the toasts are an additive
  safety net, not a replacement.

---

## 6. What's still imperfect (not fixed in this PR)

* Toast de-duplication is global (toast store collapses identical
  message + type within the visible window). If the operator probes the
  same plugin twice and both fail with the same reason, only one toast
  shows. This is intentional store behavior from a prior PR; not worth
  changing in PR-2.
* The Test button label only flips to "Probing..." for the card-level
  Test action. The detail-drawer footer button still uses the icon-only
  spinner pattern. Could match in a follow-up.
