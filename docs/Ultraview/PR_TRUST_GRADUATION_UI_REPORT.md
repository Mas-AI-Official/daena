# PR-2 -- Trust Graduation UI

**Sprint:** DAENA-SPRINT-18-TRUST-LADDER-AND-ROUTINE-AUTONOMY
**PR:** 2 of 6
**Date:** 2026-05-06

## Goal

Make the trust ladder visible. Operator sees per-(tool,
template_class) approval/rejection counters, current granted
tier, eligibility, lock reasons. Founder can raise / lower a tier
through a confirmation-phrase wall.

## What ships

`backend/app/api/v1/trust.py` (new):

* `GET /api/v1/trust/eligible-tools` -- locked eligibility lists +
  available tiers (reserved tier excluded).
* `GET /api/v1/trust/policies` -- union of policy + ladder rows
  with eligibility flags and counters.
* `POST /api/v1/trust/policies/preview-decision` -- dry-run
  "would this auto-approve right now?" -- returns the same shape
  as `should_auto_approve`.
* `POST /api/v1/trust/policies/tier-set` -- founder-only mutation,
  guarded by `require_role("FOUNDER")`. Refusals return 200 with
  `success=False + error_code` (UI inline render); 4xx only for
  bad enum / unauthorized.

`backend/app/api/v1/__init__.py` (modified): mounts trust router.

`frontend/src/pages/GovernanceTrustPage.tsx` (new):

* Reads policies + eligibility on mount.
* Renders forbidden tools with locked badge + reason.
* Per-row tier dropdown (None / Suggest only / Auto-approve
  low risk). Reserved tier UNREACHABLE.
* Tier change opens modal that displays the EXACT confirmation
  phrase to type. Submit button stays disabled until typed phrase
  matches expected. Error code from backend renders inline.
* No hardcoded "demo" rows. Empty state honest ("No trust rows
  yet. Approve a draft a few times and the ladder starts to build.").

`frontend/src/App.tsx` (modified): routes `/governance/trust` to
the new page.

`frontend/src/components/layout/Sidebar.tsx` (modified): adds
sidebar entry under Governance.

## Mythos design choices

**Confirmation phrase as static template.** The phrase is computed
from `(tool_id, tier)` -- not LLM-generated. Frontend displays it,
operator types it, backend recomputes and string-matches. Prompt
injection cannot bypass because there is no LLM in the path.

**Inline-error vs HTTP-error split.** "Confirmation phrase
mismatch" returns 200 + structured error so the modal stays open
and the user can re-type. "Invalid tier enum" returns 400 because
that's a bug, not a user mistake. "Unauthorized" returns 403
because that's a contract violation by the caller.

**Eligibility lists are server-derived, not hardcoded in the UI.**
The frontend fetches `eligible_tools` / `forbidden_tools` from
`/eligible-tools`. If the backend changes the locked set, the UI
auto-updates. This is the same honesty rule as ADR-001.

**No silent fall-back to fake data.** If `/policies` fails, the
page renders an explicit error card with "Retry to refresh." No
demo rows. No optimistic empty state pretending to be loaded.

## Locked invariants

| Invariant | Where |
|---|---|
| `/eligible-tools` returns the locked Sprint-18 sets | `TestEligibleToolsEndpoint::test_returns_locked_sets` |
| Reserved tier NOT in available_tiers | same test, `auto_execute_low_risk_local` absent |
| `/policies` empty initially | `test_empty_when_no_history` |
| `/policies` joins ladder + policy | `test_returns_policy_and_ladder_state` |
| Tier-set with valid input persists | `TestTierSetEndpoint::test_founder_can_set_tier` |
| Wrong phrase returns 200 + inline error | `test_wrong_confirmation_phrase_returns_inline_error` |
| Forbidden tool returns inline error | `test_forbidden_tool_returns_inline_error` |
| Invalid tier enum returns 400 | `test_invalid_tier_returns_400` |
| Preview decision matches policy module | `TestPreviewDecisionEndpoint::*` (3 tests) |
| FOUNDER role required on tier-set | `require_role("FOUNDER")` dependency |

## Hard rules audit

| Rule | Status |
|---|---|
| No deploy | applied |
| No force push | applied |
| No secrets read / printed / committed | applied |
| No submit / post / pay surface added | applied -- this PR adds only trust state endpoints |
| No file delete | applied |
| No multi-file apply | applied |
| FOUNDER-only tier raise | enforced via `Depends(require_role("FOUNDER"))` |
| Daena cannot raise her own tier | enforced -- tool dispatch path has no route to `/policies/tier-set` |
| Reserved tier UNREACHABLE | available_tiers excludes it; backend rejects it |

## Tests

```
backend/tests/test_trust_api.py    10 tests
```

10/10 pass. Frontend tsc exit 0.

## Files

```
new:        backend/app/api/v1/trust.py
new:        backend/tests/test_trust_api.py
modified:   backend/app/api/v1/__init__.py
new:        frontend/src/pages/GovernanceTrustPage.tsx
modified:   frontend/src/App.tsx
modified:   frontend/src/components/layout/Sidebar.tsx
new:        docs/Ultraview/PR_TRUST_GRADUATION_UI_REPORT.md
```

## Next: PR-3 -- Auto-approve low-risk draft actions
