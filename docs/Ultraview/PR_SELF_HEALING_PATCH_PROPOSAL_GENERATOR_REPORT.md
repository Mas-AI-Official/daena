# PR-3 -- Self-Healing Patch Proposal Generator

**Sprint:** DAENA-SPRINT-17-FILE-APPLY-AND-SELF-HEALING-PATCH-LOOP
**PR:** 3 of 7
**Date:** 2026-05-06

## Goal

Bridge Sprint-13's failure-detection layer to Sprint-17 PR-1's
file-apply controlled tool. Given a Failure + a brain-generated
candidate patch, produce a controlled-execution payload AND the
metadata the future apply approval will need.

## What ships

`backend/app/services/self_healing_patch_proposal.py` (new):

* `SelfHealingPatchProposalInput` frozen dataclass: `failure_id`,
  `target_repo_relative`, `change_type`, `diff_text`,
  `tests_to_run_after_apply`, `suggested_brain`,
  `repair_action_class`.
* `SelfHealingPatchProposalResult` frozen dataclass:
  `valid: bool`, `refusal_code`, `refusal_detail`,
  `proposal_payload`, `metadata`.
* `propose_patch(failure, patch)` runs the SAME safety walls as
  Sprint-17 PR-1's apply handler (so an invalid patch is rejected
  at proposal time, before any approval is even raised):
    - `suggested_brain == "human"` -> `no_brain_callable`
    - `change_type != "modify"` -> `change_type_not_modify_v1`
    - empty diff_text -> `diff_text_empty`
    - secret file -> `target_path_is_secret_file`
    - outside repo -> `target_path_outside_repo`
    - empty / shell-shaped pytest specs -> `invalid_test_path`
* On valid input, returns a result carrying:
    - `proposal_payload` shaped for the existing
      `local.file_change_proposal` controlled tool (target_path,
      change_type, diff_text)
    - `metadata.self_healing` with failure id + subsystem +
      severity + suggested_brain + repair_action_class for audit
    - `metadata.future_apply_approval` with the file_apply_preview
      shape the Sprint-17 PR-2 modal expects (target / hashes
      placeholders / tests / secret-pass / repo-pass / excerpt)

## Brain routing reuses Sprint-13 PR-6

This PR does NOT define new brain routing logic. It consumes
`failure.suggested_brain` (codex_cli / claude_code / ollama_backend
/ vllm / human) which Sprint-13 already encodes per the CLAUDE.md
cross-AI delegation table. Per the brief:

* Mechanical fixes -> codex_cli
* Multi-file reasoning -> claude_code
* Local probes -> ollama_backend / vllm
* When no brain callable -> "human" -> refused with
  `no_brain_callable` (caller routes to operator)

## Locked invariants

| Invariant | Where |
|---|---|
| Pure shaping; no side effects | `TestNoSideEffects::test_function_does_not_call_subprocess` |
| Human-suggested failures refuse auto-patch | `TestHumanFallback::test_human_brain_refused` |
| change_type locked to "modify" v1 | `TestChangeTypeLock` (5 parametrized: delete / create / rename / MODIFY case / empty) |
| Empty diff refused | `TestDiffTextValidation` (3 parametrized) |
| Secret file refused | `TestPathValidation::test_secret_file_refused` |
| Outside-repo refused | `TestPathValidation::test_outside_repo_refused` |
| Shell-shaped pytest spec refused | `TestPytestPathValidation::test_shell_shaped_test_refused` |
| Empty test list refused | `test_empty_test_list_refused` |
| Happy path returns full payload + metadata | `TestHappyPath::test_valid_proposal_returns_payload` |

## What is NOT in this PR

* **No upstream brain call.** The caller is responsible for invoking
  Codex / Claude / Ollama and capturing the `diff_text`. PR-3 only
  shapes + validates the result.
* **No GoaRequest creation.** This PR returns a payload + metadata;
  PR-4 of this sprint wires the dispatch + approval-creation flow.
* **No apply.** PR-1 ships the apply handler; PR-3 just produces
  inputs that PR-1 will accept.
* **No commit.** PR-5 of this sprint ships the commit wall.

## Tests

```
backend/tests/test_self_healing_patch_proposal.py    15 tests
```

15/15 pass.

## Files

```
new:        backend/app/services/self_healing_patch_proposal.py
new:        backend/tests/test_self_healing_patch_proposal.py
new:        docs/Ultraview/PR_SELF_HEALING_PATCH_PROPOSAL_GENERATOR_REPORT.md
```

## Next: PR-4 -- Self-Healing Apply/Test/Rollback Loop
