# Phase 9 — Review Pack (Sanitized)

**Date:** 2026-05-01
**Audience:** Codex CLI / Gemini CLI / Perplexity (and any human reviewer)
**Sanitization:** No secrets, no environment values, no tokens, no API keys, no private endpoints, no Cloud Run env. Only audit findings + sanitized code references (file paths + line numbers + function shapes).

---

## 0. What Daena is (one paragraph)

Daena is a governed multi-agent LLM orchestration platform: 10 departments × 6 capabilities each (MIND/EYES/HANDS/VOICE/SHIELD/MEMORY), a 10-stage chat pipeline with always-on Shield governance, three reasoning modes (Standard / Council / Quintessence + 15 DCP experts), three action modes (CMD / EXE), three governance modes (UNLEASHED / BALANCED / GOVERNED), 5-tier NBMF memory, multi-runtime (Claude Code / Codex / Gemini CLI / Grok / Ollama / vLLM). Backend: FastAPI + SQLAlchemy 2.0 async + Postgres (prod) / SQLite (dev). Frontend: React 19 + TypeScript + Vite 7 + Tailwind 4 + Zustand. ~26 protected routes, ~67 page components.

---

## 1. Audit method (already done)

- **Phase 9A (Tooling readiness)** — 5/6 probes green: Playwright MCP ✓, project E2E config ✓, trace recording ✓, OpenAPI schema ✓, Schemathesis ✗ (deferred), hand-written axios kept (recommend types-only generation).
- **Phase 9B (UI Action Contract Matrix)** — 158 actions audited across 12 route clusters via 6 parallel Explore-agent passes.
- **Phase 9C (Live Playwright traces)** — 5 of 10 flows run live; 5 carried forward from static evidence.
- **Phase 9D (OpenAPI contract diff)** — live `openapi.json` (396 ops) diffed against 218 frontend call sites.

---

## 2. Headline status (what we are about to repair)

### 2.1. Three UNSAFE actions (P0 — block before any user-facing demo)

| # | Action | Location | Smoking gun | Risk |
|---|---|---|---|---|
| U1 | **Company Mode: Activate Daena** | `frontend/src/pages/CompanyModePage.tsx:272-308` | UI form lets the founder set `auto_send=true` AND `require_founder_approval=false` simultaneously. Backend `POST /api/v1/company-mode/activate` honors both flags as set; no UI guard prevents the contradiction. | External email/LinkedIn/SMS sent without an approval gate. |
| U2 | **Scan: Start Scan** (REST boundary) | `backend/app/api/v1/security_dashboard.py:488-523` | Endpoint accepts `target` and dispatches to `scan_workflow.py:545-578` without first calling `target_matches_scope()`. **CONFIRMED LIVE in Phase 9C:** posting `{target: "out-of-scope-target.example.com", tier: "SCOUT"}` returned HTTP 200 + `status: queued` + a `job_id`. | Unauthorized scan against any target. Authorized-scope mechanism exists but is bypassable at the REST boundary. |
| U3 | **Engagements: Start Governed Engagement** | `backend/app/api/v1/engagements.py:55-133` | Delegates target validation to `SecurityOperationsAgent.start_engagement()`. Whether scope check fires there is **unverified** (HANDS-OFF list — audit only). | Same shape as U2 if the agent doesn't enforce. |

### 2.2. Settings persistence: 34 of 47 (72%) don't persist to backend

**Pattern (one architectural failure repeated 25 times):** UI calls `persistUiPref(...)` which writes to `localStorage` instead of `PUT /api/v1/settings/user`. **CONFIRMED LIVE in Phase 9C** for the highest-impact case: clicking "Governed" mode in `/settings/governance` produced **zero network calls** and only `localStorage['daena:governanceMode'] = 'GOVERNED'`.

Most damaging FAKE settings (founder thinks they configured something the backend never sees):

- **Governance Mode** (UNLEASHED/BALANCED/GOVERNED) — `frontend/src/pages/settings/SettingsGovernance.tsx:66-80`. Backend pipeline keeps old posture.
- **Cost-Aware Routing** + **Local-First Routing** — `SettingsLLM.tsx:204,211`. ModelRouter never reads.
- **Monthly Budget / Alert Threshold / Over-Budget Action** — `SettingsBilling.tsx:376-417`. Cost-tracker doesn't enforce.
- **All 8 notification toggles** (desktop, task, budget, heartbeat, gov-reject, runtime-disconnect, sound, email) — `SettingsNotifications.tsx`. Backend can't possibly know what to send.
- **Default Chat Mode (CMD/EXE)** + **Default Routing (STD/QE)** — `SettingsGeneral.tsx:99-133`.
- 9 more heartbeat / privacy / developer toggles in the same pattern.

