# Phase 4a-3 — Vault V1 → V2 Migration

**Branch:** `rebuild-connections-mcp-runtime`
**Lock:** ADR-002 D-003
**Scope:** migration script only — no Phase 4b, no ConnectionRegistryV2, no frontend, no deletion of legacy modules.

## What ships

| Path | Type | Purpose |
|---|---|---|
| `backend/app/services/vault_migration.py` | NEW library (~330 LOC) | Pure logic: candidate query, dual-read encrypt+decrypt validation, drift detection, structured counters |
| `backend/scripts/migrate_vault_to_v2.py` | NEW CLI (~145 LOC) | Argparse wrapper: `--dry-run` (default) / `--apply` / `--force` / `--tenant-id` / `--limit` / `--report-json` |
| `backend/tests/test_vault_migration.py` | NEW test (~500 LOC, 20 tests) | Pure helpers + dry-run + apply mode + drift detection + tenant isolation + plaintext-leak prevention |
| `backend/app/models/identity.py` | M (+7) | Add `Tenant.dek_wrapped` Mapped column (column already created by migration 006) |
| `docs/PHASE_4A_VAULT_FOUNDATION.md` | M | Mark Phase 4a-3 done |

## Default mode is dry-run

```
python -m scripts.migrate_vault_to_v2                    # dry-run, all tenants
python -m scripts.migrate_vault_to_v2 --tenant-id <UUID> # dry-run, one tenant
python -m scripts.migrate_vault_to_v2 --report-json out.json  # dry-run + report
python -m scripts.migrate_vault_to_v2 --apply            # WRITE -- requires explicit flag
python -m scripts.migrate_vault_to_v2 --apply --force    # continue past drift (operator override)
python -m scripts.migrate_vault_to_v2 --limit 10         # cap inspection
```

## Counters tracked

Founder requirement set. Each is structured-logged + appears in `--report-json`:

| Counter | Meaning |
|---|---|
| `candidate` | Legacy `ConnectorInstance` rows with `credentials != NULL` |
| `already_migrated` | Corresponding `Secret` row already exists at this `(tenant_id, secret_class, bound_to)` |
| `skipped` | Legacy plaintext is unparseable / not a dict / empty / non-encrypted-string |
| `failed` | Decrypt error (legacy or v2) — distinct from skipped |
| `drift` | Dual-read mismatch (decrypt failed / JSON decode failed / dict inequality) |
| `written` | Secret rows inserted (apply mode only; always 0 in dry-run) |
| `dek_provisioned` | Tenants whose `dek_wrapped` was created in this run (apply only) |

## Dual-read invariant

For every candidate row, the script:
1. Decodes legacy `credentials` to plaintext dict via `app.core.vault.decrypt_dict`
2. Canonicalizes to bytes via `_canonical_json_bytes` (sorted keys, tight separators, UTF-8) so dict ordering doesn't trigger false drift
3. Encrypts under `vault_v2` with AAD = `(class, tenant_id, bound_to=connection_instance:<id>)`
4. **Immediately decrypts** the freshly-produced record under the same DEK + AAD
5. JSON-decodes the roundtripped bytes
6. Compares the roundtripped dict to the original — any mismatch is **drift**

Drift handling:
- **Dry-run**: drift logged + counted; the run continues to inspect remaining candidates.
- **Apply (no `--force`)**: drift halts the batch. No partial writes. Operator must investigate.
- **Apply with `--force`**: drift logged + counted; the drifted row is NOT written; remaining rows continue.

## Plaintext leak prevention

- The `MigrationCounters` dataclass holds counts only.
- The `DriftRecord` dataclass holds `instance_id / tenant_id / bound_to / reason` — never plaintext or ciphertext bytes.
- Structured log fields are explicit allowlist (instance_id, tenant_id, secret_id, version numbers, reason strings).
- The `--report-json` output includes only counters + drift records — never plaintext.
- A test (`test_plaintext_never_appears_in_logs`) plants a sentinel string and asserts it never appears in `caplog`.
- A test (`test_report_drift_records_never_include_plaintext`) plants a sentinel string and asserts it never appears in the JSON-serialized report.

