# Codex 5.5 Executive Summary

Date: 2026-04-29

## Root Selected

Canonical root: `D:\Ideas\Daena`

Legacy root: `D:\Ideas\Daena_old_upgrade_20251213` is not present on disk and was not touched.

## What Was Audited

- Latest `docs\daena-Claude` audit material.
- Latest `docs\Codex-Pitch` investor material.
- Backend routes and services for runtimes, MCP, cron, background queue, approvals, audit, tasks, sales, and launch.
- Frontend pages for connections, departments, tasks, heartbeat, approvals, audit, and pipeline.
- Local launch prerequisites and health probes.

## What Was Broken Or Fake

- Cloud MCP catalog entries were shown as enabled/pre-installed and could be toggled without backend persistence.
- Departments page fabricated fallback department cards when backend data was absent.
- Approval and audit pages could fail into empty-looking states.
- Background queue persistence was not visible from the Tasks page.
- Cron runtime dispatch was real in backend code, but not visible enough in the UI.
- Sales/customer workflow was not available as one founder-safe draft/approval flow.

## What Was Fixed

- Cloud MCP catalog is now read-only and labeled as not installed until a tenant MCP server exists.
- Departments page now shows live backend data only, or an honest empty/error state.
- Approval queue and audit log display load failures explicitly.
- Tasks page shows DB-backed vs memory-only queue state through a new backend status route.
- Heartbeat settings show cron job runtime dispatch status and last result.
- Added draft-only customer acquisition workflow route and frontend panel.
- Sales workflow now creates lead/contact data, qualifies it, drafts outreach, creates a follow-up task, creates an approval request, and logs an audit event without sending anything externally.

## What Is Still Broken Or Partial

- Local runtime environment is broken: Python asyncio fails on `_overlapped` WinError 10106, Node/npm fails CSPRNG initialization, and launch cannot complete here.
- Full pytest, frontend typecheck/build, OpenAPI generation, and browser smoke are pending.
- Investor/grant modules remain mostly documentation, not complete product workflows.
- RAG/Obsidian status still needs a first-class verified product panel.

## What Is Now Real

- MCP persistence is DB-backed by code path.
- Cron execution path dispatches runtime adapters and persists run records.
- Background queue persistence is observable.
- API failures surface visibly.
- Customer acquisition is governed and draft-only by design.

## How To Launch Daena

```powershell
D:\Ideas\Daena\start-daena.bat
```

Direct fallback:

```powershell
cd D:\Ideas\Daena\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

cd D:\Ideas\Daena\frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

## How To Test Daena

After fixing the local Python/Node environment:

```powershell
cd D:\Ideas\Daena\backend
.\.venv\Scripts\python.exe -m pytest backend\tests\test_agent_ops.py tests\test_connections.py tests\test_heartbeat.py tests\services\test_mcp_registry_persistence.py -q
.\.venv\Scripts\python.exe -m pytest tests -q

cd D:\Ideas\Daena\frontend
npm run typecheck --if-present
npm run build
```

## What The Founder Should Demo

- Pipeline -> Customer acquisition workflow.
- Approval queue entry created from the outreach draft.
- Audit log entry proving no external send happened.
- Tasks page showing the follow-up task.
- Connections page showing honest MCP state and read-only cloud catalog.
- Runtime selector with real runtime detection.

## What Not To Demo Yet

- Actual email send, application submission, social posting, or third-party scans.
- Investor/grant workflow as a completed product module.
- RAG/Obsidian sync as verified if the status panel has not been smoke-tested.

## Next 7 Days

1. Fix local environment and run full validation.
2. Add E2E test for customer acquisition draft/approval path.
3. Add RAG/Obsidian status endpoints and UI.
4. Add investor/grant tracker route and draft-only application workflow.
5. Modularize Connections page around runtimes, MCP, connectors, and catalog.

## Next 30 Days

1. Productize Founder Command Center around daily VP report, approvals, tasks, and risks.
2. Add launch script self-tests and health assertions.
3. Add data-room/demo-day package generated from verified product state.
4. Harden auth, CORS, rate limits, and production deployment checks.
5. Add governed external-action execution after approval-chain testing.
