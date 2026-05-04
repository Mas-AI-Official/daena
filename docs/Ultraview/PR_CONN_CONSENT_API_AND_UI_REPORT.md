# PR-CONN-CONSENT-API-AND-UI -- Report

**Branch:** `rebuild-connections-mcp-runtime`
**Commit:** (to be pinned)
**Date:** 2026-05-03
**Sprint:** DAENA-LOCAL-USABILITY-SPRINT-5 (PR-4 of 6)

---

## 1. Goal

Expose the Sprint-4 PR-4 Asset Shield consent foundation through:

* A narrow HTTP surface (categories metadata + grant minting)
* A modal section in `SkillExecuteModal` that surfaces when the
  executor returns `status="needs_consent"`

The consent layer was DORMANT after Sprint-4 PR-4 -- the in-memory
store + executor gate existed but no UI / API path could mint a grant.
This PR closes that loop WITHOUT enabling any write skill: the Phase 2
read_only defense remains the actual hard wall.

---

## 2. Hard rules -- all honored

| Rule | Enforced? |
|---|---|
| Do not enable writes | YES -- `test_consent_does_not_unlock_phase2_read_only_defense` proves a synthetic write skill stays blocked even with consent in hand |
| Consent endpoint can mint grants, but executor still blocks writes at read_only defense | YES -- `phase2_write_blocking_active=True` in every category descriptor; pinned by test |
| Modal must say consent does not override write blocking yet | YES -- modal copy: "Granting consent records your approval and lets the executor pass the consent gate. It does NOT enable writes -- Phase 2 still blocks any non-read-only skill" |
| No sends / payments / browser actions | YES -- this PR only adds metadata + grant-minting routes; no external HTTP / no plugin dispatch |
| Single-use TTL behavior preserved | YES -- the API delegates to the existing `ConsentStore.grant`; tests confirm grants are consumed on first executor pass |

---

## 3. Surface area

### Backend

#### `backend/app/api/v1/skill_consent_api.py` (NEW)

* `GET /api/v1/connections/v2/skill-consent/categories`
  * Auth-required.
  * Returns 6 categories with operator-facing copy + the
    `phase2_write_blocking_active=True` global flag.
  * No tenant state -- pure metadata, safe to cache.
* `POST /api/v1/connections/v2/skill-consent/grant`
  * Auth-required.
  * Body: `{plugin_id, skill_id, category, ttl_seconds?}`.
  * Tenant binding pulled from JWT, never the body.
  * Schema-level TTL cap (Pydantic `le=MAX_GRANT_TTL_SECONDS`) -> 422
    on over-cap requests; no silent clamping.
  * Returns the new grant_id + expires_at + the operator_notice
    explaining "Phase 2 still blocks writes".

#### `backend/app/api/v1/__init__.py`

* New router import + mount at `/connections/v2/skill-consent`.

### Frontend

#### `frontend/src/pages/connections/SkillExecuteModal.tsx`

* `SkillExecutionResultDTO.status` union extended with `'needs_consent'`.
* New `CONSENT_CATEGORIES` static array (mirrors backend enum).
* When result is `needs_consent`, an amber section renders:
  * Plain-language statement: "Granting consent records your
    approval... It does NOT enable writes."
  * `<select>` for risk category (default `write_external`).
  * "Grant consent (Phase 2 still blocks writes)" button.
* `handleGrantConsent` POSTs to `/skill-consent/grant`, then re-runs
  the skill so the operator immediately sees the next decision (the
  read_only defense kicks in for write-class skills).
* Modal copy + button label make it impossible for the operator to
  miss the "still blocked" semantic.

### Tests

#### `backend/tests/test_skill_consent_api.py` (NEW, 9 tests)

1. **GET categories returns 6 with phase2 warning (1)**: code list +
   `phase2_write_blocking_active=True` + non-empty operator copy.
2. **GET categories requires auth (1)**.
3. **POST grant binds to JWT tenant (1)**: tenant_id NEVER read from
   body; direct store inspection confirms binding.
4. **POST grant requires auth (1)**.
5. **Grant + executor share the same store (1)**: API mints, gate
   sees the grant + consumes on first call.
6. **Consent does NOT unlock Phase 2 (1)**: end-to-end through
   `SkillExecutor.execute()`; synthetic write skill stays blocked
   even with fresh grant -- proves the read_only defense remains
   the hard wall.
7. **Response payload safe (1)**: no `access_token` /
   `refresh_token` / `Bearer` / `secret` / `vault` / `credentials`
   substring; structural pin on response keys.
8. **TTL above hard cap rejected (1)**: 422 at the schema layer.
9. **Unknown category rejected (1)**: 422 at the schema layer.

#### Frontend type-check

`npx tsc --noEmit` -> `EXIT=0`.

---

## 4. Test result

```
$ .venv/Scripts/python.exe -m pytest tests/test_skill_consent_api.py -q
9 passed in 7.38s

$ .venv/Scripts/python.exe -m pytest <full sprint scope> -q
216 passed in 25.88s
```

Test growth Sprint-5 PR-4:
* End of PR-3: 207 in scope
* PR-4 adds: 9 new consent-API tests = **216 in scope**

---

## 5. What did NOT change

* No allowlist entry modified.
* No executor enforcement change beyond what Sprint-4 PR-4 already
  shipped.
* No HTTP route opened that fires external action.
* No Phase 3 write surface enabled.
* The OAuth invoker, account-profile gate, MCP execution path,
  governance presets -- all unchanged.

---

## 6. Follow-up PRs

1. **`PR-CONN-GOV-PRESETS-API-UI` (Sprint-5 PR-5)** -- expose plugin
   governance presets per Founder's brief.
2. **`PR-CONN-CONSENT-DB-PERSISTENCE`** (future): replace in-memory
   `ConsentStore` with a DB table for multi-instance Cloud Run
   deployment.
3. **`PR-CONN-CONSENT-CATEGORY-FROM-CLASSIFY`** (future): expose the
   backend's `categorize_skill` result inside the
   `needs_consent` outcome so the modal can DEFAULT the category
   dropdown to the executor's classification instead of always
   `write_external`.
