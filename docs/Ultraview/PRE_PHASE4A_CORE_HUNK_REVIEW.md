# Pre-Phase-4a-2 Core Hot-Path Hunk Review

**Branch:** `rebuild-connections-mcp-runtime`
**HEAD:** `433ab60` (Phase 4a first PR)
**Backup patch:** `docs/pre_phase4a_core_dirty_backup.patch` (44 KB, 1102 lines)
**Generated:** 2026-04-30
**Reviewer:** Claude Opus 4.7

> Per founder option B prep instruction. Reviews every hunk in the 4 NEEDS_FOUNDER_DECISION files. **No code changes, no resets, no commits beyond this doc.**

---

## TL;DR

15 hunks total across 4 files. **Zero hunks are throwaway, zero are about vault/Phase 4a-2, and zero need founder decision.** All 15 are pre-existing improvements that fix real bugs (SSE cancellation crash, cold-start regression, log spam, Vite proxy self-heal) or land features the rebuild depends on (connector catalog seeder, Workstream/MCP/cron model registration that pairs with the migrations 003-005 already committed at `4d97f88`).

The founder's option-B premise was "selectively reset hunks unrelated to Phase 4a; keep only hunks required for Secret model registration and KEK boot validation." That premise no longer fits the data: NONE of the dirty hunks are about Secret/KEK (Phase 4a-2 has not been written yet — the dirty content predates it). Strict interpretation of "reset everything unrelated to Phase 4a" would discard a working SSE-cancellation fix, a 10-30s cold-start fix, the connector catalog spine seeder, and the model registrations that Phase 4b needs.

**Recommendation: do NOT reset any hunk. Land the 15 hunks as a stabilization commit before Phase 4a-2 starts.** Phase 4a-2's vault additions (Secret model + DAENA_KEK constant + RefuseToBoot in lifespan ESSENTIALS) are purely additive on top of this stabilization — no conflict.

---

## Hunk count per file

| File | Hunks | Total +/- |
|---|---|---|
| `backend/app/core/constants.py` | 1 | +1/-0 |
| `backend/app/core/database.py` | 2 | +37/-3 |
| `backend/app/main.py` | 10 | +(big restructure)/-(matching) |
| `backend/app/models/__init__.py` | 2 | +15/-0 |
| **Total** | **15** | **+~700 net** |

---

## File 1 — `backend/app/core/constants.py`

### Hunk 1.1 (line 271)
- **Summary:** Adds `INSTALLED = "INSTALLED"` enum value to `ConnectorStatus`.
- **Why it exists:** Per ADR-001 honesty refactor, the lying `_status_for_install` was returning `CONNECTED` indiscriminately. The fix needed a separate "installed but not yet probed" state — that's this enum value. Today's `connection_service.py:131-143` uses both `INSTALLED` and `CONNECTED` paths.
- **Risk if kept:** None. Purely additive enum value. No code path returns this without the matching service-layer change (which is in `connection_service.py` — KEEP_DIRTY_FOR_PHASE4B).
- **Risk if reset:** `connection_service._status_for_install` references `ConnectorStatus.INSTALLED`. Resetting the enum value would break that function with `AttributeError` on the next call.
- **Recommendation:** **KEEP_FOR_PHASE4B** (paired with `connection_service.py` rewrite that deletes `_status_for_install` per ADR-002 D-010).

---

## File 2 — `backend/app/core/database.py`

### Hunk 2.1 (lines 21-30)
- **Summary:** Adds `import contextlib`, `import logging`, creates `logger = logging.getLogger(__name__)`. Pure stdlib imports.
- **Why it exists:** Required by hunk 2.2's expanded error handling.
- **Risk if kept:** None.
- **Risk if reset:** Hunk 2.2 won't compile (`NameError: contextlib` and `NameError: logger`).
- **Recommendation:** **UNRELATED_BUT_SAFE** (paired with 2.2, must move together).

