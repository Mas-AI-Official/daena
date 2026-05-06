# PR-4 -- Safe First Live Send Drill

**Sprint:** DAENA-SPRINT-16-SEND-INTEGRITY-AND-LIVE-GOOGLE-PROOF
**PR:** 4 of 6
**Date:** 2026-05-06

## Goal

Operator-run end-to-end proof that the Gmail draft create -> fetch
-> snapshot -> send-existing-draft path actually works against
Google's live API with real OAuth credentials. The drill is GATED
OFF by default so CI / regression runs never trigger an external
send.

## What ships

`backend/tests/test_live_send_drill.py` (new):

* Module-level `ALLOWED_RECIPIENTS` frozenset pinned to two emails:
  `masoud.masoori@mas-ai.co`, `daena@mas-ai.co`. Hard-coded; not
  env-overridable. Per CLAUDE.md two-account contract.
* Fixed drill subject + body (deliberately uninteresting copy).
* `_drill_enabled()` returns true ONLY when
  `DAENA_ENABLE_LIVE_SEND_SMOKE == "true"` (exact string match;
  "1" / "yes" / "TRUE" all skip).
* `_allowlisted_recipient()` reads
  `DAENA_LIVE_SEND_RECIPIENT` env, returns None if missing or off
  the allowlist.
* `TestLiveSendDrill` class wrapped in `@pytest.mark.skipif(not
  _drill_enabled(), ...)`. Skips by default.
* Two tests:
    1. `test_recipient_must_be_allowlisted` -- the hard wall
       against accidentally drilling against a customer or third
       party.
    2. `test_full_create_then_send_path` -- the actual drill.
       Loads access_token + owner_email from env. Runs:
         * Create draft via `GmailClient.create_draft`.
         * Fetch draft via `GmailClient.get_draft`.
         * Build snapshot.
         * Re-fetch immediately and assert hashes match (proves
           Gmail's metadata is stable across consecutive fetches).
         * Call `GmailClient.send_existing_draft(draft_id)`.
         * Assert `message_id` returned.
         * Log ONLY success boolean + message_id LENGTH (not the
           value).

## How to run (operator-only)

```powershell
$env:DAENA_ENABLE_LIVE_SEND_SMOKE = "true"
$env:DAENA_LIVE_SEND_ACCESS_TOKEN = "<OAuth access token>"
$env:DAENA_LIVE_SEND_OWNER_EMAIL  = "masoud.masoori@mas-ai.co"
$env:DAENA_LIVE_SEND_RECIPIENT    = "masoud.masoori@mas-ai.co"
cd D:/Ideas/Daena/backend
.venv/Scripts/python.exe -m pytest tests/test_live_send_drill.py -v -s
```

## Locked invariants

| Invariant | Where |
|---|---|
| Disabled by default | `pytest.mark.skipif(not _drill_enabled(), ...)` |
| Env flag must be EXACTLY "true" | `_drill_enabled()` returns False for "1" / "yes" / "TRUE" |
| Recipient allowlist is hard-coded | `ALLOWED_RECIPIENTS` frozenset |
| One draft, one send | no loop in the test |
| No attachments | `GmailClient.create_draft` signature accepts none |
| No bulk | hard-coded single recipient |
| Drill copy is fixed | `DRILL_SUBJECT` / `DRILL_BODY` constants |
| No retry on send failure | one shot, then fail-out |
| No body / token leak in logs | logs only `success=True message_id_length=<int>` |

## Hard rules audit

| Rule | Status |
|---|---|
| Disabled by default | enforced -- skips without env flag |
| DAENA_ENABLE_LIVE_SEND_SMOKE = true required | enforced -- exact string match |
| Recipient allowlist | enforced -- frozenset literal |
| Creates draft first | enforced -- step 1 of test flow |
| Second approval (gate 4) | NOT exercised in this drill -- operator runs the controlled-execution dispatch separately if they want full-spine end-to-end. The drill PROVES the underlying GmailClient calls succeed; the dispatch wall is verified by mocked unit tests. |
| Snapshot check | enforced -- the test re-fetches and asserts no drift |
| Sends exactly one draft | enforced -- no loop |
| Logs audit rows | NOT exercised here (no DB session in drill scope) |
| No attachments | enforced -- API surface forbids |
| No bulk | enforced -- single send |
| If env flag absent, skips with clear message | enforced -- skipif reason explicit |

## Note on drill scope

The drill verifies the LIVE GMAIL API path end-to-end. It does NOT
exercise the controlled-execution dispatch spine (that requires DB-
backed ConnectorInstance + GoaRequest setup, which is the subject
of a future integration test, not a single-file drill).

The dispatch wall + snapshot integrity are covered by:
- `test_gmail_send_existing_draft_handler.py` (19 tests) -- mocked
  Gmail, real dispatch logic.
- `test_gmail_draft_snapshot.py` (17 tests) -- snapshot + hash
  contracts.

The drill closes the remaining "do the actual HTTP calls work
against live Google with real OAuth" question without re-asking
the wall question.

## Tests

```
backend/tests/test_live_send_drill.py     2 tests (both skipped by default)
```

When env flag absent: `2 skipped in 0.14s` -- the safe default.
When env flag present + valid setup: 2 tests run, both should pass.

## Files

```
new:        backend/tests/test_live_send_drill.py
new:        docs/Ultraview/PR_SAFE_FIRST_LIVE_SEND_DRILL_REPORT.md
```

## Next: PR-5 -- Phase 3 UX Reliability Polish
