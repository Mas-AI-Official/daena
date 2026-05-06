"""Sprint-13 PR-8 -- controlled execution design lock contract.

These tests pin the Phase 3 design WITHOUT unlocking it. The lock
is:
  * WRITE_TOOLS is empty in this PR.
  * The 10-field locked contract is exactly what
    _REQUIRED_FIELDS says.
  * INTEGRATIONS_PHASE2_READONLY remains True (env is the actual
    enforcement).
  * The validator refuses any request whose tool_id is not in
    WRITE_TOOLS -- which is the entire WRITE_TOOLS set in PR-8.

When a later sprint adds the first write tool, the test that locks
"WRITE_TOOLS is empty" will fail intentionally; the operator must
update it knowingly. That deliberate test failure is the
operator-visible signal that Phase 3 is being opened.
"""

from __future__ import annotations

import os

import pytest


pytestmark = pytest.mark.asyncio


_LOCKED_FIELDS = (
    "approval_id",
    "consent_grant_id",
    "payload_hash",
    "tool_id",
    "owner_email",
    "asset_shield_pass",
    "policy_allowlist_pass",
    "audit_preflight_row_id",
    "audit_result_row_id",
    "rollback_or_undo_instruction",
)


class TestPhase3StaysOff:
    async def test_write_tools_is_empty(self):
        """Phase 3 is locked closed in PR-8. The first write tool
        added in a later sprint must update this test on purpose."""
        from app.services.controlled_execution_design import WRITE_TOOLS

        assert WRITE_TOOLS == frozenset(), (
            f"WRITE_TOOLS expected empty for PR-8, got {sorted(WRITE_TOOLS)}"
        )

    async def test_readonly_env_default_unchanged(self):
        """The Phase 3 readonly env defaults to true. The PR does
        not flip it."""
        # When the var is unset OR set to anything other than 'false',
        # the assertion holds. The test reads the OS env directly so
        # a CI runner that sets it to 'true' explicitly is also OK.
        v = (os.environ.get("INTEGRATIONS_PHASE2_READONLY") or "true").lower()
        assert v == "true", (
            f"INTEGRATIONS_PHASE2_READONLY must remain 'true' until "
            f"a Phase 3 sprint unlocks it; got {v!r}"
        )


class TestContractShape:
    async def test_required_fields_locked(self):
        from app.services.controlled_execution_design import _REQUIRED_FIELDS

        assert _REQUIRED_FIELDS == _LOCKED_FIELDS

    async def test_dataclass_carries_all_fields(self):
        from app.services.controlled_execution_design import (
            ControlledExecutionRequest,
        )
        # Build a fully-populated request and inspect the dataclass.
        req = ControlledExecutionRequest(
            approval_id="a",
            consent_grant_id="c",
            payload_hash="0" * 64,
            tool_id="not_a_real_tool",
            owner_email=None,
            asset_shield_pass=True,
            policy_allowlist_pass=True,
            audit_preflight_row_id="p",
            audit_result_row_id=None,
            rollback_or_undo_instruction=None,
        )
        for f in _LOCKED_FIELDS:
            assert hasattr(req, f), f"missing field {f!r}"


class TestValidatorRefusesEverything:
    async def test_refuses_any_tool_id_in_pr8(self):
        from app.services.controlled_execution_design import (
            ControlledExecutionDesignError,
            ControlledExecutionRequest,
            validate_controlled_execution_request,
        )
        req = ControlledExecutionRequest(
            approval_id="a",
            consent_grant_id="c",
            payload_hash="0" * 64,
            tool_id="email_send",   # not in PR-8 allowlist
            owner_email="founder@example.com",
            asset_shield_pass=True,
            policy_allowlist_pass=True,
            audit_preflight_row_id="p",
            audit_result_row_id=None,
            rollback_or_undo_instruction=None,
        )
        with pytest.raises(ControlledExecutionDesignError) as ei:
            validate_controlled_execution_request(req)
        assert "tool_id_not_in_allowlist" in str(ei.value)

    async def test_refuses_short_payload_hash(self):
        from app.services.controlled_execution_design import (
            ControlledExecutionDesignError,
            ControlledExecutionRequest,
            WRITE_TOOLS,
            validate_controlled_execution_request,
        )
        # Even with a permissive tool, a non-sha256 hash refuses.
        # Since WRITE_TOOLS is empty, we can't build a passing
        # request -- but we can craft the hash refuse path by
        # temporarily extending the allowlist via a monkey-patch.
        import app.services.controlled_execution_design as mod

        original = mod.WRITE_TOOLS
        try:
            mod.WRITE_TOOLS = frozenset({"test_tool"})
            req = ControlledExecutionRequest(
                approval_id="a",
                consent_grant_id="c",
                payload_hash="short",
                tool_id="test_tool",
                owner_email=None,
                asset_shield_pass=True,
                policy_allowlist_pass=True,
                audit_preflight_row_id="p",
                audit_result_row_id=None,
                rollback_or_undo_instruction=None,
            )
            with pytest.raises(ControlledExecutionDesignError) as ei:
                validate_controlled_execution_request(req)
            assert "payload_hash" in str(ei.value)
        finally:
            mod.WRITE_TOOLS = original
