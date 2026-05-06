# PR-5 -- Trust-Aware VP Chat Commands

**Sprint:** DAENA-SPRINT-18-TRUST-LADDER-AND-ROUTINE-AUTONOMY
**PR:** 5 of 6
**Date:** 2026-05-06

## Goal

Daena should be able to answer six specific operator questions
about her own autonomy state -- WITHOUT an LLM in the path.
Authoritative state from `trust_policy` and `routine_autonomy`.
Deterministic regex pattern matching. No hallucinated permissions.

## What ships

`backend/app/services/trust_chat_commands.py` (new):

* Six regex patterns matched in order:
    1. `pause autonomy`
    2. `resume research-only autonomy` (also "resume autonomy")
    3. `what can you do without asking me`
    4. `what still needs approval`
    5. `show trusted routines` (also "show routines")
    6. `why didn't / did you not execute / run / fire`
* Each command runs a deterministic Python function that reads
  `trust_policy.list_policies()`, `routine_autonomy.list_routines()`,
  or mutates the global pause flag.
* `parse_and_run(text)` returns `ChatCommandResult(matched, command,
  summary, structured)`. Matched=False on no match -- caller can
  fall back to LLM if it wants.
* The `summary` field is a deterministic one-liner. No
  exclamation marks. No "I think" / "maybe". No hedging.

`backend/app/api/v1/trust_chat.py` (new):

* `POST /api/v1/trust/chat` -- thin wrapper around
  `parse_and_run`, returns the structured result verbatim.

`backend/app/api/v1/__init__.py` (modified): mounts the new router
at `/api/v1/trust/chat`.

## Mythos design choices

**No LLM in the path.** This is the load-bearing rule. If we
asked an LLM to summarize trust state, it could hallucinate
permissions ("I can also send a few low-risk emails on your
behalf!" -- the answer is no). Pattern match + deterministic
runner = the answer is exactly what the backend state says.

**Pause / resume is real, not theatrical.** "Pause autonomy" calls
`routine_autonomy.pause_all()` which mutates the JSON file. The
next routine `run_once` returns `GLOBAL_PAUSED`. This is the same
operator pause as the API endpoint, just exposed through chat.

**"Resume research-only" does NOT change tier policy.** The label
is honest because scheduler-initiated dispatches still cannot
auto-approve (trust wall #2). So routines run, but the trust
ladder still gates anything they could try to write externally.
A test pins this: `test_resume_does_not_change_trust_tiers`.

**Pattern table is order-sensitive.** "Pause autonomy" is checked
BEFORE "what" patterns so the more-specific matchers win first.
Documented in the code so future contributors don't reorder.

**No forbidden surface reachable.** `TestNoForbiddenSurfaceReached`
runs every command and asserts the structured response contains no
`sent` / `applied_at` / `commit_sha` keys. None of these commands
can dispatch.

## Locked invariants

| Invariant | Where |
|---|---|
| Six canonical phrases recognized | `TestPatternMatch::test_recognized_phrase` (11 parametric variants) |
| Unrelated text returns matched=False | `test_unrelated_text_no_match` |
| Empty / non-string returns matched=False (no raise) | `test_empty_or_non_string_no_match` |
| "What without approval" empty when no tiers granted | `TestWhatWithoutApproval::test_empty_when_no_tiers_granted` |
| "What without approval" lists granted tiers only | `test_lists_only_granted_tiers` |
| "What needs approval" includes all forbidden tools | `TestWhatNeedsApproval::test_includes_all_forbidden` |
| Pause then resume mutates global flag | `TestPauseAndResume::test_pause_then_resume` |
| Resume does NOT change trust tiers | `test_resume_does_not_change_trust_tiers` |
| No command output contains sent / applied_at / commit_sha | `TestNoForbiddenSurfaceReached` |
| Summary strings are deterministic (no LLM hedging) | `TestDeterministicSummary` |

## Hard rules audit

| Rule | Status |
|---|---|
| No deploy | applied |
| No force push | applied |
| No secrets read / printed / committed | applied |
| No external send / submit / post / pay | applied -- commands cannot reach those surfaces |
| No file delete / multi-file apply | applied |
| Answers come from authoritative backend state | enforced -- runners read trust_policy / routine_autonomy |
| No hallucinated permissions | enforced -- no LLM in the path; tested |
| Hidden action absent | enforced -- pause / resume are observable mutations on the gitignored state file |

## Tests

```
backend/tests/test_trust_chat_commands.py   23 tests
```

23/23 pass.

## Files

```
new:        backend/app/services/trust_chat_commands.py
new:        backend/app/api/v1/trust_chat.py
new:        backend/tests/test_trust_chat_commands.py
modified:   backend/app/api/v1/__init__.py
new:        docs/Ultraview/PR_TRUST_AWARE_VP_CHAT_REPORT.md
```

## Next: PR-6 -- Sprint-18 smoke + final report
