# PR-3 -- Google OAuth Live Readiness Test

**Sprint:** DAENA-SPRINT-16-SEND-INTEGRITY-AND-LIVE-GOOGLE-PROOF
**PR:** 3 of 6
**Date:** 2026-05-06

## Goal

Make Google OAuth status more than "ConnectorInstance row exists".
Add a live read-only liveness probe that classifies each provider
into a stable status enum and surfaces it in the wizard.

## What ships

`backend/app/services/google_readiness_test.py` (new):

* `_PROBE_URLS` -- LOCKED metadata-only Google endpoints:
    - Gmail: `gmail.googleapis.com/v1/users/me/profile`
    - Calendar: `googleapis.com/calendar/v3/calendars/primary`
    - Drive: `googleapis.com/drive/v3/about?fields=user/emailAddress`
* `GoogleReadinessProvider` Literal["gmail","calendar","drive"]
* `GoogleReadinessStatus` Literal["connected","expired",
  "insufficient_scope","failed","not_connected"]
* `_classify_response(status_code, body_text)` pure status-mapper:
    - 2xx -> connected
    - 401 -> expired
    - 403 + body contains "scope" or "insufficient" -> insufficient_scope
    - 403 (other) -> failed
    - anything else -> failed
* `probe_google_provider(provider, access_token, timeout=8.0)` runs
  one probe and returns ONLY `{provider, status, reason}`. NEVER
  the response body. The reason string is the HTTP status code or
  a typed network-error name -- never message bodies, never
  recipient lists, never inbox metadata.

`backend/app/api/v1/google_setup.py` (modified):

* New endpoint `POST /api/v1/connections/google-readiness-test`.
* Body: `{owner_email: str, providers: list[str]}` (providers
  defaults to all three).
* Looks up ConnectorInstance for each requested provider scoped to
  the caller's tenant + user_id + owner_email.
* If missing -> result `{status: "not_connected"}`.
* Otherwise -> `await probe_google_provider(...)`.
* Returns `{owner_email, results: [{provider, status, reason}, ...]}`.
* NO secret values returned. NO message bodies. NO calendar lists.
  NO file lists.

`frontend/src/pages/connections/GoogleAccountSetupGuide.tsx`
(modified):

* New "Test read-only" button per account panel (founder + agent).
* Renders `ReadinessBadge` per provider with stable test-id
  `readiness-{provider}-{status}` so the smoke can assert state.
* On error, shows the error message inline (no toast spam).
* Disables the button during in-flight probe.

## Locked invariants

| Invariant | Where |
|---|---|
| Probe URLs are metadata-only (no .send / .messages / .events / .files) | `TestProbeUrlsAreReadOnly::test_probe_urls_are_get_metadata_only` |
| Status classification is pure (no body propagation) | `TestClassifyResponse` (9 parametrized cases) |
| Probe NEVER leaks response body in the result | `TestProbeGoogleProvider::test_200_returns_connected_no_body_leak` (paranoid walk) |
| 401 maps to expired with operator-friendly reason | `test_401_returns_expired` |
| 403 + scope-shaped body maps to insufficient_scope | `test_403_with_scope_returns_insufficient_scope` |
| Network error / timeout maps to failed (typed reason) | `test_timeout_returns_failed`, `test_network_error_returns_failed` |
| Missing access_token short-circuits to not_connected | `test_missing_token_returns_not_connected` (no HTTP call fires) |
| Unknown provider rejected | `test_unknown_provider_returns_failed` |

## Hard rules audit

| Rule | Status |
|---|---|
| No send | enforced -- probe URLs forbidden from containing 'send' |
| No write | enforced -- only GET probes |
| No token leak | enforced -- handler never echoes the access_token |
| owner_email required | enforced -- 400 if absent in body |
| Result is connected / expired / insufficient_scope / failed | enforced -- `_classify_response` is the single mapper |
| UI shows exact status | enforced -- `ReadinessBadge` per provider |

## Tests

```
backend/tests/test_google_readiness_test.py     17 tests
```

17/17 pass. Test classes:
- `TestClassifyResponse` (9 parametrized): every status-code path.
- `TestProbeGoogleProvider` (7): unknown provider, missing token,
  200 without body leak (paranoid walk), 401 -> expired, 403 +
  scope -> insufficient_scope, timeout -> failed, network error
  -> failed.
- `TestProbeUrlsAreReadOnly` (1): URL set is locked + every URL
  forbidden from containing send / messages / events / files paths.

Frontend tsc: `npx tsc --noEmit` exits 0.

## Files

```
new:        backend/app/services/google_readiness_test.py
modified:   backend/app/api/v1/google_setup.py
new:        backend/tests/test_google_readiness_test.py
modified:   frontend/src/pages/connections/GoogleAccountSetupGuide.tsx
new:        docs/Ultraview/PR_GOOGLE_OAUTH_LIVE_READINESS_TEST_REPORT.md
```

## Next: PR-4 -- Safe First Live Send Drill
