# PR-1 -- Live Google Account Activation Checklist

**Sprint:** DAENA-SPRINT-20-LIVE-BUSINESS-OPS-ACTIVATION
**PR:** 1 of 8
**Date:** 2026-05-06

## Goal

Make Google account readiness for `masoud.masoori@mas-ai.co` and
`daena@mas-ai.co` impossible to miss in the operator's morning flow.
Cover all five statuses (connected / expired / insufficient_scope /
failed / not_connected), spell out the exact next action, auto-probe
on mount, and surface a blocker banner on the Opportunities page so
the operator never opens the inbox without seeing what's broken.

## What ships

`backend/app/services/google_readiness_test.py`:
* New `_NEXT_ACTIONS` map -- one operator-facing string per status.
* `probe_google_provider` now stamps `next_action` on every result.
* Mapping is locked to the same five statuses the existing classifier
  produces -- a regression that adds a new status without coverage
  fails the new test.

`backend/app/api/v1/google_setup.py`:
* New `GET /connections/google-activation-summary`.
* Pure DB read; never hits Google. Returns
  `{ ready, client_configured, blockers: [{role, email, missing[]}] }`.
* `missing` lists which of `gmail / drive / calendar` is NOT connected
  per pinned email.
* Distinct from `/google-setup-status` (which is the full setup-guide
  payload) and from `/google-readiness-test` (which is the live HTTP
  probe). Each endpoint has one job.

`frontend/src/hooks/useGoogleActivationSummary.ts` (new):
* Tiny hook that pulls the summary on mount; cross-page banners use it.

`frontend/src/pages/OpportunityInboxPage.tsx`:
* Pulls the summary; renders an amber `ShieldAlert` blocker card at
  the top of the inbox when `ready=false`. Each blocker spells out the
  email and the missing services and links to `/connections`.

`frontend/src/pages/connections/GoogleAccountSetupGuide.tsx`:
* Auto-probes both pinned accounts once the setup status reports them
  connected -- operator no longer has to remember to click
  Test read-only.
* Shows `next_action` per failing provider in an amber list under the
  status pills.
* Stamps `checked_at` (browser local time) so the operator can tell
  the data is current.

## Mythos design choices

**Three endpoints, three jobs.** `google-setup-status` answers "did
the operator complete the setup wizard?" `google-activation-summary`
answers "is the operator ready to RUN business operations right now?"
`google-readiness-test` answers "is Google itself happy with our
tokens?" Each is fast for its purpose. The summary endpoint is
DB-only by design so cross-page banners are cheap to render.

**Auto-probe on mount, not on every render.** The setup guide hook
guards against re-probing accounts already in the result map; the
operator gets fresh data on visit, not a probe storm.

**`next_action` is a closed enum-shaped map.** The five statuses are
the five paths an operator can take. A regression that adds a status
without a matching action is a test failure, not a UX bug discovered
in production.

**Banner copy lists the actual missing services per email.**
"Gmail not ready" is too vague -- "daena@mas-ai.co missing: gmail,
drive, calendar" tells the operator exactly what to click in the
Apps panel.

**Honest visibility of failure.** The blocker banner appears on the
Opportunities page even when the rest of the page works -- the rule
is "if outreach drafts cannot reach Gmail, the operator must see why
before they spend time on drafts."

## Locked invariants

| Invariant | Where |
|---|---|
| Endpoint requires auth | `test_endpoint_requires_auth` |
| Empty state lists client + both account blockers | `test_empty_state_lists_client_and_both_account_blockers` |
| Full connection -> ready=True, blockers=[] | `test_full_connection_flips_ready` |
| Partial connection lists missing providers | `test_partial_connection_lists_missing_providers` |
| Email match is case-insensitive | `test_email_match_is_case_insensitive` |
| Disconnected instance does not count | `test_disconnected_instance_does_not_count` |
| Response carries no credential / token / instance_id | `test_response_carries_no_credential_keys` |
| All statuses have non-empty next_action | `test_probe_result_carries_next_action_for_all_statuses` |

## Hard rules audit

| Rule | Status |
|---|---|
| No deploy | applied |
| No force push | applied |
| No secrets read / printed / committed | applied |
| Endpoint never returns secrets | enforced -- summary endpoint returns no `instance_id`, `access_token`, `refresh_token` |
| Endpoint never starts an OAuth flow | applied -- pure read |
| Endpoint never hits Google | applied -- summary is DB-only |

## Tests

```
backend/tests/test_google_activation_summary.py   8 tests
```

35/35 pass across the three Google test files (existing 27 +
new 8). Frontend tsc 0 errors.

## Files

```
modified:   backend/app/services/google_readiness_test.py
modified:   backend/app/api/v1/google_setup.py
new:        backend/tests/test_google_activation_summary.py
new:        frontend/src/hooks/useGoogleActivationSummary.ts
modified:   frontend/src/pages/OpportunityInboxPage.tsx
modified:   frontend/src/pages/connections/GoogleAccountSetupGuide.tsx
new:        docs/Ultraview/PR_LIVE_GOOGLE_ACCOUNT_ACTIVATION_CHECKLIST_REPORT.md
```

## Next: PR-2 -- Real Opportunity Source Adapters