The other 9 settings issues are heartbeat-daemon-memory only (config persists for the daemon's process lifetime; restart wipes).

### 2.3. Other punch-list items

- **PARTIAL — Session CRUD audit silence**: rename / archive / un-archive / batch-archive on `chat_sessions` write to DB cleanly but emit zero audit rows. Same gap on tasks and files.
- **PARTIAL — Policy Delete is hard-delete**: `DELETE /api/v1/policies/{id}` removes the row. Per audit-record-protection semantics, policies are audit-adjacent and should be soft-archive only.
- **PARTIAL — Scan report findability**: no "report ready" notification when an in-flight scan completes. Lose the page-state and you must hunt the History list.
- **BROKEN — Re-run Scan**: handler exists at `frontend/src/pages/ScanPage.tsx:212-234` (`rerunScan`); no UI button calls it. Backend `POST /api/v1/security/scans/{id}/rerun` is ready but unreachable.
- **FAKE — Remove Attached File** (chat): `frontend/src/components/chat/ChatInput.tsx:623`. X removes UI chip; file blob + `file_records` row remain on disk. No `DELETE /files/{id}` wired from this surface.
- **3 V1↔V2 duplicate surfaces** in Connections (Runtime Selection / Plugin Install / MCP Servers List).
- **Empty Connections V2** for fresh tenants: `GET /api/v1/connections/v2` returns 0 rows for a brand-new founder; V1 returns 6 runtimes for the same tenant. Surface looks broken to first-time users (CONFIRMED LIVE in 9C).

### 2.4. OpenAPI contract diff (4 real ghost calls)

| # | UI call | UI source | Spec reality |
|---|---|---|---|
| G1 | `DELETE /api/v1/company-mode/seed-brief` | `CompanyModePage.tsx:235` | Spec has GET + POST only → 405 |
| G2 | `GET /api/v1/projects/{id}/files` | `ProjectDetailPage.tsx:99` | Spec has `/projects/{id}` only (no `/files` sub-resource) → 404 |
| G3 | `GET /api/v1/projects/{id}/tasks` | `ProjectDetailPage.tsx:89` | Same as G2 → 404 |
| G4 | `GET /api/v1/runtimes/subscriptions` | `SettingsLLM.tsx:46` | Not in spec → 404 |

Plus 247 unused spec ops (≈85% intentional surface-broader-than-UI; ≈15% real UI-surface gaps worth investigating).

### 2.5. Audit-event coverage gaps (Rule-17 violation pattern)

Backend writes the row, but emits no audit event. This is fixable with a single audit-emit helper called from the relevant route handlers. Affected:

- Chat session: rename, archive, un-archive, batch-archive, batch-delete
- Chat: file attach, file remove (and remove is FAKE anyway)
- Chat: export session JSON
- Tasks: create, run, batch-run, retry, cancel, batch-archive, batch-delete
- Connections > Main Brain: primary-runtime change has WARNING-log only, not formal AuditLog row
- Settings: every save (explicit `PUT /settings/user` + the 25 FAKE ones)

---

## 3. Proposed repair plan (Phase 10)

The plan is to ship five small commits, each independently revertable. Implementation by Claude (only tool allowed to edit code per founder rules). Codex/Gemini/Perplexity are reviewers only.

### Commit 1 — `phase10: fix unsafe action gates`

**Backend:**
1. `backend/app/api/v1/security_dashboard.py:488-523` (start_scan handler):
   - Inject `target_matches_scope()` from `app.services.security.yellow_runtime_gate` BEFORE `_create_scan_job()`.
   - Reject with HTTP 403 + body `{detail: "target_not_in_scope", target, hint: "add to /security/scope"}` when `is_v2_enabled` AND target is out-of-scope.
   - Founder role still able to bypass (matches existing `experimental_override` pattern in runtimes.py); audit-log the bypass.

2. `backend/app/api/v1/engagements.py:55-133` (start_engagement handler):
   - Verify or add equivalent scope check before job dispatch. The audit found it's *unverified*; if it exists deeper in the agent, surface it with a comment + assertion at the route layer for visibility.

3. `frontend/src/pages/CompanyModePage.tsx`:
   - In the form-state, derive `auto_send_disabled = !require_founder_approval` (or vice versa).
   - Disable the `auto_send` checkbox when `require_founder_approval=false`. Add helper text: "Auto-send requires founder approval to remain enabled."
   - Backend `app/api/v1/company_mode.py` activate handler: server-side guard returning 422 if both `auto_send=true` and `require_founder_approval=false` (defense-in-depth so non-UI clients can't bypass).

**Tests:**
- `backend/tests/test_security_scan_scope_gate.py` (new): out-of-scope target → 403; in-scope → 200.
- `backend/tests/test_company_mode_autosend_guard.py` (new): both flags contradictory → 422.
- `frontend/e2e/cmpny-mode-autosend.spec.ts` (new): toggle interaction enforces the rule in the UI.

### Commit 2 — `phase10: persist high-impact settings to backend`

**Backend:** confirm `users.settings` JSONB has space for the new keys (it does — already used by working settings). No new tables.

**Frontend:** swap `persistUiPref(key, value)` for `useSettingsPersist(key, value)` (new hook) which:
- Locally `setState` for instant UI feedback.
- Debounces (500 ms) and `PUT /api/v1/settings/user` with `{settings: {...current, [key]: value}}`.
- On 4xx/5xx, rolls back the local state and surfaces an error.
- On mount, reads the value from a `GET /api/v1/settings/user` cache (already populated by `uiStore`), falling back to localStorage as a *display* default only — not as source-of-truth.

**Settings to migrate (priority order):**
1. Governance Mode (highest impact)
2. Local-First Routing + Cost-Aware Routing
3. Default Chat Mode (CMD/EXE)
4. Default Routing (STD/QE)
5. Notification toggles (8)
6. Privacy toggles (4)
7. Budget settings (3)

**Heartbeat config persistence (separate fix):** Daemon should read its own config from a new `heartbeat_config` table on init, not from in-memory defaults. Settings PATCH writes the row; daemon reads on boot. Otherwise heartbeat settings revert on restart.

**Tests:**
- `backend/tests/test_settings_persistence.py` (extend): per-key roundtrip.
- `frontend/e2e/settings-persistence.spec.ts` (new): change governance mode → reload page → value persists.

### Commit 3 — `phase10: repair scan report and rerun flows`

1. `frontend/src/pages/scan/ScanList.tsx`: add the missing Re-run button (handler already exists in ScanPage.tsx:212).
2. `frontend/src/pages/ScanPage.tsx`: add a `useEffect` hook that fires a toast + plays the optional notification sound when an `activeJobs` entry transitions from in-flight to `complete`. Toast deep-links to `/scan?job=<id>` which auto-loads the report.
3. `frontend/src/pages/scan/ScanList.tsx`: add a "Show archived" toggle (pure client-side; backend already supports `?include_archived=true`).
4. `backend/app/api/v1/security_dashboard.py:list_scans`: ensure `include_archived` query param is documented in OpenAPI.

**Tests:** Playwright E2E for "start → wait → complete → notification → click → report".

### Commit 4 — `phase10: chat file removal semantics + session/task/file audit events`

1. **File removal options (pick one — open question for review):**
   - **Option A (honest delete):** wire X-button to `DELETE /api/v1/files/{id}`. Cost: file is gone from chat history view.
   - **Option B (relabel):** keep current behavior; change tooltip + add `(file remains in /files)` micro-text. Cost: founder still has to clean up `/files` separately.
   - **Option C (hybrid, recommended):** X removes from the chat input draft only (current behavior, matrix-FAKE only because the surface implies deletion); add a separate "Detach + delete" menu item that calls `DELETE`.

2. **Audit emit helper** `app/services/audit/emit.py`:
   ```python
   async def emit_route_audit(action: str, *, actor_id, tenant_id, target=None, metadata=None) -> None: ...
   ```
   Apply at the chat session PATCH handler, the file delete handler, the task PATCH/DELETE handlers, and the session export handler.

3. Format: `{action: "chat_session.archived", actor_id, tenant_id, target_id, metadata: {prev_state, next_state}}`.

**Tests:** unit tests on the emit helper; route-level tests asserting an `AuditLog` row appears after each mutation.

### Commit 5 — `docs: phase10 verification report`

`docs/Ultraview/PHASE_10_PRODUCT_INTEGRATION_VERIFICATION.md` covering: what is now verified working / what remains fake-dead-unknown / top remaining UX pain / whether Daena is local product-ready / whether daena-v2 cloud demo is safe to show / exact next actions.

---

## 4. Open questions for reviewers

### For Codex (architecture / regression / tests):

1. The 25 FAKE settings all use `persistUiPref(...)`. The proposed `useSettingsPersist` hook is one architectural fix repeated 25× via codemod. Is there a *better* shape (e.g. a Zustand `settingsStore` slice that auto-persists on change)? If so, what's the regression risk of replacing `persistUiPref` everywhere in one commit vs incremental?
2. The U2 fix (REST scope gate) sits in front of the existing scope check in `scan_workflow.py:545-578`. What's the cleanest way to *avoid duplication* — call into `target_matches_scope()` from both layers, or hoist the check into a shared FastAPI dependency?
3. The U3 (engagements) gate is HANDS-OFF unless we have to touch it. If `SecurityOperationsAgent.start_engagement` already enforces scope, how do we *prove* it without modifying the agent?
4. Suggested *minimum* tests for each commit. We currently have 2/158 actions under Playwright coverage. Where should the test budget go first?

### For Gemini (UX / product flow):

1. After clicking Install (a connector), what does the user expect to see? Today: a status badge transition. Is that enough, or should there be a guided "next step" (probe / configure)?
2. After running a Scan, what's the *minimum viable* "report ready" UX? Notification dot? Toast? Inline banner that doesn't dismiss until clicked?
3. Archive vs Delete: in the matrix, several flows hard-delete (tasks, files) and several should soft-archive but currently hard-delete (policies). What's the right *UI* surface for "this is going forever vs. this can be unarchived"? A different button color? A different confirm dialog? Or a single concept ("Archive"; never "Delete" in the UI)?
4. After a Save Settings click, what does a user expect? A toast? A green check? Just no-error? Today some surface a toast, some show inline "Saved" badge, some show nothing. Pick one.
5. Simplest UI state model for a multi-step mutation (e.g. install → probe → configure → enable). Today this is per-component. What's the canonical shape?

### For Perplexity (public best-practices research):

Cite public sources for:

1. Best practices for **agent-dashboard action semantics** in modern observability/ops tools (Linear, Vercel, GitHub Actions, Anthropic Console). What's their pattern for "this action sent vs. drafted vs. queued"?
2. **Approval gates** in security workflows — what does AWS Console / Vault / Bitwarden / 1Password do for "this action requires escalated permission"? What's the minimum viable approval surface?
3. **Security scan report UX** — Snyk, Dependabot, Tenable, Burp Suite. Where do reports go after a scan completes, and how does the user find them?
4. **Settings persistence patterns** — when is localStorage acceptable vs. when must it round-trip? How does Linear / Notion / Figma handle "default new-doc settings"?

---

## 5. What is OFF-LIMITS for this review

- No secrets, env values, tokens, API keys, or private endpoints are shared in this pack.
- No production Cloud Run env or DB binding details.
- No `vault.py` / `oauth_credentials_store.py` / vault internals shared.
- No client-credential discussion.
- No request to *implement* the fixes — only review. Claude (current AI) is the only tool authorized to edit code per founder rules.

---

## 6. References (for cross-checking)

All under `docs/Ultraview/`:
- `PHASE_9_TOOLING_READINESS.md` (9A)
- `UI_ACTION_CONTRACT_MATRIX.md` (9B — full 158-action matrix)
- `PHASE_9C_PLAYWRIGHT_TRACE_REPORT.md` (9C — live)
- `PHASE_9D_OPENAPI_CONTRACT_REPORT.md` (9D)
- `FRONTEND_BACKEND_TRUTH_MATRIX.md` (route-level companion)
- `API_CONTRACT_REALITY.md` (known route gaps, dated 2026-04-29)
- `DUPLICATES_DEAD_FILES_UNWIRED_REPORT.md` (known dead surfaces, dated 2026-04-29)
- `DAENA_DATABASE_READINESS_PLAN.md` (DB readiness, dated 2026-05-01)
- `CLEAN_GCLOUD_REBUILD_CORS_FIX_REPORT.md` (cloud cutover, dated 2026-05-01)

End of pack.
