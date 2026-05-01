# Overnight Connections Rebuild — Wake-up Report

**Branch:** `rebuild-connections-mcp-runtime`
**Authorization:** Founder overnight autonomous mode (local dev only)
**Started:** 2026-04-30 evening from commit `27fe9d6`
**Stopped:** 2026-05-01 morning at commit `d3cc68c`
**Phases shipped:** Phase 4b PR 3, Phase 5 PR 1, Phase 5 PR 2
**Production deploy:** NOT performed (per hard-stop rules)

## TL;DR

Three phases shipped, 4 commits added on top of Phase 4b PR 2:

1. **Phase 4b PR 3 (`681cfa9`)** — Reconciliation service + API + CLI
   for soak-window drift detection between legacy `ConnectorInstance`,
   V2 `ConnectionV2`, and V2 `Secret` rows. Read-only by default;
   `apply=True` only cleans expired op-locks. Never prints secrets.
2. **Phase 5 PR 1 (`5c9b999`)** — New "All Connections (V2)" tab on
   `/connections` rendering rows directly from V2 truth tables. 6
   truth dimensions visible per row, real buttons (no dummies),
   honest "legacy mode" / "V2 truth mode" banner.
3. **Phase 5 PR 2 (`d3cc68c`)** — Backend gate on
   `PUT /api/v1/runtimes/primary` blocks Main Brain selection of
   non-callable runtimes (when V2 flag on). Founder can opt-in to
   Experimental Override (audit-logged). Frontend Main Brain panel
   surfaces V2 truth chips + last probe time + per-dim failure
   reasons.

**Tests:** 164/164 PASS across the relevant suites. Frontend `tsc` CLEAN.
**Production:** STILL BLOCKED on the same hard stops as before this
session. No prod data touched.

---

## 1. Phases completed

| Phase | Commit | What it shipped |
|---|---|---|
| 4b PR 3 | `681cfa9` | Reconciliation service + API + CLI |
| 5 PR 1 | `5c9b999` | V2 connections frontend (new default tab) |
| 5 PR 2 | `d3cc68c` | Main Brain V2 callable gate (backend + frontend) |

Pre-session baseline: `27fe9d6` (Phase 4b PR 2 — lying probes replaced
with real round-trips).

## 2. Commit SHAs

```
d3cc68c phase5: wire main brain selection to registry v2 callable runtimes
5c9b999 phase5: rebuild connections frontend on registry v2 truth
681cfa9 phase4b: add connection registry reconciliation and soak tooling
27fe9d6 phase4b: replace lying runtime probes and route connections through registry v2  ← session start
823c24b phase4b: add dev-only ConnectionRegistryV2 backend behind feature flag
f97b4ec docs: Phase 4b dev-only guardrails + migration system gap report
```

## 3. Files changed by phase

### Phase 4b PR 3 (`681cfa9`)
- `backend/app/services/connection_v2/reconciliation.py` (NEW, ~475 LOC)
- `backend/app/services/connection_v2/state_machine.py` (defensive UTC tz)
- `backend/app/api/v1/connections_v2.py` (+66 LOC, 2 endpoints)
- `backend/scripts/reconcile_connection_v2.py` (NEW, ~158 LOC CLI)
- `backend/tests/test_connection_v2_reconciliation.py` (NEW, 12 tests)
- `docs/PHASE_4B_PR3_RECONCILIATION_REPORT.md` (NEW)

### Phase 5 PR 1 (`5c9b999`)
- `frontend/src/hooks/useConnectionsV2.ts` (NEW, ~336 LOC)
- `frontend/src/pages/connections/ConnectionsV2Panel.tsx` (NEW, ~629 LOC)
- `frontend/src/pages/ConnectionsPage.tsx` (added V2 tab, set as default)
- `docs/PHASE_5_CONNECTIONS_FRONTEND_REPORT.md` (NEW)

### Phase 5 PR 2 (`d3cc68c`)
- `backend/app/api/v1/runtimes.py` (V2 callable gate inline in
  `set_primary_runtime`; `experimental_override` body field)
- `backend/tests/test_phase5_main_brain_callable_gate.py` (NEW, 7 tests)
- `frontend/src/pages/connections/MainBrainPanel.tsx` (V2 truth chips,
  failure reasons, last probe time, override toggle, button-disable rule)
