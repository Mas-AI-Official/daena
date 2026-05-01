# Pre-Phase-4a Dirty Working Tree Inventory

**Branch:** `rebuild-connections-mcp-runtime`
**HEAD at inventory time:** `f2a30a3` (post Phase 3 + OAuthSetupModal supplement)
**Original total files dirty:** 194 (109 modified, 82 untracked, 3 deleted)
**Generated:** 2026-04-30
**Cleanup batch update:** 2026-04-30 (post hygiene commits B + C)

> Per founder pre-Phase-4a hygiene checkpoint instruction.

---

## CLEANUP BATCH UPDATE (2026-04-30)

Two prerequisite hygiene commits landed per founder option B:

| Commit | Title | Files committed |
|---|---|---|
| `4d97f88` | `pre-phase4a: land prerequisite migrations 003-005` | 3 backend migration files (003 workstreams, 004 chat-session FK, 005 cron/mcp/background) |
| `7862991` | `pre-phase4a: sync approved skills artifacts` | 62 files across 27 skill dirs (per CLAUDE.md SKILLS SYNC RULE) |

**Post-cleanup dirty count: 164** (109 modified, 52 untracked, 3 deleted).

Net change vs original 194: **-30** (3 migrations + 27 skill dirs reduced 27 untracked entries; 62 underlying skill files were rolled into 27 entries by `git status --short` directory shorthand).

### What was deliberately NOT committed in cleanup

- The 4 NEEDS_FOUNDER_DECISION files (main.py, models/__init__.py, core/database.py, core/constants.py) -- founder picked option B which routes them to a follow-up cleanup commit, not this batch.
- The model files referenced by the new migrations (workstream.py, cron_run.py, mcp_server.py, background_task.py) -- they remain dirty/untracked. Migrations apply cleanly without them (CREATE TABLE is self-contained), but app code that queries the new tables stays broken until Phase 4b lands its model commit.
- All 36 KEEP_DIRTY_FOR_PHASE4B files -- left dirty intentionally for Phase 4b absorption.
- All 50+ frontend modifications outside scope -- deferred until founder reviews per-file diffs.

### Updated recommendation summary (164 remaining files)

| Recommendation | Was | Now |
|---|---|---|
| `COMMIT_SEPARATE_BEFORE_PHASE4A` | 150 | **120** (subtract 3 migrations + 27 skill dirs) |
| `KEEP_DIRTY_FOR_PHASE4B` | 36 | **36** (unchanged) |
| `IGNORE_FOR_NOW` | 4 | **4** (unchanged) |
| `NEEDS_FOUNDER_DECISION` | 4 | **4** (unchanged) |
| **TOTAL** | **194** | **164** |

### Updated Phase 4a risk assessment

`backend/app/core/vault.py` is still NOT in the dirty list. Cipher rewrite has clean starting point.

The 4 NEEDS_FOUNDER_DECISION files (main.py + models/__init__.py + core/database.py + core/constants.py) are still dirty. Per the option (C) recommendation in the original §9 of this doc: Phase 4a's first PR should restrict to NET-NEW files only:
- `backend/app/core/vault_v2.py` (or rewrite of vault.py to envelope crypto)
- `backend/app/models/secret.py` (new SQLAlchemy model)
- `backend/migrations/versions/006_secrets_envelope_vault.py` (new migration; numerically follows the just-landed 005)
- `scripts/migrate_vault_to_v2.py` (one-shot re-encryption tool)

These additions do NOT touch the 4 dirty hot-path files, so Phase 4a's first PR is safe to land on top of the current dirty tree.

The hot-path edits (registering Secret in models/__init__.py, RefuseToBoot in main.py, KEK boot log) move to a Phase 4a follow-up PR, gated on a separate hygiene commit for those 4 files.

**Phase 4a green-light criteria:**
- [x] Migrations 003-005 committed (`4d97f88`)
- [x] Skills synced (`7862991`)
- [x] No vault file in dirty list
- [x] No vault-related file in dirty list
- [ ] First Phase-4a PR restricted to NET-NEW files (procedural, enforced at PR time)
- [ ] Founder decides timing of the 4 NEEDS_FOUNDER_DECISION files (before second Phase-4a PR)

