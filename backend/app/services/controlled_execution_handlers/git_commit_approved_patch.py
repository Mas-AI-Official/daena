"""local.git_commit_approved_patch handler -- Sprint-17 PR-5 (2026-05-06).

The SECOND wall on top of Sprint-17 PR-1's apply. Applying a patch
does NOT authorize a commit. This tool commits the file (or set of
files) that an apply operation produced, with its own approval.

Why two walls:

  * Apply landing -> tests pass -> file is on disk.
  * Operator looks at the modified file, decides whether to commit.
  * Commit is irreversible-ish (yes, you can revert, but the SHA
    is in the log; force-pushing to fix is destructive).
  * One approval for "this patch is safe to apply", a separate one
    for "this patch is good to keep on the branch".

Refusal codes (in addition to the dispatcher's gates):

::

    payload_field_missing:<f>
        proposal_id / commit_message required.

    proposal_not_found
        No artifact at backend/.file_change_proposals/<id>.json.

    proposal_not_applied
        Artifact's status is not 'applied'. Cannot commit a
        proposal that hasn't been applied yet.

    apply_tests_did_not_pass
        Artifact lacks a clean ``applied`` flag with an
        ``applied_at`` timestamp; refuses to commit a half-applied
        change.

    git_status_has_unrelated_dirty_files
        The working tree contains modifications outside the
        proposal's target file. Refuses to bundle unrelated work
        into a self-healing commit.

    target_file_not_dirty
        The proposal's target file has no staged or unstaged
        modifications. Either the apply already committed (race),
        the apply rolled back, or someone else cleaned up.

    git_command_failed
        ``git add`` / ``git commit`` returned non-zero. Stdout +
        stderr captured into the audit trail; no retry, no push.

    invalid_commit_message
        Commit message contains control chars or is too long.

This handler NEVER pushes. It uses ``subprocess.run`` with
``shell=False`` and args-as-list. The commit message is
sanitized (control chars stripped, length capped) before any
git invocation.
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.services.controlled_execution_dispatch import (
    ControlledExecutionRefused,
    HandlerContext,
    register_tool_handler,
)
from app.services.local_file_safety import REPO_ROOT

logger = get_logger(__name__)

_TOOL_ID = "local.git_commit_approved_patch"
_REQUIRED_PAYLOAD_FIELDS: tuple[str, ...] = (
    "proposal_id",
    "commit_message",
)
_PROPOSAL_DIR = Path(__file__).resolve().parents[3] / ".file_change_proposals"

_MAX_COMMIT_MSG_LEN = 500
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _sanitize_commit_message(raw: str, *, proposal_id: str) -> str:
    """Strip control chars, cap length, and prepend a stable
    self-healing tag so the commit log groups Daena commits.

    Refuses if the result is empty or longer than 500 chars after
    sanitization (the commit message field on the GoaRequest can
    carry up to 1024, but git logs prefer terse one-liners).
    """
    if _CONTROL_CHARS.search(raw):
        raise ControlledExecutionRefused(
            "invalid_commit_message",
            "commit_message contains control characters",
        )
    cleaned = raw.strip()
    if not cleaned:
        raise ControlledExecutionRefused(
            "invalid_commit_message",
            "commit_message is empty after stripping whitespace",
        )
    tagged = f"chore(self-healing): {cleaned}"
    body = f"\n\nproposal: {proposal_id}\n"
    full = tagged[:_MAX_COMMIT_MSG_LEN] + body
    return full


def _git_porcelain_all() -> str:
    """Return the full porcelain status of the working tree."""
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    return (proc.stdout or "").strip()


def _git_run(args: list[str]) -> tuple[int, str, str]:
    """Run a git command (args-as-list, no shell). Returns
    (returncode, stdout, stderr)."""
    proc = subprocess.run(
        ["git", *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, (proc.stdout or ""), (proc.stderr or "")


async def handle_git_commit_approved_patch(
    ctx: HandlerContext,
) -> dict[str, Any]:
    # 1. Required payload fields
    for f in _REQUIRED_PAYLOAD_FIELDS:
        v = ctx.payload.get(f)
        if v is None or (isinstance(v, str) and not v.strip()):
            raise ControlledExecutionRefused(
                f"payload_field_missing:{f}",
                f"{_TOOL_ID} payload missing {f!r}",
            )

    proposal_id = str(ctx.payload["proposal_id"]).strip()
    commit_msg_raw = str(ctx.payload["commit_message"])
    commit_msg = _sanitize_commit_message(
        commit_msg_raw, proposal_id=proposal_id,
    )

    # 2. Load proposal artifact + verify it has been applied
    artifact_path = _PROPOSAL_DIR / f"{proposal_id}.json"
    if not artifact_path.exists():
        raise ControlledExecutionRefused(
            "proposal_not_found",
            f"No artifact at {artifact_path}",
        )
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    if artifact.get("status") != "applied":
        raise ControlledExecutionRefused(
            "proposal_not_applied",
            f"proposal status={artifact.get('status')!r}; expected 'applied'",
        )
    if not artifact.get("applied_at"):
        raise ControlledExecutionRefused(
            "apply_tests_did_not_pass",
            "artifact has no applied_at timestamp; refusing to commit "
            "a proposal whose apply step did not complete cleanly",
        )

    target_repo_rel = artifact.get("target_path_repo_relative") or ""
    if not target_repo_rel:
        raise ControlledExecutionRefused(
            "proposal_not_applied",
            "artifact missing target_path_repo_relative",
        )

    # 3. Inspect git status. The ONLY dirty file allowed is the
    # proposal's target file. Any other dirty entry refuses.
    porcelain = _git_porcelain_all()
    target_dirty = False
    unrelated: list[str] = []
    for line in porcelain.splitlines():
        # porcelain format: "XY <path>"
        path_part = line[3:].strip()
        if path_part == target_repo_rel:
            target_dirty = True
        else:
            unrelated.append(line)
    if unrelated:
        raise ControlledExecutionRefused(
            "git_status_has_unrelated_dirty_files",
            f"{len(unrelated)} unrelated dirty entries: "
            f"{[u[:80] for u in unrelated[:5]]}",
        )
    if not target_dirty:
        raise ControlledExecutionRefused(
            "target_file_not_dirty",
            f"target file {target_repo_rel!r} has no pending "
            f"modifications; nothing to commit",
        )

    # 4. git add the target file ONLY
    rc, out, err = _git_run(["add", "--", target_repo_rel])
    if rc != 0:
        raise ControlledExecutionRefused(
            "git_command_failed",
            f"git add returned {rc}: {(err or out)[:200]}",
        )

    # 5. git commit -m <msg>. NEVER push. NEVER amend.
    rc, out, err = _git_run(["commit", "-m", commit_msg])
    if rc != 0:
        raise ControlledExecutionRefused(
            "git_command_failed",
            f"git commit returned {rc}: {(err or out)[:200]}",
        )

    # 6. Capture the new commit SHA
    rc, sha_out, _ = _git_run(["rev-parse", "HEAD"])
    new_sha = (sha_out or "").strip() if rc == 0 else ""

    # 7. Mark artifact committed
    artifact["status"] = "committed"
    artifact["committed_at"] = datetime.now(UTC).isoformat()
    artifact["commit_sha"] = new_sha
    artifact["committed_by_approval_id"] = ctx.request.approval_id
    artifact_path.write_text(
        json.dumps(artifact, indent=2), encoding="utf-8",
    )

    logger.info(
        "controlled_execution.git_commit.success",
        proposal_id=proposal_id,
        target_repo_relative=target_repo_rel,
        commit_sha=new_sha[:12] if new_sha else "(unknown)",
        approval_id=ctx.request.approval_id,
    )

    return {
        "proposal_id": proposal_id,
        "target_repo_relative": target_repo_rel,
        "commit_sha": new_sha,
        "commit_sha_short": new_sha[:12] if new_sha else None,
        "status": "committed",
        "tool_id": _TOOL_ID,
        "owner_email": ctx.request.owner_email,
        "rollback_or_undo_instruction": (
            ctx.request.rollback_or_undo_instruction
            or f"git revert {new_sha[:12]} -- to undo the commit. "
               f"NEVER force-push to undo on a shared branch."
        ),
    }


# Side-effect register on import.
register_tool_handler(_TOOL_ID, handle_git_commit_approved_patch)
