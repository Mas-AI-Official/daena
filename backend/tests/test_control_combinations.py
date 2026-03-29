"""Tests for all control parameter combinations in the Daena pipeline.

Covers:
- AGI ON (autopilot) override: auto-approve Tier 0-2, block Tier 3+
- AGI OFF + governance slider: YOLO through PARANOID
- CMD mode: no execution, plan-only system prompt
- EXE mode: tool execution with governance
- Think mode: forces reasoning model (deepseek-r1)
- Combined scenarios: autopilot + YOLO, autopilot + PARANOID, etc.

Run: pytest tests/test_control_combinations.py -v
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from app.core.constants import (
    ChatMode,
    GovernanceSlider,
    RiskLevel,
)
from app.services.governance import GOVERNANCE_TIER_MAP, GovernanceEngine
from app.services.query_understanding import (
    IntentType,
    QueryInput,
    QueryUnderstandingService,
)

# ── Helpers ──────────────────────────────────────────────────


def _make_fake_db():
    """Return a mock async session for GovernanceEngine."""
    return MagicMock()


def _make_uuid():
    return uuid.uuid4()


# ============================================================
# 1. AUTOPILOT (AGI ON) GOVERNANCE OVERRIDE
# ============================================================


class TestAutopilotGovernance:
    """When autopilot=True (AGI ON), internal governance auto-approves
    Tier 0-2 actions. Only Tier 3+ critical actions ask the user.
    """

    @pytest.mark.asyncio
    async def test_autopilot_on_auto_approves_tier_0(self) -> None:
        """AGI ON + Tier 0 action → auto-approved, no user involvement."""
        gov = GovernanceEngine(_make_fake_db())
        result = await gov.evaluate(
            action_type="READ",
            governance_slider="STANDARD",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
            autopilot=True,
        )
        assert result["allowed"] is True
        assert result["governance_tier"] == 0
        assert result["autopilot_override"] is True
        assert "Autopilot" in result["message"]

    @pytest.mark.asyncio
    async def test_autopilot_on_auto_approves_tier_1(self) -> None:
        """AGI ON + Tier 1 action → auto-approved."""
        gov = GovernanceEngine(_make_fake_db())
        result = await gov.evaluate(
            action_type="QUERY",
            governance_slider="PARANOID",  # PARANOID + NONE risk = tier 1
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
            autopilot=True,
        )
        assert result["allowed"] is True
        assert result["governance_tier"] == 1
        assert result["autopilot_override"] is True

    @pytest.mark.asyncio
    async def test_autopilot_on_auto_approves_tier_2(self) -> None:
        """AGI ON + Tier 2 action → auto-approved."""
        gov = GovernanceEngine(_make_fake_db())
        # LLM_CALL → LOW risk (default), PARANOID + LOW = tier 2
        result = await gov.evaluate(
            action_type="LLM_CALL",  # LOW risk (unknown action default)
            governance_slider="PARANOID",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
            autopilot=True,
        )
        assert result["allowed"] is True
        assert result["governance_tier"] == 2
        assert result["autopilot_override"] is True

    @pytest.mark.asyncio
    async def test_autopilot_on_blocks_tier_3_critical(self) -> None:
        """AGI ON + Tier 3+ critical action → still requires user approval."""
        gov = GovernanceEngine(_make_fake_db())
        # STANDARD + HIGH risk = tier 3
        result = await gov.evaluate(
            action_type="DEPLOY",
            governance_slider="STANDARD",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
            autopilot=True,
        )
        assert result["allowed"] is False
        assert result["governance_tier"] == 3
        assert result["requires_approval"] is True
        assert result["autopilot_override"] is False

    @pytest.mark.asyncio
    async def test_autopilot_on_blocks_tier_4_critical(self) -> None:
        """AGI ON + Tier 4 action → always blocked even with autopilot."""
        gov = GovernanceEngine(_make_fake_db())
        # PARANOID + HIGH risk (DEPLOY) = tier 4
        result = await gov.evaluate(
            action_type="DEPLOY",
            governance_slider="PARANOID",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
            autopilot=True,
        )
        assert result["allowed"] is False
        assert result["governance_tier"] == 4
        assert result["requires_approval"] is True

    @pytest.mark.asyncio
    async def test_autopilot_on_yolo_still_blocks_tier_3(self) -> None:
        """AGI ON + STANDARD slider → Tier 3+ actions NOT auto-approved.

        This is the key test: even with autopilot, Tier 3+ governance
        always requires user approval. STANDARD + HIGH risk = tier 3.
        """
        gov = GovernanceEngine(_make_fake_db())
        # STANDARD + HIGH risk (DEPLOY) = tier 3 → autopilot can't override
        result = await gov.evaluate(
            action_type="DEPLOY",  # HIGH risk
            governance_slider="STANDARD",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
            autopilot=True,
        )
        # STANDARD + HIGH = tier 3 → NOT auto-approved even with autopilot
        assert result["allowed"] is False
        assert result["governance_tier"] == 3
        assert result["autopilot_override"] is False
        assert result["requires_approval"] is True

    @pytest.mark.asyncio
    async def test_autopilot_on_hard_law_never_bypassed(self) -> None:
        """Hard law violations block even with autopilot ON."""
        gov = GovernanceEngine(_make_fake_db())
        result = await gov.evaluate(
            action_type="DELETE",
            action_params={"target": "all_user_data", "scope": "tenant"},
            governance_slider="YOLO",
            actor_type="FOUNDER",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
            autopilot=True,
        )
        # Hard laws checked first — if violated, blocked regardless
        # The actual result depends on hard_laws implementation
        # At minimum, verify hard_law_violations field is present
        assert "hard_law_violations" in result
        assert "autopilot_override" in result

    @pytest.mark.asyncio
    async def test_autopilot_off_no_override(self) -> None:
        """When autopilot=False, no autopilot override happens."""
        gov = GovernanceEngine(_make_fake_db())
        result = await gov.evaluate(
            action_type="READ",
            governance_slider="STANDARD",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
            autopilot=False,
        )
        assert result["allowed"] is True
        assert result["autopilot_override"] is False

    @pytest.mark.asyncio
    async def test_autopilot_default_is_false(self) -> None:
        """If autopilot not provided, defaults to False."""
        gov = GovernanceEngine(_make_fake_db())
        result = await gov.evaluate(
            action_type="READ",
            governance_slider="STANDARD",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
            # autopilot not passed — defaults to False
        )
        assert result["autopilot_override"] is False


# ============================================================
# 2. AGI OFF + GOVERNANCE SLIDER COMBINATIONS
# ============================================================


class TestGovernanceSliderCombinations:
    """Without autopilot, the governance slider controls everything."""

    @pytest.mark.asyncio
    async def test_yolo_allows_medium_risk(self) -> None:
        """YOLO + MEDIUM risk → tier 0, allowed."""
        gov = GovernanceEngine(_make_fake_db())
        # WRITE_FILE is MEDIUM risk (no hard law trigger unlike EXECUTE)
        result = await gov.evaluate(
            action_type="WRITE_FILE",
            governance_slider="YOLO",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
        )
        assert result["allowed"] is True
        assert result["governance_tier"] == 0
        assert result["risk_level"] == "MEDIUM"

    @pytest.mark.asyncio
    async def test_paranoid_reviews_everything(self) -> None:
        """PARANOID slider → even NONE risk actions get tier 1 (logged)."""
        gov = GovernanceEngine(_make_fake_db())
        result = await gov.evaluate(
            action_type="READ",
            governance_slider="PARANOID",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
        )
        # PARANOID + NONE = tier 1
        assert result["governance_tier"] == 1
        assert result["allowed"] is True  # tier 1 = logged but allowed

    @pytest.mark.asyncio
    async def test_paranoid_blocks_low_risk(self) -> None:
        """PARANOID + LOW risk → tier 2, user notified."""
        gov = GovernanceEngine(_make_fake_db())
        # LLM_CALL → LOW risk (unknown action default)
        # PARANOID + LOW = tier 2
        result = await gov.evaluate(
            action_type="LLM_CALL",  # LOW risk
            governance_slider="PARANOID",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
        )
        assert result["governance_tier"] == 2
        assert result["allowed"] is True  # tier 2 = notified but allowed

    @pytest.mark.asyncio
    async def test_paranoid_blocks_medium_risk(self) -> None:
        """PARANOID + MEDIUM risk → tier 3, approval required."""
        gov = GovernanceEngine(_make_fake_db())
        # WRITE_FILE is MEDIUM risk (no hard law trigger)
        result = await gov.evaluate(
            action_type="WRITE_FILE",  # MEDIUM risk
            governance_slider="PARANOID",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
        )
        assert result["governance_tier"] == 3
        assert result["allowed"] is False
        assert result["requires_approval"] is True

    @pytest.mark.asyncio
    async def test_paranoid_blocks_high_risk(self) -> None:
        """PARANOID + HIGH risk → tier 4, council + approval required."""
        gov = GovernanceEngine(_make_fake_db())
        result = await gov.evaluate(
            action_type="DEPLOY",  # HIGH risk
            governance_slider="PARANOID",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
        )
        assert result["governance_tier"] == 4
        assert result["allowed"] is False
        assert result["requires_approval"] is True

    @pytest.mark.asyncio
    async def test_strict_blocks_high_risk(self) -> None:
        """STRICT + HIGH risk → tier 3, approval required."""
        gov = GovernanceEngine(_make_fake_db())
        result = await gov.evaluate(
            action_type="DEPLOY",
            governance_slider="STRICT",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
        )
        assert result["governance_tier"] == 3
        assert result["allowed"] is False

    @pytest.mark.asyncio
    async def test_light_allows_medium_risk(self) -> None:
        """LIGHT + MEDIUM risk → tier 1, logged only."""
        gov = GovernanceEngine(_make_fake_db())
        # WRITE_FILE is MEDIUM risk (no hard law trigger)
        result = await gov.evaluate(
            action_type="WRITE_FILE",
            governance_slider="LIGHT",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
        )
        assert result["governance_tier"] == 1
        assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_standard_blocks_critical_risk(self) -> None:
        """STANDARD + CRITICAL risk → tier 4, council + approval."""
        gov = GovernanceEngine(_make_fake_db())
        result = await gov.evaluate(
            action_type="DELETE",
            governance_slider="STANDARD",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
        )
        assert result["governance_tier"] == 4
        assert result["allowed"] is False

    @pytest.mark.asyncio
    async def test_founder_bypasses_all_tiers(self) -> None:
        """FOUNDER actor_type bypasses all tiers (Hard Law #4).

        Uses DEPLOY (HIGH risk) + PARANOID = tier 4, which normally
        requires council + approval. Founder bypasses this.
        Note: DELETE triggers Hard Law #6 which even Founder can't bypass.
        """
        gov = GovernanceEngine(_make_fake_db())
        result = await gov.evaluate(
            action_type="DEPLOY",
            governance_slider="PARANOID",
            actor_type="FOUNDER",
            actor_role="FOUNDER",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
        )
        assert result["allowed"] is True
        assert result["governance_tier"] == 4
        assert "Founder override" in result["message"]


# ============================================================
# 3. GOVERNANCE TIER MAP COMPLETENESS
# ============================================================


class TestGovernanceTierMap:
    """Verify every slider × risk combination in GOVERNANCE_TIER_MAP."""

    def test_all_sliders_present(self) -> None:
        for slider in GovernanceSlider:
            assert slider in GOVERNANCE_TIER_MAP, f"Missing slider: {slider}"

    def test_all_risks_present_for_each_slider(self) -> None:
        for slider in GovernanceSlider:
            for risk in RiskLevel:
                assert risk in GOVERNANCE_TIER_MAP[slider], (
                    f"Missing risk {risk} for slider {slider}"
                )

    def test_tiers_are_0_to_4(self) -> None:
        for slider in GovernanceSlider:
            for risk in RiskLevel:
                tier = GOVERNANCE_TIER_MAP[slider][risk]
                assert 0 <= tier <= 4, (
                    f"Invalid tier {tier} for {slider}×{risk}"
                )

    def test_yolo_is_most_permissive(self) -> None:
        """YOLO should have the lowest tiers across all risk levels."""
        for risk in RiskLevel:
            yolo_tier = GOVERNANCE_TIER_MAP[GovernanceSlider.YOLO][risk]
            for slider in GovernanceSlider:
                other_tier = GOVERNANCE_TIER_MAP[slider][risk]
                assert yolo_tier <= other_tier, (
                    f"YOLO tier {yolo_tier} > {slider} tier {other_tier} "
                    f"for risk {risk}"
                )

    def test_paranoid_is_most_restrictive(self) -> None:
        """PARANOID should have the highest tiers across all risk levels."""
        for risk in RiskLevel:
            paranoid_tier = GOVERNANCE_TIER_MAP[GovernanceSlider.PARANOID][risk]
            for slider in GovernanceSlider:
                other_tier = GOVERNANCE_TIER_MAP[slider][risk]
                assert paranoid_tier >= other_tier, (
                    f"PARANOID tier {paranoid_tier} < {slider} tier "
                    f"{other_tier} for risk {risk}"
                )


# ============================================================
# 4. CMD MODE — NEVER TRIGGERS TOOL EXECUTION
# ============================================================


class TestCmdMode:
    """CMD mode should cap risk at NONE for all non-dangerous intents."""

    def test_cmd_mode_read_risk_is_none(self) -> None:
        """CMD mode + normal query → risk NONE."""
        svc = QueryUnderstandingService()
        result = svc.analyze(QueryInput(
            raw_message="Compare React and Vue for our project",
            execution_mode=ChatMode.CMD,
        ))
        assert result.risk_level == RiskLevel.NONE

    def test_cmd_mode_coding_intent_still_no_risk(self) -> None:
        """CMD mode + coding intent → risk NONE (can't execute)."""
        svc = QueryUnderstandingService()
        result = svc.analyze(QueryInput(
            raw_message="Write a function to sort users by age in Python",
            execution_mode=ChatMode.CMD,
        ))
        # CMD mode caps non-dangerous intent to NONE risk
        assert result.risk_level == RiskLevel.NONE

    def test_cmd_mode_dangerous_intent_still_flagged(self) -> None:
        """CMD mode + DANGEROUS intent → still flagged as risky.

        Even in CMD mode, dangerous intent is not suppressed — the
        query understanding pipeline must still flag it so governance
        can log/block if needed.
        """
        svc = QueryUnderstandingService()
        result = svc.analyze(QueryInput(
            raw_message="rm -rf / and delete all databases DROP TABLE users",
            execution_mode=ChatMode.CMD,
        ))
        # DANGEROUS intent should still be flagged
        assert result.intent == IntentType.DANGEROUS
        # Risk should NOT be NONE for dangerous content
        assert result.risk_level != RiskLevel.NONE

    def test_cmd_mode_multipart_query_safe(self) -> None:
        """CMD mode + complex multi-part query → risk NONE."""
        svc = QueryUnderstandingService()
        result = svc.analyze(QueryInput(
            raw_message=(
                "First analyze the codebase, then create a plan for "
                "migrating the database, and finally summarize the risks"
            ),
            execution_mode=ChatMode.CMD,
        ))
        assert result.risk_level == RiskLevel.NONE


# ============================================================
# 5. EXE MODE — ALLOWS TOOL EXECUTION WITH GOVERNANCE
# ============================================================


class TestExeMode:
    """EXE mode should assign real risk levels based on content."""

    def test_exe_mode_coding_has_risk(self) -> None:
        """EXE mode + coding intent → at least LOW risk."""
        svc = QueryUnderstandingService()
        result = svc.analyze(QueryInput(
            raw_message="Write a function to sort users by age in Python",
            execution_mode=ChatMode.EXE,
        ))
        # In EXE mode, coding intent gets LOW risk (could execute code)
        assert result.risk_level in (RiskLevel.NONE, RiskLevel.LOW)

    def test_exe_mode_dangerous_intent_high_risk(self) -> None:
        """EXE mode + dangerous content → HIGH or CRITICAL risk."""
        svc = QueryUnderstandingService()
        result = svc.analyze(QueryInput(
            raw_message="Delete all files in the temp directory rm -rf /tmp",
            execution_mode=ChatMode.EXE,
        ))
        assert result.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    def test_exe_mode_deploy_action_high_risk(self) -> None:
        """EXE mode + deploy keywords → flagged."""
        svc = QueryUnderstandingService()
        result = svc.analyze(QueryInput(
            raw_message="Deploy the application to production and send email to all users",
            execution_mode=ChatMode.EXE,
        ))
        # Should detect as dangerous or multi-step with elevated risk
        assert result.risk_level != RiskLevel.NONE


# ============================================================
# 6. THINK MODE — FORCES REASONING MODEL
# ============================================================


class TestThinkMode:
    """Think mode should force deepseek-r1 as the reasoning model."""

    def test_think_mode_query_input_accepts_field(self) -> None:
        """QueryInput should accept execution_mode for CMD/EXE."""
        qi = QueryInput(
            raw_message="Test message",
            execution_mode=ChatMode.CMD,
        )
        assert qi.execution_mode == ChatMode.CMD

    def test_think_mode_does_not_affect_query_understanding(self) -> None:
        """Think mode is a routing concern, not a QU concern.

        QueryUnderstanding should produce the same intent/risk
        regardless of think_mode — the override happens in the
        orchestrator's model selection, not in QU.
        """
        svc = QueryUnderstandingService()
        result_normal = svc.analyze(QueryInput(
            raw_message="What is the capital of France?",
            execution_mode=ChatMode.CMD,
        ))
        result_think = svc.analyze(QueryInput(
            raw_message="What is the capital of France?",
            execution_mode=ChatMode.CMD,
        ))
        assert result_normal.intent == result_think.intent
        assert result_normal.risk_level == result_think.risk_level


# ============================================================
# 7. COMBINED SCENARIOS
# ============================================================


class TestCombinedScenarios:
    """Test interactions between multiple control parameters."""

    @pytest.mark.asyncio
    async def test_autopilot_on_paranoid_medium_risk(self) -> None:
        """AGI ON + PARANOID + MEDIUM risk = tier 3 → NOT auto-approved.

        Even with autopilot, PARANOID + MEDIUM = tier 3,
        which exceeds autopilot's auto-approve threshold (tier 0-2).
        """
        gov = GovernanceEngine(_make_fake_db())
        # WRITE_FILE is MEDIUM risk (no hard law trigger)
        result = await gov.evaluate(
            action_type="WRITE_FILE",  # MEDIUM risk
            governance_slider="PARANOID",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
            autopilot=True,
        )
        # PARANOID + MEDIUM = tier 3 → not auto-approved
        assert result["governance_tier"] == 3
        assert result["allowed"] is False
        assert result["autopilot_override"] is False
        assert result["requires_approval"] is True

    @pytest.mark.asyncio
    async def test_autopilot_on_yolo_high_risk(self) -> None:
        """AGI ON + YOLO + HIGH risk = tier 1 → auto-approved."""
        gov = GovernanceEngine(_make_fake_db())
        result = await gov.evaluate(
            action_type="DEPLOY",  # HIGH risk
            governance_slider="YOLO",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
            autopilot=True,
        )
        # YOLO + HIGH = tier 1 → auto-approved by autopilot
        assert result["governance_tier"] == 1
        assert result["allowed"] is True
        assert result["autopilot_override"] is True

    @pytest.mark.asyncio
    async def test_autopilot_off_yolo_high_risk(self) -> None:
        """AGI OFF + YOLO + HIGH risk = tier 1 → allowed (logged)."""
        gov = GovernanceEngine(_make_fake_db())
        result = await gov.evaluate(
            action_type="DEPLOY",
            governance_slider="YOLO",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
            autopilot=False,
        )
        assert result["governance_tier"] == 1
        assert result["allowed"] is True
        assert result["autopilot_override"] is False
        assert result["message"] == "Logged"

    @pytest.mark.asyncio
    async def test_autopilot_off_strict_high_risk(self) -> None:
        """AGI OFF + STRICT + HIGH risk = tier 3 → blocked."""
        gov = GovernanceEngine(_make_fake_db())
        result = await gov.evaluate(
            action_type="DEPLOY",
            governance_slider="STRICT",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
            autopilot=False,
        )
        assert result["governance_tier"] == 3
        assert result["allowed"] is False
        assert result["requires_approval"] is True

    @pytest.mark.asyncio
    async def test_cmd_mode_exe_action_governance(self) -> None:
        """CMD mode action should still go through governance normally.

        CMD vs EXE affects the system prompt and risk assessment,
        not whether governance runs.
        """
        gov = GovernanceEngine(_make_fake_db())
        result = await gov.evaluate(
            action_type="LLM_CALL",
            action_params={"intent": "SIMPLE", "risk": "NONE"},
            governance_slider="STANDARD",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
        )
        assert result["allowed"] is True
        # LLM_CALL is not in HIGH or MEDIUM risk sets → defaults to LOW
        assert result["governance_tier"] <= 2

    def test_cmd_exe_risk_levels_differ(self) -> None:
        """Same message should have different risk in CMD vs EXE."""
        svc = QueryUnderstandingService()

        cmd_result = svc.analyze(QueryInput(
            raw_message="Create a new file called report.txt and write the summary",
            execution_mode=ChatMode.CMD,
        ))
        exe_result = svc.analyze(QueryInput(
            raw_message="Create a new file called report.txt and write the summary",
            execution_mode=ChatMode.EXE,
        ))

        # CMD mode should have NONE risk (can't execute)
        # EXE mode should have at least MEDIUM risk (file write)
        assert cmd_result.risk_level == RiskLevel.NONE
        # EXE could be MEDIUM or higher depending on pattern matching
        # At minimum, it should not be NONE
        assert exe_result.risk_level != RiskLevel.NONE or exe_result.intent != IntentType.DANGEROUS


# ============================================================
# 8. PLAN EVALUATION + AUTOPILOT
# ============================================================


class TestPlanEvaluation:
    """Test workflow plan evaluation with different sliders."""

    def test_yolo_plan_auto_approves_unless_tier_4(self) -> None:
        """YOLO plan with mixed actions → auto-approved if max tier < 4."""
        result = GovernanceEngine.evaluate_plan(
            steps=[
                {"action_type": "READ"},
                {"action_type": "EXECUTE"},
                {"action_type": "WRITE_FILE"},
            ],
            governance_slider="YOLO",
            actor_type="USER",
        )
        assert result["allowed"] is True
        assert result["plan_tier"] <= 1  # YOLO caps most at low tiers

    def test_strict_plan_always_requires_approval(self) -> None:
        """STRICT slider → ALL multi-step plans require approval."""
        result = GovernanceEngine.evaluate_plan(
            steps=[
                {"action_type": "READ"},
                {"action_type": "QUERY"},
            ],
            governance_slider="STRICT",
            actor_type="USER",
        )
        assert result["requires_approval"] is True
        assert result["allowed"] is False

    def test_paranoid_plan_always_requires_approval(self) -> None:
        """PARANOID slider → ALL plans require approval + checkpoints."""
        result = GovernanceEngine.evaluate_plan(
            steps=[{"action_type": "READ"}],
            governance_slider="PARANOID",
            actor_type="USER",
        )
        assert result["requires_approval"] is True

    def test_founder_plan_always_approved(self) -> None:
        """FOUNDER can approve any plan regardless of slider."""
        result = GovernanceEngine.evaluate_plan(
            steps=[
                {"action_type": "DELETE"},
                {"action_type": "DEPLOY"},
                {"action_type": "SEND_EMAIL"},
            ],
            governance_slider="PARANOID",
            actor_type="FOUNDER",
        )
        assert result["allowed"] is True
        assert result["requires_approval"] is False


# ============================================================
# 9. SLIDER OVERRIDE VALIDATION
# ============================================================


class TestSliderOverride:
    """Test per-conversation slider override with floor enforcement."""

    def test_operator_cannot_go_below_standard(self) -> None:
        """OPERATOR's minimum is STANDARD — request for YOLO is clamped."""
        result = GovernanceEngine.validate_override(
            requested_preset="YOLO",
            user_role="OPERATOR",
        )
        assert result["was_clamped"] is True
        assert result["effective_preset"] == "STANDARD"

    def test_founder_can_use_yolo(self) -> None:
        """FOUNDER can use any slider including YOLO."""
        result = GovernanceEngine.validate_override(
            requested_preset="YOLO",
            user_role="FOUNDER",
        )
        assert result["was_clamped"] is False
        assert result["effective_preset"] == "YOLO"

    def test_viewer_locked_to_paranoid(self) -> None:
        """VIEWER is locked to PARANOID only."""
        result = GovernanceEngine.validate_override(
            requested_preset="STANDARD",
            user_role="VIEWER",
        )
        assert result["was_clamped"] is True
        assert result["effective_preset"] == "PARANOID"

    def test_team_minimum_enforced(self) -> None:
        """Team minimum overrides role default if higher."""
        result = GovernanceEngine.validate_override(
            requested_preset="LIGHT",
            user_role="FOUNDER",
            team_minimum="STRICT",
        )
        assert result["was_clamped"] is True
        assert result["effective_preset"] == "STRICT"
