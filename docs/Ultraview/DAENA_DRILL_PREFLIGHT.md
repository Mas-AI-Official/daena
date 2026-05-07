# Daena Live-Send Drill — Pre-flight
Date: 2026-05-07
Author: DAENA-GOOGLE-OAUTH-LIVE-PROOF-COMPLETION (continued)
Predecessor: `8fdaa4d` (OAuth runbook + probe script)

## Why this exists

The OAuth runbook (`DAENA_GOOGLE_OAUTH_LIVE_PROOF_COMPLETION.md`) ends at step 4 with `READY=True` and tells the operator to ping me before continuing. While the operator is doing OAuth, I'm pre-flighting everything that runs the moment they ping back — so the drill itself is friction-free and every refusal code is pre-mapped.

This document captures the full safety architecture, the gates each dispatch traverses, what audit rows look like, and the test coverage that proves the wall holds.

## Test coverage proof (already passes)

Ran 2026-05-07 against the live tree:

```
backend/tests/test_gmail_send_dispatch_integration.py    -> 42/42 ╳ 2 skipped (combined)
backend/tests/test_live_send_drill.py
backend/tests/test_gmail_send_existing_draft_handler.py
backend/tests/test_gmail_draft_snapshot.py
```

These pin every refusal code in the integrity wall. If the drill ever produces a refusal not seen here, that's a bug worth investigating before the operator authorizes a second send.

## OAuth scopes Daena requests (verified)

From `backend/app/services/integrations/oauth_service.py:59-84`:

| Provider | Scopes |
|---|---|
| Gmail | `gmail.send`, `gmail.readonly` |
| Calendar | `calendar.events` |
| Drive | `drive.readonly`, `drive.metadata.readonly` |

**Minimal-privilege.** No full-Gmail scope. No full-Drive write. Drive is read-only across the board. Operator's Google consent screen will list these exactly. If Google's consent UI shows MORE than these scopes, something is wrong — refuse and ping me.

## The 10-field locked contract

From `controlled_execution_design.py:97-108`. Every dispatch request must carry all 10:

| Field | What |
|---|---|
| `approval_id` | UUID of the approval row that authorizes this exact action |
| `consent_grant_id` | Asset Shield consent token id |
| `payload_hash` | SHA-256 hex (64 chars) of the canonical payload |
| `tool_id` | One of the 6 WRITE_TOOLS allowlist values |
| `owner_email` | The Google account whose token is used (e.g. `daena@mas-ai.co`) |
| `asset_shield_pass` | Bool, must be `true` |
| `policy_allowlist_pass` | Bool, must be `true` |
| `audit_preflight_row_id` | UUID of the audit row written BEFORE handler runs |
| `audit_result_row_id` | UUID of the audit row written AFTER handler returns |
| `rollback_or_undo_instruction` | Plain English: "delete the draft" / "this is irreversible — operator initiated send" |

If any field is missing or any boolean is `false`, the dispatcher refuses at Gate 2 (PR-8 pure validator).

## The six gates (in order; load-bearing)

From `controlled_execution_dispatch.py:210-260` + handler-level integrity wall:

### Gate 1 — Autonomy mode
- Source: `_check_autonomy_mode_allows_dispatch()`
- Refusal: dispatch refused if autonomy mode forbids write tools
- Effect: stops the request before any state is touched

### Gate 2 — PR-8 pure validator
- Source: `validate_controlled_execution_request(request)`
- Checks: tool_id in WRITE_TOOLS, payload_hash exactly 64 hex chars, all bools True, all required strings non-empty
- Refusal codes: `tool_id_not_in_allowlist`, `payload_hash_required_sha256_hex`, `design_contract_failed`

### Gate 3 — Payload integrity
- Source: lines 231-239
- Recomputes `payload_hash` from the actual payload; refuses if mismatch
- Refusal code: `payload_hash_mismatch`
- This catches: payload tampering between approval and dispatch (e.g. someone changes the recipient after approval)

### Gate 4 — Approval row matches tool
- Source: lines 241-250
- Loads approval row by `approval_id` + `tenant_id`; verifies `approval.action_type == request.tool_id`
- Refusal code: `approval_tool_id_mismatch`
- This catches: trying to dispatch a SEND with a CREATE-DRAFT approval (and vice versa) — the create approval does NOT authorize send

### Gate 5 — Registered handler
- Source: lines 252-260
- Verifies `_TOOL_HANDLERS[tool_id]` exists
- Refusal code: `tool_handler_not_registered`
- Today's registered tools: `calendar.create_tentative_event_without_invites`, `gmail.create_draft`, `gmail.send_existing_draft`, `local.file_change_proposal`, `local.file_change_proposal.apply`, `local.git_commit_approved_patch`

### Gate 6 — Sprint-15/16 integrity wall (within `gmail.send_existing_draft` handler)
- Source: `gmail_send_existing_draft.py:14-74`
- Re-fetches the draft from Gmail before send
- Re-computes canonical metadata snapshot
- Compares against the snapshot taken at approval time
- Refusal codes: `draft_recipient_mismatch`, `draft_subject_mismatch`, `draft_owner_email_mismatch`, `draft_metadata_hash_mismatch`, `draft_not_found`, `draft_snapshot_required`

This is the moment-of-truth gate. **If the operator edits the draft in Gmail between approval and send, this gate MUST refuse.** The integrity-wall tests above prove it does.

## Audit row schema

Two rows per dispatch:

### Preflight row (written before handler)
- Written when Gate 5 passes; before handler runs
- Fields: `tool_id`, `approval_id`, `payload_hash` (first 16 chars), `owner_email`, `consent_grant_id`, `asset_shield_pass`, `policy_allowlist_pass`, `tenant_id`, `user_id`, `created_at`
- Purpose: prove this exact action was about to fire

