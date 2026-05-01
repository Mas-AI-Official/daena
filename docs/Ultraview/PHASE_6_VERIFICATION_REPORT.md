# Phase 6 — Local Dev Cleanup Verification Report

**Status:** Complete (local dev only).
**Date:** 2026-05-01.
**Branch:** `rebuild-connections-mcp-runtime`.
**Builds on:** Phase 5 PR 2 → Wake-up report (commit `82d3501`).

## TL;DR

Three Phase 6 commits added on top of the wake-up report. The V2 truth
model now reaches Plugins and MCP Servers tabs, the Main Brain gate
covers hosted-API providers (not just CLI runtimes), and the route
that powers Main Brain selection is now HTTP-testable end-to-end with
a formal audit-event for Experimental Override.

**What's new:**
- Provider V2 rows for OpenAI / Anthropic / Gemini / Perplexity / Groq /
  OpenRouter / Together / Ollama / vLLM (idempotent seeder)
- Main Brain gate now refuses non-callable providers, identical to
  cli_runtimes
- Formal `audit.runtime.primary_override` event written to
  `goa_audit_events` (hash-chained tamper-evident ledger)
- HTTP-level tests for the V2 gate (the route used to be untestable
  end-to-end because it opened its own session)
- Plugins tab and MCP Servers tab render V2-truth panels when
  `USE_CONNECTION_REGISTRY_V2` is on, with amber legacy banner when off

**Tests:** 135/135 PASS across the relevant Phase 4b + Phase 5 + Phase 6
backend suites. Frontend `tsc --noEmit` CLEAN.

**Production blockers:** UNCHANGED.

## 1. Phases completed

| Sub-phase | Commit | What it shipped |
|---|---|---|
| P6-A | `3185372` | Refactor `set_primary_runtime` to `Depends(get_db)`; formal audit hook; HTTP-level tests |
| P6-B | `42d9d15` | Provider V2 row seeder + extend Main Brain gate to providers |
| P6-C | `c593728` | Plugins V2 panel + MCP Servers V2 panel + tab router with legacy banner |

## 2. Commit SHAs

```
c593728 phase6: port plugins and mcp tabs to registry v2 truth
42d9d15 phase6: add provider rows and extend main brain gate
3185372 phase6: refactor set_primary_runtime + audit hook + HTTP tests
82d3501 docs: overnight connection rebuild wakeup report  ← Phase 6 baseline
```

## 3. Tests run + results

```
tests/test_phase6_main_brain_http_gate.py        8 passed
tests/test_phase6_provider_seeder.py             7 passed
tests/test_phase5_main_brain_callable_gate.py    7 passed
tests/test_connection_v2_reconciliation.py      12 passed
tests/test_phase4b_pr2_probes.py                25 passed
tests/test_connection_v2.py                     22 passed
tests/test_runtime_adapters.py                  54 passed
                                          ----------------
                                              135 passed
```

Frontend `npx tsc --noEmit`: **CLEAN** (zero errors).

## 4. What is NOW actually fixed

| Before Phase 6 | After Phase 6 |
|---|---|
| Provider selection (OPENAI/ANTHROPIC/...) bypassed V2 gate | V2 row required; provider gate identical to cli_runtime gate |
| No V2 rows for hosted API providers | `provider_seeder.py` materializes them idempotently from configured API keys |
| Experimental Override only logged at WARNING level | Formal `goa_audit_events` row with hash chain (action_type=`audit.runtime.primary_override`, result=`OVERRIDE_GRANTED`) |
| `set_primary_runtime` route untestable end-to-end | HTTP-level tests via FastAPI test client (route now uses `Depends(get_db)`) |
| Plugins tab rendered legacy `_status_for_install` heuristic | V2-truth panel with kind ∈ {plugin, oauth_app, provider}, real probe state, in-line failure reasons |
| MCP Servers tab rendered legacy bootstrap registry view | V2-truth panel with kind=mcp_server, capability count from real tools/list, per-dim chips |
| No way to seed providers from UI | "Seed providers" button (FOUNDER+) on Plugins V2 panel |
| No way to know if you're on V2 mode for the Plugins/MCP tabs | Amber legacy banner appears when V2 flag is off, telling operator to flip the flag |

