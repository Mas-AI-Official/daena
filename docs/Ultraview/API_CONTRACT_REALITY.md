# API Contract Reality

Date: 2026-04-29

Base prefix: `/api/v1`

## Required Contract Coverage

| Desired capability | Current route reality | Status |
|---|---|---|
| `/health` | Root `/health` exists in `main.py`; `/api/v1/health/*` also exists. | working |
| `/api/status` | No exact `/api/status`; use `/health` or `/api/v1/health`. | missing alias |
| `/api/system/summary` | No exact route found; dashboard/analytics/health provide pieces. | missing |
| `/api/runtimes` | `/api/v1/runtimes` exists. | working |
| `/api/models/status` | Model status is split across `/runtimes`, `/chat/model-registry`, `/health/runtime`. | partial |
| `/api/chat/session` | Actual routes are `/api/v1/chat/sessions*`. | working with different path |
| `/api/chat/send` | Actual stream/message routes exist under `/api/v1/chat`. | working with different path |
| `/api/agents` | `/api/v1/agents` and `/api/v1/departments`. | working |
| `/api/departments` | `/api/v1/departments`. | working |
| `/api/tasks` | `/api/v1/execution/tasks` and `/api/v1/heartbeat/queue`. | partial path mismatch |
| `/api/governance/approvals` | `/api/v1/governance/approvals`, `/events`. | working |
| `/api/audit/logs` | `/api/v1/governance/audit`. | working with different path |
| `/api/mcp/status` | `/api/v1/connections/mcp-registry`, `/api/v1/mcp-sync/detected`. | partial |
| `/api/mcp/servers` | Live state under connections mcp-registry; persistent rows via service not exposed as a direct route. | partial |
| `/api/connectors/status` | `/api/v1/connections/connectors`, `/instances`, `/extensions`. | working |
| `/api/skills` | `/api/v1/skills` and `/api/v1/skill-refinery`. | working |
| `/api/memory/status` | `/api/v1/memory/stats` and dream status exist. | partial |
| `/api/rag/status` | No exact route found. | missing |
| `/api/obsidian/status` | No exact route found. | missing |
| `/api/heartbeat/status` | `/api/v1/heartbeat/status`. | working |
| `/api/heartbeat/cron/runs` | `CronRun` model exists; exact route for runs not confirmed. | partial |
| `/api/autopilot/queue` | `/api/v1/autopilot/queue/events`; state/summary per session. | partial |
| `/api/sales/leads` | Sales/prospect routes exist; exact leads route not found. | partial |
| `/api/sales/outreach/draft` | `/api/v1/marketing/author-outreach`, `/api/v1/crm/outreach-drafts`. | working with different path |
| `/api/investors/programs` | Not found. | missing |
| `/api/investors/application/draft` | Not found. | missing |
| `/api/security/authorized-workflows` | `/api/v1/security/authorized-scope` and scan routes. | partial |
| `/api/security/report/draft` | Scan report routes exist. | partial |

## Contract Fixes Made

- `/api/v1/connections/extensions/install` response now includes:
  - `mcp_persisted`
  - `mcp_server_id`
  - `persistence_error`
  - `status` = `installed` or `installed_not_persisted`
- `/api/v1/connections/extensions/uninstall` response now includes:
  - `mcp_persisted_removed`
  - `persistence_error`
- `/api/v1/heartbeat/cron` now reads the process-wide scheduler singleton.

## Recommended Contract Cleanup

1. Add read-only aliases for founder-facing simple paths:
   - `/api/status`
   - `/api/system/summary`
   - `/api/rag/status`
   - `/api/obsidian/status`
2. Expose a combined MCP server status endpoint:
   - persisted rows from `mcp_servers`
   - live bootstrap state from Claude config
   - health/probe state
3. Add investor/grants tracker routes only after the demo workflow is stable.

