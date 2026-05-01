# Phase 10 — Product Integration Verification Report

**Date:** 2026-05-01
**Operator:** Claude Code (Opus 4.7) under founder-direction interaction-audit
**Branch:** `rebuild-connections-mcp-runtime`
**Commits delivered in this run:**
- `c696f6a` — `phase10: fix unsafe action gates (U1+U2+U3) at REST boundary`
- `dc9d666` — `phase10: chat session audit emit + chat file-remove honest tooltip`
- `<this commit>` — `phase10: verification report + 9E synthesis docs`

---

## 0. TL;DR

| Layer | Before Phase 10 | After Phase 10 | Evidence |
|---|---|---|---|
| `POST /api/v1/security/scans/start` scope gate | none at REST (gate ran inside workflow Phase 0, post-job-create) | enforced at REST; 403 + `code=target_not_in_scope` for out-of-scope targets | `tests/test_phase10_unsafe_gates.py::test_u2_scan_start_blocks_out_of_scope_target` (pass) |
| `POST /api/v1/engagements` scope gate | unknown (delegated to agent — HANDS-OFF) | enforced at REST; 403 mirrors scan-start | `tests/test_phase10_unsafe_gates.py::test_u3_engagement_start_blocks_out_of_scope_target` (pass) |
| `POST /api/v1/company-mode/activate` `auto_send` + `require_founder_approval=false` | accepted, would dispatch external traffic without approval | refused at REST with 422 + `code=auto_send_requires_founder_approval` | `tests/test_phase10_unsafe_gates.py::test_u1_company_mode_autosend_without_approval_returns_422` (pass) |
| Company Mode UI form | could set the contradictory combination | `auto_send` Switch is `disabled` when approval is off; toggling approval off clears `auto_send`; helper text added | static evidence in `frontend/src/pages/CompanyModePage.tsx`; `npx tsc --noEmit` clean |
| Chat session rename / archive / unarchive / delete audit | zero ledger entries (Rule-17 honesty violation) | distinct `chat_session.{renamed,archived,unarchived,deleted}` rows in `goa_audit_events` | `tests/test_phase10_chat_session_audit.py` (3 tests pass) |
| Chat file X-button surface | implied destructive deletion (FAKE) | tooltip + aria-label state explicitly that X removes from draft only and the file remains in /files | static evidence in `ChatInput.tsx:619-633`; `npx tsc --noEmit` clean |

**Test result snapshot:**
```
backend/tests/test_phase10_unsafe_gates.py            5 passed
backend/tests/test_phase10_chat_session_audit.py      3 passed
backend/tests/test_engagement_approval_persistence.py 2 passed (patched for new gate)
backend/tests/test_company_mode.py                    11 passed (no regression)
backend/tests/test_security_dashboard_delete.py       <existing> passed
                                                      ─────────
                                                      21+ passed, 0 failed in this scope
```

**Frontend:** `npx tsc --noEmit` exits 0. No lint or type regressions.

---

## 1. Phase 9 reality check (a methodology correction the founder must see)

**This is the most important section of this report. It must be read before acting on any Phase 9 finding.**

During Phase 9C live trace I instrumented `window.fetch` and concluded that clicking "Governed" mode in `/settings/governance` produced **zero network calls** — i.e. the setting was localStorage-only and the backend never saw it (FAKE persistence). On that basis, Phase 9B classified ~25 of 47 settings as FAKE and the multi-model review devoted four commits (2A/2B/2C/2D) to a settings-persistence migration.

**The methodology was wrong.** Daena's `lib/api.ts` axios instance uses XMLHttpRequest, not the Fetch API. My `window.fetch` hook silently missed every axios PUT. While running Phase 10 commit-2A I verified the round-trip directly against the live backend:

```
> PUT /api/v1/settings/user {default_governance_mode: 'UNLEASHED'}
< 200
> GET /api/v1/settings/user
< { ..., default_governance_mode: 'UNLEASHED' }
```

The setting **does** persist end-to-end. Cross-checked against the source: every `persistUiPref(...)` call site in `frontend/src` uses a key that is in the backend's `_UI_PREF_KEYS` whitelist (`backend/app/api/v1/settings.py:136-154`), and `persistUiPref` itself debounces 500 ms then issues `PUT /settings/user` (`uiStore.ts:294-304`). The backend writes to `users.settings` JSONB, the GET endpoint returns it, and `hydrateUiFromBackend` reads it on app load.

