# Phase 4b Handoff Context

**Generated:** 2026-04-30
**Author:** Claude Opus 4.7
**Purpose:** compact checkpoint between Phase 4a (vault foundation + migration tooling) and Phase 4b (registry rewrite). One doc that a fresh session can read to pick up the rebuild without losing context.

---

## 1. Branch + HEAD

| Field | Value |
|---|---|
| Branch | `rebuild-connections-mcp-runtime` |
| HEAD | `dc792c58936392f31dfb437c664b7b3f403bdfb4` |
| Parent of HEAD | `94a0dcf` (Phase 4a-3 migration script) |
| Merge base with `master` | `8241f22` (TICKET-MCP-IMPORT-WIRING) |

## 2. Commit chain (6d3ca5e → latest)

```
dc792c5 docs: Phase 4a-3 operator gate report                              ← HEAD
94a0dcf phase4a: add vault v2 migration dry-run and dual-read validation
f0c9f85 phase4a: wire envelope vault boot validation and secret model
09b393a pre-phase4a-2: stabilize core hot-path before vault integration
d100b50 docs: option B prep -- core hot-path hunk review + backup patch
433ab60 phase4a: add isolated envelope vault foundation
1273e18 docs: update pre-Phase-4a inventory after hygiene commits
7862991 pre-phase4a: sync approved skills artifacts
4d97f88 pre-phase4a: land prerequisite migrations 003-005
38e1c5d docs: pre-Phase-4a dirty working tree inventory
f2a30a3 connections-rebuild Phase 3 supplement: archive OAuthSetupModal
b73f0b4 connections-rebuild Phase 3: archive 7 dead frontend modules
cb41be2 connections-rebuild: Ultraview review + ADR-002 lock + baseline
6d3ca5e connections-rebuild: phase 0-2 deliverables (mapping + V2 architecture)
```

13 commits since branch creation. Net delta vs `master`: same 21 pre-existing failures / 76 errors (ADR-002 D-015 baseline); zero regressions.

## 3. Current status

### Phase 3 — archive — DONE
Commits: `b73f0b4` (7 frontend orphans) + `f2a30a3` (OAuthSetupModal supplement).
All 8 dead frontend files moved to `archive/connections_rebuild_20260430_171410/`. `CONNECTIONS_ARCHIVE_LOG.md` records each row with recovery procedure + 14-day hard-delete schedule. Live `pages/connections/` now contains only KEEP / DEFER files: `MainBrainPanel.tsx`, `McpServersPanel.tsx`, `PluginsCatalogBrowser.tsx`, `installFlow.ts`, `types.ts`, `catalog.ts` (deferred to Phase 7).

### Phase 4a-1 — envelope vault foundation — DONE
Commit: `433ab60`.
- `backend/app/core/vault_v2.py` (~290 LOC, pure-functional)
- `backend/tests/test_vault_v2.py` (33 tests)
- `docs/PHASE_4A_VAULT_FOUNDATION.md`
Module is callable as a library; no live consumers; `vault.py` (legacy) still production source of truth.

