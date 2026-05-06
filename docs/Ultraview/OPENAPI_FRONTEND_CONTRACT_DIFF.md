# OpenAPI to Frontend Contract Diff

**Date:** 2026-05-06
**Sprint:** DAENA-SPRINT-21-UI-BACKEND-WIRING-CLOSURE — PR-2
**Source:** `/openapi.json` from local backend (commit a852c03) vs grep of `frontend/src/**/*.{ts,tsx}` API paths.

## Counts

- **492** total OpenAPI operations across **76** tag groups
- **60+** path prefix groups under `/api/v1/...`
- **~75** distinct path prefixes referenced from the frontend

## Bucket A — WIRED (frontend regularly calls these)

These are part of the operator-visible loop and have been confirmed reachable from the UI in PR-1 inventory.

| Path prefix | UI surface(s) |
|---|---|
| `/auth/*` | Login / Register / Refresh / OAuth callbacks |
| `/health`, `/health/detailed` | navbar `ConnectionStatusIndicator`, BackendOfflineBanner |
| `/chat/*` | ChatPage, model-registry, sessions |
| `/agents/*` | DepartmentsPage, DepartmentChatPage |
| `/department-states`, `/department-messages`, `/department-policies`, `/department-budget` | departments live status + policy/budget panels |
| `/governance/approvals*`, `/governance/audit`, `/governance/trust` | Governance pages, sidebar badge, approval drawer |
| `/execution/tasks*` | TasksPage + sidebar badge |
| `/workstreams/*` | WorkstreamsPage |
| `/opportunities/*` | OpportunityInboxPage (Sprint-20) — incl. `create-workstream`, `send-rate-limit` |
| `/connections/*`, `/connections/google-*`, `/connectors/*` | ConnectionsPage v2 (Brain / Plugins / Advanced) |
| `/runtimes/*`, `/runtime/*`, `/dynamic-models/*` | RuntimeSwapper, BrainReadinessPanel, SettingsModelsRuntimes |
| `/settings/*` | SettingsPage tabs, uiStore prefs |
| `/account/*`, `/account/provider-keys`, `/account/oauth-clients` | AccountPage subroutes |
| `/billing/*` | SettingsBilling |
| `/policies/*` | PoliciesPage |
| `/souls/*` | MindsPage / MindDetailPage |
| `/heartbeat/*` | SettingsHeartbeat + AutonomyMissionControl |
| `/memory/*` | SettingsMemory |
| `/files/*` | FilesPage |
| `/projects/*` | ProjectsPage / ProjectDetailPage |
| `/skills/*` | SkillsPage |
| `/research/drafts` | (drafts surface — see PR-5 cycle) |
| `/form-drafts/*` | (form drafts — see PR-5 cycle) |
| `/security/*`, `/security/authorized-scope`, `/security/scan*`, `/security/mode/*` | ScanPage / Walkthrough, SecurityScopePage, SecurityDashboardPage |
| `/company-mode/*` | CompanyModePage |
| `/daenabot/agents` | daenabotStore |
| `/analytics/dashboard` | AnalyticsPage |
| `/notifications/*` | navbar notifications |
| `/prompts/*` | agent-to-user interactive prompts |
| `/integrations/*` | connections marketplace |
| `/api-keys/*` | account API keys |

## Bucket B — BACKEND-ONLY INTERNAL (not UI-bound, intentional)

These are infra/auth/system probes or AI-internal endpoints. Should NOT be wired to operator UI.

| Path prefix | Purpose |
|---|---|
| `/auth/oauth/callback`, `/auth/oauth/start` | OAuth dance (browser-only redirect targets) |
| `/bridge/token` | Cross-runtime bridge token mint (CLI consumer) |
| `/system/*` (8 ops) | startup health, env truth, telemetry probes |
| `/system-self-diagnostic/*` (6 ops) | self-diagnostic background |
| `/runtime-truth/*` (7 ops) | runtime truth telemetry consumed by BrainReadinessPanel only |
| `/mobile/*` (7 ops) | mobile companion (no current UI) |
| `/marketing/*` (1) | landing-page form intake |
| `/scrape/*` (1) | back-end-only opportunity adapter |
| `/waitlist/*` (2) | landing-page waitlist intake |
| `/tts/*` (3) | voice synthesis (Voice provider in browser only) |
| `/health` (no /api/v1 prefix) | LB probe |
| `/system-autonomy/*` | autonomy missions internal consumer |
| `/controlled-execution/*` (2) | dispatcher internal (Sprint-19) |
| `/business/chat` | VP business chat (consumer is ChatPage, not separate page) |
| `/vp-commands/*` (1) | dispatcher only |
| `/trust-chat/*` (1) | trust chat helper, used by GovernanceTrustPage |

## Bucket C — BACKEND EXISTS, UI SHOULD WIRE (Sprint-21 candidates)

These paths exist on the backend but are not surfaced or are surfaced shallowly. Each is a candidate for closure in PR-3..PR-6.

