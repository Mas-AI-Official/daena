"""Sprint-14 PR-1 -- controlled execution dispatch spine contract.

Pins the gate ordering + canonical payload-hash format. PR-1 ships
the spine with NO registered tools; every dispatch MUST refuse
somewhere.

Gates (in order, each tested):
  1. Autonomy mode != approved_execution -> refuse
  2. PR-8 design validator (tool_id not in WRITE_TOOLS, etc.) -> refuse
  3. payload hash mismatch -> refuse
  4. approval not found / not approved / expired / wrong tool_id -> refuse
  5. tool handler not registered (PR-1 case) -> refuse

Plus:
  - canonical payload_hash format is contract-locked
  - endpoint mounted at /integrations/controlled-execution/dispatch
  - registered tools inspector returns [] in PR-1
"""

from __future__ import annotations

import hashlib
import json

import pytest


pytestmark = pytest.mark.asyncio


# ─────────────────────────────────────────────────────────────────────
# Canonical hash
# ─────────────────────────────────────────────────────────────────────


class TestCanonicalPayloadHash:
    async def test_format_is_sha256_of_sorted_compact_json(self):
        from app.services.controlled_execution_dispatch import compute_payload_hash

        payload = {"to": "ops@example.com", "subject": "x", "body": "hi"}
        # Recompute exactly the same way the contract describes:
        canonical = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        )
        expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        assert compute_payload_hash(payload) == expected
        assert len(expected) == 64

    async def test_key_order_does_not_affect_hash(self):
        """sort_keys=True means {"a":1,"b":2} hashes the same as
        {"b":2,"a":1}. Sprint-15's send unlock relies on this --
        the same payload approved at draft-time must hash equal at
        send-time regardless of key insertion order."""
        from app.services.controlled_execution_dispatch import compute_payload_hash

        a = {"to": "x", "subject": "y", "body": "z"}
        b = {"body": "z", "to": "x", "subject": "y"}
        assert compute_payload_hash(a) == compute_payload_hash(b)


# ─────────────────────────────────────────────────────────────────────
# Endpoint mount
# ─────────────────────────────────────────────────────────────────────


class TestEndpointMounted:
    async def test_dispatch_route_exists(self):
        from app.api.v1 import router as api_v1_router

        paths = [getattr(r, "path", "") for r in api_v1_router.routes]
        assert "/integrations/controlled-execution/dispatch" in paths

    async def test_registered_tools_route_exists(self):
        from app.api.v1 import router as api_v1_router

        paths = [getattr(r, "path", "") for r in api_v1_router.routes]
        assert "/integrations/controlled-execution/registered-tools" in paths


# ─────────────────────────────────────────────────────────────────────
# Empty registry
# ─────────────────────────────────────────────────────────────────────


class TestEmptyRegistryAtPR1:
    async def test_no_handlers_registered_yet(self):
        from app.services import controlled_execution_dispatch as mod

        # PR-1 ships an empty registry. If a later PR pre-registers
        # a handler unintentionally, this test catches it.
        mod.reset_handlers_for_tests()
        assert mod.registered_tool_ids() == []


# ─────────────────────────────────────────────────────────────────────
# Gate refusals
# ─────────────────────────────────────────────────────────────────────


class TestAutonomyModeGate:
    async def test_default_mode_refuses(self, tmp_path, monkeypatch):
        """Default autonomy mode is research_draft. Dispatch must
        refuse with autonomy_mode_does_not_allow_dispatch."""
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
            _check_autonomy_mode_allows_dispatch,
        )
        import app.api.v1.autonomy_mode as am

        # Point persistence at a tmp file with no override (default mode).
        monkeypatch.setattr(am, "_AUTONOMY_FILE", tmp_path / ".autonomy_mode.json")
        with pytest.raises(ControlledExecutionRefused) as ei:
            _check_autonomy_mode_allows_dispatch()
        assert ei.value.code == "autonomy_mode_does_not_allow_dispatch"

    async def test_approved_execution_mode_passes(self, tmp_path, monkeypatch):
        from app.services.controlled_execution_dispatch import (
            _check_autonomy_mode_allows_dispatch,
        )
        import app.api.v1.autonomy_mode as am

        target = tmp_path / ".autonomy_mode.json"
        monkeypatch.setattr(am, "_AUTONOMY_FILE", target)
        am._write_persisted(am.AutonomyMode.APPROVED_EXECUTION)
        # Should NOT raise.
        _check_autonomy_mode_allows_dispatch()


class TestRefusalCodes:
    async def test_invalid_uuid_approval_id(self, tmp_path, monkeypatch):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
            _load_approval,
        )
        with pytest.raises(ControlledExecutionRefused) as ei:
            await _load_approval(
                db=None,                     # not reached
                approval_id="not-a-uuid",
                tenant_id=None,              # not reached
            )
        assert ei.value.code == "approval_id_not_uuid"

    async def test_register_tool_handler_refuses_unknown_tool(self):
        from app.services import controlled_execution_dispatch as mod

        async def _h(ctx):
            return {}

        with pytest.raises(RuntimeError) as ei:
            mod.register_tool_handler("not.a.real.tool", _h)
        assert "not in WRITE_TOOLS" in str(ei.value)


class TestStableRefusalContract:
    """The refusal codes are the wire-format contract. The UI
    matches on these prefixes, so renaming any one is a breaking
    change. The test pins the set."""

    async def test_documented_codes_exist(self):
        # These codes are referenced from this test alone -- they
        # exist as string literals in the dispatch module. The lock
        # is "if you rename one, this test fails on purpose, and the
        # UI/test fixtures need updating in the same PR."
        expected_codes = {
            "autonomy_mode_does_not_allow_dispatch",
            "design_contract_failed",
            "payload_hash_mismatch",
            "approval_id_not_uuid",
            "approval_not_found",
            "approval_not_in_approved_state",
            "approval_expired",
            "approval_tool_id_mismatch",
            "tool_handler_not_registered",
        }
        # Read the source file and assert each code appears.
        from pathlib import Path
        src = (
            Path(__file__).resolve().parents[1]
            / "app/services/controlled_execution_dispatch.py"
        ).read_text(encoding="utf-8")
        for code in expected_codes:
            assert code in src, (
                f"refusal code {code!r} no longer present in dispatch source"
            )