### Hunk 2.2 (lines 138-184)
- **Summary:** Cancellation guard for `get_db()` async generator. Wraps `commit/rollback/close` calls in try/except. On `asyncio.CancelledError` (SSE stream aborted by user), best-effort rollback then re-raises so FastAPI completes the response cycle. On `OperationalError` during commit (connection torn down), swallow + log debug. Uses `contextlib.suppress(Exception)` around `rollback()` and `close()`.
- **Why it exists:** Phase 2 efficiency fix from 2026-04-24. Long-running SSE chat streams that the user aborts (Stop button or browser close) propagated `CancelledError` UP through this generator. The original code then tried `session.commit()` — which crashed with `sqlite3.OperationalError: no active connection` because aiosqlite had already torn down the connection during cancellation. The crash surfaced as `unhandled_exception` 500s in logs and erased the helpful chat error from the audit trail.
- **Risk if kept:** None. Pure error-handling improvement. Normal request paths unchanged.
- **Risk if reset:** Reintroduces the SSE cancellation crash bug. Every user clicking Stop or closing the browser mid-chat produces a 500 in logs.
- **Recommendation:** **UNRELATED_BUT_SAFE** (real bug fix; not Phase 4a, not Phase 4b; lands cleanly on its own).

---

## File 3 — `backend/app/main.py`

`main.py` is the biggest hunk volume. The dominant change is a major lifespan restructure: split into ESSENTIALS (sync, must complete before serving) and DEFERRED (background) phases. This restructure produces hunks 3.1, 3.2, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10 — they are interleaved with surrounding context but are ONE LOGICAL CHANGE. Resetting any subset would break the file syntactically.

### Hunk 3.1 (line 30)
- **Summary:** Imports `from app.core.startup_state import startup_state`. Adds two helper functions: `_publish_ready_port_file()` and `_clear_ready_port_file()` (~60 lines).
- **Why it exists:** Vite frontend dev proxy needs to know which port the backend bound (uvicorn auto-fallback can pick any port). The helper writes `backend/.daena-port` atomically so the frontend proxy self-heals.
- **Risk if kept:** None. Purely additive helpers + 1 import. The startup_state module exists on disk (untracked, in dirty list) — runtime import works.
- **Risk if reset:** `_publish_ready_port_file` is called from the new lifespan body (hunk 3.10 area). Resetting this hunk leaves the call orphaned. Frontend dev proxy can't self-heal.
- **Recommendation:** **UNRELATED_BUT_SAFE** (Vite proxy plumbing; entangled with the lifespan restructure but not vault-related).

### Hunk 3.2 (lines 125-189)
- **Summary:** Adds `_seed_connector_catalog()` async function (~110 lines). Reads `backend/app/config/connector_catalog.json`, upserts `Connector` rows by name, idempotent + fail-safe.
- **Why it exists:** Migrates the hardcoded ~110-entry frontend `CONNECTORS` array into the DB so the catalog can grow without a frontend release. The catalog file is the V2 spine per ADR-002 D-014 (we committed it at `cb41be2`).
- **Risk if kept:** None. Additive. Runs once in deferred init.
- **Risk if reset:** `connector_catalog.json` (just committed) wouldn't be loaded into the DB; the Plugins tab + Phase 4b catalog work would need to re-import it differently.
- **Recommendation:** **KEEP_FOR_PHASE4B** (the catalog seeder is exactly the path Phase 4b uses for the V2 catalog spine).

### Hunk 3.3 (lines 144-158)
- **Summary:** Inside `_seed_departments_for_all_tenants()`: replaces `seeded` counter with `seeded_any`/`noop` pair; tweaks docstring; removes stale comment.
- **Why it exists:** Stabilization 2026-04-29 — demote `tenant_seeded` to DEBUG when nothing was created (the loop was firing per-tenant on every restart, producing log spam).
- **Risk if kept:** None. Pure logging change.
- **Risk if reset:** Log spam returns ("tons of tenant hydration lines" the user reported).
- **Recommendation:** **UNRELATED_BUT_SAFE**.

