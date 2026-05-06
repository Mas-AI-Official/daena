"""Sprint-18 PR-1 -- trust_policy engine contract.

Pins:
  1. TRUST_FORBIDDEN_TOOLS includes send / apply / commit and these
     NEVER graduate, even with a forged tier.
  2. TRUST_ELIGIBLE_TOOLS is exactly the three low-risk draft tools.
  3. compute_template_class is stable and discriminating (different
     domains produce different classes; same domain + same subject
     stem produces the same class).
  4. should_auto_approve refuses for non-operator initiators
     regardless of counters.
  5. should_auto_approve refuses when approvals < threshold.
  6. should_auto_approve refuses when rejections > 0 even with
     plenty of approvals.
  7. set_max_auto_tier requires is_founder=True.
  8. set_max_auto_tier requires confirmation_phrase to match.
  9. set_max_auto_tier refuses TRUST_FORBIDDEN_TOOLS.
 10. set_max_auto_tier refuses AUTO_EXECUTE_LOW_RISK_LOCAL (reserved).
 11. set_max_auto_tier refuses if rejection_count > 0 (rejections
     force NONE).
 12. should_auto_approve returns auto_approve=True ONLY when ALL
     six walls pass.
 13. .trust_policy.json is gitignored.
 14. trust_policy never auto-raises a tier on its own.
"""

from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.asyncio


# ────────────────────────────────────────────────────────────────────
# Eligibility / forbidden sets
# ────────────────────────────────────────────────────────────────────


class TestEligibilitySets:
    async def test_forbidden_tools_are_exactly_send_apply_commit(self):
        from app.services.trust_policy import TRUST_FORBIDDEN_TOOLS

        assert TRUST_FORBIDDEN_TOOLS == frozenset({
            "gmail.send_existing_draft",
            "local.file_change_proposal.apply",
            "local.git_commit_approved_patch",
        })

    async def test_eligible_tools_are_exactly_three_draft_class(self):
        from app.services.trust_policy import TRUST_ELIGIBLE_TOOLS

        assert TRUST_ELIGIBLE_TOOLS == frozenset({
            "gmail.create_draft",
            "calendar.create_tentative_event_without_invites",
            "local.file_change_proposal",
        })

    async def test_no_overlap_between_eligible_and_forbidden(self):
        from app.services.trust_policy import (
            TRUST_ELIGIBLE_TOOLS, TRUST_FORBIDDEN_TOOLS,
        )

        assert (TRUST_ELIGIBLE_TOOLS & TRUST_FORBIDDEN_TOOLS) == frozenset()


# ────────────────────────────────────────────────────────────────────
# Template class hashing
# ────────────────────────────────────────────────────────────────────


class TestTemplateClass:
    async def test_gmail_same_domain_same_subject_stem_same_class(self):
        from app.services.trust_policy import compute_template_class

        c1 = compute_template_class(
            "gmail.create_draft",
            {"to": ["alice@gmail.com"], "subject": "Cold outreach v1"},
        )
        c2 = compute_template_class(
            "gmail.create_draft",
            {"to": ["bob@gmail.com"], "subject": "Cold outreach v2"},
        )
        # Same domain + same first 4 alpha words = same class.
        assert c1 == c2

    async def test_gmail_different_domains_different_classes(self):
        from app.services.trust_policy import compute_template_class

        c1 = compute_template_class(
            "gmail.create_draft",
            {"to": ["alice@gmail.com"], "subject": "hi"},
        )
        c2 = compute_template_class(
            "gmail.create_draft",
            {"to": ["alice@example.com"], "subject": "hi"},
        )
        assert c1 != c2

    async def test_calendar_duration_buckets(self):
        from app.services.trust_policy import compute_template_class

        short = compute_template_class(
            "calendar.create_tentative_event_without_invites",
            {"calendar_id": "primary", "duration_minutes": 15},
        )
        medium = compute_template_class(
            "calendar.create_tentative_event_without_invites",
            {"calendar_id": "primary", "duration_minutes": 45},
        )
        long_ = compute_template_class(
            "calendar.create_tentative_event_without_invites",
            {"calendar_id": "primary", "duration_minutes": 120},
        )
        assert short.endswith(":short")
        assert medium.endswith(":medium")
        assert long_.endswith(":long")
        assert len({short, medium, long_}) == 3

    async def test_file_change_proposal_top_level_dir_class(self):
        from app.services.trust_policy import compute_template_class

        c1 = compute_template_class(
            "local.file_change_proposal",
            {"target_path_repo_relative": "backend/app/foo.py"},
        )
        c2 = compute_template_class(
            "local.file_change_proposal",
            {"target_path_repo_relative": "backend/app/bar.py"},
        )
        c3 = compute_template_class(
            "local.file_change_proposal",
            {"target_path_repo_relative": "frontend/src/App.tsx"},
        )
        assert c1 == c2  # same top-level dir
        assert c1 != c3  # different top-level dir

    async def test_unknown_tool_falls_back_to_default(self):
        from app.services.trust_policy import compute_template_class

        cls = compute_template_class("totally.unknown.tool", {"x": 1})
        assert cls == "totally.unknown.tool:default"

    async def test_non_dict_payload_returns_default(self):
        from app.services.trust_policy import compute_template_class

        assert compute_template_class(
            "gmail.create_draft", None,  # type: ignore[arg-type]
        ) == "gmail.create_draft:default"


