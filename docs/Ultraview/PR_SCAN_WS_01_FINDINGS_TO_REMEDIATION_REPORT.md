# PR-SCAN-WS-01: Scan findings to remediation workstreams - Report

**Date:** 2026-05-02
**Branch:** `rebuild-connections-mcp-runtime`
**Author:** Claude Code (Opus 4.7) under founder direction
**Companion PRs in the same sprint:** PR-GOV-01 (`3639126`), PR-4 scan UX consolidation (`0bd2381`), parked Agent Pack Exporter (`6de2037`), PR-5 workstream spine skeleton (`094ab6f`).

> **Thesis:** PR-4 made the security scan a single Manus-style live workflow but left an actionability hole: a finding's "Remediation" panel is read-only text that cannot turn into trackable work. PR-SCAN-WS-01 closes that hole by making each finding row a single-click source for a Task + Workstream pair, linked back to the originating scan via PR-5's `artifact_refs`. No T5, no chat orchestrator changes, no scan-pipeline rewrite.

---

## 1. Hard rules check (founder brief)

| Rule | Status |
|---|---|
| 1. No production deploy | Yes - local-only changes |
| 2. No `USE_CONNECTION_REGISTRY_V2=true` flip | Yes - flag untouched |
| 3. No `vault --apply` | Yes - vault not invoked |
| 4. No file deletions | Yes - additive only |
| 5. No secrets printed or committed | Yes |
| 6. No external scans | Yes - the new endpoint reads existing scan results; never starts a scan |
| 7. No external messages | Yes |
| 8. No T5 / 3vilbob execution code modified | Yes - `evilbob_mode.py`, `red_team_ops.py`, `report_tiers.py` enum untouched |
| 9. No wholesale rewrite of Chat / Departments / Skills / Company Mode | Yes |
| 10. No agency-agents / new dependencies | Yes - stdlib + existing project libs |
| Em dash in new content (project CLAUDE.md Rule 12) | None introduced in new files |

---

## 2. Endpoint added

### 2.1 New route

`POST /api/v1/security/scans/{scan_id}/findings/{finding_id}/create-remediation`

Path parameters:
- `scan_id` - the `ScanWorkflow` job id (workflow-generated string).
- `finding_id` - either the `SecurityFinding.id` when populated, or the positional fallback `"idx-N"` for findings whose id is empty.

Request body (optional):
```json
{ "department_id": "uuid-or-null" }
```
When `department_id` is omitted, the endpoint falls back to the tenant's first active department by `sunflower_index`. When the requested department is missing or belongs to another tenant, the endpoint returns `422 NO_ACTIVE_DEPARTMENT` (no silent cross-tenant fallback).

Response:
```json
{
  "success": true,
  "data": {
    "task_id": "uuid",
    "workstream_id": "uuid",
    "scan_id": "scan-...",
    "finding_id": "finding-stable-1",
    "finding_title": "SQL injection in /login",
    "severity": "CRITICAL",
    "idempotent": false
  }
}
```

Error mapping:
- `404` - scan_id not found in ScanWorkflow's in-memory job table (or belongs to a different tenant; cross-tenant access is mapped to 404 to avoid id-existence leakage).
- `400` - scan exists but is not yet COMPLETE (`get_scan_report` raises `ValueError`).
- `404` - finding_id does not resolve in the report's findings list.
- `422` - tenant has no active department to own the workstream OR the explicit `department_id` is invalid for this tenant.

### 2.2 Architecture

The endpoint is a thin wrapper around the new pure-function service module. Tests exercise the service directly without spinning up FastAPI.

```
ScanReport.tsx (per-finding button)
  -> POST /security/scans/{scan_id}/findings/{finding_id}/create-remediation
    -> security_dashboard.create_remediation_from_finding (40 LOC wrapper)
      -> 1. workflow._jobs.get(scan_id) + tenant check  (404 on miss)
      -> 2. workflow.get_scan_report(scan_id)            (400/404 on incomplete)
      -> 3. scan_remediation.create_remediation(...)    (the actual logic)
            -> resolve_finding(findings, finding_id)    (FindingNotFoundError)
            -> find_existing_remediation(...)           (idempotency lookup)
            -> resolve_department(...)                  (NoActiveDepartmentError)
            -> ExecutionService.create_task(...)        (the Task)
            -> WorkstreamService.start(StartParams(source_type=SCAN, ...))
            -> attach_artifact_ref scan_report_ids / finding_ids / task_ids
            -> AuditService.log_decision(action_type=scan.remediation_workstream_created)
            -> attach_audit_event_ref
```

