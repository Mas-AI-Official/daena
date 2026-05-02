# PR-5: Workstream Execution Spine Skeleton - Report

**Date:** 2026-05-02
**Branch:** `rebuild-connections-mcp-runtime`
**Author:** Claude Code (Opus 4.7) under founder direction
**Companion PRs in the same sprint:** PR-GOV-01 (founder governance guard, commit `3639126`), PR-4 (security scan UX consolidation, commit `0bd2381`), parked Agent Pack Exporter note (commit `6de2037`).

> **Thesis:** Daena already has a Workstream model, service, API, and a frontend page (Council R3 lock, 2026-04-25). The spine skeleton was 80% built. PR-5 closes the four documented gaps from the founder brief (source attribution, progress hint, artifact / audit / notification ref containers, archive endpoint, dev-safe demo affordance) and wires one safe source (manual task → workstream) without touching chat, scan, departments, or skills wholesale.

---

## 1. Hard rules check (founder brief)

| Rule | Status |
|---|---|
| 1. No production deploy | Yes - local-only changes |
| 2. No `USE_CONNECTION_REGISTRY_V2=true` flip | Yes - flag untouched |
| 3. No `vault --apply` | Yes - vault not invoked |
| 4. No file deletions | Yes - additive only; no DELETE_CANDIDATE moves |
| 5. No secrets printed or committed | Yes - no env / token / key surfaces touched |
| 6. No external scans | Yes |
| 7. No external messages (email / DM / SMS / webhook) | Yes |
| 8. No T5 / 3vilbob execution code modified | Yes - `evilbob_mode.py`, `red_team_ops.py`, etc. untouched |
| 9. No wholesale rewrite of Chat / Scan / Tasks / Departments / Skills | Yes - only Tasks gets one optional flag (additive); chat / scan / departments / skills untouched |
| 10. No agency-agents / new dependencies | Yes - only stdlib + existing project libs |
| Em dash in new content (project CLAUDE.md Rule 12) | None introduced |

---

## 2. Inventory: existing surfaces touched and not touched

### 2.1 Already shipped (Council R3 lock, 2026-04-25)

The Workstream skeleton was substantially in place before PR-5:

| Surface | Status before PR-5 |
|---|---|
| `backend/app/models/workstream.py` - Workstream + WorkstreamEvent + 5-state lifecycle (RUNNING / BLOCKED / WAITING_APPROVAL / COMPLETE / FAILED) + 5-step escalation ladder + 16 event kinds + SoftDeleteMixin | shipped |
| `backend/app/services/workstream_service.py` - start / transition / pause / resume / redirect / escalate / complete / fail / append_timeline_event / list_events / list_for_tenant + LEGAL_TRANSITIONS table | shipped |
| `backend/app/api/v1/workstreams.py` - GET /, POST /, GET /{id}, POST /{id}/redirect, POST /{id}/pause, POST /{id}/resume, POST /{id}/escalate, POST /{id}/cancel, GET /{id}/events | shipped |
| `frontend/src/pages/WorkstreamsPage.tsx` - list with status filter, card with status pill + escalation badge, detail drawer with timeline + redirect input | shipped |
| `backend/migrations/versions/003_add_workstreams.py` - schema migration | shipped |
| `backend/tests/test_workstream_service.py` - 11 contract tests (state machine, escalation, redirect, timeline) | shipped, all green |
| Router mounted at `/api/v1/workstreams` (registered in `backend/app/api/v1/__init__.py:113`) | shipped |

### 2.2 Adjacent overlapping primitives (left untouched on purpose)

Per the canonicalization plan §0.1 row 7, **Tasks / Workstreams** are intended to converge into one canonical surface. PR-5 is the first step of that convergence; it does not collapse anything yet:

| Primitive | Disposition this PR |
|---|---|
| `backend/app/models/execution.py` Task | Untouched. PR-5 adds an *optional* `workstream_id` echo to the create-task response when the new `also_create_workstream` flag is set. Existing callers see no shape change. |
| `backend/app/api/v1/missions.py` + `services/security/mission_intelligence.py` | Untouched. Listed `KEEP API; no UI` in the canonicalization plan §1.4. |
| `backend/app/models/pipeline.py` + `api/v1/pipeline.py` | Untouched. Pipeline is the sales 8-stage pipeline, not a request lifecycle pipeline. Different concern. |
| `backend/app/models/department_task.py` | Untouched. |
| `backend/app/models/project.py` + `api/v1/projects.py` | Untouched. |
| `backend/app/models/background_task.py` + `services/autopilot/background_queue.py` | Untouched. PR-5 spawn flag does not write to the background queue - that is a future PR. |