## Legacy data preservation

Per founder rules 6 + 7 + 10: this script **never** sets `ConnectorInstance.credentials = None`. The legacy column stays populated until Phase 4b decides to delete the legacy storage. Likewise, legacy `core/vault.py` and `oauth_credentials_store.py` remain on disk — the script does NOT modify or delete them.

## Graceful precheck

The script runs a pre-check: `'secrets' table exists`. If migration 006 hasn't been applied yet, the run aborts with a clear message and `aborted_reason="secrets_table_missing"` in the report. No work is done; no rows touched.

## Dry-run report (dev DB, 2026-04-30)

Run against the local dev DB (`daena_dev2.db`) after applying migration 006 in dev:

```json
{
  "options": {"dry_run": true, "force": false, "tenant_id": null, "limit": null},
  "counters": {
    "candidate": 44,
    "already_migrated": 0,
    "skipped": 44,
    "failed": 0,
    "drift": 0,
    "written": 0,
    "dek_provisioned": 0
  },
  "drift_records": [],
  "aborted": false,
  "aborted_reason": null
}
```

Interpretation: 44 ConnectorInstance rows have `credentials != SQL NULL` but every cell stores the JSON literal `"null"` (4-char string), which deserializes to Python `None` and gets classified as "skipped/null". **No real encrypted credentials exist in the dev DB to migrate.** The dry-run validates the cipher path is callable end-to-end (via the unit tests) and confirms zero drift.

## What this script does NOT do

- Does not delete legacy `core/vault.py`.
- Does not delete `oauth_credentials_store.py` or its JSON file.
- Does not migrate other secret stores (`VaultSecret` financial table, `oauth_credentials_store.json`, etc.) — only `ConnectorInstance.credentials` for now.
- Does not null `ConnectorInstance.credentials` after writing the new Secret row.
- Does not auto-rotate the legacy KEK.
- Does not call audit-log services (Daena's audit_service signature isn't stable on this branch — counts are structured-logged instead, ready to wire to audit when Phase 4b rebuilds the service layer).

## Test results (2026-04-30)

- `test_vault_migration.py`: **20 / 20 passed in 0.68s**
- Combined vault stack (`test_vault_v2 + test_vault_boot + test_secret_model + test_vault_migration`): **91 / 91 passed**
- Targeted regression (`test_connections + test_extension_permissions + test_runtime_adapters`): **same 78 passed / 2 failed** baseline (2 in-scope failures unchanged, expected-to-be-replaced in Phase 4b per ADR-002 D-010)
- Frontend `tsc --noEmit`: **CLEAN**

## What unblocks Phase 4b

Per ADR-002 D-003 / Phase 4a-3 founder spec: Phase 4b should NOT start until **the dual-read window proves zero drift in production**. The proper sequence:

1. ✅ Phase 4a-1 ships envelope vault foundation (commit `433ab60`)
2. ✅ Phase 4a-2 wires KEK boot validation + Secret model + migration 006 (commit `f0c9f85`)
3. ✅ Phase 4a-3 ships migration script + dual-read validation **dry-run path** (this commit)
4. **NEXT (operator action, NOT Phase 4b yet):** operator runs `--dry-run` against production database and reviews the report
5. **NEXT (operator action):** operator runs `--apply` (with founder approval after dry-run review)
6. **NEXT (7-day soak):** dual-read window where both legacy `core/vault.py` and new `vault_v2` paths are exercised; reconciliation cron emits zero-drift confirmation
7. **THEN:** Phase 4b registry rewrite begins

This script's existence does not unblock Phase 4b on its own — the operator-driven `--apply` + soak window is the gate.

---

**End of Phase 4a-3 doc.**
