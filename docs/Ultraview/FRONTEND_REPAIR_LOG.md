# Frontend Repair Log

Generated: 2026-04-29  
Canonical root: `D:\Ideas\Daena`

## Repairs Shipped In This Pass

| Area | Files | Repair | Effect chain verified |
|---|---|---|---|
| Analytics truth | `frontend/src/pages/AnalyticsPage.tsx` | Removed placeholder wording and fake zero department/provider fallback on API failure. Added visible offline banner and `--` metrics when data is unavailable. | Page load -> `GET /analytics/dashboard` -> success renders metrics; failure records global API error + inline analytics offline state. |
| Developer settings | `frontend/src/pages/settings/SettingsDeveloper.tsx` | Removed fake masked API key and fake “generate key” action. API keys now link to `/account`. Webhook controls are disabled with reason because no backend route exists. | Click API keys -> navigate to live account surface. Webhook controls cannot pretend to save. |
| Slash commands | `frontend/src/components/chat/SlashCommands.tsx` | Removed fake `/export`, `/compact`, `/clear`; wired `/cost` to billing and `/marketplace` to skills. | Slash command -> real route or real UI state change. |
| Connectors | `frontend/src/pages/ConnectionsPage.tsx` | Removed fake connector “View docs” toast and connector batch-selection toolbar. Reworded hosted OAuth broker as unavailable in local build. | Connector row -> configure/connect/disconnect/switch only. No batch connector action remains. |
| Memory/RAG/Obsidian | `backend/app/api/v1/memory.py`, `frontend/src/pages/settings/SettingsMemory.tsx` | Added `GET /memory/status` and wired settings to it. NBMF status is real, RAG reports `not_configured`, Obsidian checks actual Daena-Mind vault path. Added error/retry states. | Page load -> `GET /memory/status` -> render NBMF/RAG/Obsidian status; failure shows endpoint unreachable, not zero counts. |
| Skills registry | `frontend/src/pages/SkillsPage.tsx` | Added registry load-error state. Rewrote bulk permission/enable/disable actions to await backend mutations, report partial failures, and refresh canonical state on failure. | Click bulk action -> `PATCH /skills/{id}` for each skill -> success toast only after promises settle. |
| Memory import | `frontend/src/pages/settings/SettingsGeneral.tsx` | Fixed import action from invalid `POST /memory` to real `POST /memory/memories` with `content_type`, `scope`, and confidence. | Import to Daena -> NBMF store endpoint -> memory row persisted or error toast. |

## Existing Repairs Confirmed In Code

| Area | Evidence | Status |
|---|---|---|
| API failures visible | `frontend/src/lib/api.ts` records every non-cancelled error in `errorStore` and logs details; `ConnectionStatusIndicator` is mounted in header. | Confirmed. |
| Runtime fallback removed | `RuntimeSwapper.tsx` no longer defines hardcoded `DEFAULT_RUNTIMES`; `useRuntimeRegistry.ts` polls `/runtimes`. | Confirmed. |
| MCP persistence | Backend has DB-backed MCP registry service and models from the prior P0/P1 repair pass. Connections page uses MCP registry hooks and import flow. | Confirmed by code shape, not live-smoked due runtime environment failure. |
| Cron execution claim | `SettingsHeartbeat.tsx` reads `/heartbeat/cron` and surfaces dispatch/run records. Backend `heartbeat.py` and scheduler were touched in prior pass. | Confirmed by code shape, not live-smoked due runtime environment failure. |
| Background queue visibility | `TasksPage.tsx` reads `/autopilot/queue/status`; backend queue exposes persistence metadata. | Confirmed by code shape. |
| Approval queue visibility | `GovernanceApprovalsPage.tsx` and chat inline approval banner read `/governance/approvals` and post decisions. | Confirmed. |
| Audit log visibility | `GovernanceAuditPage.tsx` reads `/governance/audit` and `/governance/audit/verify`. | Confirmed. |
| Draft-only sales workflow | `PipelinePage.tsx` posts to `/sales/customer-acquisition/draft-workflow`; backend creates draft, task, approval, and audit event with no external send. | Confirmed. |

## Remaining Honest Disabled/Unavailable Surfaces

| Surface | Why it remains unavailable | Current behavior |
|---|---|---|
| Developer webhooks | No backend webhook persistence/delivery/audit contract yet. | Disabled with reason. |
| RAG vector retrieval | NBMF exists, but no dedicated vector search route is registered. | `/memory/status` returns `rag.not_configured`. |
| Dedicated investor/grant route | No active App route or backend module dedicated to grants/investors yet. | No exposed fake page. |
| Hosted OAuth broker | Local build does not include hosted broker service. | Connections page states unavailable and offers MCP/manual OAuth. |

## No External Actions Performed

No emails, application submissions, social posts, restricted scraping, or third-party security scans were performed. The sales/customer workflow remains draft-only with founder approval.