---

## 3. Data shape found

### 3.1 SecurityFinding (`backend/app/services/security/report_tiers.py:55`)

The dataclass already carried everything the brief asked for, **except a guarantee of stable id**:

| Brief field | Source field | Notes |
|---|---|---|
| id or stable index | `SecurityFinding.id: str = ""` + positional fallback | The id defaults to empty in some scanner paths; the endpoint accepts the positional `"idx-N"` form so frontend can always submit something. Documented under "remaining debt" below. |
| title | `SecurityFinding.title` | always populated |
| severity | `SecurityFinding.severity: FindingSeverity` enum | CRITICAL / HIGH / MEDIUM / LOW / INFO |
| remediation text | `SecurityFinding.remediation: str` (T2+) | empty string when scan tier was SCOUT |
| target | `SecurityFinding.location: str` | "<file>:<line>" or URL |
| evidence | `SecurityFinding.evidence_chain_id: str` + `poc_artifact*` | not consumed by remediation creation; kept for traceability |
| report id / job id | `ScanReport.job_id` / scan_id path param | already tenant-scoped via `ScanJob.tenant_id` |

### 3.2 Where the report comes from

`workflow.get_scan_report(scan_id)` reads from in-memory cache first, then falls back to `${SECURITY_REPORTS_DIR}/{scan_id}.json` for restart-recovered scans. The `ScanWorkflow._jobs` dict is the source of truth for tenant ownership; restart-recovered scans (no entry in `_jobs`) cannot create remediation today - this is a deliberate trade-off documented in §7.

---

## 4. Task / Workstream mapping

### 4.1 Task (`backend/app/services/execution_service.py`)

Created via the existing `ExecutionService.create_task` path with `also_create_workstream=False` (we create the workstream ourselves with `source_type=SCAN`; the auto-spawn would mis-tag it as `source_type=TASK`). Body composed by `build_task_description`:

```
Remediate: <finding.title>
---
Location: <file:line>
Severity: <CRITICAL|HIGH|MEDIUM|LOW|INFO>
Source scan: <scan_id>
Finding id: <finding_id>
Detected by: <source_tool>
CVE refs: <CVE list>

Remediation guidance:
<finding.remediation>

Suggested fix code:
<finding.fix_code>
```

### 4.2 Workstream (`backend/app/models/workstream.py`)

Per the PR-5 spec:

| Field | Value |
|---|---|
| `source_type` | `WorkstreamSourceType.SCAN` |
| `source_ref_id` | `None` - scan_id is workflow-generated, not UUID; link via artifact_refs instead |
| `goal` | `"Remediate: <finding.title>"` (matches Task name for consistency) |
| `next_step_text` | `finding.remediation[:500]` or fallback "Apply remediation guidance from the source scan finding" |
| `initial_context` | `{spawned_from: "scan_finding", scan_id, finding_id, severity, task_id}` |
| `artifact_refs.scan_report_ids` | `[scan_id]` |
| `artifact_refs.finding_ids` | `[finding_id]` |
| `artifact_refs.task_ids` | `[task_id]` |
| `audit_event_refs` | `[audit_event_id]` after AuditService.log_decision |

The frontend `WorkstreamsPage` (PR-5) renders the SCAN source badge, the artifact ref chips, and the audit-events deep-link without any additional changes.

---

## 5. Idempotency behavior

### 5.1 Strategy

`find_existing_remediation` performs a per-tenant linear scan of Workstreams with `source_type=SCAN AND archived_at IS NULL`, then matches `(scan_id, finding_id)` against the JSON `artifact_refs` dict. When a hit is found:

- The existing Workstream id is returned (no new row created).
- The first entry in `artifact_refs.task_ids` is returned as `task_id` (preserves linkage across retries).
- `idempotent: true` flag is set on the response.
- The frontend toast reads "Remediation already tracked" instead of "Remediation task created".

### 5.2 Why linear scan (not a junction table or composite column)

The brief said: *"If idempotency requires new DB table and is too large, document limitation and return existing matching task by source metadata if easy."*

Linear scan is "easy" (no new schema, idempotent by source metadata). The cost: O(N) per call where N is the number of SCAN-sourced workstreams per tenant. For the realistic bound (small founder workspace, dozens to low hundreds of remediation workstreams over a tenant lifetime, archived ones excluded), this is in the low-millisecond range on SQLite + sub-millisecond on Postgres.

When scale grows past O(thousands of SCAN-sourced workstreams per tenant): introduce a `(tenant_id, scan_id, finding_id)` composite column on Workstream + a unique index. Documented under §7 remaining debt.

