# Phase 1 Launch Runbook – NBMF Governance Upgrade

## Purpose
Guide platform operators through the rollout of Phase 1 (governance & audit hardening) enhancements, ensuring manifests, ledger verification, and observability assets are live before enabling further phases.

## Prerequisites
- Repository updated with latest Phase 1 code.
- `DAENA_MEMORY_AES_KEY` available for current deployment.
- Optional: `DAENA_KMS_SIGNING_KEY` if manifest signatures are required on day one.

## Step-by-Step
1. **Bootstrap**
   - `python Tools/daena_memory_switch.py --status`
   - Confirm `read_mode` aligns with planned deployment (legacy/hybrid/nbmf).
2. **Install/Update CLI Tools**
   - Ensure new Tools exist: `daena_key_rotate.py`, `daena_key_validate.py`, `daena_ledger_verify.py`.
   - Run `python Tools/daena_ledger_verify.py` to populate `.ledger/`.
3. **Create Initial Manifest Chain**
   - Execute rotation once (even if same key) to seed manifest log:
     ```bash
     python Tools/daena_key_rotate.py --dry-run  # optional verification
     python Tools/daena_key_rotate.py --operator "initial-seed" --signing-key "$DAENA_KMS_SIGNING_KEY"
     ```
   - Validate immediately: `python Tools/daena_key_validate.py --signing-key "$DAENA_KMS_SIGNING_KEY"`
4. **Dashboard Deployment**
   - Import `monitoring/dashboards/nbmf_observability.json` into Grafana/Honeycomb.
   - Attach Prometheus scrape to `/monitoring/memory/prometheus`.
5. **Documentation & Comms**
   - Share `Governance/NBMF_governance_sop.md` with governance board.
   - Log completion in ledger: `log_event(action="phase1_launch", ...)` (automatic via CLI optional script below).
6. **Verify End-to-End**
   - `python Tools/daena_cutover.py --verify-only`
   - `pytest --noconftest tests/test_memory_metrics_endpoint.py tests/test_ledger_verify.py`

## Post-Launch Tasks
- Schedule weekly ledger + manifest checks (automate via cron/CI).
- Add dashboards to leadership meeting agenda.
- Prepare backlog items for Phase 2 (TrustManager v2, chaos routines).

## Helpful Commands
```bash
# One-liner to log launch completion
python - <<'PY'
from memory_service.ledger import log_event
log_event(action="phase1_launch", ref="rollout", store="nbmf", route="governance", extra={"status": "completed"})
PY
```

Keep this runbook alongside SOP for future audits. Update after every policy change.

