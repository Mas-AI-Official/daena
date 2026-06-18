# Ready To Go Checklist

Date: 2026-04-29

| Area | Status | Notes |
|---|---|---|
| Launch | blocked | Local Python asyncio and Node CSPRNG fail before services start. |
| Backend | static pass | `py_compile` passed on touched backend files; pytest blocked by environment. |
| Frontend | patched, build blocked | Fake MCP/department UI removed; build blocked by Node CSPRNG failure. |
| Real-time | partial | SSE hooks/endpoints exist; live smoke pending. |
| Agents | improved | Departments page no longer fabricates fallback data. |
| MCP | improved | Persistence path is DB-backed by code; cloud catalog no longer claims live installs. |
| Connectors | partial | Backend catalog exists; live connector OAuth smoke pending. |
| Memory/RAG/Obsidian | partial | Needs first-class status panel and smoke validation. |
| Skills | partial | Routes/folders exist; live smoke pending. |
| Governance | improved | Approval queue load failures are visible. |
| Approval Queue | improved | Sales workflow creates approval requests; live browser validation pending. |
| Audit Logs | improved | Audit load failures are visible; sales workflow writes audit event by code. |
| Sales Workflow | improved | Draft-only customer acquisition workflow added with founder approval gate. |
| Investor Workflow | missing product module | Docs exist; product tracker still needed. |
| Cybersecurity Workflow | guarded partial | Authorized scope routes exist; no third-party scans run. |
| Pitch/Demo | good docs | Needs live product proof after environment repair. |
| Tests | blocked | Environment prevents pytest/npm; static checks passed. |
| Security | improved | External action path is draft-only and approval-gated. |
| Deployment | not ready | Do not deploy until tests/build/launch pass. |

## Pass Criteria Before Demo

- Backend health returns healthy.
- Frontend loads at `http://localhost:5173`.
- Login/session works.
- Chat stream works.
- `/runtimes` shows real runtime state.
- Cloud MCP catalog is read-only and installed MCPs report persistence status.
- Background queue status shows DB-backed or memory-only honestly.
- Cron jobs report runtime dispatch status and last result.
- Approval and audit routes work.
- Sales workflow creates draft outreach, task, approval, and audit without sending.
- No external message, application, post, scrape, or scan is executed without founder approval.
