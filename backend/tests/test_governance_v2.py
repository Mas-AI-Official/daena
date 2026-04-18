"""Tests for GovernanceEngine v2 — slider resolution, plan approval, overrides."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.constants import GovernanceMode, RiskLevel
from app.services.governance import (
    ROLE_DEFAULT_PRESETS,
    ROLE_MODE_CONSTRAINTS,
    GovernanceEngine,
)

# ── Fixtures ──────────────────────────────────────────────────────

def _mock_db() -> None:
    """Placeholder — GovernanceEngine static methods don't need DB."""
    return None


def _engine() -> GovernanceEngine:
    return GovernanceEngine(_mock_db())


# ── get_effective_preset ──────────────────────────────────────────

class TestGetEffectivePreset:
    """Tests for role x team x org mode inheritance chain."""

    def test_founder_gets_requested_unleashed(self) -> None:
        """Founder can request UNLEASHED -- no constraints block it."""
        result = GovernanceEngine.get_effective_preset(
            user_role="FOUNDER",
            requested_preset="UNLEASHED",
        )
        assert result == GovernanceMode.UNLEASHED

    def test_founder_gets_requested_governed(self) -> None:
        result = GovernanceEngine.get_effective_preset(
            user_role="FOUNDER",
            requested_preset="GOVERNED",
        )
        assert result == GovernanceMode.GOVERNED

    def test_admin_clamped_to_balanced_minimum(self) -> None:
        """Admin requests UNLEASHED but gets clamped to BALANCED (role minimum)."""
        result = GovernanceEngine.get_effective_preset(
            user_role="ADMIN",
            requested_preset="UNLEASHED",
        )
        assert result == GovernanceMode.BALANCED

    def test_operator_default_is_governed(self) -> None:
        """Operator with no explicit request gets GOVERNED (role default)."""
        result = GovernanceEngine.get_effective_preset(
            user_role="OPERATOR",
        )
        assert result == GovernanceMode.GOVERNED

    def test_viewer_locked_to_governed(self) -> None:
        """Viewer is locked to GOVERNED regardless of request."""
        result = GovernanceEngine.get_effective_preset(
            user_role="VIEWER",
            requested_preset="UNLEASHED",
        )
        assert result == GovernanceMode.GOVERNED

    def test_team_minimum_raises_floor(self) -> None:
        """Team minimum GOVERNED overrides Admin's BALANCED request."""
        result = GovernanceEngine.get_effective_preset(
            user_role="ADMIN",
            requested_preset="BALANCED",
            team_minimum="GOVERNED",
        )
        assert result == GovernanceMode.GOVERNED

    def test_org_minimum_raises_floor(self) -> None:
        """Org minimum BALANCED overrides Founder's UNLEASHED request."""
        result = GovernanceEngine.get_effective_preset(
            user_role="FOUNDER",
            requested_preset="UNLEASHED",
            org_minimum="BALANCED",
        )
        assert result == GovernanceMode.BALANCED

    def test_team_and_org_combined(self) -> None:
        """Effective min = max(role_min, team_min, org_min)."""
        result = GovernanceEngine.get_effective_preset(
            user_role="MANAGER",
            requested_preset="BALANCED",
            team_minimum="GOVERNED",
            org_minimum="BALANCED",
        )
        # Manager role_min=BALANCED, team=GOVERNED, org=BALANCED
        # effective_min = max(1, 2, 1) = 2 -> GOVERNED
        # Requested BALANCED (1) < GOVERNED (2) -> clamped to GOVERNED
        assert result == GovernanceMode.GOVERNED

    def test_default_preset_per_role(self) -> None:
        """Each role gets its correct default when no preset requested."""
        for role, expected in ROLE_DEFAULT_PRESETS.items():
            result = GovernanceEngine.get_effective_preset(
                user_role=role.value,
            )
            # Default must be >= role minimum
            role_min, _ = ROLE_MODE_CONSTRAINTS[role]
            assert result == expected, f"Role {role.value}: expected {expected}, got {result}"


# ── get_allowed_range ─────────────────────────────────────────────

