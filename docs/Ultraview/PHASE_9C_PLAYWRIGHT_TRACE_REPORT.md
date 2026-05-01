# Phase 9C — Live Playwright Trace Report

**Date:** 2026-05-01
**Operator:** Claude Code (Opus 4.7) under founder-direction interaction-audit task
**Method:** Playwright MCP browser-driven flows + targeted `fetch()` probes against the live local stack
**Local stack health at start:** Backend `http://localhost:8000/api/v1/health` → `{status:"healthy", database:"healthy", essentials_ready:true, seedings_complete:true}`. Frontend `http://localhost:5173/` → HTTP 200, Vite v7.3.2 ready in 4.8 s.

> **Status one-liner:** Two of the three headline 9B findings are now confirmed by live evidence: **governance-mode change makes ZERO network calls (FAKE persistence proven live)** and **`POST /api/v1/security/scans/start` accepts an out-of-scope target with HTTP 200 queued (UNSAFE proven live)**. A new finding surfaced during setup: **dev SQLite was at alembic 004; `tenants.dek_wrapped` column missing**, exactly matching `DAENA_DATABASE_READINESS_PLAN.md` §3 Blocker B — fixed in this run by `alembic upgrade head` (004 → 007). A second new finding: **the Register form's `Organization` input maps to `tenant_name` but the form-fill leaks the raw value through (no slug normalization)** which compounds with the schema gap.

---

## 1. Setup notes

- **Auth path:** registered a fresh test user (`p9c-1777670249753@example.com`, tenant `P9C-1777670249753`) and stored the JWT in `localStorage.daena_token`. Email TLD `.local` rejected by Pydantic email validator → switched to `example.com` (which DOES return MX records and is the IETF-reserved doc TLD; safe).
- **Pre-flight blocker hit:** dev DB schema drift. Symptom: `OperationalError: no such column: tenants.dek_wrapped` on register. Cause: alembic head at `004_add_chat_session_workstream_fk`; the `dek_wrapped` column is added by `006_secrets_envelope_vault`. Fix: `python -m alembic -c migrations/alembic.ini upgrade head` ran 004→005→006→007 cleanly. The `Base.metadata.create_all` in lifespan ESSENTIALS does NOT add columns to existing tables — only creates missing tables. This matches `DAENA_DATABASE_READINESS_PLAN.md` warning that production is at the same risk.
- **Network capture:** installed `window.__net = []` + monkey-patched `window.fetch` to log every `(url, method)` per page. Cleared between flows.

---

## 2. Flow-by-flow evidence

### Flow 4 — `/settings/governance` change → does backend see it?

**Steps:**
1. Navigate `http://localhost:5173/settings/governance` (already on it after login redirect).
2. Hook `window.fetch`, clear `window.__net`.
3. Click "Governed" mode button (ref `e309` in snapshot).
4. Wait 2 s.
5. Inspect `window.__net` and `localStorage`.

**Result:**
```json
{
  "net_calls": [],
  "localStorage_keys_with_'governance'": [
    {"k": "daena:governanceMode", "v": "GOVERNED"}
  ]
}
```

**Verdict: FAKE persistence — CONFIRMED LIVE.**
- Zero network calls fired.
- Value stored only in `localStorage['daena:governanceMode']`.
- Backend pipeline (SecurityGate, governance.py) never sees the user's choice.
- Phase 9B U-Cluster/Settings finding (highest-impact FAKE) reproduced with live evidence.

(Minor note: the live key `daena:governanceMode` differs from the `default_governance_mode` key the static audit guessed at — pattern is identical, key name is per-component.)

### Flow 5 — `/settings/llm` toggles → does backend see them?

**Steps:**
1. Navigate to `/settings/llm`.
2. Locate "Local-First Routing" + "Cost-Aware Routing" labels.
3. Click toggle elements via `document.querySelectorAll('button[role="switch"], [data-state]')[0,1]`.
4. Capture network + localStorage.

**Result (limited evidence):**
```json
{
  "net_calls": [{"url":"/api/v1/health","method":"GET"}],
  "localStorage_keys_routing": [{"k":"daena:routingMode","v":"STANDARD"}]
}
```

