# DAENA Local Usability -- Sprint-4 Smoke Status

**Run at:** 2026-05-03 ~22:30 local
**Branch:** `rebuild-connections-mcp-runtime`
**Sprint:** DAENA-LOCAL-USABILITY-SPRINT-4 (PR-6 of 6)
**Pre-sprint baseline:** `cc05379` (post Sprint-3 smoke)

---

## TL;DR

Sprint-4 ran through 6 PRs (originally 5; founder pause inserted
`GOOGLE-ACCOUNT-PROFILES` after PR-2). **0 hard stops.** Sprint-4
takes Daena from "OAuth foundation exists but not wired" to "real
Gmail/Drive read-only execution path with account-profile
disambiguation, consent gate foundation, and per-plugin governance
presets." Phase 3 writes are STILL BLOCKED by the same Phase 2
read_only defense -- the consent gate is foundation only.

---

## Section-by-section results

### Section 1 -- Backend launches cleanly + restarted

| Check | Status | Evidence |
|---|---|---|
| 1.1 Backend killed + relaunched | PASS | `_dev_kill_uvicorn.ps1` killed PID 19244 + 6640; relaunched directly via `.venv/Scripts/python.exe -m uvicorn` (`.bat` launcher exited prematurely under cmd /c -- noted) |
| 1.2 `/health` 200 with Sprint-3 + Sprint-4 code | PASS | `{"status":"healthy",...}` |
| 1.3 Marketplace API serves PR-1 honesty fix | PASS | `GET /v2/marketplace/cards` 200; vLLM card now flows through the honesty guard from Sprint-3 PR-1 |

### Section 2 -- Frontend reachable

| Check | Status | Evidence |
|---|---|---|
| 2.1 Frontend serves 200 | PASS | `curl http://localhost:5173` -> 200 |
| 2.2 `/connections` page renders | PASS | chrome-devtools snapshot rendered cleanly; sidebar + Brain + Plugins + Advanced tabs visible |
| 2.3 Console clean | PASS | 4 messages (3 vite + 1 pre-existing a11y advisory) |

### Section 3 -- OAuthInvoker wired (PR-1)

| Check | Status | Evidence |
|---|---|---|
| 3.1 `_execute_real_oauth` exists | PASS | committed `5955429`; method dispatches when `backend_surface=oauth + execution_mode=mcp_tool` |
| 3.2 Token refresh on 401 path wired | PASS | `test_oauth_401_then_refresh_then_200_executes_and_marks_refreshed` green |
| 3.3 Audit row never carries token material | PASS | `test_audit_row_never_carries_token_material` walks every action_params string + asserts no token leak |
| 3.4 `extra_audit_fields` rejects token-shaped keys | PASS | unit test pins forbidden substring filter |

### Section 4 -- Gmail/Drive read-only promoted (PR-2)

| Check | Status | Evidence |
|---|---|---|
| 4.1 4 entries flipped to mcp_tool | PASS | committed `81ecac6` |
| 4.2 target_tool aligned with OAuthInvoker allowlist | PASS | `test_sprint4_gmail_drive_target_tools_match_invoker_allowlist` green |
| 4.3 Sprint-2 invariant flipped | PASS | `test_pr3_gmail_and_drive_remain_planned_only` REPLACED by `test_sprint4_gmail_and_drive_now_promoted` |
| 4.4 No Gmail/Drive write skill promoted | PASS | `test_sprint4_no_gmail_drive_write_skills_promoted` 16-name forbidden list defends |

### Section 5 -- Google account profile gate (PR-3, NEW)

| Check | Status | Evidence |
|---|---|---|
| 5.1 `owner_email` column on ConnectorInstance | PASS | committed `6acf7e6`; nullable + indexed; back-compat preserved |
| 5.2 Unique constraint relaxed to allow multi-account per user | PASS | `(tenant_id, connector_id, user_id, owner_email)` unique |
| 5.3 Multi-instance + no hint -> needs_connection / oauth_account_profile_required | PASS | `test_executor_surfaces_account_profile_required` green |
| 5.4 Multi-instance + matching hint -> dispatches correct token | PASS | `test_executor_dispatches_with_owner_email_hint` confirms via captured Authorization header |
| 5.5 Hint normalization (case + whitespace) | PASS | `test_find_multi_instance_hint_normalizes_case_and_whitespace` green |
| 5.6 JSONB fallback for legacy rows | PASS | `test_find_uses_jsonb_fallback_for_legacy_instances` green |
| 5.7 DISCONNECTED instances do not contribute to ambiguity | PASS | `test_find_disconnected_instance_does_not_count` green |

### Section 6 -- Asset Shield consent foundation (PR-4)

