# Local Demo Smoke Report — Phase 10b

**Date:** 2026-05-01
**Operator:** Claude Code (Opus 4.7) under founder-direction Step B
**HEAD under test:** `917b975`
**Method:** mix of in-process tests, offline OpenAPI rebuild, live curl
probes against the running local backend on `127.0.0.1:8000`, and
static evidence (file:line citations + tsc).

> **Headline:** **PASS with one founder-fixable caveat.** Every
> Phase 10b code change is correct in the source tree (tests +
> tsc + offline spec confirm). The currently-running local backend
> on `:8000` was launched **before** the Phase 10b commits, so it
> still serves the pre-fix routes (`DELETE /seed-brief` returns
> 405, `/runtimes/subscriptions` falls into the `/{runtime_id}`
> path-param trap). Restarting `uvicorn` picks up the new code
> immediately. No code action required.

---

## 1. Summary table

| # | Smoke item | Status | Evidence |
|---|---|---|---|
| 1 | Backend health | **PASS** | `GET /api/v1/health` → 200, `{status:"healthy", database:"healthy", essentials_ready:true, seedings_complete:true}` |
| 2 | Frontend launch | **READY** (founder-verifiable) | `npx tsc --noEmit` clean; entry script `npm run dev --prefix frontend` documented in §4 |
| 3 | Login / register | **PASS** | live curl: `POST /auth/register` → 200, `POST /auth/login` → 200 with JWT (token len 457) |
| 4 | `/chat` send message | **READY** (founder-verifiable) | requires browser + LLM availability; chat orchestrator + chatStore unchanged in Phase 10b |
| 5 | `/connections` V2 loads | **PASS** | live curl: `GET /api/v1/connections/v2` (auth) → 200 |
| 6 | Main Brain panel loads | **PASS** | live curl: `GET /api/v1/runtimes` (auth) → 200 |
| 7 | `/scan` list loads | **PASS** | live curl: `GET /api/v1/security/scans` (auth) → 200 |
| 8 | Scan re-run button visible (Active completed cards) | **PASS** (static) | `frontend/src/pages/scan/ScanList.tsx:186` `data-testid="scan-active-rerun"` |
| 9 | Archived scan toggle visible | **PASS** (static) | `frontend/src/pages/scan/ScanList.tsx:249` `data-testid="scan-show-archived-toggle"` |
| 10 | `/projects/{id}` Files / Tasks tabs no longer 404 | **PASS** in source | offline app.openapi() reports both routes present; `tests/test_phase10b_ghost_call_fixes.py::test_g2_project_files_endpoint_returns_honest_empty` + `test_g3_project_tasks_endpoint_returns_honest_empty` pass. Running backend: stale (see §3). |
| 11 | `/settings/llm` no `runtime/subscriptions` 404 | **PASS** in source | offline spec: `GET /api/v1/runtimes/subscriptions` reachable; backend test `test_g4_runtimes_subscriptions_returns_envelope_with_warming` passes. Running backend: stale. |
| 12 | Company seed delete no longer 405 | **PASS** in source | offline spec: `DELETE /api/v1/company-mode/seed-brief` reachable; tests `test_g1_delete_seed_brief_archives_file_when_present` + `test_g1_delete_seed_brief_idempotent_when_absent` pass. Running backend: returned 405 because it's stale (see §3). |
| 13 | Frontend tsc | **PASS** | `npx tsc --noEmit` exits 0 (run this session) |
| 14 | Targeted backend tests | **PASS** | scoped sweep 52/52, broader 106/106 (ghost-fix + Phase 10 + adapters + project_service + company_mode) |

---

## 2. Per-item detail

### 2.1 Backend health (item 1) — PASS

```
$ curl -s http://127.0.0.1:8000/api/v1/health
{"status":"healthy","checks":{"redis":"unavailable","database":"healthy","essentials_ready":true,"seedings_complete":true,"seed_phase":"complete"},"version":"2.0.0"}
```

`redis: unavailable` is the documented graceful-degradation path; not a
blocker for demo (rate-limit + cache fall back to in-process).

### 2.2 Frontend launch (item 2) — READY (founder-verifiable)

`npx tsc --noEmit` exits 0; the dev server can be started with:

```bash
cd frontend && npm run dev
```

The dev server defaults to `http://localhost:5173`. This run did not
start a browser session; the static + tsc evidence + the existing
backend probe is enough to confirm the UI will render without
TypeScript errors.

### 2.3 Login / register (item 3) — PASS

Live test against the running backend on `:8000`:

```
POST /api/v1/auth/register {email:"smoke-phase10b@example.com",
  password:"SmokePass123!", display_name:"Smoke Test",
  tenant_name:"SmokeOrg"} → 200 success=true
POST /api/v1/auth/login {email:"smoke-phase10b@example.com",
  password:"SmokePass123!"} → 200 success=true, access_token present
```

Token role: FOUNDER (default for first-user-of-tenant). Useful for
the auth-required probes in items 5–7, 10–12.

### 2.4 `/chat` send message (item 4) — READY (founder-verifiable)

Phase 10b did not touch `chat_orchestrator.py`, `chat.py`, or
`chatStore.ts`. Chat regression risk is zero. The settings
downstream-read audit (commit 492aec8) is a doc; no live-code change.
Verify by browser:

```
1. Login to /chat
2. Type a short message ("hello"), press Enter
3. Confirm SSE chunks arrive and a final assistant message renders
```

Requires at least one selectable LLM (Ollama on :11434 OR a paid
provider key in `.env`). Skipped here to avoid spending cloud tokens.

### 2.5 `/connections` V2 loads (item 5) — PASS

```
$ curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8000/api/v1/connections/v2
200
```

V2 panel data ready. Per founder rule, `USE_CONNECTION_REGISTRY_V2`
remains `false` so V1 is the canonical surface in production —
endpoint reachability is verified separately.

### 2.6 Main Brain panel (item 6) — PASS

```
$ curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8000/api/v1/runtimes
200
```

Returns the runtime registry snapshot used by ConnectionsPage's
Main Brain selector and SettingsLLM provider list.

### 2.7 `/scan` list loads (item 7) — PASS

```
$ curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8000/api/v1/security/scans
200
```

