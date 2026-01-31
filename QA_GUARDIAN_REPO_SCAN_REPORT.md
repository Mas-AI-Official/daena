# QA Guardian Repository Scan Report
**Generated:** 2026-01-21T17:56:45-05:00  
**Project:** Daena - Mas-AI Official Repository  
**Location:** D:\Ideas\Daena_old_upgrade_20251213

---

## EXECUTIVE SUMMARY

This report analyzes the Daena repository to identify existing QA, testing, governance, monitoring, and guardian infrastructure, and determines what needs to be added to create a production-grade QA Guardian system.

**Status:** ⚠️ **Partial Infrastructure Exists - Requires Significant Upgrade**

---

## PART 1: WHAT EXISTS NOW

### ✅ Testing Infrastructure (Basic)

**Found 118 test-related files:**
- **Location:** `tests/` (67 test files), `scripts/` (smoke tests), root-level test scripts
- **Key Files:**
  - `tests/test_comprehensive_suite.py` (20KB)
  - `tests/test_comprehensive_system.py` (13KB)
  - `tests/test_daena_end_to_end.py`
  - `scripts/smoke_test_phases_1_7.py` (comprehensive smoke test)
  - `pytest.ini` (pytest configuration)
  - `docs/2025/2025-12-20/PHASE8_QA_SMOKE_TESTS_COMPLETE.md`

**Capabilities:**
- ✅ End-to-end tests
- ✅ API integration tests
- ✅ Council/department tests
- ✅ NBMF (memory) tests
- ✅ Smoke tests for Phases 1-7
- ✅ Pytest framework configured

**Gaps:**
- ❌ No automated golden workflow verification
- ❌ No regression detection system
- ❌ No incident normalization or triage
- ❌ Tests are not organized by severity/criticality
- ❌ No self-healing or auto-fix capabilities

---

### ⚠️ Guardian Infrastructure (Stub/Minimal)

**Found Guardian Components:**

1. **`Core/guardian/` directory:**
   - `guardian_ai.py` (8 lines - stub with minimal model scanning)
   - `audit_kernel.py` (stub)
   - `daemon_safety.py` (stub)
   - `fault_simulator.py` (stub)
   - `sanity_check.py` (stub)
   - `mesh/` and `rollout/` subdirectories

2. **`security/guardian/` directory:**
   - `guardian_agent.json` (6 lines - basic agent def with permissions)

3. **`Core/recorder/incident_recorder.py`:**
   - Basic event recording (11 lines - stub)

**Status:** These are **placeholder stubs**, not production-ready guardian systems.

**Capabilities:**
- ⚠️ Basic model scanning concept
- ⚠️ Agent definition with permissions
- ⚠️ Incident recording concept

**Gaps:**
- ❌ No runtime incident collection or triage
- ❌ No severity classification
- ❌ No auto-fix or patch generation
- ❌ No approval workflows
- ❌ No deny-list enforcement
- ❌ No two-phase commit
- ❌ No quarantine mechanism

---

### ✅ Monitoring Infrastructure (Basic)

**Found Monitoring Components:**

1. **`monitoring/` directory:**
   - `error_watcher.py` (30 lines - basic log watching)
   - `connection_status_monitor.py`
   - `grafana_dashboard.json`
   - Subdirectories: `failover/`, `grafana/`, `llm_logs/`, `timelog/`, `uptime/`

2. **Core monitoring modules (70+ files):**
   - `Core/monitoring/monitoring_daemon.py`
   - `Core/department_health_monitor.py`
   - `Core/healthcheck.py`
   - Department/phase-specific monitors

3. **Health endpoints:**
   - `backend/routes/health.py`
   - `backend/routes/health_routing.py`

**Capabilities:**
- ✅ Basic error log watching
- ✅ Health check endpoints
- ✅ Grafana dashboard template
- ✅ Department health monitoring

**Gaps:**
- ❌ No structured incident schema
- ❌ No signal aggregation from runtime
- ❌ No correlation with incidents
- ❌ Not integrated with guardian/triage

---

### ✅ Audit & Logging (Extensive)

**Found Audit Components (86+ audit-related files):**

1. **Audit endpoints:**
   - `backend/routes/audit.py`
   - `backend/tools/audit_log.py`
   - `logs/tools_audit.jsonl`

2. **Audit modules:**
   - `Core/guardian/audit_kernel.py`
   - `Core/control/audit_tracker.py`
   - `Core/ethics/decision_audit.py`
   - `Core/reaction_audit/chain_auditor.py`
   - `memory_service/audit.py`
   - `tests/test_audit_and_ledger_chain.py`