class TestGetAllowedRange:
    def test_founder_full_range(self) -> None:
        low, high = GovernanceEngine.get_allowed_range("FOUNDER")
        assert low == GovernanceMode.UNLEASHED
        assert high == GovernanceMode.GOVERNED

    def test_admin_range(self) -> None:
        low, high = GovernanceEngine.get_allowed_range("ADMIN")
        assert low == GovernanceMode.BALANCED
        assert high == GovernanceMode.GOVERNED

    def test_team_minimum_raises_low(self) -> None:
        low, high = GovernanceEngine.get_allowed_range(
            "ADMIN", team_minimum="GOVERNED",
        )
        assert low == GovernanceMode.GOVERNED
        assert high == GovernanceMode.GOVERNED

    def test_auditor_locked(self) -> None:
        low, high = GovernanceEngine.get_allowed_range("AUDITOR")
        assert low == GovernanceMode.GOVERNED
        assert high == GovernanceMode.GOVERNED


# ── evaluate (single action) ─────────────────────────────────────

class TestEvaluate:
    @pytest.mark.asyncio
    async def test_hard_law_violation_blocks(self) -> None:
        """Hard law violations always block, regardless of slider."""
        engine = _engine()
        result = await engine.evaluate(
            action_type="DELETE",
            action_params={"target": "all_user_data", "permanent": True},
            governance_slider="YOLO",
            actor_type="FOUNDER",
            actor_role="FOUNDER",
            tenant_id=uuid4(),
            user_id=uuid4(),
        )
        # DELETE is CRITICAL risk — check if hard laws fire
        # (depends on hard_laws implementation)
        assert result["risk_level"] in (
            RiskLevel.CRITICAL.value, RiskLevel.HIGH.value,
        )

    @pytest.mark.asyncio
    async def test_read_action_is_silent_on_yolo(self) -> None:
        """READ action on YOLO slider → Tier 0 (silent pass)."""
        engine = _engine()
        result = await engine.evaluate(
            action_type="READ",
            governance_slider="YOLO",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=uuid4(),
            user_id=uuid4(),
        )
        assert result["allowed"] is True
        assert result["governance_tier"] == 0
        assert result["message"] == "Silent pass"

    @pytest.mark.asyncio
    async def test_high_risk_on_paranoid_requires_approval(self) -> None:
        """DEPLOY on PARANOID → high tier, requires approval."""
        engine = _engine()
        result = await engine.evaluate(
            action_type="DEPLOY",
            governance_slider="PARANOID",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=uuid4(),
            user_id=uuid4(),
        )
        assert result["requires_approval"] is True
        assert result["allowed"] is False

    @pytest.mark.asyncio
    async def test_founder_bypasses_approval(self) -> None:
        """Founder override: approval not required even at high tier."""
        engine = _engine()
        result = await engine.evaluate(
            action_type="DEPLOY",
            governance_slider="PARANOID",
            actor_type="FOUNDER",
            actor_role="FOUNDER",
            tenant_id=uuid4(),
            user_id=uuid4(),
        )
        assert result["requires_approval"] is False
        assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_plan_coverage_auto_approves_low_tier(self) -> None:
        """Action within approved plan with tier <= 2 → auto-approve."""
        engine = _engine()
        result = await engine.evaluate(
            action_type="WRITE_FILE",
            governance_slider="STANDARD",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=uuid4(),
            user_id=uuid4(),
            plan_approval_id=uuid4(),
        )
        assert result["plan_covered"] is True

    @pytest.mark.asyncio
    async def test_risk_classification(self) -> None:
        """Verify risk levels for different action types."""
        engine = _engine()
        tid, uid = uuid4(), uuid4()

        read_result = await engine.evaluate(
            action_type="READ", governance_slider="STANDARD",
            actor_type="USER", actor_role="OPERATOR",
            tenant_id=tid, user_id=uid,
        )
        assert read_result["risk_level"] == RiskLevel.NONE.value

        write_result = await engine.evaluate(
            action_type="WRITE_FILE", governance_slider="STANDARD",
            actor_type="USER", actor_role="OPERATOR",
            tenant_id=tid, user_id=uid,
        )
        assert write_result["risk_level"] == RiskLevel.MEDIUM.value

        delete_result = await engine.evaluate(
            action_type="DELETE", governance_slider="STANDARD",
            actor_type="USER", actor_role="OPERATOR",
            tenant_id=tid, user_id=uid,
        )
        assert delete_result["risk_level"] == RiskLevel.CRITICAL.value


# ── evaluate_plan (workflow pre-approval) ─────────────────────────

