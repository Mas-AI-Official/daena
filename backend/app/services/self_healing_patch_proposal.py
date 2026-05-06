"""Self-Healing Patch Proposal Generator -- Sprint-17 PR-3 (2026-05-06).

Bridges the Sprint-13 PR-6 failure-detection layer to the Sprint-17
PR-1 file-change-apply controlled tool. Given:

  * a ``Failure`` (from ``self_healing_service.enumerate_failures``)
  * the candidate patch produced by the suggested brain (a Codex /
    Claude / Ollama call upstream of this module)

this module shapes a payload the existing
``local.file_change_proposal`` controlled tool will accept, and
ALSO records the metadata the future apply approval will need:

  * target_repo_relative
  * change_type (locked to "modify" for v1)
  * diff_text (the full new file content; v1 contract)
  * tests_to_run_after_apply (pytest paths, validated)
  * suggested_brain + repair_action_class for audit

This module does NOT:

  * call any LLM
  * write to disk
  * dispatch any controlled execution
  * apply any patch
  * commit anything

It is a PURE shaping + validation layer. The caller (PR-4 of this
sprint, or a future autonomous loop) is responsible for routing
the upstream brain call, capturing its diff_text, and dispatching
the controlled tool.

Refusal reasons (returned, not raised, so the caller can route
back to a human):

::

    no_brain_callable
        suggested_brain == "human"; auto-generation refused.

    target_path_outside_repo / target_path_is_secret_file
        Reuses local_file_safety regex.

    invalid_test_path
        A test spec failed validate_pytest_path.

    diff_text_empty
        Generated patch was empty.

    change_type_not_modify_v1
        Only modify is supported in apply v1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.services.controlled_execution_dispatch import ControlledExecutionRefused
from app.services.local_file_safety import (
    is_secret_file,
    resolve_under_repo,
    validate_pytest_path,
)
from app.services.self_healing_service import Failure


PatchChangeType = Literal["modify"]


@dataclass(frozen=True)
class SelfHealingPatchProposalInput:
    """The input to ``propose_patch``. Carries everything needed to
    build a controlled-execution payload + a future apply approval.
    """

    failure_id: str
    target_repo_relative: str
    change_type: str  # only "modify" passes validation in v1
    diff_text: str
    tests_to_run_after_apply: list[str]
    suggested_brain: str
    repair_action_class: str


@dataclass(frozen=True)
class SelfHealingPatchProposalResult:
    """Output of ``propose_patch``. Carries either the controlled-
    execution payload (when valid) OR a refusal reason (when one of
    the static walls refused).

    Why both shapes in one return: the caller is the autonomous
    repair loop, and "refused" is a NORMAL state -- it means the
    failure must route back to a human. Raising would treat that
    as exceptional. Returning a tuple-like result lets the caller
    handle "valid" and "needs_human" symmetrically.
    """

    valid: bool
    refusal_code: str | None
    refusal_detail: str | None
    proposal_payload: dict[str, Any] | None
    metadata: dict[str, Any] = field(default_factory=dict)


def _refused(code: str, detail: str) -> SelfHealingPatchProposalResult:
    return SelfHealingPatchProposalResult(
        valid=False,
        refusal_code=code,
        refusal_detail=detail,
        proposal_payload=None,
    )


def propose_patch(
    *, failure: Failure, patch: SelfHealingPatchProposalInput,
) -> SelfHealingPatchProposalResult:
    """Validate the patch input and return a controlled-execution
    payload for the local.file_change_proposal tool.

    The patch contract:

      * change_type must be "modify"
      * diff_text must be non-empty
      * target_repo_relative must resolve under the repo root
      * target_repo_relative must NOT match a secret-file pattern
      * tests_to_run_after_apply must be non-empty AND every entry
        must pass validate_pytest_path (no shell metachars, no
        absolute paths, no flags)
      * suggested_brain must NOT be "human" (auto-generation
        refused; route back to operator)

    On success, returns a result with ``valid=True`` and a
    ``proposal_payload`` ready to feed into
    ``local.file_change_proposal`` via the controlled-execution
    dispatch. The metadata block carries the future apply payload
    fields the approval-creation flow will need.
    """
    if patch.suggested_brain == "human":
        return _refused(
            "no_brain_callable",
            "Failure suggests human review; auto-patch refused.",
        )

    if patch.change_type != "modify":
        return _refused(
            "change_type_not_modify_v1",
            f"v1 supports change_type='modify' only; got "
            f"{patch.change_type!r}",
        )

    if not patch.diff_text or not patch.diff_text.strip():
        return _refused(
            "diff_text_empty",
            "Brain returned an empty patch; route to human.",
        )

    if not patch.target_repo_relative or not patch.target_repo_relative.strip():
        return _refused(
            "target_path_outside_repo",
            "target_repo_relative is empty",
        )

    if is_secret_file(patch.target_repo_relative):
        return _refused(
            "target_path_is_secret_file",
            f"{patch.target_repo_relative!r} matches a secret pattern",
        )

    try:
        resolve_under_repo(patch.target_repo_relative)
    except ControlledExecutionRefused as exc:
        return _refused(exc.code, str(exc))

    if not patch.tests_to_run_after_apply:
        return _refused(
            "invalid_test_path",
            "tests_to_run_after_apply must be non-empty",
        )
    try:
        validated_tests = [
            validate_pytest_path(t) for t in patch.tests_to_run_after_apply
        ]
    except ControlledExecutionRefused as exc:
        return _refused(exc.code, str(exc))

    # Build the local.file_change_proposal payload.
    proposal_payload: dict[str, Any] = {
        "target_path": patch.target_repo_relative,
        "change_type": patch.change_type,
        "diff_text": patch.diff_text,
    }

    # Build the metadata the future apply approval will carry. The
    # approval-creation flow stamps this on the new GoaRequest's
    # action_params under file_apply_preview so the modal renders.
    metadata: dict[str, Any] = {
        "self_healing": {
            "failure_id": patch.failure_id,
            "failure_subsystem": failure.subsystem,
            "failure_severity": failure.severity,
            "suggested_brain": patch.suggested_brain,
            "repair_action_class": patch.repair_action_class,
        },
        "future_apply_approval": {
            "target_repo_relative": patch.target_repo_relative,
            "change_type": patch.change_type,
            "tests_to_run_after_apply": validated_tests,
            "diff_preview_lines": len(patch.diff_text.splitlines()),
            "diff_excerpt": patch.diff_text[:800],
            # secret + outside-repo checks both passed at this point
            # because the validators above didn't refuse.
            "secret_file_check_passed": True,
            "outside_repo_check_passed": True,
        },
    }

    return SelfHealingPatchProposalResult(
        valid=True,
        refusal_code=None,
        refusal_detail=None,
        proposal_payload=proposal_payload,
        metadata=metadata,
    )