### Result row (written after handler)
- Outcome: `SUCCESS` or `REFUSED:<code>` or `FAILED:<exception>`
- Includes refusal code if applicable (e.g. `oauth_not_connected:google`, `draft_recipient_mismatch`)
- For successful Gmail send: includes `gmail_message_id` (from Gmail's API response)
- Purpose: prove what actually happened

After a successful send, `/governance/audit` should show **both rows** with matching `approval_id`, `tool_id=gmail.send_existing_draft`, and the result row with `outcome=SUCCESS` + `gmail_message_id` populated.

## Refusal-code cheat sheet (full)

| Code | Origin | Cause | Operator fix |
|---|---|---|---|
| `tool_id_not_in_allowlist` | Gate 2 | tool_id not in WRITE_TOOLS | Use one of the 6 registered tools |
| `payload_hash_required_sha256_hex` | Gate 2 | hash wrong length/format | Compute SHA-256 hex (64 chars) of canonical payload |
| `design_contract_failed` | Gate 2 | required field missing or bool false | Check 10-field contract above |
| `payload_hash_mismatch` | Gate 3 | hash doesn't match recomputed payload | Re-canonicalize payload, recompute hash |
| `approval_tool_id_mismatch` | Gate 4 | approval row is for a different tool | Use the approval that matches this tool_id |
| `tool_handler_not_registered` | Gate 5 | handler missing in registry | Server config issue — ping me |
| `oauth_not_connected:google` | Handler | ConnectorInstance row missing for owner_email | Connect that account via /connections |
| `payload_field_missing:to` (etc) | Handler | Gmail field missing | Re-create draft with all required fields |
| `owner_email_required` | Handler | request lacks owner_email | Set owner_email = `daena@mas-ai.co` |
| `draft_not_found` | Gate 6 | Gmail returned 404 for draft_id | Draft was deleted; re-create |
| `draft_snapshot_required` | Gate 6 | approval row predates Sprint-16 snapshots | Re-create approval (Sprint-16 enforces snapshot) |
| `draft_owner_email_mismatch` | Gate 6 | snapshot owner ≠ current draft owner | Use same owner_email for create + send |
| `draft_recipient_mismatch` | Gate 6 | draft `to` field changed | Operator edited draft in Gmail; re-create |
| `draft_subject_mismatch` | Gate 6 | draft subject changed | Same; re-create |
| `draft_metadata_hash_mismatch` | Gate 6 | snapshot drifted, no specific field caught | Generic drift; re-create |

## What I will dispatch when you ping me

When you reach `READY=True`, ping me. The drill proceeds:

### Step A — Build a draft

I'll ask you for:
1. Recipient email (single address — single send only for first proof)
2. Subject (exact text)
3. Body (exact text)

Then I dispatch:
```
POST /api/v1/integrations/controlled-execution/dispatch
{
  "approval_id": "<created here>",
  "consent_grant_id": "<created here>",
  "payload_hash": "<sha256 of canonical payload>",
  "tool_id": "gmail.create_draft",
  "owner_email": "daena@mas-ai.co",
  "asset_shield_pass": true,
  "policy_allowlist_pass": true,
  "audit_preflight_row_id": "...",
  "audit_result_row_id": "...",
  "rollback_or_undo_instruction": "delete the Gmail draft"
}
```

You approve in `/governance/approvals`. Daena writes the draft.

### Step B — Verify draft in Gmail UI directly

You open `mail.google.com` as `daena@mas-ai.co` → Drafts → confirm exact recipient + subject + body match what you approved.

**Stop here. Do not proceed to send unless the draft contents are byte-exact.**

### Step C — Send the draft

I dispatch:
```
{
  "tool_id": "gmail.send_existing_draft",
  "owner_email": "daena@mas-ai.co",
  "draft_id": "<from Step A response>",
  "rollback_or_undo_instruction": "this is irreversible -- operator initiated send"
}
```

Separate approval. Gate 6 fires the snapshot check before send. If the snapshot drifted (e.g. you edited the draft in Step B), it refuses.

### Step D — Post-send verification

1. `mail.google.com` as `daena@mas-ai.co` → Sent → confirm message
2. `http://127.0.0.1:5173/governance/audit` → confirm both audit rows present, result row outcome=SUCCESS, gmail_message_id populated
3. `scripts/check-google-oauth.ps1` → send rate limit `used` should be 1

## Sanity check (recommended once)

Between Step A and Step C, do this **once**:
1. Open the draft in `mail.google.com` Drafts
2. Edit the recipient field (change a character)
3. Save the edit
4. Tell me to dispatch send anyway

The dispatcher MUST refuse with `draft_recipient_mismatch`. If it doesn't, Sprint-16 has a bug and we stop.

This is the operator's only foolproof way to verify the wall fires. The 42 passing tests prove it fires in unit tests; this proves it fires against your real Gmail. Worth the 30 seconds.

## Sprint-22 readiness

After Step D + the sanity check, all three gates are passed:
1. ✅ Google OAuth client configured (probe shows `client_configured=True`)
2. ✅ Both accounts connected (probe shows `READY=True`)
3. ✅ One operator-approved live send completed cleanly + integrity wall verified

Sprint-22 may then start. Until then, it stays gated.

## What I will NOT do

- Auto-approve any approval row — operator approval only
- Send to a recipient that wasn't operator-supplied for this exact drill
- Skip the Step C sanity check unless operator explicitly opts out
- Proceed without seeing the audit rows confirm SUCCESS in `/governance/audit`
- Re-run the drill with a different recipient without a fresh approval cycle