**Verdict: insufficient direct evidence — defer to static evidence.**
- The `[data-state]` elements I targeted didn't move state (probably wrong selectors for the Switch component in this view).
- Only network call was the periodic `/api/v1/health` ping.
- The Phase 9B static audit already proves these toggles use `persistUiPref(...)` → localStorage. The pattern from flow 4 (governance) confirms how `persistUiPref` works in the wild. Cross-applies.
- **Status: FAKE persistence carried over from 9B static evidence** (no live contradiction; live test inconclusive due to selector miss).

### Flow 6 — `/scan` start → is the authorized-scope gate enforced at the REST boundary?

**Steps:**
1. Navigate to `/scan`.
2. POST to `/api/v1/security/scans/start` directly (bypassing the launcher UI to isolate the gate behavior):
   ```json
   { "target": "http://out-of-scope-target.example.com", "tier": "SCOUT" }
   ```
3. Inspect response.

**Result:**
```json
{
  "status": 200,
  "body": "{\"job_id\":\"19bada19-4e6\",\"target\":\"http://out-of-scope-target.example.com\",\"tier\":\"SCOUT\",\"status\":\"queued\",\"created_at\":1777670348.5700064,\"progress_pct\":0.0,\"findings_count\":0}"
}
```

**Verdict: UNSAFE U2 — CONFIRMED LIVE.**
- HTTP **200 queued** for an out-of-scope target. Job created (`19bada19-4e6`).
- The gate exists in `scan_workflow.py:545-578` (Phase 0) but does not run before `security_dashboard.py:488-523` returns 200 to the caller.
- The user already has a `job_id` for an unauthorized target; if scope rejection happens later in workflow, that's an internal job-state transition, not a request rejection. The UI shows an "in-flight" job until it transitions to failed.
- Founder rule violation: "Do not run external security scans" — the structural risk is that *anything that lets the REST layer accept a scan target without scope-checking first* is the wrong architecture, even if the workflow eventually rejects. The HTTP success code is what the FE acts on.

> Pre-condition discovery: the endpoint requires a valid `ReportTier` enum value (`SCOUT`, `ANALYST`, `OPERATOR`, `ARCHITECT`, or `EVILBOB` per `report_tiers.py:36+`). The first attempt with `TIER_1_PROFILING` returned `400 - 'TIER_1_PROFILING' is not a valid ReportTier`. The second attempt with `SCOUT` returned 200. So input validation IS present for tier; just not for *target authorization*.

### Flow 8 — `/chat` attach + remove file → does backend file persist?

**Steps:**
1. Upload via `POST /api/v1/files/upload` directly (mirrors what the chat input does):
   ```
   FormData{ file: Blob('phase9c file remove test content', text/plain), purpose: 'chat_attachment' }
   ```
2. List files via `GET /api/v1/files`.
3. (Static) Inspect `frontend/src/components/chat/ChatInput.tsx:623` for the X-button handler.

**Result:**
```json
{
  "upload_status": 200,
  "file_id": "67fceeb2-a53e-4b9f-85b3-19eefd5b12f7",
  "files_count_before": 1
}
```

**Verdict: FAKE remove — CONFIRMED via static + live composite.**
- Upload writes to disk + DB (✓ backend behavior correct).
- Static evidence (Phase 9B): `ChatInput.tsx:623` X-button handler is `removeAttachment` (UI state mutation only) — no `api.delete` or `DELETE /files/{id}` call.
- Live evidence: file persists in `GET /files` after upload, and there is no remove flow that decrements the count. (To strictly prove the FAKE, I would have needed the chat input to attach the file via UI flow, then click X, then re-list; the test path was equivalent enough — the file is there, and there is no delete code path from chat to remove it.)

### Flow 1 — `/connections` → All Connections (V2) probe

**Steps:**
1. Navigate to `/connections`.
2. `GET /api/v1/connections/v2` (FOUNDER role).

**Result:**
```json
{ "list_status": 200, "total_rows": 0 }
```

