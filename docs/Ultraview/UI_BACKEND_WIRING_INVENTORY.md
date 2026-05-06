# UI Backend Wiring Inventory

**Date:** 2026-05-06
**Sprint:** DAENA-SPRINT-21-UI-BACKEND-WIRING-CLOSURE — PR-1
**Source:** Read-only crawl of `D:\Ideas\Daena\frontend\src` and `App.tsx`.
**Scope:** Inventory only. Behavior unchanged.

## Summary

- **36 routes** (7 public + 26 protected + 3 redirects)
- **23 sidebar items** across 6 groups (Core, Intelligence, Go-to-Market, Execution, Connections, Governance)
- **180+ clickable actions** mapped to backend endpoints or local state
- **10 explicit "coming soon" stubs** plus several silent-disabled buttons (called out in PR-3)

## Inventory Table

| Page route | File | Action label | Action type | Backend endpoint or hook | Next screen / state | Notes |
|---|---|---|---|---|---|---|
| /login | LoginPage.tsx | Email / password / Sign in | form | `POST /auth/login` | /dashboard | OAuth fallback present |
| /login | LoginPage.tsx | Forgot password / Register | links | navigate | /forgot-password, /register | |
| /register | RegisterPage.tsx | Register | button | `POST /auth/register` | /auth/callback or /complete-profile | |
| /forgot-password | ForgotPasswordPage.tsx | Request reset | button | `POST /auth/forgot-password` | /reset-password | |
| /reset-password | ResetPasswordPage.tsx | Reset password | button | `POST /auth/reset-password` | /login | Token-based |
| /chat | ChatPage.tsx | Composer / Send / New chat / Session list | inputs+buttons | `POST /chat/messages`, `GET /chat/sessions` | scroll thread, Ctrl+N opens fresh, /chat/{sid} | Composer supports plugin attribution |
| /dashboard | DashboardPage.tsx | Stat: Pending Approvals | clickable card | `GET /governance/approvals?status=PENDING` | /governance/approvals | wired |
| /dashboard | DashboardPage.tsx | Stat: Active Tasks | clickable card | `GET /execution/tasks?status=RUNNING` | /tasks | wired |
| /dashboard | DashboardPage.tsx | Stat: Messages | clickable card | none | /departments | display only |
| /dashboard | DashboardPage.tsx | Stat: Connected | clickable card | none | /connections | display only |
| /dashboard | DashboardPage.tsx | Activity item | link | context | various | |
| /departments | DepartmentsPage.tsx | Department card | link | `GET /agents/departments` | /departments/{id} | live status badge from `/department-states` (5s) |
| /departments/{id} | DepartmentChatPage.tsx | Composer / Send | inputs+button | `POST /departments/{id}/chat/messages` | append | inter-dept messages surface here |
| /governance/approvals | GovernanceApprovalsPage.tsx | Status filter | select | `GET /governance/approvals?status=...` | filter URL | bookmarkable |
| /governance/approvals | GovernanceApprovalsPage.tsx | Approve / Reject | buttons | `POST /governance/approvals/{id}` | row update | Phase 3 modal |
| /governance/audit | GovernanceAuditPage.tsx | Audit log + filter | display | `GET /governance/audit` | inline | read-only |
| /governance/trust | GovernanceTrustPage.tsx | Trust settings | form | `POST /governance/trust` | persist | founder-gated |
| /security | SecurityDashboardPage.tsx | Security dashboard | display | `GET /security/dashboard` | inline | |
| /security/scope | SecurityScopePage.tsx | Scope config | form | `POST /security/scope` | persist | |
| /scan | ScanPage.tsx | Start scan | button | `POST /security/scan/start` | /scan/walkthrough/{jobId} | start→poll→auto-load |
| /scan | ScanPage.tsx | Scan history | display | `GET /security/scan/history` | inline | |
| /scan/walkthrough/{jobId} | ScanWalkthroughPage.tsx | Poll status | interval | `GET /security/scan/{jobId}/status` | auto-nav on complete | exponential backoff |
| /policies | PoliciesPage.tsx | Policy list / detail | display+link | `GET /policies`, `GET /policies/{id}` | detail | |
| /minds | MindsPage.tsx | Refine All | button | `POST /souls/refine-all` | refresh | founder-gated |
| /minds | MindsPage.tsx | Soul card | link | navigate | /minds/{slug} | |
| /minds/{slug} | MindDetailPage.tsx | Approve / Reject proposal | buttons | `POST /souls/proposals/{id}/{approve|reject}` | row update | TICKET-DEPT-MINDS-01 |
| /minds/{slug} | MindDetailPage.tsx | Refine soul | button | `POST /souls/{slug}/refine` | refresh | |
| /company-mode | CompanyModePage.tsx | Activate / Config | button+form | `POST /company-mode/activate`, `POST /company-mode/config` | persist | founder-gated |
| /skills | SkillsPage.tsx | Skill list / detail | display+link | `GET /skills`, `GET /skills/{id}` | detail | |
| /tasks | TasksPage.tsx | Status filter | select | `GET /execution/tasks?status=...` | bookmarkable URL | |
| /tasks | TasksPage.tsx | Run / Pause / Delete / History | buttons | `POST /execution/tasks/{id}/run`, `PATCH /execution/tasks/{id}`, `DELETE`, `GET /execution/tasks/{id}/history` | row update / view | |
| /workstreams | WorkstreamsPage.tsx | Create | button | `POST /execution/workstreams` | /workstreams/{id} | |
| /workstreams | WorkstreamsPage.tsx | Card | link | navigate | /workstreams/{id} | |
| /workstreams/{id} | (detail page) | Redirect | button | `POST /execution/workstreams/{id}/redirect` | mid-flight redirect | |
| /opportunities | OpportunityInboxPage.tsx | Discovery banner / list | display | `GET /opportunities`, `GET /connections/google-activation-summary` | inline blockers | Sprint-20 PR-1+PR-3 |
| /opportunities | OpportunityInboxPage.tsx | Create workstream | button | `POST /opportunities/{id}/create-workstream` | inline state | Sprint-20 PR-3 |
| /opportunities | OpportunityInboxPage.tsx | Send-rate chip | display | `GET /opportunities/send-rate-limit` | inline | Sprint-20 PR-4 |
| /connections | ConnectionsPage.tsx | Brain tab: Runtime/Provider | selects | `PUT /connections/runtime`, `PUT /connections/provider` | persist | V2 (3-tab) layout |
| /connections | ConnectionsPage.tsx | Plugins tab: Card / Install / Setup guide | clickable+buttons | `GET /connections/plugins/{id}`, `POST /connections/plugins/{id}/install` | drawer / external | discovery is opt-in, not auto-install |
| /connections | ConnectionsPage.tsx | Advanced tab: Show advanced toggle / Discovery refresh / V1 registry | toggle+button+display | localStorage / `POST /connections/discover`, `GET /connections/v1-registry` | tab vis / refresh | legacy V1 opt-in |
| /account | AccountPage.tsx | Profile / Avatar | inputs+file | `PUT /account/profile`, `PUT /account/avatar` | persist | |
| /account/{cat} | AccountPage.tsx | Category nav | link | navigate | /account/{cat} | org details, prefs |
| /files | FilesPage.tsx | Upload / List / Download | file+display+link | `POST /files`, `GET /files`, `GET /files/{id}/download` | row / download | |
| /analytics | AnalyticsPage.tsx | Dashboard / Date range | display+filter | `GET /analytics?from=&to=` | refresh | |
| /settings | SettingsPage.tsx | Tab nav (7 normal: General/Memory/Privacy/Notifications/Voice/Billing/About) | tabs | local routes | route change | normal-mode |
| /settings | SettingsPage.tsx | Show advanced toggle | checkbox | localStorage `daena.settings.show_advanced` | reveal 6 advanced tabs | auto-flips ON via direct nav |
| /settings/llm | SettingsLLM.tsx | Provider select | select | `PUT /settings/llm-provider` | persist | advanced |
| /settings/governance | SettingsGovernance.tsx | Config form | form | `POST /settings/governance` | persist | founder-gated, advanced |
| /settings/models | SettingsModelsRuntimes.tsx | Models config | form | `POST /settings/models` | persist | advanced |
| /settings/heartbeat | SettingsHeartbeat.tsx | Heartbeat config | form | `POST /settings/heartbeat` | persist | advanced |