# ────────────────────────────────────────────────────────────────────
# should_auto_approve walls
# ────────────────────────────────────────────────────────────────────


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    """Repoint both trust_ladder and trust_policy storage at tmp."""
    from app.services import trust_ladder, trust_policy

    monkeypatch.setattr(
        trust_ladder, "_LADDER_FILE", tmp_path / ".trust_ladder.json",
    )
    monkeypatch.setattr(
        trust_policy, "_POLICY_FILE", tmp_path / ".trust_policy.json",
    )
    yield


class TestShouldAutoApproveWalls:
    async def test_forbidden_tool_never_graduates(self, isolated_state):
        from app.services.trust_policy import (
            DispatchInitiator, should_auto_approve,
        )

        for forbidden in (
            "gmail.send_existing_draft",
            "local.file_change_proposal.apply",
            "local.git_commit_approved_patch",
        ):
            d = should_auto_approve(
                tool_id=forbidden,
                payload={"foo": "bar"},
                initiator=DispatchInitiator.OPERATOR,
            )
            assert d.auto_approve is False
            assert d.reason == "tool_forbidden_from_graduation"

    async def test_non_operator_initiator_never_graduates(self, isolated_state):
        from app.services.trust_policy import (
            DispatchInitiator, should_auto_approve, TrustTier,
            set_max_auto_tier,
        )
        from app.services import trust_ladder

        # Set up a tool that would PASS every other wall:
        # gmail.create_draft to gmail.com, founder-granted tier,
        # 5 approvals, 0 rejections.
        payload = {"to": ["alice@gmail.com"], "subject": "cold outreach v1"}
        from app.services.trust_policy import compute_template_class
        tc = compute_template_class("gmail.create_draft", payload)

        for _ in range(6):
            trust_ladder.record_decision(
                tool_id="gmail.create_draft",
                template_id=tc,
                decision="approved",
            )
        set_max_auto_tier(
            tool_id="gmail.create_draft",
            template_class=tc,
            tier=TrustTier.AUTO_APPROVE_LOW_RISK,
            requested_by_user_id="founder-id",
            is_founder=True,
            confirmation_phrase=(
                "I authorize trust tier auto_approve_low_risk for "
                "gmail.create_draft"
            ),
        )

        # Operator initiator -> graduated.
        d_op = should_auto_approve(
            tool_id="gmail.create_draft",
            payload=payload,
            initiator=DispatchInitiator.OPERATOR,
        )
        assert d_op.auto_approve is True

        # Other initiators -> still gated.
        for non_op in (
            DispatchInitiator.SCHEDULER,
            DispatchInitiator.SELF_HEALING,
            DispatchInitiator.DELEGATED,
        ):
            d = should_auto_approve(
                tool_id="gmail.create_draft",
                payload=payload,
                initiator=non_op,
            )
            assert d.auto_approve is False
            assert d.reason == "non_operator_initiator_never_graduates"

    async def test_no_history_refuses(self, isolated_state):
        from app.services.trust_policy import (
            DispatchInitiator, should_auto_approve, TrustTier,
            set_max_auto_tier, compute_template_class,
        )
        payload = {"to": ["a@gmail.com"], "subject": "hi"}
        tc = compute_template_class("gmail.create_draft", payload)
        set_max_auto_tier(
            tool_id="gmail.create_draft",
            template_class=tc,
            tier=TrustTier.AUTO_APPROVE_LOW_RISK,
            requested_by_user_id="f",
            is_founder=True,
            confirmation_phrase=(
                "I authorize trust tier auto_approve_low_risk for "
                "gmail.create_draft"
            ),
        )
        d = should_auto_approve(
            tool_id="gmail.create_draft",
            payload=payload,
            initiator=DispatchInitiator.OPERATOR,
        )
        assert d.auto_approve is False
        assert d.reason.startswith("approvals_count_0_below_threshold")

    async def test_approvals_below_threshold_refuses(self, isolated_state):
        from app.services.trust_policy import (
            DispatchInitiator, should_auto_approve, TrustTier,
            set_max_auto_tier, compute_template_class,
        )
        from app.services import trust_ladder

        payload = {"to": ["a@gmail.com"], "subject": "hi"}
        tc = compute_template_class("gmail.create_draft", payload)
        for _ in range(3):
            trust_ladder.record_decision(
                tool_id="gmail.create_draft",
                template_id=tc,
                decision="approved",
            )
        set_max_auto_tier(
            tool_id="gmail.create_draft",
            template_class=tc,
            tier=TrustTier.AUTO_APPROVE_LOW_RISK,
            requested_by_user_id="f",
            is_founder=True,
            confirmation_phrase=(
                "I authorize trust tier auto_approve_low_risk for "
                "gmail.create_draft"
            ),
        )
        d = should_auto_approve(
            tool_id="gmail.create_draft",
            payload=payload,
            initiator=DispatchInitiator.OPERATOR,
        )
        assert d.auto_approve is False
        assert "below_threshold" in d.reason

    async def test_rejection_arriving_after_tier_grant_blocks_graduation(
        self, isolated_state,
    ):
        """Founder grants tier first (counters clean). Then 5
        approvals accumulate. Then ONE rejection arrives. The
        reader-side wall must refuse even though the policy still
        carries AUTO_APPROVE_LOW_RISK -- the rejection is the
        signal of trust loss, not the tier."""
        from app.services.trust_policy import (
            DispatchInitiator, should_auto_approve, TrustTier,
            set_max_auto_tier, compute_template_class,
        )
        from app.services import trust_ladder

        payload = {"to": ["a@gmail.com"], "subject": "hi"}
        tc = compute_template_class("gmail.create_draft", payload)
        # Founder grants tier while history is clean.
        set_max_auto_tier(
            tool_id="gmail.create_draft",
            template_class=tc,
            tier=TrustTier.AUTO_APPROVE_LOW_RISK,
            requested_by_user_id="f",
            is_founder=True,
            confirmation_phrase=(
                "I authorize trust tier auto_approve_low_risk for "
                "gmail.create_draft"
            ),
        )
        for _ in range(5):
            trust_ladder.record_decision(
                tool_id="gmail.create_draft",
                template_id=tc,
                decision="approved",
            )
        # Sanity: graduated.
        d_before = should_auto_approve(
            tool_id="gmail.create_draft",
            payload=payload,
            initiator=DispatchInitiator.OPERATOR,
        )
        assert d_before.auto_approve is True

        # Rejection arrives.
        trust_ladder.record_decision(
            tool_id="gmail.create_draft",
            template_id=tc,
            decision="rejected",
        )
        # Reader-side wall refuses now even though tier is still set.
        d_after = should_auto_approve(
            tool_id="gmail.create_draft",
            payload=payload,
            initiator=DispatchInitiator.OPERATOR,
        )
        assert d_after.auto_approve is False
        assert d_after.reason == "rejections_reset_trust_to_none"
        assert d_after.rejection_count == 1

    async def test_max_tier_none_refuses(self, isolated_state):
        """Default tier is NONE; even with 100 approvals, no
        graduation."""
        from app.services.trust_policy import (
            DispatchInitiator, should_auto_approve, compute_template_class,
        )
        from app.services import trust_ladder

        payload = {"to": ["a@gmail.com"], "subject": "hi"}
        tc = compute_template_class("gmail.create_draft", payload)
        for _ in range(100):
            trust_ladder.record_decision(
                tool_id="gmail.create_draft",
                template_id=tc,
                decision="approved",
            )
        d = should_auto_approve(
            tool_id="gmail.create_draft",
            payload=payload,
            initiator=DispatchInitiator.OPERATOR,
        )
        assert d.auto_approve is False
        assert d.reason == "max_auto_tier_is_none"

    async def test_all_walls_pass_returns_true(self, isolated_state):
        from app.services.trust_policy import (
            DispatchInitiator, should_auto_approve, TrustTier,
            set_max_auto_tier, compute_template_class,
        )
        from app.services import trust_ladder

        payload = {"to": ["a@gmail.com"], "subject": "outreach launch"}
        tc = compute_template_class("gmail.create_draft", payload)
        for _ in range(5):
            trust_ladder.record_decision(
                tool_id="gmail.create_draft",
                template_id=tc,
                decision="approved",
            )
        set_max_auto_tier(
            tool_id="gmail.create_draft",
            template_class=tc,
            tier=TrustTier.AUTO_APPROVE_LOW_RISK,
            requested_by_user_id="f",
            is_founder=True,
            confirmation_phrase=(
                "I authorize trust tier auto_approve_low_risk for "
                "gmail.create_draft"
            ),
        )
        d = should_auto_approve(
            tool_id="gmail.create_draft",
            payload=payload,
            initiator=DispatchInitiator.OPERATOR,
        )
        assert d.auto_approve is True
        assert d.reason == "trust_graduated"
        assert d.template_class == tc
        assert d.approvals_count == 5
        assert d.rejection_count == 0


