"""Sprint-14 PR-5 -- trust ladder foundation contract.

Pins:
  1. record_decision("approved", ...) increments approvals_count
     + stamps last_approved_at.
  2. record_decision("rejected", ...) increments rejection_count
     + stamps last_rejected_at.
  3. PR-5 NEVER raises max_auto_tier above DEFAULT_MAX_AUTO_TIER
     ("none") automatically.
  4. PR-5 never auto-executes anything; the module surface is
     record + read only.
  5. Persistence file is gitignored.
"""

from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.asyncio


class TestRecordDecision:
    async def test_approved_then_rejected_round_trip(
        self, tmp_path, monkeypatch,
    ):
        from app.services import trust_ladder as mod

        monkeypatch.setattr(mod, "_LADDER_FILE", tmp_path / ".trust_ladder.json")

        e1 = mod.record_decision(
            tool_id="gmail.create_draft",
            template_id="cold_email_v1",
            decision="approved",
        )
        assert e1.approvals_count == 1
        assert e1.last_approved_at is not None
        assert e1.rejection_count == 0

        e2 = mod.record_decision(
            tool_id="gmail.create_draft",
            template_id="cold_email_v1",
            decision="approved",
        )
        assert e2.approvals_count == 2

        e3 = mod.record_decision(
            tool_id="gmail.create_draft",
            template_id="cold_email_v1",
            decision="rejected",
        )
        assert e3.approvals_count == 2
        assert e3.rejection_count == 1
        assert e3.last_rejected_at is not None

        # Independently fetched entry sees same values.
        loaded = mod.get_entry(
            tool_id="gmail.create_draft",
            template_id="cold_email_v1",
        )
        assert loaded is not None
        assert loaded.approvals_count == 2
        assert loaded.rejection_count == 1


class TestNoAutoTierEscalation:
    async def test_max_auto_tier_stays_default_after_many_approvals(
        self, tmp_path, monkeypatch,
    ):
        """PR-5 record-only invariant: even after N approvals,
        max_auto_tier stays at DEFAULT_MAX_AUTO_TIER. Trust
        graduation is a separate sprint."""
        from app.services import trust_ladder as mod

        monkeypatch.setattr(mod, "_LADDER_FILE", tmp_path / ".trust_ladder.json")

        for _ in range(12):
            mod.record_decision(
                tool_id="gmail.create_draft",
                template_id="cold_email_v1",
                decision="approved",
            )
        e = mod.get_entry(
            tool_id="gmail.create_draft",
            template_id="cold_email_v1",
        )
        assert e is not None
        assert e.max_auto_tier == mod.DEFAULT_MAX_AUTO_TIER


class TestInvalidInputs:
    async def test_unknown_decision_value_raises(self, tmp_path, monkeypatch):
        from app.services import trust_ladder as mod

        monkeypatch.setattr(mod, "_LADDER_FILE", tmp_path / ".trust_ladder.json")
        with pytest.raises(ValueError):
            mod.record_decision(
                tool_id="x", template_id="y", decision="ignored",  # type: ignore[arg-type]
            )


class TestGitignored:
    async def test_persistence_file_in_gitignore(self):
        backend_root = Path(__file__).resolve().parents[1]
        gitignore = (backend_root / ".gitignore").read_text(encoding="utf-8")
        assert ".trust_ladder.json" in gitignore


class TestNoAutoExecutionSurface:
    """Walk the module's public surface and assert no callable named
    'execute' / 'auto_execute' / 'apply' / 'run' lives there. PR-5
    is record-only by contract."""

    async def test_no_auto_execute_function(self):
        from app.services import trust_ladder as mod

        forbidden = {
            "execute", "auto_execute", "apply", "run",
            "auto_approve", "auto_reject",
        }
        for name in dir(mod):
            if name.startswith("_"):
                continue
            assert name.lower() not in forbidden, (
                f"trust_ladder exposes forbidden callable: {name}"
            )