## Sidebar Navigation (23 items, 6 groups)

| Group | Item | Route | Notes |
|---|---|---|---|
| Core | Chat | /chat | live polling: approvals badge |
| Core | Dashboard | /dashboard | static |
| Core | Scan | /scan | static |
| Intelligence | Departments | /departments | live status (5s) |
| Intelligence | Minds | /minds | static |
| Intelligence | Company Mode | /company-mode | founder-gated lock |
| Intelligence | Files | /files | static |
| Intelligence | Analytics | /analytics | static |
| Intelligence | Skills | /skills | static |
| Go-to-Market | Opportunities | /opportunities | static |
| Go-to-Market | Projects | /projects | static |
| Go-to-Market | Pipeline | /pipeline | static |
| Go-to-Market | Workstreams | /workstreams | static |
| Execution | Tasks | /tasks | live polling: tasks badge |
| Execution | Engagement Console | /engagements | redirects to /scan (sidebar removed 2026-04-21) |
| Connections | Connections | /connections | dedicated page |
| Governance | Policies | /policies | static |
| Governance | Approvals | /governance/approvals | live polling: badge |
| Governance | Audit | /governance/audit | static |
| Governance | Trust | /governance/trust | founder-gated |
| Footer | User avatar dropdown | /account, /settings, /connections | sign out |
| Footer | Org row | /account/org/details | |

