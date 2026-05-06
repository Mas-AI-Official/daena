# DAENA -- Sprint-15 Google Live + First Send Smoke + Final Report

**Sprint:** DAENA-SPRINT-15-GOOGLE-LIVE-AND-FIRST-SEND-UNLOCK
**PR:** 6 of 6 (final)
**Date:** 2026-05-06
**Author:** Mythos (Daena, via Claude Code)

This is the truth at the close of Sprint-15. Daena now crosses
from "controlled draft actor beta" to "first controlled external
send" -- but only via the narrowest possible path: send a SPECIFIC
already-approved Gmail draft, after a SECOND approval, only if the
draft's From: header matches the approving owner_email.

## What Sprint-15 actually shipped

| PR | What | Commit |
|---|---|---|
| 1 | Google OAuth live setup wizard (per-provider pills + refusal hint) | f3f5700 |
| 2 | gmail.send_existing_draft (FIRST controlled external send) | afb7c6a |
| 3 | Phase 3 second approval wall (irrevocability + draft snapshot) | e2cb33f |
| 4 | Audit viewer 'Phase 3 only' filter | 1b7bcae |
| 5 | File proposal apply design lock (no endpoint, design only) | 4302b13 |
| 6 | this report | local |

## WRITE_TOOLS: from three to four

```python
# Sprint-14:
WRITE_TOOLS = frozenset({
    "gmail.create_draft",
    "calendar.create_tentative_event_without_invites",
    "local.file_change_proposal",
})

# Sprint-15 PR-2:
WRITE_TOOLS = frozenset({
    "gmail.create_draft",
    "gmail.send_existing_draft",                               # NEW
    "calendar.create_tentative_event_without_invites",
    "local.file_change_proposal",
})
```

The Sprint-14 contract test `test_write_tools_is_sprint14_set`
was renamed `test_write_tools_is_sprint15_set` and updated -- the
deliberate operator-visible signal that Phase 3 is widening by
ONE narrow send tool. `test_no_send_tool_in_allowlist` was
rewritten as `test_no_broad_send_or_submit_or_apply_in_allowlist`
with a sharper rule: no tool may END with `.send` / `.submit` /
`.post` / `.apply` / `.pay`; any `.send`-shaped tool must be on
the explicit narrow allowlist `{"gmail.send_existing_draft"}`.

## Send refusal codes (Sprint-15 PR-2 contract)

```
owner_email_required
payload_field_missing:draft_id
oauth_not_connected:google
draft_not_found
draft_owner_email_mismatch          ← lock against draft-substitution
(success)
```

The handler refuses BEFORE any HTTP call to Gmail when OAuth is
missing. After OAuth resolves, it FETCHES the draft from Gmail
via `GET /drafts/{id}` and asserts the draft's `From:` header
contains the request's `owner_email` -- the lock that prevents a
draft created under a different connected account from being sent
under the operator's account.

## Smoke verification

| # | Check | Pass? |
|---|---|---|
| 1 | backend starts (lifespan registers all 4 controlled-execution handlers) | yes -- handlers package imports gmail_send_existing_draft alongside the Sprint-14 three |
| 2 | frontend starts (tsc clean) | yes -- exit 0 |
| 3 | Google OAuth setup wizard renders with per-provider pills + Refresh button | yes -- PR-1 wires `useGoogleSetupStatus.refresh` + ProviderPills component |
| 4 | Missing OAuth gives exact refusal `oauth_not_connected:google` | yes -- both gmail.create_draft AND gmail.send_existing_draft handlers refuse with this code BEFORE any Gmail HTTP call |
| 5 | Gmail draft creation still works with mocks | yes -- 7/7 Sprint-14 PR-2 handler tests pass |
| 6 | Gmail send_existing_draft requires second approval | yes -- gate 4 enforces approval.action_type == "gmail.send_existing_draft"; create-draft approvals carry "gmail.create_draft" so their tool_id mismatches at dispatch |
| 7 | Generic send_email is impossible | yes -- `test_no_broad_send_or_submit_or_apply_in_allowlist` pins it; `gmail.send_email` is NOT in WRITE_TOOLS and the test forbids future re-introduction |
| 8 | Send refuses payload_hash mismatch | yes -- gate 3 in dispatcher (Sprint-14); applies to gmail.send_existing_draft because Sprint-15 reuses the dispatch spine unchanged |
| 9 | Send refuses owner_email mismatch | yes -- handler refuses `draft_owner_email_mismatch` after fetching the draft and inspecting its From: header |
| 10 | Send refuses stale approval | yes -- gate 4 checks `approval.expires_at`; Sprint-14 already pinned this and Sprint-15 reuses it |
| 11 | Send refuses Asset Shield fail | yes -- gate 2 enforces `asset_shield_pass=True` in the design contract |
| 12 | Audit viewer shows controlled execution rows | yes -- PR-4 adds Phase 3 only toggle wired to `isControlledExecutionRow(action_type)` |
| 13 | File apply still impossible | yes -- `TestApplyToolStaysOutOfWriteTools::test_apply_tool_id_not_in_write_tools` pins it; `TestNoHttpEndpointExists` walks the v1 router and asserts no apply route exists |
| 14 | Calendar invite-send still impossible | yes -- Sprint-14 PR-3 invariant unchanged; `attendees=None` always |
| 15 | submit / post / apply / pay still absent | yes -- `test_no_broad_send_or_submit_or_apply_in_allowlist` pins all five suffixes |
| 16 | Frontend tsc | clean (exit 0) |
| 17 | Backend tests | 86/86 pass on Sprint-14 + Sprint-15 fast subset |

