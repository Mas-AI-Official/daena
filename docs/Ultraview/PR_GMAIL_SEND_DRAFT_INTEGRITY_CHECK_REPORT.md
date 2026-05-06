# PR-2 -- Gmail Send Draft Integrity Check

**Sprint:** DAENA-SPRINT-16-SEND-INTEGRITY-AND-LIVE-GOOGLE-PROOF
**PR:** 2 of 6
**Date:** 2026-05-06

## Goal

Make the Sprint-15 send path actually safe against draft tampering
between approval and send. PR-1 shipped the snapshot contract;
PR-2 makes it the wall.

## What ships

`backend/app/services/controlled_execution_handlers/gmail_send_existing_draft.py`
(modified):

* New imports from `gmail_draft_snapshot`:
  `build_snapshot_from_gmail_draft`, `compute_draft_metadata_hash`,
  `first_drift_field`.
* New module-level mapping `_DRIFT_FIELD_TO_REFUSAL_CODE` -- the
  load-bearing wire from a snapshot field name to a stable refusal
  code:
    - `owner_email` / `from_value` -> `draft_owner_email_mismatch`
    - `to` -> `draft_recipient_mismatch`
    - `subject` -> `draft_subject_mismatch`
    - everything else -> `draft_metadata_hash_mismatch`
* Inserted between the existing From: header check and the actual
  send call:
    1. Read `ctx.approval.action_params['draft_snapshot']`.
    2. If missing or not a dict -> refuse `draft_snapshot_required`.
    3. Build the current snapshot from the already-fetched draft
       metadata (no second HTTP round-trip).
    4. Call `first_drift_field(approved=approved_snapshot,
       current=current_snapshot)`.
    5. If drift detected, raise the mapped refusal code with both
       hash prefixes in the detail string.
* Success result now carries `approved_snapshot_hash` and
  `verified_snapshot_hash` so the PR-5 audit-viewer polish can
  render "what was approved is what was sent" proof.

## Refusal codes (Sprint-16 additions)

```
draft_snapshot_required          send approval missing draft_snapshot
                                 in action_params (legacy / pre-Sprint-16)

draft_recipient_mismatch         snapshot's `to` differs from current draft

draft_subject_mismatch           snapshot's `subject` differs from current draft

draft_metadata_hash_mismatch     snapshot drifted but no specific named field
                                 caught it (e.g. message_id changed)
```

`draft_owner_email_mismatch` is preserved from Sprint-15 PR-2 and
now fires from BOTH the From: header check (Sprint-15 lock) AND
the snapshot owner_email/from_value drift (Sprint-16 lock).

## Locked invariants

| Invariant | Where |
|---|---|
| Snapshot required for every send | `TestSnapshotRequired::test_no_action_params_refused` + `test_snapshot_not_dict_refused` |
| Recipient drift refuses with stable code | `TestSnapshotDriftRefusals::test_recipient_drift_refused` |
| Subject drift refuses with stable code | `TestSnapshotDriftRefusals::test_subject_drift_refused` |
| message_id drift maps to metadata_hash_mismatch | `TestSnapshotDriftRefusals::test_message_id_drift_refused` |
| Snapshot wall fires AFTER From: header check | code order in handler -- existing Sprint-15 lock preserved |
| Send NEVER fires when snapshot mismatches | `assert not fake_client.send_existing_draft.called` in every drift test |
| Audit row carries both hashes (proof of integrity) | `TestSuccessPath::test_mocked_send_returns_safe_payload` |

## What is NOT in this PR

* **No upstream snapshot creator.** The send-approval flow that
  builds the GoaRequest with `action_params={"draft_snapshot":
  ...}` lives elsewhere. PR-2 enforces the wall; whoever raises
  the approval is responsible for capturing the snapshot. Until
  that flow exists, every `gmail.send_existing_draft` dispatch
  refuses with `draft_snapshot_required` -- which is the correct
  default-deny posture.
* **No new endpoint.** Snapshot lives in `action_params`.
* **No race recovery.** If the snapshot mismatches, the operator
  must REJECT and re-create a new send approval against the
  current draft. There is no "auto-refresh and re-approve" path
  -- that would defeat the wall.

## Tests

```
backend/tests/test_gmail_send_existing_draft_handler.py     19 tests
backend/tests/test_gmail_draft_snapshot.py                  17 tests
```

19/19 send-handler tests pass. 5 NEW Sprint-16 tests:
- `TestSnapshotRequired::test_no_action_params_refused`
- `TestSnapshotRequired::test_snapshot_not_dict_refused`
- `TestSnapshotDriftRefusals::test_recipient_drift_refused`
- `TestSnapshotDriftRefusals::test_subject_drift_refused`
- `TestSnapshotDriftRefusals::test_message_id_drift_refused`

Existing Sprint-15 tests updated to provide a matching
`approval_params=_approval_with_snapshot(...)` so they continue to
exercise the From: header lock without tripping Sprint-16's wall.

Combined Sprint-14 + Sprint-15 + Sprint-16 fast subset:
**108 / 108 pass.**

## Hard rules audit

| Rule | Status |
|---|---|
| No deploy | applied |
| No secrets read / printed / committed | applied -- handler scrubs result, paranoid walk in success test |
| No generic send | enforced -- WRITE_TOOLS unchanged |
| No bulk | enforced -- one draft_id only |
| No attachments | enforced -- send_existing_draft signature |
| No send unless second approval exists | enforced -- gate 4 (action_type match) |
| No send unless OAuth account matches owner_email | enforced (Sprint-15 + Sprint-16 double check) |
| No send unless current Gmail draft matches approval snapshot | NEW -- enforced, this PR |
| No trust auto-escalation | unchanged |

## Files

```
modified:   backend/app/services/controlled_execution_handlers/gmail_send_existing_draft.py
modified:   backend/tests/test_gmail_send_existing_draft_handler.py
new:        docs/Ultraview/PR_GMAIL_SEND_DRAFT_INTEGRITY_CHECK_REPORT.md
```

## Next: PR-3 -- Google OAuth Live Readiness Test