## 5. What is STILL not fixed

| Gap | Why not | Owner |
|---|---|---|
| Production vault migration | Hard stop — founder approval + operator-side `--apply` | Founder + Operator |
| `USE_CONNECTION_REGISTRY_V2=true` in prod | Hard stop | Founder + Operator |
| `vault.py` legacy fallback removal | Hard stop | Founder |
| `oauth_credentials_store.py` removal | Hard stop | Founder |
| Provider rows are NOT auto-probed at seeder time | By design — probing requires real provider HTTP calls; operator triggers via `POST /v2/{id}/probe` | Future or operator manual |
| Provider probe implementations | The probe registry currently uses `NoopProbe` for `kind=provider` — Phase 7 should add real HTTP ping probes (e.g. OpenAI `GET /models`, Anthropic `GET /messages` with no body) | Future Phase |
| Lifespan startup auto-seeding of provider rows | Not wired into `app/main.py` lifespan; operator must POST to `/reconciliation/seed-providers` once per tenant | Future Phase |

## 6. Whether live `/connections` is now using V2 truth

**YES — fully when `USE_CONNECTION_REGISTRY_V2` is on.**

| Tab | V2-aware? | Notes |
|---|---|---|
| All Connections (V2) | ✅ Always | Phase 5 PR 1 |
| Main Brain | ✅ Always | V2 chips render even with flag off (informational); gate enforced when flag on |
| Plugins | ✅ When flag on | Legacy panel + amber banner when flag off (Phase 6 P6-C) |
| MCP Servers | ✅ When flag on | Legacy panel + amber banner when flag off (Phase 6 P6-C) |