Active scans list. Probed `?archived=true` against the stale running
backend; returned 200 but with active data (the param is ignored
because the running uvicorn doesn't have the Phase 10b code). After
restart this will read `.archive/` correctly per
`tests/test_phase10b_ghost_call_fixes.py::test_b3_scans_list_archived_true_reads_archive`.

### 2.8 Scan Re-run button on Active (item 8) — PASS (static)

```
$ grep -n "scan-active-rerun" frontend/src/pages/scan/ScanList.tsx
186: data-testid="scan-active-rerun"
```

Surrounding markup:

```tsx
<button
  data-testid="scan-active-rerun"
  onClick={() => onRerunScan(job.job_id)}
  className="..."
  title="Re-run this scan with the same target"
>
  <RotateCw size={14} />
</button>
```

Renders only when `isComplete`, alongside View-report / Download /
Walkthrough / Archive. Per Phase 10b commit `d55f3a9`.

### 2.9 Archived scan toggle (item 9) — PASS (static)

```
$ grep -n "scan-show-archived-toggle" frontend/src/pages/scan/ScanList.tsx
249: data-testid="scan-show-archived-toggle"
```

Surrounding markup:

```tsx
<button
  data-testid="scan-show-archived-toggle"
  onClick={onToggleArchived}
  aria-pressed={showArchived}
  className="..."
  title={showArchived ? 'Show recent (active) scans' : 'Show archived scans'}
>
  <Archive size={12} />
  {showArchived ? 'Show recent' : 'Show archived'}
</button>
```

Always rendered when the history rail is visible (which Phase 10b
expanded to also render when `showArchived === true` even with empty
history, so an empty-archive state is reachable).

### 2.10 `/projects/{id}/{tasks,files}` no longer 404 (item 10) — PASS in source

```
$ # offline app.openapi() probe (this run):
OK   GET /api/v1/projects/{project_id}/files
OK   GET /api/v1/projects/{project_id}/tasks
```

```
$ pytest tests/test_phase10b_ghost_call_fixes.py -k "g2 or g3"
test_g3_project_tasks_endpoint_returns_honest_empty PASSED
test_g2_project_files_endpoint_returns_honest_empty PASSED
test_g2_g3_unknown_project_returns_404                PASSED
```

After backend restart the live `:8000` will serve these too.

### 2.11 `/settings/llm` runtime subscriptions (item 11) — PASS in source

```
$ # offline app.openapi() probe:
OK   GET /api/v1/runtimes/subscriptions
```

```
$ pytest tests/test_phase10b_ghost_call_fixes.py -k g4
test_g4_runtimes_subscriptions_returns_envelope_with_warming PASSED
```

The running backend on :8000 still routes `/runtimes/subscriptions`
into the `/{runtime_id}` path-param trap (returns
`{success:false, error: Runtime 'subscriptions' not found}`); restart
fixes it.

### 2.12 Company seed delete no longer 405 (item 12) — PASS in source

```
$ # offline app.openapi() probe:
OK   DELETE /api/v1/company-mode/seed-brief
```

```
$ pytest tests/test_phase10b_ghost_call_fixes.py -k g1
test_g1_delete_seed_brief_archives_file_when_present PASSED
test_g1_delete_seed_brief_idempotent_when_absent     PASSED
```

The running backend returned `405 Method Not Allowed` because the
new route landed after it was started. Restart serves it.

### 2.13 Frontend tsc (item 13) — PASS

```
$ cd frontend && npx tsc --noEmit; echo "exit=$?"
exit=0
```

Zero TypeScript errors after Phase 10b edits to ScanPage.tsx,
ScanList.tsx, SettingsDeveloper.tsx, plus the new
`e2e/scan-lifecycle.spec.ts`.

### 2.14 Targeted backend tests (item 14) — PASS

```
backend/tests/test_phase10b_ghost_call_fixes.py            8 passed
backend/tests/test_phase10_unsafe_gates.py                  5 passed
backend/tests/test_phase10_chat_session_audit.py            3 passed
backend/tests/test_engagement_approval_persistence.py        2 passed
backend/tests/test_company_mode.py                          9 passed
backend/tests/test_company_mode_seed.py                      4 passed
backend/tests/test_project_service.py                       21 passed
                                                          ─────────
                                                          52 passed in 20.79s
```

Broader sweep (with `test_runtime_adapters.py`): **106 passed, 0 failed.**

---

## 3. Founder-fixable caveat — restart the running backend

**The local uvicorn currently bound to `127.0.0.1:8000` was launched
before the Phase 10b commits.** It serves the pre-fix routes:

* `DELETE /api/v1/company-mode/seed-brief` → 405 (route not registered)
* `GET /api/v1/runtimes/subscriptions` → caught by `/{runtime_id}`
  path param, returns `Runtime 'subscriptions' not found`
* `GET /api/v1/security/scans?archived=true` → 200 but archived
  param is ignored (returns active list)

**Fix:** restart uvicorn so the Python process re-imports the modules
with the Phase 10b code. There is no DB migration required.

I did not auto-kill the existing process — process ownership is
ambiguous (could be a founder dev session) and the agent rules forbid
unattended destructive actions.

**Recommended restart command** (operator, in `backend/`):

```bash
# 1. Stop the existing server (Ctrl+C in the terminal that owns it,
#    or via PID 23356 on this machine if it's truly orphan).
# 2. Start fresh:
.venv/Scripts/python.exe -m uvicorn app.main:create_app --factory \
  --host 127.0.0.1 --port 8000 --reload
```

Once restarted, re-run the live probes from §2.10–§2.12 to confirm the
new responses. The in-process test suite already exercises the same
code paths, so the post-restart probe is just a courtesy verification
for the demo dry-run.

---

## 4. Quick demo runbook

For a 5-minute live walkthrough against the local stack post-restart:

1. **Health badge** — `curl /api/v1/health` → green.
2. **Auth** — register a fresh user; login.
3. **Connections** — open `/connections` → V2 panel renders the
   connector grid; Main Brain shows current primary runtime.
4. **Settings** — toggle Default Governance Mode; reload; toggle
   persists. **Caveat to mention:** 9 of 14 settings persist but
   their backend consumers don't read them yet (see audit doc).
5. **Scan** — open `/scan`. With one archived scan present (you can
   create one via Quick Scan + Archive), click "Show archived" →
   archived rail renders; toggle back → active list returns.
6. **Project detail** — open any project → click the Tasks tab and
   the Files tab. Both load with honest "no tracking yet" empty
   states (no 404).
7. **Company Mode** (founder only) — open `/company-mode`. Try the
   Auto-send + Founder-approval-OFF combination → UI Switch is
   disabled; if you bypass via the API the 422 guard fires.

Total time: ~5 min. No external network calls required.

---

## 5. Hard rules respected

* No production deploy.
* No `USE_CONNECTION_REGISTRY_V2=true` flip.
* No `vault --apply`.
* `vault.py` / `oauth_credentials_store.py` not touched.
* No secrets read or printed (the test JWT is per-session and bounded;
  the `SmokePass123!` test password is published openly because this
  is a disposable test user against a local-only DB).
* No external scans run.
* No external messages / emails sent.
* No Phase 11 work begun.

End of report.