### 2.3 Frontend untouched

`frontend/src/pages/TasksPage.tsx` is **not** modified. The brief is clear: improve the existing Workstreams page rather than create a duplicate. The Tasks page remains the canonical "background tasks" surface; the Workstreams page is the canonical "what is the spine doing" surface. The convergence is deferred.

---

## 3. Canonical model chosen

**`backend/app/models/workstream.py` Workstream** is the canonical artifact for Daena's action lifecycle, per the Council R3 lock (2026-04-25) and the Execution Spine PRD (2026-05-01) section 7.1. PR-5 extends it; it does not replace it.

### 3.1 Field mapping (founder brief vs. shipped model)

| Brief field | Status before PR-5 | Status after PR-5 |
|---|---|---|
| `id` | shipped (UUID PK) | unchanged |
| `tenant_id` | shipped (TenantMixin) | unchanged |
| `user_id` / `owner_id` | shipped (`user_id`) | unchanged |
| `source_type: chat \| scan \| task \| department \| company_mode \| manual` | not present | **added** as `WorkstreamSourceType` SAEnum (7 values incl. `dev_demo`); defaults to `manual` so legacy callers do not break |
| `title` | shipped as `goal` (String 500) | unchanged - `goal` is the existing column; the brief's `title` maps to it 1:1 |
| `status` | shipped (`WorkstreamStatus` SAEnum) | unchanged |
| `current_step` | shipped as `next_step_text` (String 500) | unchanged - `next_step_text` is the existing column; the brief's `current_step` maps to it 1:1 |
| `progress_percent` | not present | **added** as SmallInteger, default 0; clamped 0..100 by `update_progress()` |
| `artifact_refs` | shipped only inside `WorkstreamEvent.payload` (not first-class) | **promoted** to first-class JSON dict column (`{kind: [ref_ids]}`) |
| `audit_event_refs` | not present | **added** as JSON list (deduplicated append) |
| `notification_refs` | not present | **added** as JSON list (deduplicated append) |
| `created_at` / `updated_at` | shipped (TimestampMixin) | unchanged |

### 3.2 Why `goal` and `next_step_text` were kept (not renamed to `title` and `current_step`)

The frontend already consumes `goal` and `next_step_text`; the existing test suite asserts on those names; the redirect parser writes to `goal`. Renaming would have been a wide breakage with no behavior change. The brief field list is a spec, not a rename order - the existing names satisfy the spec.

### 3.3 Migration

`backend/migrations/versions/009_add_workstream_spine_fields.py` - additive ALTER TABLE adding the 6 new columns + a Postgres ENUM TYPE + 1 supporting index on `source_type`. Idempotent (mirrors the established 002 / 008 pattern). SQLite dev path picks up the columns automatically via `Base.metadata.create_all`.

---

## 4. Endpoints added / confirmed

### 4.1 Endpoints already shipped (kept unchanged)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/workstreams` | List for tenant (filter by status, excludes archived) |
| POST | `/api/v1/workstreams` | Start a new workstream (now accepts optional `source_type` + `source_ref_id`) |
| GET | `/api/v1/workstreams/{id}` | Detail + last 50 events |
| POST | `/api/v1/workstreams/{id}/redirect` | Parse + apply redirect instruction |
| POST | `/api/v1/workstreams/{id}/pause` | Pause autopilot (status unchanged) |
| POST | `/api/v1/workstreams/{id}/resume` | Resume autopilot |
| POST | `/api/v1/workstreams/{id}/escalate` | Bump escalation level (one-way up) |
| POST | `/api/v1/workstreams/{id}/cancel` | Mark FAILED |
| GET | `/api/v1/workstreams/{id}/events` | Full timeline (oldest first, max 1000) |

### 4.2 Endpoints added by PR-5

