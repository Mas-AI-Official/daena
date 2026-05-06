"""local.file_change_proposal.apply handler -- Sprint-17 PR-1 (2026-05-06).

The HIGHEST-RISK Phase 3 unlock to date: actual file mutation. The
handler runs only after the six dispatcher gates have passed AND
a SECOND approval has been raised (the create-proposal approval
does NOT authorize apply -- different action_type, different
GoaRequest).

Design (Mythos):

  * Backup-based rollback. The handler reads current file content,
    sha256s it, refuses if != approved current_file_hash, then
    writes a byte-for-byte backup to a fresh UUID directory under
    backend/.file_change_backups/<uuid>/. On rollback, the backup
    bytes are copied back -- NEVER the operator-supplied
    rollback_patch text. The patch text is documentation only.
  * Atomic apply via os.replace. New content is written to a
    temp file in the same directory, then renamed atomically. If
    the process crashes between write and replace, the temp is
    orphaned but the original is untouched.
  * pytest-only test commands. tests_to_run_after_apply must be
    a list of repo-relative pytest paths (regex-locked in
    local_file_safety.validate_pytest_path). Anything that looks
    like a shell command refuses BEFORE apply with
    invalid_test_path.
  * Test failure triggers automatic rollback (copy backup back).
  * NO commit. Commit is a SEPARATE controlled tool
    (local.git_commit_approved_patch) with its own approval.

Refusal codes (in addition to dispatcher gates):

::

    payload_field_missing:<field>
        proposal_id / current_file_hash / approved_diff_hash /
        repo_root_relative_path / backup_file_path / rollback_patch
        / tests_to_run_after_apply / commit_approval_id /
        change_type required.

    proposal_not_found
        No artifact at backend/.file_change_proposals/<proposal_id>.json.

    proposal_already_applied
        Artifact's status is 'applied' or 'rejected'.

    target_path_outside_repo / target_path_is_secret_file
        Reuses local_file_safety regex (Sprint-14 PR-4 / Sprint-17
        shared module).

    change_type_delete_not_allowed_in_apply_v1
        Apply is restricted to change_type='modify'. Delete and
        create variants require future contracts.

    current_file_hash_mismatch
        sha256 of on-disk content != approved current_file_hash.
        Means the file changed between proposal and apply.

    approved_diff_hash_mismatch
        sha256 of artifact's diff_text != approved
        approved_diff_hash. Means the artifact was tampered with.

    target_file_dirty_in_git
        git status reports the target file modified. Refuses to
        apply atop unrelated edits. Other dirty files are tolerated.

    invalid_test_path
        A test spec failed validate_pytest_path (shell-shaped or
        non-repo-relative).

    apply_failed
        Disk write or rename raised. Backup is intact; no rollback
        needed because the file was never replaced.

    tests_failed_rolled_back
        At least one declared test failed. The handler reverted
        the file from backup; the operator sees the test output
        and can iterate on the proposal.

    rollback_failed
        Tests failed AND the backup-restore raised. CRITICAL:
        operator must inspect the file at target path manually.
        Daena emits a high-priority audit row.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.services.controlled_execution_dispatch import (
    ControlledExecutionRefused,
    HandlerContext,
    register_tool_handler,
)
from app.services.local_file_safety import (
    REPO_ROOT,
    is_secret_file,
    resolve_under_repo,
    validate_pytest_path,
)

logger = get_logger(__name__)

_TOOL_ID = "local.file_change_proposal.apply"

_REQUIRED_PAYLOAD_FIELDS: tuple[str, ...] = (
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

# Proposal directory (same as proposal-create writes to).
_PROPOSAL_DIR = Path(__file__).resolve().parents[3] / ".file_change_proposals"
# Backup directory (gitignored alongside proposals).
_BACKUP_DIR = Path(__file__).resolve().parents[3] / ".file_change_backups"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _git_status_porcelain(target_repo_relative: str) -> str:
    """Return git status --porcelain output for the target file
    only. Empty when the file is clean. Args-as-list, no shell."""
    proc = subprocess.run(
        ["git", "status", "--porcelain", "--", target_repo_relative],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    return (proc.stdout or "").strip()


async def _run_pytest(test_spec: str) -> tuple[int, str]:
    """Run python -m pytest <validated spec> in a worker thread.
    Returns (returncode, combined_output_tail)."""

    def _sync():
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", test_spec, "-x", "--tb=short"],
            cwd=str(REPO_ROOT / "backend"),
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, out[-1500:]

    return await asyncio.to_thread(_sync)


def _atomic_write(target: Path, new_bytes: bytes) -> None:
    """Write new_bytes to a temp file in the same directory, then
    os.replace into target. Atomic on Windows + POSIX."""
    tmp = target.with_suffix(target.suffix + f".daena.{uuid.uuid4().hex}.tmp")
    tmp.write_bytes(new_bytes)
    os.replace(str(tmp), str(target))


async def handle_file_change_proposal_apply(
    ctx: HandlerContext,
) -> dict[str, Any]:
    # 1. Required payload fields.
    for f in _REQUIRED_PAYLOAD_FIELDS:
        v = ctx.payload.get(f)
        if v is None or (isinstance(v, str) and not v.strip()):
            raise ControlledExecutionRefused(
                f"payload_field_missing:{f}",
                f"{_TOOL_ID} payload missing {f!r}.",
            )

    proposal_id = str(ctx.payload["proposal_id"]).strip()
    current_file_hash_expected = str(ctx.payload["current_file_hash"]).strip()
    approved_diff_hash_expected = str(ctx.payload["approved_diff_hash"]).strip()
    repo_rel = str(ctx.payload["repo_root_relative_path"]).strip()
    rollback_patch = str(ctx.payload["rollback_patch"])  # documentation only
    tests = ctx.payload["tests_to_run_after_apply"]
    change_type = str(ctx.payload["change_type"]).strip().lower()

    if change_type != "modify":
        raise ControlledExecutionRefused(
            "change_type_delete_not_allowed_in_apply_v1",
            f"apply v1 supports change_type='modify' only; got "
            f"{change_type!r}",
        )

    if not isinstance(tests, list) or not tests:
        raise ControlledExecutionRefused(
            "payload_field_missing:tests_to_run_after_apply",
            "tests_to_run_after_apply must be a non-empty list",
        )
    validated_tests = [validate_pytest_path(t) for t in tests]

    # 2. Path safety reuse from Sprint-14 PR-4.
    if is_secret_file(repo_rel):
        raise ControlledExecutionRefused(
            "target_path_is_secret_file",
            f"{repo_rel!r} matches a known secret-file pattern",
        )
    target_abs = resolve_under_repo(repo_rel)

    # 3. Load proposal artifact.
    artifact_path = _PROPOSAL_DIR / f"{proposal_id}.json"
    if not artifact_path.exists():
        raise ControlledExecutionRefused(
            "proposal_not_found",
            f"No artifact at {artifact_path}",
        )
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    if artifact.get("status") in ("applied", "rejected"):
        raise ControlledExecutionRefused(
            "proposal_already_applied",
            f"proposal status={artifact.get('status')!r}",
        )

    # 4. Approved-diff-hash check (artifact's diff_text vs the
    # hash the approver was looking at).
    actual_diff_hash = _sha256_text(artifact.get("diff_text", ""))
    if actual_diff_hash != approved_diff_hash_expected:
        raise ControlledExecutionRefused(
            "approved_diff_hash_mismatch",
            f"artifact diff hash {actual_diff_hash[:16]}.. != "
            f"approved {approved_diff_hash_expected[:16]}..",
        )

    # 5. Current-file-hash check (on-disk content vs the hash the
    # approver was looking at).
    if not target_abs.exists():
        raise ControlledExecutionRefused(
            "current_file_hash_mismatch",
            f"target file does not exist: {target_abs}",
        )
    current_bytes = target_abs.read_bytes()
    actual_current_hash = _sha256_bytes(current_bytes)
    if actual_current_hash != current_file_hash_expected:
        raise ControlledExecutionRefused(
            "current_file_hash_mismatch",
            f"on-disk hash {actual_current_hash[:16]}.. != "
            f"approved {current_file_hash_expected[:16]}..",
        )

    # 6. Git-dirty check for the TARGET file only.
    dirty = _git_status_porcelain(repo_rel)
    if dirty:
        raise ControlledExecutionRefused(
            "target_file_dirty_in_git",
            f"target file has uncommitted changes: "
            f"{dirty.splitlines()[0][:120]}",
        )

    # 7. Backup BEFORE apply.
    backup_uuid = uuid.uuid4().hex
    backup_dir = _BACKUP_DIR / proposal_id / backup_uuid
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_file = backup_dir / target_abs.name
    backup_file.write_bytes(current_bytes)

    # 8. Compute new content from artifact's diff_text. v1 stores
    # the FULL new file content in diff_text rather than a patch
    # diff -- this is the simplest correct contract because we
    # already pinned approved_diff_hash to that exact text.
    # A future PR can extend to unified-diff when the patch tool
    # ships.
    new_content_text = artifact.get("diff_text", "")
    new_bytes = new_content_text.encode("utf-8")

    # 9. Atomic apply.
    try:
        _atomic_write(target_abs, new_bytes)
    except OSError as exc:
        raise ControlledExecutionRefused(
            "apply_failed",
            f"atomic write raised: {type(exc).__name__}",
        ) from exc

    # 10. Run declared tests. On any failure, rollback from backup.
    test_results: list[dict[str, Any]] = []
    rolled_back = False
    rollback_error: str | None = None
    any_failed = False

    for spec in validated_tests:
        rc, tail = await _run_pytest(spec)
        passed = rc == 0
        test_results.append({
            "spec": spec,
            "returncode": rc,
            "passed": passed,
            "tail": tail,
        })
        if not passed:
            any_failed = True

    if any_failed:
        try:
            # Restore from backup. Atomic.
            _atomic_write(target_abs, backup_file.read_bytes())
            rolled_back = True
        except OSError as exc:
            rollback_error = f"{type(exc).__name__}: {exc}"
            logger.error(
                "controlled_execution.file_apply.rollback_failed",
                proposal_id=proposal_id,
                target_repo_relative=repo_rel,
                error=rollback_error,
            )
            raise ControlledExecutionRefused(
                "rollback_failed",
                f"tests failed AND rollback raised: {rollback_error}; "
                f"operator must inspect {repo_rel} manually.",
            ) from exc

        raise ControlledExecutionRefused(
            "tests_failed_rolled_back",
            f"declared tests failed; file rolled back from backup. "
            f"Test results: "
            f"{[(r['spec'], r['returncode']) for r in test_results]}",
        )

    # 11. Mark artifact applied.
    artifact["status"] = "applied"
    artifact["applied_at"] = datetime.now(UTC).isoformat()
    try:
        backup_repo_rel = str(
            backup_file.relative_to(REPO_ROOT)
        ).replace("\\", "/")
    except ValueError:
        # Backup directory was repointed outside the repo (e.g. a
        # tmpdir during tests). Surface the absolute path verbatim.
        backup_repo_rel = str(backup_file).replace("\\", "/")
    artifact["backup_file_path"] = backup_repo_rel
    artifact["applied_by_approval_id"] = ctx.request.approval_id
    artifact_path.write_text(
        json.dumps(artifact, indent=2), encoding="utf-8",
    )
    logger.info(
        "controlled_execution.file_apply.success",
        proposal_id=proposal_id,
        target_repo_relative=repo_rel,
        backup=str(backup_file),
        approval_id=ctx.request.approval_id,
    )

    return {
        "proposal_id": proposal_id,
        "target_repo_relative": repo_rel,
        "backup_file_path": backup_repo_rel,
        "tests_run": len(validated_tests),
        "tests_passed": True,
        "rolled_back": rolled_back,
        "status": "applied",
        "tool_id": _TOOL_ID,
        "owner_email": ctx.request.owner_email,
        "rollback_or_undo_instruction": (
            ctx.request.rollback_or_undo_instruction
            or f"Restore from backup {backup_file.name} via the "
               f"governance audit log; commit is gated by a SEPARATE "
               f"local.git_commit_approved_patch approval."
        ),
        # Note: rollback_patch is documentation, not the rollback
        # mechanism. Surface it for the operator's eyes only.
        "rollback_patch_summary_lines": len(rollback_patch.splitlines()),
    }


# Side-effect register on import.
register_tool_handler(_TOOL_ID, handle_file_change_proposal_apply)