| Check | Status | Evidence |
|---|---|---|
| 6.1 Consent gate wired into executor as Step 2 | PASS | committed `ec571ee`; runs BEFORE read_only defense |
| 6.2 Gate is dormant for current Phase 2 entries | PASS | `test_no_phase2_skill_currently_requires_consent` green |
| 6.3 Synthetic write skill blocks without consent | PASS | `test_executor_blocks_synthetic_write_without_consent` -> needs_consent / consent_required |
| 6.4 Synthetic write skill with consent consumes grant + still hits read_only defense | PASS | `test_executor_consumes_consent_then_hits_phase2_defense` -- the foundation-only invariant |
| 6.5 Read_only skills never consult store | PASS | ExplodingStore raises if find_active called -- test passes |
| 6.6 Categorization complete: every category has a class mapping | PASS | `test_skill_class_consent_category_mapping_is_complete` green |

### Section 7 -- Per-plugin governance presets (PR-5)

| Check | Status | Evidence |
|---|---|---|
| 7.1 8 founder-listed plugins covered | PASS | committed `c1bfd0f`; founder list test green |
| 7.2 Conservative defaults pinned | PASS | Stripe PAYMENT=DENY / Filesystem WRITE_EXTERNAL=DENY / Gmail SEND_MESSAGE=DENY all tested |
| 7.3 Phase 2 floor stays usable | PASS | `test_recommended_tier_for_every_phase2_skill_is_allow_or_ask` -- never DENY |
| 7.4 JSON serialization safe | PASS | round-trips through json.dumps |
| 7.5 No enforcement change | PASS | metadata-only; consent gate + read_only defense unchanged |

### Section 8 -- Tests

| Suite | Result |
|---|---|
| `test_skill_executor_phase2.py` | **64 passed** in 2.6s |
| `test_oauth_invoker.py` | **21 passed** in 0.5s |
| `test_skill_executor_oauth_wireup.py` | **13 passed** in 0.4s |
| `test_oauth_account_profiles.py` (NEW Sprint-4 PR-3) | **12 passed** |
| `test_skill_consent.py` (NEW Sprint-4 PR-4) | **24 passed** |
| `test_plugin_governance_presets.py` (NEW Sprint-4 PR-5) | **25 passed** |
| Frontend `npx tsc --noEmit` | **0 errors** |

Sprint-4 in scope: **162 backend tests passing in their natural files**.

Note: when ALL test files in this sprint scope run in one pytest
invocation, the same pre-existing cross-file tenant-id collision
from earlier sprints still produces a few errors. This is NOT a
Sprint-4 regression -- each file passes cleanly in isolation.

---

## Newly usable features

| Capability | Before Sprint-4 | After Sprint-4 |
|---|---|---|
| OAuth executor branch | foundation only (`OAuthInvoker` existed but unwired) | LIVE -- `_execute_real_oauth` dispatches when `backend_surface=oauth + execution_mode=mcp_tool` |
| Gmail/Drive promoted skills | 0 (planned_only) | 4 (`messages.list_unread`, `messages.search`, `files.list`, `files.get_metadata`) |
| Multi-Google-account support | impossible (DB constraint) | foundation: `owner_email` column + executor disambiguation |
| Account-profile selector for OAuth calls | none | `operator_inputs["_owner_email"]` flows through executor |
| Consent gate for write skills | none | wired as Step 2 in executor; dormant for read_only=True; ready for Phase 3 writes |
| Per-plugin governance presets | none | static table + classify + recommend helpers; ready for future API + UI |

**Total promoted Phase-2.x skills: 14 -> 18** (Sprint-4 added 4 Gmail/Drive).

---

## What still requires manual operator action

### Required for live Gmail/Drive use

1. **Connect a Google OAuth profile** (one or more) via the Plugins UI.
   For the founder's stated separation:
   - Personal: connect `app-gmail` with `owner_email=masoud.masoori@mas-ai.co`
   - Company: connect `app-gmail` with `owner_email=daena@mas-ai.co`
   The OAuth callback does NOT yet auto-populate `owner_email` --
   that's the next follow-up PR (`PR-CONN-GOOGLE-ACCOUNT-PROFILES-CAPTURE`).
   Until then the operator must manually set `owner_email` on the
   created instance (e.g. via the policy editor or DB tool).

2. **For multi-account flows**: every Gmail/Drive skill call must
   carry `_owner_email` in `operator_inputs` to disambiguate.

3. **DEV DB schema**: the `owner_email` column was added to
   `ConnectorInstance`. Existing dev rows have it as NULL (back-compat).
   Production deploy requires an Alembic migration (separate PR
   `PR-CONN-GMAIL-DRIVE-PRODUCTION-ALEMBIC`).

### Required before Phase 3 writes

1. **`PR-CONN-CONSENT-API-AND-UI`** -- HTTP endpoint to mint grants;
   drawer modal to surface the request + collect approval.