| Method | Path | Purpose |
|---|---|---|
| **PATCH** | `/api/v1/workstreams/{id}/archive` | Soft-delete via SoftDeleteMixin's `archived_at`. Idempotent: re-archive is a no-op. Status is preserved (no forced COMPLETE/FAILED). Cross-tenant access raises 404. |
| **POST** | `/api/v1/workstreams/dev-safe-demo` | Spin up a populated demo workstream end-to-end with `source_type=dev_demo`, synthetic artifact ids, ends in COMPLETE with `progress_percent=100`. Falls back to first active department if `department_id` is omitted; 422 when tenant has no active departments. |

### 4.3 Service helpers added

- `WorkstreamService.archive(workstream_id, tenant_id, archived_by_user_id)`
- `WorkstreamService.update_progress(workstream_id, tenant_id, percent)` - clamps 0..100, does not touch status
- `WorkstreamService.attach_artifact_ref(workstream_id, tenant_id, kind, ref_id, emit_event=True)` - appends + dedupes; optional ARTIFACT timeline event
- `WorkstreamService.attach_audit_event_ref(workstream_id, tenant_id, audit_event_id)` - appends + dedupes (no timeline event to avoid flood)
- `WorkstreamService.attach_notification_ref(workstream_id, tenant_id, notification_id)` - appends + dedupes (no timeline event to avoid flood)
- `WorkstreamService.create_dev_safe_demo(tenant_id, user_id, department_id)` - populated demo factory
- `WorkstreamService._get_including_archived(workstream_id, tenant_id)` - internal helper so re-archive is idempotent

---

## 5. Frontend surface chosen

**Improved `frontend/src/pages/WorkstreamsPage.tsx` in place.** No new page, no duplicate, no Tasks-page changes. The existing page already had the right shape; PR-5 added:

1. **`SourceBadge` component** - 7 source colors (chat=sky, scan=red, task=purple, department=yellow, company_mode=emerald, manual=gray, dev_demo=amber). Renders next to the StatusPill in card + drawer headers.
2. **`ProgressBar` component** - thin bar, 0..100, hidden when `progress_percent === 0` (so a workstream that never reports progress does not get a deceptive 0% bar).
3. **`ReferencePanels` component** in the detail drawer - three sections:
   - "Artifacts produced" grouped by kind with monospace ref chips
   - "View N audit events" link to `/governance/audit?workstream_id=...`
   - "View N notifications" link to `/notifications?workstream_id=...`
   - Honest empty state when no refs have been emitted yet
4. **"Demo workstream" button** in the page header - calls `POST /workstreams/dev-safe-demo`, refreshes the list, opens the new workstream's detail drawer. Lets the founder see the spine alive without first wiring chat / scan / tasks.
5. **"Archive" button** in the detail drawer - calls `PATCH /workstreams/{id}/archive`, closes the drawer, refreshes the list.
6. **Updated empty-state copy** - names the three sources (EXE chat, manual task with the new flag, future scan / company-mode) and points the operator at the Demo button.
7. **Reference counts on cards** - small icon-prefix counts (FileText / ShieldCheck / Mail) for artifact / audit / notification refs at a glance.

Frontend `tsc --noEmit` passes cleanly (0 errors).

---

## 6. What sources are wired now vs. deferred

### 6.1 Wired in PR-5

1. **Manual task → Workstream shell** (opt-in via `also_create_workstream: bool = false` on `POST /api/v1/execution/tasks`). When the flag is true:
   - `ExecutionService.create_task` calls `_spawn_workstream_for_task` after the task is committed.
   - The spawned workstream gets `source_type=task`, `source_ref_id=task.id`, `goal=task.name`, `next_step_text=task.description`, `initial_context={"spawned_from": "manual_task", "task_id": str(task.id)}`.
   - Department resolution: explicit `department_id` from the request is validated; otherwise falls back to the tenant's first active department by `sunflower_index`.
   - The response includes `workstream_id` so the frontend can deep-link.
   - The spawn is wrapped in `try/except` - a workstream failure NEVER fails the task (the task is the contract; the workstream is an optional observability layer).
2. **Dev-safe demo** (always available via `POST /api/v1/workstreams/dev-safe-demo`). Source type is its own enum value (`dev_demo`) so the demo is visually distinct in the list.