---

## 1. Summary by area + status

| Area | M | ?? | D | Total |
|---|---|---|---|---|
| backend (app code) | 49 | 23 | 1 | 73 |
| backend_test | 4 | 5 | 0 | 9 |
| backend_script | 0 | 4 | 0 | 4 |
| backend_migration | 0 | 3 | 0 | 3 |
| frontend | 50 | 15 | 2 | 67 |
| skills | 0 | 27 | 0 | 27 |
| packages | 2 | 4 | 0 | 6 |
| docs | 0 | 0 | 0 | 0 |
| scripts | 0 | 1 | 0 | 1 |
| meta (axon) | 2 | 0 | 0 | 2 |
| root_doc (CLAUDE.md, AGENTS.md) | 2 | 0 | 0 | 2 |
| **TOTAL** | **109** | **82** | **3** | **194** |

## 2. Summary by recommendation (founder enum)

| Recommendation | Count |
|---|---|
| `COMMIT_SEPARATE_BEFORE_PHASE4A` | 150 |
| `KEEP_DIRTY_FOR_PHASE4B` | 36 |
| `IGNORE_FOR_NOW` | 4 (axon meta + CLAUDE.md + AGENTS.md) |
| `NEEDS_FOUNDER_DECISION` | 4 |
| `RESET_AFTER_BACKUP` | 0 |
| **TOTAL** | **194** |

## 3. NEEDS_FOUNDER_DECISION (4 — critical Phase 4a hot-path files)

These four files are modified in the dirty tree AND are very likely to be touched by Phase 4a (vault rewrite). If Phase 4a starts without resolving them, the Phase-4a diff will sit on top of unrelated Codex edits, producing a hard-to-review PR and possible merge conflicts.

| Path | Why critical for Phase 4a | Suggested resolution |
|---|---|---|
| `backend/app/main.py` | Phase 4a must add `RefuseToBoot` on missing `DAENA_KEK` in cloud mode + `vault.kek_loaded` log line at startup. The dirty version contains uncommitted Codex changes (pipeline / heartbeat wiring). | Review the dirty diff. If it's stable -> commit-separate. If unfinished -> reset hunks unrelated to Phase 4a, leave the rest. |
| `backend/app/models/__init__.py` | Phase 4a will register the new `Secret` SQLAlchemy model. Dirty version has Codex-added imports for new models. | Same as main.py. |
| `backend/app/core/database.py` | Phase 4a may add tenant-scoped query helpers + `secrets` table init. | Review dirty diff for compatibility with envelope encryption. |
| `backend/app/core/constants.py` | Phase 4a will add `DAENA_KEK` env-var name + secret class constants. Dirty version has Codex-added constants. | Review for naming collisions with planned Phase 4a additions. |

`backend/app/core/vault.py` itself is **NOT in the dirty list** -- the Phase 4a rewrite has a clean starting point for the cipher path.

## 4. KEEP_DIRTY_FOR_PHASE4B (36 — Phase 4b will rewrite these anyway)

These are exactly the files the V2 spec + ADR-002 D-010, D-012 plan to rewrite/rename in Phase 4b. Pre-committing them now creates merge conflicts when Phase 4b lands. Letting Phase 4b absorb them is cleaner.

Includes: 18 backend modified files (`connections.py`, `connector_oauth.py`, `mcp_*.py`, `runtimes.py`, `model_*.py`, all 3 CLI adapters in scope, `connection_service.py`, `oauth_service.py`, `test_connections.py`, etc.); 11 backend untracked files (`connector_install.py`, `policies.py`, `runtime.py`, `mcp_server.py` model, `runtime_truth_registry.py`, migration 005, 2 catalog tests, etc.); 2 frontend untracked directory roots (`pages/connections/`, `components/connections/`) covering the V2 surface; 4 packages/daena-mcp untracked files; 4 skills/connector-* directories.