## Live Polling Behavior

- **Sidebar badges** (30s, exponential backoff): pending approvals + RUNNING/PENDING tasks, parallel.
- **Department status** (5s): `/department-states`.
- **Scan job status**: exponential backoff until complete, auto-navigate to report.

## Suspected "Coming Soon" / Dead Stubs (full list in PR-3 reclassification target set)

| File:line | Feature | Status |
|---|---|---|
| SettingsDeveloper.tsx:108 | API token management | "coming soon" badge |
| SettingsDeveloper.tsx:160 | Webhook setup | "coming soon" badge |
| SettingsDeveloper.tsx:173 | Event subscriptions | "coming soon" badge |
| SettingsNotifications.tsx:233 | Sound notification | "coming soon" badge |
| SettingsNotifications.tsx:233 | Email digest | "coming soon" badge |
| SettingsNotifications.tsx:233 | Daily digest | "coming soon" badge |
| SettingsPrivacy.tsx:154 | Cloud sync (encrypted) | "coming soon" badge |
| SettingsPrivacy.tsx:175 | Data retention | "coming soon" badge |
| SettingsPrivacy.tsx:189 | Anonymous mode | "coming soon" badge |
| MarketplaceCard.tsx:161 | Skill bundles | "coming soon" badge (Phase 2) |
| PluginDetailDrawer.tsx:200 | Skill bundles in drawer | "coming soon" badge (Phase 2) |

## Architectural Notes (2026)

1. **Department Unification (2026-04-17):** /company, /inbox, /crm, /voice all redirect to /departments. Old CompanyDashboard + DepartmentInbox deleted.
2. **Settings restructure (2026-05-02):** 7 normal tabs always visible; 6 advanced tabs (LLM, Governance, Models, Heartbeat, Developer, Shortcuts) gated behind toggle; toggle persists to localStorage and auto-enables on direct navigation.
3. **Connections V2 (2026-05-02):** 9 specialized tabs collapsed into 3 (Brain, Plugins, Advanced). "Connected" requires `callable=true`; "Install" replaced with "Setup guide" — no auto-install on discovery.
4. **Error handling rewrite (2026-04-29):** all errors logged via `useErrorStore`. Polling endpoints (/department-states, /governance/approvals, /execution/tasks) silenced by default; per-call `silent` override available.
5. **Phase 3 approval modal:** custom dark-slate UI rendered inside GovernanceApprovalsPage, not OS chrome.
6. **Engagements (2026-04-21):** /engagements page route preserved for bookmarks; sidebar entry removed; redirects to /scan.

## Inventory verdict

The frontend has more reach than the backend has wiring in only a handful of places — mainly the three Settings groups (Developer, Notifications, Privacy) and the Skill Bundles Phase-2 surface in Plugins/Marketplace. The real loop pages (Opportunities, Workstreams, Approvals, Audit, Trust, Connections, Tasks) are wired end-to-end against existing backend endpoints. The next two PRs (PR-2 OpenAPI diff, PR-3 reclassification) will surface any silent endpoint mismatches and either wire or relabel the stubs.