**What was actually broken vs. what I claimed was broken:**

| Phase 9B claim | Reality | What's actually broken (if anything) |
|---|---|---|
| 25 settings are FAKE because they don't persist | Persistence works end-to-end | The downstream-read at the *consuming* services (chat orchestrator, ModelRouter, cost-tracker, notification emitter) — does the backend actually USE the persisted values? Many likely don't, and *that's* the real gap. |
| `daena:governanceMode` localStorage-only | localStorage is a cache; PUT/GET round-trips correctly | Whether SecurityGate / orchestrator reads `user.settings.default_governance_mode` instead of a hardcoded default. Unverified — punt to Phase 11. |
| Cost-aware routing toggle is FAKE | Toggle persists | Whether ModelRouter reads `user.settings.cost_aware_routing`. Unverified. |
| Notification toggles are FAKE | Toggles persist | Whether the (currently absent) notification emitter reads them. The emitter doesn't exist yet — that's the Phase 11+ feature. |

**Implication:** Phase 10 commits 2A / 2B / 2C / 2D as scoped in the multi-model synthesis are **not necessary**. The persistence layer already works. The next-step work, if the founder wants it, is the **downstream-read audit** — which services should read which settings, and wiring them. That is its own discovery + design + implementation cycle, not a 4-commit settings migration.

**Why this matters:** if I had blindly executed commits 2A–2D as planned, I would have introduced a parallel `settingsStore` slice that re-writes the same setting through a different code path, doubling the persistence calls and risking write-clobber races between the new store and existing `persistUiPref`. That regression would have been caused by a bad audit, not a real product gap.

**Founder action required (not blocking):** confirm the corrected scope. The Phase 9B matrix entries marked FAKE for `persistUiPref`-using settings should be re-classified as **PARTIAL — persists, downstream-read TBD**.

---

## 2. What Phase 10 actually shipped (in this run)

### Commit 1 — `phase10: fix unsafe action gates (U1+U2+U3) at REST boundary`

**Backend:**
- `backend/app/api/v1/security_dashboard.py` — `start_scan` now requires `Depends(get_current_user)` (was using hardcoded `user_id="system"`, `tenant_id="default"`; **anyone could scan anything** previously). Added scope check via `target_matches_scope(body.target, load_authorized_scope(tenant_id))` BEFORE workflow dispatch. Returns 403 with `{code: "target_not_in_scope", target, hint}` when out-of-scope.
- `backend/app/api/v1/engagements.py` — same scope check at REST boundary; defense-in-depth even if the agent enforces internally.
- `backend/app/api/v1/company_mode.py` — server-side guard refuses `auto_send=true` + `require_founder_approval=false` with 422.

**Frontend:**
- `frontend/src/pages/CompanyModePage.tsx` — `auto_send` Switch is `disabled={!req.require_founder_approval}`; toggling approval off clears `auto_send`; helper text states the rule.

**Tests:**
- 5 new tests in `backend/tests/test_phase10_unsafe_gates.py` (all pass).
- Patched `backend/tests/test_engagement_approval_persistence.py` to opt into a fixture scope (the existing test pre-dated the new gate; added `with patch(load_authorized_scope, return_value=AuthorizedScope(exact_domains=...))`).

**Live evidence (Phase 9C):** before this commit, posting `{target:"out-of-scope-target.example.com", tier:"SCOUT"}` returned **200 queued + a job_id**. After this commit, the same request returns **403** before the workflow ever runs. Founder rule "no external scans" hardened.

### Commit 4 — `phase10: chat session audit emit + chat file-remove honest tooltip`

**Backend (`backend/app/api/v1/chat.py`):**
- `update_session` (PATCH) now appends a `goa_audit_events` row with a distinctive `action_type`:
  - `chat_session.archived` (when `is_archived=true`)
  - `chat_session.unarchived` (when `is_archived=false`)
  - `chat_session.renamed` (when `title` is set)
  - `chat_session.updated` (any other metadata change)
- `delete_session` (DELETE) appends `chat_session.deleted`.
- Audit emit is best-effort: failures are warning-logged but never block the user mutation (Codex review recommendation).

