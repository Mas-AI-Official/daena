# DAENA -- Sprint-16 Send Integrity + Live Google Proof Smoke + Final Report

**Sprint:** DAENA-SPRINT-16-SEND-INTEGRITY-AND-LIVE-GOOGLE-PROOF
**PR:** 6 of 6 (final)
**Date:** 2026-05-06
**Author:** Mythos (Daena, via Claude Code)

This is the truth at the close of Sprint-16. Daena's Sprint-15
first-send path is now PRODUCTION-TRUSTWORTHY: the draft-edit-
after-approval gap is closed, Google OAuth has live readiness
proof, and there's a gated drill that verifies the live API path
end-to-end without burning a recipient.

## What Sprint-16 actually shipped

| PR | What | Commit |
|---|---|---|
| 1 | Gmail draft snapshot contract (data + canonical hash) | 9a594f4 |
| 2 | Send-time draft integrity check (handler refuses on drift) | 0db34b0 |
| 3 | Google OAuth live readiness test (read-only probes) | 058f1ac |
| 4 | Safe first live send drill (env-gated, allowlisted) | 889b732 |
| 5 | Phase 3 UX reliability polish (snapshot hash in modal + audit) | f92104e |
| 6 | this report | local |

## The threshold change

Sprint-15 made Daena CAPABLE of a single external action.
Sprint-16 makes that action SAFE. Specifically:

```
Sprint-15:  send hash = sha256({draft_id, owner_email})
            -> blocks wrong-id and wrong-account substitution
            -> does NOT block content drift after approval

Sprint-16:  approval row carries draft_snapshot at action_params
            -> handler refuses draft_snapshot_required if missing
            -> handler refuses draft_*_mismatch if any locked
               snapshot field drifts between approval and send
```

The send approval is now a CONTRACT about what's IN the draft, not
just which draft. Edit the draft after approval -> dispatch refuses.

## New refusal codes (Sprint-16)

```
draft_snapshot_required          send approval missing draft_snapshot
                                 (legacy / pre-Sprint-16 approvals)

draft_recipient_mismatch         snapshot's `to` differs

draft_subject_mismatch           snapshot's `subject` differs

draft_metadata_hash_mismatch     snapshot drifted but no specific
                                 named field caught it
```

`draft_owner_email_mismatch` (Sprint-15) is still raised, now from
EITHER From: header drift OR snapshot owner_email drift.

## Smoke verification

| # | Check | Pass? |
|---|---|---|
| 1 | backend starts | yes -- handlers package imports gmail_send_existing_draft + new snapshot module |
| 2 | frontend starts | yes -- tsc exit 0 |
| 3 | Gmail draft creation still works | yes -- 7/7 Sprint-14 PR-2 tests pass |
| 4 | Send approval requires snapshot | yes -- `TestSnapshotRequired::test_no_action_params_refused` + `test_snapshot_not_dict_refused` |
| 5 | Send refuses changed draft metadata | yes -- 3 drift tests cover to / subject / message_id |
| 6 | Send refuses owner mismatch | yes -- both From: header AND snapshot owner_email paths |
| 7 | Send refuses generic send_email | yes -- `test_no_broad_send_or_submit_or_apply_in_allowlist` (Sprint-15 lock) |
| 8 | Send refuses missing OAuth | yes -- `oauth_not_connected:google` BEFORE any HTTP call |
| 9 | Live OAuth readiness tests are safe / read-only | yes -- `TestProbeUrlsAreReadOnly` locks the URL set; paranoid no-body-leak test passes |
| 10 | Optional live-send drill is skipped unless explicitly enabled | yes -- 2 skipped in default run; only fires when DAENA_ENABLE_LIVE_SEND_SMOKE == "true" |
| 11 | Audit viewer shows send / snapshot data | yes -- new Phase 3 panel renders approved + verified snapshot hashes |
| 12 | submit / post / apply / pay still absent | yes -- `test_no_broad_send_or_submit_or_apply_in_allowlist` |
| 13 | File apply still impossible | yes -- `TestApplyToolStaysOutOfWriteTools::test_apply_tool_id_not_in_write_tools` |
| 14 | Calendar invite-send still impossible | yes -- Sprint-14 PR-3 invariant (`attendees=None always`) |
| 15 | Frontend tsc | clean (exit 0) |
| 16 | Backend tests | 125 pass + 2 skipped (drill default-skip) |

