# NBMF CI/CD Integration Guide

## Overview

This document describes how NBMF governance artifacts are integrated into the CI/CD pipeline to ensure compliance, auditability, and operational readiness.

## CI/CD Integration

### GitHub Actions Workflow

The `.github/workflows/ci.yml` workflow includes a step to generate governance artifacts automatically on every push to `main`:

```yaml
- name: Generate NBMF governance artifacts
  run: |
    echo "Generating NBMF governance artifacts..."
    python Tools/generate_governance_artifacts.py --output-dir artifacts/governance --skip-drill || echo "Governance artifacts generation failed (non-blocking)"
  continue-on-error: true
```

### Artifacts Generated

The following artifacts are generated and uploaded to GitHub Actions:

1. **`ledger_manifest.json`**: Cryptographic manifest of the ledger with Merkle root
2. **`policy_summary.json`**: Summary of active ABAC and compression policies
3. **`drill_report.json`**: Disaster recovery drill results (optional, skipped in CI for speed)
4. **`governance_summary.json`**: Combined summary of all artifacts

### Artifact Retention

- Artifacts are retained for **30 days** in GitHub Actions
- Artifacts are stored in the `artifacts/governance/` directory
- Accessible via the GitHub Actions UI under "Artifacts"

## Manual Generation

You can also generate governance artifacts manually:

```bash
# Generate all artifacts (including DR drill)
python Tools/generate_governance_artifacts.py

# Skip DR drill for faster generation
python Tools/generate_governance_artifacts.py --skip-drill

# Specify custom output directory
python Tools/generate_governance_artifacts.py --output-dir ./my_artifacts
```

## SEC-Loop CI Integration

### SEC-Loop Test Job

Add to `.github/workflows/ci.yml`:

```yaml
- name: Run SEC-Loop tests
  run: |
    python -m pytest tests/test_self_evolve_policy.py \
      tests/test_self_evolve_retention.py \
      tests/test_self_evolve_abac.py \
      -v
```

### SEC-Loop Artifacts

SEC-Loop events are automatically included in ledger manifests:
- `sec_promote_abstract` - Promotion events
- `sec_rollback_promotion` - Rollback events
- `sec_rollback_batch` - Batch rollback events

These appear in `ledger_manifest.json` and are included in Merkle root calculations.

---

## Pre-Release Checklist

Before each release, ensure:

1. ✅ Governance artifacts are generated successfully
2. ✅ Ledger manifest shows no integrity issues
3. ✅ Policy summary reflects current production policies
4. ✅ DR drill passes (run manually before major releases)
5. ✅ All artifacts are reviewed and approved
6. ✅ SEC-Loop tests pass (if SEC-Loop enabled)

## Integration with Release Process

### Automated (Recommended)

The CI/CD pipeline automatically generates artifacts on every push to `main`. Review the artifacts in the GitHub Actions UI before deploying.

### Manual (For Critical Releases)

For critical releases or when you need a full DR drill:

```bash
# 1. Generate full governance artifacts
python Tools/generate_governance_artifacts.py

# 2. Review artifacts
cat governance_artifacts/governance_summary.json

# 3. Commit artifacts to release branch (optional)
git add governance_artifacts/
git commit -m "chore: Add governance artifacts for v2.0.0"
```

## Artifact Structure

```
artifacts/governance/
├── ledger_manifest.json      # Ledger integrity manifest
├── policy_summary.json        # ABAC + compression policies
├── drill_report.json          # DR drill results (if run)
└── governance_summary.json     # Combined summary
```

## Failure Handling

### Error Handling & Exit Codes

The `generate_governance_artifacts.py` script now returns non-zero exit codes on failure:

- **Exit 0**: All artifacts generated successfully
- **Exit 1**: One or more critical artifacts failed (ledger, policy, or drill)

This ensures CI/CD pipelines fail when governance artifacts cannot be generated, preventing deployment with incomplete audit trails.

### Known Failure Modes

**Ledger Export Failures**:
- **Cause**: Ledger file corruption, missing directory
- **Impact**: CI/CD fails (non-zero exit code)
- **Recovery**: Fix ledger file or regenerate from backup

**Policy Summary Failures**:
- **Cause**: Invalid policy config, missing files
- **Impact**: CI/CD fails (non-zero exit code)
- **Recovery**: Fix policy configuration files

**DR Drill Failures**:
- **Cause**: Backfill errors, missing stores
- **Impact**: CI/CD fails if `--skip-drill` not used
- **Recovery**: Fix underlying issues or skip drill for non-critical builds

**Timeout Protection**:
- **Cause**: Long-running operations (backfill, large ledger)
- **Impact**: Commands timeout after 5 minutes
- **Recovery**: Increase timeout or optimize operations

## Troubleshooting

### Artifacts Generation Fails

If artifact generation fails in CI:

1. Check the GitHub Actions logs for specific errors
2. Run the script locally to reproduce:
   ```bash
   python Tools/generate_governance_artifacts.py
   ```
3. Ensure all dependencies are installed:
   ```bash
   pip install -r backend/requirements.txt
   ```

### Missing Tools

If tools are missing:

```bash
# Verify tools exist
ls Tools/daena_*.py Tools/ledger_chain_export.py

# Check tool permissions
chmod +x Tools/*.py
```

### Database Connection Issues

If database connection fails:

1. Ensure database is initialized
2. Check database connection string in environment variables
3. Run seed script first:
   ```bash
   python backend/scripts/seed_6x8_council.py
   ```

## Best Practices

1. **Review Before Release**: Always review governance artifacts before deploying to production
2. **Run Full DR Drill**: Run full DR drill (without `--skip-drill`) before major releases
3. **Archive Artifacts**: Download and archive artifacts for compliance/audit purposes
4. **Monitor CI**: Set up alerts for CI failures in artifact generation
5. **Version Control**: Consider committing artifacts to a `releases/` directory for historical tracking

## Related Documentation

- [NBMF Production Readiness](./NBMF_PRODUCTION_READINESS.md)
- [NBMF Governance SOP](../Governance/NBMF_governance_sop.md)
- [CI/CD Pipeline](../.github/workflows/ci.yml)