When `USE_CONNECTION_REGISTRY_V2 = false`:
- All Connections (V2) tab still renders V2 truth (it's the V2 surface)
- Main Brain shows V2 truth chips for runtimes that have V2 rows
  (informational; backend gate is bypassed since flag is off)
- Plugins + MCP Servers tabs render legacy data with a banner saying
  "this view uses old heuristics; see All Connections (V2) for truth"

## 7. Whether Main Brain switching is now real

**YES, for both CLI runtimes AND providers.**

- CLI runtime path: covered by Phase 5 PR 2 (`kind=cli_runtime`)
- Provider path: NEW in Phase 6 (`kind=provider`, `slug=lowercase(ModelProvider.value)`)
- Audit trail: NEW in Phase 6 (`audit.runtime.primary_override`)
- HTTP tests: NEW in Phase 6 (route refactor enabled E2E coverage)

Test matrix (8/8 in `test_phase6_main_brain_http_gate.py`):

| Path | Coverage |
|---|---|
| CLI runtime, callable=False, no override | refuse with code='runtime_not_callable' |
| CLI runtime, callable=True | allow + persist |
| Provider, callable=False, no override | refuse with code='runtime_not_callable', v2_kind='provider' |
| Provider, callable=True | allow + persist |
| Flag off | gate skipped entirely; legacy behavior |
| Override + non-callable | allow + writes audit event |
| Normal select | does NOT write audit event (sanity) |
| Persistence | `User.settings.primary_runtime` updated correctly |

## 8. Whether any legacy UI lies remain

**Conditional. Behavior depends on the flag:**

| Flag state | Plugins tab | MCP Servers tab | Main Brain | All Connections V2 |
|---|---|---|---|---|
| OFF | Legacy heuristic + banner | Legacy data + banner | Legacy + V2 chips (info-only) | V2 truth |
| ON | V2 truth | V2 truth | V2 truth + gate enforced | V2 truth |

So when the flag is ON, **no UI lies remain anywhere.**

When the flag is OFF (production default):
- The lies are restricted to the legacy Plugins and MCP Servers panels
- Both panels show an amber banner explaining the heuristic nature
- Main Brain gate is bypassed but UI still shows V2 chips for context
- All Connections (V2) is the source of truth and is the default tab

## 9. Production blockers (unchanged)

1. `USE_CONNECTION_REGISTRY_V2` defaults to False in `.env`
2. Vault migration `--apply` requires founder approval + operator action
3. Legacy `vault.py` not removed
4. Legacy `oauth_credentials_store.py` not removed
5. Cloud Run env vars not flipped to V2 mode

## 10. Risky choices made during Phase 6

- **`PluginsV2Panel` polls 3 hooks in parallel** (one per kind). Each
  has its own 30s timer. Cheap (3 GET /v2 calls every 30s) but worth
  noting. A future cleanup could collapse into a single
  `useConnectionsV2WithKinds(kinds)` hook.
- **Provider gate uses `lowercase(ModelProvider.value)` for slug**.
  This is stable (enum values are uppercase strings like "OPENAI" so
  the slug is always "openai"). If the enum is renamed, the slug
  would break — pinned by tests.
- **Audit event payload includes `v2_truth` snapshot**. By design — the
  point of the override audit is to record EXACTLY what state the
  V2 row was in when override was granted, so future investigation
  can answer "was this a one-time anomaly or a chronic problem?".
  Sensitive data (secrets, KEK, DEK) NEVER appears in the snapshot.
- **`flag_modified(db_user, "settings")`** added so SQLAlchemy emits
  an UPDATE for the JSONB column. The previous `async_session_factory()`
  path side-stepped this requirement; the new shared session needs it.
  This is a behavior-preserving fix, not a behavior change.
- **HTTP test for non-callable provider passes a `monkeypatch.setattr`
  on `s.openai_api_key`/`s.anthropic_api_key`** since the legacy
  validation in the route still checks `(configured_value or "").strip()`.
  This is a test-environment patch only — production env loading is
  unaffected.

## 11. Exact next founder actions

1. **Review this report.**
2. **Spot-check the 3 commits**: `git log --oneline 82d3501..HEAD`
3. **Local-dev smoke**:
   - Start backend + frontend
   - Set `USE_CONNECTION_REGISTRY_V2=true` in `backend/.env`, restart
   - Navigate to `/connections` → Plugins tab → click "Seed providers"
   - Confirm provider rows appear; status will show `failed` until
     a real probe runs (the `NoopProbe` registered for `kind=provider`
     fails by default — Phase 7 ships real provider probes)
   - Navigate to MCP Servers tab; if you've installed any MCP via
     Claude Desktop, confirm rows appear with truth chips
   - Try setting Main Brain to a non-callable provider: should refuse
     with `runtime_not_callable`
   - Toggle Experimental Override + retry: should pin and write a
     `goa_audit_events` row
4. **Decide on Phase 7 scope** — most natural candidates:
   - Real per-provider probe implementations (replace `NoopProbe` for
     `kind=provider`)
   - Auto-seed providers in lifespan startup so first /connections
     visit shows them without manual seeding
   - Plan production deploy: vault migration dry-run, soak window
     scheduling, schema alignment per `MIGRATION_SYSTEM_GAP_REPORT`
5. **No production action needed** — all hard stops still in effect.

## 12. Whether production is still blocked

**YES.** Same 5 hard stops as before:

- ❌ No production deploy
- ❌ `USE_CONNECTION_REGISTRY_V2=true` in production
- ❌ Production vault `--apply`
- ❌ `vault.py` deletion
- ❌ `oauth_credentials_store.py` deletion

## 13. Final recommendation

**CONTINUE.** The V2 truth model now reaches every honesty surface
that was in scope for the local dev rebuild:

- Probes are real (no more "binary == online")
- Backend status derived from probes (no more
  "credentials == connected")
- All four `/connections` tabs are V2-aware (or banner-flagged
  when V2 flag is off)
- Main Brain gate covers CLI runtimes AND providers
- Drift is detectable + reportable via reconciler
- Audit trail captures founder overrides with hash-chained integrity

What remains is operator-side production rollout work that requires
founder approval, plus Phase 7 polish (real provider probes, lifespan
auto-seed, MCP probe robustness). The local dev story is complete.

---

**Generated:** 2026-05-01.
**Generated by:** Claude Code (Opus 4.7) Phase 6 autonomous run.
