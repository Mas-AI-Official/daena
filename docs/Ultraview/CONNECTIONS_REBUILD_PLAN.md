# Connections / MCP / Plugins / Runtime - Rebuild Plan

**Branch:** `rebuild-connections-mcp-runtime`
**Started:** 2026-04-30 17:14 UTC
**Archive root:** `archive/connections_rebuild_20260430_171410/`
**Status:** Phases 0-2 complete. Ultraview + ADR-002 lock complete (2026-04-30). Phase 3 entry criteria pending baseline acceptance. Phases 3-10 queued.

**Authoritative spec:** `docs/CONNECTIONS_MCP_PLUGIN_ARCHITECTURE_V2.md` (Draft 2)
**Locked decisions:** `docs/ADR-002-connections-rebuild-locked-decisions.md` (15 decisions D-001..D-015 -- ADR wins over V2 spec on conflict)
**Review record:** `docs/Ultraview/ULTRAVIEW_REPORT.md`

---

## Goal

Rebuild the Connections / MCP / Plugins / Runtime integration system so that **every claim the UI makes is backed by persisted, probed truth.** No row says "connected" unless a real probe + capability call succeeded. No button is dummy. No two registries diverge.

Specifically: the active `/connections` page is already clean (good news), but the substrate underneath is two parallel registries that don't agree, plus archived-but-undeleted lying siblings still in source. V2 collapses to one registry, one truth model, one no-lie discipline.

---

## Working principle (binding for every phase)

> **Archive first. Never delete first.** Every file we replace gets moved to `archive/connections_rebuild_20260430_171410/<original_path>` with a note in `CONNECTIONS_ARCHIVE_LOG.md`. This is non-negotiable.

> **Prove every claim.** We do not say a connection works unless we can show: (1) backend endpoint response, (2) DB row, (3) probe success, (4) capability call success, (5) audit log row, (6) restart-survival.

---

## Phase status

| # | Phase | Status | Deliverable | Source |
|---|---|---|---|---|
| 0 | Setup - branch + archive dir + doc skeletons | done | `rebuild-connections-mcp-runtime` branch, `archive/connections_rebuild_20260430_171410/`, `docs/_explore/` | this session |
| 1 | Map every connection/MCP/runtime file | done | `docs/_explore/01-05_*.md` (5 explorer reports) | this session |
| 1b | Synthesize file map + damage report | done | `docs/CONNECTIONS_CURRENT_DAMAGE_REPORT.md`, `docs/CONNECTIONS_FILE_MAP.md` | this session |
| 2 | Council architecture design (3 proposers + chairman synthesis) | done | `docs/_explore/06_arch_proposal_A_system.md`, `_B_security.md`, `_C_frontend.md`, `docs/CONNECTIONS_MCP_PLUGIN_ARCHITECTURE_V2.md` | this session |
| 3 | Archive old broken modules | NEXT (gated on baseline acceptance) | `docs/CONNECTIONS_ARCHIVE_LOG.md`, files moved to `archive/` | next session |
| **4a** | **Vault rewrite (per ADR-002 D-003)** | NEXT | `secrets` table + `tenants.dek_wrapped` + envelope crypto + `DAENA_KEK` env + `RefuseToBoot` + `scripts/migrate_vault_to_v2.py` | next session |
| **4b** | Registry + token + OAuth + API-key storage | NEXT (gated on 4a) | `backend/app/services/connections/*.py`, Alembic migration `006_connection_v2.py`, `connection_v2_op_lock` table, per-kind discriminated unions, delete `_status_for_install`, rename `mcp_bridge.py` -> `mcp_bridge_runtime_adapter.py` | next session(s) |
| 5 | Discovery sources - Claude / Codex / Gemini / npm / env | NEXT | `backend/app/services/connections/discovery.py` with all sources | next session |
| 6 | Frontend rebuild - `/connections` page tree (5 tabs + 2 drawers) | NEXT | `frontend/src/pages/connections/` clean tree, `useConnectionRegistry.ts` consolidated hook | next session |
| 7 | Cloudflare + Sentry reference E2E | NEXT | `docs/CLOUDFLARE_CONNECTION_E2E_REPORT.md`, `docs/SENTRY_CONNECTION_E2E_REPORT.md` | next session |
| 8 | Brain switching with real routing impact | NEXT | `docs/BRAIN_ROUTING_FIX_REPORT.md`, persisted main brain that actually changes routing | next session |
| 9 | Backend + frontend tests | NEXT | `docs/CONNECTIONS_TEST_REPORT.md`, regression tests for every lifecycle transition | next session |
| 10 | Final validation report | NEXT | `docs/CONNECTIONS_REBUILD_FINAL_REPORT.md` with proof-or-fail verdict per checklist item | final session |