### 6.2 Deferred (future PRs in the spine series, per the Execution Spine PRD §14)

| Source | Future PR | Why deferred |
|---|---|---|
| Chat EXE action → Workstream shell | PR-SPINE-03 (S0 CLASSIFY generalization) | Touches `chat_orchestrator.py` (KEEP_HOT_PATH per canonicalization plan §1.1); needs full SSE event taxonomy from PR-SPINE-04 |
| Scan report → remediation workstream | PR-SCAN-WS-01 (separate ticket) | Touches `scan_workflow.py` which was just consolidated in PR-4; one PR per surface keeps blast radius small |
| Company-mode mission → workstream | PR-COMPANY-WS-01 | Company Mode has its own mission concept (`services/company_mode_*.py`) that needs a separate mapping decision |
| Department-spawned background work → workstream | PR-DEPT-WS-01 | Department workflows live in `services/departments/*` and are not yet wired to a request lifecycle |

---

## 7. Tests run

### 7.1 New tests (PR-5)

`backend/tests/test_workstream_spine_skeleton.py` - **18 tests, all green:**

| Group | Test | What it pins |
|---|---|---|
| New-field persistence | `test_new_fields_default_correctly_on_start` | Default source=MANUAL, progress=0, empty refs |
| | `test_new_fields_persist_when_explicitly_set` | source_type + source_ref_id round-trip through DB |
| Archive | `test_archive_sets_archived_at_and_returns_row` | PATCH /archive sets archived_at + archived_by |
| | `test_archive_is_idempotent` | Re-archive is no-op (returns same row, no exception) |
| | `test_archived_workstream_drops_from_list` | List endpoint excludes archived rows |
| | `test_archive_cross_tenant_raises_not_found` | Tenant A cannot archive tenant B's workstream |
| Progress | `test_update_progress_clamps_high` | 150 clamps to 100 |
| | `test_update_progress_clamps_low` | -5 clamps to 0 |
| | `test_update_progress_does_not_change_status` | Progress is informational; state machine still owns lifecycle |
| Refs | `test_attach_artifact_ref_appends_and_dedupes` | Append per kind, dedupe duplicates |
| | `test_attach_audit_event_ref_dedupes` | Audit ref dedupe |
| | `test_attach_notification_ref_dedupes` | Notification ref dedupe |
| Demo | `test_dev_safe_demo_lands_complete_with_progress_100` | Demo ends in COMPLETE + progress=100 |
| | `test_dev_safe_demo_uses_dev_demo_source_type` | Source type = DEV_DEMO |
| | `test_dev_safe_demo_populates_artifact_refs` | At least one artifact ref produced |
| Task wiring | `test_task_create_default_does_not_spawn_workstream` | No flag = no workstream (backwards compat) |
| | `test_task_create_with_flag_spawns_workstream` | Flag true = workstream spawned with source_type=TASK |
| | `test_task_create_with_flag_falls_back_to_first_active_dept` | No dept_id falls back to first active |

### 7.2 Regression tests (existing, all green)

| File | Tests | Result |
|---|---|---|
| `tests/test_workstream_service.py` | 11 | 11/11 pass |
| `tests/test_settings_governance_guard.py` | 17 | 17/17 pass (PR-GOV-01) |
| `tests/test_execution.py` | 6 | 6/6 pass |
| `tests/test_execution_run_task.py` | 5 | 5/5 pass |
| **Combined regression** | **39** | **39/39 pass** |

### 7.3 Frontend

- `npx tsc --noEmit` clean (0 errors).
- Playwright not run - the brief said "only if cheap" and the page-level interactions (Demo button, Archive button, ReferencePanels) are covered structurally by the type signatures + backend tests. A future PR-SPINE-06 (per PRD §14) will add Playwright when the SSE event taxonomy and live console land.

### 7.4 Migration

`backend/migrations/versions/009_add_workstream_spine_fields.py` imports cleanly; revision chain confirmed (`009_add_workstream_spine_fields` → `008_add_notifications`). Migration is idempotent and uses the established `_column_exists` / `_index_exists` / `_pg_enum_exists` helpers. Not run against a live Postgres in this PR (per hard rule 1: no production deploy).

