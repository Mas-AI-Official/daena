# Frontend Keep Repair Rebuild Remove

Date: 2026-04-29

This classification is based on graph lookup, route/source inspection, current API probes, and existing repair logs. It is not a design opinion pass. The standard is: real backend data, persistent actions, visible failure, and acceptable performance.

| Area | File path | Classification | Current problem | Backend endpoint | Data real | Persists | Performance impact | Priority |
|---|---|---|---|---|---|---|---|---|
| Chat/history | `frontend\src\pages\ChatPage.tsx` | KEEP | Core workflow is useful. Some runtime and quota indicators still depend on split status sources. | `/api/v1/chat/*`, `/api/v1/billing/my-quota` | Mostly real | Yes | Medium due streaming and history loads | P1 repair indicators |
| Navbar/sidebar | `frontend\src\components\layout\Header.tsx`, `Sidebar.tsx` | REPAIR | `AGI ACTIVE` can imply system health while backend may be degraded/offline. | `/heartbeat/status`, `/governance/approvals`, auth store | Mixed | Partial | Low | P0 label truth |
| Dashboard | `frontend\src\pages\DashboardPage.tsx` | REPAIR | Has useful summary, but some cards are static or optimistic. Security Ops count appears hardcoded in places. | `/agents`, `/analytics`, `/heartbeat` | Mixed | Read-only | Medium | P1 |
| Mind Control | `frontend\src\pages\MindsPage.tsx`, `MindDetailPage.tsx` | KEEP | Founder likes it. Needs status truth tied to runtime registry. | `/souls`, `/company-mode` | Mostly real | Yes | Low | P1 |
| Runtime providers | `frontend\src\pages\ConnectionsPage.tsx`, `useRuntimeRegistry.ts` | REBUILD | Split-brain status across runtime cache, API keys, CLI auth, and provider models. Existing `/runtimes` does not persist full truth state. | `/runtimes` | Partial | Partial | High due repeated probes | P0 |
| MCP servers | `ConnectionsPage.tsx`, `useMcpRegistry.ts`, `useMCPDetections.ts` | REBUILD | Detection count and rendered live count diverge. Imported does not always mean callable. Secrets from configs must never be surfaced. | `/mcp-sync/*`, `/connections/mcp-registry` | Partial | Partial | High | P0 |
| Extensions | `ConnectionsPage.tsx` | REBUILD | Browse catalog can say installed before durable callable state exists. Large hardcoded marketplace still present. | `/connections/extensions/*` | Mixed | Partial | High component cost | P0 |
| Plugins | `ConnectionsPage.tsx` | REBUILD | Too many card-like fake marketplace states. Needs installed/configured/persisted/reachable/callable truth. | `/connections/catalog`, `/connections/extensions` | Mixed | Partial | High | P1 |
| Connections | `ConnectionsPage.tsx` | REBUILD | One oversized 3000 line page owns runtimes, MCP, connectors, plugins, import flows, and modal marketplace. Hard to verify and slow. | Many | Mixed | Partial | High | P0/P1 |
| Departments | `frontend\src\pages\DepartmentsPage.tsx` | KEEP | Founder likes it. Previous fake fallback cards were reportedly removed. Needs live error states kept. | `/agents`, `/department-*` | Mostly real | Read/write depending action | Medium | P1 |
| Skills | `frontend\src\pages\SkillsPage.tsx` | KEEP | Useful if backed by registry. Needs no fake activation success. | `/skills`, `/skills/refinery` | Mostly real | Yes | Medium | P1 |
| Tasks | `frontend\src\pages\TasksPage.tsx` | KEEP | Useful. Queue persistence status was added in prior work. | `/execution/tasks`, `/autopilot/queue/status` | Mostly real | Yes | Medium | P1 |
| Files | `frontend\src\pages\FilesPage.tsx` | KEEP | Founder likes it. Must preserve file safety and explicit errors. | `/files` | Real if endpoint succeeds | Yes | Medium | P1 |
| Security Ops | `frontend\src\pages\SecurityDashboardPage.tsx`, `frontend\src\pages\security\*` | REPAIR | User reports skeleton forever. Endpoint probe showed `/api/v1/security/dashboard` is 404, while page fetches `/security/status`, `/security/tools`, `/security/shields`, `/security/opsec/status`. Needs error/empty/offline states, not infinite skeleton. | `/security/status`, `/security/tools`, `/security/shields` | Unknown until authenticated page probe | Read/write security actions | High | P0 |
| Scan Scope | `frontend\src\pages\SecurityScopePage.tsx` | KEEP | Scoped defensive workflow is valuable. Must stay defensive and approval gated. | `/security/authorized-scope` | Real | Yes | Low | P1 |
| Approvals | `frontend\src\pages\GovernanceApprovalsPage.tsx` | KEEP | Core governance surface. Recent repair added load error state. | `/governance/approvals` | Real | Yes | Low | P1 |
| Policy Rules | `frontend\src\pages\PoliciesPage.tsx`, `frontend\src\components\policies\*` | REPAIR | Needs proof save compiles to backend policy and affects execution loop. Dropdown contrast reported bad. | `/policies/*` | Partial until tested | Should persist | Medium | P0/P1 |
| Audit Log | `frontend\src\pages\GovernanceAuditPage.tsx` | KEEP | Core truth trail. Needs audit links from runtime registry events. | `/governance/audit` | Real | Yes | Medium | P1 |
| Analytics | `frontend\src\pages\AnalyticsPage.tsx` | REPAIR | Prior work removed fake placeholder behavior. Needs live validation. | `/analytics/*` | Partial | Read-only | Medium | P2 |
| Settings / LLM Providers | `frontend\src\pages\settings\SettingsLLM.tsx` | REPAIR | Provider health and API key source of truth are inconsistent. Perplexity/Gemini config exists in `.env`, but UI must show configured vs tested. | `/settings/user`, `/runtimes`, provider configs | Partial | Partial | Medium | P0 |
| Settings / Models & Runtimes | `SettingsPage.tsx`, runtime hooks | REBUILD into Runtime Center | Same split-brain problem as Connections. | `/runtimes` | Partial | Partial | Medium | P0 |
| Settings / Memory | `frontend\src\pages\settings\SettingsMemory.tsx` | KEEP | `/memory/status` now honestly says NBMF online, RAG not configured, Obsidian available. Needs retrieval test before claiming RAG online. | `/memory/status` | Real | Read-only | Low | P1 |
| Settings / Governance | `frontend\src\pages\settings\SettingsGovernance.tsx` | REPAIR | Must expose only Unleashed, Balanced, Governed by default. Hide old noisy tiers under Advanced. | `/settings/user`, governance runtime | Partial | Yes if settings save works | Low | P0 |
| Settings / Notifications | `frontend\src\pages\settings\SettingsNotifications.tsx` | REPAIR | Browser notification test exists, but email notifications are UI-only unless configured. Disable or mark not configured. | Browser API, no clear backend | Mixed | Local only | Low | P1 |
| Billing & Usage | `frontend\src\pages\settings\SettingsBilling.tsx`, billing pages | REPAIR/HIDE UNTIL REAL | Duplicate founder quota/plan symptom likely from tenant plan plus founder quota profile. Show one founder truth or hide production billing. | `/billing/*` | Mixed | Yes | Medium | P0 |
| Daena Heartbeat | `frontend\src\pages\settings\SettingsHeartbeat.tsx` | REPAIR | API shows configured checks but daemon stopped, cycle_count 0. UI must distinguish configured from executed. | `/heartbeat/status`, `/heartbeat/run-once` | Real but misleading | Yes for run history if wired | Medium | P0 |
| Company/tenant panel | `frontend\src\pages\CompanyModePage.tsx`, `AccountPage.tsx`, org/settings | REPAIR | Tenant/founder identity duplication needs backend DB audit. | `/org`, `/settings/user`, `/billing` | Mixed | Yes | Medium | P0 |

## Immediate P0 Frontend Direction

Do not keep patching `ConnectionsPage.tsx` as the source of truth. It is too large and combines too many lifecycle states. Build a separate Runtime & Connections Center backed by a new backend truth API, then either replace `/connections` with it or leave old marketplace browsing behind an advanced tab.
