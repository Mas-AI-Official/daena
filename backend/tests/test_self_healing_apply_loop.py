"""Sprint-17 PR-4 -- self-healing apply / test / rollback loop.

Pins:
  1. Audit-before stamped (always, regardless of outcome).
  2. Audit-after stamped (always, regardless of outcome).
  3. Success path: outcome="success", handler_result populated,
     no blocker workstream.
  4. tests_failed_rolled_back -> outcome="tests_rolled_back", no
     blocker (the apply handler already restored from backup).
  5. rollback_failed -> outcome="rollback_failed", blocker
     workstream payload emitted (P0 manual cleanup).
  6. Other refusals -> outcome="refused", no blocker.
  7. Unexpected handler crash -> outcome="crashed", blocker emitted.
  8. Loop NEVER raises (callers can rely on result fields only).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


pytestmark = pytest.mark.asyncio


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


class TestAuditAlwaysStamped:
    async def test_success_stamps_pre_and_post(self, monkeypatch):
        from app.services import self_healing_apply_loop as mod

        async def _fake_dispatch(db, *, request, payload, tenant_id, user_id):
            return {"status": "applied", "tests_passed": True}

        monkeypatch.setattr(
            mod, "dispatch_controlled_execution", _fake_dispatch,
        )

        result = await mod.run_apply_cycle(
            db=MagicMock(), request=_make_request(),
            payload={}, tenant_id="t", user_id="u",
        )
        assert result.outcome == "success"
        assert result.audit_preflight["when"] == "preflight"
        assert result.audit_result["when"] == "result"
        assert result.audit_preflight["tool_id"] == "local.file_change_proposal.apply"
        assert result.handler_result == {"status": "applied", "tests_passed": True}
        assert result.blocker_workstream is None


class TestRefusalClassification:
    async def test_tests_failed_rolled_back(self, monkeypatch):
        from app.services import self_healing_apply_loop as mod
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )

        async def _fake_dispatch(*args, **kwargs):
            raise ControlledExecutionRefused(
                "tests_failed_rolled_back",
                "1 test failed",
            )

        monkeypatch.setattr(
            mod, "dispatch_controlled_execution", _fake_dispatch,
        )

        result = await mod.run_apply_cycle(
            db=MagicMock(), request=_make_request(),
            payload={}, tenant_id="t", user_id="u",
        )
        assert result.outcome == "tests_rolled_back"
        assert result.refusal_code == "tests_failed_rolled_back"
        # NO blocker -- file already restored by the handler
        assert result.blocker_workstream is None

    async def test_rollback_failed_emits_blocker(self, monkeypatch):
        from app.services import self_healing_apply_loop as mod
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )

        async def _fake_dispatch(*args, **kwargs):
            raise ControlledExecutionRefused(
                "rollback_failed",
                "PermissionError on backup restore",
            )

        monkeypatch.setattr(
            mod, "dispatch_controlled_execution", _fake_dispatch,
        )

        result = await mod.run_apply_cycle(
            db=MagicMock(), request=_make_request(),
            payload={}, tenant_id="t", user_id="u",
        )
        assert result.outcome == "rollback_failed"
        assert result.refusal_code == "rollback_failed"
        # Blocker workstream populated.
        assert result.blocker_workstream is not None
        assert "BLOCKER" in result.blocker_workstream["goal"]
        assert (
            result.blocker_workstream["initial_context"]
            ["self_repair_blocker"]["severity"]
            == "blocker"
        )

    async def test_other_refusal_no_blocker(self, monkeypatch):
        from app.services import self_healing_apply_loop as mod
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )

        async def _fake_dispatch(*args, **kwargs):
            raise ControlledExecutionRefused(
                "current_file_hash_mismatch",
                "drifted",
            )

        monkeypatch.setattr(
            mod, "dispatch_controlled_execution", _fake_dispatch,
        )

        result = await mod.run_apply_cycle(
            db=MagicMock(), request=_make_request(),
            payload={}, tenant_id="t", user_id="u",
        )
        assert result.outcome == "refused"
        assert result.refusal_code == "current_file_hash_mismatch"
        assert result.blocker_workstream is None


class TestUnexpectedCrash:
    async def test_handler_raises_emits_blocker(self, monkeypatch):
        from app.services import self_healing_apply_loop as mod

        async def _fake_dispatch(*args, **kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(
            mod, "dispatch_controlled_execution", _fake_dispatch,
        )

        result = await mod.run_apply_cycle(
            db=MagicMock(), request=_make_request(),
            payload={}, tenant_id="t", user_id="u",
        )
        assert result.outcome == "crashed"
        assert result.refusal_code == "handler_crashed"
        assert result.blocker_workstream is not None
        # The crash detail mentions the exception type.
        assert "RuntimeError" in result.refusal_detail


class TestLoopNeverRaises:
    """Callers rely on result fields, not on exception flow.
    The loop must catch every reasonable failure mode."""

    @pytest.mark.parametrize("exc_factory", [
        lambda: RuntimeError("arbitrary"),
        lambda: ValueError("arbitrary"),
        lambda: KeyError("missing"),
    ])
    async def test_arbitrary_exception_does_not_propagate(
        self, monkeypatch, exc_factory,
    ):
        from app.services import self_healing_apply_loop as mod

        async def _fake_dispatch(*args, **kwargs):
            raise exc_factory()

        monkeypatch.setattr(
            mod, "dispatch_controlled_execution", _fake_dispatch,
        )

        # Must not raise.
        result = await mod.run_apply_cycle(
            db=MagicMock(), request=_make_request(),
            payload={}, tenant_id="t", user_id="u",
        )
        assert result.outcome == "crashed"
