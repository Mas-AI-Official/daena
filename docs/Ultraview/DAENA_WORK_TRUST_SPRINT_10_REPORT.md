# DAENA-WORK-TRUST-SPRINT-10 — Report

**Branch:** master (local only — not pushed)
**Date:** 2026-05-05
**Status:** Done. 242/242 tests passing across the full Sprint-10 regression band; frontend tsc clean. Commits 854a602, bd7e8c0, 31c4faa, 8a0b673, e6c... (PR-6 final).

---

## What this sprint is for

The previous sprint armed five zero-input MCPs (Filesystem / Time / Fetch / Memory / Sequential Thinking) and proved the local beta works. This sprint takes the next honest step: make Daena trustworthy for Masoud's REAL work — research-driven jobs and content — without enabling any external write surface yet.

The brief explicitly named the trust boundary:

> You can trust Daena as a supervised read-only assistant now.
> You can trust her with your jobs/projects after the next sprint, once
> ScrapeGraphAI, Google setup, local drafts, and audit visibility are wired.
> You should not trust her yet to act externally until consent, policies,
> audit viewer, and repeated manual proofs are complete.

Sprint-10 lands the second sentence. Sprint-11+ owns the third.

---

## What shipped, by PR

### PR-1 (854a602) — Google OAuth live setup helpers

Static `GoogleAccountSetupGuide` became a live four-step checklist.

| Step | Pass condition |
|---|---|
| 1. OAuth client configured | `oauth_client_config_store.get_metadata('google').configured == True` |
| 2. Founder account `masoud.masoori@mas-ai.co` connected | `ConnectorInstance.status == CONNECTED` AND `owner_email` matches (case-insensitive) |
| 3. Agent account `daena@mas-ai.co` connected | same shape, agent email |
| 4. Both accounts ready | derived: client AND founder AND agent |

Files:
- `backend/app/api/v1/google_setup.py` (NEW)
- `frontend/src/hooks/useGoogleSetupStatus.ts` (NEW)
- `frontend/src/pages/connections/GoogleAccountSetupGuide.tsx` (extended)
- Wired into `AppsStorePanel` so the guide is reachable in the live UI (PR-6 polish — earlier the guide was orphan code in an unused `AppsPanel`)

Hard rules held: no auto-OAuth, no secret reads, case-insensitive email match, disconnected instances do NOT count, frontend hook hits the relative API path so dev (Vite proxy) and prod (reverse proxy) both work.

Tests: 10 new (8 backend integration + 2 frontend source-grep pins).

### PR-2 (bd7e8c0) — ScrapeGraphAI governed read-only skill

