# PR-6 -- Gmail Send Controlled Dispatch Integration Test

**Sprint:** DAENA-SPRINT-17-FILE-APPLY-AND-SELF-HEALING-PATCH-LOOP
**PR:** 6 of 7
**Date:** 2026-05-06

## Goal

Plug the gap the Sprint-16 PR-4 live drill could not cover: a
DB-backed integration test that exercises the FULL dispatch spine
end-to-end with real DB rows + mocked Gmail HTTP. Until now, each
gate was unit-tested individually (mocked dispatch + mocked DB) or
proven against live Google (real DB? no -- direct GmailClient).
This PR closes the loop.

## What ships

`backend/tests/test_gmail_send_dispatch_integration.py` (new):

Six integration tests against the in-memory aiosqlite test engine
(scoped to the existing `test_engine` / `db_session` fixtures from
`conftest.py`):

1. **TestFullDispatchHappyPath** -- full end-to-end. Seeds Tenant
   + User + Connector("Gmail") + ConnectorInstance(access_token)
   + GoaRequest(status="approved", action_params with
   draft_snapshot). Flips autonomy mode to APPROVED_EXECUTION.
   Mocks GmailClient via `_build_client` monkeypatch. Calls
   `dispatch_controlled_execution` and asserts:
     - All six gates pass (handler ran)
     - `fake_client.get_draft` was awaited once with draft_id
     - `fake_client.send_existing_draft` was awaited once with draft_id
     - Result carries `status="sent"`, `message_id`, both snapshot
       hashes (Sprint-16 PR-5 invariant)
2. **test_autonomy_mode_off_refuses** -- gate 1: mode=research_draft
   refuses with `autonomy_mode_does_not_allow_dispatch`.
3. **test_payload_hash_mismatch_refuses** -- gate 3: wrong
   payload_hash refuses with `payload_hash_mismatch`.
4. **test_expired_approval_refuses** -- gate 4: `expires_at` in
   the past refuses with `approval_expired`.
5. **test_wrong_action_type_refuses** -- gate 4: a
   `gmail.create_draft` approval refuses to authorize
   `gmail.send_existing_draft` with `approval_tool_id_mismatch`.
6. **test_snapshot_drift_refuses** -- Sprint-16 PR-2 wall: even
   though all 5 dispatch gates pass, the in-handler snapshot
   integrity check refuses with `draft_recipient_mismatch` and
   `send_existing_draft` is NEVER called.

## What this proves vs. existing tests

| Coverage | Before PR-6 | PR-6 |
|---|---|---|
| Each gate refuses correctly | yes (mocked unit tests) | yes |
| GmailClient HTTP path works against Google | yes (live drill, gated) | n/a |
| Full dispatch spine + DB lookup + handler integration | NO | yes |
| Snapshot wall fires AFTER all gates pass | yes (mocked handler) | yes (real DB) |
| Approval row's action_type drives gate 4 | unit only | yes (real DB) |
| Approval row's expires_at column actually enforces expiry | unit only | yes (real DB) |

## Locked invariants

| Invariant | Where |
|---|---|
| Real DB session enforces FK + NOT NULL constraints | sqlite enforces; tenant + user + risk_level seeded |
| Approval lookup uses tenant_id scoping | GoaRequest seeded under test_tenant_id |
| ConnectorInstance lookup uses tenant + user + owner_email | seeded with all three |
| Snapshot match -> send fires | happy path test |
| Snapshot drift -> send refuses | drift test |

## Tests

```
backend/tests/test_gmail_send_dispatch_integration.py    6 tests
```

6/6 pass against in-memory sqlite + aiosqlite. NO real Gmail
HTTP calls fire; no real OAuth tokens used.

## Files

```
new:        backend/tests/test_gmail_send_dispatch_integration.py
new:        docs/Ultraview/PR_GMAIL_SEND_CONTROLLED_DISPATCH_INTEGRATION_TEST_REPORT.md
```

## Next: PR-7 -- Sprint-17 Smoke + Final Report
