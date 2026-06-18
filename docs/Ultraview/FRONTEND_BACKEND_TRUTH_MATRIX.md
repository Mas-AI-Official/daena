# Frontend Backend Truth Matrix

Generated: 2026-04-29  
Canonical root: `D:\Ideas\Daena`  
Scope: active React routes from `frontend/src/App.tsx`, active page components under `frontend/src/pages`, shared chat controls, and visible founder-control surfaces.

## System-Wide Surfaces

| Surface | Frontend file | Visible controls/cards | Backend contract | Realtime | Truth status |
|---|---|---|---|---|---|
| App shell routes | `frontend/src/App.tsx` | Protected route gate, redirects | auth store + route-level components | none | Working route table. Legacy redirects go to active pages. |
| Header connection state | `frontend/src/components/layout/Header.tsx`, `frontend/src/components/common/ConnectionStatusIndicator.tsx` | Global degraded/down indicator, retry/dismiss | `frontend/src/stores/errorStore.ts` fed by `frontend/src/lib/api.ts` | store updates | Working. API failures are visible without toast spam. |
| API client | `frontend/src/lib/api.ts` | All Axios traffic | `/api/v1/*`, JWT refresh, error classification | none | Working. Silent-prefix failures still record to error store. |
| Runtime picker | `frontend/src/components/chat/RuntimeSwapper.tsx`, `frontend/src/hooks/useRuntimeRegistry.ts` | Runtime dropdown/status | `GET /runtimes`, `PUT /runtimes/primary`, `POST /runtimes/{id}/test`, `POST /runtimes/{id}/disconnect` | 30s polling | Working. No hardcoded runtime fallback remains. |
| Chat console | `frontend/src/pages/ChatPage.tsx`, `frontend/src/stores/chatStore.ts`, `frontend/src/components/chat/ChatInput.tsx` | send, attach files, session rename/archive, mode selection | `GET /chat/sessions`, `GET /chat/sessions/{id}/messages`, `POST /chat/messages/stream`, `PATCH /chat/sessions/{id}`, `POST /files/upload`, `GET /billing/my-quota` | streaming fetch | Working backend path. External actions remain governed by chat/orchestrator policy. |
| Slash commands | `frontend/src/components/chat/SlashCommands.tsx` | `/settings`, `/connect`, `/governance`, `/heartbeat`, `/audit`, `/cost`, `/marketplace`, `/memory`, `/scan` | navigation to real pages; `/mode cmd/exe` updates UI store | none | Repaired. Fake `/export`, `/compact`, and fake cost toast removed. |

## Route/Page Matrix

