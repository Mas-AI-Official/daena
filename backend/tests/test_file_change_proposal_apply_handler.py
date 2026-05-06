"""Sprint-17 PR-1 -- file_change_proposal.apply handler contract.

Pins:
  1. Handler registered after package import.
  2. All 9 required payload fields refuse when missing.
  3. change_type='delete' refused (apply v1 = modify only).
  4. Proposal not found / already applied refused.
  5. current_file_hash mismatch refused (file drifted on disk).
  6. approved_diff_hash mismatch refused (artifact tampered).
  7. Secret-file path refused (reuses Sprint-14 PR-4 regex).
  8. Outside-repo path refused.
  9. Invalid pytest spec refused with invalid_test_path.
 10. tests-pass success path: file mutated, artifact marked applied.
 11. tests-fail path: file rolled back from BACKUP (not from
     rollback_patch text), artifact NOT marked applied, refusal
     code tests_failed_rolled_back.
 12. backup file is created and contains the ORIGINAL bytes.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest


pytestmark = pytest.mark.asyncio


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _make_request(**overrides):
    from app.services.controlled_execution_design import ControlledExecutionRequest
    base = dict(
        approval_id="00000000-0000-0000-0000-000000000000",
        consent_grant_id="grant-x",
        payload_hash="0" * 64,
        tool_id="local.file_change_proposal.apply",
        owner_email="founder@example.com",
        asset_shield_pass=True,
        policy_allowlist_pass=True,
        audit_preflight_row_id="audit-pre",
        audit_result_row_id=None,
        rollback_or_undo_instruction=None,
    )
    base.update(overrides)
    return ControlledExecutionRequest(**base)


def _make_ctx(*, request, payload):
    from app.services.controlled_execution_dispatch import HandlerContext
    return HandlerContext(
        request=request,
        approval=MagicMock(),
        payload=payload,
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        db=MagicMock(),
    )


@pytest.fixture
def repo_temp_file(tmp_path, monkeypatch):
    """Build a temp file inside the repo + matching artifact + payload.

    Yields a dict carrying everything the handler needs:
      - target_abs        absolute path of the temp file
      - target_repo_rel   repo-relative path string
      - original_bytes
      - new_text          the diff_text (which v1 stores as the
                          full new file content)
      - artifact_path
      - payload           full payload dict for the handler
    """
    from app.services.controlled_execution_handlers import (
        file_change_proposal_apply as mod,
    )
    from app.services.local_file_safety import REPO_ROOT

    # Create a target file under backend/.tmp_apply_test/<uuid>/file.py
    target_dir = REPO_ROOT / "backend" / ".tmp_apply_test" / uuid.uuid4().hex
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "subject.py"
    original = b"VALUE = 'original'\n"
    target.write_bytes(original)

    new_text = "VALUE = 'new'\n"
    repo_rel = str(target.relative_to(REPO_ROOT)).replace("\\", "/")

    # Repoint proposal + backup dirs into the test tmp_path so we
    # don't pollute the real .file_change_proposals.
    proposal_dir = tmp_path / "_proposals"
    backup_dir = tmp_path / "_backups"
    proposal_dir.mkdir()
    backup_dir.mkdir()
    monkeypatch.setattr(mod, "_PROPOSAL_DIR", proposal_dir)
    monkeypatch.setattr(mod, "_BACKUP_DIR", backup_dir)

    # Stub git status to "clean" by default; tests that need dirty
    # override this themselves.
    monkeypatch.setattr(mod, "_git_status_porcelain", lambda _p: "")

    proposal_id = str(uuid.uuid4())
    artifact = {
        "proposal_id": proposal_id,
        "tool_id": "local.file_change_proposal",
        "target_path": str(target),
        "target_path_repo_relative": repo_rel,
        "change_type": "modify",
        "diff_text": new_text,
        "status": "proposed",
    }
    artifact_path = proposal_dir / f"{proposal_id}.json"
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")

    payload = {
        "proposal_id": proposal_id,
        "current_file_hash": _sha(original),
        "approved_diff_hash": _sha_text(new_text),
        "repo_root_relative_path": repo_rel,
        "backup_file_path": "ignored",
        "rollback_patch": "--- a\n+++ b\n",
        "tests_to_run_after_apply": ["tests/test_local_file_safety.py"],
        "commit_approval_id": "11111111-1111-1111-1111-111111111111",
        "change_type": "modify",
    }

    yield {
        "mod": mod,
        "target_abs": target,
        "target_repo_rel": repo_rel,
        "original_bytes": original,
        "new_text": new_text,
        "artifact_path": artifact_path,
        "payload": payload,
        "proposal_id": proposal_id,
        "backup_dir": backup_dir,
    }

    # Cleanup target file
    if target.exists():
        target.unlink()
    if target_dir.exists():
        try:
            target_dir.rmdir()
        except OSError:
            pass


class TestRegistered:
    async def test_handler_in_registry_after_import(self):
        import app.services.controlled_execution_handlers  # noqa: F401
        from app.services.controlled_execution_dispatch import registered_tool_ids

        assert "local.file_change_proposal.apply" in registered_tool_ids()


class TestPayloadValidation:
    @pytest.mark.parametrize("missing", [
        "proposal_id",
        "current_file_hash",
        "approved_diff_hash",
        "repo_root_relative_path",
        "backup_file_path",
        "rollback_patch",
        "tests_to_run_after_apply",
        "commit_approval_id",
        "change_type",
    ])
    async def test_required_field_missing(self, missing, repo_temp_file):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        mod = repo_temp_file["mod"]

        payload = dict(repo_temp_file["payload"])
        payload.pop(missing)
        ctx = _make_ctx(request=_make_request(), payload=payload)
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_file_change_proposal_apply(ctx)
        assert ei.value.code == f"payload_field_missing:{missing}"

    async def test_change_type_delete_refused(self, repo_temp_file):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        mod = repo_temp_file["mod"]

        payload = dict(repo_temp_file["payload"])
        payload["change_type"] = "delete"
        ctx = _make_ctx(request=_make_request(), payload=payload)
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_file_change_proposal_apply(ctx)
        assert ei.value.code == "change_type_delete_not_allowed_in_apply_v1"


class TestProposalArtifact:
    async def test_proposal_not_found(self, repo_temp_file):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        mod = repo_temp_file["mod"]

        payload = dict(repo_temp_file["payload"])
        payload["proposal_id"] = "nonexistent-uuid"
        ctx = _make_ctx(request=_make_request(), payload=payload)
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_file_change_proposal_apply(ctx)
        assert ei.value.code == "proposal_not_found"

    async def test_proposal_already_applied(self, repo_temp_file):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        mod = repo_temp_file["mod"]

        # Mark artifact applied.
        artifact_path = repo_temp_file["artifact_path"]
        artifact = json.loads(artifact_path.read_text())
        artifact["status"] = "applied"
        artifact_path.write_text(json.dumps(artifact))

        ctx = _make_ctx(
            request=_make_request(),
            payload=repo_temp_file["payload"],
        )
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_file_change_proposal_apply(ctx)
        assert ei.value.code == "proposal_already_applied"


class TestHashIntegrity:
    async def test_current_file_hash_mismatch(self, repo_temp_file):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        mod = repo_temp_file["mod"]

        # Tamper with the target file on disk.
        target = repo_temp_file["target_abs"]
        target.write_bytes(b"MODIFIED EXTERNALLY\n")

        ctx = _make_ctx(
            request=_make_request(),
            payload=repo_temp_file["payload"],
        )
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_file_change_proposal_apply(ctx)
        assert ei.value.code == "current_file_hash_mismatch"

    async def test_approved_diff_hash_mismatch(self, repo_temp_file):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        mod = repo_temp_file["mod"]

        payload = dict(repo_temp_file["payload"])
        payload["approved_diff_hash"] = "0" * 64  # not the real hash
        ctx = _make_ctx(request=_make_request(), payload=payload)
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_file_change_proposal_apply(ctx)
        assert ei.value.code == "approved_diff_hash_mismatch"


class TestPathSafety:
    async def test_secret_file_refused(self, repo_temp_file):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        mod = repo_temp_file["mod"]

        payload = dict(repo_temp_file["payload"])
        payload["repo_root_relative_path"] = "backend/.env"
        ctx = _make_ctx(request=_make_request(), payload=payload)
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_file_change_proposal_apply(ctx)
        assert ei.value.code == "target_path_is_secret_file"

    async def test_outside_repo_refused(self, repo_temp_file):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        mod = repo_temp_file["mod"]

        payload = dict(repo_temp_file["payload"])
        payload["repo_root_relative_path"] = "../../etc/passwd.py"
        ctx = _make_ctx(request=_make_request(), payload=payload)
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_file_change_proposal_apply(ctx)
        assert ei.value.code == "target_path_outside_repo"


class TestPytestPathSafety:
    async def test_invalid_pytest_path_refused(self, repo_temp_file):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        mod = repo_temp_file["mod"]

        payload = dict(repo_temp_file["payload"])
        payload["tests_to_run_after_apply"] = [
            "backend/tests/test_a.py; rm -rf /",
        ]
        ctx = _make_ctx(request=_make_request(), payload=payload)
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_file_change_proposal_apply(ctx)
        assert ei.value.code == "invalid_test_path"

    async def test_empty_test_list_refused(self, repo_temp_file):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        mod = repo_temp_file["mod"]

        payload = dict(repo_temp_file["payload"])
        payload["tests_to_run_after_apply"] = []
        ctx = _make_ctx(request=_make_request(), payload=payload)
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_file_change_proposal_apply(ctx)
        assert ei.value.code == "payload_field_missing:tests_to_run_after_apply"


class TestGitDirtyRefusal:
    async def test_dirty_target_file_refused(self, repo_temp_file, monkeypatch):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        mod = repo_temp_file["mod"]

        repo_rel = repo_temp_file["target_repo_rel"]
        monkeypatch.setattr(
            mod, "_git_status_porcelain",
            lambda p: f" M {repo_rel}",
        )

        ctx = _make_ctx(
            request=_make_request(),
            payload=repo_temp_file["payload"],
        )
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_file_change_proposal_apply(ctx)
        assert ei.value.code == "target_file_dirty_in_git"


class TestApplyAndRollback:
    async def test_tests_pass_applies_and_marks_artifact(self, repo_temp_file, monkeypatch):
        mod = repo_temp_file["mod"]
        target = repo_temp_file["target_abs"]
        new_text = repo_temp_file["new_text"]

        # Stub _run_pytest -> all pass
        async def _fake_pytest(spec):
            return 0, "1 passed"
        monkeypatch.setattr(mod, "_run_pytest", _fake_pytest)

        ctx = _make_ctx(
            request=_make_request(),
            payload=repo_temp_file["payload"],
        )
        result = await mod.handle_file_change_proposal_apply(ctx)

        assert result["status"] == "applied"
        assert result["tests_passed"] is True
        assert result["rolled_back"] is False
        # File contents updated
        assert target.read_bytes() == new_text.encode("utf-8")
        # Artifact marked applied
        artifact = json.loads(repo_temp_file["artifact_path"].read_text())
        assert artifact["status"] == "applied"
        assert artifact["applied_at"] is not None
        # Backup carries ORIGINAL bytes
        backup_glob = list(
            repo_temp_file["backup_dir"].rglob("subject.py")
        )
        assert len(backup_glob) == 1
        assert backup_glob[0].read_bytes() == repo_temp_file["original_bytes"]

    async def test_tests_fail_rollback_from_backup(self, repo_temp_file, monkeypatch):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        mod = repo_temp_file["mod"]
        target = repo_temp_file["target_abs"]

        # Stub _run_pytest -> fail
        async def _fake_pytest(spec):
            return 1, "1 failed: assertion error"
        monkeypatch.setattr(mod, "_run_pytest", _fake_pytest)

        ctx = _make_ctx(
            request=_make_request(),
            payload=repo_temp_file["payload"],
        )
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_file_change_proposal_apply(ctx)
        assert ei.value.code == "tests_failed_rolled_back"

        # File contents back to ORIGINAL
        assert target.read_bytes() == repo_temp_file["original_bytes"]
        # Artifact NOT marked applied (still 'proposed')
        artifact = json.loads(repo_temp_file["artifact_path"].read_text())
        assert artifact["status"] == "proposed"


class TestRollbackUsesBackupNotPatch:
    async def test_rollback_uses_backup_bytes(self, repo_temp_file, monkeypatch):
        """Mythos pin: rollback must read from backup file, NOT from
        the operator-supplied rollback_patch text. We prove this by
        passing a deliberately-wrong rollback_patch and checking
        that rollback still produces the original bytes."""
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        mod = repo_temp_file["mod"]
        target = repo_temp_file["target_abs"]

        async def _fake_pytest(spec):
            return 1, "fail"
        monkeypatch.setattr(mod, "_run_pytest", _fake_pytest)

        payload = dict(repo_temp_file["payload"])
        # If the handler used rollback_patch as the rollback source,
        # the file would end up containing this nonsense.
        payload["rollback_patch"] = "GARBAGE THAT WOULD BE WRITTEN IF USED"

        ctx = _make_ctx(request=_make_request(), payload=payload)
        with pytest.raises(ControlledExecutionRefused):
            await mod.handle_file_change_proposal_apply(ctx)

        # File restored from BACKUP (the actual original bytes), not
        # from the bogus rollback_patch text.
        assert target.read_bytes() == repo_temp_file["original_bytes"]
        assert b"GARBAGE" not in target.read_bytes()
