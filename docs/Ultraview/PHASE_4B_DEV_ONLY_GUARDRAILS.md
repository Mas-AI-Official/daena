# Phase 4b Dev-Only Guardrails

**Branch:** `rebuild-connections-mcp-runtime`
**HEAD:** `da8f737`
**Generated:** 2026-04-30
**Status:** Phase 4b is GREEN-LIT for dev-only work. Production deploy is BLOCKED.

---

## State of the world

| Question | Answer |
|---|---|
| Production exists? | **YES** -- Cloud Run service `daena` in GCP project `daena-467315`, deployed 2026-03-21 (`https://daena-596551989073.us-central1.run.app`) |
| Production credentials known? | **NO** -- prod DB binding is in Cloud Run secret manager / env, not visible from this branch. Real-credential count in production is UNKNOWN until operator runs `python -m backend.scripts.migrate_vault_to_v2 --dry-run --report-json` against prod |
| Production migration dry-run required before Phase 4b deploy? | **YES, mandatory** |
| Phase 4b status | DEV-ONLY until prod migration gate cleared |
| Production deploy of Phase 4b? | **BLOCKED** until founder approval after prod dry-run review + 7-day soak with zero drift |

## The feature flag

`USE_CONNECTION_REGISTRY_V2` (settings + env var):

| Environment | Default | Behavior when false | Behavior when true |
|---|---|---|---|
| Production | **false** (mandatory) | Live UI hits legacy `connection_service.py`. Legacy `core/vault.py` is the secret-storage path. New V2 endpoints exist but operate on the empty `connection_v2` table. | Forbidden in production until soak gate clears. |
| Staging | false (when staging exists) | Same as prod-false. | Permitted only after staging-soak. |
| Local dev | false (default) | Same as prod-false. | Permitted; V2 is the canonical source-of-truth for the dev tenant. Writes go to `secrets` table via `vault_v2`. |

Exact env-var name: `USE_CONNECTION_REGISTRY_V2=true` to flip on. Default-false in `core/config.py`. `Settings.use_connection_registry_v2: bool = False` -- a missing env var = false.

## Rollback path

If anything goes wrong with Phase 4b at any environment:

1. **Set `USE_CONNECTION_REGISTRY_V2=false`** (or unset). Live UI immediately reverts to legacy `connection_service.py`.
2. **Legacy registry is intact:** `RuntimeRegistry`, `MCPRegistry`, `connection_service._status_for_install` all still exist (Phase 4b PR 1 does NOT delete them).
3. **Legacy vault is intact:** `core/vault.py` + `oauth_credentials_store.py` still serve all reads + writes when the flag is off.
4. **`secrets` table writes during Phase 4b dev** stay in the `secrets` table. They are inert when the flag is off. Operator can DROP TABLE secrets if rollback needs to be permanent.
5. **No frontend changes** in Phase 4b PR 1 -- the existing `MainBrainPanel`/`McpServersPanel`/`PluginsCatalogBrowser` keep calling existing legacy routes.

## Hard rules (carried from founder green-light)

1. **No production deploy.** Phase 4b code lands on this branch but does NOT trigger any deployment automation. `deploy-cloud.sh` is NOT to be run by Claude.
2. **No production `--apply`** of the vault migration script. Operator-only, with founder approval, after dry-run review.
3. **Do not delete `core/vault.py`.** Legacy read path stays.
4. **Do not delete `oauth_credentials_store.py`.** Same reason.
5. **Do not force production to use vault_v2 yet.** All vault_v2 writes are gated on `USE_CONNECTION_REGISTRY_V2 == true`.
6. **Feature flag default false in production.** Confirmed in test (`test_feature_flag_off_keeps_legacy_behavior`).
7. **Dev may use `USE_CONNECTION_REGISTRY_V2=true`.** Confirmed in test (`test_feature_flag_on_uses_v2_in_dev`).
8. **All V2 secret writes use vault_v2.** `connection_v2/registry.py` writes go through `vault_v2.encrypt_secret` + persist into `secrets` table. Never `vault.encrypt_dict` from V2 paths.
9. **Dual-read compatibility path:** when reading a secret, check `secrets` table first; on miss, fall back to legacy `ConnectorInstance.credentials` decoded via `vault.decrypt_dict`. Confirmed in test (`test_legacy_rows_remain_readable_via_dual_read`).
10. **No Connections frontend rebuild.** Phase 4b PR 1 is backend service-layer + new API routes only. Frontend `pages/connections/*` stays as-is.

