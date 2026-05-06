"""File Proposal Apply Design Lock -- Sprint-15 PR-5 (2026-05-06).

This module is design-only. It does NOT apply any file change,
does NOT open any apply endpoint, does NOT register any
controlled-execution handler.

What it locks
-------------

The contract for any future ``local.file_change_proposal.apply``
write tool. When a later sprint enables actual file-change apply,
the executor MUST consume an ``ApplyFileChangeProposalRequest``
that carries every field below. Missing any field is a hard refuse.

The 9-field contract
--------------------

::

    proposal_id              -> uuid of the FileChangeProposal row
                                created by the existing
                                local.file_change_proposal tool
    current_file_hash        -> sha256 of the on-disk file at
                                apply-time (refuse on mismatch:
                                file changed since proposal)
    approved_diff_hash       -> sha256 of the approved diff body
                                (refuse on mismatch: diff tampered
                                between approval and apply)
    repo_root_relative_path  -> path under D:\\Ideas\\Daena (refuse
                                if it resolves outside the repo or
                                is a secret-file pattern)
    backup_file_path         -> absolute path under
                                backend/.file_change_backups/<uuid>/
                                where the pre-apply file copy was
                                written (refuse if the backup
                                doesn't exist on disk)
    rollback_patch           -> reverse-direction patch the executor
                                stores so the operator can undo
                                with one command
    tests_to_run_after_apply -> list[str] of test paths the executor
                                runs AFTER applying. If any fails
                                the executor MUST roll back.
    commit_approval_id       -> SECOND approval row id authorising
                                a commit (apply-then-commit is two
                                walls, not one)
    change_type              -> Literal["modify"] only. PR-5 forbids
                                "delete" outright.

Additional locks
----------------

* ``local.file_change_proposal.apply`` is NOT in WRITE_TOOLS in
  Sprint-15. Sprint-16 (or later) is the only sprint allowed to
  add it. The contract test
  ``TestApplyToolStaysOutOfWriteTools`` pins this.
* No HTTP endpoint. Adding one without flipping the constants in
  this module on purpose breaks the Sprint-16 unlock test.
* Adding the apply tool requires touching:
    1. ``WRITE_TOOLS`` in ``controlled_execution_design``
    2. The Asset Shield egress allowlist for local.file
    3. The plain-English policy compiler templates for
       file-change-apply
    4. A dedicated negative test that proves missing fields refuse
    5. A backup directory is gitignored and writable
    6. A second-approval wall for the commit step

The repo-root + secret-file checks REUSE the regex set already
shipped in ``controlled_execution_handlers/file_change_proposal.py``
PR-4 of Sprint-14. The apply tool's path-resolution rules MUST be
identical to the proposal tool's, byte for byte.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal


# ── The apply tool stays OUT of WRITE_TOOLS ──────────────────────────


# Sprint-15 PR-5: the apply tool is intentionally NOT in WRITE_TOOLS.
# The constant below is for readability + the contract test only.
APPLY_TOOL_ID: Final[str] = "local.file_change_proposal.apply"


# ── 9-field locked contract ──────────────────────────────────────────


_REQUIRED_APPLY_FIELDS: Final[tuple[str, ...]] = (
    "proposal_id",
    "current_file_hash",
    "approved_diff_hash",
    "repo_root_relative_path",
    "backup_file_path",
    "rollback_patch",
    "tests_to_run_after_apply",
    "commit_approval_id",
    "change_type",
)


# Locked at design time. ``"delete"`` is explicitly excluded; PR-5
# forbids destructive apply outright. A separate sprint can introduce
# a ``"delete_with_two_approvals"`` literal later, but only with a
# new contract test that pins the new shape.
ApplyChangeType = Literal["modify"]


@dataclass(frozen=True)
class ApplyFileChangeProposalRequest:
    """The shape every future file-change apply must consume.

    Every field is required. The executor that ships in a later
    sprint will:

      1. Read the on-disk file at ``repo_root_relative_path``,
         compute sha256, refuse if != ``current_file_hash``.
      2. Compute sha256 of the approved diff payload, refuse if
         != ``approved_diff_hash``.
      3. Confirm ``backup_file_path`` exists and is non-empty.
      4. Apply the diff. If apply raises, restore the backup and
         refuse.
      5. Run every entry in ``tests_to_run_after_apply``. If any
         non-zero exits, restore the backup and refuse.
      6. Look up ``commit_approval_id``: separate approval row
         whose ``action_type`` is the commit tool. If absent or
         not approved, leave the file applied but do NOT commit.
    """

    proposal_id: str
    current_file_hash: str
    approved_diff_hash: str
    repo_root_relative_path: str
    backup_file_path: str
    rollback_patch: str
    tests_to_run_after_apply: list[str]
    commit_approval_id: str
    change_type: ApplyChangeType


# ── Refusal helper (design-only; does not actually execute) ──────────


class FileProposalApplyDesignError(Exception):
    """Raised when an apply request fails the design contract.

    PR-5 ships the validation function so the future executor can
    call it as a hard wall. PR-5 itself does not apply anything.
    """


def validate_apply_file_change_proposal_request(
    req: ApplyFileChangeProposalRequest,
) -> None:
    """Validate the request against the locked contract. Raises on
    failure.

    This is the PURE validator. No file-system hop, no Asset Shield
    call, no DB lookup. The executor must populate every field by
    actually doing the disk + DB + diff work, and pass the results
    in.
    """
    if not req.proposal_id:
        raise FileProposalApplyDesignError("proposal_id_required")
    if not req.current_file_hash or len(req.current_file_hash) != 64:
        raise FileProposalApplyDesignError(
            "current_file_hash_required_sha256_hex"
        )
    if not req.approved_diff_hash or len(req.approved_diff_hash) != 64:
        raise FileProposalApplyDesignError(
            "approved_diff_hash_required_sha256_hex"
        )
    if not req.repo_root_relative_path:
        raise FileProposalApplyDesignError(
            "repo_root_relative_path_required"
        )
    if not req.backup_file_path:
        raise FileProposalApplyDesignError("backup_file_path_required")
    if not req.rollback_patch:
        raise FileProposalApplyDesignError("rollback_patch_required")
    if not isinstance(req.tests_to_run_after_apply, list):
        raise FileProposalApplyDesignError(
            "tests_to_run_after_apply_must_be_list"
        )
    if not req.commit_approval_id:
        raise FileProposalApplyDesignError(
            "commit_approval_id_required_separate_from_proposal_approval"
        )
    if req.change_type != "modify":
        raise FileProposalApplyDesignError(
            f"change_type_must_be_modify_in_apply_v1: got {req.change_type!r}"
        )
    return None
