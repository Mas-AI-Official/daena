# Daena OVERNIGHT — Button Wiring Matrix
Date: 2026-05-07
Author: OVERNIGHT scope (PR-6)
Scope: critical-path founder business loop CTAs + Diagnostics, with endpoint + verification status

## Methodology

Walked the founder's daily business loop end-to-end:
1. **Opportunities** (`/opportunity-inbox`) — discovery → archive/reject
2. **Workstreams** (`/workstreams`) — view → action → archive
3. **Approvals** (`/governance/approvals`) — approve/reject Phase-3 actions
4. **Tasks** (`/tasks`) — run → retry → cancel
5. **Connections** (`/connections`) — discover → test → install (audited V3 Phase 1)
6. **Settings** (`/settings/*`) — toggles persist (audited PR-8 tonight)

For each primary CTA: grep'd the page for the `onClick` handler, traced to the `api.METHOD(path)` call, then confirmed the matching `@router.METHOD(path)` exists in `backend/app/api/v1/*`.

Dead button criteria (HARD FAIL):
- `onClick={() => {}}` → empty handler
- `onClick={() => toast.info('… coming …')}` → fake feedback
- `disabled` with no enable path
- Calls a route that doesn't exist in backend

## Matrix — business loop critical path

### `/opportunity-inbox` (OpportunityInboxPage.tsx)

| CTA | Handler | API call | Backend route | Status |
|---|---|---|---|---|
| Run discovery now | `runDiscovery()` | `POST /api/v1/opportunities/run-discovery` | `opportunities.py:181` | **WIRED** |
| Archive | `actionRow(id, 'archive')` | `POST /api/v1/opportunities/{id}/archive` | `opportunities.py:226` | **WIRED** |
| Reject | `actionRow(id, 'reject')` | `POST /api/v1/opportunities/{id}/reject` | `opportunities.py:241` | **WIRED** |
| (rate-limit poll) | useEffect | `GET /api/v1/opportunities/send-rate-limit` | `opportunities.py:101` | **WIRED** |

### `/workstreams` (WorkstreamsPage.tsx)

| CTA | Handler | API call | Backend route | Status |
|---|---|---|---|---|
| Open detail | `loadWorkstream(id)` | `GET /workstreams/{id}` | `workstreams.py:520` | **WIRED** |
| Redirect | `handleRedirect()` | `POST /workstreams/{id}/redirect` | `workstreams.py:544` | **WIRED** |
| Pause | `handleAction('pause')` | `POST /workstreams/{id}/pause` | `workstreams.py:678` | **WIRED** |
| Resume | `handleAction('resume')` | `POST /workstreams/{id}/resume` | `workstreams.py:692` | **WIRED** |
| Escalate | `handleAction('escalate')` | `POST /workstreams/{id}/escalate` | `workstreams.py:706` | **WIRED** |
| Cancel | `handleAction('cancel')` | `POST /workstreams/{id}/cancel` | `workstreams.py:726` | **WIRED** |
| Archive | `handleArchive()` | `PATCH /workstreams/{id}/archive` | `workstreams.py:773` | **WIRED** |
| Demo workstream | `createDemo()` | `POST /workstreams/dev-safe-demo` | `workstreams.py:859` | **WIRED** |
| (live console feed) | EventSource | `GET /workstreams/{id}/stream` | `workstreams.py:893` | **WIRED** |

### `/governance/approvals` (GovernanceApprovalsPage.tsx)

| CTA | Handler | API call | Backend route | Status |
|---|---|---|---|---|
| Approve (Phase 3) | `handlePhase3Decide('APPROVE')` | `POST /governance/approvals/{id}/decide` | exists | **WIRED** |
| Reject (Phase 3) | `handlePhase3Decide('REJECT')` | `POST /governance/approvals/{id}/decide` | exists | **WIRED** |
| Approve (general) | `handleDecide(id, 'APPROVE')` | `POST /governance/approvals/{id}/decide` | exists | **WIRED** |
| Reject (general) | `handleDecide(id, 'REJECT')` | `POST /governance/approvals/{id}/decide` | exists | **WIRED** |

### `/tasks` (TasksPage.tsx)

| CTA | Handler | API call | Backend route | Status |
|---|---|---|---|---|
| Run | `handleRun(id)` | `POST /execution/tasks/{id}/run` | exists | **WIRED** |
| Retry | `handleRetry(id)` | `PATCH /execution/tasks/{id}` + `POST /execution/tasks/{id}/run` | exists | **WIRED** |
| Cancel | `handleCancel(id)` | `PATCH /execution/tasks/{id}` (status=CANCELLED) | exists | **WIRED** |
| Bulk archive | `handleBulkArchive()` | `PATCH /execution/tasks/{id}` for each | exists | **WIRED** |

### `/connections` (audited V3 Phase 1)

Already in `DAENA_CONNECTIONS_V3_PHASE1_SMOKE.md`. Single primary button per card; whole-card click opens drawer; "Discover installed tools" calls real discovery; "Test" runs real probe.

## Dead-button audit

Grep result for the three dead-button patterns across `frontend/src`:

| Pattern | Matches |
|---|---|
| `onClick={() => {}}` | 0 |
| `onClick={() => alert('coming...')}` | 0 |
| `onClick={() => toast.info('… coming …')}` | 1 (SettingsDeveloper Webhook Save — now behind PR-8 roadmap expander) |
| `disabled className opacity-60 pointer-events-none` (faux-disabled forms) | 1 (SettingsDeveloper Webhook URL form — also behind PR-8 expander) |

**Net dead surface in normal-mode UI: 0 after PR-8.** The two SettingsDeveloper findings are roadmap items behind an expander explicitly labelled "Roadmap (not active yet)".

## Out of scope (not in business loop)

These pages were NOT walked tonight (lower priority):
- `/security/*` (audit shows api wiring exists; not in critical loop)
- `/projects/*` (CRUD wiring; lower priority)
- `/dashboard` (read-only aggregation; lower priority)
- `/skills/*` (skill catalog viewer; lower priority)
- `/department/*` (chat-with-agent; uses chat orchestrator which is well-tested)
- `/files/*` (file browser; not in critical loop)

These should be walked in a future audit pass. The grep-based dead-button scan above did NOT find any dead patterns in these pages either, so the failure surface is bounded.

## Conclusion

**The founder's business loop is fully wired.** Every primary CTA on the critical path goes to a real backend endpoint that exists in `backend/app/api/v1/`. There are zero dead buttons in the normal UI after PR-8. The only "Coming soon" surfaces left are roadmap items behind an explicit "Roadmap (not active yet)" expander, which is honest.

PR-7 (wire missing endpoints) is therefore **not needed tonight** — the matrix shows nothing to wire.

## Caveats

- This matrix verified `route exists in source`. It did NOT verify `route returns the expected response shape` or `route succeeds end-to-end with auth + tenant scoping`. That's NUser browser-crawl scope (PR-10).
- Bulk operations (e.g., "Archive 5 tasks at once") were not load-tested.
- Race conditions between optimistic UI and server response were not stress-tested.
- The matrix did not exercise the `/connections` Discover/Test path (operator-action; pending Ctrl+Shift+R).