- `docs/PHASE_5_MAIN_BRAIN_ROUTING_REPORT.md` (NEW)

## 4. Tests run + results

Final stabilization run (PowerShell, `D:\Ideas\Daena\backend`):

```
tests/test_phase5_main_brain_callable_gate.py     7 passed
tests/test_connection_v2_reconciliation.py       12 passed
tests/test_phase4b_pr2_probes.py                 25 passed
tests/test_connection_v2.py                      22 passed
tests/test_runtime_adapters.py                   54 passed
tests/test_yellow_runtime_gate.py                39 passed
tests/test_config_runtime.py                      5 passed
                                          --------------
                                                164 passed
```

Frontend `npx tsc --noEmit`: **CLEAN** (zero errors).

Pre-existing failures NOT touched (predate this session, unrelated to
Connections rebuild):
- `tests/test_connections.py::test_install_no_auth_connector_is_connected`
  (legacy heuristic; expects CONNECTED for no-auth connector without
  `callable_without_auth` schema flag — code returns INSTALLED)
- `tests/test_connections.py::test_extensions_install_persists_tenant_mcp_server`
  (MCP server STATUS_ACTIVE vs DISCOVERED; orthogonal to V2 work)

## 5. What is NOW actually fixed

| Before | After |
|---|---|
| Runtime adapters lied: "binary exists == online" | Real round-trip probe required to flip callable=true (Phase 4b PR 2 — already shipped before session) |
| No way to detect drift between legacy and V2 | `ConnectionReconciliationService` + CLI + API endpoints (PR 3) |
| `/connections` UI showed `connected` for any installed connector | New V2 tab shows 6 truth dims + label derived from real probe state (PR 5/1) |
| Main Brain selection accepted any installed runtime | Backend refuses non-callable runtimes when V2 flag on; founder opt-in override audit-logged (PR 5/2) |
| Operator had no visibility into vault drift | `secret_drift` reported (informational) by reconciler |
| Stale probes invisible | `stale_probe` flagged when `callable_at` older than 24h |

## 6. What is STILL not fixed