**These also include the 7 Phase-3-archived files' originals -- those are now under archive/ + tracked there; they no longer appear in the dirty list at the original path.**

## 5. COMMIT_SEPARATE_BEFORE_PHASE4A (150 — independent uncommitted work)

The bulk of the dirty tree. Most are Codex pass output from 2026-04-29 documented in `docs/SESSION-LOG.md` as completed but uncommitted. They are independent of the connections rebuild and of Phase 4a's vault work. They include:

- 30+ frontend pages outside `pages/connections/` (DashboardPage, ChatPage, AnalyticsPage, etc.)
- 15+ frontend components, hooks, stores
- 25+ backend API/service files outside the rebuild scope (heartbeat, pipeline, security_dashboard, soul_engine, scan_workflow, etc.)
- 27 skills/* untracked directories (Codex skill scrapes per CLAUDE.md SKILLS SYNC RULE)
- 9 backend test files (4 modified, 5 untracked)
- 4 backend script files
- 3 backend migration files (003_add_workstreams, 004_add_chat_session_workstream_fk, 005_add_cron_mcp_background_tables)
- 3 deleted files (`backend/app/api/v1/ws.py`, `frontend/src/pages/DaenaBotPage.tsx`, `frontend/src/pages/FounderPage.tsx`)
- Frontend `AUDIT_2026-04-25.md` (top-level)
- `packages/daena-mcp/README.md`, `package-lock.json`, etc.

Recommended: a separate **"hygiene commit"** to land these BEFORE Phase 4a starts. It does not affect Phase 4a's design but keeps Phase 4a diffs reviewable. The hygiene commit should be split into 2-4 logical commits by area (frontend pages, backend services, skill scrapes, migrations) for review hygiene.

**Warning:** Some of the modified frontend/backend files may contain incomplete Codex work (per SESSION-LOG entries that explicitly admit "Blocked: npm/typecheck/lint/build/dev launch blocked by Node CSPRNG assertion" -- meaning the Codex passes never verified their changes built/passed tests). Review each before committing. Recovery option: `git diff <file>` per suspect file; reset hunks that look unfinished.

## 6. IGNORE_FOR_NOW (4)

| Path | Why ignore |
|---|---|
| `.axon/meta.json` | Auto-regenerated by code-review-graph; will be rebuilt by SessionStart hook. |
| `backend/.axon/meta.json` | Same. |
| `CLAUDE.md` | User-managed (founder edits directly). Not Claude Code's lane to commit. |
| `AGENTS.md` | User-managed (per AGENTS standard). Same. |

## 7. RESET_AFTER_BACKUP (0)

No file in the dirty tree is recommended for reset. The 3 deletions (`ws.py`, `DaenaBotPage.tsx`, `FounderPage.tsx`) are intentional removals from prior sessions; they should be committed alongside their replacement work in the COMMIT_SEPARATE batch, not reverted.

---

## 8. Per-file table (all 194 entries)

| # | path | status | area | source | p4a? | p4b? | risk | recommendation |
|---|---|---|---|---|---|---|---|---|
| 1 | `.axon/meta.json` | M | meta | auto-regenerated | - | - | low (auto-regen) | **IGNORE_FOR_NOW** |
| 2 | `AGENTS.md` | M | root_doc | user-managed | - | - | low | **IGNORE_FOR_NOW** |
| 3 | `CLAUDE.md` | M | root_doc | user-managed | - | - | low | **IGNORE_FOR_NOW** |
| 4 | `backend/.axon/meta.json` | M | meta | auto-regenerated | - | - | low (auto-regen) | **IGNORE_FOR_NOW** |
| 5 | `backend/app/api/v1/__init__.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 6 | `backend/app/api/v1/agent_ops.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 7 | `backend/app/api/v1/analytics.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 8 | `backend/app/api/v1/autopilot.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 9 | `backend/app/api/v1/company_mode.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 10 | `backend/app/api/v1/connections.py` | M | backend | Codex 2026-04-29 connections rebuild prep | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 11 | `backend/app/api/v1/connector_oauth.py` | M | backend | Codex 2026-04-29 connections rebuild prep | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 12 | `backend/app/api/v1/governance.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 13 | `backend/app/api/v1/health.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 14 | `backend/app/api/v1/heartbeat.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 15 | `backend/app/api/v1/mcp_sync.py` | M | backend | Phase 0-2 V2 work (untracked) | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 16 | `backend/app/api/v1/memory.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 17 | `backend/app/api/v1/pipeline.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 18 | `backend/app/api/v1/runtimes.py` | M | backend | Codex 2026-04-29 connections rebuild prep | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 19 | `backend/app/api/v1/security_dashboard.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 20 | `backend/app/api/v1/ws.py` | D | backend | Prior session deletion (uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 21 | `backend/app/config/dcps.json` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 22 | `backend/app/core/constants.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | HIGH -- Phase 4a may need to register new models / lifespan here | **NEEDS_FOUNDER_DECISION** |
| 23 | `backend/app/core/database.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | HIGH -- Phase 4a may need to register new models / lifespan here | **NEEDS_FOUNDER_DECISION** |
| 24 | `backend/app/core/websocket.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 25 | `backend/app/main.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | HIGH -- Phase 4a may need to register new models / lifespan here | **NEEDS_FOUNDER_DECISION** |
| 26 | `backend/app/models/__init__.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | HIGH -- Phase 4a may need to register new models / lifespan here | **NEEDS_FOUNDER_DECISION** |
| 27 | `backend/app/models/chat.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 28 | `backend/app/schemas/connections.py` | M | backend | Codex 2026-04-29 connections rebuild prep | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 29 | `backend/app/services/approval.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 30 | `backend/app/services/auth.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 31 | `backend/app/services/autopilot/__init__.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 32 | `backend/app/services/autopilot/background_queue.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 33 | `backend/app/services/chat_orchestrator.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 34 | `backend/app/services/connection_service.py` | M | backend | Codex 2026-04-29 connections rebuild prep | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 35 | `backend/app/services/heartbeat/cron_scheduler.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 36 | `backend/app/services/heartbeat/heartbeat_checks.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 37 | `backend/app/services/heartbeat/heartbeat_daemon.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 38 | `backend/app/services/integrations/oauth_service.py` | M | backend | Codex 2026-04-29 connections rebuild prep | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 39 | `backend/app/services/llm_service.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 40 | `backend/app/services/mcp_invoker.py` | M | backend | Codex 2026-04-29 connections rebuild prep | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 41 | `backend/app/services/mcp_registry.py` | M | backend | Codex 2026-04-29 connections rebuild prep | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 42 | `backend/app/services/model_registry.py` | M | backend | Codex 2026-04-29 connections rebuild prep | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 43 | `backend/app/services/model_router.py` | M | backend | Codex 2026-04-29 connections rebuild prep | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 44 | `backend/app/services/pipeline_service.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 45 | `backend/app/services/providers/claude_cli.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 46 | `backend/app/services/runtimes/adapters/claude_code.py` | M | backend | Codex 2026-04-29 connections rebuild prep | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 47 | `backend/app/services/runtimes/adapters/claude_session.py` | M | backend | Codex 2026-04-29 connections rebuild prep | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 48 | `backend/app/services/runtimes/adapters/codex.py` | M | backend | Codex 2026-04-29 connections rebuild prep | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 49 | `backend/app/services/runtimes/registry.py` | M | backend | Codex 2026-04-29 connections rebuild prep | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 50 | `backend/app/services/security/install_scanner.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 51 | `backend/app/services/security/scan_workflow.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 52 | `backend/app/services/security_gate.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 53 | `backend/app/services/soul_engine.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 54 | `backend/run.py` | M | backend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 55 | `backend/tests/test_agent_ops.py` | M | backend_test | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 56 | `backend/tests/test_connections.py` | M | backend_test | Codex 2026-04-29 connections rebuild prep | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 57 | `backend/tests/test_dcp_loader.py` | M | backend_test | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 58 | `backend/tests/test_heartbeat.py` | M | backend_test | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 59 | `frontend/src/App.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 60 | `frontend/src/components/chat/ChatInput.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 61 | `frontend/src/components/chat/MessageBubble.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 62 | `frontend/src/components/chat/RuntimeSwapper.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 63 | `frontend/src/components/chat/SlashCommands.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 64 | `frontend/src/components/chat/ThinkingProcess.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 65 | `frontend/src/components/common/Button.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 66 | `frontend/src/components/execution/ExecutionPanel.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 67 | `frontend/src/components/icons/BrandIcons.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 68 | `frontend/src/components/layout/Header.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 69 | `frontend/src/components/layout/PageLayout.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 70 | `frontend/src/lib/api.ts` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 71 | `frontend/src/lib/mutations.ts` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 72 | `frontend/src/pages/AccountPage.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 73 | `frontend/src/pages/AnalyticsPage.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 74 | `frontend/src/pages/ChatPage.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 75 | `frontend/src/pages/CompanyModePage.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 76 | `frontend/src/pages/ConnectionsPage.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 77 | `frontend/src/pages/DaenaBotPage.tsx` | D | frontend | Prior session deletion (uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 78 | `frontend/src/pages/DashboardPage.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 79 | `frontend/src/pages/DepartmentChatPage.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 80 | `frontend/src/pages/DepartmentsPage.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 81 | `frontend/src/pages/EngagementConsolePage.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 82 | `frontend/src/pages/FilesPage.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 83 | `frontend/src/pages/FounderPage.tsx` | D | frontend | Prior session deletion (uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 84 | `frontend/src/pages/GovernanceApprovalsPage.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 85 | `frontend/src/pages/GovernanceAuditPage.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 86 | `frontend/src/pages/MindDetailPage.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 87 | `frontend/src/pages/MindsPage.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 88 | `frontend/src/pages/PipelinePage.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 89 | `frontend/src/pages/PoliciesPage.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 90 | `frontend/src/pages/ProjectDetailPage.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 91 | `frontend/src/pages/ProjectsPage.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 92 | `frontend/src/pages/ScanPage.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 93 | `frontend/src/pages/ScanWalkthroughPage.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 94 | `frontend/src/pages/SecurityDashboardPage.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 95 | `frontend/src/pages/SecurityScopePage.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 96 | `frontend/src/pages/SettingsPage.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 97 | `frontend/src/pages/SkillsPage.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 98 | `frontend/src/pages/TasksPage.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 99 | `frontend/src/pages/account/AccountApiKeys.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 100 | `frontend/src/pages/settings/SettingsBilling.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 101 | `frontend/src/pages/settings/SettingsDeveloper.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 102 | `frontend/src/pages/settings/SettingsGeneral.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 103 | `frontend/src/pages/settings/SettingsGovernance.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 104 | `frontend/src/pages/settings/SettingsHeartbeat.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 105 | `frontend/src/pages/settings/SettingsMemory.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 106 | `frontend/src/pages/settings/SettingsModelsRuntimes.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 107 | `frontend/src/pages/settings/SettingsNotifications.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 108 | `frontend/src/providers/VoiceProvider.tsx` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 109 | `frontend/src/stores/authStore.ts` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 110 | `frontend/src/styles/globals.css` | M | frontend | Codex 2026-04-29 (per SESSION-LOG) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 111 | `packages/daena-mcp/package.json` | M | packages | Codex 2026-04-29 connections rebuild prep | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 112 | `packages/daena-mcp/src/index.ts` | M | packages | Codex 2026-04-29 connections rebuild prep | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 113 | `backend/app/api/v1/connector_install.py` | ?? | backend | Phase 0-2 V2 work (untracked) | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 114 | `backend/app/api/v1/policies.py` | ?? | backend | Plain-English Policy Compiler work (uncommitted) | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 115 | `backend/app/api/v1/runtime.py` | ?? | backend | Phase 0-2 V2 work (untracked) | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 116 | `backend/app/api/v1/workstreams.py` | ?? | backend | Workstream feature work (uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 117 | `backend/app/config/pii_blocklist.yaml` | ?? | backend | Codex pass (untracked, uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 118 | `backend/app/core/db_concurrent.py` | ?? | backend | Codex pass (untracked, uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 119 | `backend/app/core/sse_channels.py` | ?? | backend | Codex pass (untracked, uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 120 | `backend/app/core/startup_state.py` | ?? | backend | Codex pass (untracked, uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 121 | `backend/app/models/background_task.py` | ?? | backend | Codex pass (untracked, uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 122 | `backend/app/models/cron_run.py` | ?? | backend | Codex pass (untracked, uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 123 | `backend/app/models/mcp_server.py` | ?? | backend | Phase 0-2 V2 work (untracked) | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 124 | `backend/app/models/workstream.py` | ?? | backend | Workstream feature work (uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 125 | `backend/app/services/cognition/completeness_probe.py` | ?? | backend | Cognition pass (uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 126 | `backend/app/services/company_context.py` | ?? | backend | Codex pass (untracked, uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 127 | `backend/app/services/pii_guard.py` | ?? | backend | Plain-English Policy Compiler work (uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 128 | `backend/app/services/policy_compiler.py` | ?? | backend | Plain-English Policy Compiler work (uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 129 | `backend/app/services/policy_store.py` | ?? | backend | Plain-English Policy Compiler work (uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 130 | `backend/app/services/runtime_truth_registry.py` | ?? | backend | Phase 0-2 V2 work (untracked) | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 131 | `backend/app/services/web_eyes.py` | ?? | backend | Cognition pass (uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 132 | `backend/app/services/workstream_redirect_parser.py` | ?? | backend | Workstream feature work (uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 133 | `backend/app/services/workstream_service.py` | ?? | backend | Workstream feature work (uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 134 | `backend/bin/` | ?? | backend | Codex pass (untracked, uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 135 | `backend/migrations/versions/003_add_workstreams.py` | ?? | backend_migration | Workstream feature work (uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 136 | `backend/migrations/versions/004_add_chat_session_workstream_fk.py` | ?? | backend_migration | Workstream feature work (uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 137 | `backend/migrations/versions/005_add_cron_mcp_background_tables.py` | ?? | backend_migration | Codex 2026-04-29 connections rebuild prep | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 138 | `backend/scripts/cleanup_codex_stderr_leak.py` | ?? | backend_script | Codex pass (untracked, uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 139 | `backend/scripts/council_perplexity.py` | ?? | backend_script | Codex pass (untracked, uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 140 | `backend/scripts/smoke_workstream_service.py` | ?? | backend_script | Workstream feature work (uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 141 | `backend/scripts/verify_primary_mind_picker.py` | ?? | backend_script | Codex pass (untracked, uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 142 | `backend/tests/services/` | ?? | backend_test | Codex pass (untracked, uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 143 | `backend/tests/test_connector_catalog_api.py` | ?? | backend_test | Codex 2026-04-29 connections rebuild prep | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 144 | `backend/tests/test_connector_catalog_seed.py` | ?? | backend_test | Codex 2026-04-29 connections rebuild prep | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 145 | `backend/tests/test_no_shared_session_gather.py` | ?? | backend_test | Codex pass (untracked, uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 146 | `backend/tests/test_workstream_service.py` | ?? | backend_test | Workstream feature work (uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 147 | `backend/testssl.sh/` | ?? | backend | Codex pass (untracked, uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 148 | `frontend/AUDIT_2026-04-25.md` | ?? | frontend | Codex pass (untracked, uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 149 | `frontend/src/components/common/BackendOfflineBanner.tsx` | ?? | frontend | Codex pass (untracked, uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 150 | `frontend/src/components/common/ConnectionStatusIndicator.tsx` | ?? | frontend | Codex pass (untracked, uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 151 | `frontend/src/components/connections/` | ?? | frontend | Phase 0-2 V2 work (untracked) | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 152 | `frontend/src/components/policies/` | ?? | frontend | Plain-English Policy Compiler work (uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 153 | `frontend/src/hooks/useApprovalsStream.ts` | ?? | frontend | Codex pass (untracked, uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 154 | `frontend/src/hooks/useConnectorCatalog.ts` | ?? | frontend | Codex pass (untracked, uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 155 | `frontend/src/hooks/useRuntimeRegistry.ts` | ?? | frontend | Codex pass (untracked, uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 156 | `frontend/src/lib/sse.ts` | ?? | frontend | Codex pass (untracked, uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 157 | `frontend/src/pages/WorkstreamsPage.tsx` | ?? | frontend | Workstream feature work (uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 158 | `frontend/src/pages/connections/` | ?? | frontend | Phase 0-2 V2 work (untracked) | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 159 | `frontend/src/pages/scan/` | ?? | frontend | Security pass (uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 160 | `frontend/src/pages/security/` | ?? | frontend | Security pass (uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 161 | `frontend/src/stores/backendHealthStore.ts` | ?? | frontend | Codex pass (untracked, uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 162 | `frontend/src/stores/errorStore.ts` | ?? | frontend | Codex pass (untracked, uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 163 | `packages/daena-mcp/README.md` | ?? | packages | Codex 2026-04-29 connections rebuild prep | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 164 | `packages/daena-mcp/package-lock.json` | ?? | packages | Codex 2026-04-29 connections rebuild prep | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 165 | `packages/daena-mcp/src/daena-client.ts` | ?? | packages | Codex 2026-04-29 connections rebuild prep | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 166 | `packages/daena-mcp/src/tools/` | ?? | packages | Codex 2026-04-29 connections rebuild prep | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 167 | `scripts/scrape_codex_plugins.py` | ?? | scripts | Codex pass (untracked, uncommitted) | - | - | low (out-of-scope, independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 168 | `skills/approval-feedback-loop/` | ?? | skills | Codex skill scrape (per SKILLS SYNC RULE) | - | - | low (independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 169 | `skills/auto-browser/` | ?? | skills | Codex skill scrape (per SKILLS SYNC RULE) | - | - | low (independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 170 | `skills/autobrowse/` | ?? | skills | Codex skill scrape (per SKILLS SYNC RULE) | - | - | low (independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 171 | `skills/career-ops/` | ?? | skills | Codex skill scrape (per SKILLS SYNC RULE) | - | - | low (independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 172 | `skills/codex-browser-use/` | ?? | skills | Codex skill scrape (per SKILLS SYNC RULE) | - | - | low (independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 173 | `skills/codex-claude-md-management/` | ?? | skills | Codex skill scrape (per SKILLS SYNC RULE) | - | - | low (independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 174 | `skills/codex-hookify/` | ?? | skills | Codex skill scrape (per SKILLS SYNC RULE) | - | - | low (independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 175 | `skills/codex-plugin-dev/` | ?? | skills | Codex skill scrape (per SKILLS SYNC RULE) | - | - | low (independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 176 | `skills/codex-skill-creator/` | ?? | skills | Codex skill scrape (per SKILLS SYNC RULE) | - | - | low (independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 177 | `skills/connector-cloudflare/` | ?? | skills | Codex skill scrape (per SKILLS SYNC RULE) | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 178 | `skills/connector-figma/` | ?? | skills | Codex skill scrape (per SKILLS SYNC RULE) | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 179 | `skills/connector-gmail/` | ?? | skills | Codex skill scrape (per SKILLS SYNC RULE) | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 180 | `skills/connector-slack/` | ?? | skills | Codex skill scrape (per SKILLS SYNC RULE) | - | Y | medium -- Phase 4b will rewrite/collide | **KEEP_DIRTY_FOR_PHASE4B** |
| 181 | `skills/debate/` | ?? | skills | Codex skill scrape (per SKILLS SYNC RULE) | - | - | low (independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 182 | `skills/exam-form-filler/` | ?? | skills | Codex skill scrape (per SKILLS SYNC RULE) | - | - | low (independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 183 | `skills/heygem-avatar/` | ?? | skills | Codex skill scrape (per SKILLS SYNC RULE) | - | - | low (independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 184 | `skills/ltx-gpu-config/` | ?? | skills | Codex skill scrape (per SKILLS SYNC RULE) | - | - | low (independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 185 | `skills/news-to-video/` | ?? | skills | Codex skill scrape (per SKILLS SYNC RULE) | - | - | low (independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 186 | `skills/predict-build-vs-buy/` | ?? | skills | Codex skill scrape (per SKILLS SYNC RULE) | - | - | low (independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 187 | `skills/remotion-composition/` | ?? | skills | Codex skill scrape (per SKILLS SYNC RULE) | - | - | low (independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 188 | `skills/scraper-architecture/` | ?? | skills | Codex skill scrape (per SKILLS SYNC RULE) | - | - | low (independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 189 | `skills/social-media-browser-puppeteer/` | ?? | skills | Codex skill scrape (per SKILLS SYNC RULE) | - | - | low (independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 190 | `skills/twitterapi-io/` | ?? | skills | Codex skill scrape (per SKILLS SYNC RULE) | - | - | low (independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 191 | `skills/universal-shortform-director/` | ?? | skills | Codex skill scrape (per SKILLS SYNC RULE) | - | - | low (independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 192 | `skills/video-hook/` | ?? | skills | Codex skill scrape (per SKILLS SYNC RULE) | - | - | low (independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 193 | `skills/wan2gp-8gb/` | ?? | skills | Codex skill scrape (per SKILLS SYNC RULE) | - | - | low (independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |
| 194 | `skills/winning-pitch-deck/` | ?? | skills | Codex skill scrape (per SKILLS SYNC RULE) | - | - | low (independent) | **COMMIT_SEPARATE_BEFORE_PHASE4A** |

---

## 9. Phase 4a safety verdict

`backend/app/core/vault.py` is NOT in the dirty list. The Phase 4a vault rewrite has a clean starting point on the **cipher path itself**.

However, Phase 4a will likely need to touch 4 surrounding hot-path files that ARE dirty: `main.py`, `models/__init__.py`, `core/database.py`, `core/constants.py`. If these are not resolved first, the Phase 4a PR will sit on top of unrelated Codex modifications.

**Phase 4a CAN start safely if-and-only-if** ONE of the following is done first:
- (A) The 4 NEEDS_FOUNDER_DECISION files are reviewed and committed in a hygiene commit (the recommended path); OR
- (B) The 4 NEEDS_FOUNDER_DECISION files are reset to HEAD (only safe if their dirty content is intentional Codex throwaway -- see SESSION-LOG entries to judge); OR
- (C) Phase 4a's first PR is restricted to NET-NEW files only (`new model file`, `new alembic migration`, `new scripts/migrate_vault_to_v2.py`) and does not touch the 4 hot-path files yet -- the model/lifespan registration becomes a Phase 4a follow-up PR after the hygiene is sorted.

Recommendation: pick (C) for first Phase-4a PR + (A) for the second Phase-4a PR. This keeps each PR small and reviewable.

## 10. Files that MUST be handled before Phase 4a

If staying with option (A) above:

1. `backend/app/main.py` -- review uncommitted hunks, commit-separate or selective-reset.
2. `backend/app/models/__init__.py` -- same.
3. `backend/app/core/database.py` -- same.
4. `backend/app/core/constants.py` -- same.

If staying with option (C):

- None -- but the 4 must be handled before the SECOND Phase-4a PR (the one that registers the new `Secret` model + RefuseToBoot + KEK boot log).

In either case, the 27 skills/* scrapes and the 3 backend migrations should also be committed in the hygiene batch -- they are stable per CLAUDE.md SKILLS SYNC RULE and the migrations need to land before Phase 4b's migration `006_connection_v2.py` can apply cleanly.

---

**End of inventory.**
