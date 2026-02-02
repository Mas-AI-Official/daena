# QA Guardian Module Documentation

**Version:** 1.1.0  
**Last Updated:** 2026-01-21  
**Module Path:** `backend/qa_guardian/`

---

## Overview

QA Guardian is Daena's production-grade quality assurance and self-healing subsystem. It provides:

1. **Error Detection** - Catches errors across backend, frontend, agents, departments, and workflows
2. **Safe Self-Correction** - Proposes fixes with risk assessment and founder approval gates
3. **Audit Trail** - Complete logging of all incidents, proposals, and actions
4. **Quarantine** - Isolates misbehaving agents and manages recovery

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                          QA GUARDIAN                                │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐           │
│   │   Triage    │───▶│  Analysis   │───▶│   Propose   │           │
│   │   Agent     │    │   Engine    │    │   Fix       │           │
│   └─────────────┘    └─────────────┘    └──────┬──────┘           │
│                                                 │                   │
│   ┌─────────────┐    ┌─────────────┐    ┌──────▼──────┐           │
│   │ Quarantine  │◀───│  Decision   │◀───│   Verify    │           │
│   │  Manager    │    │   Engine    │    │   Tests     │           │
│   └─────────────┘    └─────────────┘    └──────┬──────┘           │
│                                                 │                   │
│                           ┌─────────────────────▼───────────────┐  │
│                           │      FOUNDER APPROVAL GATE          │  │
│                           │   (Required for MEDIUM/HIGH risk)   │  │
│                           └─────────────────────┬───────────────┘  │
│                                                 │                   │
│                           ┌─────────────────────▼───────────────┐  │
│                           │           COMMIT FIX                │  │
│                           │    (Apply changes + run tests)      │  │
│                           └─────────────────────────────────────┘  │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘
```

---

## API Endpoints

### Status & Control

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/qa/status` | Get QA Guardian status |
| POST | `/api/v1/qa/start` | Start guardian loop |
| POST | `/api/v1/qa/stop` | Stop guardian loop |
| POST | `/api/v1/qa/kill-switch` | Emergency stop all auto-fixes |

### Incidents

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/qa/incidents` | List all incidents |
| GET | `/api/v1/qa/incidents/{id}` | Get incident details |
| POST | `/api/v1/qa/incidents` | Create an incident manually |
| PUT | `/api/v1/qa/incidents/{id}/close` | Close an incident |

### Proposals & Approvals

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/qa/proposals` | List patch proposals |
| GET | `/api/v1/qa/proposals/{id}` | Get proposal details |
| POST | `/api/v1/qa/proposals/{id}/approve` | Founder approves proposal |
| POST | `/api/v1/qa/proposals/{id}/deny` | Founder denies proposal |

### Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/qa/run-regression` | Trigger regression tests |
| POST | `/api/v1/qa/run-security-scan` | Trigger security scan |
| POST | `/api/v1/qa/rollback/{id}` | Rollback a committed fix |

### UI

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/qa/ui` | QA Guardian Dashboard |
| GET | `/api/v1/qa/approvals` | Approval Workflow UI |

---

## Components

### 1. Guardian Loop (`guardian_loop.py`)

The main orchestration loop that:
- Monitors for new errors (queued from various sources)
- Creates incidents
- Dispatches to specialized agents
- Manages the two-phase commit process

```python
from backend.qa_guardian.guardian_loop import get_guardian_loop

loop = get_guardian_loop()
loop.start()  # Begin monitoring
loop.report_error("ValidationError", "Missing required field: email")
```

### 2. Decision Engine (`decision_engine.py`)

Applies Charter rules to determine:
- Severity level (P0-P4)
- Risk level (CRITICAL, HIGH, MEDIUM, LOW)
- Whether auto-fix is allowed
- Deny-list violations

```python
from backend.qa_guardian.decision_engine import DecisionEngine

engine = DecisionEngine()
result = engine.assess_risk(proposed_files=["backend/routes/auth.py"])
# Returns: {"risk_level": "HIGH", "deny_list_touched": ["auth"], "requires_approval": True}
```

### 3. Control API (`control_api.py`)

The unified interface for Daena VP:

```python
from backend.qa_guardian import get_control_api

api = get_control_api()

# Create incident
incident = await api.create_incident(
    source="runtime",
    error_type="ValidationError",
    error_message="Missing field"
)

# Propose fix
proposal = await api.propose_fix(
    incident_id=incident.incident_id,
    files=[FileChange(file_path="backend/routes/tasks.py", ...)],
    reasoning="Added missing validation",
    verification_plan=VerificationPlan(...),
    rollback_plan=RollbackPlan(...)
)

# If high-risk, request approval
if proposal.risk_level in ["HIGH", "CRITICAL"]:
    approval = await api.request_founder_approval(proposal.proposal_id)
```

### 4. Quarantine Manager (`quarantine.py`)

Manages agent isolation:

```python
from backend.qa_guardian import get_quarantine_manager

qm = get_quarantine_manager()

# Record an incident (may trigger quarantine)
result = qm.record_incident("inc_001", "agent_marketing_lead", "P1")

# Check if quarantined
status = qm.get_quarantine_status("agent_marketing_lead")