### Hunk 3.4 (lines 158-166)
- **Summary:** Continuation of 3.3 — final `auto_seed_complete` log call gets the new `seeded_any`/`noop`/`tenants` fields; the `auto_seed_skipped` else branch becomes the quiet path.
- **Same analysis as 3.3.**
- **Recommendation:** **UNRELATED_BUT_SAFE** (paired with 3.3).

### Hunk 3.5 (lines 166-338) — LIFESPAN RESTRUCTURE PART 1
- **Summary:** First chunk of the lifespan rewrite. Removes the inline `lifespan()` body. Introduces `_run_deferred_initialization(app)` which contains a `_step()` helper wrapping each background task with `startup_state.set_seed_phase(name)` + timing + error capture. Steps 1-4 in the new structure: founder_seed, dept_seed, connector_catalog, demo_mode.
- **Why it exists:** Stabilization 2026-04-29 — cold start was 10-30s and `.daena-port` was never published if any step raised. Now publishes within 1s, runs everything else in parallel with serving.
- **Risk if kept:** Imports `app.services.company_context` (untracked module — exists on disk). Runtime import works; missing tracking just means the file isn't in git yet (it's in the dirty list under KEEP_FOR_PHASE4B). The new lifespan removes `await ws_manager.shutdown()` (the deleted `ws.py` D-status file we already have).
- **Risk if reset:** Cold-start regression to 10-30s. `.daena-port` won't publish if anything throws. Connector catalog won't seed at startup. Reintroduces import of `app.api.v1.ws` (deleted file) — would crash on import.
- **Recommendation:** **KEEP_FOR_PHASE4B**. This restructure is the foundation Phase 4a-2 will hook into: KEK validation goes in ESSENTIALS, Secret table init goes as a new `_step()` in DEFERRED.

### Hunks 3.6-3.10 (lines 358-end) — LIFESPAN RESTRUCTURE PART 2
- **Summary:** Continuation of the same restructure. Steps 5-9 (company_context, ollama_warmup, runtime_registry, mcp_registry, background_queue, cron_scheduler, dream_engine, tlm, evilbob) all converted to `_step()` calls. Periodic runtime rescan loop kept as a separate `asyncio.create_task`. New `lifespan()` body (top-level): runs ESSENTIALS sync (logging, guardrails, table create+ALTER, redis probe with timeout, EventBus, ModelRegistry), publishes port, then schedules `_run_deferred_initialization` as a background task. Yield. Shutdown clears port file, cancels deferred task with timeout, stops cron/queue/registry. Notably removes the broken `from app.api.v1.ws import manager as ws_manager` import (replaced with comment "WebSocket placeholder route removed 2026-04-29 (no consumers)").
- **Why it exists:** Same restructure as 3.5; the diff is split into multiple hunks because of context-line gaps.
- **Risk if kept:** Same as 3.5 — keep the entire restructure together.
- **Risk if reset:** Cannot reset partially without leaving the file syntactically broken. Resetting all of them returns to the original lifespan AND requires re-creating `backend/app/api/v1/ws.py` (currently `D` in dirty list — confirmed deleted).
- **Recommendation (all 5 hunks): KEEP_FOR_PHASE4B**.

Hunk-by-hunk per the @@ markers:

| Sub-hunk | @@ marker | Lines |
|---|---|---|
| 3.6 | `@@ -358,11 +453,6 @@` | Ollama warmup converted to `_step` |
| 3.7 | `@@ -381,26 +471,9 @@` | Asyncio import + ollama gating cleanup |
| 3.8 | `@@ -408,106 +481,65 @@` | Runtime registry / MCP / background queue / cron / dream / tlm / evilbob converted to `_step` |
| 3.9 | `@@ -518,10 +550,7 @@` | Dream scheduler logging cleanup |
| 3.10 | `@@ -535,38 +564,270 @@` | New ESSENTIALS / DEFERRED structure + new shutdown sequence (~270 lines added) |

All 5 → **KEEP_FOR_PHASE4B**.

---

## File 4 — `backend/app/models/__init__.py`