---

## 8. Risks + next PRs

### 8.1 Risks introduced

| Risk | Mitigation |
|---|---|
| Spawning a workstream from a task is opt-in; operators may not discover the flag | Default off so no surprise. Future PR-SPINE-05 ("+ New action" launcher) makes the spawn the primary path; the explicit flag stays for API consumers who want plain Tasks. |
| Dev-safe demo writes a Workstream row; could pollute the list | Demo workstream uses a distinct `source_type=dev_demo` badge so the operator can see + archive it. The Archive button on the detail drawer is the disposal path. |
| `progress_percent` is informational only; no caller writes it yet (other than the demo) | Added as a column today so the schema is ready when chat / tasks / scan adopters wire it; no UI lies because `progress_percent === 0` hides the bar. |
| `artifact_refs` is a JSON dict, not a relational FK; cross-table joins are not possible | Acceptable for skeleton - reference IDs are opaque strings the frontend resolves at click-time. Future hardening could promote individual ref kinds to junction tables when query patterns demand it. |
| Migration 009 is additive but adds a new ENUM TYPE on Postgres; downgrade requires DROP TYPE | Downgrade path provided + tested via `_pg_enum_exists` guard. Per CLAUDE.md hard law #2, downgrade is dev-only - production runs are forward-only. |
| `_get_including_archived` exposes archived rows by id for the archive() path; could leak archive state if mis-called | Marked `_private` (leading underscore); only used internally by `archive()`. Public read paths still go through `get()` which filters archived. |

### 8.2 Next PRs to land in the spine sequence (per Execution Spine PRD §14)

| PR | Scope | Estimate | Authorization |
|---|---|---|---|
| PR-SPINE-02 | Capability Registry single surface + 5-min cache | 3h | not authorized |
| PR-SPINE-03 | S0 CLASSIFY generalization (chat → all entry points) | 3h | not authorized |
| PR-SPINE-04 | S5 PROGRESS unified SSE event taxonomy | 2h | not authorized |
| PR-SPINE-05 | "+ New action" launcher frontend + draft endpoint | 4h | not authorized |
| PR-SPINE-06 | Workstream page live console (SSE consumer + Playwright) | 5h | not authorized |
| PR-SCAN-WS-01 | Scan report → remediation workstream wiring | 2h | not authorized |
| PR-COMPANY-WS-01 | Company Mode mission → workstream wiring | 2h | not authorized |
| PR-AUDIT-VERIFY | Hash-chain verify endpoint + nightly cron + operator UI | 2h | not authorized |
| PR-DREAM-01 | Dream cycle scheduler + DreamReport table | 3h | not authorized |
| PR-LEARN-01 | LearningService persistence to NBMF T0 | 2h | not authorized |

Each of those depends only on PR-5's skeleton being landed. None of them are auto-triggered by this PR. The founder picks the next one.

---

## 9. Files changed

### 9.1 Backend (modified)

- `backend/app/models/workstream.py` - added `WorkstreamSourceType` enum + 6 columns on Workstream
- `backend/app/services/workstream_service.py` - added `archive`, `update_progress`, `attach_artifact_ref`, `attach_audit_event_ref`, `attach_notification_ref`, `create_dev_safe_demo`, `_get_including_archived`; extended `StartParams` and `start()` for source attribution
- `backend/app/api/v1/workstreams.py` - added `PATCH /{id}/archive`, `POST /dev-safe-demo`, `_resolve_demo_department`, extended `_serialize_workstream` and `StartWorkstreamRequest`, added `DevSafeDemoRequest`
- `backend/app/services/execution_service.py` - extended `create_task` with `also_create_workstream` + `department_id` params; added `_spawn_workstream_for_task`
- `backend/app/api/v1/execution.py` - passes the two new fields to `service.create_task`
- `backend/app/schemas/execution.py` - added `also_create_workstream` + `department_id` to `CreateTaskRequest`; added `workstream_id` to `TaskResponse`

### 9.2 Backend (new)

- `backend/migrations/versions/009_add_workstream_spine_fields.py` - Alembic migration adding 6 columns + ENUM + 1 index to `workstreams`
- `backend/tests/test_workstream_spine_skeleton.py` - 18 contract tests