## What Phase 4b PR 1 ships

- New SQLAlchemy models (`connection_v2`, `connection_v2_capability`, `connection_v2_op_lock`)
- Alembic migration `007_connection_v2_registry`
- Service layer (`backend/app/services/connection_v2/`)
- New REST endpoints under `/api/v1/connections/v2/*`
- Pydantic discriminated-union validators per kind
- 6-truth-dimension state machine (`derive_label`)
- Per-dimension failure storage
- Op-lock table for in-progress state
- Vault_v2 integration for new writes
- Dual-read compatibility for legacy reads
- 8 mandated test areas

## What Phase 4b PR 1 does NOT ship

- The frontend cutover from legacy to V2 routes (Phase 4b PR 2 or Phase 7).
- Deletion of `connection_service._status_for_install` (Phase 4b PR 2 / SAME PR as live API swap, per ADR-002 D-010).
- Rename of `mcp_bridge.py` adapter (Phase 4b PR 2, per ADR-002 D-012).
- Real per-kind probe implementations (this PR ships the contract + a no-op probe for tests; PR 2 implements per-kind probes including the 5 lying CLI adapter rewrites).
- Reconciliation cron for the soak window (Phase 4b PR 3).
- Catalog signing service (deferred per ADR-002 D-006).
- Bridge dispatch enablement (BLOCKED in V2 per ADR-002 §12).

## Production operator steps required before deploy

These steps are the operator's responsibility -- Claude cannot perform them from this branch:

1. **Confirm prod alembic state.** SSH/cloud-shell into the deploy environment, run `alembic -c migrations/alembic.ini current`. Expected: some revision `<= 006`. If `< 006`, also run `alembic -c migrations/alembic.ini upgrade head` to apply 003-006.
2. **Set `DAENA_KEK` in Cloud Run secret manager.** Generate 32 random bytes, base64-encode (44 chars), store as `DAENA_KEK`. Update Cloud Run service env. Redeploy. Verify boot log emits `vault.kek_loaded sha256_prefix=<8hex>`.
3. **Run prod dry-run** with prod `DATABASE_URL` + `DAENA_KEK` in env: `python -m backend.scripts.migrate_vault_to_v2 --dry-run --report-json out.json`. Inspect `out.json`.
4. **Founder reviews `out.json`.** Look for: candidate count, drift count (should be 0), failed count (should be 0), aborted=false.
5. **Operator runs `--apply`** with founder approval. If drift in apply: operator inspects with `--force` only after explicit founder green-light.
6. **Soak window: 7 days.** During this window, both legacy `vault.py` and new `vault_v2` paths must work. Operator periodically re-runs `--dry-run` (now reports `already_migrated > 0` for migrated rows). Zero drift in re-runs = soak passing.
7. **Founder approves Phase 4b production deploy.** Includes flipping `USE_CONNECTION_REGISTRY_V2=true` in Cloud Run.
8. **Phase 4b PR 2 ships** (live API swap + `_status_for_install` deletion + lying CLI adapter rewrite). After that lands and is verified in prod, legacy `vault.py` + `oauth_credentials_store.py` may be deleted in a separate cleanup PR.

Until ALL eight steps complete, **Phase 4b stays dev-only.**

---

**End of dev-only guardrails.**
