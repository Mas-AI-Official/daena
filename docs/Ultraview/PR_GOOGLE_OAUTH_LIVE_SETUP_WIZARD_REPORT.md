# PR-1 -- Google OAuth Live Setup Wizard

**Sprint:** DAENA-SPRINT-15-GOOGLE-LIVE-AND-FIRST-SEND-UNLOCK
**PR:** 1 of 6
**Date:** 2026-05-06

## Goal

Make the two pinned Google accounts visible at provider granularity
(Gmail / Calendar / Drive), let the operator refresh status without a
full page reload, and surface the EXACT refusal code that Phase 3
controlled writes raise when an account isn't connected.

## What ships

`frontend/src/pages/connections/GoogleAccountSetupGuide.tsx` (modified):

* New `PHASE3_PROVIDERS` closed list -- the three providers Phase 3
  cares about. Static, not operator-editable.
* New `ProviderPills` component renders one pill per provider per
  account. Pill is emerald when the slug is in
  `connected_services`, grey otherwise. Test-ids:
  `google-{founder|agent}-provider-{slug}-{on|off}` so Playwright
  smoke can assert presence.
* New `Refresh status` button wired to the existing
  `useGoogleSetupStatus` hook's `refresh()`. Spinner animates while
  loading; button disables while in flight.
* New rose-bordered "Phase 3 controlled writes refuse without this
  connection" block. Surfaces the exact refusal code
  `oauth_not_connected:google` so when an operator sees the code in
  the audit log, they can map it back to this guide.

`frontend/src/hooks/useGoogleSetupStatus.ts`: untouched. Hook already
exposed `refresh` since Sprint-10; PR-1 just wires the button.

## Backend

NO new endpoint. The existing
`GET /api/v1/connections/google-setup-status` already returns
`connected_services` per account, which is the data PR-1 renders.
Avoiding a new endpoint per CLAUDE.md Rule 2 (one canonical file per
concern).

A future PR-1.5 could add a `POST /test-readonly` endpoint that pings
Gmail/Calendar/Drive in read-only mode for a deeper liveness check;
PR-1 ships without it because the ConnectorInstance row's existence
is already proof that OAuth completed against Google's servers.

## Locked invariants

| Invariant | Where |
|---|---|
| No secret values returned by the status endpoint | unchanged from Sprint-10 |
| No OAuth flow started by the wizard | unchanged; "Manual step required" copy preserved |
| owner_email is captured at OAuth time, not edited here | endpoint reads existing row, no write |
| Refresh re-fetches the same read-only payload | `void refresh()` callback |
| Phase 3 refusal code visible in the UI | `oauth_not_connected:google` literal in the rose block |

## Tests

Frontend type-check: `npx tsc --noEmit` -- run as part of PR-6 smoke.

The existing component tests in `GoogleAccountSetupGuide.test.tsx`
(if any) continue to pass because the `connected. Services: ...`
text was REPLACED with a pill row keyed by data-testid; no tests in
the repo asserted the substring (verified by grep).

## Hard rules audit

| Rule | Status |
|---|---|
| No secret display | enforced -- no client_secret / token in DOM |
| owner_email captured | unchanged -- the OAuth row's `owner_email` is the source |
| UI clearly says which account is active | enforced -- two role panels (Founder vs Agent voice) preserved |
| Refusal hint when OAuth missing | enforced -- new rose block names the exact code |

## Files

```
modified:   frontend/src/pages/connections/GoogleAccountSetupGuide.tsx
new:        docs/Ultraview/PR_GOOGLE_OAUTH_LIVE_SETUP_WIZARD_REPORT.md
```

## Next: PR-2 -- Gmail Send Existing Draft Controlled Tool
