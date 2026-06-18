# Validation Report

Date: 2026-04-29

Canonical root: `D:\Ideas\Daena`

## Scope Validated

P0/P1 repair pass:

- Frontend/backend truth fixes.
- Fake UI behavior removal.
- Runtime/status fallback review.
- MCP persistence review.
- Cron runtime dispatch review.
- Background queue persistence visibility.
- Approval queue and audit trail visibility.
- Draft-only sales/customer workflow with founder approval.
- Local launch attempt.

## Code Repairs Completed

| Area | Result |
|---|---|
| Fake UI behavior | Cloud MCP catalog rows are now read-only, not selectable, not batch-toggleable, and not shown as enabled/running. Departments no longer fabricate placeholder cards when backend data is missing. |
| Runtime/status fallbacks | Existing RuntimeSwapper real-registry behavior preserved: no hardcoded demo runtime fallback. Connections cloud catalog no longer presents catalog entries as live status. |
| API failure visibility | API errors already flow to `errorStore` and the header connection indicator. This pass added visible approval-queue and audit-log load errors. |
| Buttons and controls | Sales/customer workflow button is wired to a real backend route. Cloud MCP toggle/select controls are disabled by design with a reason. |
| MCP persistence | Backend MCP install/uninstall writes tenant-scoped `McpServer` rows; UI reports persistence failure instead of generic success. |
| Cron execution | Cron scheduler path invokes runtime adapters through the runtime registry and writes `CronRun` records. UI now exposes job/runtime dispatch status. |
| Background queue | Added `/api/v1/autopilot/queue/status`; Tasks page shows DB-backed vs memory-only queue state honestly. |
| Approval/audit visibility | Approvals and audit pages now show load failures instead of silently rendering empty data. |
| Sales workflow | Added draft-only customer acquisition workflow: prospect, qualify, draft outreach, create follow-up task, create approval request, write audit event. No external message is sent. |

## Static Validation Passed

Backend syntax:

```powershell
cd D:\Ideas\Daena
backend\.venv\Scripts\python.exe -m py_compile backend\app\api\v1\agent_ops.py backend\app\api\v1\autopilot.py backend\app\services\autopilot\background_queue.py backend\tests\test_agent_ops.py
```

Result: passed.

Patch whitespace:

```powershell
git diff --check -- backend/app/api/v1/agent_ops.py backend/app/api/v1/autopilot.py backend/app/services/autopilot/background_queue.py backend/tests/test_agent_ops.py frontend/src/pages/PipelinePage.tsx frontend/src/pages/DepartmentsPage.tsx frontend/src/pages/TasksPage.tsx frontend/src/pages/settings/SettingsHeartbeat.tsx frontend/src/pages/GovernanceApprovalsPage.tsx frontend/src/pages/GovernanceAuditPage.tsx frontend/src/pages/ConnectionsPage.tsx
```

Result: passed.

## Tests Added Or Updated

- `backend/tests/test_agent_ops.py::test_customer_acquisition_workflow_route_is_draft_only`

Previously added MCP/cron regression tests remain in the tree, but could not be executed in this session because the local Python runtime cannot import `asyncio`.

## Runtime Validation Blocked

Backend tests:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_agent_ops.py -q
```

Result: blocked before test collection.

Error:

```text
OSError: [WinError 10106] The requested service provider could not be loaded or initialized
```

Direct proof:

```powershell
backend\.venv\Scripts\python.exe -c "import asyncio; print('asyncio ok')"
```

Result: same `_overlapped` / WinError 10106 failure.

Frontend build/typecheck:

```powershell
cd D:\Ideas\Daena\frontend
npm run build
npm run typecheck --if-present
```

Result: blocked before Vite/TypeScript can run.

Error:

```text
Could not determine Node.js install directory
Assertion failed: ncrypto::CSPRNG(nullptr, 0)
```

Launch:

```powershell
cd D:\Ideas\Daena\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Result: blocked at `uvicorn.config -> import asyncio` with WinError 10106.

Frontend launch:

```powershell
cd D:\Ideas\Daena\frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Result: blocked by Node CSPRNG initialization failure.

Health checks:

- `http://127.0.0.1:8000/health`: no backend listener; `Invoke-WebRequest` also fails on the same local service-provider issue.
- `http://127.0.0.1:5173`: no frontend listener; `Invoke-WebRequest` also fails on the same local service-provider issue.
- `netstat -ano | Select-String ':8000|:5173'`: no listeners found.

## Required Re-Run After Environment Fix

```powershell
cd D:\Ideas\Daena\backend
.\.venv\Scripts\python.exe -m pytest backend\tests\test_agent_ops.py tests\test_connections.py tests\test_heartbeat.py tests\services\test_mcp_registry_persistence.py -q
.\.venv\Scripts\python.exe -m pytest tests -q

cd D:\Ideas\Daena\frontend
npm run typecheck --if-present
npm run build

cd D:\Ideas\Daena
.\start-daena.bat
```

Browser smoke after launch:

- Chat / runtime selector.
- Connections / MCP install and cloud catalog.
- Tasks / background queue status.
- Settings / heartbeat cron status.
- Governance approvals.
- Governance audit log.
- Sales pipeline customer acquisition workflow.

## Verdict

Code-level P0/P1 repairs are patched and static validation passed. Live validation is blocked by the local Windows socket/crypto provider state, not by a product-level assertion from these checks. Do not mark Daena production-ready until pytest, frontend build, local launch, and browser smoke pass on a healthy environment.