### 5.3 Tenant isolation

The idempotency lookup filters on `tenant_id` first. A Workstream that exists for tenant A under `(scan-shared, finding-stable-1)` does NOT short-circuit creation for tenant B with the same pair. Pinned by `test_create_remediation_tenant_isolation`.

---

## 6. UI behavior

### 6.1 New component: `CreateRemediationButton` in `ScanReport.tsx`

Per finding row, after the existing PoC-artifact / verified-fix lines. States:

| State | Render | Trigger |
|---|---|---|
| Idle | `[wrench icon] Create remediation task` button | Default |
| Loading | `[spinner] Creating...` (button disabled) | After click, before response |
| Success (new) | `[checkmark] Created workstream + task` with deep-links | 200 + `idempotent=false` |
| Success (idempotent) | `[checkmark] Already tracked as workstream + task` | 200 + `idempotent=true` |
| Error | inline `text-status-error` message + role="alert" + toast | non-2xx response |
| Disabled | grayed button + italic note "This finding has no stable id..." | Resolved id is empty (never happens with the current `idx-N` fallback, but the guard documents the contract) |

Wording locked: **"Create remediation task"**. Never "auto-fix", never "fix this for me". The button opens trackable work; it does not promise a one-click fix. Per the founder brief: *"Do not claim auto-fix."*

### 6.2 Deep links

After success, the panel renders two links:
- "workstream" -> `/workstreams?focus=<workstream_id>` (the existing WorkstreamsPage; the focus param is honored by future PR-SPINE-06 with deep-link drawer auto-open; today it is graceful-degrade to the list view).
- "task" -> `/tasks` (the existing TasksPage).

Both links are honest: the routes exist today and the rows will be visible. There is no "view details" link to a per-task page that doesn't exist.

### 6.3 Frontend tsc

`npx tsc --noEmit` clean (0 errors).

---

## 7. Tests run

### 7.1 New tests (PR-SCAN-WS-01)

`backend/tests/test_scan_remediation.py` - **18 tests, all green:**

| Group | Test | What it pins |
|---|---|---|
| `resolve_finding` | `test_resolve_finding_by_stable_id` | Stable-id lookup |
| | `test_resolve_finding_by_idx_when_id_empty` | `idx-N` positional fallback |
| | `test_resolve_finding_returns_none_for_unknown` | Unknown id returns None |
| `build_task_description` | `test_build_task_description_includes_severity_and_remediation` | Severity + location + remediation + fix_code in body |
| | `test_build_task_description_handles_minimal_finding` | Sparse finding still produces valid body |
| `create_remediation` happy path | `test_create_remediation_creates_task_and_workstream` | One task + one workstream from one finding |
| | `test_create_remediation_uses_scan_source_type` | `source_type=SCAN`, `source_ref_id=None` |
| | `test_create_remediation_links_artifact_refs` | All 3 ref kinds populated correctly |
| | `test_create_remediation_attaches_audit_event_ref` | `audit_event_refs` grows by exactly 1 |
| | `test_create_remediation_resolves_by_idx_when_id_empty` | End-to-end with `idx-1` |
| Idempotency | `test_create_remediation_is_idempotent` | Second call returns same workstream + task |
| | `test_find_existing_remediation_misses_other_finding` | Different finding from same scan does not dedupe |
| Tenant isolation | `test_create_remediation_tenant_isolation` | Tenant A's workstream does not short-circuit tenant B |
| Error paths | `test_create_remediation_unknown_finding_raises` | Unknown finding -> `FindingNotFoundError` |
| | `test_create_remediation_no_active_dept_raises` | Tenant with zero depts -> `NoActiveDepartmentError` |
| | `test_create_remediation_invalid_dept_id_raises` | Cross-tenant dept_id is rejected (no silent fallback) |
| Serialization | `test_serialize_result_shape` | Frontend contract pinned |
| | `test_serialize_result_handles_null_task_id` | Legacy data path safe |

### 7.2 Regression sweep (all green)

| File | Tests | Result |
|---|---|---|
| `test_workstream_spine_skeleton.py` (PR-5) | 18 | 18/18 pass |
| `test_workstream_service.py` | 11 | 11/11 pass |
| `test_settings_governance_guard.py` (PR-GOV-01) | 17 | 17/17 pass |
| `test_execution.py` | 6 | 6/6 pass |
| `test_execution_run_task.py` | 5 | 5/5 pass |
| **Combined regression** | **57** | **57/57 pass** |

Combined with the new 18 PR-SCAN-WS-01 tests, **75 tests pass across the related surface**.

