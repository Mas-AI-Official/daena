# DAENA -- Sprint-14 Phase 3 Controlled Writes Smoke + Final Report

**Sprint:** DAENA-PHASE3-CONTROLLED-WRITES-SPRINT-14
**PR:** 7 of 7 (final)
**Date:** 2026-05-06
**Author:** Mythos (Daena, via Claude Code)

This is the truth at the close of Sprint-14. Daena now crosses
from "proposes-only" to "controlled real-world actor" -- but only
for the three safest write actions, only after every gate passes.

## What Sprint-14 actually shipped

| PR | What | Commit |
|---|---|---|
| 1 | Controlled execution dispatch spine + 6 gates | local |
| 2 | gmail.create_draft (first WRITE_TOOL) + Sprint-14 set lock | local |
| 3 | calendar.create_tentative_event_without_invites | local |
| 4 | local.file_change_proposal (diff, not direct write) | local |
| 5 | trust ladder foundation (record-only) | local |
| 6 | Phase 3 approval modal (rich payload preview) | local |
| 7 | this report | local |

## WRITE_TOOLS: from empty to three

```python
# Sprint-13 PR-8:
WRITE_TOOLS = frozenset()

# Sprint-14 PR-2:
WRITE_TOOLS = frozenset({
    "gmail.create_draft",
    "calendar.create_tentative_event_without_invites",
    "local.file_change_proposal",
})
```

The Sprint-13 PR-8 contract test that asserted "WRITE_TOOLS is
empty" was renamed to `test_write_tools_is_sprint14_set` and now
asserts the EXACT three-tool set. A new
`test_no_send_tool_in_allowlist` test pins the absence of any
`.send / .submit / .post / .apply / .pay` variant. Sprint-14 is
draft / tentative / proposal only.

## The 6 dispatch gates (load-bearing)

```
1. Autonomy mode == approved_execution    (Sprint-13 PR-1 mode)
2. PR-8 design contract validator         (tool_id, hash, bools)
3. Recomputed payload_hash matches        (canonical sort_keys SHA-256)
4. GoaRequest exists, approved, fresh,
   action_type matches tool_id            (DB lookup)
5. Tool handler registered                (closed registry)
6. Handler runs                           (gmail / calendar / file)
```

Each gate raises `ControlledExecutionRefused` with a stable code.
The 9 codes are pinned by `TestStableRefusalContract` -- renaming
one fails CI.

## Stable refusal codes

```
autonomy_mode_does_not_allow_dispatch
design_contract_failed
payload_hash_mismatch
approval_id_not_uuid
approval_not_found
approval_not_in_approved_state
approval_expired
approval_tool_id_mismatch
tool_handler_not_registered
oauth_not_connected:google
owner_email_required
payload_field_missing:<field>
attendees_not_allowed_in_tentative_tool
target_path_outside_repo
target_path_is_secret_file
change_type_delete_not_allowed_in_proposal_v1
change_type_invalid
```

## What every Sprint-14 write does NOT do

| Gmail | Calendar | File |
|---|---|---|
| send | invite-send | overwrite |
| reply-send | guest notification | delete |
| attachment-send | external email | secret-file edit |
| | | escape repo root |

## Smoke verification

| Check | Pass? |
|---|---|
| backend boots with handlers package import wired | yes -- main.py lifespan logs `controlled_execution.handlers.registered` |
| frontend tsc clean | 0 errors |
| dispatch endpoint mounted at `/api/v1/integrations/controlled-execution/dispatch` | tested |
| All writes blocked in default autonomy mode (research_draft) | tested -- `TestAutonomyModeGate::test_default_mode_refuses` |
| Gmail draft requires approval + consent + payload_hash | tested -- 8 handler tests |
| Gmail send is impossible | enforced -- `.send` not in WRITE_TOOLS; `test_no_send_tool_in_allowlist` |
| Calendar event creates no invites | enforced -- attendees=None always; `test_create_event_called_without_attendees` |
| File proposal does not overwrite | enforced -- artifact-only; status="proposed", applied_at=null |
| Trust ladder records but does not auto-execute | enforced -- `TestNoAutoExecutionSurface` |
| Phase 3 limited to 3 approved tools only | enforced -- `WRITE_TOOLS` closed |
| No send/submit/post/apply broad paths exist | tested -- `test_no_send_tool_in_allowlist` |
| Frontend tsc | clean |
| Backend tests | 106/106 pass on Sprint-14 + Sprint-13 + Sprint-12 fast subset |

## Hard-rule audit (full Sprint-14)

| Rule | Status |
|---|---|
| No deploy | applied |
| No force push | applied |
| No secrets read / printed / committed | applied -- handler results scrub access_token / refresh_token |
| No payment / refund / subscription | applied |
| No unauthorized scan | applied |
| No browser automation on external sites | applied |
| No direct send / submit / post / apply in this sprint | enforced + tested |
| No bypass of OAuth / account authorization | enforced -- `oauth_not_connected:google` refusal before any HTTP call |
| No global package installs | applied |
| No removing Asset Shield | applied -- gates 1-3 still fire |
| No fake success | enforced -- "Daena proposes; never auto-executes" rule still encoded as DATA across PR-4/PR-6 of Sprint-13 |
| No write unless full PR-8 contract passes | enforced + tested |

## Five additions on top of GPT-5.5's brief, all landed

| Addition | Where it landed |
|---|---|
| Autonomy-mode gate in dispatch | PR-1 gate 1 |
| OAuth-not-connected refusal explicit | PR-2 + PR-3 (`oauth_not_connected:google`) |
| Update PR-8 contract test deliberately | PR-2 (renamed + locked Sprint-14 set + send-absence test) |
| Idempotency design hook | PR-1 registry pattern (handler-level idempotency lands when first send tool ships) |
| Locked canonical payload-hash format | PR-1 `compute_payload_hash` with regression test |

## How far from 100% Daena VP

Per the operator's estimate at sprint kick-off:

> After Sprint-14: Daena becomes controlled real-world actor beta.
> Maybe 65-70% toward full VP.

Daena now:
- has a single Phase 3 write surface
- can create a Gmail draft (no send) after operator approval
- can create a Calendar tentative event (no invites) after operator approval
- can propose a local file change as a diff artifact (no apply)
- records every approval / rejection in the trust ladder
- shows every Phase 3 request in a rich modal with full preview

Daena still cannot:
- send / submit / post / apply (Sprint-15+)
- scan unauthorized targets
- bypass OAuth
- auto-execute any patch
- raise its own trust tier

That's the wall the next sprint crosses with founder approval, not
this one.

## Sprint-14 commit log

```
PR-1 controlled execution dispatch spine
PR-2 controlled gmail.create_draft as first phase 3 write
PR-3 controlled calendar tentative event without invites
PR-4 controlled file change proposal (diff, not direct write)
PR-5 trust ladder foundation (record-only)
PR-6 phase 3 controlled execution approval modal
PR-7 (this report)
```

## End

If the operator approves, push fast-forward to `origin/master`.
No deploy. No Phase 3 unlock beyond the locked three-tool set.

Mythos out.