---

## Chairman decisions baked into V2 (locked)

These are decisions made during Phase 2 council synthesis and **amended by ADR-002 (2026-04-30)**. They override CEO's original spec where there was conflict - see `CONNECTIONS_MCP_PLUGIN_ARCHITECTURE_V2.md` §22 for the disagreements record. **ADR-002 wins over this list and over V2 spec where they conflict.**

1. **6 boolean truth dimensions, not a 16-state enum.** `detected` / `configured` / `imported` / `reachable` / `authenticated` / `callable`. **Per-dim failure storage (ADR-002 D-001)** -- each dim has `<dim>_at` + `<dim>_failure_at` + `<dim>_failure_reason`; failure on one dim never overwrites another. **`imported=true` requires durable persistence that survives restart (ADR-002 D-007).** **14 derived labels** (was 11 -- adds `healthy_stale` and `degraded_stale` per ADR-002 D-005).
2. **One `connection_v2` SQLAlchemy table** + `connection_v2_op_lock` table for in-progress state (ADR-002 D-002). Replaces `runtimes/registry.py` (in-memory) + `runtime_truth_registry.py` (JSON) + extends `mcp_servers` table. **Per-kind Pydantic discriminated unions ship in Phase 4 (ADR-002 D-008).**
3. **Envelope-encrypted vault is a REWRITE, not extension (ADR-002 D-003).** Split into Phase 4a (vault) + Phase 4b (registry/tokens). `oauth_credentials_store.py` deleted only at end of Phase 4b after dual-read window proves zero drift.
4. **3-tier plugin trust** (OFFICIAL / COMMUNITY / UNVERIFIED). UNVERIFIED requires founder approval in ALL governance modes, including UNLEASHED. **`daena-mcp` classified OFFICIAL before Phase 9 npm publish (ADR-002 D-011).**
5. **Default governance mode for new tenants is BALANCED, not UNLEASHED.** **`governance_tier` has no silent service-layer default (ADR-002 D-013).**
6. **Page tree: 5 tabs + 2 drawers** (Brain, Catalog, Installed, MCP Servers, API Keys + Plugin Detail drawer + Audit drawer). CEO's original 10 subtabs conflated row-level concerns with nav.
7. **SSE for state changes + 60s SWR for list views.** **Stale ≠ failed -- explicit `*_stale` labels (ADR-002 D-005).**
8. **Bridge dispatch BLOCKED until Phase 2** of daena-mcp v0.2 (RCE risk in v0.1).
9. **Probe means END-CAPABILITY-CALL success, not "binary exists".** Five CLI adapters that return `ONLINE` on binary presence are the worst single offender today. **`_status_for_install` deleted in Phase 4b (ADR-002 D-010).**
10. **Codified no-lie principle** with ESLint enforcement: badge color is a pure function of backend-set boolean fields. Frontend never derives a state.
11. **Old runtimes APIs kept via WRAP layer, not 308 redirect (ADR-002 D-004).** Public route surface unchanged; deletion deferred to post-V2 cleanup phase.
12. **Catalog signing deferred to post-V2 hardening (ADR-002 D-006).** Dev/internal builds ship unsigned with banner; production signing service is a separate ADR.
13. **`mcp_bridge.py` adapter renamed to `mcp_bridge_runtime_adapter.py` (ADR-002 D-012)** to disambiguate from `mcp_sync/detector.py`.

