# Codex 5.5 Full System Audit

Date: 2026-04-29

## Canonical Root

Selected root: `D:\Ideas\Daena`

Evidence:
- `D:\Ideas\Daena` exists and contains `.git`, `backend`, `frontend`, `docs`, `docs\daena-Claude`, and `docs\Codex-Pitch`.
- `D:\Ideas\Daena_old_upgrade_20251213` was not present on disk during this audit.
- Current launch scripts (`start-daena.bat`, `setup-daena.bat`, `start-daena.sh`) point to `D:\Ideas\Daena`.
- `frontend\vite.config.ts` reads `backend\.daena-port`, which is produced by `backend\run.py`.
- Recent 2026-04-29 audit and pitch docs live under `D:\Ideas\Daena\docs`.

## Stack

Frontend:
- React 19, TypeScript 5.9, Vite 7, Tailwind 4, Zustand, Axios, React Router 7.
- Active entry: `frontend\src\App.tsx`.
- Active dev command: `npm run dev` inside `frontend`.
- Backend proxy: Vite reads `backend\.daena-port` and falls back to `127.0.0.1:8000`.

Backend:
- FastAPI, SQLAlchemy async, Alembic, SQLite dev, PostgreSQL-compatible production.
- Active entry: `backend\app\main.py`.
- Active launcher: `backend\run.py`.
- Active local command: `backend\.venv\Scripts\python.exe run.py`.
- Root health: `/health`.
- API prefix: `/api/v1`.

Database and migrations:
- Dev DB artifacts observed: `daena_dev2.db`, `backend\daena_dev2.db`.
- SQLAlchemy models include recent `CronRun`, `McpServer`, `BackgroundTask`, and `Workstream`.
- Alembic migration `backend\migrations\versions\005_add_cron_mcp_background_tables.py` exists for the post-audit persistence tables.

## Verified Systems

Runtime/model status:
- Backend route family: `/api/v1/runtimes`.
- Frontend hook: `frontend\src\hooks\useRuntimeRegistry.ts`.
- Frontend no longer uses the old `DEFAULT_RUNTIMES` fallback in `RuntimeSwapper`.
- Primary Mind is controlled from Connections/Mind Control and persisted via `/runtimes/primary`.

Frontend error visibility:
- `frontend\src\lib\api.ts` now records failures in `errorStore` and warns in console.
- `ConnectionStatusIndicator` is mounted in the header.
- Polling endpoints may be quiet by default, but failures are no longer invisible.

MCP:
- DB model: `backend\app\models\mcp_server.py`.
- Registry service: `backend\app\services\mcp_registry.py`.
- Import path `/api/v1/mcp-sync/import` persists to DB.
- This pass repaired `/api/v1/connections/extensions/install` and `/api/v1/connections/extensions/uninstall` so the UI install path also persists/soft-deletes MCP rows.

Cron/heartbeat:
- Scheduler service now dispatches through runtime adapters and persists `CronRun`.
- This pass fixed `backend\app\api\v1\heartbeat.py` so `/heartbeat/cron` reads the same process-wide scheduler that `main.py.lifespan` starts.

Background queue:
- `backend\app\services\autopilot\background_queue.py` is DB-backed and wired during lifespan.
- SSE endpoint exists at `/api/v1/autopilot/queue/events`.

Governance:
- Approval routes exist under `/api/v1/governance/approvals`.
- SSE endpoint exists at `/api/v1/governance/approvals/events`.
- Audit routes exist under `/api/v1/governance/audit`.

Security:
- Security dashboard, authorized scope, scan events, and tool management routes exist.
- Cybersecurity must remain authorized-only; external scanning still requires explicit founder approval and documented scope.

Memory/RAG/Obsidian:
- Memory endpoints exist under `/api/v1/memory`.
- RAG/Obsidian status endpoints were not found as first-class `/rag/status` or `/obsidian/status` routes; current memory/graph integration is distributed across memory, docs, graphify, Axon, and codebase-memory artifacts.

Company operations:
- Sales routes exist under `/api/v1/sales` via `agent_ops.py`.
- Pipeline/project routes exist under `/api/v1/pipeline` and `/api/v1/projects`.
- Company Mode routes exist and are designed for founder-approved sales/marketing activation.
- Investor/grant routes were not found as dedicated `/investors/*` or `/grants/*` API families; current investor work is mostly in docs/pitch package.

## Fixes Made In This Pass

- `backend\app\api\v1\connections.py`: UI MCP install now writes config and persists a tenant-scoped `McpServer`; uninstall now removes config and soft-deletes the DB row.
- `frontend\src\pages\ConnectionsPage.tsx`: install toasts now show an explicit error if config was written but DB persistence failed.
- `backend\app\api\v1\heartbeat.py`: API cron listing now uses the process-wide scheduler singleton.
- `backend\tests\test_connections.py`: added persistence and soft-delete regression tests.
- `backend\tests\test_heartbeat.py`: added singleton-consistency regression test.

## Validation Status

Static:
- `python -m py_compile` passed for changed Python files.
- `git diff --check` passed for changed files.

Blocked:
- Pytest cannot run in this Windows session because importing `asyncio` fails with `_overlapped` WinError 10106.
- `npm` cannot run because Node initialization fails on CSPRNG.
- WSL cannot run due `Wsl/Service/0x8007072c`.

No production-ready claim is made until those environment issues are resolved and tests/build pass.

