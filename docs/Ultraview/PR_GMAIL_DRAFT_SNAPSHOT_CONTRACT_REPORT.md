# PR-1 -- Gmail Draft Snapshot Contract

**Sprint:** DAENA-SPRINT-16-SEND-INTEGRITY-AND-LIVE-GOOGLE-PROOF
**PR:** 1 of 6
**Date:** 2026-05-06

## Goal

Close the draft-edit-after-approval gap. The Sprint-15 send hash
binds `{draft_id, owner_email}` only -- it blocks wrong-id and
wrong-account substitution but NOT content mutation between
approval and dispatch. Sprint-16 binds the send approval to a
captured snapshot of the draft state at approval time, then
verifies it at send time.

## What ships

`backend/app/services/gmail_draft_snapshot.py` (new):

* `GmailDraftSnapshot` frozen dataclass with 9 fields:
  `draft_id`, `owner_email`, `to`, `from_value`, `subject`,
  `body_snippet`, `captured_at`, optional `message_id`,
  optional `thread_id`.
* `compute_draft_metadata_hash(snapshot)` -- LOCKED canonical
  format. sha256 of normalized, sort_keys, separators=(",", ":"),
  ensure_ascii=False JSON. Excludes `captured_at` from the hash
  so wall-clock drift doesn't break verification. Lower-cases +
  strips email-shaped fields. Drops None / empty-string values
  so absence and explicit-empty hash identically.
* `build_snapshot_from_gmail_draft(draft_meta, owner_email, ...)`
  -- builds a snapshot from the response of Gmail's
  `GET /drafts/{id}?format=metadata`. Reads headers
  case-insensitively. Truncates body_snippet to 240 chars.
* `first_drift_field(approved, current)` -- returns the FIRST
  drifted field name in load-bearing order:
  `owner_email` -> `to` -> `subject` -> `from_value` -> `draft_id`
  -> `message_id` -> `thread_id` -> `body_snippet`. The handler in
  PR-2 maps each name to a stable refusal code.

## Why these 9 fields

| Field | Why locked |
|---|---|
| draft_id | Pins WHICH draft is approved |
| owner_email | Pins WHICH Google account; lower+strip normalized |
| message_id | Gmail's draft-internal message id; drift implies a different physical message |
| thread_id | Different thread = different conversation context |
| to | Primary attack vector for substitution |
| from_value | Asserts the From: header didn't change (display-name spoof catch) |
| subject | Operator-visible field; drift here is the most likely tamper signal |
| body_snippet | First 240 chars of body; full body NOT stored to respect Asset Shield boundaries |
| captured_at | Audit-only timestamp; EXCLUDED from hash so time drift never refuses |

## Locked invariants

| Invariant | Where |
|---|---|
| Hash format pinned (sha256 of normalized JSON) | `TestCanonicalDraftHash::test_format_is_sha256_of_normalized_compact_json` |
| captured_at excluded from hash | `test_captured_at_excluded` |
| Email fields normalized before hashing | `test_email_normalization` |
| None and empty-string equivalent | `test_none_and_empty_excluded` |
| Hash stable across key permutations | `test_dict_key_order_does_not_affect_hash` |
| Subject change changes hash | `test_subject_change_changes_hash` |
| To change changes hash | `test_to_change_changes_hash` |
| Snapshot frozen (immutable post-build) | `TestSnapshotIsFrozen::test_dataclass_frozen` |
| First-drift order is load-bearing for refusal codes | `TestFirstDriftField::*` |

## What is NOT in this PR

* **No upstream creator wired.** This PR ships the contract only.
  PR-2 of this sprint enforces it at dispatch time. The flow that
  CAPTURES the snapshot at send-approval-creation time lives in
  whichever upstream code raises the GoaRequest -- not yet built.
* **No body persistence.** The snapshot stores a 240-char snippet
  only. Storing full body would expand the Asset Shield surface;
  the snippet is enough to catch substantive content drift while
  staying within egress boundaries.
* **No backend endpoint.** Snapshot lives in
  `GoaRequest.action_params['draft_snapshot']` -- no new route
  needed.

## Tests

```
backend/tests/test_gmail_draft_snapshot.py     17 tests
```

17/17 pass. Test classes:
- `TestCanonicalDraftHash` (7): format pin, captured_at exclusion,
  email normalization, None/empty equivalence, key-order stability,
  subject drift, to drift.
- `TestSnapshotExtraction` (4): build from Gmail metadata,
  case-insensitive headers, missing-header handling, body
  truncation.
- `TestFirstDriftField` (5): no drift returns None, captured_at
  drift returns None, to/subject/owner_email drift order.
- `TestSnapshotIsFrozen` (1): immutable dataclass.

## Files

```
new:        backend/app/services/gmail_draft_snapshot.py
new:        backend/tests/test_gmail_draft_snapshot.py
new:        docs/Ultraview/PR_GMAIL_DRAFT_SNAPSHOT_CONTRACT_REPORT.md
```

## Next: PR-2 -- Send-Time Draft Integrity Check
