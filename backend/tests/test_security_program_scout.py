"""Sprint-13 PR-5 -- authorized security program scout contract.

Pins:
  1. _security_bounty_overlay returns the locked overlay shape with
     program_name / allowed_domains / out_of_scope_rules /
     reward_range / report_url / identity_required /
     safe_next_action / scope_check_status.
  2. NO scan / exploit / test_target field ever appears in the
     overlay.
  3. scope_check_status is always "not_yet_in_scope" by default.
  4. safe_next_action contains the literal "register" + "manually"
     guard text -- the UI may render this verbatim.
"""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.asyncio


_REQUIRED_KEYS = {
    "program_name",
    "allowed_domains",
    "out_of_scope_rules",
    "reward_range",
    "report_url",
    "identity_required",
    "safe_next_action",
    "scope_check_status",
}

_FORBIDDEN_KEY_PREFIXES = ("scan", "exploit", "test_target", "auto_test")


class TestOverlayShape:
    async def test_keys_locked(self):
        from app.services.research_flow import _security_bounty_overlay

        overlay = _security_bounty_overlay(
            "* Bounty: $500 - $5000 USD\n* Out of scope: physical security\n"
            "Submit reports at https://hackerone.com/example/reports"
        )
        actual = set(overlay.keys())
        missing = _REQUIRED_KEYS - actual
        assert not missing, f"missing overlay keys: {sorted(missing)}"

    async def test_no_scan_or_exploit_field(self):
        from app.services.research_flow import _security_bounty_overlay

        overlay = _security_bounty_overlay("anything")
        for key in overlay.keys():
            lowered = key.lower()
            for forbidden in _FORBIDDEN_KEY_PREFIXES:
                assert not lowered.startswith(forbidden), (
                    f"security bounty overlay leaked forbidden field: {key}"
                )

    async def test_scope_check_status_default(self):
        from app.services.research_flow import _security_bounty_overlay

        overlay = _security_bounty_overlay("anything")
        assert overlay["scope_check_status"] == "not_yet_in_scope"

    async def test_safe_next_action_has_register_manually_guard(self):
        from app.services.research_flow import _security_bounty_overlay

        overlay = _security_bounty_overlay("")
        text = (overlay["safe_next_action"] or "").lower()
        assert "register" in text
        assert "manually" in text
        assert "scan" in text and "refuse" in text

    async def test_identity_required_detected(self):
        from app.services.research_flow import _security_bounty_overlay

        overlay = _security_bounty_overlay(
            "Submit via HackerOne; must be a member of the program."
        )
        assert overlay["identity_required"] is True

    async def test_report_url_extracted_when_present(self):
        from app.services.research_flow import _security_bounty_overlay

        overlay = _security_bounty_overlay(
            "Report at https://example.com/security/report-an-issue"
        )
        assert overlay["report_url"] is not None
        assert "report" in overlay["report_url"].lower()


class TestPayloadIntegration:
    async def test_security_bounty_payload_carries_overlay(self, monkeypatch):
        """When kind=business_opportunity + opportunity_type=security_bounty,
        the structured_payload built by create_research_draft should
        contain the overlay keys merged in."""
        from app.services import research_flow as rf

        fake_text = "Bounty: $1000\nReport at https://example.com/report"

        class FakeOutcome:
            success = True
            result = fake_text
            error = None

        async def fake_extract(url, goal, max_chars):
            return FakeOutcome()

        monkeypatch.setattr(rf, "extract_from_url", fake_extract)

        # Use a fake DB + fake user that won't run the actual write.
        # We exercise the function up to the model build; an
        # AttributeError on db.add is acceptable since we only care
        # that the payload assembly path succeeds before that.
        import uuid

        class FakeDB:
            def add(self, obj):
                # Capture the constructed model so we can inspect it.
                FakeDB.captured = obj

            async def flush(self):
                pass

            async def refresh(self, obj):
                pass

        db = FakeDB()
        try:
            await rf.create_research_draft(
                db=db,
                kind="business_opportunity",
                url="https://example.com/policy",
                goal="extract bounty program details",
                user_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                opportunity_type="security_bounty",
            )
        except Exception:
            # The fake DB doesn't implement the full session
            # contract; we only need the model to have been
            # constructed with structured_payload populated.
            pass

        captured = getattr(FakeDB, "captured", None)
        assert captured is not None, (
            "create_research_draft did not reach the model construction path"
        )
        sp = getattr(captured, "structured_payload", {}) or {}
        assert sp.get("opportunity_type") == "security_bounty"
        assert sp.get("scope_check_status") == "not_yet_in_scope"
        # The overlay text always carries the manual-register guard.
        action = (sp.get("safe_next_action") or "").lower()
        assert "register" in action and "manually" in action