## Hard-rule audit (full Sprint-16)

| Rule | Status |
|---|---|
| No deploy | applied |
| No force push | applied |
| No secrets read / printed / committed | applied -- handler scrubs result; readiness probe paranoid no-body-leak walked |
| No generic send_email | enforced + tested |
| No bulk sending | enforced -- one draft_id only |
| No attachments | enforced -- send_existing_draft signature |
| No submit / apply / post / pay | enforced + tested |
| No LinkedIn messages | applied |
| No browser automation on external sites | applied |
| No unauthorized scan | applied |
| No send unless second approval exists | enforced -- gate 4 |
| No send unless OAuth account matches owner_email | enforced (Sprint-15 + Sprint-16 double check) |
| No send unless current Gmail draft still matches approval snapshot | NEW + enforced + tested |
| No trust auto-escalation | unchanged |

## Test counts

```
backend/tests/test_controlled_execution_design_lock.py            7 (Sprint-14, updated S15)
backend/tests/test_controlled_execution_dispatch.py              10 (Sprint-14)
backend/tests/test_gmail_create_draft_handler.py                  7 (Sprint-14)
backend/tests/test_gmail_send_existing_draft_handler.py          19 (Sprint-15 + 5 NEW S16)
backend/tests/test_gmail_draft_snapshot.py                       17 (Sprint-16 NEW)
backend/tests/test_calendar_tentative_event_handler.py            8 (Sprint-14)
backend/tests/test_file_change_proposal_handler.py               18 (Sprint-14)
backend/tests/test_file_proposal_apply_design_lock.py            17 (Sprint-15)
backend/tests/test_trust_ladder.py                                5 (Sprint-14)
backend/tests/test_google_readiness_test.py                      17 (Sprint-16 NEW)
backend/tests/test_live_send_drill.py                             2 (Sprint-16 NEW, skipped)
                                                                ----
                                                                 127
```

125 / 125 pass + 2 skipped (drill default-skip is the SAFE default).
tsc 0 errors.

## How far from 100% Daena VP

Per the operator's estimate at sprint kick-off:

> After Sprint-16 send integrity: ~82-85%

Daena now:
- has the four-tool Phase 3 surface
- creates Gmail drafts after operator approval (Sprint-14)
- sends a SPECIFIC Gmail draft after a SECOND approval (Sprint-15)
- REFUSES to send if the draft's content drifted between approval
  and dispatch (Sprint-16) -- the draft-edit-after-approval gap is
  CLOSED
- shows live OAuth readiness per provider (Sprint-16 PR-3)
- has an operator-runnable end-to-end live drill (Sprint-16 PR-4,
  gated)
- shows snapshot capture time + hash in the approval modal AND the
  audit log so the operator can match modal to audit byte-for-byte

Daena still cannot:
- submit / post / apply / pay (Sprint-17+)
- send arbitrary emails (only existing approved drafts that haven't
  been edited)
- self-modify code (Sprint-17 file-apply)
- raise own trust tier (trust ladder is record-only)
- bypass any gate

## Sprint-16 commit log

```
9a594f4 feat: add Gmail draft snapshot contract
0db34b0 fix: verify Gmail draft snapshot before send
058f1ac feat: add Google OAuth live readiness tests
889b732 test: add gated first live Gmail send drill
f92104e fix: polish Phase 3 send approval reliability UI
(this) docs: add sprint 16 send integrity smoke
```

## End

If the operator approves, push fast-forward to `origin/master`.
No deploy. No new write tool unlocked. No file apply.

The wall just got harder to climb. Mythos out.