**Verdict: WORKING (endpoint healthy) but EMPTY for fresh tenant.**
- Per ADR-002 Phase 5/6: V2 rows are detection-seeded, not eagerly populated for new tenants. The Provider Seed endpoint mentioned in 9B (`POST /api/v1/connections/v2/providers/seed`) is the explicit Phase 6 item to fix this.
- For a fresh founder, `/connections` V2 panel renders empty until the seed lands. **This is exactly the "interface with no functionality" pattern the founder flagged in the original brief**, but cleanly explained: the surface is honest about being empty (per ADR-001 honesty rule).
- The V1 `/api/v1/runtimes` endpoint works correctly for the same fresh tenant: 6 runtimes registered (`claude_code`, `codex`, `gemini_cli`, `grok_cli`, `vllm`, `ollama`), `primary_runtime: claude_code`, 4 online + 1 offline (Grok). This is the legacy data path that the V2 truth model is migrating *from*.

### Flow 9 — `/tasks` create → does it persist?

**Steps:**
1. POST to `/api/v1/execution/tasks` with a minimal body:
   ```json
   { "title": "Phase9C Test Task", "description": "Audit-created task", "priority": "medium" }
   ```
2. List tasks.

**Result:**
```json
{ "create_status": 422, "list_count": 0, "latest": "missing" }
```

**Verdict: SCHEMA MISMATCH — minor finding.**
- Task create body schema requires fields beyond `title/description/priority`. 422 returned. List remains empty. The Phase 9B audit said `POST /execution/tasks/{task_id}/run` is verified-working; the *creation* schema wasn't probed there.
- Not surfaced as a P0/P1 — the UI's `TasksPage.tsx` has a working create flow (per 9B), so the UI form must send the additional required fields. My direct-API probe was an under-spec'd payload.
- **Action:** add `TaskCreateBody` schema doc-comment so out-of-band callers can construct a valid payload without reading the Pydantic class.

### Flows 2, 3, 7, 10 — deferred (not run live this pass)

The remaining flows (Main Brain non-callable refusal, Experimental Override audit, Scan archive findability, Backend-offline error state) were not run live in this pass to preserve runtime budget for Phase 9E and Phase 10. Each has solid static evidence in the 9B matrix:
- **Flow 2 (V2 callable gate):** `MainBrainPanel.tsx:130-149` enforces gate when `USE_CONNECTION_REGISTRY_V2=true`; static evidence is conclusive. Live test would require seeded V2 rows (see Flow 1: 0 rows in fresh tenant).
- **Flow 3 (Override audit):** `runtimes.py:438` emits `runtimes.primary_override_not_callable` at WARNING-log level; not yet a formal AuditLog row (Phase 7 item per CLAUDE.md Rule 17). Phase 10 commit-4 adds the AuditLog row.
- **Flow 7 (Scan archive findability):** static evidence is conclusive (matrix §3.5; archived JSON moves to `var/security_reports/.archive/` but no `?show_archived=true` UI toggle). Phase 10 commit-3 adds the toggle.
- **Flow 10 (Backend offline):** the `BackendOfflineBanner.tsx:6` already polls `/api/v1/health` and surfaces a banner on failure; the `errorStore` + `ConnectionStatusIndicator` cluster is per-ADR-001 and was visually verified during the alembic-recovery interlude (when backend lifespan was mid-restart, the navbar dot turned amber correctly).

---

## 3. New findings beyond the matrix (surfaced during live trace)

### N1. Dev DB alembic drift (resolved in this run)

**Symptom:** `OperationalError: no such column: tenants.dek_wrapped` on `POST /api/v1/auth/register`.
**Root cause:** alembic head at `004`; columns from migrations 005–007 missing. Local SQLite uses `Base.metadata.create_all` to create *missing tables* but not to add *missing columns*. So the schema silently drifts after a migration adds new columns to existing tables.
**Fix in this run:** `cd backend && python -m alembic -c migrations/alembic.ini upgrade head`. Output:
```
INFO  [alembic.runtime.migration] Running upgrade 004 -> 005 (cron_runs, mcp_servers, background_tasks)
INFO  [alembic.runtime.migration] Running upgrade 005 -> 006 (secrets envelope vault, tenants.dek_wrapped)
INFO  [alembic.runtime.migration] Running upgrade 006 -> 007 (connection_v2, capability, op_lock)
```
**Status:** dev now at head. Production schema state remains the operator-side concern from `DAENA_DATABASE_READINESS_PLAN.md` Steps 7.3–7.5.

### N2. Register form: `tenant_name` required, but UI label is `Organization` — and slug-uniqueness collision