**Frontend (`frontend/src/components/chat/ChatInput.tsx`):**
- Attached-file chip's tooltip + the X button's aria-label now explicitly state: "remove from this draft only. The file remains in /files."
- This is the Option C resolution from the Phase 9E synthesis — keep current behavior, label it honestly. Anything stronger (true detach+delete) is queued for Phase 10b.

**Tests:**
- 3 new tests in `backend/tests/test_phase10_chat_session_audit.py` (all pass).
- Verifies rename / archive / unarchive each emit distinct action types; delete emits its own type AND the session is soft-archived (not hard-deleted).

### Commit 5 (this commit) — `docs`

This file. Plus:
- `docs/Ultraview/PHASE_9_TOOLING_READINESS.md` (9A)
- `docs/Ultraview/UI_ACTION_CONTRACT_MATRIX.md` (9B — 158-action matrix)
- `docs/Ultraview/PHASE_9C_PLAYWRIGHT_TRACE_REPORT.md` (9C — with the methodology-error correction noted in §1)
- `docs/Ultraview/PHASE_9D_OPENAPI_CONTRACT_REPORT.md` (9D — 4 real ghost calls)
- `docs/Ultraview/PHASE_9_REVIEW_PACK.md` (9E.1 — sanitized pack sent to reviewers)
- `docs/Ultraview/PHASE_9_MULTI_MODEL_REVIEW.md` (9E.2 — Codex + Gemini + Perplexity synthesis)
- `docs/Ultraview/PHASE_9_PERPLEXITY_RAW.md` (9E raw Perplexity output + 8 citations)
- `docs/Ultraview/openapi-live.json` (live spec, 362 KB, 396 ops)
- `docs/Ultraview/openapi-diff.json` (programmatic diff, 28 KB)

---

## 3. What was NOT done in this run (Phase 10b backlog)

Per the multi-model review's chairman synthesis, the original 5-commit plan expanded to a 7-commit plan plus polish micro-commit. This run shipped Commits 1, 4, and 5. The remaining 5 commits did NOT ship in this session — and the §1 reality check changes the value proposition for several of them. Re-prioritized:

| ID | Original commit | Re-prioritized status |
|---|---|---|
| 2A | Governance mode persistence | **DOWNGRADE — already works.** Re-scope to "verify SecurityGate reads `user.settings.default_governance_mode`" and wire if not. |
| 2B | Routing + chat-mode defaults persistence | **DOWNGRADE — already works.** Same shape as 2A. Re-scope to "verify ModelRouter reads `user.settings.{local_first_routing,cost_aware_routing,default_routing_mode}`." |
| 2C | Billing budget + over-budget action persistence | **DOWNGRADE — already works.** Re-scope to "verify `cost_tracker` reads `user.settings.{monthly_budget,budget_alert_threshold,over_budget_action}`." |
| 2D | Notification + privacy toggle persistence | **DOWNGRADE — already works.** Real gap is that the notification emitter doesn't exist yet (separate Phase 11 feature). |
| 3 | Scan rerun button + report-ready notification + show-archived toggle | **STILL VALID.** `frontend/src/pages/ScanPage.tsx:212` has the `rerunScan()` handler; no UI button calls it. Phase 9B + 9E both confirmed. ~1-hour fix. |
| 5 | Archive-primary delete-secondary UI grammar | **STILL VALID** for policies (currently hard-deletes; should be soft-archive). Lower priority than 3. |
| 6 | Global Sync Status navbar indicator | **STILL VALID** as Gemini's novel UX contribution, but the §1 reality check makes it less urgent — there's no FAKE-cluster to surface anymore. |
| Audit emit for tasks + files | Per Codex test-priority order #8 | **STILL VALID.** Mirrors the chat-session audit pattern from commit 4. ~1 hour total. |
| OpenAPI ghost-call fixes (G1-G5) | Phase 9D | **STILL VALID.** 4 real broken calls: `DELETE /company-mode/seed-brief`, `GET /projects/{id}/files`, `GET /projects/{id}/tasks`, `GET /runtimes/subscriptions`. Each ~10-20 LOC backend or 1-line frontend deletion. |

---

## 4. Verified working (with citations)