---

## Sources of truth

| Document | Purpose |
|---|---|
| `docs/CONNECTIONS_REBUILD_PLAN.md` | THIS DOC - project plan + phase status |
| `docs/CONNECTIONS_MCP_PLUGIN_ARCHITECTURE_V2.md` | Canonical V2 architecture spec |
| `docs/CONNECTIONS_CURRENT_DAMAGE_REPORT.md` | What is broken today (with file:line evidence) |
| `docs/CONNECTIONS_FILE_MAP.md` | Every relevant file with KEEP/ARCHIVE/REWRITE/WRAP recommendation |
| `docs/_explore/01_damage_findings.md` | Synthesized prior audit findings |
| `docs/_explore/02_backend_file_map.md` | Backend file inventory |
| `docs/_explore/03_frontend_file_map.md` | Frontend file inventory |
| `docs/_explore/04_mcp_package_map.md` | daena-mcp package + discovery scripts inventory |
| `docs/_explore/05_lying_ui_findings.md` | Specific lying-UI patterns with file:line |
| `docs/_explore/06_arch_proposal_A_system.md` | Council Member A - System Architect proposal |
| `docs/_explore/06_arch_proposal_B_security.md` | Council Member B - Security & Governance proposal |
| `docs/_explore/06_arch_proposal_C_frontend.md` | Council Member C - Frontend & UX proposal |

---

## Pickup instructions for the next session

To continue this rebuild without losing context:

1. `cd D:\Ideas\Daena && git status` - confirm you are on `rebuild-connections-mcp-runtime` branch.
2. Read in this order:
   1. `docs/CONNECTIONS_REBUILD_PLAN.md` (this file - the project map)
   2. `docs/ADR-002-connections-rebuild-locked-decisions.md` (the locked founder decisions; wins over spec on conflict)
   3. `docs/CONNECTIONS_MCP_PLUGIN_ARCHITECTURE_V2.md` (the spec to implement)
   4. `docs/Ultraview/ULTRAVIEW_REPORT.md` (the review that surfaced the 15 required changes)
   5. `docs/CONNECTIONS_CURRENT_DAMAGE_REPORT.md` §"P0 - must fix before V2 ships" (the priority list)
   6. `docs/CONNECTIONS_FILE_MAP.md` §"Recommendations summary" (the action plan per file -- amended in this round)

## Phase 3 entry criteria (added per ADR-002)

Phase 3 archive operations CANNOT start until ALL of:
- [x] ADR-002 committed
- [x] V2 spec amended to match ADR-002 (per-dim failure storage, op-lock table, vault rewrite, WRAP not 308, stale ≠ failed, etc.)
- [x] File map updated (`ConnectionsMcpServers.tsx` added; `connection_service.py` reclassified REWRITE; `mcp_bridge.py` flagged for rename)
- [x] Frontend baselines recorded (tsc clean; build 1 out-of-scope error; lint 125 pre-existing errors)
- [ ] Backend pytest baseline pass/fail summary recorded (in progress at write time)
- [ ] Founder reviews pre-existing failure clusters and signs off
- [ ] `connector_catalog.json` committed (this batch)
- [ ] `gitnexus impact` run per file in ARCHIVE list (Phase 3 step 1, before any `git mv`)
- [ ] CRUD UX patterns from `ConnectionsMcpServers.tsx` reviewed for port to V2 `McpServersPanel.tsx` Tools sub-tab

Then:
3. **Phase 3 -- archive step.** Files marked ARCHIVE in the (amended) file map. Write `docs/CONNECTIONS_ARCHIVE_LOG.md` as you go (one row per archived file: original path → archive path → why → replacement file → risk → `gitnexus impact` result).
4. **Phase 4a -- vault rewrite.** Per ADR-002 D-003. Ships before Phase 4b. Existing `oauth_credentials_store.py` stays alive throughout 4a.
5. **Phase 4b -- registry / OAuth / API-key storage.** Per V2 §4, §15. Generate Alembic migration `006_connection_v2.py` with the `connection_v2` + `connection_v2_op_lock` + `connection_v2_capability` tables. Per-kind discriminated unions ship in this PR (D-008). Delete `connection_service._status_for_install` in this PR (D-010). Rename `mcp_bridge.py` -> `mcp_bridge_runtime_adapter.py` in this PR (D-012).
6. **Do not skip the archive step.** Every file in `frontend/src/pages/connections/Connections{Connectors,Extensions,Runtimes,McpServers}.tsx` must be moved (not deleted) before being replaced.

