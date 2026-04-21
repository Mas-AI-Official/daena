"""Git-backed phase checkpoints (Shannon Pattern 2 port).

Each scan phase can commit its workspace state to a private git
repo inside the scan's deliverables directory. The commit hash is
returned so the EvidenceChain can store it as a phase seal and
subsequent re-runs can rollback to that state for deterministic
crash recovery.

Shannon's implementation is 32 lines of semaphore + three shell-
wrapped git functions (no worktrees, no branches). We mirror that
discipline in Python and add an integration point for Klyntar's
hash-chained EvidenceChain so the git log and the evidence chain
are cryptographically linked: tamper with either and the pairing
breaks.

Core contract:

    * is_git_repo(path)        True when path is a git worktree
    * init_git_repo(path)      Idempotent git init + initial commit
    * create_checkpoint(path, description, attempt=1,
                        evidence_chain_id="") -> commit_hash
    * rollback_to(path, commit_hash)   git reset --hard + clean
    * list_checkpoints(path, limit=50)  -> [CheckpointRef, ...]

Concurrency: a single-process asyncio.Semaphore(1) serializes all
git mutations. Index.lock retries with exponential backoff (2^n s,
max 5 attempts) mirror Shannon's ``executeGitCommandWithRetry``.

Safety: if the path is not a git repo AND the caller has not asked
for init, all operations return early with a log line. This mirrors
Shannon's ``isGitRepository`` false-return-continue pattern. That
default matters for the FREE tier where users don't want git
overhead on every scan.

BACKGROUND PATH ONLY -- never import in hot path
"""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


# Single-process mutex over git mutations. Shannon uses a GitSemaphore
# class with a queue; asyncio.Semaphore(1) is the cleaner Python shape.
_GIT_SEMAPHORE: asyncio.Semaphore = asyncio.Semaphore(1)


# stderr substrings that indicate a git-lock contention; retry on any.
_LOCK_PATTERNS: tuple[str, ...] = (
    "index.lock",
    "unable to lock",
    "Another git process",
    "fatal: Unable to create",
    "fatal: index file",
)


# Max retry attempts + initial backoff in seconds. Shannon uses 5 + 1.0.
_MAX_ATTEMPTS: int = 5
_INITIAL_BACKOFF_SECONDS: float = 1.0


@dataclass(frozen=True, slots=True)
class CheckpointRef:
    """A single git commit inside the checkpoint log."""

    commit_hash: str
    short_hash: str             # first 12 chars
    subject: str
    timestamp: str              # ISO 8601
    phase: str = ""
    evidence_chain_id: str = ""


@dataclass(slots=True)
class CheckpointResult:
    """Outcome of create_checkpoint."""

    ok: bool
    commit_hash: str = ""
    phase: str = ""
    attempt: int = 1
    reason: str = ""


# ---------------------------------------------------------------------------
# Low-level git runner with retry
# ---------------------------------------------------------------------------


def _is_lock_error(stderr: str) -> bool:
    return any(pat in stderr for pat in _LOCK_PATTERNS)