# ────────────────────────────────────────────────────────────────────
# set_max_auto_tier: founder-only, confirmation, reserved tiers
# ────────────────────────────────────────────────────────────────────


class TestSetTier:
    async def test_non_founder_refused(self, isolated_state):
        from app.services.trust_policy import set_max_auto_tier, TrustTier

        with pytest.raises(PermissionError):
            set_max_auto_tier(
                tool_id="gmail.create_draft",
                template_class="gmail.create_draft:default",
                tier=TrustTier.AUTO_APPROVE_LOW_RISK,
                requested_by_user_id="not-founder",
                is_founder=False,
                confirmation_phrase="anything",
            )

    async def test_confirmation_phrase_mismatch_refused(self, isolated_state):
        from app.services.trust_policy import set_max_auto_tier, TrustTier

        with pytest.raises(ValueError) as ei:
            set_max_auto_tier(
                tool_id="gmail.create_draft",
                template_class="gmail.create_draft:default",
                tier=TrustTier.AUTO_APPROVE_LOW_RISK,
                requested_by_user_id="founder",
                is_founder=True,
                confirmation_phrase="wrong phrase",
            )
        assert "confirmation_phrase_mismatch" in str(ei.value)

    async def test_forbidden_tool_refused(self, isolated_state):
        from app.services.trust_policy import (
            set_max_auto_tier, TrustTier, expected_confirmation_phrase,
        )

        with pytest.raises(ValueError) as ei:
            set_max_auto_tier(
                tool_id="gmail.send_existing_draft",
                template_class="any",
                tier=TrustTier.AUTO_APPROVE_LOW_RISK,
                requested_by_user_id="founder",
                is_founder=True,
                confirmation_phrase=expected_confirmation_phrase(
                    "gmail.send_existing_draft",
                    TrustTier.AUTO_APPROVE_LOW_RISK,
                ),
            )
        assert "tool_forbidden_from_graduation" in str(ei.value)

    async def test_reserved_tier_refused(self, isolated_state):
        from app.services.trust_policy import (
            set_max_auto_tier, TrustTier, expected_confirmation_phrase,
        )

        with pytest.raises(ValueError) as ei:
            set_max_auto_tier(
                tool_id="gmail.create_draft",
                template_class="any",
                tier=TrustTier.AUTO_EXECUTE_LOW_RISK_LOCAL,
                requested_by_user_id="founder",
                is_founder=True,
                confirmation_phrase=expected_confirmation_phrase(
                    "gmail.create_draft",
                    TrustTier.AUTO_EXECUTE_LOW_RISK_LOCAL,
                ),
            )
        assert "tier_reserved_unreachable_in_sprint18" in str(ei.value)

    async def test_rejections_force_none(self, isolated_state):
        """If trust_ladder shows any rejection, raising the tier
        above NONE refuses."""
        from app.services.trust_policy import (
            set_max_auto_tier, TrustTier, expected_confirmation_phrase,
            compute_template_class,
        )
        from app.services import trust_ladder

        payload = {"to": ["a@gmail.com"], "subject": "x"}
        tc = compute_template_class("gmail.create_draft", payload)
        trust_ladder.record_decision(
            tool_id="gmail.create_draft",
            template_id=tc,
            decision="rejected",
        )
        with pytest.raises(ValueError) as ei:
            set_max_auto_tier(
                tool_id="gmail.create_draft",
                template_class=tc,
                tier=TrustTier.AUTO_APPROVE_LOW_RISK,
                requested_by_user_id="founder",
                is_founder=True,
                confirmation_phrase=expected_confirmation_phrase(
                    "gmail.create_draft",
                    TrustTier.AUTO_APPROVE_LOW_RISK,
                ),
            )
        assert "rejections_force_tier_none" in str(ei.value)

    async def test_can_lower_to_none_even_with_rejections(self, isolated_state):
        from app.services.trust_policy import (
            set_max_auto_tier, TrustTier, expected_confirmation_phrase,
        )
        from app.services import trust_ladder

        trust_ladder.record_decision(
            tool_id="gmail.create_draft",
            template_id="x",
            decision="rejected",
        )
        # Allowed -- lowering is always safe.
        entry = set_max_auto_tier(
            tool_id="gmail.create_draft",
            template_class="x",
            tier=TrustTier.NONE,
            requested_by_user_id="founder",
            is_founder=True,
            confirmation_phrase=expected_confirmation_phrase(
                "gmail.create_draft", TrustTier.NONE,
            ),
        )
        assert entry.max_auto_tier == TrustTier.NONE