3. **Audit documentation:**
   - `docs/COMPREHENSIVE_DAENA_AUDIT_REPORT.md`
   - Various audit reports in `docs/`

**Capabilities:**
- ✅ Comprehensive audit trail
- ✅ Decision auditing
- ✅ Tool call logging
- ✅ Ledger chain audit

**Gaps:**
- ❌ No schema for QA-specific audits
- ❌ No incident replay mechanism
- ❌ Not linked to auto-fix approval

---

### ✅ Governance System (Advanced - CMP)

**Found Governance Components (17+ files):**

1. **Governance folders:**
   - `Governance/` (9 children)
   - `Governance_external/` (NBMF governance SOP)
   - `governance_artifacts/` (summary JSON)

2. **Governance modules:**
   - `Core/governance/` (governance subsystem)
   - `Core/cmp/` (Collaborative Multi-Proposal system)
   - `data/brain_store/governance_queue.json`

**Capabilities:**
- ✅ CMP (Collaborative Multi-Proposal) system
- ✅ Proposal voting and execution
- ✅ Governance queue
- ✅ Audit trail for governance decisions

**Gaps:**
- ❌ Not integrated with QA Guardian approval workflows
- ❌ No QA-specific governance policies
- ❌ No founder approval gates for risky QA fixes

---

### ⚠️ CI/CD Pipeline (Exists, Needs QA Gates)

**Found CI Workflows (.github/workflows/):**

1. **Existing workflows:**
   - `nbmf-ci.yml` (NBMF benchmarking + council tests)
   - `ci.yml` (basic CI)
   - `ci-fixed.yml`
   - `deploy.yml`
   - `requirements-install.yml`
   - `weekly_drill.yml`

**Capabilities:**
- ✅ NBMF benchmarking across CPU/GPU/TPU
- ✅ Council structure validation (8 depts × 6 agents = 48)
- ✅ SEC-Loop tests
- ✅ ModelGateway hardware abstraction test
- ✅ Governance artifact generation
- ✅ Multi-matrix testing

**Gaps:**
- ❌ No secrets scanning
- ❌ No dependency vulnerability scanning
- ❌ No LLM-based PR code review
- ❌ No lint/format enforcement
- ❌ No deterministic quality gates blocking merges
- ❌ No integration with QA Guardian

---

### ✅ Department & Agent System (Robust)

**Database Models:**
- `Department` model (database.py line 61)
- `Agent` model (database.py line 77)
- Sunflower architecture (honeycomb cell adjacency)
- 8 departments × 6 agents = 48 total agents expected

**Capabilities:**
- ✅ Structured department/agent system
- ✅ Relationship tracking
- ✅ Sunflower spatial routing
- ✅ Council configuration validate in CI

**Ready for QA Guardian department integration:** ✅

---

## PART 2: WHAT IS MISSING

### ❌ QA Guardian Charter (Policy Document)
- **Status:** Does not exist
- **Required:** `docs/QA_GUARDIAN_CHARTER.md` with:
  - Purpose, scope, roles
  - Severity framework
  - Auto-fix rules (two-phase commit)
  - High-risk deny list
  - Quarantine rules
  - Tool-call replay requirements
  - Security baseline
  - Emergency stop procedures

---

### ❌ QA Guardian Department (Hidden Department)
- **Status:** Guardian stubs exist, but no QA department
- **Required:** Create hidden `qa_guardian` department with 6 agents:
  1. `qa_triage_agent` - categorize incidents
  2. `qa_regression_agent` - run golden workflows
  3. `qa_security_agent` - secrets/deps/vuln scan
  4. `qa_code_review_agent` - PR review
  5. `qa_auto_fix_agent` - safe patch generation
  6. `qa_reporter_agent` - incidents → dashboard/issues

Each agent needs:
- JSON I/O schema
- Permission boundaries
- Tool access policy
- Audit logging

---

### ❌ Guardian Loop (Runtime Self-Heal)
- **Status:** Error watcher exists but no self-heal loop
- **Required:**
  - Signal collection: exceptions, timeouts, conflicts, failures
  - Incident normalization (schema + idempotency)
  - Decision engine: observe vs auto-fix vs escalate
  -Lock/ownership mechanism
  - Rollback plans
  - Post-fix verification

---

