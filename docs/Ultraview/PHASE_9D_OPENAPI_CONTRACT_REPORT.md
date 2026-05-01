# Phase 9D — Live OpenAPI Contract Diff Report

**Date:** 2026-05-01
**Operator:** Claude Code (Opus 4.7) under founder-direction interaction-audit task
**Method:** Live `openapi.json` fetched from running local backend (port 8000), diffed against every `api.{get,post,put,patch,delete}` and `EventSource/fetch` call site in `frontend/src/`
**Artifacts:**
- `docs/Ultraview/openapi-live.json` — 362 KB, 396 operations across 352 paths
- `docs/Ultraview/openapi-diff.json` — full programmatic diff with locations

> **Status one-liner:** **149 of 164 unique frontend call paths matched the live spec.** The 15 unmatched fall into **5 real broken calls**, **3 cosmetic ghosts** (template-var collapse / code comment / SSE-method-label mismatch), and **7 SSE/fetch direct-fetch ghosts** that *do* match the spec under POST/GET. Of the 247 "unused" spec operations, ≈85% are intentional (backend surface broader than UI: benchmark, founder-routing, daenabot internal, mobile, bridge, OAuth callback handlers); ≈15% are real UI gaps where a UI surface should exist but doesn't.

---

## 1. Headline numbers

| Metric | Count |
|---|---:|
| Frontend call sites scanned (`api.METHOD()` + `fetch()` + `new EventSource()`) | 218 |
| Unique `(METHOD, PATH)` keys | 164 |
| Live OpenAPI operations | 396 |
| Matched (UI ↔ spec, after bilateral `{var}` → `{p}` normalization) | **149** |
| **Ghost calls** (UI calls path absent from spec) | 15 (4-5 real) |
| **Unused spec ops** (spec has it, UI never calls) | 247 (≈37 worth investigating) |

Backend version: `Daena 0.1.0`. Servers list: not declared in spec (acceptable — implies same-origin). All 49 router groups from `backend/app/api/v1/__init__.py` are reflected in the spec.

---

## 2. Real ghost calls — UI will get 404 / 405 in production

These need fixes (either implement the endpoint or remove the UI call).

| # | UI call | UI source | Spec reality | Severity |
|---|---|---|---|---|
| G1 | `DELETE /api/v1/company-mode/seed-brief` | `pages/CompanyModePage.tsx:235` | Spec has only `GET` + `POST` for that path. DELETE returns **405 Method Not Allowed**. | **HIGH** — user-visible: "Delete Seed Brief" button in `/company-mode` UI silently fails (or 405-toasts). |
| G2 | `GET /api/v1/projects/{id}/files` | `pages/ProjectDetailPage.tsx:99` | Spec has `/projects/{project_id}` (GET/PUT/DELETE) only. **No `/files` sub-resource.** Returns 404. | **MEDIUM** — Project Detail page's Files tab will be empty / error-state. Either `GET /files?project_id={id}` exists and the call should be rewritten, or the endpoint needs to be implemented. |
| G3 | `GET /api/v1/projects/{id}/tasks` | `pages/ProjectDetailPage.tsx:89` | Same as G2: no `/tasks` sub-resource on `/projects/{id}`. Returns 404. | **MEDIUM** — same shape. |
| G4 | `GET /api/v1/runtimes/subscriptions` | `pages/settings/SettingsLLM.tsx:46` | Spec has no `/runtimes/subscriptions` path. Returns 404. | **LOW-MEDIUM** — SettingsLLM probably degrades silently to "no subscriptions" but hides the real cause. |
| G5 | `GET /api/v1/settings` (bare) | `pages/settings/SettingsDeveloper.tsx:48` | Spec has only `/settings/user`, `/settings/{section}`. Bare `/settings` returns 404. | **LOW** — likely a fallback / dead-code pattern in SettingsDeveloper; refactor to `GET /settings/user`. |

### Confirmed-false ghosts (no fix needed, just diff-tool noise)

| Ghost | Reality |
|---|---|
| `GET /api/v1/runtimes/foo` (`lib/api.ts:80`) | Doc comment example showing how to disable silent mode for a path. Not a real call. |
| `POST /api/v1/souls/proposals/{p}/{p}` (`MindDetailPage.tsx:135`) | UI builds `/proposals/${proposalId}/${decision}`; spec has both `/approve` and `/reject` as concrete suffixes. The UI substitutes the `decision` value (`'approve'` or `'reject'`) at runtime — both real spec paths. False ghost from my normalizer collapsing two `{}` to two `{p}` instead of distinguishing literal-action from id. |
| `POST /api/v1/workstreams/{p}/{p}` (`WorkstreamsPage.tsx:266`) | Same pattern. Spec has `/cancel`, `/escalate`, `/pause`, `/redirect`, `/resume` suffixes. All match at runtime when UI substitutes the action name. |

### SSE/fetch ghosts (false-method-label, all match spec under POST/GET)