Each claim links to a test or live trace.

- **U2 scan REST scope gate enforced** — `tests/test_phase10_unsafe_gates.py:test_u2_scan_start_blocks_out_of_scope_target` (passing).
- **U3 engagement REST scope gate enforced** — same file: `test_u3_engagement_start_blocks_out_of_scope_target` (passing).
- **U1 Company Mode contradiction refused at REST** — same file: `test_u1_company_mode_autosend_without_approval_returns_422` + safe-combos test (passing).
- **U1 Company Mode UI guard** — static: `frontend/src/pages/CompanyModePage.tsx:553-575` (Switch `disabled={!req.require_founder_approval}` + helper text).
- **Chat session rename audit emit** — `tests/test_phase10_chat_session_audit.py:test_chat_session_rename_writes_audit_row`.
- **Chat session archive vs unarchive distinct audits** — same file: `test_chat_session_archive_unarchive_writes_distinct_audit_rows`.
- **Chat session delete audit + soft-archive** — same file: `test_chat_session_delete_writes_audit_row`.
- **Chat file X-button honest semantics** — static: `frontend/src/components/chat/ChatInput.tsx:619-633`.
- **Settings persistence end-to-end (governance mode example)** — live trace this run: `PUT /settings/user {default_governance_mode:'UNLEASHED'}` → 200; subsequent GET returns the new value.
- **Local backend health** — `GET /api/v1/health` returns `{status:"healthy", database:"healthy", essentials_ready:true, seedings_complete:true}`.
- **OpenAPI live spec accessible** — `docs/Ultraview/openapi-live.json` (396 ops; saved this run).
- **Frontend typecheck clean** — `npx tsc --noEmit` exits 0 after all Phase 10 changes.

---

## 5. Remaining fake / dead / unknown (post-Phase-10)

- **Connection V2 panel for fresh tenants** — empty until detection-seed or Provider-Seed lands. Real UX gap (Phase 9C confirmed). Phase 6 backlog item.
- **Re-run Scan button** — handler exists, button doesn't (Phase 9B BROKEN; Phase 10b commit-3).
- **Webhooks form** — intentionally disabled. Backend route unbuilt. Status: DEAD by design.
- **Email notifications** — intentionally disabled. SMTP not wired.
- **Policy hard-delete** — still hard-delete (Phase 9B PARTIAL; Phase 10b commit-5).
- **Scan report-ready notification** — no UI signal (Phase 9B PARTIAL; Phase 10b commit-3).
- **3 V1↔V2 connection surface duplicates** — still present until V2 prod-flag flips (per founder rules, V2 stays `false` in prod for now).
- **Downstream consumer reads** of `user.settings` (governance mode, routing toggles, budget) — the new uncertainty surfaced by §1's correction. Each consumer needs a separate verification + wire pass.

---

## 6. Top remaining UX pain (in priority order)

1. **Founder still can't tell which settings actually affect behavior.** Even now that I've confirmed they persist, the question "did this setting change anything in the pipeline?" has no UI answer. Gemini's "Global Sync Status" indicator (Phase 10b commit-6) addresses the persistence visibility, but a richer "this setting is consumed by service X" indicator would be more honest about the §1 gap.
2. **Re-run Scan dead button** — easy fix, high visibility (Phase 10b commit-3).
3. **Scan report-ready notification missing** — user has to babysit the page (Phase 10b commit-3).
4. **Connection V2 empty for fresh tenants** — first impression problem.
5. **The 4 OpenAPI ghost calls** — UI features that 404/405 silently. Each is a small repair.

---

## 7. Local product-readiness assessment

**Local Daena is product-ready for: founder + invited testers** with a documented "settings persist; downstream-consumption being verified" caveat.

| Demo flow | Safe to show? | Notes |
|---|---|---|
| Sign in → /chat → send message | YES | Per Phase 9C live trace (modulo LLM availability) |
| /governance/audit → verify chain → filter | YES | Verified working via Phase 9B + audit infrastructure mature |
| /security/scope → add target → save | YES | Verified working in Phase 9B |
| /scan → start scan | YES, **now safe** | Phase 10 commit-1 enforces scope; out-of-scope returns 403 |
| /company-mode → activate | YES, **now safe** | Phase 10 commit-1 prevents the auto_send/approval contradiction |
| /connections → install MCP / connect provider | YES | Verified in Phase 9B + Phase 5 reports |
| /settings any-tab change → reload → verify persist | YES | Settings DO persist (per §1 correction) |
| /tasks lifecycle | PARTIAL | UI works; create-via-API has schema mismatch (Phase 9C N3) — UI form sends required fields; bare API call may not |

