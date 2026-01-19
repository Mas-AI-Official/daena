# NBMF Memory Governance SOP (Phase 1)

## Scope
This standard operating procedure covers all activities related to NBMF memory governance for the Daena Sunflower–Honeycomb platform, including:

- Encryption key rotation and manifest handling
- Ledger integrity checks
- Operational readiness for cutover/rollback
- Observability expectations (dashboards, metrics, alerts)

## Responsibilities
- **Memory Ops (Platform)**: execute rotations, maintain manifests, respond to ledger anomalies.
- **Governance Board**: review weekly reports, approve policy changes, own compliance attestations.
- **Security**: manage signing keys, KMS credentials, and incident response.
- **Observability**: maintain dashboards and alerting thresholds.

## Daily / Weekly Checklist
1. Review `/monitoring/memory` snapshot; ensure p95 latencies within SLO (L1 ≤ 25 ms, L2 ≤ 120 ms).
2. Confirm ledger append-only integrity via `python Tools/daena_ledger_verify.py`.
3. Inspect rotation manifest directory for new entries; validate chain with `python Tools/daena_key_validate.py`.
4. Verify dashboards are receiving metrics (Honeycomb/Grafana import provided below).
5. Confirm monitoring endpoints require `X-DAENA-API-KEY`; rotate the key periodically (see Monitoring Auth).
6. Review `config/policy_config.yaml` changes; reload in-service by calling `router.policy.refresh()` or restarting the service.

## Key Rotation Procedure
1. Export current flags for record: `python Tools/daena_memory_switch.py --status`.
2. Run dry-run backfill integrity: `python Tools/daena_cutover.py --verify-only`.
3. Execute rotation (cloud KMS fetches new material automatically when configured):
   ```bash
   python Tools/daena_key_rotate.py \
     --key-id nbmf-memory \
     --operator "<name|automation-id>" \
     --signing-key "$DAENA_KMS_SIGNING_KEY"
   ```
4. Update runtime environment with printed `DAENA_MEMORY_AES_KEY`. Note the `key_version` returned in logs/manifests.
5. Validate manifest chain and ledger immediately after rotation:
   ```bash
   python Tools/daena_key_validate.py --signing-key "$DAENA_KMS_SIGNING_KEY"
   python Tools/daena_ledger_verify.py
   ```
6. Record outcome in governance log (ledger `action="kms_rotation"` + `action="kms_manifest"` already emitted) — ensure key version metadata is captured for audit.

### Cloud KMS Notes
- Set `DAENA_CLOUD_KMS_ENDPOINT` and optional `DAENA_CLOUD_KMS_TOKEN` for automatic key generation.
- Rotation logs include `key_version`; manifests now persist the same to support chain notarization and audit trails.

## Cutover/Rollback Quick Reference
- **Cutover**: `python Tools/daena_cutover.py`
- **Rollback**: `python Tools/daena_rollback.py`
- Always run `daena_cutover.py --verify-only` before switching modes or after rollback.

## Observability
- **Access Policy**: Maintain `config/policy_config.yaml` for role/tenant-based memory permissions. Default allows are broad; any restrictive updates must be reviewed by governance before deployment.
- Dashboards located at `monitoring/dashboards/nbmf_observability.json`.
- Primary metrics exposed:
  - `nbmf_read_p95_ms`, `nbmf_write_p95_ms`
  - `legacy_reads`, `legacy_writes` (should be zero post cutover)
  - Divergence rates (Phase 2 placeholder)
- Prometheus endpoint (secured in Phase 3): `/monitoring/memory/prometheus`.
- **Monitoring Auth**: Set `DAENA_MONITORING_API_KEY` for the service. Clients (dashboards, Prometheus) must pass `X-DAENA-API-KEY` with the matching value. Rotate keys per security policy and update dependent services; log the rotation in the ledger using `log_event(action="monitoring_key_rotate", ...)`.
- **Ledger Chain Relay**: Use `python Tools/ledger_chain_export.py --output <path>` to compute a Merkle root of `.ledger/ledger.jsonl`. Provide `--chain-endpoint` to post the summary to your blockchain relay (honors `DAENA_CHAIN_ENDPOINT`/`DAENA_CHAIN_TOKEN`).
- **Disaster Recovery Drill**: Run `python Tools/daena_drill.py` (optionally `--dry-run` or `--limit <n>`) to execute a legacy backfill replay + ledger verification. Record results and include in quarterly DR reports.

## Governance Review Cadence
- **Weekly**: Ops to send dashboard snapshot + ledger verification results to governance board.
- **Monthly**: Full review including cutover readiness, manifest chain audit, and open issues.

## Incident Response
1. If ledger verification fails:
   - Freeze key operations.
   - Restore ledger from last verified backup.
   - File incident report with governance board.
2. If manifest verification fails:
   - Re-run rotation with new key immediately.
   - Investigate signature mismatch (possible tampering).
3. Document resolution in ledger (`action="incident_report"`).

## Phase 6: Governance Artifact Capture

Operators must snapshot NBMF ledger integrity and policy posture before each release:

1. Generate the Merkle manifest and persist it under `Governance/artifacts/ledger_manifest.json`.
   ```bash
   python Tools/ledger_chain_export.py --print --out Governance/artifacts/ledger_manifest.json
   ```
2. Capture the current ABAC + fidelity summary for audit.
   ```bash
   python Tools/daena_policy_inspector.py > Governance/artifacts/policy_summary.json
   ```
3. Attach both JSON artifacts to the release checklist and notarize the ledger manifest if blockchain posting is enabled.
4. Execute the NBMF drill to capture backfill verification, store snapshot, ledger summary, and policy posture in one report:
   ```bash
   python Tools/daena_drill.py --limit 0 > Governance/artifacts/drill_report.json
   ```
   Or run the bundled automation (used by CI):
   ```bash
   python Tools/generate_governance_artifacts.py
   ```

## Appendices
- **Appendix A**: Dashboard import (see `monitoring/dashboards/nbmf_observability.json`).
- **Appendix B**: CLI reference
  - `Tools/daena_key_rotate.py` – rotation + manifest creation
  - `Tools/daena_key_validate.py` – manifest chain validation
  - `Tools/daena_ledger_verify.py` – ledger integrity
  - `Tools/daena_memory_switch.py` – mode changes