---

## Pre-Phase-3 baseline (per ADR-002 D-015)

Recorded against branch `rebuild-connections-mcp-runtime` at commit `6d3ca5e` (HEAD before doc-fix commit).

### Backend
- **Test count (collected):** 3671 tests across `backend/tests/` (verified `pytest --collect-only -q`).
- **Python:** 3.11.9 (`.venv/Scripts/python.exe`).
- **Pytest config:** `backend/pyproject.toml` (no per-test timeout plugin available; `--timeout=30` rejected by current plugin set).
- **Tests excluded from baseline run:** `tests/test_scan_workflow.py` -- this file wedges the suite (two prior runs hung at the file-collection point and timed out at 480s and 900s without producing a summary). Excluded so the rest of the suite can finish; the wedge itself is a known-failing item that needs its own ticket before Phase 4.

#### Full-suite summary (excluding test_scan_workflow.py)

```
21 failed, 3532 passed, 16 skipped, 6 warnings, 76 errors in 385.33s (0:06:25)
```

Total executed: **3645** tests (3671 collected − 26 in `test_scan_workflow.py`).

| Outcome | Count | % of executed |
|---|---|---|
| passed | 3532 | 96.9% |
| failed | 21 | 0.6% |
| errors (collection / fixture) | 76 | 2.1% |
| skipped | 16 | 0.4% |

#### Pre-existing error clusters by file (76 errors total)

All 76 errors share a common root cause: SQLAlchemy `IntegrityError` (likely tenant_id / FK fixture setup gap that pre-dates this branch). The clusters by file:

| File | Errors | Notes | In Connections-rebuild scope? |
|---|---|---|---|
| `tests/test_department_message.py` | 17 | tenant-isolated department message flow | NO |
| `tests/test_department_state.py` | 13 | tenant_id FK in `department_state` table | NO |
| `tests/test_department_policy.py` | 11 | tenant-scoped policy CRUD | NO |
| `tests/test_department_budget.py` | 9 | tenant-scoped budget proposal | NO |
| `tests/test_files_api.py` | 8 | tenant-scoped file metadata IntegrityError | NO |
| `tests/test_pipeline_service.py` | 6 | sales pipeline event emission | NO |
| `tests/test_border_signal_emits.py` | 5 | sales/marketing border signals | NO |
| `tests/test_daena_vp_integration.py` | 4 | VP / DCP integration | NO |
| `tests/test_extension_permissions.py` | 3 | extension permission save/merge | **PARTIALLY -- extension permissions are part of CMP service** |

**Out-of-scope for Connections rebuild (73/76):** department, files, pipeline, border signal, and DCP modules that the rebuild does not touch. **In-scope (3/76):** `test_extension_permissions.py` -- 3 errors. These tests will need fixture fixes or replacement when `connection_service.py` is rewritten in Phase 4b (ADR-002 D-010).

#### Pre-existing failures by name (21 failures)