ScrapeGraphAI lives in `D:\Ideas\Daena\venv_daena` (separate from backend's `.venv`). The new `app/services/scrape` package spawns the venv_daena Python as a subprocess via stdin/stdout JSON, audits the call, returns to the caller.

```
POST /api/v1/scrape/extract  (FOUNDER role only)
Request:  {url, goal, max_chars}
Response: {success, result, truncated, error, worker_version, audit_event_id}
```

Hard rules pinned by tests:
- **URL safety**: re-uses the same `url_safety.is_public_url_safe` the mcp-fetch precall validator uses. One source of truth for SSRF blocking.
- **Cap**: default 8000 chars, hard ceiling 32000.
- **Timeout**: 60s. Worker timeout returns a structured `ExtractResult`, never raises.
- **No login / form submission**: worker uses `SmartScraperGraph` only. Source-grep test rejects `SubmitterGraph`, `FormSubmitterGraph`, `LoginGraph`, `InteractiveScraperGraph`.
- **No credential leakage**: worker rejects any output containing `sk-` / `Bearer ` / `ya29.` / `1//0e` prefixes; parent re-checks. Audit row carries `url_host` (scheme+host only) + `goal_length` + `result_length`, **NEVER** the full URL value, the goal text, or the result body.
- **No paid-API requirement**: default LLM is Ollama at localhost:11434. OpenAI fallback only when `DAENA_SCRAPE_LLM=openai` AND `OPENAI_API_KEY` is set; the key is passed by env-name reference, never inlined into the config dict.

Tests: 28 new (23 service + 5 API). Worker subprocess mocked.

### PR-3 + PR-4 (31c4faa) — Career + Content read-only research flows

```
POST /api/v1/research/career    (FOUNDER role only)
POST /api/v1/research/content   (FOUNDER role only)
GET  /api/v1/research/drafts    (any auth, tenant + user scoped)
GET  /api/v1/research/drafts/{id}
```

Each flow chains: `source URL → ScrapeGraphAI → ResearchDraft (status=DRAFT)`. That's it.

Honest deliverable: there is **no** `/send`, `/submit`, `/apply`, `/post`, `/publish`, `/dispatch` endpoint. Source-grep tests pin that the API + service files contain none of those verbs, none of `smtplib` / `requests.post` / `playwright` / `sendgrid` / `gmail.send`. The schema itself has zero `sent_at` / `submitted_at` / `posted_at` / `applied_at` / `published_at` columns — a future maintainer adding one fails the suite.

Why combined commit: the two flows share a service + a model + a draft list. Splitting across two commits would just copy 80% of the same code.

The summary stored on the draft is ScrapeGraphAI's goal-driven extraction output (SmartScraperGraph already runs the goal as the LLM prompt). A future PR can add a separate post-process LLM stage without changing this contract.

Files:
- `backend/app/models/research.py` — `ResearchDraft` model
- `backend/app/services/research_flow.py` — service that chains scrape + persist
- `backend/app/api/v1/research.py` — four endpoints
- `backend/app/models/__init__.py` — model registration

Tests: 11 new (parametrized career/content, SSRF parity, FOUNDER auth gate, cross-user 404, schema-no-dispatch-columns, source-no-dispatch-verbs).

### PR-5 (8a0b673) — Audit viewer plugin filter + plugin-invocation detail panel

Two changes to `GovernanceAuditPage.tsx`:

1. **Plugin filter dropdown** alongside Action Type / Risk / Result / Date filters. Setting it auto-implies `action_type = 'plugin.skill_invocation'` so the operator never has to combine two filters to ask "what did mcp-fetch do."

2. **Plugin Invocation detail panel** rendered when `entry.action_type === 'plugin.skill_invocation'`. Surfaces the brief-mandated fields:
   - plugin / skill / status (outcome)
   - **Mode pill: amber for any row marked write, emerald for read-only.** Defense visualisation — Phase 2 should never show amber.
   - target_tool / host / result_length / blocked_reason
   - audit id

The plugin invocation keys are removed from the generic "Additional Details" dump so the panel doesn't double-render them.

Tests: 5 source-grep pins (filter state + filtered useMemo + panel testid + shownKeys allowlist + no-credential-renderer).

### PR-6 (this commit) — Work-trust smoke

End-to-end live verification + the `AppsStorePanel` wire-up that surfaces the new Google setup guide. Plus a defensive fallback in `google_setup.py` for dev SQLite databases that pre-date the `owner_email` column on `ConnectorInstance` (the dev path needs graceful degrade until the operator migrates / wipes the dev DB; production is on Postgres + Alembic so this branch never fires there).

---

## Live smoke evidence (in order I ran it)

| Check | Result |
|---|---|
| **A.** Backend up — `GET /health` | `{"status":"healthy"}` ✅ |
| **B.** Allowlist API — 23 entries; the 4 zero-input MCPs all `mode=mcp_tool` | ✅ all four surface |
| **C.** Phase 3 floor — write entries in PHASE2_ALLOWLIST | **0** ✅ |
| **D.** Google setup status — empty state | All four steps `connected: false`, `ready: false`, both pinned emails returned ✅ |
| **E.** ScrapeGraphAI SSRF block — `http://localhost/admin?secret=hunter2` | 400 `url_safety:url_localhost_host` + audit_event_id; **`hunter2` does NOT echo back** ✅ |
| **F.** Career research SSRF block — `http://10.0.0.5/internal` | 400 `url_safety:url_private_ip` ✅ |
| **G.** Content research SSRF block — `http://192.168.1.1/router` | 400 `url_safety:url_private_ip` ✅ |
| **H.** Drafts list — fresh tenant | `{"drafts": []}` ✅ |
| **I.** Frontend `/connections` renders, verdict honest | (carried from Sprint-9 PR-4) ✅ |
| **J.** Audit viewer plugin filter dropdown renders | `audit-filter-plugin` testid present, "All plugins" default ✅ |

The two live-UI gaps (the actual `AppsStorePanel` route requires the operator to enable "Show advanced" mode + click "OAuth apps (V2)"; the audit viewer panel needs a plugin-invocation row in the calling user's tenant) are downstream UX issues, not Sprint-10 contract violations. The wiring is in source; source-grep tests pin both.

---

## Hard rules — every one held

| Brief rule | Held |
|---|---|
| Do not push | ✅ master is local only |
| Do not deploy | ✅ |
| Do not read/print/commit secrets | ✅ — pinned by `test_response_carries_no_credential_keys` (PR-1), `test_extract_endpoint_audit_row_does_not_leak_url_value_or_goal` (PR-2), `_parse_worker_output` credential-shape gate (PR-2) |
| Do not send email | ✅ — pinned by `test_research_api_source_has_no_send_post_submit_verbs` |
| Do not apply to jobs | ✅ — same source-grep test catches `/apply` |
| Do not post externally | ✅ — same test catches `/post`, `/publish`, `playwright`, `gmail.send` |
| Do not change files outside approved local workspace | ✅ — only `D:\Ideas\Daena\` touched |
| Do not run browser automation on external sites | ✅ — no playwright in research flow source |
| Do not run unrestricted scraping | ✅ — every scrape gated by `is_public_url_safe` + cap + timeout + audit |
| Do not enable Phase 3 writes | ✅ — `PHASE2_ALLOWLIST` carries 0 non-read-only entries |
| Do not bypass target scope | ✅ — Sprint-9's REST-boundary scope gate untouched |

---

## What this sprint gives Masoud

**Before:** Daena could scan, search files, fetch a public URL, recall the time. Useful for a demo but not for actual work.

**After:** Daena can take a job posting URL or an article URL and produce a local, audited, capped, read-only draft Masoud can read + curate. No external action. No email. No application submitted. No post made. The audit log shows what happened with the new plugin filter narrowing to specific tools.

The next manual step is for Masoud to:
1. Open Settings → OAuth Clients, paste Google `client_id` + `client_secret` from console.cloud.google.com
2. Click Connect on Gmail (or Drive or Calendar) in the marketplace, sign in as `masoud.masoori@mas-ai.co`
3. Click Connect again, sign in as `daena@mas-ai.co`
4. The live checklist flips green step-by-step

After that, Daena has supervised read-only access to both Google accounts (when the read-side OAuth skills are armed in a separate PR — they exist in PHASE2_ALLOWLIST but execution_mode for OAuth-flavored entries is wired separately).

---

## Numbers

- **5 commits** (4 distinct PRs + 1 wrap commit): 854a602, bd7e8c0, 31c4faa, 8a0b673, plus this one
- **242 backend tests passing** across the full Sprint-10 regression band
- **Frontend tsc clean**
- **0 hard-rule violations** across all 11 brief guards
- **0 changes to backend governance pipeline** (Phase 2 read-only floor untouched)
- **0 secret reads** (no env value, no token, no client_secret value crosses any tested code path)

---

## Files touched

### New
- `backend/app/api/v1/google_setup.py`
- `backend/app/api/v1/scrape.py`
- `backend/app/api/v1/research.py`
- `backend/app/services/scrape/__init__.py`
- `backend/app/services/scrape/service.py`
- `backend/app/services/scrape/worker.py`
- `backend/app/services/research_flow.py`
- `backend/app/models/research.py`
- `backend/tests/test_google_setup_status.py`
- `backend/tests/test_scrape_service.py`
- `backend/tests/test_scrape_api.py`
- `backend/tests/test_research_flow.py`
- `backend/tests/test_audit_viewer_plugin_filter.py`
- `frontend/src/hooks/useGoogleSetupStatus.ts`

### Modified
- `backend/app/api/v1/__init__.py` (router mounting)
- `backend/app/models/__init__.py` (ResearchDraft registration)
- `frontend/src/pages/connections/GoogleAccountSetupGuide.tsx` (live checklist)
- `frontend/src/pages/connections/AppsStorePanel.tsx` (mount the guide)
- `frontend/src/pages/GovernanceAuditPage.tsx` (plugin filter + detail panel)

---

## Sprint-11 candidates (operator picks)

1. **Push the local beta to origin.** master is 5 commits ahead.
2. **OAuth-side skill execution wire-up** — the PHASE2_ALLOWLIST already has Gmail / Drive read-skills with `execution_mode='mcp_tool'` and `backend_surface='oauth'`; once the operator finishes the Google connect dance, those skills become live without additional code.
3. **Plain-English policy compiler exposure** — let the operator write a short rule like "never let Daena send anything to anyone I've labelled 'cold'" and SecurityGate enforces it. Foundation already exists per global CLAUDE.md.
4. **Local LLM post-process step** for research drafts — extract structured fields (role title, comp range, required skills) from the messy scrape output. Pure LLM, no new external surface.
5. **Audit log review-state UI** — operator marks plugin runs as reviewed/needs-review without modifying the immutable hash chain (annotation only).

My read: **#1 + #2** is the highest-trust next step. Push gives Masoud a known-good restore point; OAuth wire-up unlocks his actual Gmail / Drive / Calendar reads on top of the new local artifact infrastructure.

---

**Branch sits at master, local only. Stop and report.**