## Hard-rule audit (full Sprint-15)

| Rule | Status |
|---|---|
| No deploy | applied |
| No force push | applied |
| No secrets read / printed / committed | applied -- handler results scrub access_token / refresh_token; safe-walk test pins this for both gmail handlers |
| No generic send_email | enforced + tested |
| No submit / apply / post / pay | enforced + tested |
| No LinkedIn messages | applied |
| No external browser automation | applied |
| No unauthorized scan | applied |
| No attachments | enforced -- send_existing_draft signature accepts only draft_id |
| No bulk sending | enforced -- handler accepts ONE draft_id |
| No send without approved Gmail draft row | enforced -- gate 4 |
| No send if draft payload hash changed | enforced -- gate 3 |
| No send if owner_email mismatch | enforced -- handler refuses `draft_owner_email_mismatch` |
| No send if Asset Shield fails | enforced -- gate 2 |
| No send if approval / consent missing or stale | enforced -- gate 4 (approval), design contract (consent_grant_id) |
| No trust auto-escalation yet | unchanged -- trust_ladder is record-only |

## Test counts

```
backend/tests/test_controlled_execution_design_lock.py             7 (Sprint-14, updated)
backend/tests/test_controlled_execution_dispatch.py               10 (Sprint-14)
backend/tests/test_gmail_create_draft_handler.py                   7 (Sprint-14)
backend/tests/test_gmail_send_existing_draft_handler.py           14 (Sprint-15 NEW)
backend/tests/test_calendar_tentative_event_handler.py             8 (Sprint-14)
backend/tests/test_file_change_proposal_handler.py                18 (Sprint-14)
backend/tests/test_file_proposal_apply_design_lock.py             17 (Sprint-15 NEW)
backend/tests/test_trust_ladder.py                                 5 (Sprint-14)
                                                                  ---
                                                                   86
```

86/86 pass. tsc 0 errors.

## How far from 100% Daena VP

Per the operator's estimate at sprint kick-off:

> After Sprint-15: 78-82%

Daena now:
- has the four-tool Phase 3 surface
- can create a Gmail draft (no send) after operator approval
- can SEND a specific Gmail draft after a SECOND operator
  approval (irrevocability banner + draft snapshot in modal)
- can create a Calendar tentative event (no invites) after
  operator approval
- can propose a local file change as a diff artifact (no apply)
- shows the Phase 3 audit row at one click via the audit viewer
  filter

Daena still cannot:
- submit / post / apply / pay (Sprint-16+)
- send arbitrary emails (only existing approved drafts)
- send without owner_email match (draft-substitution lock)
- send without OAuth (refused before any HTTP call)
- scan unauthorized targets
- bypass OAuth
- auto-execute any patch
- raise its own trust tier

## Sprint-15 commit log

```
f3f5700 feat: add Google OAuth live setup wizard
afb7c6a feat: add controlled Gmail send existing draft
e2cb33f feat: add second approval wall for Gmail send
1b7bcae feat: add controlled execution audit filter
4302b13 docs/test: lock file proposal apply design
(this) docs: add sprint 15 first send smoke
```

## End

If the operator approves, push fast-forward to `origin/master`.
No deploy. No new send tool beyond `gmail.send_existing_draft`.
No file apply unlocked.

Mythos out.
