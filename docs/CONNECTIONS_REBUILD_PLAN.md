# Connections / MCP / Plugins / Runtime - Rebuild Plan

**Branch:** `rebuild-connections-mcp-runtime`
**Started:** 2026-04-30 17:14 UTC
**Archive root:** `archive/connections_rebuild_20260430_171410/`
**Status:** Phases 0-2 complete. Phases 3-10 queued for follow-up sessions.

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
| 3 | Archive old broken modules | NEXT | `docs/CONNECTIONS_ARCHIVE_LOG.md`, files moved to `archive/` | next session |
| 4 | Backend rebuild - registry, discovery, OAuth, probe | NEXT | `backend/app/services/connections/*.py`, Alembic migration `006_connection_v2.py` | next session(s) |
| 5 | Discovery sources - Claude / Codex / Gemini / npm / env | NEXT | `backend/app/services/connections/discovery.py` with all sources | next session |
| 6 | Frontend rebuild - `/connections` page tree (5 tabs + 2 drawers) | NEXT | `frontend/src/pages/connections/` clean tree, `useConnectionRegistry.ts` consolidated hook | next session |
| 7 | Cloudflare + Sentry reference E2E | NEXT | `docs/CLOUDFLARE_CONNECTION_E2E_REPORT.md`, `docs/SENTRY_CONNECTION_E2E_REPORT.md` | next session |
| 8 | Brain switching with real routing impact | NEXT | `docs/BRAIN_ROUTING_FIX_REPORT.md`, persisted main brain that actually changes routing | next session |
| 9 | Backend + frontend tests | NEXT | `docs/CONNECTIONS_TEST_REPORT.md`, regression tests for every lifecycle transition | next session |
| 10 | Final validation report | NEXT | `docs/CONNECTIONS_REBUILD_FINAL_REPORT.md` with proof-or-fail verdict per checklist item | final session |

---

## Chairman decisions baked into V2 (locked)

These are decisions made during Phase 2 council synthesis. They override CEO's original spec where there was conflict - see `CONNECTIONS_MCP_PLUGIN_ARCHITECTURE_V2.md` §22 for the disagreements record.

1. **6 boolean truth dimensions, not a 16-state enum.** `detected` / `configured` / `imported` / `reachable` / `authenticated` / `callable` - each with `<dim>_at` timestamp + `<dim>_failure_reason`. The 11 user-facing labels are pure functions over these.
2. **One `connection_v2` SQLAlchemy table.** Replaces `runtimes/registry.py` (in-memory) + `runtime_truth_registry.py` (JSON) + extends `mcp_servers` table.
3. **Envelope-encrypted vault** for OAuth tokens / API keys. Kills the `oauth_credentials_store.py` JSON-file debt.
4. **3-tier plugin trust** (OFFICIAL / COMMUNITY / UNVERIFIED). UNVERIFIED requires founder approval in ALL governance modes, including UNLEASHED.
5. **Default governance mode for new tenants is BALANCED, not UNLEASHED.**
6. **Page tree: 5 tabs + 2 drawers** (Brain, Catalog, Installed, MCP Servers, API Keys + Plugin Detail drawer + Audit drawer). CEO's original 10 subtabs conflated row-level concerns with nav.
7. **SSE for state changes + 60s SWR for list views.**
8. **Bridge dispatch BLOCKED until Phase 2** of daena-mcp v0.2 (RCE risk in v0.1).
9. **Probe means END-CAPABILITY-CALL success, not "binary exists".** Five CLI adapters that return `ONLINE` on binary presence are the worst single offender today.
10. **Codified no-lie principle** with ESLint enforcement: badge color is a pure function of backend-set boolean fields. Frontend never derives a state.

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
   2. `docs/CONNECTIONS_MCP_PLUGIN_ARCHITECTURE_V2.md` (the spec to implement)
   3. `docs/CONNECTIONS_CURRENT_DAMAGE_REPORT.md` §"P0 - must fix before V2 ships" (the priority list)
   4. `docs/CONNECTIONS_FILE_MAP.md` §"Recommendations summary" (the action plan per file)
3. Start Phase 3: archive the files marked ARCHIVE in the file map. Write `docs/CONNECTIONS_ARCHIVE_LOG.md` as you go (one row per archived file: original path → archive path → why → replacement file → risk).
4. Then Phase 4: build backend services per V2 §15 (API surface) and §4 (schema). Generate Alembic migration `006_connection_v2.py`.
5. **Do not skip the archive step.** Every file in `frontend/src/pages/connections/Connections{Connectors,Extensions,Runtimes}.tsx` must be moved (not deleted) before being replaced.

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