## 8. Cloud `daena-v2` demo safety

Status from prior reports (`CLEAN_GCLOUD_REBUILD_CORS_FIX_REPORT.md`): cloud `daena-v2` is healthy, readiness 17/17 PASS, CORS fixed, `USE_CONNECTION_REGISTRY_V2=false`.

**Phase 10 changes do NOT need to deploy to cloud for the demo to be safe** — the U1/U2/U3 gates are in code that hasn't shipped to `daena-v2` yet. **For a public-facing cloud demo, the Phase 10 commits MUST land in the next image build before serving traffic.** Per founder rules: "Do not deploy production." → next image build is a separate founder-approved cycle.

If the demo is browser-against-cloud: Phase 10 commits do not protect that demo until they ship. **Recommendation:** demo against local for now; cloud demo waits for a `phase10` image build under explicit founder approval.

## 9. Honest disclosures + transparency notes

- **Commit `c696f6a` bundles pre-existing in-flight branch work along with my P0 changes.** The `git add` of named files swept the full working-tree state — those files (`security_dashboard.py`, `engagements.py`, etc.) had pre-existing uncommitted edits from prior connections-rebuild work. The +853/-141 line count is misleading; my P0 contribution is on the order of ~80 net lines. I verified my edits *are* present in the commit (grep confirmed `target_not_in_scope`, `auto_send_requires_founder_approval`, `disabled={!req.require_founder_approval}` all landed). Going forward, commits should `git diff HEAD <file>` before staging to filter pre-existing edits — I did this for `dc9d666` (262/5, much closer to actual changes).
- **Phase 9C methodology error documented in §1.** This corrects the 25-FAKE-settings finding to "persistence works; downstream-read TBD."
- **No production deploy this run.** No GCP touch.
- **No `USE_CONNECTION_REGISTRY_V2=true` flip.**
- **No `vault --apply`** run.
- **No `vault.py` / `oauth_credentials_store.py`** touched.
- **No secrets read or printed.** Test JWTs are per-session and bounded.
- **No external network scans run.** The "out-of-scope target" used in tests + live trace was `out-of-scope-target.example.com` (IETF-reserved doc TLD).
- **One alembic migration run on the local SQLite dev DB** (004 → 007). Production schema is unaffected.
- **External-model review pack** (`PHASE_9_REVIEW_PACK.md`) was sanitized: no secrets, no env values, no tokens, no Cloud Run config. Codex / Gemini / Perplexity received only audit findings + sanitized file:line references.

---

## 10. Exact next actions (in priority order)

1. **Founder reads §1 reality check** and confirms the corrected scope (matrix re-classifications: 25 FAKE → PARTIAL persists / downstream-read TBD).
2. **Cloud demo decision:** local-only for now, OR queue a `phase10` image build under explicit approval.
3. **Phase 10b commit-3 (Re-run Scan button + report-ready notification + show-archived toggle)** — highest user-visible win, ~1 hour. Safe to autonomous if approved.
4. **OpenAPI ghost-call fixes (G1-G5)** — small repairs; G1 is highest-impact (`DELETE /company-mode/seed-brief` 405 today; founder-facing).
5. **Phase 11 discovery: downstream-consumer-read audit.** Define which settings each service reads from `user.settings`. Without this, even though the FAKE-settings flag was wrong about persistence, the founder's underlying concern ("does the system act on what I told it?") is unanswered.
6. **Add Playwright e2e for the P0 gates** so future regressions surface immediately. Codex's test priority order: U2 → U3 → U1 → governance-persistence E2E (now: governance-CONSUMPTION E2E) → ...
7. **Add audit emit to tasks + files** — same shape as the chat session audit emit in commit 4. ~1 hour.
8. **Eventually: Phase 10b commit-5** (policy soft-archive) and **commit-6** (Global Sync Status indicator).

End of report.
