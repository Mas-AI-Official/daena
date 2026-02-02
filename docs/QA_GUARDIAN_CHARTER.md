# QA Guardian Charter
## Daena Quality Assurance & Self-Healing System

**Version:** 1.0.0  
**Effective Date:** 2026-01-21  
**Owner:** Founder / Mas-AI  
**Classification:** Internal Policy Document

---

## Table of Contents

1. [Purpose](#a-purpose)
2. [Scope](#b-scope)
3. [Roles & Responsibilities](#c-roles--responsibilities)
4. [Severity Framework](#d-severity-framework)
5. [Auto-Fix Rules (Two-Phase Commit)](#e-auto-fix-rules-two-phase-commit)
6. [High-Risk Deny List](#f-high-risk-deny-list)
7. [Quarantine & Containment](#g-quarantine--containment)
8. [Tool-Call Replay & Evidence](#h-tool-call-replay--evidence)
9. [Audit & Observability](#i-audit--observability)
10. [Security Baseline](#j-security-baseline)
11. [Human Override & Emergency Stop](#k-human-override--emergency-stop)
12. [Amendment Process](#l-amendment-process)

---

## A) Purpose

### Why QA Guardian Exists

The QA Guardian system exists to ensure **quality, reliability, safety, security, and trust** in Daena's operations. It serves as an autonomous quality assurance layer that:

1. **Detects Issues Early** - Continuously monitors runtime behavior, catching errors before they impact users
2. **Prevents Regressions** - Runs golden workflows to ensure core functionality never breaks
3. **Enables Safe Self-Correction** - Applies low-risk fixes automatically while escalating risky changes
4. **Maintains Audit Trail** - Documents all incidents, decisions, and fixes for accountability
5. **Protects Critical Systems** - Enforces strict boundaries around sensitive operations
6. **Builds Trust** - Demonstrates that AI systems can operate safely with appropriate guardrails

### Core Principles

1. **Safety First** - When in doubt, observe and escalate. Never compromise system integrity.
2. **Transparency** - All guardian actions must be logged and auditable.
3. **Minimal Intervention** - Fix only what's broken. Avoid unnecessary changes.
4. **Founder Authority** - Human oversight is paramount for risky decisions.
5. **Defense in Depth** - Multiple layers of protection, never a single point of failure.

---

## B) Scope

### What Guardian CAN Observe

The QA Guardian has **read access** to:

- Runtime logs and exceptions
- Task execution status and failures
- Agent conflicts and timeout events
- Tool call inputs/outputs (with secret redaction)
- Configuration files and environment state
- Test results and CI/CD status
- Memory/context retrieval operations
- User-reported issues (when submitted)
- Dependency manifests and lock files
- Code diffs and pull requests

### What Guardian CAN Change (With Approval Gates)

The QA Guardian may propose changes to:

| Category | Auto-Fix Allowed | Requires Approval |
|----------|------------------|-------------------|
| Log level adjustments | ✅ Yes | ❌ No |
| Retry count tuning | ✅ Yes | ❌ No |
| Timeout adjustments (non-critical) | ✅ Yes | ❌ No |
| Missing env var with safe default | ✅ Yes | ❌ No |
| Type/lint fixes (non-breaking) | ✅ Yes | ❌ No |
| Config typo corrections | ✅ Yes | ❌ No |
| Dependency version bumps (patch) | ⚠️ Conditional | ✅ If security-related |
| Route handler fixes | ⚠️ Conditional | ✅ If breaking |
| Agent behavior modifications | ❌ No | ✅ Always |
| Department structure changes | ❌ No | ✅ Always |
| Workflow modifications | ❌ No | ✅ Always |

### What Guardian Must NEVER Change Automatically

**ABSOLUTE DENY LIST** - These areas require explicit founder approval with no exceptions:

1. **Authentication & Identity** - Login flows, session management, JWT signing
2. **Authorization & Permissions** - RBAC, ABAC, role assignments, access control
3. **Billing & Payments** - Pricing logic, payment processing, subscription management
4. **Secrets & Credentials** - API keys, passwords, tokens, encryption keys
5. **Database Migrations** - Schema changes, data migrations, destructive operations
6. **Encryption & Security Policy** - TLS config, cipher suites, security headers
7. **Production Deployment** - Deploy scripts, infrastructure changes, environment promotion
8. **Founder/Root Commands** - Any command requiring root-level access
9. **Audit Log Modification** - Never modify or delete audit records
10. **This Charter Document** - Changes require formal amendment process

---

## C) Roles & Responsibilities

### Daena (VP Orchestrator)

- Receives incident notifications from QA Guardian
- Routes tasks to appropriate departments
- Escalates critical issues to founder
- Maintains overall system health awareness
- Can request QA review at any time

### QA Guardian Department (Hidden)

The QA Guardian operates as a **hidden department** with 6 specialized agents:

| Agent | Responsibility |
|-------|----------------|
| `qa_triage_agent` | Collect errors, categorize by type (bug/config/security/dependency/data/workflow), produce incident objects |
| `qa_regression_agent` | Run golden workflows + test suite on demand, produce verification reports |
| `qa_security_agent` | Secrets scan + dependency scan + static analysis, produce security reports |
| `qa_code_review_agent` | Read diffs/PRs + CI logs, produce structured reviews with recommendations |
| `qa_auto_fix_agent` | Generate safe patches with rollback plans, enforce two-phase commit, respect deny list |
| `qa_reporter_agent` | Publish incidents/fixes to logs/dashboard, create GitHub issues when configured |

**Hidden Department Rules:**
- Excluded from sunflower routing calculations
- Excluded from council count validation (8 departments × 6 agents = 48)
- Does not appear in public agent listings
- Has elevated read permissions but restricted write permissions

### Founder (Human Authority)

- **Ultimate decision maker** for high-risk changes
- Receives escalations for deny-list areas
- Can approve/deny proposed fixes with reason
- Can invoke emergency kill-switch
- Can quarantine/restore agents
- Can amend this charter

### Department/Agent Responsibilities

When an incident occurs:

1. **Affected Agent** - Must cooperate with triage, provide context
2. **Affected Department** - Must not block guardian access to logs
3. **Other Agents** - Continue normal operations unless quarantine ordered
4. **All Agents** - Must respect guardian directives during incident response

---

## D) Severity Framework

### Severity Levels

| Level | Name | Description | Response Time | Auto-Fix? |
|-------|------|-------------|---------------|-----------|
| **P0** | Critical | System down, data loss, security breach | < 5 min | ❌ Escalate immediately |
| **P1** | High | Major feature broken, significant user impact | < 30 min | ❌ Escalate required |
| **P2** | Medium | Feature degraded, workaround available | < 4 hours | ⚠️ Conditional |
| **P3** | Low | Minor issue, cosmetic, no impact | < 24 hours | ✅ Auto-fix if safe |
| **P4** | Info | Observation, optimization opportunity | Best effort | ✅ Auto-fix if safe |

### Severity Classification Rules

**P0 (Critical):**
- Application crash affecting all users
- Database corruption or data loss
- Security breach or credential exposure
- Payment processing failure
- Complete authentication failure

**P1 (High):**
- Major workflow broken
- Significant performance degradation (>10x slowdown)
- Critical API endpoint down
- Agent stuck in infinite loop
- Memory leak affecting stability

**P2 (Medium):**
- Non-critical feature broken
- Intermittent errors (>5% failure rate)
- Slow response times (>3s average)
- Agent returning incorrect results occasionally
- Third-party integration failing

**P3 (Low):**
- UI display issues
- Minor configuration inconsistencies
- Non-blocking validation errors
- Log verbosity issues
- Documentation inaccuracies

**P4 (Info):**
- Optimization opportunities
- Code style improvements
- Dependency updates available
- Test coverage gaps
- Performance suggestions

### Default Behavior

**STRICT DEFAULT: OBSERVE-ONLY**

Unless ALL of the following are true, Guardian must observe and escalate:

1. Severity is P3 or P4
2. Risk level is LOW
3. Change does NOT touch deny-list areas
4. Verification plan exists and is executable
5. Rollback plan exists and is tested
6. No other incidents are currently active
7. Rate limit not exceeded (max 5 auto-fixes per hour)

---

## E) Auto-Fix Rules (Two-Phase Commit)

### Overview

All auto-fix attempts MUST follow the **Two-Phase Commit Protocol**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                     TWO-PHASE COMMIT FLOW                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐      │
│  │  DETECT  │───▶│ PROPOSE  │───▶│  VERIFY  │───▶│  COMMIT  │      │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘      │
│       │               │               │               │            │
│       ▼               ▼               ▼               ▼            │
│  Collect         Generate        Run tests/        Apply patch     │
│  evidence        patch +         golden            only if         │
│  + context       rollback        workflows         verify passes   │
│                  plan                                              │
│                                                                     │
│  [If High-Risk: Pause before COMMIT and await Founder Approval]    │
└─────────────────────────────────────────────────────────────────────┘
```

### Phase 1: PROPOSE

Guardian must generate:

1. **Patch Definition**
   - File(s) to modify
   - Exact changes (diff format)
   - Reasoning for each change

2. **Verification Plan**
   - Which tests to run
   - Which golden workflows to execute
   - Success criteria (pass/fail thresholds)

3. **Rollback Plan**
   - Steps to revert changes
   - Data backup locations (if applicable)
   - Expected rollback time

4. **Risk Assessment**
   - Risk level (LOW/MEDIUM/HIGH/CRITICAL)
   - Deny-list areas touched (if any)
   - Potential side effects
   - Approval requirements

### Phase 2: VERIFY

Before any patch is applied:

1. **Run Verification Plan**
   - Execute specified tests
   - Run golden workflows
   - Check for unexpected side effects

2. **Validate Success Criteria**
   - All tests must pass (or meet threshold)
   - Golden workflows must succeed
   - No new errors introduced

3. **If Verification Fails**
   - Abort auto-fix
   - Log failure reason
   - Escalate if severity warrants

### Phase 3: COMMIT (Conditional)

**For LOW risk changes:**
- Apply patch automatically if verification passes
- Log all changes with full audit trail
- Schedule post-fix monitoring

**For MEDIUM risk changes:**
- Require 5-minute delay before applying
- Allow founder intervention window
- Apply only if no objection received

**For HIGH/CRITICAL risk changes:**
- **STOP** - Do not apply automatically
- Create approval request
- Notify founder immediately
- Wait for explicit approval with reason
- If approved, proceed with enhanced monitoring

### Approval Request Format

```json
{
  "approval_request_id": "apr_20260121_001",
  "incident_id": "inc_20260121_042",
  "severity": "P1",
  "risk_level": "HIGH",
  "proposed_fix": {
    "files": ["backend/routes/auth.py"],
    "changes": "...(diff)...",
    "reasoning": "Fix session validation bug"
  },
  "deny_list_areas_touched": ["authentication"],
  "verification_status": "PASSED",
  "rollback_plan": "...",
  "requested_at": "2026-01-21T18:09:16Z",
  "expires_at": "2026-01-21T22:09:16Z",
  "founder_action": null
}
```

---

## F) High-Risk Deny List

### Absolute Deny List (Never Auto-Modify)

The following areas **MUST NEVER** be automatically modified by QA Guardian:

| Area | Pattern Matches | Reason |
|------|-----------------|--------|
| **Authentication** | `**/auth/**`, `**/login/**`, `**/session/**`, `**/jwt/**`, `**/oauth/**` | Identity security |
| **Authorization** | `**/permissions/**`, `**/roles/**`, `**/rbac/**`, `**/abac/**`, `**/access/**` | Access control |
| **Billing** | `**/billing/**`, `**/payment/**`, `**/subscription/**`, `**/pricing/**`, `**/stripe/**` | Financial integrity |
| **Secrets** | `**/.env*`, `**/secrets/**`, `**/credentials/**`, `**/keys/**` | Credential security |
| **Database** | `**/migrations/**`, `**/alembic/**`, `DROP TABLE`, `DELETE FROM`, `TRUNCATE` | Data integrity |
| **Encryption** | `**/crypto/**`, `**/encryption/**`, `**/ssl/**`, `**/tls/**` | Security policy |
| **Deployment** | `**/deploy/**`, `**/k8s/**`, `**/terraform/**`, `**/docker-compose.prod**` | Infrastructure |
| **Founder Commands** | `**/root/**`, `**/admin/**`, `**/founder/**` | Authority boundary |
| **Audit Logs** | `**/audit/**`, `**/ledger/**`, `logs/*.jsonl` | Audit integrity |
| **Charter** | `QA_GUARDIAN_CHARTER.md` | Policy integrity |

### Deny List Enforcement

1. **Pre-Patch Check** - Before generating any patch, scan for deny-list patterns
2. **If Match Found** - Immediately flag as HIGH risk, require founder approval
3. **No Exceptions** - Even "safe" changes to deny-list files require approval
4. **Logging** - All deny-list access attempts are logged with full context

### Escalation for Deny-List Changes

When a fix requires modifying deny-list areas:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DENY-LIST ESCALATION FLOW                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. Guardian detects issue in deny-list area                        │
│  2. Guardian generates patch proposal (read-only analysis)          │
│  3. Guardian creates PRIORITY escalation to Founder                 │
│  4. Notification sent via all configured channels                   │
│  5. Guardian enters WATCH mode (no auto-fix attempts)               │
│  6. Founder reviews with full context:                              │
│     - Incident details                                              │
│     - Proposed patch (diff)                                         │
│     - Risk assessment                                               │
│     - Verification results                                          │
│     - Rollback plan                                                 │
│  7. Founder decides: APPROVE / DENY / REQUEST_MORE_INFO             │
│  8. If APPROVED: Guardian applies patch with enhanced monitoring    │
│  9. If DENIED: Guardian logs decision, marks incident as "blocked"  │
│  10. Post-fix verification runs automatically                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## G) Quarantine & Containment

### Quarantine Triggers

An agent or department is quarantined when:

1. **Repeated Failures** - 3+ incidents within 1 hour from same source
2. **Critical Incident** - Single P0/P1 incident from agent behavior
3. **Resource Exhaustion** - Agent consuming excessive resources
4. **Security Violation** - Attempt to access unauthorized resources
5. **Infinite Loop** - Agent detected in non-terminating state
6. **Manual Trigger** - Founder explicitly quarantines

### Quarantine Actions

| Action | Description |
|--------|-------------|
| **DISABLE** | Agent stopped, no new tasks assigned |
| **LIMIT** | Reduced permissions, read-only mode |
| **REDIRECT** | Tasks routed to backup agent |
| **ISOLATE** | Network access restricted |
| **NOTIFY** | Founder alerted immediately |

### Quarantine Procedure

```python
# Quarantine State Machine
class QuarantineState:
    ACTIVE = "active"           # Normal operation
    SUSPECTED = "suspected"     # Under observation
    QUARANTINED = "quarantined" # Fully isolated
    RECOVERING = "recovering"   # Postmortem complete, testing
    RESTORED = "restored"       # Back to normal

# Transitions
ACTIVE -> SUSPECTED:   # 2+ incidents in 30 min
SUSPECTED -> QUARANTINED:  # 3rd incident OR critical
QUARANTINED -> RECOVERING: # Postmortem approved
RECOVERING -> RESTORED:    # Verification tests pass
RECOVERING -> QUARANTINED: # Verification fails
```

### Restoration Requirements

Before an agent can be restored from quarantine:

1. **Postmortem Required** - Document root cause, contributing factors, timeline
2. **Fix Verified** - Underlying issue must be resolved and verified
3. **Founder Approval** - Explicit approval to restore
4. **Gradual Rollout** - Start with limited traffic (10% → 50% → 100%)
5. **Enhanced Monitoring** - 24-hour observation period post-restore

### Quarantine Notification Template

```json
{
  "event": "AGENT_QUARANTINED",
  "agent_id": "agent_marketing_lead",
  "department": "marketing",
  "reason": "repeated_failures",
  "incident_count": 3,
  "incident_ids": ["inc_001", "inc_002", "inc_003"],
  "quarantine_level": "DISABLE",
  "backup_agent": "agent_marketing_backup",
  "timestamp": "2026-01-21T18:09:16Z",
  "restoration_requirements": [
    "postmortem_approved",
    "fix_verified",
    "founder_approval"
  ]
}
```

---

## H) Tool-Call Replay & Evidence

### Evidence Collection Requirements

All guardian actions must be grounded in **verifiable evidence**:

1. **Tool Call Logs**
   - Input parameters (secrets redacted)
   - Output/response
   - Execution time
   - Error messages (if any)
   - Caller context (which agent, which task)

2. **Stack Traces**
   - Full exception chain
   - File and line numbers
   - Local variable context (non-sensitive)

3. **Reproduction Steps**
   - Sequence of events leading to incident
   - Minimal reproduction case
   - Environment conditions

4. **Code Citations**
   - File path + line numbers
   - Relevant code snippets
   - Git blame/history if applicable

### Secret Redaction Rules

**NEVER log or replay:**
- API keys (pattern: `*_KEY`, `*_SECRET`, `*_TOKEN`)
- Passwords (any field containing `password`, `passwd`, `pwd`)
- Bearer tokens (pattern: `Bearer *`)
- JWT tokens (pattern: `eyJ*`)
- Credit card numbers (pattern: `\d{13,19}`)
- SSNs (pattern: `\d{3}-\d{2}-\d{4}`)

**Redaction format:** `[REDACTED:type]`

Example:
```json
{
  "tool": "http_request",
  "input": {
    "url": "https://api.example.com/data",
    "headers": {
      "Authorization": "[REDACTED:bearer_token]",
      "X-API-Key": "[REDACTED:api_key]"
    }
  }
}
```

### Tool-Call Replay

Guardian supports **deterministic replay** of tool calls for debugging:

1. **Enable Replay Mode** - Set `QA_REPLAY_MODE=true`
2. **Select Incident** - Specify incident ID to replay
3. **Mock External Calls** - External APIs use recorded responses
4. **Verify Behavior** - Compare actual vs expected outcomes

---

## I) Audit & Observability

### Structured Logging Format

All guardian actions use **structured JSON logs**:

```json
{
  "timestamp": "2026-01-21T18:09:16.123Z",
  "level": "INFO",
  "service": "qa_guardian",
  "agent": "qa_triage_agent",
  "action": "incident_created",
  "incident_id": "inc_20260121_042",
  "severity": "P2",
  "subsystem": "api",
  "details": {
    "error_type": "ValidationError",
    "file": "backend/routes/tasks.py",
    "line": 142
  },
  "trace_id": "tr_abc123",
  "span_id": "sp_def456"
}
```

### Incident Schema

```typescript
interface Incident {
  // Identity
  incident_id: string;           // Unique ID (inc_YYYYMMDD_NNN)
  idempotency_key: string;       // Hash of incident signature
  created_at: string;            // ISO timestamp
  updated_at: string;            // ISO timestamp
  
  // Classification
  severity: "P0" | "P1" | "P2" | "P3" | "P4";
  risk_level: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  subsystem: string;             // api, database, agent, workflow, etc.
  category: "bug" | "config" | "security" | "dependency" | "data" | "workflow" | "agent_conflict";
  
  // Source
  source: "runtime" | "ci" | "user_report" | "scheduled_scan";
  affected_agent?: string;
  affected_department?: string;
  
  // Details
  summary: string;               // One-line description
  description: string;           // Full description
  evidence: Evidence[];          // Stack traces, logs, tool calls
  suspected_root_cause?: string;
  reproduction_steps?: string[];
  
  // Response
  proposed_actions: Action[];
  approval_required: boolean;
  owner?: string;                // Assigned agent/human
  
  // Lifecycle
  status: "open" | "triaging" | "proposed" | "awaiting_approval" | 
          "verified" | "committed" | "rolled_back" | "closed";
  resolution?: string;
  closed_at?: string;
}

interface Evidence {
  type: "stack_trace" | "log_entry" | "tool_call" | "code_reference";
  content: string;
  file?: string;
  line?: number;
  timestamp?: string;
}

interface Action {
  action_type: "observe" | "auto_fix" | "escalate" | "quarantine";
  description: string;
  patch?: PatchProposal;
  approval_status?: "pending" | "approved" | "denied";
}
```

### Patch Proposal Schema

```typescript
interface PatchProposal {
  proposal_id: string;
  incident_id: string;
  created_at: string;
  
  // Changes
  files: FileChange[];
  
  // Plans
  verification_plan: VerificationPlan;
  rollback_plan: RollbackPlan;
  
  // Assessment
  risk_level: string;
  deny_list_touched: string[];
  estimated_impact: string;
  
  // Status
  status: "proposed" | "verifying" | "verified" | "applying" | 
          "applied" | "failed" | "rolled_back";
  verification_result?: VerificationResult;
  applied_at?: string;
  applied_by?: string;
}

interface FileChange {
  file_path: string;
  change_type: "modify" | "create" | "delete";
  diff: string;
  reasoning: string;
}

interface VerificationPlan {
  tests: string[];           // Test files to run
  golden_workflows: string[]; // Workflow IDs to execute
  success_criteria: {
    min_test_pass_rate: number;  // e.g., 1.0 (100%)
    max_new_errors: number;      // e.g., 0
  };
}

interface RollbackPlan {
  steps: string[];
  backup_location?: string;
  estimated_time_seconds: number;
  tested: boolean;
}
```

### Verification Report Schema

```typescript
interface VerificationReport {
  report_id: string;
  proposal_id: string;
  created_at: string;
  
  // Results
  tests_run: number;
  tests_passed: number;
  tests_failed: number;
  golden_workflows_run: number;
  golden_workflows_passed: number;
  
  // Verdict
  success: boolean;
  failure_reasons?: string[];
  
  // Details
  test_results: TestResult[];
  workflow_results: WorkflowResult[];
  new_errors_detected: string[];
}
```

---

## J) Security Baseline

### Secret Scanning Policy

**Enforcement:** CI pipeline MUST block merges if secrets detected

**Scan Targets:**
- All committed files
- Environment files (even gitignored)
- CI/CD configuration files
- Docker files and compose configs

**Tools Required:**
- GitLeaks or TruffleHog (pattern-based)
- Custom patterns for Mas-AI specific tokens

**Action on Detection:**
1. Block merge immediately
2. Alert security team / founder
3. Rotate any potentially exposed secrets
4. Document in security log

### Dependency Scanning Policy

**Enforcement:** CI pipeline MUST warn on vulnerabilities, block on CRITICAL

**Scan Frequency:**
- On every PR/push
- Weekly scheduled scan of main branch
- On-demand via QA guardian

**Severity Handling:**
| Vuln Severity | Action |
|---------------|--------|
| Critical | Block merge, escalate immediately |
| High | Block merge, require fix or waiver |
| Medium | Warn, require acknowledgment |
| Low | Warn, log for tracking |

**Tools Required:**
- `pip-audit` or `safety` for Python
- `npm audit` for JavaScript
- Snyk or Dependabot for comprehensive scanning

### Minimum CI Gates

The following checks MUST pass before any merge to main:

1. **Lint/Format** - Code style conformance
2. **Type Check** - Type safety verification (if applicable)
3. **Unit Tests** - All unit tests pass
4. **Integration Tests** - At least one golden workflow passes
5. **Secrets Scan** - No secrets detected
6. **Dependency Scan** - No critical vulnerabilities
7. **Build Success** - Application builds without errors

**LLM PR Review:**
- Advisory only (cannot block merge alone)
- Posts structured findings to PR
- Highlights potential issues for human review

---

## K) Human Override & Emergency Stop

### Founder Kill-Switch

**Environment Variable:** `QA_GUARDIAN_KILL_SWITCH=true`

When enabled:
- All auto-fix attempts immediately halt
- Guardian enters OBSERVE-ONLY mode
- All proposed patches are held (not applied)
- Existing incident locks are released
- Notification sent confirming kill-switch active

**Activation:**
```bash
# Via environment variable
export QA_GUARDIAN_KILL_SWITCH=true

# Via API (founder auth required)
POST /api/v1/qa/kill-switch
Authorization: Bearer <founder_token>
{"action": "enable", "reason": "Emergency maintenance"}
```

### Rate Limits

| Action | Limit | Window | Reset |
|--------|-------|--------|-------|
| Auto-fix attempts | 5 | 1 hour | Rolling |
| Patch proposals | 20 | 1 hour | Rolling |
| Incident creation | 100 | 1 hour | Rolling |
| Approval requests | 10 | 1 hour | Rolling |

When rate limit exceeded:
- Log warning with details
- Enter OBSERVE-ONLY mode
- Alert founder
- Wait for manual reset or window expiry

### Rollback Procedures

**Immediate Rollback (< 1 minute):**
```bash
# Via API
POST /api/v1/qa/rollback/{proposal_id}
Authorization: Bearer <founder_token>

# Response includes:
# - Rollback status
# - Changed files restored
# - Verification result
```

**Full System Rollback:**
1. Activate kill-switch
2. Stop all running patches
3. Restore from last known good state
4. Run golden workflows to verify
5. Notify all stakeholders

### Manual Override Commands

Founders can issue direct commands:

```bash
# Force close an incident (skip verification)
POST /api/v1/qa/incidents/{id}/force-close

# Force approve a patch (skip 2-phase)
POST /api/v1/qa/proposals/{id}/force-approve

# Force quarantine an agent
POST /api/v1/qa/quarantine/{agent_id}

# Force restore an agent
POST /api/v1/qa/restore/{agent_id}
```

**All override commands require:**
- Founder authentication
- Reason documented
- Full audit logging

---

## L) Amendment Process

### Who Can Amend

Only the **Founder** or designated **Charter Steward** can amend this document.

### Amendment Procedure

1. **Proposal** - Create formal amendment proposal with:
   - Section(s) to modify
   - Proposed changes (diff format)
   - Rationale
   - Impact assessment

2. **Review Period** - Minimum 24 hours for review
   - Exception: Security-related amendments can be expedited

3. **Approval** - Founder explicit approval required

4. **Version Update** - Increment version number

5. **Communication** - Notify all stakeholders of changes

6. **Effective Date** - Changes take effect 24 hours after approval
   - Exception: Security-related amendments effective immediately

### Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-01-21 | Founder | Initial charter |

---

## Appendix A: Quick Reference Card

```
┌────────────────────────────────────────────────────────────────────┐
│               QA GUARDIAN QUICK REFERENCE                          │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  DEFAULT MODE: OBSERVE-ONLY                                        │
│                                                                    │
│  AUTO-FIX ALLOWED: P3/P4 + LOW risk + NOT deny-list                │
│                                                                    │
│  TWO-PHASE COMMIT: PROPOSE → VERIFY → COMMIT                       │
│                                                                    │
│  DENY-LIST: auth, billing, secrets, migrations, deploy,            │
│             crypto, permissions, audit, founder, this charter      │
│                                                                    │
│  QUARANTINE: 3 incidents/hour → disable + notify founder           │
│                                                                    │
│  KILL-SWITCH: QA_GUARDIAN_KILL_SWITCH=true                         │
│                                                                    │
│  RATE LIMITS: 5 auto-fixes/hour, 20 proposals/hour                 │
│                                                                    │
│  ESCALATION: High-risk → Founder approval required                 │
│                                                                    │
│  LOGGING: All actions → structured JSON → audit trail              │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## Appendix B: Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `QA_GUARDIAN_ENABLED` | `false` | Master enable for guardian system |
| `QA_GUARDIAN_KILL_SWITCH` | `false` | Emergency stop all auto-fixes |
| `QA_GUARDIAN_AUTO_FIX` | `false` | Allow automatic fix application |
| `QA_GUARDIAN_LOG_LEVEL` | `INFO` | Logging verbosity |
| `QA_GUARDIAN_RATE_LIMIT` | `5` | Max auto-fixes per hour |
| `QA_GUARDIAN_NOTIFY_WEBHOOK` | `` | Webhook for notifications |
| `QA_MODEL_FAST` | `gpt-4o-mini` | Model for log parsing |
| `QA_MODEL_REASONING` | `o1` | Model for root cause analysis |
---

## Appendix C: Frontend Patching Rules

**Added in Version 1.1.0**

### Frontend Changes - Special Handling

Frontend code (HTML, CSS, JavaScript, templates) has **different risk profiles** than backend code:

| Content Type | Auto-Fix Allowed | Notes |
|--------------|------------------|-------|
| CSS styling fixes | ✅ Yes (P3/P4) | Color, spacing, layout |
| HTML typo fixes | ✅ Yes (P3/P4) | Text content only |
| JavaScript lint fixes | ✅ Yes (P3/P4) | Style, unused vars |
| Template rendering fixes | ⚠️ Conditional | If isolated component |
| Form validation changes | ❌ No | Requires approval |
| API endpoint references | ❌ No | Requires approval |
| Auth-related UI | ❌ No | Always requires approval |
| Payment/billing UI | ❌ No | Always requires approval |

### Frontend Patch Proposal Requirements

All frontend patches MUST include:

1. **Affected Files** - List all HTML/CSS/JS/template files
2. **Visual Impact** - Description of UI changes
3. **Functional Impact** - Any behavior changes
4. **Browser Compatibility** - Tested browsers/versions
5. **Rollback Simplicity** - Frontend rollback is usually instant (page refresh)

### Frontend Deny-List Patterns

```
**/templates/login*.html
**/templates/auth*.html
**/templates/payment*.html
**/templates/billing*.html
**/templates/admin*.html
**/templates/founder*.html
**/static/js/*auth*.js
**/static/js/*payment*.js
**/static/js/*security*.js
```

### Frontend Approval Workflow

```
Frontend Patch → Low Risk?
  │
  ├── YES (CSS/text-only) → Auto-Fix + Log
  │
  └── NO (JS logic/forms/API) → Founder Approval Required
                                    │
                                    ├── APPROVED → Apply + Monitor
                                    │
                                    └── DENIED → Close + Document
```

---

## Appendix D: Daena VP Authority

**Added in Version 1.1.0**

### Daena's Role in QA Guardian

Daena VP operates as the **coordinating intelligence** for QA Guardian:

| Action | Daena Authority | Details |
|--------|-----------------|---------|
| Create Incidents | ✅ Full | Can create incidents from any source |
| Propose Fixes | ✅ Full | Can generate patch proposals |
| Request Verification | ✅ Full | Can trigger test runs |
| Apply LOW Risk Fixes | ✅ Conditional | Only if all criteria met |
| Apply MEDIUM Risk Fixes | ⚠️ Delayed | 5-minute window for founder objection |
| Apply HIGH/CRITICAL Fixes | ❌ No | Must request founder approval |
| Escalate to Founder | ✅ Always | Can always escalate |
| Quarantine Agents | ⚠️ Conditional | Only on repeated failures |
| Restore Agents | ❌ No | Founder approval required |
| Modify Deny-List | ❌ Never | Charter amendment only |
| Modify Charter | ❌ Never | Founder only |

### Guardian Control API for Daena

Daena uses the Guardian Control API to interact with QA Guardian:

```python
# Guardian Control API Endpoints (Daena's interface)
class GuardianControlAPI:
    
    # Create a new incident
    async def create_incident(
        self,
        source: str,
        error_type: str,
        error_message: str,
        severity: str = None,  # Auto-classified if None
        subsystem: str = None,
        evidence: List[Evidence] = None
    ) -> Incident
    
    # Propose a fix for an incident
    async def propose_fix(
        self,
        incident_id: str,
        files: List[FileChange],
        reasoning: str,
        verification_plan: VerificationPlan,
        rollback_plan: RollbackPlan,
        target_type: str = "backend"  # "backend" or "frontend"
    ) -> PatchProposal
    
    # Run verification on a proposal
    async def verify_fix(
        self,
        proposal_id: str
    ) -> VerificationReport
    
    # Request founder approval
    async def request_founder_approval(
        self,
        proposal_id: str,
        urgency: str = "normal",  # "normal", "high", "critical"
        notes: str = None
    ) -> ApprovalRequest
    
    # Commit an approved fix
    async def commit_fix(
        self,
        proposal_id: str,
        approval_id: str = None  # Required if approval was needed
    ) -> CommitResult
    
    # Rollback a committed fix
    async def rollback_fix(
        self,
        proposal_id: str,
        reason: str
    ) -> RollbackResult
    
    # Quarantine an agent (repeated failures)
    async def quarantine_agent(
        self,
        agent_id: str,
        reason: str,
        incident_ids: List[str]
    ) -> QuarantineResult
```

### Daena Decision Matrix

When Daena encounters an issue, this matrix determines action:

```
Issue Detected
    │
    ├── Is it already an open incident? 
    │   └── YES → Update existing incident
    │
    └── NO → Create new incident
            │
            ├── Classify severity (P0-P4)
            │
            ├── P0/P1 → IMMEDIATE ESCALATION to founder
            │
            ├── P2 → Can propose fix, needs approval
            │
            ├── P3/P4 → Can auto-fix if:
            │   ├── Risk is LOW
            │   ├── Not in deny-list
            │   ├── Verification passes
            │   ├── Rate limit not exceeded
            │   └── No other active incidents
            │
            └── Otherwise → OBSERVE + ESCALATE
```

---

## Appendix E: Extended Deny-List

**Added in Version 1.1.0**

### Complete Deny-List Patterns

```python
DENY_LIST_PATTERNS = [
    # Authentication & Identity
    "**/auth/**", "**/login/**", "**/session/**", 
    "**/jwt/**", "**/oauth/**", "**/sso/**",
    
    # Authorization & Permissions
    "**/permissions/**", "**/roles/**", "**/rbac/**", 
    "**/abac/**", "**/access/**", "**/acl/**",
    
    # Billing & Payments
    "**/billing/**", "**/payment/**", "**/subscription/**", 
    "**/pricing/**", "**/stripe/**", "**/invoice/**",
    
    # Secrets & Credentials
    "**/.env*", "**/secrets/**", "**/credentials/**", 
    "**/keys/**", "**/*.pem", "**/*.key",
    
    # Database & Migrations
    "**/migrations/**", "**/alembic/**",
    
    # Encryption & Security Policy
    "**/crypto/**", "**/encryption/**", "**/ssl/**", 
    "**/tls/**", "**/certificates/**",
    
    # Deployment & Infrastructure
    "**/deploy/**", "**/k8s/**", "**/terraform/**", 
    "**/docker-compose.prod**", "**/infrastructure/**",
    
    # Founder & Admin Commands
    "**/root/**", "**/admin/**", "**/founder/**",
    
    # Audit & Ledger
    "**/audit/**", "**/ledger/**", "logs/*.jsonl",
    
    # Charter Documents
    "QA_GUARDIAN_CHARTER.md",
    
    # Frontend Security-Sensitive
    "**/templates/login*.html", "**/templates/auth*.html",
    "**/templates/payment*.html", "**/templates/founder*.html",
    "**/static/js/*auth*.js", "**/static/js/*payment*.js",
    
    # Destructive Data Operations (SQL patterns)
    "DROP TABLE", "DROP DATABASE", "TRUNCATE", 
    "DELETE FROM", "UPDATE ... SET ... WHERE 1=1",
]
```

### Deny-List Check API

```python
def is_in_deny_list(path: str) -> bool:
    """Check if a path matches any deny-list pattern"""
    import fnmatch
    normalized = path.replace("\\", "/")
    return any(fnmatch.fnmatch(normalized, p) for p in DENY_LIST_PATTERNS)

def get_deny_list_matches(paths: List[str]) -> List[str]:
    """Return all paths that match deny-list patterns"""
    return [p for p in paths if is_in_deny_list(p)]
```

---

## Appendix F: Approval Workflow UI Requirements

**Added in Version 1.1.0**

### Founder Approval Dashboard

The approval workflow UI MUST provide:

1. **Pending Approvals List**
   - Sorted by urgency (critical first)
   - Shows: proposal_id, incident_id, severity, risk_level, created_at, expires_at
   - Quick approve/deny buttons

2. **Diff Preview**
   - Side-by-side comparison
   - Syntax highlighting
   - Line numbers
   - Affected deny-list areas highlighted in RED

3. **Risk Assessment Panel**
   - Risk level badge (CRITICAL/HIGH/MEDIUM/LOW)
   - Deny-list areas touched
   - Estimated impact
   - Verification results

4. **Verification Results**
   - Tests run / passed / failed
   - Golden workflows status
   - New errors detected (if any)

5. **Action Buttons**
   - **APPROVE** - Apply the patch
   - **DENY** - Reject with reason (required)
   - **REQUEST MORE INFO** - Ask for clarification
   - **DEFER** - Extend expiry window

### Approval Request Expiry

- Default expiry: 4 hours
- Critical severity: 1 hour
- If expired: Auto-close, requires new proposal
- Founder can extend expiry

---

## Version History (Extended)

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-01-21 | Founder | Initial charter |
| 1.1.0 | 2026-01-21 | QA Guardian | Added frontend patching rules, Daena VP authority, extended deny-list, approval workflow UI requirements |

---

**END OF CHARTER**

*This document is the authoritative source for QA Guardian policy and operations.*