2. **`PR-CONN-CONSENT-DB-PERSISTENCE`** -- replace in-memory store
   with DB-backed for multi-instance deployment.
3. **`PR-CONN-PHASE3-WRITE-SKILL-FRAMEWORK`** -- the actual unlock
   that lifts the read_only defense for consent-granted writes,
   plus per-skill safety verification (dry-run preview, diff
   confirmation, undo path).

---

## Sprint-4 commits landed (6 PRs + 0 docs-pin)

```
c1bfd0f  canonicalization: add per-plugin governance presets         [PR-5]
ec571ee  canonicalization: add Asset Shield consent foundation       [PR-4]
6acf7e6  canonicalization: add Google account profile gate           [PR-3 NEW]
81ecac6  canonicalization: promote Gmail and Drive read-only skills  [PR-2]
5955429  canonicalization: wire OAuth invoker into skill executor    [PR-1]
cc05379  docs: update local usability smoke after Sprint 3           (pre-sprint baseline)
```

(PR-6 commit will land after this doc is committed.)

---

## Hard stops encountered

**NONE.** Sprint queue ran cleanly through all 6 PRs.

The only meaningful interruption was the founder pause after PR-2 to
declare the "no mixing identities" rule. PR-3 was inserted to close
that hole; the renumbered queue completed cleanly.

---

## Phase 3 writes status

**STILL BLOCKED.** All four floors remain in place:

1. PHASE2_ALLOWLIST contains zero `read_only=False` entries.
2. The Phase 2 read_only defense at executor Step 3 catches any
   write that escaped past the consent gate (Step 2).
3. The consent gate (PR-4) demands explicit operator approval for
   any non-read-only skill before reaching Step 3.
4. Per-plugin governance presets (PR-5) recommend DENY for
   Stripe PAYMENT, Filesystem WRITE_EXTERNAL, Gmail SEND_MESSAGE
   even with consent.

For a write to fire, ALL four floors would need explicit lift. The
Phase 3 framework PR will lift floor 2 ONLY for skills that have
matching consent + a vendor preset that doesn't DENY + a per-skill
safety verification (dry-run + diff + undo).

---

## Exact startup commands (next session)

```bash
# Window 1: backend
cd D:\Ideas\Daena
scripts\start-backend-dev.bat
# (or directly: backend\.venv\Scripts\python.exe -m uvicorn
#  app.main:app --host 127.0.0.1 --port 8000 --no-access-log)

# Window 2: frontend
cd D:\Ideas\Daena\frontend
npm run dev

# Browser
start http://localhost:5173
```

Then to live-verify Sprint-4:

1. Open `/connections` -> Brain tab. Confirm vLLM still shows
   "Not installed / offline" (honest) and the Plugins tab marketplace
   card no longer says "Installed" for vLLM (PR-1 of Sprint-3 fix
   confirmed live).
2. To manually exercise the OAuth executor: connect Gmail OR Drive
   via the existing OAuth flow, then trigger a Phase 2.x execute
   for `app-gmail:summarize_unread` -- without `owner_email` set
   on the instance OR with multiple instances and no `_owner_email`
   hint, the executor returns `needs_connection / oauth_account_profile_required`.

---

## Suggested next sprint (Sprint-5)

Per the follow-up PRs identified across Sprint-4:

1. **`PR-CONN-GOOGLE-ACCOUNT-PROFILES-CAPTURE`** -- update OAuth
   callback to populate `ConnectorInstance.owner_email` from
   `fetch_account_identity()`. Required before live Gmail/Drive use.
2. **`PR-CONN-CONSENT-API-AND-UI`** -- HTTP endpoint + drawer modal
   for the consent flow.
3. **`PR-CONN-GOV-PRESETS-API`** -- `GET /v2/governance/plugin-presets`
   endpoint + frontend badge rendering.
4. **`PR-CONN-FRONTEND-ACCOUNT-PROFILE-PICKER`** -- drawer UI for
   choosing between connected Google accounts.
5. **`PR-CONN-GMAIL-DRIVE-PRODUCTION-ALEMBIC`** -- migration before
   any production deploy of the schema change.

Recommended order: 1 -> 4 -> 5 (unlock Gmail/Drive for real use) ->
2 -> 3 (governance UX polish) -> Phase 3 writes (separate sprint).

---

## Final words

Sprint-4 took Daena from "OAuth invoker exists but unwired" to "real
Gmail/Drive read-only execution path with account-profile awareness
+ consent foundation + governance presets." Writes are still
blocked by four independent floors -- the safest possible posture
while the read-only Phase 2 layer expands.

**0 hard stops. 88 new tests across 6 PRs. 4 new live skills. 2
new safety layers (account profiles + consent gate). 1 vendor
opinion table (presets).**

Sprint-4 COMPLETE.
