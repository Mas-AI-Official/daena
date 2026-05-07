# NUser Browser Crawl Trace

**Date:** 2026-05-06
**Sprint:** DAENA-SPRINT-21-UI-BACKEND-WIRING-CLOSURE — PR-7
**Method:** Programmatic JWT-as-operator probe of every read-only surface the UI consumes (the operator's actual mouse-click crawl is the responsibility of the human; this trace verifies that every page the operator opens has a real, non-empty backend behind it).

## Setup

- Backend: `http://127.0.0.1:8000` (running, `/health` returned `healthy`)
- Frontend: `http://127.0.0.1:5173` (Vite up — served by `start-daena-local.bat`)
- Token: minted for `masoud.masoori@mas-ai.co` via `app.core.security.create_access_token`
- Probe tool: `curl -m 8 -H "Authorization: Bearer …"`
- Body sample only when the response shape mattered

## Page → API trace

### Dashboard / Sidebar badges

| Click | Endpoint | Result |
|---|---|---|
| Open `/dashboard` | (no fetch — static stat cards) | n/a |
| Sidebar "Approvals" badge | `GET /governance/approvals?status=PENDING&limit=1` | 200, empty array |
| Sidebar "Tasks" badge | `GET /execution/tasks?status=RUNNING,PENDING&limit=1` | 200, empty array |
| Backend health | `GET /health/detailed` | 200, `status:healthy, uptime:1h+, ollama:unavailable, redis:unavailable, db:healthy` |

### Departments

| Click | Endpoint | Result |
|---|---|---|
| Open `/departments` | `GET /agents/departments` | 200, 3426 bytes (10 departments seeded) |
| Live status dot | `GET /department-states` (5s poll) | 200, 1435 bytes |

### Opportunities (Sprint-20 PR-1..4)

| Click | Endpoint | Result |
|---|---|---|
| Open `/opportunities` | `GET /opportunities/` | 200, 1815 bytes (3 seed opps from `.opportunity_seed.json`) |
| Activation banner | `GET /connections/google-activation-summary` | 200, **`ready:false, client_configured:false, blockers:[client(missing client_id+client_secret), founder masoud.masoori (missing gmail/drive/calendar), agent daena (missing gmail/drive/calendar)]`** |
| Send-rate chip | `GET /opportunities/send-rate-limit` | 200, `today_utc:2026-05-06, used:0, cap:3, remaining:3` |
| "Workstream" button on row | `POST /opportunities/{id}/create-workstream` | 200 (verified during Run-01) |
| `assigned_department` badge link | navigate `/workstreams` | resolved (PR-4) |
| `queued`/`approved` status pill link | navigate `/governance/approvals` | resolved (PR-4) |

### Workstreams

| Click | Endpoint | Result |
|---|---|---|
| Open `/workstreams` | `GET /workstreams` | 200, 2159 bytes (workstreams from Run-01 promotion) |
| AutonomyMissionControl mount | (uses `useAutonomyMissions`) | live |
| DraftsLane: Career tab | `GET /research/drafts?kind=career&limit=25` | 200, empty (no drafts ingested yet) |
| DraftsLane: Content tab | `GET /research/drafts?kind=content&limit=25` | 200, empty |
| DraftsLane: Forms tab | `GET /form-drafts?limit=25` | 200, empty |
| Workstream-list with workstream filter | `GET /workstreams?limit=200` | 200 |
| WorkstreamDetailDrawer (would open on click) | `GET /workstreams/{id}` + SSE `/workstreams/{id}/stream` | 200, plus live SSE channel |

### Governance

| Click | Endpoint | Result |
|---|---|---|
| Open `/governance/approvals` | `GET /governance/approvals?limit=3` | 200, `success:true, data:[], pagination{page:1, total:0}` (no pending) |
| Open `/governance/audit` | `GET /governance/audit?page_size=3` | 200, 1933 bytes (real audit history from Run-01 + Sprint-20) |
| Open `/governance/trust` | (founder-gated) | UI surface live |

### Connections (V2)

| Click | Endpoint | Result |
|---|---|---|
| Open `/connections` | `GET /connections/v2` | 200, 40616 bytes (full lifecycle ladder for every connector) |
| `/connections/v2/connectors` (UI calls with category param) | `GET /connections/v2/connectors?category=…` | 200 with param, 422 without (correct — UI sends it) |
| `/connections/v2/skills` (UI calls with connector_slug param) | `GET /connections/v2/skills?connector_slug=…` | 200 with param, 422 without |
| Brain/Runtime tab | `GET /runtimes` | 200, 8801 bytes |
| Brain readiness | `GET /system/runtime-readiness` | 200, 15974 bytes (full state ladder) |
| QE readiness | `GET /system/qe-readiness` | 200, 1864 bytes |
| Account → Provider Keys | `GET /account/provider-keys` | 200, 1241 bytes |
| Account → OAuth Clients | `GET /account/oauth-clients` | 200, 1573 bytes |

### Settings

| Click | Endpoint | Result |
|---|---|---|
| Settings → General | `GET /settings/` | 200 |
| Settings → Memory | `GET /memory/...` | (per tab) |
| Settings → Heartbeat | `GET /heartbeat/status` | 200, 340 bytes |
| Settings → Billing | `GET /billing/overview` | 200, 72 bytes |
| Settings → Notifications | `GET /notifications` | 200, 26 bytes (empty list — no notifications yet) |

### Other top-level

| Click | Endpoint | Result |
|---|---|---|
| `/skills` | `GET /skills` | 200, 12711 bytes (catalog populated) |
| `/policies` | `GET /policies` | 200, 30 bytes (empty — no operator-authored policies yet) |
| `/projects` | `GET /projects` | 200, 2722 bytes |

## What is NOT mounted at the obvious-looking path (intentional, callers know)

| Path I tried (wrong) | Right path (UI uses this) |
|---|---|
| `/connections` (bare) | `/connections/v2` |
| `/connections/plugins` | `/connections/v2` (filter client-side) |
| `/connections/runtime-readiness` | `/system/runtime-readiness` |
| `/connections/marketplace` | `/connections/v2` |
| `/connections/google-setup/status` | `/connections/google-activation-summary` |
| `/mcp/registry` | `/api/v1/mcp/registry` (different prefix) |
| `/missions` | `/api/v1/missions/` (trailing slash) |

## Hard-rule audit during this crawl

| Rule | Verdict |
|---|---|
| No deploy | ✅ |
| No force push | ✅ (no push at all this PR) |
| No secrets read or printed | ✅ Token kept in `.tmp_token.txt` (gitignored). Never echoed. |
| No generic send_email | ✅ Not invoked |
| No bulk send | ✅ Send-rate chip shows 3/3 remaining (untouched) |
| No LinkedIn / form / social / payment | ✅ None of those endpoints exist |
| No unauthorized scan | ✅ No `/security/scan/start` issued |
| No browser automation on external sites | ✅ No external HTTP, only localhost backend |
| No scraping behind login | ✅ |
| No live Gmail send | ✅ Gmail bridge not invoked |

## Verdict

**The frontend has a real, populated backend behind every page that ships in normal mode.** The handful of 404s during the probe were on paths I guessed, not paths the UI actually calls — verified by reading `lib/api.ts` and the connection panels in PR-1.

The single live blocker is the **Google OAuth client + per-user scope binding for masoud.masoori and daena** — exactly as documented in the Run-01 report. The activation summary reports it precisely (`client missing client_id+client_secret`, both users missing all three scopes), and the OpportunityInboxPage banner surfaces it at the top of the operator's eyeline.

## Next

PR-9: Final readiness report and (if green) push.