### 7.3 Frontend

- `npx tsc --noEmit` clean (0 errors).
- Playwright not run - the brief said "frontend test if existing scan component tests exist" and there is no existing Playwright spec for ScanReport.tsx today. Adding one would expand the surface beyond skeleton.

### 7.4 Endpoint-level tests

I deliberately did NOT write a TestClient-level test for `POST /security/scans/{scan_id}/findings/{finding_id}/create-remediation`. The endpoint is a thin wrapper:

1. Lookup `_get_workflow()._jobs[scan_id]` + tenant check (4 lines).
2. Call `workflow.get_scan_report(scan_id)` (3 lines).
3. Hand off to the service function (which has 18 unit tests).

A TestClient test would need to monkey-patch the singleton ScanWorkflow with a fake job + report, which is ceremony for low marginal coverage. The 4 lines of glue are visually inspected; if scale or change risk grows, an endpoint integration test can be added in a follow-up.

---

## 8. Files changed

### 8.1 Backend (new)

- `backend/app/services/security/scan_remediation.py` - 5 public functions + 1 dataclass + 4 exception types.
- `backend/tests/test_scan_remediation.py` - 18 contract tests.

### 8.2 Backend (modified)

- `backend/app/api/v1/security_dashboard.py` - added `CreateRemediationRequest` schema + `create_remediation_from_finding` endpoint + 4 imports (AsyncSession, get_db, scan_remediation symbols).

### 8.3 Frontend (modified)

- `frontend/src/pages/scan/ScanReport.tsx` - added `CreateRemediationButton` component + per-finding render hook + 5 icon imports + state-machine UI for idle / loading / success / error / disabled.

### 8.4 Docs (new)

- `docs/Ultraview/PR_SCAN_WS_01_FINDINGS_TO_REMEDIATION_REPORT.md` (this file).

### 8.5 Files NOT touched (per hard rules)

- `backend/app/services/security/cognitive_scan_engine.py`
- `backend/app/services/security/scan_workflow.py`
- `backend/app/services/security/zero_fp_gate.py`
- `backend/app/services/security/asset_shield/*`
- `backend/app/services/security/evilbob_mode.py`
- `backend/app/services/security/red_team_ops.py` (T5)
- `backend/app/services/security/exploitation_queue.py` (T5)
- `backend/app/services/security/zero_day_engine.py` (T5)
- `backend/app/services/security/osint_engine.py` (T5)
- `backend/app/services/security/laevateinn/*` (T3+ scan reasoning)
- `backend/app/services/chat_orchestrator.py`
- `backend/app/services/company_mode*.py`
- `backend/app/services/departments/*`
- `backend/app/services/skill_refinery/*`
- `frontend/src/pages/ChatPage.tsx`
- `frontend/src/pages/SkillsPage.tsx`
- `frontend/src/pages/scan/ScanLauncher.tsx`, `ScanList.tsx`, `ScanArtifacts.tsx`, `ScopeStatusBanner.tsx`, `tiers.tsx`
- All vault / OAuth / V2 connection paths

---

## 9. Remaining scan-to-fix debt

### 9.1 Items deferred to future PRs

| Debt | Severity | Future PR |
|---|---|---|
| Some scanner paths leave `SecurityFinding.id` empty; today the frontend uses `idx-N` positional fallback which is stable per-report but breaks if findings re-order between report regenerations | MED | PR-SCAN-FINDING-IDS - have `_aggregate_findings` mint deterministic ids (e.g. SHA256 of `tool:rule:location:title`) |
| Restart-recovered scans (in `var/security_reports/{job_id}.json`) are NOT resolvable for remediation creation today because the disk format does not carry `tenant_id` | MED | PR-SCAN-DISK-TENANT - extend `_persist_report` to write tenant_id; reader fall-back path verifies tenant before returning |
| `find_existing_remediation` does a per-tenant linear scan (O(N) per call) | LOW | PR-SCAN-WS-INDEX - add `(tenant_id, scan_id, finding_id)` composite column + unique index when N exceeds ~500 per tenant |
| Frontend deep-link `/workstreams?focus=<id>` is honest-but-graceful: the WorkstreamsPage renders the focused workstream in the list but does not auto-open the drawer | LOW | PR-SPINE-06 - add `?focus` query-param handling in WorkstreamsPage to auto-open drawer |
| Bulk action: "Create remediation tasks for all CRITICAL findings in this scan" not exposed today | LOW | PR-SCAN-BULK-REMEDIATE - bulk endpoint + frontend multi-select UI |
| Audit hash chain verify endpoint not yet wired (the audit row IS hash-chained per Hard Law 9; but no `/governance/audit/verify` UI surface) | LOW | PR-AUDIT-VERIFY (per Execution Spine PRD §14) |
| Status sync from Task (PENDING -> RUNNING -> COMPLETE) does NOT update the linked Workstream's status today | MED | PR-SPINE-04 (SSE event taxonomy) - emit `spine.task_status_changed` event from ExecutionService.update_task_status that flips the Workstream state via `transition()` |
| Remediation creation does NOT call governance pre-check; it bypasses GovernanceEngine because creating tracking work is itself low-risk | LOW | Document as acceptable; if a tenant requires governance even on remediation tracking, add a `governance_check=true` query-param later |