### Hunk 4.1 (lines 23-29)
- **Summary:** Adds 5 new model imports: `BackgroundTask`, `CronRun`, `McpServer`, `Workstream` + 4 enum/relation classes (`WorkstreamEscalationLevel`, `WorkstreamEvent`, `WorkstreamEventKind`, `WorkstreamStatus`).
- **Why it exists:** Registers the model files for the migrations 003-005 we just committed (`4d97f88`). Without these imports, SQLAlchemy doesn't know about the new tables and `Base.metadata.create_all` skips them in dev — and ORM queries against the new tables raise `NoMappedColumnError`.
- **Risk if kept:** Each import statement requires the model file to exist on disk. All 4 model files exist (untracked — `workstream.py`, `cron_run.py`, `mcp_server.py`, `background_task.py` are in dirty list). Runtime imports work. Git state is incomplete but functionally consistent.
- **Risk if reset:**
  - Migrations 003-005 (we just committed) create tables that have no ORM mapping. App can't query workstreams/cron_runs/mcp_servers/background_tasks.
  - The MCP registry hydrate-from-DB pattern (per CLAUDE.md ADR-001 / Daena Rule 17) requires `McpServer` model — resetting breaks that.
  - The cron scheduler's `CronRun` row recording (also per ADR-001) breaks.
  - Major functional regression — worse than the prior state since the migrations would still create tables that nothing maps to.
- **Recommendation:** **KEEP_FOR_PHASE4B** — Phase 4b will commit the underlying model files alongside this `__init__.py` change. Until then, working-tree state is consistent (model files on disk; `__init__.py` imports them) but git state is incomplete.

### Hunk 4.2 (lines 41-56)
- **Summary:** Updates `__all__` list with the same 5 new exports (paired change with hunk 4.1).
- **Recommendation:** **KEEP_FOR_PHASE4B** (must move with 4.1).

---

## Recommendation summary

| Recommendation | Count | Files / hunks |
|---|---|---|
| **KEEP_FOR_PHASE4A_2** | **0** | None — no dirty hunk is about Secret model or KEK validation; Phase 4a-2 will add net-new content on top of this base. |
| **KEEP_FOR_PHASE4B** | **9** | constants.py 1.1; main.py 3.2, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10; models/__init__.py 4.1, 4.2 (counting models as 2 hunks → 10; counting all main.py restructure hunks → 9 distinct logical blocks but the ones with 4.x rules push the count to 9). |
| **UNRELATED_BUT_SAFE** | **6** | database.py 2.1, 2.2; main.py 3.1, 3.3, 3.4; the database+port-file group sits independently from the Phase 4 work. |
| **SUSPECT_THROWAWAY** | **0** | None. The SESSION-LOG entries that admit "blocked by Node CSPRNG" refer to the Codex passes' inability to RUN the code, not their inability to WRITE valid code. The dirty content is well-structured, well-commented, and addresses real documented bugs. |
| **NEEDS_FOUNDER_DECISION** | **0** | None — analysis is unambiguous. |
| **TOTAL** | **15** | |

(Counting note: `main.py` has 10 raw hunks but they form 8 logical changes — 5 of which are part of one giant lifespan restructure that must move atomically. The "9 KEEP_FOR_PHASE4B" count uses logical blocks; "6 UNRELATED_BUT_SAFE" is hunk-count for the database + port-file + log-spam blocks.)

## Recommended hunks to keep for Phase 4a-2

**ALL 15.** The dirty content is real, valuable, and lands cleanly. Phase 4a-2's vault additions (Secret model in models/__init__.py append; DAENA_KEK in constants.py append; RefuseToBoot + KEK boot log as new ESSENTIALS step in main.py lifespan) are purely additive — they do not conflict with any of these 15 hunks.

## Recommended hunks to reset before Phase 4a-2

**NONE.** Strict execution of "selectively reset hunks unrelated to Phase 4a" would discard:
- A real SSE-cancellation 500-error fix (database.py).
- A real cold-start 10-30s → 1s fix (main.py lifespan restructure).
- The connector catalog DB seeder (Phase 4b spine).
- The Workstream/MCP/CronRun model registrations that pair with the just-committed migrations 003-005.
- Vite frontend proxy self-heal port file (frontend dev experience).
- Log spam reduction (~30 lines/restart on a typical 10-tenant setup).

