"""Sprint-17 PR-5 -- git_commit_approved_patch handler contract.

Pins:
  1. Handler registered after package import.
  2. proposal_id + commit_message required.
  3. Proposal not found / not applied / no applied_at refused.
  4. Unrelated dirty files in git status refuses.
  5. Target file not dirty refuses.
  6. Control chars / empty commit message refused.
  7. git add / git commit failures captured as git_command_failed.
  8. Success path: artifact updated to status=committed with commit_sha.
  9. Handler NEVER pushes (subprocess args asserted).
 10. Commit message is sanitized + tagged with chore(self-healing) prefix.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock

import pytest


pytestmark = pytest.mark.asyncio


def _make_request(**overrides):
    from app.services.controlled_execution_design import ControlledExecutionRequest
    base = dict(
        approval_id="00000000-0000-0000-0000-000000000000",
        consent_grant_id="grant-x",
        payload_hash="0" * 64,
        tool_id="local.git_commit_approved_patch",
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
def commit_setup(tmp_path, monkeypatch):
    """Build an applied proposal artifact + clean payload.

    Repoints _PROPOSAL_DIR into the test tmp_path. Stubs
    _git_porcelain_all and _git_run; tests override them as needed.
    """
    from app.services.controlled_execution_handlers import (
        git_commit_approved_patch as mod,
    )

    proposal_dir = tmp_path / "_proposals"
    proposal_dir.mkdir()
    monkeypatch.setattr(mod, "_PROPOSAL_DIR", proposal_dir)

    proposal_id = str(uuid.uuid4())
    repo_rel = "backend/app/example.py"
    artifact = {
        "proposal_id": proposal_id,
        "tool_id": "local.file_change_proposal",
        "target_path_repo_relative": repo_rel,
        "change_type": "modify",
        "diff_text": "x = 1\n",
        "status": "applied",
        "applied_at": "2026-05-06T12:00:00+00:00",
    }
    (proposal_dir / f"{proposal_id}.json").write_text(json.dumps(artifact))

    # Default git stubs: clean status with target dirty + successful
    # commit returning a fake SHA. Tests can override per case.
    porcelain_calls = []
    git_run_calls = []

    def _fake_porcelain():
        porcelain_calls.append(True)
        return f" M {repo_rel}"

    def _fake_git_run(args):
        git_run_calls.append(list(args))
        if args[0] == "rev-parse":
            return 0, "abcdef1234567890abcdef1234567890abcdef12\n", ""
        return 0, "", ""

    monkeypatch.setattr(mod, "_git_porcelain_all", _fake_porcelain)
    monkeypatch.setattr(mod, "_git_run", _fake_git_run)

    return {
        "mod": mod,
        "proposal_id": proposal_id,
        "repo_rel": repo_rel,
        "proposal_dir": proposal_dir,
        "git_run_calls": git_run_calls,
        "porcelain_calls": porcelain_calls,
        "payload": {
            "proposal_id": proposal_id,
            "commit_message": "fix self-healing patch for example.py",
        },
    }


class TestRegistered:
    async def test_handler_in_registry(self):
        import app.services.controlled_execution_handlers  # noqa: F401
        from app.services.controlled_execution_dispatch import registered_tool_ids

        assert "local.git_commit_approved_patch" in registered_tool_ids()


class TestPayloadValidation:
    @pytest.mark.parametrize("missing", ["proposal_id", "commit_message"])
    async def test_required_field_missing(self, missing, commit_setup):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        mod = commit_setup["mod"]

        payload = dict(commit_setup["payload"])
        payload.pop(missing)
        ctx = _make_ctx(request=_make_request(), payload=payload)
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_git_commit_approved_patch(ctx)
        assert ei.value.code == f"payload_field_missing:{missing}"


class TestProposalChecks:
    async def test_proposal_not_found(self, commit_setup):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        mod = commit_setup["mod"]

        payload = dict(commit_setup["payload"])
        payload["proposal_id"] = "nonexistent"
        ctx = _make_ctx(request=_make_request(), payload=payload)
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_git_commit_approved_patch(ctx)
        assert ei.value.code == "proposal_not_found"

    async def test_proposal_not_applied(self, commit_setup):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        mod = commit_setup["mod"]

        # Mark artifact 'proposed' instead of 'applied'
        artifact_path = (
            commit_setup["proposal_dir"]
            / f"{commit_setup['proposal_id']}.json"
        )
        artifact = json.loads(artifact_path.read_text())
        artifact["status"] = "proposed"
        artifact_path.write_text(json.dumps(artifact))

        ctx = _make_ctx(
            request=_make_request(), payload=commit_setup["payload"],
        )
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_git_commit_approved_patch(ctx)
        assert ei.value.code == "proposal_not_applied"


class TestCommitMessageSanitization:
    async def test_control_chars_refused(self, commit_setup):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        mod = commit_setup["mod"]

        payload = dict(commit_setup["payload"])
        payload["commit_message"] = "fix\x00null-byte"
        ctx = _make_ctx(request=_make_request(), payload=payload)
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_git_commit_approved_patch(ctx)
        assert ei.value.code == "invalid_commit_message"

    async def test_empty_commit_message_refused(self, commit_setup):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        mod = commit_setup["mod"]

        payload = dict(commit_setup["payload"])
        payload["commit_message"] = "   "  # whitespace only
        ctx = _make_ctx(request=_make_request(), payload=payload)
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_git_commit_approved_patch(ctx)
        # Whitespace-only fails the required-field check first.
        assert ei.value.code == "payload_field_missing:commit_message"


class TestGitStatusChecks:
    async def test_unrelated_dirty_file_refused(self, commit_setup, monkeypatch):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        mod = commit_setup["mod"]
        repo_rel = commit_setup["repo_rel"]

        # Status reports BOTH the target AND an unrelated file dirty.
        def _fake_porcelain():
            return f" M {repo_rel}\n M backend/app/unrelated.py"
        monkeypatch.setattr(mod, "_git_porcelain_all", _fake_porcelain)

        ctx = _make_ctx(
            request=_make_request(), payload=commit_setup["payload"],
        )
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_git_commit_approved_patch(ctx)
        assert ei.value.code == "git_status_has_unrelated_dirty_files"

    async def test_target_file_not_dirty_refused(self, commit_setup, monkeypatch):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        mod = commit_setup["mod"]

        def _fake_porcelain():
            return ""  # clean tree -- nothing to commit
        monkeypatch.setattr(mod, "_git_porcelain_all", _fake_porcelain)

        ctx = _make_ctx(
            request=_make_request(), payload=commit_setup["payload"],
        )
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_git_commit_approved_patch(ctx)
        assert ei.value.code == "target_file_not_dirty"


class TestGitFailures:
    async def test_git_add_failure_refuses(self, commit_setup, monkeypatch):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        mod = commit_setup["mod"]

        def _fake_git_run(args):
            if args[0] == "add":
                return 1, "", "fatal: pathspec did not match"
            return 0, "", ""
        monkeypatch.setattr(mod, "_git_run", _fake_git_run)

        ctx = _make_ctx(
            request=_make_request(), payload=commit_setup["payload"],
        )
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_git_commit_approved_patch(ctx)
        assert ei.value.code == "git_command_failed"


class TestSuccessAndNoPush:
    async def test_success_marks_committed(self, commit_setup):
        mod = commit_setup["mod"]

        ctx = _make_ctx(
            request=_make_request(), payload=commit_setup["payload"],
        )
        result = await mod.handle_git_commit_approved_patch(ctx)

        assert result["status"] == "committed"
        assert result["tool_id"] == "local.git_commit_approved_patch"
        assert result["commit_sha"].startswith("abcdef1234567890")
        assert result["commit_sha_short"] == "abcdef123456"

        # Artifact updated
        artifact_path = (
            commit_setup["proposal_dir"]
            / f"{commit_setup['proposal_id']}.json"
        )
        artifact = json.loads(artifact_path.read_text())
        assert artifact["status"] == "committed"
        assert artifact["commit_sha"].startswith("abcdef1234567890")
        assert artifact["committed_at"] is not None

    async def test_handler_never_pushes(self, commit_setup):
        """Walk every git subprocess invocation and assert no
        'push' / 'force' / '--no-verify' arg ever appears."""
        mod = commit_setup["mod"]

        ctx = _make_ctx(
            request=_make_request(), payload=commit_setup["payload"],
        )
        await mod.handle_git_commit_approved_patch(ctx)

        for invocation in commit_setup["git_run_calls"]:
            assert "push" not in invocation, f"push found in {invocation}"
            assert "--force" not in invocation
            assert "-f" not in invocation
            assert "--no-verify" not in invocation
            # No interactive flags either.
            assert "-i" not in invocation
            assert "rebase" not in invocation


class TestCommitMessageTagging:
    async def test_message_prefixed_with_self_healing_chore(
        self, commit_setup, monkeypatch,
    ):
        """The committed message MUST start with the
        chore(self-healing) prefix so the git log groups Daena
        commits."""
        mod = commit_setup["mod"]

        # Capture the actual commit message git was given
        captured = {}

        def _fake_git_run(args):
            if args[0] == "commit":
                # ["commit", "-m", "<msg>"]
                captured["message"] = args[2]
                return 0, "", ""
            if args[0] == "rev-parse":
                return 0, "shashashashashashashashashashashashashash\n", ""
            return 0, "", ""
        monkeypatch.setattr(mod, "_git_run", _fake_git_run)

        payload = dict(commit_setup["payload"])
        payload["commit_message"] = "patch the example file"
        ctx = _make_ctx(request=_make_request(), payload=payload)
        await mod.handle_git_commit_approved_patch(ctx)

        assert captured["message"].startswith("chore(self-healing): ")
        assert "patch the example file" in captured["message"]
        # Body should reference the proposal id
        assert commit_setup["proposal_id"] in captured["message"]