### 9.2 What this PR explicitly does NOT promise

- **No auto-fix.** The button creates trackable work, not code. Daena does not patch the source.
- **No scan re-trigger.** The endpoint reads existing scan results; it never starts a new scan (hard rule 6).
- **No T5 / EvilBob workflow reachability.** EVILBOB-tier findings (where `exploit_path` is populated) can have remediation created the same as any other finding; the `exploit_path` text is intentionally NOT included in the Task description (operator viewing the scan report still sees it; the Task surface is for fix work, not offensive walkthroughs).
- **No external-send.** Audit log is local; no email / DM / webhook.

---

## 10. Honesty notes

- The endpoint requires the scan to be in `workflow._jobs` (in-memory) at call time. Scans that the process-restart wiped from memory but persisted to disk are NOT addressable today. This is documented under §7 (PR-SCAN-DISK-TENANT) and is a deliberate scope cut to keep the skeleton small.
- The `idx-N` positional fallback works perfectly for the current session but is fragile across report regenerations. Until `PR-SCAN-FINDING-IDS` lands, an operator who reruns the same scan and clicks "Create remediation" twice using positional ids may get TWO workstreams (one per report instance). The stable-id path is unaffected.
- The audit_event id captured by `AuditService.log_decision` lands in `audit_event_refs` only on success; if AuditService throws, the warning is logged and the workstream is still created (audit is the observability layer, the workstream is the contract). Pinned by the `try/except` in `create_remediation` and tested in `test_create_remediation_attaches_audit_event_ref` (positive path) - the negative path is documented but not asserted because forcing AuditService failure requires invasive mocking and the failure path is small.
- The button color is `bg-primary-500/15` (the same teal Daena uses for primary actions), not `accent-amber` or `status-warning`. This is deliberate: creating a remediation Task is a standard product action, not an emergency. The amber/warning palette is reserved for blocked / failed states.

---

## 11. Commit message

```
canonicalization: create remediation workstreams from scan findings

PR-SCAN-WS-01: close the PR-4 actionability hole. Each finding row in
ScanReport now exposes a "Create remediation task" button that spawns
a Task (existing autopilot queue) plus a Workstream shell with
source_type=SCAN linked back to the originating scan via PR-5
artifact_refs. Idempotent on (scan_id, finding_id). No auto-fix
claim. No T5 / scan-pipeline / chat orchestrator changes.

Backend
- New endpoint: POST /security/scans/{scan_id}/findings/{finding_id}/
  create-remediation (404 on missing scan/finding, 400 on incomplete
  scan, 422 on missing department, 200 on success/idempotent)
- New module: services/security/scan_remediation.py
  - resolve_finding (stable id + idx-N positional fallback)
  - find_existing_remediation (tenant-scoped artifact_refs lookup)
  - resolve_department (explicit + first-active fallback)
  - build_task_description (severity + location + remediation +
    fix_code carried into the Task body)
  - create_remediation (orchestrates Task + Workstream + audit)
  - serialize_result (frontend contract)

Frontend
- ScanReport.tsx: per-finding CreateRemediationButton component with
  idle/loading/success/idempotent/error/disabled states. Wording
  locked to "Create remediation task" (never "auto-fix"). Deep links
  to /workstreams + /tasks on success. tsc clean.

Tests
- 18 new contract tests in test_scan_remediation.py (all green)
- 0 regressions across test_workstream_spine_skeleton.py (18/18),
  test_workstream_service.py (11/11),
  test_settings_governance_guard.py (17/17),
  test_execution.py (6/6), test_execution_run_task.py (5/5)
- 57 regression tests pass alongside the 18 new tests = 75 total

Honors all 10 founder hard rules. Frontend tsc clean.

Report: docs/Ultraview/PR_SCAN_WS_01_FINDINGS_TO_REMEDIATION_REPORT.md
```

End of report.