# ────────────────────────────────────────────────────────────────────
# Surface guarantees
# ────────────────────────────────────────────────────────────────────


class TestNoAutoEscalation:
    async def test_module_has_no_auto_escalate_callable(self):
        """Trust policy is record + decision-only. It NEVER raises a
        tier on its own. Walk public surface and refuse any callable
        named 'auto_escalate' / 'self_grant' / 'auto_grant'."""
        from app.services import trust_policy as mod

        forbidden = {
            "auto_escalate", "self_grant", "auto_grant",
            "self_promote", "promote",
        }
        for name in dir(mod):
            if name.startswith("_"):
                continue
            assert name.lower() not in forbidden, (
                f"trust_policy exposes forbidden callable: {name}"
            )

    async def test_default_get_policy_returns_none_tier(self, isolated_state):
        from app.services.trust_policy import get_policy, TrustTier

        e = get_policy(
            tool_id="gmail.create_draft",
            template_class="never-set-before",
        )
        assert e.max_auto_tier == TrustTier.NONE


class TestGitignored:
    async def test_persistence_file_in_gitignore(self):
        backend_root = Path(__file__).resolve().parents[1]
        gitignore = (backend_root / ".gitignore").read_text(encoding="utf-8")
        assert ".trust_policy.json" in gitignore
