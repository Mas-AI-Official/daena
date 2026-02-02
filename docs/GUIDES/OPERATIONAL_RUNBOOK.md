# Operational Runbook for Daena AI

## Overview

This runbook provides operational procedures for running Daena AI in production, including common tasks, troubleshooting, and emergency procedures.

## Table of Contents

1. [Daily Operations](#daily-operations)
2. [Weekly Operations](#weekly-operations)
3. [Monthly Operations](#monthly-operations)
4. [Troubleshooting](#troubleshooting)
5. [Emergency Procedures](#emergency-procedures)
6. [Performance Tuning](#performance-tuning)

## Daily Operations

### Morning Checks

```bash
# 1. System Health Check
curl -H "X-API-Key: ops-key" http://localhost:8000/health

# 2. Memory Metrics
curl -H "X-API-Key: ops-key" http://localhost:8000/monitoring/memory

# 3. CAS Efficiency
curl -H "X-API-Key: ops-key" http://localhost:8000/monitoring/memory/cas

# 4. Check for Anomalies
curl -H "X-API-Key: ops-key" http://localhost:8000/api/v1/analytics/anomalies
```

### Key Metrics to Review

- **CAS Hit Rate**: Should be >60%
- **Latency**: L1 <25ms, L2 <120ms
- **Error Rate**: Should be <0.1%
- **Active Agents**: Should be 48 (6×8 structure)
- **Memory Usage**: Check growth rate

### Daily Tasks

```bash
# Run CAS diagnostics
python Tools/daena_cas_diagnostics.py

# Check rate limiting stats
curl -H "X-API-Key: ops-key" \
     http://localhost:8000/api/v1/tenant-rate-limit/stats

# Review analytics summary
curl -H "X-API-Key: ops-key" \
     http://localhost:8000/api/v1/analytics/summary
```

## Weekly Operations

### Monday: Governance Review

```bash
# Generate governance artifacts
python Tools/generate_governance_artifacts.py

# Review policy summary
python Tools/daena_policy_inspector.py

# Check ledger integrity
python Tools/daena_ledger_verify.py
```

### Wednesday: Performance Review

```bash
# Analyze efficiency metrics
curl -H "X-API-Key: ops-key" \
     http://localhost:8000/api/v1/analytics/agents/efficiency

# Review cost tracking
curl -H "X-API-Key: ops-key" \
     http://localhost:8000/monitoring/memory/cost-tracking

# Check communication patterns
curl -H "X-API-Key: ops-key" \
     http://localhost:8000/api/v1/analytics/communication-patterns
```

### Friday: Disaster Recovery Drill

```bash
# Run DR drill
python Tools/daena_drill.py

# Create snapshot
python Tools/daena_snapshot.py

# Verify backups
ls -lh legacy_archive_*.json.zst
```

## Monthly Operations

### First Week: Key Rotation

```bash
# Rotate encryption keys
python Tools/daena_key_rotate.py

# Validate rotation
python Tools/daena_key_validate.py

# Update all services with new key
# (Set DAENA_MEMORY_AES_KEY environment variable)
```

### Second Week: Policy Review

```bash
# Review ABAC policies
python Tools/daena_policy_inspector.py

# Check tenant access
# Review monitoring logs

# Update policies if needed
# Edit config/policy_config.yaml
```

### Third Week: Performance Optimization

```bash
# Analyze trends
# Review Grafana dashboards
# Check analytics data

# Optimize based on findings
# Adjust compression levels
# Tune rate limits
# Update aging policies
```

### Fourth Week: Compliance Audit

```bash
# Generate compliance report
python Tools/generate_governance_artifacts.py

# Export ledger chain
python Tools/ledger_chain_export.py --out ledger_chain_$(date +%Y%m).json

# Review audit logs
# Check for anomalies
```

## Troubleshooting

### Issue: High Latency

**Symptoms:**
- L1 p95 > 25ms
- L2 p95 > 120ms

**Diagnosis:**
```bash
# Check memory metrics
curl -H "X-API-Key: ops-key" \
     http://localhost:8000/monitoring/memory

# Review analytics
curl -H "X-API-Key: ops-key" \
     http://localhost:8000/api/v1/analytics/summary

# Check for bottlenecks
curl -H "X-API-Key: ops-key" \
     http://localhost:8000/api/v1/analytics/communication-patterns
```

**Solutions:**
1. Increase L1 cache size
2. Review compression settings
3. Check network connectivity
4. Optimize queries
5. Scale horizontally if needed

### Issue: Low CAS Hit Rate

**Symptoms:**
- CAS hit rate < 50%
- High LLM costs

**Diagnosis:**
```bash
# Check CAS diagnostics
python Tools/daena_cas_diagnostics.py

# Review request patterns
curl -H "X-API-Key: ops-key" \
     http://localhost:8000/monitoring/memory/cas
```

**Solutions:**
1. Review prompt normalization
2. Adjust SimHash threshold
3. Analyze request patterns
4. Improve caching strategy

### Issue: Memory Growth

**Symptoms:**
- Storage growing rapidly
- High memory usage

**Diagnosis:**
```bash
# Check memory stats
curl -H "X-API-Key: ops-key" \
     http://localhost:8000/monitoring/memory

# Review aging policies
python Tools/daena_policy_inspector.py
```

**Solutions:**
1. Run aging scheduler
2. Review retention policies
3. Tighten compression
4. Archive old data

### Issue: Divergence Errors

**Symptoms:**
- Divergence rate > 1%
- Trust manager failures

**Diagnosis:**
```bash
# Check divergence metrics
curl -H "X-API-Key: ops-key" \
     http://localhost:8000/monitoring/memory

# Review trust manager logs
# Check ledger entries
```

**Solutions:**
1. Review trust manager settings
2. Check data quality
3. Verify consistency checks
4. Adjust divergence thresholds

## Emergency Procedures

### Service Outage

1. **Check Health**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Review Logs**
   ```bash
   kubectl logs -f deployment/daena-production
   ```

3. **Check Metrics**
   ```bash
   curl -H "X-API-Key: ops-key" \
        http://localhost:8000/monitoring/memory
   ```

4. **Rollback if Needed**
   ```bash
   python Tools/daena_rollback.py
   ```

### Data Corruption

1. **Stop Writes**
   ```bash
   export DAENA_NBMF_ENABLED=false
   ```

2. **Verify Integrity**
   ```bash
   python Tools/daena_ledger_verify.py
   ```

3. **Restore from Snapshot**
   ```bash
   python Tools/daena_snapshot.py --restore latest_snapshot.json
   ```

4. **Replay Ledger**
   ```bash
   python Tools/daena_replay.py --ledger .ledger/ledger.jsonl
   ```

### Security Incident

1. **Rotate Keys Immediately**
   ```bash
   python Tools/daena_key_rotate.py
   ```

2. **Review Access Logs**
   ```bash
   # Check ledger for unauthorized access
   python Tools/daena_ledger_verify.py
   ```

3. **Revoke Compromised Credentials**
   ```bash
   # Update API keys
   # Revoke tenant access if needed
   ```

4. **Generate Incident Report**
   ```bash
   python Tools/generate_governance_artifacts.py
   ```

## Performance Tuning

### CAS Optimization

```bash
# Adjust SimHash threshold (in memory_config.yaml)
simhash_threshold: 0.88  # Lower = more matches

# Review normalization
# Check prompt preprocessing
```

### Memory Tier Tuning

```bash
# Adjust L1 cache size
# Edit memory_config.yaml
l1_cache_size: 10000

# Tune compression
zstd_level: 17  # Higher = better compression, slower

# Adjust aging policies
# Edit aging schedules
```

### Rate Limiting Tuning

```bash
# Adjust tenant limits
export DAENA_TENANT_RATE_LIMIT_RPM=2000

# Review utilization
curl -H "X-API-Key: ops-key" \
     http://localhost:8000/api/v1/tenant-rate-limit/stats
```

## Monitoring Checklist

### Every Hour

- [ ] Check CAS hit rate
- [ ] Monitor latency percentiles
- [ ] Review error rates
- [ ] Check active agents

### Every Day

- [ ] Review governance artifacts
- [ ] Check for anomalies
- [ ] Review cost tracking
- [ ] Verify backups

### Every Week

- [ ] Run DR drill
- [ ] Review performance trends
- [ ] Check communication patterns
- [ ] Optimize based on data

### Every Month

- [ ] Rotate encryption keys
- [ ] Review policies
- [ ] Performance optimization
- [ ] Compliance audit

## Escalation Path

1. **Level 1**: Operations Team
   - Monitor metrics
   - Run diagnostics
   - Basic troubleshooting

2. **Level 2**: Engineering Team
   - Investigate issues
   - Tune configurations
   - Optimize performance

3. **Level 3**: Architecture Team
   - Design changes
   - Major updates
   - System redesign

## Contact Information

- **On-Call**: [Contact Info]
- **Escalation**: [Contact Info]
- **Documentation**: docs/
- **Runbooks**: docs/OPERATIONAL_RUNBOOK.md

---

**Last Updated**: 2025-01-XX  
**Status**: ✅ Production Ready  
**Version**: 2.0.0