| File / test | In Connections-rebuild scope? |
|---|---|
| `tests/test_3vilbob_advanced.py::TestSecurityDashboardAPI::test_load_scan_history_empty` | NO |
| `tests/test_3vilbob_advanced.py::TestSecurityDashboardAPI::test_load_scan_history_with_traces` | NO |
| `tests/test_3vilbob_wiring.py::TestSecurityDashboardAPI::test_load_scan_history_empty` | NO |
| `tests/test_audit_service_unit.py::test_chain_integrity_across_larger_sequence` | NO |
| **`tests/test_connections.py::test_install_no_auth_connector_is_connected`** | **YES -- tests the lying CONNECTED-on-no-auth behavior the rebuild kills** |
| **`tests/test_connections.py::test_extensions_install_persists_tenant_mcp_server`** | **YES -- tests current install path; will be replaced in Phase 4b** |
| `tests/test_founder_routing.py::test_founder_routing_telemetry_returns_registry_and_recent_routes` | NO |
| `tests/test_memory.py::test_recall_for_chat_prefers_session_then_user_then_explicit_tenant` | NO |
| `tests/test_memory.py::test_recall_for_chat_with_query_ranks_by_relevance` | NO |
| `tests/test_memory.py::test_recall_for_chat_without_query_uses_deterministic_sort` | NO |
| `tests/test_skill_refinery.py::test_skill_store_create` | NO |
| `tests/test_skill_refinery.py::test_skill_store_rejects_high_maturity_create` | NO |
| `tests/test_skill_refinery.py::test_skill_store_promote_and_demote` | NO |
| `tests/test_skill_refinery.py::test_skill_store_promote_at_max_fails` | NO |
| `tests/test_skill_refinery.py::test_skill_store_demote_at_min_fails` | NO |
| `tests/test_skill_refinery.py::test_skill_store_search_by_domain` | NO |
| `tests/test_skill_refinery.py::test_skill_store_list_by_maturity` | NO |
| `tests/test_skill_refinery.py::test_skill_store_archive` | NO |
| `tests/test_skill_refinery_phase2.py::test_search_skills_returns_relevant` | NO |
| `tests/test_skill_refinery_phase2.py::test_search_skills_empty_when_no_match` | NO |
| `tests/test_skill_refinery_phase2.py::test_evidence_block_integration` | NO |

**In-scope failures (2/21):** both are in `tests/test_connections.py` and they assert the lying behavior the rebuild explicitly removes. They WILL be replaced (not "fixed") in Phase 4b when `_status_for_install` is deleted (ADR-002 D-010). Treat them as expected-to-be-rewritten, not as regressions if they change shape.

#### Action required before Phase 4 starts

1. **Triage the 76 IntegrityError-class errors.** They share a root cause -- one fixture fix likely recovers all of them. Out of Connections-rebuild scope but blocking for "net delta zero" measurement. Open a ticket.
2. **Investigate `tests/test_scan_workflow.py` wedge.** Identify the hanging test and either fix or quarantine. Open a ticket.
3. **Plan replacement (not regression-fix) of the 2 in-scope `test_connections.py` failures.** Phase 4b PR includes new tests against the 6-truth-field schema; the 2 failing tests are deleted (or rewritten) in the same PR.
4. **Per CLAUDE.md Rule 7, "net delta zero failures or better"** is measured against this baseline on commit `6d3ca5e`:
   - **3532 passed / 21 failed / 76 errors / 16 skipped** (excluding `test_scan_workflow.py`).
   - Phase 4+ PRs must not regress these numbers (failures may DECREASE only if pre-existing items are fixed in scope).

### Frontend
- **`tsc --noEmit` (loose, default):** **CLEAN** -- no output before exit.
- **`npm run build` (`tsc -b && vite build`, project-references mode, stricter):** **1 TypeScript error** in out-of-scope file:
  - `src/pages/SecurityDashboardPage.tsx:298:15` -- `error TS2322: Type '(showLoader?: boolean) => Promise<void>' is not assignable to type 'MouseEventHandler<HTMLButtonElement>'`. Out-of-scope for connections rebuild; pre-existing on branch.
- **`eslint src --max-warnings 99999`:** 135 problems = **125 errors / 10 warnings**. Most are `no-empty` blocks and `@typescript-eslint/no-unused-vars` in stores and pages outside the connections tree. Treated as pre-existing baseline; the V2 ESLint `no-derived-state` rule will be additive on top of this.

### Catalog tracking (per ADR-002 D-014)
- `backend/app/config/connector_catalog.json` was **untracked** (`?? backend/app/config/connector_catalog.json`) at the start of this round.
- Committed in this batch alongside the doc fixes. Post-commit `git ls-files` will return the path.