7 calls show as ghosts because my diff labels `EventSource(...)` and direct `fetch(...)` as `SSE/FETCH` while the spec lists them as `GET` or `POST`. All paths exist:

| UI fetch | Spec match |
|---|---|
| `fetch /api/v1/chat/messages/stream` | `POST /api/v1/chat/messages/stream` |
| `fetch /api/v1/files/upload` | `POST /api/v1/files/upload` |
| `fetch /api/v1/billing/my-quota` | `GET /api/v1/billing/my-quota` |
| `fetch /api/v1/health` | `GET /api/v1/health` |
| `fetch /api/v1/heartbeat/status` | `GET /api/v1/heartbeat/status` |
| `fetch /api/v1/tts/speak` | `POST /api/v1/tts/speak` |
| `fetch /api/v1/chat/messages/{id}/feedback` | `POST /api/v1/chat/messages/{message_id}/feedback` |

**Net: 4 actionable real ghosts** (G1–G4); G5 is low-priority cleanup. None are UNSAFE in the security sense — they fail closed (404 / 405) rather than running with bad data.

---

## 3. Unused spec operations — 247 total, ≈37 worth attention

Per-group breakdown (counts) — full per-row data in `openapi-diff.json`:

| Group | Unused | Likely category |
|---|---:|---|
| connections | 21 | Mostly OAuth callback handlers + V2 internal endpoints accessed by hooks (likely false-unused after deeper trace). Worth a focused pass. |
| benchmark | 15 | Entire `/api/v1/benchmark/*` API has no UI surface. Intentional — benchmark is operator-only. |
| autopilot | 8 | `/queue/events` SSE is used; `/state/{session_id}`, `/summary/{session_id}`, `/approve`, etc. are not surfaced. Most likely intentional (chat orchestrator drives autopilot, not direct UI). |
| execution | 8 | Several `/executions/...` detail endpoints exist with no UI. Tasks UI uses subset only. |
| connectors | 6 | OAuth callback + provider list endpoints — invoked by browser redirect flows, not by `api.*`, so they don't appear in scan. |
| chat | 6 | Includes `POST /chat/messages/stream` (false-unused; called via `fetch`), session-message CRUD subset. |
| agents | 6 | `/agents/agents` CRUD never surfaced; only `/agents/departments` is. |
| founder | 5 | `/founder/routing/*` policy endpoints — no dedicated UI; probably intentional founder-CLI surface. |
| governance | 5 | (Need per-row check.) |
| crm | 4 | CRM endpoints accessed via department-chat flows, not directly. |
| department-budget | 4 | Budget proposals API has no UI surface. |
| engagements | 4 | `/engagements/{id}` and `/engagements/{id}/report` actually used by UI — false-unused due to SSE/fetch pattern. |
| ... 14 more groups | < 4 each | Mostly intentional or false-unused |

### Worth-investigating slice (≈37 operations)

These are the unused spec endpoints where the absence of a UI surface seems *unintentional*:

- **Connections OAuth flow**: `GET /connectors/{id}/oauth/authorize`, `GET /connectors/oauth/callback`, `GET /connectors/oauth/providers`, `GET /connectors/mcp-oauth/callback`. UI uses popup/redirect for OAuth, so direct `api.*` calls won't appear — these are *probably* false-unused and need browser-trace confirmation in 9C.
- **Connection instances**: `GET /connections/instances/{id}`, `GET /connections/instances/{id}/permissions`, several `PATCH` permission endpoints. UI may call these via hook helpers that I missed in the regex — needs `useConnectorCatalog`/`useConnectorInstances` hook trace.
- **Department budget**: 4 endpoints with no UI. Either build a Department Budget UI or document as agent-only API.
- **Founder routing policy**: 5 endpoints with no UI. Per `FRONTEND_BACKEND_TRUTH_MATRIX`, founder routing is currently handled via Settings tabs that don't actually persist (the FAKE settings cluster from 9B). These endpoints exist precisely to enable the persistence migration in Phase 10 commit-2.
- **Benchmark**: 15 endpoints. Decide: ship a `/benchmark` UI, or remove the routes? They're stable plumbing per `BENCHMARK_*` reports — keep but document as operator-only.

The remaining ~210 unused are intentional or false-unused (false-unused includes: SSE-pattern fetches, hook-helper indirection my grep missed, OAuth callback handlers invoked by browser redirect, mobile API for a future client, etc.).

---

## 4. Response-shape risks

The diff is path-level; I did not parse Pydantic models against TypeScript inline-typed call-site casts (no current type-bridge). However, the matrix audit (9B) flagged several places where the UI relies on undocumented response shape:

- **Settings persistence FAKE cluster** (25 entries): UI never reads back what backend returns because it doesn't call backend at all. Once Phase 10 commit-2 wires these to `PUT /settings/user`, response-shape contract becomes load-bearing. The current `users.settings` JSONB column is untyped at the API surface — `PUT /settings/user` accepts arbitrary `{ settings: {...} }` and echoes it.
- **Scan report shape** (`GET /security/scans/{job_id}/report`): UI parses `{job_id, tier, findings[], summary, report_pdf_path, cost_usd, duration_secs, pipeline_stages_used, recommendations, severity_counts}` — exhaustively covered by ScanReport.tsx. Shape stable per Phase 5 reports.
- **Connection V2 truth** (`GET /api/v1/connections/v2`): UI parses `ConnectionV2Row` with 6-truth-dim structure (`detected/configured/imported/reachable/authenticated/callable`). Shape stable per ADR-002.
- **Approval queue events** (`GET /governance/approvals/events` SSE): event types `pending`, `resolved` — shape covered.
- **Chat stream** (`POST /chat/messages/stream` SSE): 16+ event types (`session_created`, `user_message`, `thinking`, `governance_notice`, `chunk`, `memory_writeback`, `tool_call`, `approval_pending`, `tool_blocked`, `governance_approval_pending`, `governance_approval_resolved`, `vp_plan`, `vp_subtasks_created`, `scan_dispatched`, `finalize`, `error`). Shape stable; per-event handlers in `chatStore.ts:447+`.

No silent response-shape mismatches found *at the level this static diff can reach*. Schemathesis (Phase 9A §5) would surface field-level drift; deferred per recommendation in 9A pending a real shape-mismatch trigger. **Defer install remains correct.**

---

## 5. Recommendation: types-only OpenAPI generation

**Recommendation unchanged from Phase 9A: hybrid.** Keep `lib/api.ts` runtime; add `openapi-typescript` for compile-time types. Concrete commands (Phase 10 commit-2 candidate):

```bash
cd frontend
npm install -D openapi-typescript
npx openapi-typescript ../docs/Ultraview/openapi-live.json -o src/types/api-schema.d.ts
```

Then add a `gen:api` npm script and import types at the call site:

```ts
import type { paths } from '@/types/api-schema'

type ScanReport = paths['/api/v1/security/scans/{job_id}/report']['get']['responses']['200']['content']['application/json']
```

Migration is incremental — no big-bang rewrite. Start with the 5 real ghost-call sites (G1–G5 above) since they're already broken; the type would have surfaced the gap at compile time.

**Not recommended:** Orval, openapi-fetch, or full SDK regen. Same reasoning as 9A: the bespoke `silent-prefixes / errorStore / JWT-refresh-queue` interceptor logic in `lib/api.ts` would be obliterated by any of those pipelines.

---

## 6. Concrete repair items derived from this diff

These get folded into the Phase 10 backlog:

| ID | Action | Owner | Cost |
|---|---|---|---|
| D-G1 | Add `DELETE /api/v1/company-mode/seed-brief` to `backend/app/api/v1/company_mode.py` (or change UI to use `POST /seed-brief` with empty body and treat empty as deletion). | Backend | ~10 LOC + 1 test |
| D-G2 | Add `GET /api/v1/projects/{project_id}/files` returning files filtered by `project_id` (probably a thin wrapper over the existing `files` table query). | Backend | ~20 LOC + 1 test |
| D-G3 | Add `GET /api/v1/projects/{project_id}/tasks` (same shape as G2 but for `tasks`). | Backend | ~20 LOC + 1 test |
| D-G4 | Add `GET /api/v1/runtimes/subscriptions` to `runtimes.py` (or remove the UI call if subscriptions data lives elsewhere). | Backend | ~15 LOC OR delete UI call |
| D-G5 | Refactor `SettingsDeveloper.tsx:48` to `GET /settings/user` instead of bare `/settings`. | Frontend | 1-line diff |
| D-T1 | Add `npm install -D openapi-typescript` + `npm run gen:api` script + `frontend/src/types/api-schema.d.ts` generated file. | Frontend tooling | ~5 min |
| D-T2 | Migrate 5 high-impact call sites (the 4 real ghosts above + ScanReport.tsx) to use generated `paths` types. Proves the workflow without a big-bang rewrite. | Frontend | ~1 hour |

---

## 7. Boundaries respected

- No production deploy.
- No `USE_CONNECTION_REGISTRY_V2` flip.
- No `vault --apply`.
- No vault.py / oauth_credentials_store.py touched.
- No secrets read or printed (Perplexity API key existence checked via `grep -q` count, value never enumerated).
- No external scans run.
- Backend was started locally on port 8000; OpenAPI fetched without auth (default FastAPI behavior); spec contains zero secret values (FastAPI doesn't include env in `/openapi.json`).
- Schemathesis NOT installed (deferred per 9A recommendation; no shape-mismatch trigger found in this pass).

## 8. Where this report goes next

- Feeds Phase 9E.1 (Sanitized Review Pack) headline numbers + the 4 real ghost calls.
- Feeds Phase 10 commit-1 (none — gates first) and commit-2 (settings persistence) and a *new commit-2b* for the 4 ghost-call backend endpoints if founder approves the scope expansion.
- Saved artifacts: `openapi-live.json`, `openapi-diff.json`. `openapi-live-routes.txt` was a one-shot scratch and will be deleted to avoid index pollution.