### ❌ Incident Schema & Management
- **Status:** Basic incident recorder stub exists
- **Required:** Full incident lifecycle:
  - incident_id, severity, subsystem, source, evidence, root_cause
  - status tracking (open → proposed → verified → committed → closed)
  - risk_level, approval_required fields
  - Idempotency keys
  - Rollback metadata

---

### ❌ Golden Workflows (Regression Suite)
- **Status:** Smoke tests exist, but not "golden workflows" with auto-verification
- **Required:**
  - Core golden workflow: task → route → execute → log → UI
  - CMP golden workflow: propose → vote → execute → audit
  - Tool reliability golden workflow
  - Memory/logging golden workflow
  - These must ALWAYS pass and be run by qa_regression_agent

---

### ❌ Two-Phase Commit for Auto-Fix
- **Status:** Does not exist
- **Required:**
  1. PROPOSE: generate patch + verification plan + rollback plan
  2. VERIFY: run tests/golden workflows
  3. COMMIT: apply patch only if verification passes
  - High-risk areas require founder approval before COMMIT

---

### ❌ High-Risk Deny List
- **Status:** Does not exist
- **Required:** Explicit list of areas that cannot be auto-modified:
  - auth/identity, permissions/roles
  - billing/payments/pricing
  - secrets/credentials
  - database migrations
  - encryption/security policy
  - production deployment configs

---

### ❌ Founder Approval UI Flow
- **Status:** Does not exist
- **Required:**
  - Dashboard route to show pending risky fixes
  - Approve/Deny buttons with reason field
  - Integration with guardian loop

---

### ❌ Security Scanning in CI
- **Status:** Not in CI pipeline
- **Required:**
  - Secrets scan (GitLeaks, TruffleHog, or similar)
  - Dependency vulnerability scan (Safety, pip-audit, Snyk)
  - Basic SAST/static analysis

---

### ❌ LLM PR Review in CI
- **Status:** Does not exist
- **Required:**
  - Read diff + failing logs (if any)
  - Output structured JSON + human summary
  - Post as PR comment
  - Must NOT be the only gate (advisory only)

---

### ❌ Model Routing Policy for QA
- **Status:** No QA-specific model policy
- **Required:**
  - Fast/cheap model for log parsing
  - Strong reasoning model for root-cause + patches
  - Claude (if available) for code comprehension
  -Configurable via env vars
  - Evidence citations (file + line numbers)

---

### ❌ QA Dashboard Panel
- **Status:** Does not exist
- **Required:** Dashboard route showing:
  - Open incidents + severity
  - Recent proposals, verified fixes, rollbacks
  - Regression run status
  - Security scan summary
  - "Request QA Review" button

---

### ❌ Quarantine Mechanism
- **Status:** Does not exist
- **Required:**
  - If agent/dept causes repeated incidents → quarantine
  - Disable/limit permissions temporarily
  - Route tasks to backup agent
  - Notify founder
  - Require postmortem before re-enable

---

### ❌ Tool-Call Replay & Evidence
- **Status:** Tool audit logs exist, but no replay mechanism
- **Required:**
  - Guardian must log tool call inputs/outputs (redact secrets)
  - Stack traces
  - Reproduction steps
  - File + line citations for code findings

---

## PART 3: RISKS & CONFLICTS

### Potential Conflicts
1. **Department Structure:** Adding a hidden `qa_guardian` department modifies the 8×6=48 agent structure. We must either:
   - Mark `qa_guardian` as hidden (excluded from council count)
   - Update council validation to expect 9 departments
   - **Recommendation:** Mark as hidden, excluded from sunflower routing

2. **Existing Stubs:** `Core/guardian/`, `security/guardian/` have stub files. We should:
   - Preserve existing files
   - Extend/upgrade them OR
   - Create new `qa_guardian/` namespace to avoid conflicts
   - **Recommendation:** Create `backend/qa_guardian/` for new logic

3. **CI Pipeline:** `nbmf-ci.yml` already validates council structure. Adding QA gates could:
   - Slow down CI significantly if LLM review is not async
   - **Recommendation:** Run security scans in parallel, make LLM review async/optional

4. **Database Schema:** Adding incident tables requires migration
   - **Recommendation:** Add incident tables via Alembic migration, non-destructive

### Breaking Change Risks
- ✅ **Low risk** if we:
  - Add new department as "hidden" flag
  - Create new backend/qa_guardian/ namespace
  - Add new routes under `/api/v1/qa/`
  - Make guardian loop opt-in via env var initially
  - No modifications to existing department/agent logic