async def _run_git(
    args: list[str],
    cwd: Path,
    *,
    timeout_seconds: float = 10.0,
) -> tuple[int, str, str]:
    """Execute a git command async. Returns (rc, stdout, stderr).

    Never raises on git exit code; callers inspect the tuple.
    Raises only on OSError (git binary missing) so cold-start
    misconfiguration is visible.
    """
    proc = await asyncio.create_subprocess_exec(
        "git", *args,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(
            proc.communicate(), timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return (124, "", "git command timed out")
    return (
        proc.returncode or 0,
        (stdout_b or b"").decode("utf-8", errors="replace"),
        (stderr_b or b"").decode("utf-8", errors="replace"),
    )


async def _run_git_with_retry(
    args: list[str],
    cwd: Path,
    *,
    max_attempts: int = _MAX_ATTEMPTS,
) -> tuple[int, str, str]:
    """Retry git commands on lock-style contention with exponential backoff.

    Non-lock errors return immediately. Lock errors retry up to
    ``max_attempts`` times with ``2 ** (attempt - 1) * _INITIAL_BACKOFF``
    between attempts.
    """
    last: tuple[int, str, str] = (1, "", "")
    for attempt in range(1, max_attempts + 1):
        rc, stdout, stderr = await _run_git(args, cwd)
        if rc == 0:
            return (rc, stdout, stderr)
        last = (rc, stdout, stderr)
        if not _is_lock_error(stderr):
            return last
        if attempt < max_attempts:
            delay = _INITIAL_BACKOFF_SECONDS * (2 ** (attempt - 1))
            logger.info(
                "evidence_checkpoint.git_lock_retry",
                attempt=attempt,
                delay_seconds=delay,
                stderr_preview=stderr[:200],
            )
            await asyncio.sleep(delay)
    return last


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def is_git_repo(path: str | Path) -> bool:
    """True when ``path`` exists and contains a .git subdirectory."""
    p = Path(path)
    if not p.is_dir():
        return False
    return (p / ".git").is_dir()


async def init_git_repo(
    path: str | Path,
    *,
    author_name: str = "Daena Klyntar",
    author_email: str = "klyntar@daena.local",
    initial_commit_message: str = "klyntar: deliverables repo initialized",
) -> bool:
    """Idempotent git init + initial commit.

    Returns True on success (repo now exists + has at least one
    commit). False means git is unusable (binary missing, path
    invalid, etc.) and subsequent checkpoint calls will also fail.
    Safe to call repeatedly; does nothing when already initialized.
    """
    p = Path(path)
    try:
        p.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning(
            "evidence_checkpoint.init_mkdir_failed",
            path=str(p), error=str(exc),
        )
        return False

    if is_git_repo(p):
        return True

    async with _GIT_SEMAPHORE:
        rc, _, stderr = await _run_git(["init", "--quiet"], p)
        if rc != 0:
            logger.warning(
                "evidence_checkpoint.init_failed",
                path=str(p), stderr_preview=stderr[:200],
            )
            return False

        # Configure local author identity. Klyntar audit should show
        # the tool, not the operator's personal git config.
        await _run_git(["config", "user.name", author_name], p)
        await _run_git(["config", "user.email", author_email], p)

        # Create a .klyntar-repo marker + make initial commit.
        marker = p / ".klyntar-repo"
        try:
            marker.write_text(
                f"# klyntar deliverables repo\ninitialized: {datetime.utcnow().isoformat()}Z\n",
                encoding="utf-8",
            )
        except OSError:
            return False

        await _run_git_with_retry(["add", ".klyntar-repo"], p)
        rc, _, stderr = await _run_git_with_retry(
            ["commit", "--allow-empty", "-m", initial_commit_message], p,
        )
        if rc != 0:
            logger.warning(
                "evidence_checkpoint.init_commit_failed",
                path=str(p), stderr_preview=stderr[:200],
            )
            return False

    return True


async def _current_head(path: Path) -> str:
    """Return current HEAD commit hash (full), or empty string."""
    rc, stdout, _ = await _run_git(["rev-parse", "HEAD"], path)
    if rc != 0:
        return ""
    return stdout.strip()


async def _rollback_workspace(path: Path) -> tuple[bool, str]:
    """Equivalent to Shannon's rollbackGitWorkspace: reset hard + clean."""
    rc, _, stderr = await _run_git_with_retry(
        ["reset", "--hard", "HEAD"], path,
    )
    if rc != 0:
        return (False, f"git reset failed: {stderr[:200]}")
    rc, _, stderr = await _run_git_with_retry(["clean", "-fd"], path)
    if rc != 0:
        return (False, f"git clean failed: {stderr[:200]}")
    return (True, "")


async def create_checkpoint(
    deliverables_dir: str | Path,
    description: str,
    *,
    phase: str = "",
    attempt: int = 1,
    evidence_chain_id: str = "",
) -> CheckpointResult:
    """Commit the workspace state to git and return the commit hash.

    Shannon's ``createGitCheckpoint``: on attempt > 1, rollback the
    workspace first (``git reset --hard`` + ``git clean -fd``), then
    ``git add -A`` + ``git commit --allow-empty``. The commit
    message embeds the phase + attempt + evidence_chain_id so the
    git log is a readable audit trail mutually linkable with the
    Klyntar EvidenceChain.

    Args:
        deliverables_dir: path to the scan's deliverables repo.
            Must already be initialized via init_git_repo(); non-repo
            paths return ok=False with a reason.
        description: free-text description of what this phase did.
        phase: optional phase name ("profiling" / "scanning" / ...).
        attempt: 1-based attempt number (for retries).
        evidence_chain_id: optional EvidenceChain id to embed in the
            commit message so chain and git log are mutually
            auditable.
    """
    p = Path(deliverables_dir)
    if not is_git_repo(p):
        # Shannon fail-safe: log and continue. This is the correct
        # behavior for FREE-tier users who do not want git overhead.
        logger.info(
            "evidence_checkpoint.skipped_not_git_repo",
            path=str(p), phase=phase, description=description[:80],
        )
        return CheckpointResult(
            ok=False, phase=phase, attempt=attempt,
            reason="path is not a git repo; init_git_repo first",
        )

    async with _GIT_SEMAPHORE:
        if attempt > 1:
            ok, reason = await _rollback_workspace(p)
            if not ok:
                return CheckpointResult(
                    ok=False, phase=phase, attempt=attempt, reason=reason,
                )

        rc, _, stderr = await _run_git_with_retry(["add", "-A"], p)
        if rc != 0:
            return CheckpointResult(
                ok=False, phase=phase, attempt=attempt,
                reason=f"git add -A failed: {stderr[:200]}",
            )

        # Commit message: "CHECKPOINT: <phase> :: <description> (attempt <n>) [evidence:<id>]"
        subject_parts = ["CHECKPOINT"]
        if phase:
            subject_parts.append(phase)
        subject = " :: ".join(subject_parts) + f" :: {description}"
        if attempt > 1:
            subject += f" (attempt {attempt})"
        if evidence_chain_id:
            subject += f" [evidence:{evidence_chain_id}]"

        rc, _, stderr = await _run_git_with_retry(
            ["commit", "--allow-empty", "-m", subject], p,
        )
        if rc != 0:
            return CheckpointResult(
                ok=False, phase=phase, attempt=attempt,
                reason=f"git commit failed: {stderr[:200]}",
            )

        commit_hash = await _current_head(p)
        logger.info(
            "evidence_checkpoint.created",
            path=str(p), phase=phase, attempt=attempt,
            commit=commit_hash[:12], evidence_chain_id=evidence_chain_id,
        )
        return CheckpointResult(
            ok=True, commit_hash=commit_hash, phase=phase, attempt=attempt,
        )


async def rollback_to(
    deliverables_dir: str | Path, commit_hash: str,
) -> tuple[bool, str]:
    """git reset --hard <hash> + git clean -fd. Returns (ok, reason)."""
    p = Path(deliverables_dir)
    if not is_git_repo(p):
        return (False, "path is not a git repo")
    if not _is_hex_hash(commit_hash):
        return (False, f"invalid commit hash: {commit_hash!r}")

    async with _GIT_SEMAPHORE:
        rc, _, stderr = await _run_git_with_retry(
            ["reset", "--hard", commit_hash], p,
        )
        if rc != 0:
            return (False, f"git reset --hard failed: {stderr[:200]}")
        rc, _, stderr = await _run_git_with_retry(["clean", "-fd"], p)
        if rc != 0:
            return (False, f"git clean -fd failed: {stderr[:200]}")
    logger.info(
        "evidence_checkpoint.rolled_back",
        path=str(p), commit=commit_hash[:12],
    )
    return (True, "")


async def list_checkpoints(
    deliverables_dir: str | Path, *, limit: int = 50,
) -> list[CheckpointRef]:
    """Return the most recent ``limit`` checkpoints, newest first.

    Parses ``git log --oneline --pretty=...`` and extracts the
    optional [evidence:<id>] tag from the subject.
    """
    p = Path(deliverables_dir)
    if not is_git_repo(p):
        return []

    # Use a null-byte record separator so subjects with embedded
    # colons do not confuse the parser.
    fmt = "%H%x1f%s%x1f%aI"
    rc, stdout, _ = await _run_git(
        ["log", f"--max-count={int(limit)}", f"--pretty=format:{fmt}"], p,
    )
    if rc != 0 or not stdout.strip():
        return []

    out: list[CheckpointRef] = []
    for line in stdout.splitlines():
        parts = line.split("\x1f")
        if len(parts) != 3:
            continue
        commit_hash, subject, timestamp = parts
        phase = _extract_phase(subject)
        evidence_chain_id = _extract_evidence_id(subject)
        out.append(CheckpointRef(
            commit_hash=commit_hash,
            short_hash=commit_hash[:12],
            subject=subject,
            timestamp=timestamp,
            phase=phase,
            evidence_chain_id=evidence_chain_id,
        ))
    return out


# ---------------------------------------------------------------------------
# Parse helpers
# ---------------------------------------------------------------------------


_PHASE_RE = re.compile(r"CHECKPOINT\s*::\s*([a-zA-Z_][\w]*)\s*::")
_EVIDENCE_RE = re.compile(r"\[evidence:([^\]]+)\]")


def _extract_phase(subject: str) -> str:
    m = _PHASE_RE.search(subject)
    return m.group(1) if m else ""


def _extract_evidence_id(subject: str) -> str:
    m = _EVIDENCE_RE.search(subject)
    return m.group(1) if m else ""


def _is_hex_hash(s: str) -> bool:
    """Accept git hash shapes (40 hex chars for SHA-1, 64 for SHA-256)."""
    if not s:
        return False
    if len(s) not in (7, 8, 12, 40, 64):
        # Allow abbreviated commit hashes (7/8/12) + full SHA-1 (40) + SHA-256 (64).
        return False
    return all(c in "0123456789abcdef" for c in s.lower())


# ---------------------------------------------------------------------------
# Utility: wrap a phase with auto-checkpoint on success
# ---------------------------------------------------------------------------


async def checkpoint_if_enabled(
    deliverables_dir: str | Path,
    description: str,
    *,
    phase: str,
    evidence_chain_id: str = "",
    enabled: bool = False,
) -> CheckpointResult:
    """Call this at the end of each scan phase.

    ``enabled`` comes from the ``klyntar_checkpoints_enabled`` config
    flag (default False). When False, the function is a no-op that
    returns ``ok=False, reason="checkpoints disabled"``. When True,
    it initializes the repo if needed (idempotent) and creates a
    checkpoint. This is the single entrypoint scan_workflow.py uses
    so the feature flag gates cleanly.
    """
    if not enabled:
        return CheckpointResult(
            ok=False, phase=phase, reason="checkpoints disabled",
        )

    p = Path(deliverables_dir)
    if not is_git_repo(p):
        inited = await init_git_repo(p)
        if not inited:
            return CheckpointResult(
                ok=False, phase=phase,
                reason="failed to init git repo",
            )

    return await create_checkpoint(
        p, description,
        phase=phase, evidence_chain_id=evidence_chain_id,
    )