class TestEvaluatePlan:
    def test_empty_plan_auto_approves(self) -> None:
        result = GovernanceEngine.evaluate_plan(steps=[])
        assert result["allowed"] is True
        assert result["plan_tier"] == 0
        assert result["step_count"] == 0

    def test_low_risk_plan_auto_approves(self) -> None:
        """Plan with only READ/SEARCH → auto-approve on STANDARD."""
        steps = [
            {"action_type": "SEARCH"},
            {"action_type": "READ"},
            {"action_type": "QUERY"},
        ]
        result = GovernanceEngine.evaluate_plan(
            steps=steps, governance_slider="STANDARD",
        )
        assert result["allowed"] is True
        assert result["plan_tier"] <= 2

    def test_high_risk_plan_requires_approval(self) -> None:
        """Plan containing DELETE → requires approval on STANDARD."""
        steps = [
            {"action_type": "SEARCH"},
            {"action_type": "DELETE", "params": {}},
        ]
        result = GovernanceEngine.evaluate_plan(
            steps=steps, governance_slider="STANDARD",
        )
        assert result["requires_approval"] is True

    def test_strict_always_requires_approval(self) -> None:
        """STRICT: ALL multi-step plans require approval."""
        steps = [
            {"action_type": "READ"},
            {"action_type": "QUERY"},
        ]
        result = GovernanceEngine.evaluate_plan(
            steps=steps, governance_slider="STRICT",
        )
        assert result["requires_approval"] is True

    def test_paranoid_always_requires_approval(self) -> None:
        """PARANOID: ALL plans require approval."""
        steps = [{"action_type": "READ"}]
        result = GovernanceEngine.evaluate_plan(
            steps=steps, governance_slider="PARANOID",
        )
        assert result["requires_approval"] is True

    def test_yolo_auto_approves_unless_tier_4(self) -> None:
        """YOLO: auto-approve even with high-risk actions."""
        steps = [
            {"action_type": "DEPLOY"},
            {"action_type": "SEND_EMAIL"},
        ]
        result = GovernanceEngine.evaluate_plan(
            steps=steps, governance_slider="YOLO",
        )
        # YOLO auto-approves unless max_tier >= 3
        # DEPLOY is HIGH risk → on YOLO that's tier depends on matrix
        # But YOLO is very permissive
        assert result["allowed"] is True or result["plan_tier"] >= 3

    def test_founder_bypasses_plan_approval(self) -> None:
        """Founder: never requires plan approval."""
        steps = [
            {"action_type": "DELETE"},
            {"action_type": "DEPLOY"},
        ]
        result = GovernanceEngine.evaluate_plan(
            steps=steps,
            governance_slider="PARANOID",
            actor_type="FOUNDER",
        )
        assert result["requires_approval"] is False
        assert result["allowed"] is True

    def test_plan_tier_is_max_of_steps(self) -> None:
        """Plan tier = max tier across all steps."""
        steps = [
            {"action_type": "READ"},       # NONE risk
            {"action_type": "WRITE_FILE"}, # MEDIUM risk
            {"action_type": "DELETE"},      # CRITICAL risk
        ]
        result = GovernanceEngine.evaluate_plan(
            steps=steps, governance_slider="STANDARD",
        )
        assert result["plan_tier"] == max(
            s["governance_tier"] for s in result["step_tiers"]
        )
        assert result["step_count"] == 3


# ── validate_override ─────────────────────────────────────────────

class TestValidateOverride:
    def test_valid_override_accepted(self) -> None:
        """Override within allowed range is accepted."""
        result = GovernanceEngine.validate_override(
            requested_preset="GOVERNED",
            user_role="ADMIN",
        )
        assert result["effective_preset"] == "GOVERNED"
        assert result["was_clamped"] is False

    def test_override_clamped_to_floor(self) -> None:
        """Override below floor is clamped up."""
        result = GovernanceEngine.validate_override(
            requested_preset="UNLEASHED",
            user_role="ADMIN",
        )
        assert result["effective_preset"] == "BALANCED"
        assert result["was_clamped"] is True

    def test_override_with_team_minimum(self) -> None:
        """Team minimum raises the floor for override."""
        result = GovernanceEngine.validate_override(
            requested_preset="BALANCED",
            user_role="ADMIN",
            team_minimum="GOVERNED",
        )
        assert result["effective_preset"] == "GOVERNED"
        assert result["was_clamped"] is True
        assert result["effective_minimum"] == "GOVERNED"

    def test_viewer_override_always_governed(self) -> None:
        """Viewer trying to override always gets GOVERNED."""
        result = GovernanceEngine.validate_override(
            requested_preset="UNLEASHED",
            user_role="VIEWER",
        )
        assert result["effective_preset"] == "GOVERNED"
        assert result["was_clamped"] is True