| Gap | Why not | Owner |
|---|---|---|
| Production vault migration | Hard stop — requires founder approval + operator-side `--apply` against prod DB | Founder + Operator |
| `USE_CONNECTION_REGISTRY_V2` in prod | Hard stop — flipping in prod requires operator action with full migration context | Founder + Operator |
| Provider-id (OPENAI/GEMINI/etc.) callable gate | V2 doesn't model hosted-API providers as `cli_runtime` kind yet. Gate skips them. Phase 6+. | Future Phase |
| MCP Servers tab + Plugins tab still on legacy data | Out of PR 5/1 scope — only the new V2 tab and Main Brain panel were rebuilt | Future Phase |
| Formal AuditLog entry for experimental override | Logged at WARNING level, not via the `audit_service` event hook (which doesn't have a slot for runtime-pin events yet) | Future Phase |
| HTTP-level test for `/runtimes/primary` V2 gate | Route uses `async_session_factory()` directly so test SQLite session can't reach it. Unit-level coverage in place; refactor deferred. | Future cleanup PR |

## 7. Whether live `/connections` is now using V2 truth

**Partially.**

- ✅ The new "All Connections (V2)" tab IS using V2 truth and is the
  default tab on `/connections` page load.
- ✅ Status pills, truth-ladder mini chips, and the details drawer all
  read directly from `derive_label()` over real `ConnectionV2` rows.
- ✅ Buttons (Probe / Enable / Disable / Archive) call real V2 endpoints.
- ⚠️ The 3 legacy tabs (Main Brain, Plugins, MCP Servers) still render
  alongside. Main Brain has been V2-aware (PR 5/2). Plugins +
  MCP Servers still use legacy data — out of PR scope.

## 8. Whether Main Brain switching is now real

**Yes, when `USE_CONNECTION_REGISTRY_V2=true`.**

- Backend gate refuses non-callable runtimes with a clear
  `runtime_not_callable` code + full V2 truth dump in the error
  payload.
- Frontend disables the "Set Main Brain" button and explains why
  via tooltip + inline V2 failure reason.
- Experimental Override checkbox lets founder pin a non-callable
  runtime; the backend logs `runtimes.primary_override_not_callable`
  with user_id + role + runtime_id + tenant_id.
- Successful selection persists to `User.settings.primary_runtime`
  in the JSONB column (verified by existing tests).
- Routing policy honors the persisted value via the existing
  `model_router.route_runtime` path (no changes needed there;
  gate just makes sure we don't pin a brain that won't actually
  run).

When `USE_CONNECTION_REGISTRY_V2=false` (the production default),
the gate is bypassed entirely — legacy behavior preserved.

## 9. Remaining production blockers

These have not changed during this session:

1. **`USE_CONNECTION_REGISTRY_V2`** still defaults to False in `.env`.
   Flipping it in production requires:
   - Operator runs `alembic -c migrations/alembic.ini upgrade head`
     on prod DB (creates V2 tables — currently dev-only).
   - Operator sets `DAENA_KEK` in Cloud Run Secret Manager (KEK boot
     validation will refuse to start otherwise).
   - Operator runs `python backend/scripts/migrate_vault_to_v2.py
     --dry-run` and reviews report.
   - Founder explicit approval for `--apply`.
   - 7-day soak window with reconciler showing zero drift before
     `USE_CONNECTION_REGISTRY_V2=true` flip.

2. **Vault migration `--apply`** still requires founder approval +
   operator action against prod.

3. **Legacy `vault.py`** still in place. Removal post-soak.

4. **Legacy `oauth_credentials_store.py`** still in place. Removal
   post-soak.

5. **Legacy 3 tabs on `/connections`** still render (intentional).
   Phase 6+ replaces them with V2 equivalents.

## 10. Exact next founder actions

1. **Review this report** + the 3 phase reports under `docs/`:
   - `docs/PHASE_4B_PR3_RECONCILIATION_REPORT.md`
   - `docs/PHASE_5_CONNECTIONS_FRONTEND_REPORT.md`
   - `docs/PHASE_5_MAIN_BRAIN_ROUTING_REPORT.md`
2. **Spot-check the commits** with `git log --oneline 27fe9d6..HEAD`.
3. **(Local-dev smoke)** Start backend + frontend, navigate to
   `/connections` → "All Connections (V2)" tab. Verify amber legacy-mode
   banner appears (since `.env` default is `USE_CONNECTION_REGISTRY_V2=false`).
4. **(Optional)** Set `USE_CONNECTION_REGISTRY_V2=true` in
   `backend/.env`, restart backend, confirm emerald V2-truth banner.
5. **(Optional)** Trigger a reconciliation:
   `python backend/scripts/reconcile_connection_v2.py -v`
6. **Decide on Phase 6 scope** — likely candidates:
   - Refactor `set_primary_runtime` to accept `db: AsyncSession =
     Depends(get_db)` so HTTP tests can exercise the V2 gate
   - Add `kind=provider` rows to V2 for hosted APIs (OPENAI/GEMINI/
     ANTHROPIC/...) so Main Brain gate covers them too
   - Replace MCP Servers tab + Plugins tab with V2 equivalents
   - Plan production deploy: vault migration dry-run + soak window
     scheduling
7. **NOTHING in production yet** — all hard stops still in effect.

## 11. Risky choices made while founder slept

- **Backend route uses inline V2 gate logic instead of calling a
  reusable helper.** Easier to audit in one place but duplicates
  with the bridge's `derive_legacy_status_from_v2`. Acceptable
  since the gate semantics are slightly different (refuse vs. map
  to legacy status). Refactor opportunity in Phase 6.
- **Experimental Override only logs at WARNING level.** Not a formal
  audit log entry yet. The current `audit_service` doesn't have a
  hook for runtime-pin events; adding one was out of PR scope.
  Founder visibility preserved via the WARNING line in stdout +
  any structured log sink.
- **Reconciliation `apply=True` cleans expired op-locks even when
  `tenant_id` filter is omitted.** This means a founder running with
  `all_tenants=True` could clean op-locks for tenants they don't
  own. Justified because (a) the endpoint is FOUNDER+, (b)
  expired locks are by definition garbage, (c) this is dev tooling
  with V2 flag on. Documented in the PR 3 report.
- **Frontend "Set Main Brain" button uses optimistic disable** based
  on the V2 row data the panel just polled. The backend is the
  source of truth — a stale optimistic check could let a click
  through that backend then refuses. Toast handles the refusal
  cleanly but for fairness the button could also re-fetch V2 on
  click. Minor UX improvement deferred.
- **State machine `derive_label` was patched to coerce naive
  datetimes to UTC.** SQLite drops `tzinfo` even when the column is
  `DateTime(timezone=True)`; PostgreSQL preserves it. The coercion
  is a no-op on Postgres (already tz-aware) and a correctness fix
  on SQLite (dev tests). Safe defensive change.
- **`docs/*.md` is gitignored**, so PR reports were `git add -f`'d.
  This matches the pattern of existing committed docs in the same
  directory (e.g. `ADR-002-connections-rebuild-locked-decisions.md`).

## 12. Commands founder must run manually

None for these phases. Everything that COULD be done locally was done.

For production rollout (still blocked, founder approval + operator
action required):

```bash
# On prod box:
alembic -c migrations/alembic.ini upgrade head

# Verify DAENA_KEK is set in Cloud Run Secret Manager:
gcloud run services describe daena --region=us-central1 \
  --format=json | jq '.spec.template.spec.containers[0].env'

# Dry-run migration:
python backend/scripts/migrate_vault_to_v2.py --dry-run --report-json prod-migration-dry-run.json

# Review report -- if clean, then (founder approval REQUIRED):
python backend/scripts/migrate_vault_to_v2.py --apply

# Start 7-day soak; check daily:
python backend/scripts/reconcile_connection_v2.py -v --report-json soak-day-N.json

# After zero-drift soak window:
# Set USE_CONNECTION_REGISTRY_V2=true in Cloud Run env
# Then deploy
```

## 13. Whether production is still blocked

**YES.** All 5 hard-stop conditions documented in the founder's
overnight authorization remain in effect:

- ❌ No production deploy
- ❌ No `USE_CONNECTION_REGISTRY_V2=true` in production
- ❌ No production vault `--apply`
- ❌ No `vault.py` deletion
- ❌ No `oauth_credentials_store.py` deletion

## 14. Whether old UI lies remain anywhere

**Partially.** The new V2 tab is honest. The legacy tabs are not
yet:

- ✅ "All Connections (V2)" tab — honest, renders only V2 truth
- ✅ Main Brain tab — V2-aware (chips, gate, override) when flag on
- ⚠️ Plugins / Catalog tab — still uses legacy `_status_for_install`
  heuristic (CONNECTED if has-credentials, INSTALLED otherwise).
  The backend route now derives status from V2 when the flag is on
  (Phase 4b PR 2 bridge), but the UI doesn't visually surface the
  V2 truth dims here.
- ⚠️ MCP Servers tab — uses legacy probe-auth + extension-scanner
  output. Phase 6+ replaces with V2 mcp_server kind rows.

The most honest move next: replace those two tabs in a follow-up
Phase 5 PR 3 (or Phase 6) using the `useConnectionsV2` hook with
a `kind` filter.

## 15. Final recommendation

**CONTINUE.** The V2 truth model now reaches all the critical
honesty surfaces:

- Backend probes are real (no more "binary exists == online")
- Backend status is derived from probes (no more
  "credentials exist == connected")
- Frontend shows the truth dims where it matters most (the V2 tab
  + Main Brain selection)
- Drift between legacy and V2 is detectable + reportable

What remains is mostly operator-side production work that requires
founder approval. The local dev story is complete and stable.

If founder wants more local-dev work in a later autonomous session,
the natural Phase 6 candidates are:

1. **Plugins + MCP Servers tabs on V2** — port them to
   `useConnectionsV2('plugin')` + `useConnectionsV2('mcp_server')`,
   killing the last UI lies
2. **`kind=provider` V2 rows for hosted APIs** — extends the Main
   Brain gate to OPENAI/GEMINI/ANTHROPIC selections
3. **Refactor `set_primary_runtime` for E2E tests** — make the V2
   gate HTTP-testable
4. **Formal audit_service hook** — `audit.runtime.primary_override`
   instead of WARNING log

Production rollout is on you and the operator.

---

**Generated:** 2026-05-01.
**Generated by:** Claude Code (Opus 4.7) overnight autonomous mode.