# Restore (requires founder approval)
qm.restore_agent("agent_marketing_lead", founder_approved=True)
```

### 5. Specialized Agents (`agents/`)

| Agent | Purpose |
|-------|---------|
| `qa_triage_agent` | Collect errors, categorize, create incidents |
| `qa_regression_agent` | Run tests and golden workflows |
| `qa_security_agent` | Secrets scan, dependency audit |
| `qa_code_review_agent` | Read diffs, produce reviews |
| `qa_auto_fix_agent` | Generate safe patches |
| `qa_reporter_agent` | Publish to dashboard, create issues |

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `QA_GUARDIAN_ENABLED` | `false` | Master enable switch |
| `QA_GUARDIAN_KILL_SWITCH` | `false` | Emergency stop |
| `QA_GUARDIAN_AUTO_FIX` | `false` | Allow automatic fixes |
| `QA_GUARDIAN_LOG_LEVEL` | `INFO` | Logging verbosity |
| `QA_GUARDIAN_RATE_LIMIT` | `5` | Max auto-fixes per hour |
| `QA_MODEL_FAST` | `gpt-4o-mini` | Model for log parsing |
| `QA_MODEL_REASONING` | `o1` | Model for root cause analysis |
| `QA_MODEL_CODE` | `claude-3-5-sonnet` | Model for code patches |

### Enable QA Guardian

In `START_DAENA.bat`:
```batch
set "QA_GUARDIAN_ENABLED=true"
set "QA_GUARDIAN_AUTO_FIX=false"
```

Or via environment:
```bash
export QA_GUARDIAN_ENABLED=true
export QA_GUARDIAN_AUTO_FIX=false
```

---

## Deny-List

The following areas **NEVER** allow automatic modification:

1. **Authentication** - `**/auth/**`, `**/jwt/**`, `**/login/**`
2. **Authorization** - `**/permissions/**`, `**/roles/**`, `**/rbac/**`
3. **Billing** - `**/billing/**`, `**/payment/**`, `**/stripe/**`
4. **Secrets** - `**/.env*`, `**/secrets/**`, `**/keys/**`
5. **Database** - `**/migrations/**`, `**/alembic/**`
6. **Encryption** - `**/crypto/**`, `**/ssl/**`, `**/tls/**`
7. **Deployment** - `**/deploy/**`, `**/k8s/**`, `**/terraform/**`
8. **Founder** - `**/founder/**`, `**/admin/**`
9. **Audit** - `**/audit/**`, `**/ledger/**`
10. **Charter** - `QA_GUARDIAN_CHARTER.md`

See full list in `backend/qa_guardian/__init__.py`.

---

## Two-Phase Commit Flow

```
1. DETECT → Collect evidence, create incident
2. PROPOSE → Generate patch + verification + rollback plan
3. VERIFY → Run tests, golden workflows
4. COMMIT → Apply changes (only after approval if risky)
```

### Low Risk (P3/P4, no deny-list)
- Auto-fix allowed
- Apply immediately after verification passes
- Log everything

### Medium Risk
- 5-minute delay before applying
- Founder can object
- Enhanced monitoring after commit

### High/Critical Risk
- **STOP** - Never auto-apply
- Create approval request
- Founder must explicitly approve
- Enhanced monitoring for 24 hours

---

## Approval Workflow

### Approval Request
```json
{
  "approval_id": "apr_20260121_001",
  "proposal_id": "patch_001",
  "incident_id": "inc_042",
  "risk_level": "HIGH",
  "deny_list_areas": ["backend/routes/auth.py"],
  "expires_at": "2026-01-21T22:00:00Z",
  "status": "pending"
}
```

### Founder Actions
1. **APPROVE** - Apply the patch
2. **DENY** - Reject with reason (required)
3. **REQUEST_MORE_INFO** - Ask for clarification
4. **DEFER** - Extend expiry window

### Access Approval UI
```
http://localhost:8000/api/v1/qa/approvals
```

---

## Audit Logging

All actions are logged to:
- `logs/qa_guardian_control_api.jsonl`
- `logs/qa_guardian_quarantine.jsonl`
- Database `qa_audit_logs` table

Log format:
```json
{
  "timestamp": "2026-01-21T18:00:00Z",
  "action": "create_incident",
  "actor": "daena_vp",
  "incident_id": "inc_001",
  "severity": "P2"
}
```

---

## Testing

### Run QA Guardian Tests
```bash
cd d:\Ideas\Daena_old_upgrade_20251213
.\venv_daena_main_py310\Scripts\python.exe -m pytest tests/qa_guardian/ -v
```

### Run Golden Workflows
```bash
.\venv_daena_main_py310\Scripts\python.exe -m pytest tests/golden_workflows/ -v
```

### Run Wiring Audit
```bash
.\venv_daena_main_py310\Scripts\python.exe -m pytest tests/test_wiring_audit.py -v
```

---

## Daena Integration

Daena VP can use the Guardian Control API:

```python
# In Daena's decision loop
from backend.qa_guardian import get_control_api

api = get_control_api()

# Daena detects an issue
incident = await api.create_incident(
    source="daena_observation",
    error_type="PerformanceDegradation",
    error_message="Response time increased 5x",
    severity="P2"
)

# Daena proposes a fix
proposal = await api.propose_fix(
    incident_id=incident.incident_id,
    files=[...],
    reasoning="Optimize database query",
    verification_plan=...,
    rollback_plan=...
)

# If approval required, Daena waits
if proposal.risk_level in ["HIGH", "CRITICAL"]:
    approval = await api.request_founder_approval(proposal.proposal_id)
    # Daena waits for founder action
```

---

## References

- **Charter:** `docs/QA_GUARDIAN_CHARTER.md`
- **Implementation Summary:** `docs/FULL_SYSTEM_IMPLEMENTATION_SUMMARY.md`
- **Broken Wiring Report:** `docs/BROKEN_WIRING_REPORT.md`

---

*QA Guardian - Keeping Daena safe and reliable*