### Recent edits to legacy files (per Ultraview H8 verification)
- `frontend/src/pages/connections/ConnectionsConnectors.tsx` -- `git log --since="7 days ago" --oneline` returned **zero commits** in last 7 days. The 2026-04-30 modtime visible in `ls -la` is from working-tree edits not yet committed. No risk of losing committed fixes by archiving.
- `frontend/src/pages/connections/ConnectionsMcpServers.tsx` -- **untracked** (`?? frontend/src/pages/connections/ConnectionsMcpServers.tsx`); zero git history; zero external imports. Confirms ADR-002 D-009 ARCHIVE classification.

### Sign-off requirement
Per founder decision 2026-04-30: Phase 3 archive operations cannot start until:
1. Final pytest pass/fail summary line is appended to this section.
2. Founder reviews the pre-existing failure clusters and acknowledges the baseline.
3. The known-failing tests are listed by name (not aggregated).

This ensures every later phase can prove non-regression against a real number, not a "all green" claim that the audit pass admits we don't have.

---

## Risk register

| # | Risk | Mitigation |
|---|---|---|
| R1 | Phase 4 backend rebuild may break existing 3086 passing tests | Run full test suite before/after each backend file change. Net delta must be zero failures or better. |
| R2 | The `mcp_servers` table generalization may conflict with prior unfinished rebuild attempt | Phase 3 archive includes the prior `models/mcp_server.py` (untracked) so we can compare; V2 schema is additive where possible |
| R3 | OAuth callback rewrite affects live tokens | Vault migration script encrypts existing `oauth_credentials_store.json` entries in place during Phase 4; rollback plan documented |
| R4 | Frontend `/connections` page consolidation may break user bookmarks | Old route paths kept as redirects for one release |
| R5 | Two-registry collapse may briefly desync during deploy | Single Alembic migration + atomic switchover; feature flag `USE_REGISTRY_V2` defaults false until cutover |

---

## Out of scope for this rebuild (explicit scope cuts)

- **Daena's chat / departments / files / dashboard pages.** Not touched. Only files where `git grep -lE "(connection|connector|mcp_|plugin|runtime|brain|model_registry)"` matches are in scope.
- **Bridge dispatch in `daena-mcp --bridge` mode.** Blocked at backend until Phase 2 of daena-mcp v0.2 (separate work).
- **Mobile/responsive polish of the new pages.** V2 is desktop-first; mobile pass is post-launch.
- **Multi-region OAuth.** Single-region for now.
- **Importing data FROM Daena INTO another platform.** This rebuild is one-way (external → Daena).

---

## Definition of done (V2 ships when…)

Phase 10 final report must show ALL of:

- [ ] Backend starts cleanly with V2 services registered
- [ ] Frontend renders `/connections` with 5 tabs + 2 drawers
- [ ] `GET /api/v1/connections/registry` returns DB-backed rows
- [ ] `GET /api/v1/connections/catalog` returns connector_catalog.json
- [ ] Import from Claude Desktop config persists rows that survive backend restart
- [ ] Probe of an MCP server runs `tools/list` JSON-RPC and respects 5s timeout
- [ ] Probe of a CLI runtime spawns `--version` AND attempts a sample chat call
- [ ] Failed probe never marks `callable=true`
- [ ] Cloudflare full E2E: discover → install → OAuth → probe → callable → audit row
- [ ] Sentry full E2E: same
- [ ] Main brain switch persists, requires `callable=true`, changes `model_router` routing
- [ ] No frontend button has empty handler
- [ ] No frontend badge derived from in-memory state alone
- [ ] All external actions emit audit rows
- [ ] No secrets printed in logs (verified by `grep -E "(token|secret|key|bearer)" backend.log` returning only redacted forms)
- [ ] Test suite: 3086 prior + new V2 tests, zero regressions
- [ ] Zero TypeScript errors

---

**Pickup signal for next session:** "Continue Daena Connections rebuild from Phase 3 archive step."