### Phase 4a-2 — Secret model + KEK boot validation — DONE
Commit: `f0c9f85` (preceded by stabilization commit `09b393a` per founder option B' choice).
- `backend/app/core/vault_boot.py` (~140 LOC) — `load_kek_from_env(is_production)`, `RefuseToBoot`, `kek_sha256_prefix`
- `backend/app/core/constants.py` — `DAENA_KEK_ENV`, `LEGACY_VAULT_KEK_ENV`, `KEK_BYTE_LENGTH`, `PLACEHOLDER_KEK_VALUES`
- `backend/app/models/secret.py` — `Secret` SQLAlchemy model (TenantMixin + TimestampMixin + unique on `(tenant_id, secret_class, bound_to)`)
- `backend/app/models/__init__.py` — Secret registered
- `backend/migrations/versions/006_secrets_envelope_vault.py` — table + `tenants.dek_wrapped` column
- `backend/app/main.py` — KEK validation step inserted at top of lifespan ESSENTIALS (`vault.kek_loaded sha256_prefix=<8hex> is_production=<bool>` log)
- `backend/tests/test_vault_boot.py` (32 tests) + `backend/tests/test_secret_model.py` (6 tests)
Phase 4a-2 commit honored ALL 10 founder rules. `vault.py` (legacy) untouched. `oauth_credentials_store.py` untouched.

### Phase 4a-3 — migration dry-run + dual-read validation — DONE
Commit: `94a0dcf`.
- `backend/app/services/vault_migration.py` (~330 LOC) — pure-functional library
- `backend/scripts/migrate_vault_to_v2.py` (~145 LOC) — argparse CLI
- `backend/tests/test_vault_migration.py` (20 tests)
- `backend/app/models/identity.py` — added `Tenant.dek_wrapped` Mapped column
- `docs/PHASE_4A_VAULT_MIGRATION.md`
Counters: candidate / already_migrated / skipped / failed / drift / written / dek_provisioned. Default `--dry-run`. Drift in `--apply` aborts batch unless `--force`. Plaintext NEVER printed (sentinel-string tests pin this).

**Combined Phase 4a vault stack: 91 / 91 tests passing in 0.68s.**

## 4. Production gate (per `docs/PHASE_4A_3_OPERATOR_GATE_REPORT.md`)

| Question | Answer |
|---|---|
| Production exists? | **YES** — Cloud Run `daena` in GCP `daena-467315`, deployed 2026-03-21 (`https://daena-596551989073.us-central1.run.app`) |
| Production DB binding visible from this branch? | **NO** — Cloud Run secret manager / env var; founder must inspect from operator side |
| Real encrypted credentials in dev DB? | **NO** — 44 ConnectorInstance rows all hold JSON-null literals; vault_secrets empty; oauth_credentials_store.json absent |
| Real encrypted credentials in production? | **UNKNOWN** — requires operator-side dry-run with prod DATABASE_URL + DAENA_KEK in env |
| Has `--apply` ever run? | **NO** anywhere |
| Phase 4b in dev-only mode allowed? | **YES**, conditionally (founder option B' = parallel dev) |
| Production deploy of Phase 4b allowed? | **NO** until operator runs prod dry-run + apply + 7-day soak with zero drift |

**Decision rule outcome (per Phase 4a-3 operator-gate spec):** production exists → Phase 4b is BLOCKED for production deploy. Dev work may proceed in parallel with operator-side prod migration.

## 5. Required Phase 4b rules

These rules apply to all Phase 4b code unless founder explicitly overrides per-rule:

1. **`USE_CONNECTION_REGISTRY_V2` feature flag, default `false` in production.** New env var to gate which path service-layer writers use. Dev `.env` may set it `true`. Cloud Run `APP_ENV=production` must default to `false` until operator flips it post-soak.
2. **Vault_v2 for new V2 secret writes.** All Phase 4b code paths that need to persist a secret use `app.core.vault_v2.encrypt_secret` + the `Secret` model. Never call legacy `app.core.vault.encrypt_dict` from new code paths.
3. **Legacy read path remains.** Any code that reads a secret must check the new `secrets` table first AND fall back to legacy `ConnectorInstance.credentials` (decrypted via legacy `vault.decrypt_dict`). This dual-read continues until the operator confirms zero drift over the 7-day soak window.
4. **Do not delete `core/vault.py`.** It stays as the legacy read path until post-soak.
5. **Do not delete `oauth_credentials_store.py` / `.daena_oauth_overrides.json`.** Same reason.
6. **Do not modify `vault_v2.py` unless a test proves a bug** (per Phase 4a-3 founder rule, carried forward).
7. **No frontend rebuild yet.** Phase 4b is backend service-layer only. Frontend `pages/connections/*` (MainBrainPanel, McpServersPanel, PluginsCatalogBrowser) stays as-is. Phase 7 is the frontend rebuild gate.
8. **No production deploy.** Phase 4b code lands on this branch but does NOT trigger any deployment automation.
9. **Per ADR-002 D-010**: delete `connection_service._status_for_install` in the SAME PR that introduces the 6 truth fields. No transition window where both lying status function AND new truth fields coexist.
10. **Per ADR-002 D-012**: rename `backend/app/services/runtimes/adapters/mcp_bridge.py` → `mcp_bridge_runtime_adapter.py` to disambiguate from `mcp_sync/detector.py`.
11. **Per ADR-002 D-008**: per-kind Pydantic discriminated-union validator on `connection_v2.config` JSONB ships in the FIRST Phase 4b PR, not later.
12. **Connection_v2 op-lock table** (per ADR-002 D-002): in-progress state lives in `connection_v2_op_lock`, NOT booleans on `connection_v2`. `derive_label(row, active_ops)` reads the lock state.
13. **Per-dimension failure storage** (per ADR-002 D-001): each truth dim carries `<dim>_failure_at` + `<dim>_failure_reason`; failure on one dim never overwrites another's reason.
14. **`imported = true` requires durable-restart-safe persistence** (per ADR-002 D-007). Lifespan startup MUST NOT auto-set `imported=true` for in-memory hydration without DB row.
15. **`stale != failed`** (per ADR-002 D-005). New labels `healthy_stale` and `degraded_stale` are distinct from `failed`.
16. **WRAP, not 308 redirect** for `/runtimes` API (per ADR-002 D-004). `runtimes.py` keeps its public surface; internals call new service.
17. **No write through `_status_for_install`-style status functions in any new code.** New service functions return / accept `ConnectionV2Out` with the 6 truth fields explicitly.
18. **Audit hook**: Phase 4b adds the audit row emission for vault read/write events that Phase 4a-3 explicitly deferred (count-only logging is the current state). Use the existing `audit_service` patterns.
19. **No reset of any of the 164 still-dirty files** without founder approval (see §6 risk register).

## 6. Open risks

### R1 — Alembic / repo-root migration gap

`alembic.ini` is missing at the repo root; `alembic current` and `alembic heads` both fail with `No 'script_location' key found`. The application currently relies on `Base.metadata.create_all` in `main.py` lifespan ESSENTIALS to create new tables in dev. Production deploy may or may not run `alembic upgrade head` — the operator must confirm. If prod doesn't run alembic, migrations 003-006 may not be applied to the prod DB even though they are committed.

**Mitigation for Phase 4b:** add an `alembic.ini` to the repo root in the first Phase 4b PR (procedural, no code logic). OR explicitly call `command.upgrade(config, "head")` from a one-shot Cloud Run job. Either path requires operator coordination.

### R2 — Remaining dirty files (160 files)

Per `docs/PRE_PHASE4A_DIRTY_TREE_INVENTORY.md` (updated to 164 then 160 after stabilization):
- 36 files marked `KEEP_DIRTY_FOR_PHASE4B` — these are exactly the files Phase 4b will rewrite (`connections.py`, `connector_oauth.py`, `mcp_*.py`, `runtimes.py`, `model_router.py`, all 3 CLI adapters in scope, `connection_service.py`, `oauth_service.py`, `connector_install.py`, `policies.py`, `runtime.py`, `mcp_server.py` model, `runtime_truth_registry.py`, migration 005 already committed, 2 catalog tests, `pages/connections/` + `components/connections/` directory roots, 4 packages/daena-mcp untracked files, 4 skills/connector-* directories).
- 120 files marked `COMMIT_SEPARATE_BEFORE_PHASE4A` — the rest (out-of-scope frontend pages, backend modules, tests). Did NOT block Phase 4a; will not block Phase 4b unless they conflict with specific edits.
- 4 files marked `IGNORE_FOR_NOW` — `.axon/meta.json` x 2 + `CLAUDE.md` + `AGENTS.md`.

**Risk:** Phase 4b must not blindly commit any of these without per-file review. Use `git add <explicit-paths>` for every commit. Forbidden: `git add -A` or `git add .` on this branch.

### R3 — Old registry compatibility

`useRuntimeRegistry.ts` is currently DEAD CODE (zero non-self consumers) — verified via grep + gitnexus impact at the time of Phase 4a-1. Phase 4b plans to merge it into `useConnectionRegistry.ts` (per ADR-002 §13). However:
- The dead-code state is brittle: a future random commit could re-introduce a consumer.
- Phase 4b should grep for `useRuntimeRegistry` again at PR time and confirm still 0 non-self consumers before deletion.
- WRAP layer for `/runtimes` API (per ADR-002 D-004) means the existing `runtimes.py` route file STAYS during Phase 4b. The `RuntimeRegistry` service layer is the part that changes.
- The 5 lying CLI adapters (`claude_code.py:182-186`, `codex.py:93-97`, `gemini_cli.py:59-63`, `grok_cli.py:49-53`, `mcp_bridge.py:88-93`) need real round-trip `check_health` per ADR-002 / V2 §14. Phase 4b PR for the runtime-side rewrite must include this.

### R4 — Production migration gate

The single biggest risk: Phase 4b ships to production while prod DB has legacy encrypted credentials that haven't been migrated. Mitigation:
- Feature flag `USE_CONNECTION_REGISTRY_V2` defaults `false` in production until soak passes.
- Dual-read path in service layer: try `Secret` table first, fall back to legacy `ConnectorInstance.credentials`.
- Operator runs prod dry-run BEFORE Phase 4b's first prod deploy.
- Post-soak: founder flips the flag; legacy modules deleted in a separate cleanup PR.

### R5 — `core/vault.py` dev placeholder still in use

`backend/.env` has `VAULT_ENCRYPTION_KEY=dev-only-32-byte-key-for-aes2560` (placeholder). `DAENA_KEK` is not set. Phase 4a-2's `load_kek_from_env(is_production=False)` returns the deterministic `DEV_FALLBACK_KEK` with a loud warning. This is correct dev behavior. **Operator action required for production**: generate 32 random bytes, base64-encode, store in Cloud Run Secret Manager as `DAENA_KEK`, redeploy. Verification: boot log line `vault.kek_loaded sha256_prefix=<8hex>` in Cloud Run logs.

## 7. Exact next prompt to continue Phase 4b

Paste this verbatim to start Phase 4b dev work (founder option B' = parallel dev path):

```
Green-light Phase 4b dev work in parallel mode (option B' from
PHASE_4A_3_OPERATOR_GATE_REPORT).

Scope for first Phase 4b PR (backend only):
1. Add USE_CONNECTION_REGISTRY_V2 feature flag (default false in
   production, may be true in dev). In core/config.py.
2. Create backend/app/models/connection_v2.py with the schema from
   ADR-002 D-001 + V2 spec §4 (one table for all kinds + per-dim
   failure storage + connection_v2_op_lock side table).
3. Add Alembic migration 007_connection_v2_registry.py (creates
   both tables + indexes per V2 §4).
4. Create backend/app/services/connection_v2/ package skeleton:
   - registry.py (read/write API)
   - permissions.py (per-tool permission CRUD, ported from
     connection_service.py)
   - probe_contract.py (per-kind probe interface, NOT yet
     implementations)
   - state_machine.py (derive_label() pure function per ADR-002 D-005
     with 14 labels including healthy_stale + degraded_stale)
5. Add Pydantic discriminated-union validator on connection_v2.config
   per ADR-002 D-008.
6. Tests for the new schema + state machine + permission CRUD
   (in-memory SQLite via existing conftest fixtures).
7. Do NOT yet implement the lying-CLI-adapter rewrite (separate PR).
8. Do NOT yet delete connection_service._status_for_install (deletion
   is in the SAME PR that swaps the live API to use connection_v2 --
   that's PR 2 of Phase 4b, not PR 1).

Rules (carried from Phase 4a-3 + ADR-002):
- USE_CONNECTION_REGISTRY_V2=false in production by default
- Vault_v2 for new writes; legacy read path remains
- Don't delete vault.py / oauth_credentials_store.py
- Don't modify vault_v2.py unless a test proves a bug
- No frontend rebuild
- No production deploy
- Don't reset any of the 160 still-dirty files without per-file review
- Use `git add <explicit-paths>` for every commit; never `git add -A`
- Per-dim failure storage; op-lock table for in-progress state
- imported=true requires durable persistence
- stale != failed
- WRAP, not 308 redirect, for runtimes.py

Before coding:
1. Confirm branch is rebuild-connections-mcp-runtime
2. Confirm HEAD is dc792c5
3. Confirm migration 006 exists and chain is 001-006 valid
4. Confirm `secrets` table is empty (Phase 4a-3 didn't apply)

After implementation:
1. Run targeted tests: test_connection_v2.py (new), test_vault_v2.py
   (existing must still pass)
2. Run frontend tsc only if practical
3. Run migration sanity check (chain 001-007 valid)
4. Commit as:
   phase4b: connection_v2 model + migration 007 + service skeleton
5. Stop and report:
   - commit SHA
   - files changed
   - tests run
   - whether USE_CONNECTION_REGISTRY_V2 default is correct
   - whether legacy read paths still work
   - whether Phase 4b PR 2 (live API swap + _status_for_install
     deletion + lying CLI adapter rewrite) can start
```

---

## Files to read at session start (in order)

1. `docs/PHASE_4B_HANDOFF_CONTEXT.md` (this file -- the project map)
2. `docs/ADR-002-connections-rebuild-locked-decisions.md` (the 16 locked decisions; wins over spec on conflict)
3. `docs/CONNECTIONS_MCP_PLUGIN_ARCHITECTURE_V2.md` (the spec to implement)
4. `docs/PHASE_4A_3_OPERATOR_GATE_REPORT.md` (production gate state)
5. `docs/PHASE_4A_VAULT_FOUNDATION.md` + `docs/PHASE_4A_VAULT_MIGRATION.md` (what 4a actually shipped)
6. `docs/PRE_PHASE4A_DIRTY_TREE_INVENTORY.md` (the 160 still-dirty files + recommendations)
7. `docs/CONNECTIONS_FILE_MAP.md` (per-file KEEP/ARCHIVE/REWRITE/WRAP -- amended)
8. `docs/CONNECTIONS_REBUILD_PLAN.md` (phase status table + entry criteria)

## Files to NOT touch in Phase 4b

- `backend/app/core/vault.py` (legacy)
- `backend/app/core/vault_v2.py` (Phase 4a-1, frozen unless test bug)
- `backend/app/core/vault_boot.py` (Phase 4a-2)
- `backend/app/services/vault_migration.py` (Phase 4a-3)
- `backend/app/services/integrations/oauth_credentials_store.py` (legacy, deferred to post-soak)
- All `frontend/src/pages/connections/*` files (no frontend rebuild)
- All `archive/` files (already moved; do NOT restore)
- `CLAUDE.md`, `AGENTS.md` (user-managed)
- The 4 NEEDS_FOUNDER_DECISION files were already stabilized at `09b393a`; do NOT undo

---

**End of Phase 4b handoff context.**
