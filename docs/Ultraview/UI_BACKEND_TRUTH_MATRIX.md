# UI Backend Truth Matrix

Date: 2026-04-29

Status labels: working, repaired, partial, missing, disabled, unknown.

| Page/control family | Frontend file | Backend route/service | Persistence | Realtime | Status | Required next fix |
|---|---|---|---|---|---|---|
| Chat sessions/messages | `frontend\src\pages\ChatPage.tsx`, chat components | `/api/v1/chat/sessions`, `/messages`, `/messages/stream`, `chat_orchestrator.py` | DB chat/session models | streaming response | working/needs live validation | Run chat smoke once environment works. |
| Per-message model selector | `ChatInput.tsx` | `/api/v1/chat/model-registry`, `/api/v1/runtimes` | runtime/user settings | polling | working | Confirm selectable list in browser. |
| RuntimeSwapper component | `RuntimeSwapper.tsx` | props from runtime registry | none directly | none | not mounted in header | Keep as reusable or remove later. |
| Primary Mind | `connections\ConnectionsRuntimes.tsx`, `ConnectionsPage.tsx` | `/api/v1/runtimes/primary` | `User.settings.primary_runtime` | polling | working/needs live validation | Browser smoke. |
| Header connection health | `Header.tsx`, `ConnectionStatusIndicator.tsx` | `errorStore` fed by Axios | local store only | polling/error events | working | None. |
| Connector catalog | `useConnectorCatalog.ts`, `ConnectionsPage.tsx` | `/api/v1/connections/catalog` | `connectors` table seeded from JSON | cache/polling | working | Move browse modal marketplace to DB. |
| MCP install from connector setup modal | `ConnectionsPage.tsx` | `/connections/extensions/install` | Claude config plus `mcp_servers` row | refresh polling | repaired | Run regression tests after environment fix. |
| MCP uninstall | `ConnectionsPage.tsx` / extension rows | `/connections/extensions/uninstall` | Claude config removed, `McpServer` disabled | refresh polling | repaired | Browser smoke. |
| MCP registry live list | `ConnectionsPage.tsx` | `/connections/mcp-registry`, `mcp_bootstrap.py` | config-derived live state | polling | partial | Add DB+live combined view later. |
| Skills registry | `SkillsPage.tsx` | `/api/v1/skills`, `/api/v1/skill-refinery` | DB/file-backed services | polling | likely working | Smoke create/search. |
| Governance approvals | `GovernanceApprovalsPage.tsx` | `/api/v1/governance/approvals`, `/events` | DB approval requests | SSE | working/needs validation | SSE browser check. |
| Governance audit | `GovernanceAuditPage.tsx` | `/api/v1/governance/audit`, `/verify` | audit table/service | polling | working/needs validation | Verify filters and detail view. |
| Heartbeat cron list | settings heartbeat + routes | `/api/v1/heartbeat/cron` | process scheduler + `cron_runs` on execution | SSE `/cron/events` | repaired | Test after environment fixed. |
| Autopilot queue events | workstreams/tasks surfaces | `/api/v1/autopilot/queue/events` | `background_tasks` table | SSE | working/needs validation | Browser check reconnect. |
| Departments | `DepartmentsPage.tsx`, `DepartmentChatPage.tsx` | `/api/v1/departments`, `/agents`, department services | DB departments/agents | polling | working/needs validation | One department chat smoke. |
| DaenaBot | `/daenabot` redirect, chat commands | `/api/v1/daenabot/execute` | action/audit services | none | partial | Expose honestly through chat only. |
| Sales/customer workflow | Company Mode, Pipeline, Sales endpoints | `/api/v1/sales/prospect`, `/qualify`, `/marketing/author-outreach`, pipeline routes | CRM/pipeline tables | polling | partial | Build one guided demo UI flow. |
| Investor/grants | docs/pitch package | no dedicated `/investors/*` found | docs only | none | missing | Add tracker/draft API later. |
| Cybersecurity workflows | `ScanPage`, security pages | security dashboard, authorized scope, scan events | scan/job artifacts | SSE scan events | partial/guarded | Keep authorization gate visible. |
| Voice/avatar controls | `VoiceProvider`, TTS routes | `/api/v1/tts/*`, voice WS file exists | unknown | websocket/HTTP | partial | Validate device/browser permissions. |
| Memory/RAG/Obsidian panels | Settings memory + memory API | `/api/v1/memory/*` | memory tables | polling | partial | Add `/rag/status` and `/obsidian/status` or honest disabled cards. |
| System health | Dashboard/settings | `/health`, `/api/v1/health/*` | none | polling | working/needs live validation | Add `/api/status` alias if desired. |

## P0/P1 UI Fixes Completed

- MCP install no longer claims success if DB persistence fails.
- Global API failures are visible through the header indicator.
- Runtime fake fallback is removed from the active registry path.

## Remaining UI Truth Gaps

- Browse modal extension catalog is still frontend-static.
- Investor/grant operations are mostly document workflows, not product workflows.
- RAG/Obsidian status lacks a first-class API and should be either implemented or labeled as "not connected yet."
- Some advanced cognitive/Laevateinn surfaces use stubs and must stay experimental.