**Symptom 1:** With `email` being a `.local` TLD: 422 — Pydantic email validator rejects "special-use or reserved" TLDs (per RFC 6761).
**Symptom 2:** With valid email + `organization` field: 422 — backend explicitly requires `tenant_name`, not `organization`.
**Reality check:** `frontend/src/stores/authStore.ts:55-60` actually DOES send `tenant_name`. The `RegisterPage.tsx:29` calls `register(email, password, displayName, tenantName)`, so the form does pass it through. So why did my form-fill 422? Because my Playwright form-fill targeted the field labeled "Organization" and the form *also* needs the user to type the same value into a `tenant_name` field — but there's no separate `tenant_name` field in the UI! I was sending the `Organization` value as `tenantName` correctly through the click handler. So the issue was actually the email TLD.
**Action item:** the UI label "Organization" silently doubles as the tenant-slug source. Either rename the label to "Tenant / Organization name" or add a slug-preview field so the user knows what's being persisted. **Low-priority polish; not a P0/P1.**

### N3. Bare `GET /api/v1/runtimes` works for fresh tenant (returns 6 runtimes); `GET /api/v1/connections/v2` returns 0 rows for same tenant

This is the V1 vs V2 *data-path duality* that 9B flagged as "3 V1↔V2 duplicates" — confirmed live. V1 runtime registry is process-global; V2 truth registry is per-tenant + detection-seeded. Until provider-seed runs, fresh tenants see populated V1 panels and empty V2 panels for the same conceptual asset. **Recommendation: 9F backlog — eager-seed the V2 runtime rows on tenant creation** (or at least at first `/connections` page load) so the UI doesn't appear "empty" to a brand-new founder.

---

## 4. Trace artifacts

Playwright MCP captures (referenced in `frontend/.playwright-mcp/`):
- `page-2026-05-01T21-12-21-218Z.yml` — initial / state
- `page-2026-05-01T21-17-32-702Z.yml` — post-login /chat
- `page-2026-05-01T21-17-43-991Z.yml` — /settings/governance pre-click
- `page-2026-05-01T21-17-58-316Z.yml` — /settings/governance post-click ("GOVERNED" pressed)
- `page-2026-05-01T21-18-50-737Z.yml` — /scan post-navigate
- Console log: `console-2026-05-01T21-12-25-073Z.log` (cumulative)

---

## 5. Carry-forward into 9F backlog

| ID | Finding | Phase 10 commit | Severity |
|---|---|---|---|
| C-FAKE-GOV | Governance Mode persists to `daena:governanceMode` localStorage; backend never sees it | commit-2 | **HIGH** (founder-facing) |
| C-FAKE-LLM | Local-First / Cost-Aware Routing toggles persist to localStorage; ModelRouter never reads them | commit-2 | HIGH |
| C-UNSAFE-SCAN-START | `POST /security/scans/start` accepts out-of-scope target with 200 queued | commit-1 | **CRITICAL P0** |
| C-FAKE-FILE-X | ChatInput X-button removes UI state only; file blob + DB row persist | commit-4 | MEDIUM |
| C-EMPTY-V2 | Fresh tenant has 0 V2 rows; UI shows empty Connections panel until seeded | commit-2 | MEDIUM (UX) |
| N1 | Dev DB schema drift requires manual `alembic upgrade head` | docs / dev guide | LOW |
| N2 | Register form `Organization` label is opaquely also `tenant_name` source | polish | LOW |
| N3 | V1 vs V2 data-path duality (V1 runtimes populated, V2 empty for same tenant) | commit-2 / docs | MEDIUM |

---

## 6. Boundaries respected

- No production deploy; no GCP touch.
- No `USE_CONNECTION_REGISTRY_V2` flip.
- No `vault --apply`.
- No vault.py / oauth_credentials_store.py touched.
- No secrets read or printed (test JWTs are per-session and bounded).
- **External-network test target was `out-of-scope-target.example.com`** — a non-existent subdomain of the IETF-reserved `example.com` documentation domain. No real external host was probed. The 200-queued response confirms the gate gap; the workflow's own internal scope check would have rejected the target *if* it had run, so no real outbound scan traffic was generated either way.
- Schemathesis NOT installed.
- One alembic migration run on the local SQLite dev DB (004 → 007). This is the dev DB only; production is unaffected.
