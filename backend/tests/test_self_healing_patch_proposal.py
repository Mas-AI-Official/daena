"""Sprint-17 PR-3 -- self-healing patch proposal generator.

Pins:
  1. suggested_brain == "human" returns no_brain_callable refusal.
  2. change_type != "modify" returns change_type_not_modify_v1.
  3. Empty diff_text returns diff_text_empty.
  4. Secret-file target returns target_path_is_secret_file.
  5. Outside-repo target returns target_path_outside_repo.
  6. Invalid pytest spec returns invalid_test_path.
  7. Empty test list returns invalid_test_path.
  8. Happy path returns valid=True with payload + metadata.
  9. Result is propose-only (no patch apply, no commit, no LLM call).
"""

from __future__ import annotations

import pytest


def _make_failure(
    *, suggested_brain="codex_cli", subsystem="test_regression",
    severity="warn",
):
    from app.services.self_healing_service import Failure
    return Failure(
        id="failure-abc",
        subsystem=subsystem,
        severity=severity,
        description="2 new pytest failures in fast subset",
        suggested_brain=suggested_brain,
        repair_action_class="patch_pytest_failures",
        department_hint="Engineering",
    )


def _make_patch(
    *,
    failure_id="failure-abc",
    target_repo_relative="backend/app/example.py",
    change_type="modify",
    diff_text="x = 1\n",
    tests_to_run_after_apply=None,
    suggested_brain="codex_cli",
    repair_action_class="patch_pytest_failures",
):
    from app.services.self_healing_patch_proposal import (
        SelfHealingPatchProposalInput,
    )
    return SelfHealingPatchProposalInput(
        failure_id=failure_id,
        target_repo_relative=target_repo_relative,
        change_type=change_type,
        diff_text=diff_text,
        tests_to_run_after_apply=(
            tests_to_run_after_apply
            if tests_to_run_after_apply is not None
            else ["tests/test_local_file_safety.py"]
        ),
        suggested_brain=suggested_brain,
        repair_action_class=repair_action_class,
    )


class TestHumanFallback:
    def test_human_brain_refused(self):
        from app.services.self_healing_patch_proposal import propose_patch

        failure = _make_failure(suggested_brain="human")
        patch = _make_patch(suggested_brain="human")
        result = propose_patch(failure=failure, patch=patch)
        assert result.valid is False
        assert result.refusal_code == "no_brain_callable"


class TestChangeTypeLock:
    @pytest.mark.parametrize("ct", ["delete", "create", "rename", "MODIFY", ""])
    def test_non_modify_refused(self, ct):
        from app.services.self_healing_patch_proposal import propose_patch

        failure = _make_failure()
        patch = _make_patch(change_type=ct)
        result = propose_patch(failure=failure, patch=patch)
        assert result.valid is False
        assert result.refusal_code == "change_type_not_modify_v1"


class TestDiffTextValidation:
    @pytest.mark.parametrize("diff", ["", "   ", "\n\n"])
    def test_empty_diff_refused(self, diff):
        from app.services.self_healing_patch_proposal import propose_patch

        failure = _make_failure()
        patch = _make_patch(diff_text=diff)
        result = propose_patch(failure=failure, patch=patch)
        assert result.valid is False
        assert result.refusal_code == "diff_text_empty"


class TestPathValidation:
    def test_secret_file_refused(self):
        from app.services.self_healing_patch_proposal import propose_patch

        failure = _make_failure()
        patch = _make_patch(target_repo_relative="backend/.env")
        result = propose_patch(failure=failure, patch=patch)
        assert result.valid is False
        assert result.refusal_code == "target_path_is_secret_file"

    def test_outside_repo_refused(self):
        from app.services.self_healing_patch_proposal import propose_patch

        failure = _make_failure()
        patch = _make_patch(target_repo_relative="../../etc/passwd.py")
        result = propose_patch(failure=failure, patch=patch)
        assert result.valid is False
        assert result.refusal_code == "target_path_outside_repo"


class TestPytestPathValidation:
    def test_shell_shaped_test_refused(self):
        from app.services.self_healing_patch_proposal import propose_patch

        failure = _make_failure()
        patch = _make_patch(
            tests_to_run_after_apply=["tests/test_a.py; rm -rf /"],
        )
        result = propose_patch(failure=failure, patch=patch)
        assert result.valid is False
        assert result.refusal_code == "invalid_test_path"

    def test_empty_test_list_refused(self):
        from app.services.self_healing_patch_proposal import propose_patch

        failure = _make_failure()
        patch = _make_patch(tests_to_run_after_apply=[])
        result = propose_patch(failure=failure, patch=patch)
        assert result.valid is False
        assert result.refusal_code == "invalid_test_path"


class TestHappyPath:
    def test_valid_proposal_returns_payload(self):
        from app.services.self_healing_patch_proposal import propose_patch

        failure = _make_failure(suggested_brain="codex_cli")
        patch = _make_patch(
            failure_id="failure-abc",
            target_repo_relative="backend/app/example.py",
            change_type="modify",
            diff_text="x = 42\n",
            tests_to_run_after_apply=[
                "tests/test_local_file_safety.py",
                "tests/test_self_healing_patch_proposal.py",
            ],
            suggested_brain="codex_cli",
            repair_action_class="patch_pytest_failures",
        )
        result = propose_patch(failure=failure, patch=patch)
        assert result.valid is True
        assert result.refusal_code is None

        # Controlled-execution payload shape
        assert result.proposal_payload == {
            "target_path": "backend/app/example.py",
            "change_type": "modify",
            "diff_text": "x = 42\n",
        }

        # Future-apply metadata includes everything the modal needs
        meta = result.metadata
        assert meta["self_healing"]["failure_id"] == "failure-abc"
        assert meta["self_healing"]["suggested_brain"] == "codex_cli"
        future = meta["future_apply_approval"]
        assert future["target_repo_relative"] == "backend/app/example.py"
        assert future["change_type"] == "modify"
        assert future["tests_to_run_after_apply"] == [
            "tests/test_local_file_safety.py",
            "tests/test_self_healing_patch_proposal.py",
        ]
        assert future["secret_file_check_passed"] is True
        assert future["outside_repo_check_passed"] is True
        assert future["diff_preview_lines"] == 1
        assert future["diff_excerpt"] == "x = 42\n"


class TestNoSideEffects:
    """Pin: the generator never writes to disk, never calls an LLM,
    never dispatches anything. It is a pure shaping function."""

    def test_function_does_not_call_subprocess(self, monkeypatch):
        import subprocess

        called = []
        original_run = subprocess.run

        def _track(*args, **kwargs):
            called.append((args, kwargs))
            return original_run(*args, **kwargs)
        monkeypatch.setattr(subprocess, "run", _track)

        from app.services.self_healing_patch_proposal import propose_patch
        propose_patch(failure=_make_failure(), patch=_make_patch())
        assert called == [], (
            f"propose_patch invoked subprocess: {called!r}"
        )
