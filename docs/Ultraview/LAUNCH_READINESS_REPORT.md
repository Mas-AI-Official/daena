# Launch Readiness Report

Date: 2026-04-29

Canonical root: `D:\Ideas\Daena`

## Launch Commands

Preferred:

```powershell
D:\Ideas\Daena\start-daena.bat
```

Backend direct:

```powershell
cd D:\Ideas\Daena\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend direct:

```powershell
cd D:\Ideas\Daena\frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

## Current Launch State

Launch is blocked in this Codex desktop environment:

- Python cannot import `asyncio` because `_overlapped` raises WinError 10106.
- Node/npm abort during crypto initialization: `ncrypto::CSPRNG(nullptr, 0)`.
- No listeners were detected on `8000` or `5173`.
- HTTP health probes cannot be trusted because local request tooling also hits the service-provider failure.

## Working By Code Inspection And Static Validation

- Canonical root is `D:\Ideas\Daena`; no duplicate root was patched.
- MCP persistence path writes tenant-scoped `McpServer` rows and hydrates registry state.
- Cron scheduler invokes runtime adapters and writes `CronRun` rows.
- Background queue exposes truthful persistence status.
- Header connection issue indicator receives API failures through `errorStore`.
- Runtime picker has no hardcoded demo fallback.
- Approval queue and audit log now show load errors visibly.
- Cloud MCP catalog no longer pretends entries are installed or running.
- Customer acquisition workflow creates a lead, draft outreach, follow-up task, approval request, and audit event without sending anything externally.

## Critical Blockers

| Priority | Blocker | Owner |
|---|---|---|
| P0 | Windows socket/crypto provider is broken for Python asyncio, Node CSPRNG, and local HTTP probes. | environment/operator |
| P0 | Full backend pytest cannot run until Python asyncio imports. | engineering after environment fix |
| P0 | Frontend typecheck/build cannot run until Node initializes. | engineering after environment fix |
| P1 | Browser smoke test is pending because backend/frontend cannot launch in this environment. | engineering after environment fix |

## Demo Readiness

Investor demo readiness: 72/100 by code inspection, blocked from live proof.

Production readiness: 60/100 until tests, build, launch, and smoke pass.

## What To Demo After Environment Fix

- Founder asks Daena to prepare a customer acquisition workflow.
- Daena creates a CRM lead, qualifies it, drafts outreach, creates a follow-up task, opens an approval request, and logs the audit trail.
- Connections shows real runtime/MCP state, with cloud catalog entries honestly marked as not installed.
- Tasks shows DB-backed or memory-only queue status.
- Heartbeat shows cron runtime dispatch and last run status.
- Approvals and audit pages show the governance chain.

## What Not To Demo Yet

- External email sending.
- Investor/grant submission.
- LinkedIn or restricted-platform automation.
- Third-party cybersecurity scanning.
- RAG/Obsidian as fully verified live sync unless a fresh smoke test proves it.

## Next 24 Hours

1. Repair local Python/Node/HTTP provider state or run validation from a clean terminal/VM.
2. Re-run backend tests and frontend build.
3. Launch Daena locally.
4. Smoke the customer acquisition draft/approval path in the browser.

## Next 7 Days

1. Add browser E2E for the customer acquisition workflow.
2. Add first-class RAG/Obsidian status panels.
3. Split `ConnectionsPage.tsx` into smaller route-owned components.
4. Add investor/grant tracker product routes.
5. Add end-to-end launch script health assertions.
