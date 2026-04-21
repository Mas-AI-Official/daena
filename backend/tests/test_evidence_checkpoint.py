"""Tests for evidence_checkpoint.py (Shannon Pattern 2 port).

Covers:
  * _is_hex_hash validation
  * _is_lock_error pattern matching
  * _extract_phase + _extract_evidence_id parsers
  * is_git_repo detection (non-dir, non-repo dir, real repo)
  * init_git_repo idempotence + real-git initial commit
  * create_checkpoint happy path + returns real hash
  * create_checkpoint on non-repo path returns ok=False with reason
  * rollback_to happy path + bad hash rejected
  * list_checkpoints parses subjects with phase + evidence tags
  * checkpoint_if_enabled: disabled flag short-circuits
  * checkpoint_if_enabled: enabled flag auto-inits repo

The live-git tests use tmp_path and real git. If the binary isn't
available on CI, those tests skip via pytest.importorskip on
subprocess spawnability.
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import pytest

from app.services.security.evidence_checkpoint import (
    CheckpointRef,
    CheckpointResult,
    _extract_evidence_id,
    _extract_phase,
    _is_hex_hash,
    _is_lock_error,
    checkpoint_if_enabled,
    create_checkpoint,
    init_git_repo,
    is_git_repo,
    list_checkpoints,
    rollback_to,
)


# ----------------------------------------------------------------------
# Skip live-git tests when git binary is unavailable
# ----------------------------------------------------------------------


def _git_available() -> bool:
    try:
        subprocess.run(
            ["git", "--version"], capture_output=True, timeout=5, check=True,
        )
        return True
    except Exception:
        return False


requires_git = pytest.mark.skipif(
    not _git_available(), reason="git binary not available",
)


# ----------------------------------------------------------------------
# Pure-function unit tests
# ----------------------------------------------------------------------


def test_is_hex_hash_accepts_real_shas():
    assert _is_hex_hash("a" * 40) is True       # SHA-1
    assert _is_hex_hash("b" * 64) is True       # SHA-256
    assert _is_hex_hash("abcdef1") is True      # 7-char abbrev
    assert _is_hex_hash("abcdef12345") is False  # 11 (not a valid length)
    assert _is_hex_hash("abcdef123456") is True  # 12-char abbrev


def test_is_hex_hash_rejects_bad_inputs():
    assert _is_hex_hash("") is False
    assert _is_hex_hash("xyz123") is False          # non-hex + wrong length
    assert _is_hex_hash("G" * 40) is False          # non-hex char, right length
    assert _is_hex_hash("a" * 100) is False         # too long


def test_is_lock_error_detects_shannon_patterns():
    assert _is_lock_error("fatal: Unable to create '.git/index.lock': File exists") is True
    assert _is_lock_error("Another git process is running") is True
    assert _is_lock_error("fatal: index file smudge worker error") is True
    assert _is_lock_error("ordinary error not related to locks") is False
    assert _is_lock_error("") is False


def test_extract_phase_from_subject():
    assert _extract_phase("CHECKPOINT :: profiling :: initial scan") == "profiling"
    assert _extract_phase("CHECKPOINT :: exploitation_queue :: ok") == "exploitation_queue"
    assert _extract_phase("CHECKPOINT :: no phase here") == ""
    assert _extract_phase("random commit") == ""


def test_extract_evidence_id_from_subject():
    assert _extract_evidence_id("CHECKPOINT :: x [evidence:scan-abc]") == "scan-abc"
    assert _extract_evidence_id("CHECKPOINT :: x [evidence:ec-12345-xyz]") == "ec-12345-xyz"
    assert _extract_evidence_id("no tag here") == ""
    assert _extract_evidence_id("[evidence:]") == ""   # empty group rejected


# ----------------------------------------------------------------------
# is_git_repo (filesystem only, no git calls)
# ----------------------------------------------------------------------


def test_is_git_repo_nonexistent(tmp_path):
    assert is_git_repo(tmp_path / "no-such-dir") is False


def test_is_git_repo_plain_dir(tmp_path):
    d = tmp_path / "plain"
    d.mkdir()
    assert is_git_repo(d) is False


def test_is_git_repo_recognizes_dot_git(tmp_path):
    d = tmp_path / "repo"
    d.mkdir()
    (d / ".git").mkdir()
    assert is_git_repo(d) is True


# ----------------------------------------------------------------------
# checkpoint_if_enabled: disabled short-circuit
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checkpoint_if_disabled_is_noop(tmp_path):
    r = await checkpoint_if_enabled(
        tmp_path, "desc", phase="profiling", enabled=False,
    )
    assert r.ok is False
    assert "disabled" in r.reason


@pytest.mark.asyncio
async def test_checkpoint_on_non_repo_returns_reason(tmp_path):
    r = await create_checkpoint(tmp_path / "no-repo", "desc")
    assert r.ok is False
    assert "not a git repo" in r.reason.lower()


# ----------------------------------------------------------------------
# Live-git tests (require git binary)
# ----------------------------------------------------------------------


@requires_git
@pytest.mark.asyncio
async def test_init_git_repo_creates_valid_repo(tmp_path):
    d = tmp_path / "deliverables"
    ok = await init_git_repo(d)
    assert ok is True
    assert is_git_repo(d) is True
    assert (d / ".klyntar-repo").is_file()


@requires_git
@pytest.mark.asyncio
async def test_init_git_repo_is_idempotent(tmp_path):
    d = tmp_path / "deliverables"
    ok1 = await init_git_repo(d)
    ok2 = await init_git_repo(d)
    assert ok1 is True and ok2 is True


@requires_git
@pytest.mark.asyncio
async def test_create_checkpoint_returns_real_hash(tmp_path):
    d = tmp_path / "deliverables"
    await init_git_repo(d)
    # Add a file so there's something to commit.
    (d / "queue.json").write_text('{"vulnerabilities": []}', encoding="utf-8")
    r = await create_checkpoint(
        d, "injection queue written",
        phase="exploitation_queue",
        evidence_chain_id="scan-42",
    )
    assert r.ok is True
    assert _is_hex_hash(r.commit_hash) is True
    assert r.phase == "exploitation_queue"


@requires_git
@pytest.mark.asyncio
async def test_checkpoint_if_enabled_auto_inits_repo(tmp_path):
    d = tmp_path / "auto-init"
    assert is_git_repo(d) is False
    r = await checkpoint_if_enabled(
        d, "desc", phase="profiling", enabled=True,
    )
    assert r.ok is True
    assert is_git_repo(d) is True
    assert _is_hex_hash(r.commit_hash) is True


@requires_git
@pytest.mark.asyncio
async def test_list_checkpoints_parses_phase_and_evidence(tmp_path):
    d = tmp_path / "d"
    await init_git_repo(d)
    (d / "a.txt").write_text("one", encoding="utf-8")
    await create_checkpoint(
        d, "first phase", phase="profiling", evidence_chain_id="ec-1",
    )
    (d / "b.txt").write_text("two", encoding="utf-8")
    await create_checkpoint(
        d, "second phase", phase="scanning", evidence_chain_id="ec-2",
    )

    entries = await list_checkpoints(d, limit=10)
    # Newest first; expect at least 2 CHECKPOINT commits + the init commit
    assert len(entries) >= 2
    # Newest should be 'scanning'
    newest = entries[0]
    assert newest.phase == "scanning"
    assert newest.evidence_chain_id == "ec-2"
    assert _is_hex_hash(newest.commit_hash) is True
    assert newest.short_hash == newest.commit_hash[:12]


@requires_git
@pytest.mark.asyncio
async def test_rollback_to_restores_workspace(tmp_path):
    d = tmp_path / "rb"
    await init_git_repo(d)
    (d / "state.txt").write_text("phase1", encoding="utf-8")
    r1 = await create_checkpoint(d, "phase1", phase="profiling")
    assert r1.ok is True
    # Mutate + checkpoint phase2
    (d / "state.txt").write_text("phase2", encoding="utf-8")
    r2 = await create_checkpoint(d, "phase2", phase="scanning")
    assert r2.ok is True
    assert (d / "state.txt").read_text() == "phase2"

    ok, reason = await rollback_to(d, r1.commit_hash)
    assert ok is True, reason
    assert (d / "state.txt").read_text() == "phase1"


@requires_git
@pytest.mark.asyncio
async def test_rollback_rejects_bad_hash(tmp_path):
    d = tmp_path / "bad-rb"
    await init_git_repo(d)
    ok, reason = await rollback_to(d, "not-a-real-hash")
    assert ok is False
    assert "invalid commit hash" in reason.lower()


@requires_git
@pytest.mark.asyncio
async def test_rollback_on_non_repo_rejected(tmp_path):
    ok, reason = await rollback_to(tmp_path / "nope", "a" * 40)
    assert ok is False
    assert "not a git repo" in reason.lower()


@requires_git
@pytest.mark.asyncio
async def test_concurrent_checkpoints_serialize(tmp_path):
    """Two concurrent create_checkpoint calls must not race index.lock."""
    d = tmp_path / "concur"
    await init_git_repo(d)
    (d / "x.txt").write_text("A", encoding="utf-8")

    async def cp(phase: str):
        return await create_checkpoint(d, f"phase {phase}", phase=phase)

    results = await asyncio.gather(cp("p1"), cp("p2"), cp("p3"))
    for r in results:
        assert r.ok is True, r.reason
    # Three distinct commit hashes produced (semaphore ensured order).
    hashes = {r.commit_hash for r in results}
    assert len(hashes) == 3
