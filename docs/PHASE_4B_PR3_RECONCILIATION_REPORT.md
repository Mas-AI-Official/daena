# Phase 4b PR 3 — Reconciliation + Soak Tooling

**Status:** Complete (local dev only).
**Date:** 2026-05-01.
**Branch:** `rebuild-connections-mcp-runtime`.
**Builds on:** Phase 4b PR 2 (commit `27fe9d6`).

## What this PR adds

Operator-facing tooling to detect drift between three sources of truth
during the soak window:

| Source | What it stores |
|---|---|
| `connector_instances` (legacy) | per-user installs + status string |
| `connection_v2` (V2) | 6 truth dims + per-dim failure metadata |
| `secrets` (V2 vault) | envelope-encrypted credentials |

A reconciliation report flags any place these three disagree, **without
ever printing plaintext secrets**.

## Files

| File | Role |
|---|---|
| `backend/app/services/connection_v2/reconciliation.py` | `ConnectionReconciliationService`, `ReconciliationReport`, `DriftEntry` |
| `backend/app/api/v1/connections_v2.py` (modified) | `GET /reconciliation/status` + `POST /reconciliation/run` (FOUNDER+) |
| `backend/scripts/reconcile_connection_v2.py` | CLI wrapper, dry-run default, JSON report option |
| `backend/tests/test_connection_v2_reconciliation.py` | 12 tests covering all 8 founder-mandated areas |
| `backend/app/services/connection_v2/state_machine.py` (small fix) | Defensive UTC tz coercion for SQLite-backed dev tests |

## Drift kinds detected

| Kind | Severity | What it means |
|---|---|---|
| `missing_v2_mirror` | warn | legacy row exists, no V2 row — mirror writer didn't run |
| `missing_legacy_row` | info | V2 row has no legacy counterpart — V2-native row, expected |
| `status_mismatch` | warn | `legacy.status` disagrees with V2 `derive_label` mapped via `label_to_legacy_status` |
| `stale_probe` | info | callable=True but `callable_at` older than threshold (default 24h) |
| `secret_drift` | info | legacy has creds but no V2 `Secret` row exists for this connection |
| `orphan_op_lock` | warn | `connection_v2_op_lock` row with `expires_at` in the past |
| `legacy_orphan_connector` | warn | legacy instance references a non-existent Connector |
| `apply_refused_flag_off` | error | safety belt: `apply=True` requested but `USE_CONNECTION_REGISTRY_V2` is False |

## Safety contract (founder-locked)

1. **Always read-only by default.** `apply=False` (the default) never
   writes anything.
2. **`apply=True` is silently downgraded to `apply=False`** if
   `USE_CONNECTION_REGISTRY_V2` is False. A drift entry of kind
   `apply_refused_flag_off` is added to the report so the operator
   sees why.
3. **Even with `apply=True`, only `orphan_op_lock` rows can be cleaned
   automatically.** Legacy `ConnectorInstance` rows and `Secret` rows
   are NEVER mutated by this service. Vault migration is a separate
   founder-approved tool.
4. **Plaintext secrets / KEK / DEK material are NEVER included in any
   drift entry.** A canary test in
   `test_connection_v2_reconciliation.py::TestNoSecretLeakage`
   asserts a marker secret never appears in the JSON-serialized report.

## API surface

### `GET /api/v1/connections/v2/reconciliation/status`

Read-only snapshot of the current tenant. Always fresh (no cache).
Requires FOUNDER role.

```json
{
  "success": true,
  "v2_enabled": false,
  "data": {
    "started_at": "...",
    "finished_at": "...",
    "duration_ms": 12,
    "apply_mode": false,
    "legacy_row_count": 7,
    "v2_row_count": 5,
    "secret_row_count": 0,
    "mutations_applied": 0,
    "counters": {
      "missing_v2_mirror": 2,
      "status_mismatch": 1,
      "secret_drift": 4
    },
    "drift": [...],
    "has_drift": true
  }
}
```

### `POST /api/v1/connections/v2/reconciliation/run`

Triggers a fresh run. Query params:

| Param | Default | Effect |
|---|---|---|
| `apply` | `false` | When `true` AND V2 flag on, cleans expired op-locks |
| `all_tenants` | `false` | Founder scope-bypass: scan every tenant |

Same response shape as the GET. Adds `applied_requested` +
`applied_effective` so the caller can tell whether `apply=True` was
honored.

## CLI usage

```bash
# Dry-run, all tenants, summary to stdout
python backend/scripts/reconcile_connection_v2.py

# Verbose (every drift entry)
python backend/scripts/reconcile_connection_v2.py -v

# Single tenant, JSON report to file
python backend/scripts/reconcile_connection_v2.py \
    --tenant-id 11111111-1111-1111-1111-111111111111 \
    --report-json /tmp/drift.json

# Apply safe mutations (op-lock cleanup only)
python backend/scripts/reconcile_connection_v2.py --apply
```

Exit codes:
- `0` — clean, no drift
- `1` — drift detected
- `2` — invalid invocation

## Tests

12/12 in `test_connection_v2_reconciliation.py` PASS.
Combined Phase 4b PR1+PR2+PR3 + runtime adapter suite: **113/113 PASS**.

| Test class | Coverage |
|---|---|
| `TestZeroDrift` | empty DB + perfect mirror produce no drift |
| `TestMissingV2Mirror` | legacy without V2 row triggers `missing_v2_mirror` |
| `TestStatusMismatch` | legacy.status disagrees with V2 derived label |
| `TestStaleProbe` | callable_at older than threshold flags as stale |
| `TestV2Only` | V2 row without legacy counterpart is `info` severity |
| `TestFeatureFlagBlocksApply` | `apply=True` refused with V2 flag off |
| `TestNoSecretLeakage` | canary secret never appears in JSON report |
| `TestTenantScoping` | `tenant_id` filter actually scopes |
| `TestReportShape` | report dict has all required fields, JSON-serializable |

## Production blockers (unchanged)

This PR does not unblock production. The following hard stops remain:

1. `USE_CONNECTION_REGISTRY_V2` still defaults to False in `.env`
2. Vault migration `--apply` still requires founder approval
3. Legacy `vault.py` still in place (not deleted)
4. Legacy `oauth_credentials_store.py` still in place (not deleted)

## Next founder actions

1. Review this report.
2. (Optional) Run the CLI locally to see what drift exists in dev:
   `python backend/scripts/reconcile_connection_v2.py -v`
3. When ready: Phase 5 PR 1 starts with frontend rebuild.

## Risks / known issues

- The `status_mismatch` check uses the same `label_to_legacy_status`
  map that the bridge uses to write the status — so the only way a
  mismatch shows up is if (a) the V2 row was probed after the legacy
  row was written, or (b) something other than the bridge wrote the
  legacy status. This is by design; mismatches are real drift.
- `secret_drift` is informational only — vault migration is a
  separate, founder-approved flow (`backend/scripts/migrate_vault_to_v2.py`).
- The reconciliation service does NOT call `probe_and_record` to
  refresh stale rows. Probing has side effects (network calls,
  auth checks); the operator must trigger probes explicitly via
  the V2 API. The reconciler only *reports* staleness.