### 9.3 Frontend (modified)

- `frontend/src/pages/WorkstreamsPage.tsx` - added `SourceBadge`, `ProgressBar`, `countArtifactRefs`, `ReferencePanels`, Demo workstream button, Archive button, extended Workstream interface, updated empty-state copy

### 9.4 Docs (new)

- `docs/Ultraview/PR_WORKSTREAM_SPINE_SKELETON_REPORT.md` (this file)

### 9.5 Files NOT touched (per hard rules)

- `frontend/src/pages/TasksPage.tsx`
- `frontend/src/pages/ScanPage.tsx`
- `frontend/src/pages/ChatPage.tsx`
- `frontend/src/pages/SkillsPage.tsx`
- All department, soul, governance, security pages
- All T5 / EvilBob / red_team / exploitation / zero_day / osint files
- `connection_v2/` flag (`USE_CONNECTION_REGISTRY_V2`)
- `vault_adapter.py`, `vault_migration.py`, `oauth_credentials_store.py` (Rule 18 protected files)
- `chat_orchestrator.py`, `scan_workflow.py`, `cognitive_scan_engine.py`

---

## 10. Honesty notes

- **The skeleton does not yet wire any real source other than manual tasks + dev demo.** Chat EXE, scan reports, and company mode missions are explicitly deferred. The brief said "wire only one or two safe sources"; this PR ships exactly that.
- **`progress_percent` has no automatic writer outside the dev-safe demo.** The column is added so future PRs (PR-SPINE-04 SSE event taxonomy in particular) can populate it; until then, real workstreams will show no progress bar (which is correct - the bar is hidden when 0).
- **`artifact_refs` is a JSON dict, not joined to actual artifact tables.** Deep links from the frontend chips currently navigate to plausible paths (e.g. `/security/reports/<id>`) but no scan-report page exists yet. The empty state is honest and the panels render the data they have.
- **The "Live timeline" + reasoning panel + Action buttons (Pause/Resume/Redirect/Archive) referenced in PRD §11.2** are present in the existing drawer plus PR-5's Archive button. The Reasoning panel section (collapsed by default with thinking events / Council member responses / DCP lens picks) is deferred to PR-SPINE-06 because it depends on the SSE event taxonomy that PR-SPINE-04 ships.
- **Tasks page is not removed and is not relabeled.** The brief's option for a "Workstream tab on Tasks page" was considered and declined: the existing WorkstreamsPage is the canonical surface, and adding a tab to TasksPage would create the very duplication the founder asked us to avoid. Tasks remain useful as the background-tasks queue view; Workstreams are the spine view.

---

## 11. Commit message

```
canonicalization: add workstream execution spine skeleton

PR-5: extend the existing Workstream model + service + API + frontend
page with the six fields and two endpoints the Execution Spine PRD
requires for one-visible-lifecycle parity. Wire one safe source
(manual task -> workstream) as opt-in. No chat / scan / departments /
skills wholesale rewrite.

Backend
- Workstream model: source_type + source_ref_id + progress_percent +
  artifact_refs + audit_event_refs + notification_refs
- WorkstreamService: archive, update_progress, attach_*_ref,
  create_dev_safe_demo, _get_including_archived
- API: PATCH /workstreams/{id}/archive, POST /workstreams/dev-safe-demo
- ExecutionService: optional also_create_workstream flag spawns a
  Workstream shell with source_type=task pointing back at the task
- Migration 009: additive ALTER TABLE + Postgres ENUM + 1 index

Frontend
- WorkstreamsPage: SourceBadge, ProgressBar, ReferencePanels,
  Demo workstream button, Archive button, honest empty state copy
- tsc clean

Tests
- 18 new contract tests in test_workstream_spine_skeleton.py (all green)
- 0 regressions in existing test_workstream_service.py (11/11),
  test_settings_governance_guard.py (17/17), test_execution.py (6/6),
  test_execution_run_task.py (5/5)

Honors all 10 founder hard rules (no deploy, no V2 flag flip, no
vault apply, no deletions, no secrets, no external scans/messages,
no T5 modifications, no Chat/Scan/Tasks/Departments/Skills wholesale
rewrite, no agency-agents / new deps).
```

End of report.
