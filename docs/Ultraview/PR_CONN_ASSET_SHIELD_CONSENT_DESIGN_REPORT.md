# PR-CONN-ASSET-SHIELD-CONSENT-DESIGN -- Report

**Branch:** `rebuild-connections-mcp-runtime`
**Commit:** (to be pinned)
**Date:** 2026-05-03
**Sprint:** DAENA-LOCAL-USABILITY-SPRINT-4 (PR-4 of 6)

---

## 1. Goal

Foundation for the Asset Shield consent layer that will gate Phase 3
write actions. Ships:

* Categorization function (any non-read-only skill maps to a risk class)
* In-memory `ConsentStore` with TTL + single-use semantics
* Executor-side `check_consent_or_request` gate (wired as Step 2 in
  `SkillExecutor.execute()` -- runs BEFORE the read_only defense)
* Executor `consent_store` kwarg for test isolation
* New `needs_consent` SkillExecutionStatus
* 24 tests across categorization / store / gate / E2E executor /
  PII defense / foundation invariant

The gate is **DORMANT for current Phase 2 entries** (every allowlist
entry is `read_only=True` so categorization returns `None`). The
synthetic-write tests prove the wiring works end-to-end without
enabling any actual write today.

---

## 2. Hard rules -- all honored

| Rule | Enforced? |
|---|---|
| Do not enable Phase 3 writes | YES -- Phase 2 read_only defense remains the hard wall after the consent gate. New `test_executor_consumes_consent_then_hits_phase2_defense` proves consent + write still blocks at the read_only check |
| Do not send anything | YES -- gate only ASKS for consent + records the request; no external HTTP fires |
| Do not execute browser actions | YES -- same |
| Do not change governance defaults | YES -- gate is additive; no existing flow's behaviour changes for read_only skills |
| Tests that write skills stay blocked without consent | YES -- `test_executor_blocks_synthetic_write_without_consent` |
| No PII in consent request/grant | YES -- both dataclasses pinned to (plugin, skill, category, UUID, timestamps); structural test forbids token-shaped fields |

---

## 3. Surface area

### `backend/app/services/connection_v2/skill_consent.py` (NEW)

* `SkillConsentCategory` enum: `READ_SENSITIVE` / `WRITE_EXTERNAL` /
  `SEND_MESSAGE` / `PAYMENT` / `BROWSER_ACTION` / `SECURITY_SCAN`
* `categorize_skill(entry)` pure function:
  - `read_only=True` -> `None`
  - Plugin-id hint table (Stripe -> PAYMENT, Slack/Gmail -> SEND_MESSAGE,
    Playwright/ChromeDevTools -> BROWSER_ACTION, etc.)
  - Skill-id substring hint (send/draft/delete/...)
  - Default for any non-read-only -> WRITE_EXTERNAL (conservative)
* `ConsentStore` -- in-memory grant store, TTL default 5 min, hard cap
  30 min, single-use, lazy-GC on read
* `SkillConsentRequest` -- crafted by the executor, surfaced to operator
* `SkillConsentGrant` -- operator's approval (single-use)
* `check_consent_or_request(entry, *, tenant_id, store)` -> `(allowed,
  category, request)` -- the executor-side gate

### `backend/app/services/connection_v2/skill_executor.py`

* New `consent_store` kwarg on `SkillExecutor.__init__`
* New Step 2 in `execute()`: consent gate
  - `read_only=True` skills -> categorize returns None -> gate skipped
  - Non-read-only without grant -> `needs_consent` outcome with the
    request blob in the operator-facing summary
  - Non-read-only with matching grant -> grant consumed, fall through
    to Step 3 (read_only defense, which still blocks today)
* New `SkillExecutionStatus = "needs_consent"` literal

### `backend/tests/test_skill_consent.py` (NEW)

24 tests across 6 logical sections:

1. **Categorization (8 tests)**: read_only / Stripe / Slack / Gmail /
   Playwright / skill-name substrings / unknown plugin defaults to
   WRITE_EXTERNAL
2. **ConsentStore semantics (5 tests)**: grant + find + acknowledge,
   scope mismatch, TTL clamp, expired-on-acknowledge, lazy-GC on find
3. **`check_consent_or_request` flow (3 tests)**: read_only allowed,
   missing-consent returns request, present-consent consumes
4. **PII / leak defense (2 tests)**: Request + Grant dataclasses pinned
   to non-token-shaped fields
5. **Foundation invariant (1 test)**: today every Phase 2 entry has
   `categorize_skill(e) is None`. A future write skill MUST update
   this test (proves the audit trail).
6. **End-to-end executor (5 tests)**: synthetic write without consent
   -> needs_consent; with consent -> grant consumed, hits Phase 2
   defense; read_only does NOT consult store (verified via
   ExplodingStore that raises if `find_active` is called); kwarg
   passthrough; default-store fallback

---

## 4. Foundation, not deployment

What this PR DOES:
* Wires the consent gate into the executor.
* Categorizes any future write skill into a known risk class.
* Provides the storage + check function the future approval-queue UI
  will write into / read from.
* Pins via tests that the gate is DORMANT today AND that wiring works
  for the future.

What this PR DOES NOT do:
* No write skill is enabled in `PHASE2_ALLOWLIST`. The Phase 2
  read_only defense remains the hard wall.
* No HTTP route added (`POST /v2/skill-consent` is for a future PR).
* No frontend modal -- the design lives in the operator-facing
  summary + the future approval-queue PR will render it.
* No DB-backed consent table (in-memory single-process today;
  multi-instance deployment is gated on the V2 production rollout).

---

## 5. Test result

```
$ .venv/Scripts/python.exe -m pytest tests/test_skill_consent.py
24 passed in 0.29s

$ .venv/Scripts/python.exe -m pytest tests/test_skill_executor_phase2.py \
                                     tests/test_oauth_invoker.py \
                                     tests/test_skill_executor_oauth_wireup.py \
                                     tests/test_oauth_account_profiles.py \
                                     tests/test_skill_consent.py
137 passed in 5.22s
```

Test growth Sprint-4 PR-4:
* End of PR-3: 64 phase2 + 21 oauth_invoker + 13 wireup + 12 account_profiles = 110
* PR-4 adds: 24 new consent + 3 net (existing executor tests now have to handle the new Step 2 path; all auto-passed because read_only=True skills skip the gate)
* Total in scope: **137 passing**

---

## 6. What did NOT change

* Phase 2 read-only entries -- all 14 promoted skills + remaining
  planned-only entries flow exactly as before. The consent gate is
  invisible to them (categorize returns None).
* Phase 3 write surfaces -- still impossible. The Phase 2 read_only
  defense at Step 3 catches any consent-bearing write attempt. Phase 3
  unlock is a future PR that flips that gate AND requires consent
  AND adds per-skill safety verification.
* The OAuth invoker, account-profile gate, MCP execution path -- all
  unchanged. Consent is a NEW step at the front of the pipeline.
* No new dependencies, no install, no production deploy.

---

## 7. Follow-up PRs

1. **`PR-CONN-CONSENT-API-AND-UI`** -- HTTP endpoint to mint grants
   (operator approval), drawer modal that POSTs an approval +
   re-runs the original skill request.
2. **`PR-CONN-CONSENT-DB-PERSISTENCE`** -- replace in-memory
   `ConsentStore` with DB-backed for multi-instance deployment.
3. **`PR-CONN-PHASE3-WRITE-SKILL-FRAMEWORK`** -- the actual Phase 3
   PR that lifts the read_only defense for consent-granted writes
   AND adds per-skill safety verification (e.g. dry-run preview,
   diff confirmation, undo path).
