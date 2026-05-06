"""Sprint-15 PR-5 -- file-change-apply design lock contract.

These tests pin the design WITHOUT unlocking it.

The locks:
  * ``local.file_change_proposal.apply`` is NOT in WRITE_TOOLS.
  * No apply handler is registered in
    ``controlled_execution_dispatch._TOOL_HANDLERS``.
  * The 9-field locked contract is exactly what
    ``_REQUIRED_APPLY_FIELDS`` says.
  * The validator refuses any request with a missing required
    field, a non-sha256 hash, or change_type != "modify".
  * No HTTP endpoint exposes apply.

When a later sprint adds the apply tool, the test
``TestApplyToolStaysOutOfWriteTools`` will fail intentionally; the
operator must update it knowingly. That deliberate test failure is
the operator-visible signal that file-apply is being unlocked.
"""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.asyncio


_LOCKED_FIELDS = (
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


def _good_request():
    """Build a fully-valid apply request for negative-path tests."""
    from app.services.file_proposal_apply_design import (
        ApplyFileChangeProposalRequest,
    )
    return ApplyFileChangeProposalRequest(
        proposal_id="prop-uuid",
        current_file_hash="0" * 64,
        approved_diff_hash="1" * 64,
        repo_root_relative_path="backend/app/example.py",
        backup_file_path=r"backend\.file_change_backups\prop-uuid\example.py",
        rollback_patch="--- a\n+++ b\n",
        tests_to_run_after_apply=["backend/tests/test_example.py"],
        commit_approval_id="commit-approval-uuid",
        change_type="modify",
    )


class TestApplyToolUnlockedInSprint17:
    """Sprint-17 PR-1 (2026-05-06): the apply tool is now in
    WRITE_TOOLS. The Sprint-15 PR-5 lock has been deliberately
    flipped in this same PR -- the operator-visible signal that
    file-apply has been unlocked."""

    async def test_apply_tool_id_in_write_tools(self):
        from app.services.controlled_execution_design import WRITE_TOOLS
        from app.services.file_proposal_apply_design import APPLY_TOOL_ID

        assert APPLY_TOOL_ID == "local.file_change_proposal.apply"
        assert APPLY_TOOL_ID in WRITE_TOOLS, (
            f"{APPLY_TOOL_ID!r} expected in WRITE_TOOLS after Sprint-17 "
            f"unlock; got {sorted(WRITE_TOOLS)}"
        )

    async def test_apply_handler_registered(self):
        """The dispatcher's handler registry MUST carry an entry
        for the apply tool now. The Sprint-17 handlers package
        side-effect-imports the new handler module."""
        import app.services.controlled_execution_handlers  # noqa: F401
        from app.services.controlled_execution_dispatch import (
            registered_tool_ids,
        )
        from app.services.file_proposal_apply_design import APPLY_TOOL_ID

        assert APPLY_TOOL_ID in registered_tool_ids()


class TestContractShape:
    async def test_required_fields_locked(self):
        from app.services.file_proposal_apply_design import (
            _REQUIRED_APPLY_FIELDS,
        )
        assert _REQUIRED_APPLY_FIELDS == _LOCKED_FIELDS

    async def test_dataclass_carries_all_fields(self):
        from app.services.file_proposal_apply_design import (
            ApplyFileChangeProposalRequest,
        )
        req = _good_request()
        for f in _LOCKED_FIELDS:
            assert hasattr(req, f), f"missing field {f!r}"

    async def test_dataclass_is_frozen(self):
        """Apply request is immutable -- once built, every field
        is fixed. Prevents accidental mutation between approval
        and apply."""
        from dataclasses import FrozenInstanceError

        req = _good_request()
        with pytest.raises(FrozenInstanceError):
            req.proposal_id = "tampered"  # type: ignore[misc]


class TestValidatorRefusesMissingFields:
    async def test_validates_good_request(self):
        from app.services.file_proposal_apply_design import (
            validate_apply_file_change_proposal_request,
        )
        # Should not raise.
        validate_apply_file_change_proposal_request(_good_request())

    @pytest.mark.parametrize("field,bad_value,expected_substring", [
        ("proposal_id", "", "proposal_id_required"),
        ("current_file_hash", "", "current_file_hash_required"),
        ("current_file_hash", "short", "current_file_hash_required"),
        ("approved_diff_hash", "", "approved_diff_hash_required"),
        ("approved_diff_hash", "short", "approved_diff_hash_required"),
        ("repo_root_relative_path", "", "repo_root_relative_path_required"),
        ("backup_file_path", "", "backup_file_path_required"),
        ("rollback_patch", "", "rollback_patch_required"),
        ("commit_approval_id", "", "commit_approval_id_required"),
    ])
    async def test_refuses_missing_or_short_field(
        self, field, bad_value, expected_substring,
    ):
        from app.services.file_proposal_apply_design import (
            ApplyFileChangeProposalRequest,
            FileProposalApplyDesignError,
            validate_apply_file_change_proposal_request,
        )

        good = _good_request()
        kwargs = {f: getattr(good, f) for f in _LOCKED_FIELDS}
        kwargs[field] = bad_value
        bad_req = ApplyFileChangeProposalRequest(**kwargs)

        with pytest.raises(FileProposalApplyDesignError) as ei:
            validate_apply_file_change_proposal_request(bad_req)
        assert expected_substring in str(ei.value)


class TestChangeTypeForbidsDelete:
    async def test_change_type_delete_refused(self):
        from app.services.file_proposal_apply_design import (
            ApplyFileChangeProposalRequest,
            FileProposalApplyDesignError,
            validate_apply_file_change_proposal_request,
        )
        good = _good_request()
        kwargs = {f: getattr(good, f) for f in _LOCKED_FIELDS}
        kwargs["change_type"] = "delete"  # type: ignore[arg-type]
        # The Literal narrowing won't catch this at runtime, only at
        # type-check time. The validator catches it at runtime.
        bad_req = ApplyFileChangeProposalRequest(**kwargs)
        with pytest.raises(FileProposalApplyDesignError) as ei:
            validate_apply_file_change_proposal_request(bad_req)
        assert "change_type_must_be_modify_in_apply_v1" in str(ei.value)


class TestApplyOnlyViaControlledExecutionDispatch:
    """Sprint-17: there is STILL no dedicated apply HTTP route.
    The apply tool fires only via the controlled-execution dispatch
    endpoint at POST /api/v1/integrations/controlled-execution/dispatch.
    A direct apply route would skip the six dispatch gates."""

    async def test_no_dedicated_apply_route(self):
        from app.api.v1 import router as v1_router

        for route in v1_router.routes:
            path = getattr(route, "path", "")
            # Forbid a /file-apply or /apply-file-change-proposal
            # endpoint anywhere. Apply must flow through the
            # controlled-execution dispatch.
            assert not path.endswith("/file-apply"), (
                f"route {path!r} would skip the dispatch gates"
            )
            assert "file_change_proposal/apply" not in path, (
                f"route {path!r} would expose direct apply"
            )