---

## PART 4: RECOMMENDATIONS

### Phase 1: Foundation (Non-Breaking)
1. Create QA Guardian Charter document
2. Design incident schema (no DB changes yet)
3. Add stub QA Guardian department (marked hidden)
4. Add environment variable `QA_GUARDIAN_ENABLED=false` (opt-in)

### Phase 2: Infrastructure
1. Add incident database tables via Alembic migration
2. Create 6 QA agents with JSON schemas
3. Implement signal collection (errors, timeouts, failures)
4. Build incident normalization

### Phase 3: Guardian Loop
1. Implement decision engine (observe/auto-fix/escalate)
2. Add idempotency, locking, rate limits
3. Implement two-phase commit for safe fixes
4. Add deny-list enforcement

### Phase 4: CI Quality Gates
1. Add secrets scanning (GitLeaks/TruffleHog)
2. Add dependency vuln scanning (pip-audit/Safety)
3. Add lint/format enforcement
4. Add LLM PR review (async, advisory)
5. Make deterministic checks block merges

### Phase 5: UI & Observability
1. Add QA dashboard route
2. Implement founder approval flow
3. Add structured logging for all guardian actions
4. Create golden workflow tests

### Phase 6: Production Hardening
1. Add quarantine mechanism
2. Implement tool-call replay
3. Add emergency kill-switch
4. Performance testing & rate limiting
5. Security audit

---

## PART 5: FILE INVENTORY

### Files to Add (New)
- `docs/QA_GUARDIAN_CHARTER.md`
- `backend/qa_guardian/` (entire directory)
- `backend/qa_guardian/__init__.py`
- `backend/qa_guardian/agents/` (6 agent modules)
- `backend/qa_guardian/schema.py` (incident schema)
- `backend/qa_guardian/guardian_loop.py`
- `backend/qa_guardian/decision_engine.py`
- `backend/qa_guardian/patch_generator.py`
- `backend/routes/qa_guardian.py`
- `frontend/src/features/qa-dashboard/` (UI components)
- `.github/workflows/qa-gates.yml` (new CI workflow)
- `tests/qa_guardian/` (QA guardian tests)
- `tests/golden_workflows/` (golden workflow suite)
- Database migration file (Alembic)

### Files to Modify (Extend)
- `backend/database.py` (add Incident, QAProposal, QAAudit tables)
- `backend/main.py` (register /api/v1/qa routes)
- `backend/config/constants.py` (add QA_GUARDIAN_ENABLED flag)
- `.github/workflows/nbmf-ci.yml` (add QA gates)
- `README.md` (add QA Guardian section)
- `.env` (add QA env vars with safe defaults)

### Files to Preserve (No Changes)
- All existing tests
- All existing guardian stubs (can be deprecated later)
- All existing monitoring
- All existing audit infrastructure

---

## ACCEPTANCE CRITERIA CHECKLIST

Based on user requirements, the QA Guardian system must meet:

- [ ] Guardian Loop runs without crashing the app
- [ ] At least one golden workflow test passes locally and in CI
- [ ] CI blocks merges on failing tests or security scan failures
- [ ] LLM review posts a PR comment with actionable findings
- [ ] Auto-fix is gated and cannot modify high-risk areas without founder approval
- [ ] Quarantine mode works (repeated failures → agent disabled/limited + rerouted)
- [ ] Tool-call replay logging exists (with secret redaction)
- [ ] Founder Approve UI flow for risky fixes (approve/deny with reason)
- [ ] Charter document exists and is complete
- [ ] No secrets in code (all env vars)
- [ ] Additive changes only (no breaking changes)
- [ ] Structured logs for all guardian actions
- [ ] Two-phase commit enforced for auto-fix
- [ ] Deny-list prevents automatic modification of high-risk areas

---

## CONCLUSION

**Current State:** Daena has strong foundations (testing, audit, governance, monitoring) but lacks a production-grade QA Guardian system.

**Gap:** The existing `Core/guardian/` and `security/guardian/` are placeholder stubs, not functional guardian systems.

**Recommendation:** Implement a comprehensive QA Guardian system as a **hidden department** with 6 specialized agents, integrated with existing infrastructure through well-defined APIs, and enforce quality gates in CI/CD.

**Risk Level:** LOW (if implemented as additive, opt-in, hidden department)

**Estimated Complexity:** HIGH (but well-scoped with clear deliverables)

---
**END OF SCAN REPORT**