| Route | Page/component | Primary UI elements | Backend endpoints | Persistence/audit | Status |
|---|---|---|---|---|---|
| `/login` | `LoginPage.tsx` | login form | `POST /auth/login` via auth store | session/token | Working. |
| `/register` | `RegisterPage.tsx` | registration form | `POST /auth/register` via auth store | user/tenant | Working. |
| `/forgot-password` | `ForgotPasswordPage.tsx` | reset request | `POST /auth/forgot-password` | email/token if backend configured | Working or backend-dependent. |
| `/reset-password` | `ResetPasswordPage.tsx` | reset form | `POST /auth/reset-password` | auth credential | Working or backend-dependent. |
| `/complete-profile` | `CompleteProfilePage.tsx` | tenant/company setup | profile endpoints/auth store | user profile | Working. |
| `/dashboard` | `DashboardPage.tsx` | founder summary cards, health, approvals, pipeline, runtime | `GET /chat/sessions`, `/governance/approvals`, `/agents/departments`, `/health/detailed`, `/memory/memories`, `/governance/audit`, `/pipeline/summary`, `/runtimes` | read-only dashboard | Working with visible degraded states. |
| `/chat`, `/chat/:sessionId` | `ChatPage.tsx` | VP chat, sessions, attachments, running tasks | `/chat/*`, `/execution/tasks`, `/files/upload`, `/projects/{id}` | chat/session/message/audit backend | Working. |
| `/governance/approvals` | `GovernanceApprovalsPage.tsx`, `InlineApprovalBanner.tsx` | approval list, approve/reject | `GET /governance/approvals`, `POST /governance/approvals/{id}/decide`, `GET /governance/approvals/events` | approval rows + audit | Working. SSE with polling backstop. |
| `/governance/audit` | `GovernanceAuditPage.tsx` | audit feed, verify chain | `GET /governance/audit`, `GET /governance/audit/verify` | audit log | Working. |
| `/tasks` | `TasksPage.tsx` | task queue, retry, cancel, queue status | `GET /execution/tasks`, `PATCH /execution/tasks/{id}`, `POST /execution/tasks/{id}/run`, `GET /autopilot/queue/status` | task rows + persistent queue | Working. Background queue persistence is visible. |
| `/connections` | `ConnectionsPage.tsx` | runtimes, connectors, MCP servers, cloud catalog, CLI bridge | `/runtimes`, `/connections/connectors`, `/connections/instances`, `/connections/extensions`, `/connections/extensions/install`, `/connections/extensions/{id}/permissions`, `/connectors/{id}/oauth/authorize`, `/settings/oauth-credentials`, `/bridge/status`, `/bridge/token`, MCP sync hooks | runtime/user settings, connector instances, extension permissions, MCP registry | Repaired. Connector batch fake controls removed; cloud catalog read-only until install; hosted broker labeled unavailable locally. |
| `/skills` | `SkillsPage.tsx` | skill registry, import, activation, governance tier, bulk controls | `GET /skills`, `GET /skills/installed`, `POST /skills`, `PATCH /skills/{id}` | skill registry | Repaired. Bulk controls now await backend and refresh on partial failure. |
| `/settings` | `SettingsPage.tsx` | settings sections | section-specific endpoints below | varies | Working shell. |
| `/settings/general` | `SettingsGeneral.tsx` | profile, defaults, import data | `GET/PUT /settings/user`, `POST /memory/memories` | user settings + memory | Repaired. Import now posts to real NBMF store endpoint. |
| `/settings/developer` | `SettingsDeveloper.tsx` | API keys link, disabled webhooks, debug switches, env card | `GET /settings`, `GET /health`; API keys via `/account` | settings/UI prefs | Repaired. Fake masked API key removed; webhook form disabled with reason. |
| `/settings/memory` | `SettingsMemory.tsx` | NBMF/RAG/Obsidian status, tiers, purge, validation | `GET /memory/status`, `POST /memory/memories/clear-ephemeral`, `POST /memory/experiences/validate` | memory rows + trust validation | Repaired. New honest status route exposes RAG not-configured and Obsidian vault state. |
| `/settings/heartbeat` | `SettingsHeartbeat.tsx` | heartbeat status/history/cron, pause/start/run/configure | `GET /heartbeat/status`, `/heartbeat/history`, `/heartbeat/cron`, `POST /heartbeat/*` | heartbeat config + cron runs | Working. Cron execution claims are backed by runtime dispatch/run records if backend service is healthy. |
| `/settings/billing` | `SettingsBilling.tsx`, `SettingsLLM.tsx` | usage/quota/provider history/subscriptions | `/billing/*`, `/settings/user`, `/runtimes/subscriptions` | billing/settings | Working if backend data available. |
| `/settings/models-runtimes` | `SettingsModelsRuntimes.tsx` | provision model, runtime/model status | `POST /dynamic-models/provision`, `GET /runtimes`, `GET /chat/model-registry` | runtime/model registry | Working/honest status. |
| `/settings/privacy` | `SettingsPrivacy.tsx` | export/delete request/privacy prefs | `GET /settings/user/export`, `POST /settings/user/delete-request`, `GET /settings/user` | account data/settings | Working or backend-dependent. |
| `/departments`, `/departments/:id` | `DepartmentsPage.tsx`, `DepartmentChatPage.tsx` | department cards, department chat | `GET /agents/departments` | department records | Repaired earlier. No fake department fallback cards. |
| `/minds`, `/minds/:slug` | `MindsPage.tsx`, `MindDetailPage.tsx` | soul gallery, refine all, proposals, detail refine/approve/reject | `GET /souls`, `GET /souls/proposals`, `POST /souls/refine-all`, `GET /souls/{slug}`, `POST /souls/{slug}/refine`, `POST /souls/proposals/{id}/{decision}` | soul/proposal records | Working; proposal fallback failure does not block souls. |
| `/company-mode` | `CompanyModePage.tsx` | seed brief, activate mission, mission drafts/send outcomes | `/company-mode/*` | company-mode records, approvals for external sends | Working. External sends remain approval-gated by backend. |
| `/pipeline` | `PipelinePage.tsx` | sales/delivery pipeline, create/advance/mark lost, customer-acquisition draft workflow | `GET /pipeline/summary`, `GET /pipeline/projects`, `POST /pipeline/projects`, `POST /pipeline/projects/{id}/advance`, `POST /pipeline/projects/{id}/mark-lost`, `POST /sales/customer-acquisition/draft-workflow` | pipeline project, lead/contact, task, approval, audit | Working. Draft-only sales workflow creates founder approval and sends nothing externally. |
| `/projects`, `/projects/:id` | `ProjectsPage.tsx`, `ProjectDetailPage.tsx` | CRUD project, tasks/files/working dir | `GET/POST/PUT /projects`, `GET /projects/{id}`, `GET /projects/{id}/tasks`, `GET /projects/{id}/files`, `PUT /projects/{id}` | project records | Working. |
| `/files` | `FilesPage.tsx` | upload/list/download/search/sort | `GET /files`, `POST /files/upload`, `GET /files/{id}/download` | file records/storage | Working. |
| `/analytics` | `AnalyticsPage.tsx` | usage/cost/governance/dept/provider charts | `GET /analytics/dashboard` | read-only analytics | Repaired. API failure shows unavailable/stale style state instead of fake zeros. |
| `/policies` | `PoliciesPage.tsx` | policy compile/save/delete | `GET /policies`, `POST /policies/compile`, `POST /policies`, `DELETE /policies/{id}` | policy YAML/DB + audit | Working. |
| `/security` | `SecurityDashboardPage.tsx` | security overview/tools/scans/shields/missions | `GET /security/status`, `/security/tools`, `/security/shields`, `/security/opsec/status`, `/security/scans/{id}` | security state | Working. Scanning remains authorization-gated. |
| `/security/scope` | `SecurityScopePage.tsx` | authorized scope editor/test | `GET/PUT /security/authorized-scope`, `POST /security/authorized-scope/test` | authorized scope | Working. Prevents third-party scans without scope. |
| `/scan`, `/scan/walkthrough/:jobId` | `ScanPage.tsx`, `ScanWalkthroughPage.tsx` | start/list/delete/rerun/report/pdf/walkthrough | `/security/scans/*`, SSE events | scan job/report rows | Working with SSE/polling. Requires authorized target. |
| `/engagements` redirect | `EngagementConsolePage.tsx` | engagement jobs/start/status | `/engagements`, `/engagements/{id}/status`, approval response body | engagement jobs/approvals | Working/backend-dependent. |
| `/workstreams` | `WorkstreamsPage.tsx` | workstream detail/redirect/actions/list | `/workstreams`, `/workstreams/{id}`, `/workstreams/{id}/redirect`, `/workstreams/{id}/{action}` | workstream records | Working/backend-dependent. |
| `/account` | `AccountPage.tsx` | account details/API keys | account API key components | user/API key records | Working. Developer API-key panel links here. |

## Explicitly Disabled Or Not Yet Active

| Surface | Reason | Current UI behavior |
|---|---|---|
| Developer webhooks | No persistent webhook route/audit contract in current backend. | Disabled controls with `Not connected` badge and reason. |
| Dedicated Investor/Grant page | No active route in `App.tsx` yet. | No fake page is exposed. Investor/grant work should route through docs/pipeline until a backend module exists. |
| Dedicated RAG vector service | No dedicated vector/RAG retrieval route registered. | `/memory/status` reports `rag.status = not_configured`; NBMF recall remains real. |
| Hosted OAuth broker | Local build has no hosted broker. | Connections page labels hosted broker unavailable and offers MCP/manual OAuth setup. |
| External sales sending | Unsafe without founder approval. | Sales workflow creates draft + approval only; `external_action_sent=false`. |