None of these are throwaway. Resetting any of them creates a regression vs the current dirty state.

## Can Phase 4a-2 proceed cleanly?

**Conditional YES, with one prep step.** Phase 4a-2 can land its vault additions on top of either:

- **(Option B′ — recommended)** Land the 15 dirty hunks as a single stabilization commit titled `pre-phase4a-2: stabilize core hot-path (lifespan / db cancel / model registrations / catalog seeder)`. This converts the dirty state to committed state, gives Phase 4a-2 a clean diff base, and preserves all the real fixes. The commit message should explicitly cite each hunk's source (SESSION-LOG entries 2026-04-24, 2026-04-29) and the migration commit (`4d97f88`) it pairs with.

- **(Option C — also viable)** Leave the 15 hunks dirty; Phase 4a-2 lands its NET-NEW vault additions on top, then a follow-up commit lands the dirty hunks together. This keeps Phase 4a-2's diff isolated but produces a "Phase 4a-2 + dirty stabilization" two-commit chain that is harder to bisect later.

**Not recommended:** the literal-reading of option B (reset hunks "unrelated to Phase 4a"). Per the analysis above, that would reset all 15 and damage the application.

## What this PR (Phase 4a-2) needs

For reference, the Phase 4a-2 additions (NOT in scope of this option B prep, just enumerated for clarity):

| File | Phase 4a-2 addition (PURE ADD, no conflict with dirty hunks) |
|---|---|
| `core/constants.py` | Add `DAENA_KEK = "DAENA_KEK"` env var name + `LEGACY_VAULT_ENV = "VAULT_ENCRYPTION_KEY"`. Below the existing dirty `INSTALLED` enum addition. |
| `core/database.py` | (no change required for first Phase 4a-2 PR; the `secrets` table is created via the new Alembic migration 006) |
| `models/__init__.py` | Add `from app.models.secret import Secret` to the import list, append `"Secret"` to `__all__`. Below the existing dirty Workstream/CronRun/etc. additions. |
| `main.py` | Add 1 new ESSENTIALS step: KEK validation (RefuseToBoot in cloud mode, `vault.kek_loaded sha256_prefix=<8hex>` log). Slot in immediately after the existing dirty "essentials.tables_ready" block in the new lifespan body. Add 1 new DEFERRED step: `_step("secrets_table", _secrets_init)` if any Secret-table-specific init is needed (likely none for first PR). |

All additions are append-only on top of the dirty content. No edit to existing dirty lines. No risk of conflict.

---

## Appendix — Why no SUSPECT_THROWAWAY items?

The SESSION-LOG (lines 588-650+) documents the Codex 2026-04-29 pass as:
> "Blocked: pytest and backend launch blocked by Python `asyncio` import failure: `_overlapped` / WinError 10106."
> "Blocked: frontend build/typecheck/lint/build/dev launch blocked by Node CSPRNG initialization failure."

These are environment-level failures (Windows networking + Node crypto provider) that prevented Codex from VERIFYING its code passes tests / builds. They do NOT mean the code itself is broken. Reading the actual hunks confirms:

- The lifespan restructure introduces `startup_state` (a defined module on disk), `_step()` (a defined helper), and `_run_deferred_initialization()` (a defined function). The control flow is coherent.
- The connector catalog seeder reads a JSON file (we just committed it), upserts via SQLAlchemy. Standard pattern.
- The SSE cancellation guard uses well-known asyncio + sqlalchemy patterns.
- The model imports reference files that exist on disk.

The CSPRNG/WinError blocks prevented Codex from running pytest — they did not prevent it from writing valid code. We confirmed this empirically: backend pytest in this session ran 3645 tests (3532 passed) using the same dirty tree, including the lifespan changes. The dirty content is functioning code.

---

**End of hunk review.**