| Path prefix | Why it matters | Sprint-21 PR |
|---|---|---|
| `/missions/*` (16 ops) | AutonomyMissionControl uses some, but full mission list / cancel / debug is unsurfaced | PR-5 |
| `/skill-refinery/*` (15 ops) | Skill Refinery Phase 1+2 is wired internally; UI status panel limited | PR-6 |
| `/benchmark/*` (15 ops) | model/runtime benchmark suite — surfaced only inside dev tools | (roadmap-only) |
| `/security-dashboard/*` (22 ops) | SecurityDashboardPage shows a slice; many sub-views like trust-tier history, kill-switch state, source-correlator runs are not surfaced | (roadmap-only or partial) |
| `/connections-v2-*` namespace (9 ops across governance / skills / consent) | partially wired in Connections v2, but skill-consent and skill-bundle endpoints sit behind a Phase-2 placeholder | PR-3 + PR-6 |
| `/connector-install/*`, `/connector-oauth/*` (10 ops) | new ConnectorInstallDialog uses a slice; setup-blocker UX should make the full lifecycle reachable | PR-6 |
| `/department-policies/*`, `/department-budget/*` (9 ops) | DepartmentDetail shows them but mutate paths underused | PR-5 |
| `/founder/*` (5 ops) | founder-private surfaces (audit, telemetry); GovernanceTrustPage covers a slice | (founder-only, intentional) |
| `/self-improvement/*` (8 ops) | self-improvement proposals; only sidebar surfaces them through morning-readiness | PR-5 (existing) |
| `/dynamic-models/*` (4 ops) | hot-add API keys + model probe; surfaced in SettingsModelsRuntimes but only partially | PR-6 |
| `/connections-google-setup/*` (3 ops) | Google setup guide page covers the happy path; missing UX for "client misconfigured" follow-up | PR-3/PR-6 |
| `/sales/*`, `/crm/*` (3+4 ops) | CRM mini-loop in DepartmentChatPage; full list/CRUD UI not built | (roadmap-only) |
| `/engagements/*` (5 ops) | route preserved, page redirects to /scan; data unused | (legacy, fine to leave) |
| `/notifications/*` (2 ops) | navbar surfaces them; no settings page beyond "coming soon" | PR-3 |
| `/api-keys/*` (3 ops) | covered by AccountProviderKeys; the parallel `/account/provider-keys` is the canonical one | (duplicate-ish — note for cleanup) |

## Bucket D — UI LABELS AHEAD OF BACKEND (relabel or remove)

These are the only items where the frontend appears to advertise something that has no real backend wiring:

| Place | Label | Backend status | Resolution |
|---|---|---|---|
| `SettingsDeveloper.tsx:108,160,173` | API tokens / Webhooks / Event subscriptions | no endpoints exist | **PR-3:** show "Roadmap only" or hide from Settings; do not pretend it's a config |
| `SettingsNotifications.tsx:233` | Sound, Email digest, Daily digest | no backend persistence; only `/notifications` for fetch | **PR-3:** mark as roadmap, keep sound (browser-side) toggle if local-only |
| `SettingsPrivacy.tsx:154,175,189` | Cloud sync, Data retention, Anonymous mode | no endpoints | **PR-3:** roadmap-only; do not show toggles that don't persist |
| `MarketplaceCard.tsx:161`, `PluginDetailDrawer.tsx:200` | Skill bundles | `/connections-v2-skills` exists but bundles are Phase 2 | **PR-3 / PR-6:** roadmap label, keep card |

## Bucket E — DUPLICATES FLAGGED FOR LATER

Not blocking Sprint-21, but to record:

- `/api-keys/*` (3 ops) and `/account/provider-keys/*` (3 ops) overlap — only the second is consumed by UI.
- `/connections/*` (27 ops, "v1") and `/connections-v2-*` (27 ops, "v2") run in parallel; the Connections page V2 is canonical, V1 is opt-in via Advanced toggle. Acceptable for the duration of this sprint; to converge later.
- `/runtime/*` (7 ops) and `/runtimes/*` (8 ops) both addressed — conscious split: `/runtimes` is registry, `/runtime` is single-runtime ops. OK.
- `/system/*` (8 ops) and `/system-self-diagnostic/*` (6 ops) overlap on identity / probe — acceptable, one is meta, the other is health.

## Verdict

The backend has more capability than the UI surfaces by design. The only true contract gap (UI ahead of backend) is the three Settings groups in Bucket D (Developer / Notifications / Privacy) and the Skill Bundles Phase-2 placeholders. Those are PR-3's exact target. Every other UI surface either calls real endpoints or is a deliberate dev/roadmap gate.

PR-3 will:
1. Replace each Bucket-D coming-soon block with either a real wiring (where backend exists), a precise "roadmap-only — see X" label, or move it behind the dev/advanced toggle.
2. Verify that any "online" / "connected" / "ready" pill in Connections / Runtime panels is backed by a probe, not a static default.
3. Add source-grep tests so we do not regress (no `disabled` static-true on a labeled action without a paired blocker reason).
