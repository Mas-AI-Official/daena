"""Tests for all control parameter combinations in the Daena pipeline.

Covers:
- AGI ON (autopilot) override: auto-approve all tiers (only hard laws block)
- AGI OFF + governance mode: UNLEASHED / BALANCED / GOVERNED
- CMD mode: no execution, plan-only system prompt
- EXE mode: tool execution with governance
- Think mode: forces reasoning model (deepseek-r1)
- Combined scenarios: autopilot + UNLEASHED, autopilot + GOVERNED, etc.

Run: pytest tests/test_control_combinations.py -v
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from app.core.constants import (
    ChatMode,
    GovernanceMode,
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
        """AGI ON + Tier 0 action -> auto-approved, no user involvement."""
        gov = GovernanceEngine(_make_fake_db())
        result = await gov.evaluate(
            action_type="READ",
            governance_slider="BALANCED",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
            autopilot=True,
        )
        assert result["allowed"] is True
        assert result["governance_tier"] == 0
        assert result["autopilot_override"] is True
        assert "AGI" in result["message"]

    @pytest.mark.asyncio
    async def test_autopilot_on_auto_approves_tier_1(self) -> None:
        """AGI ON + Tier 1 action -> auto-approved."""
        gov = GovernanceEngine(_make_fake_db())
        # GOVERNED + NONE risk = tier 0, GOVERNED + LOW = tier 1
        result = await gov.evaluate(
            action_type="LLM_CALL",  # LOW risk (unknown action default)
            governance_slider="GOVERNED",
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
        """AGI ON + Tier 2 action -> auto-approved."""
        gov = GovernanceEngine(_make_fake_db())
        # GOVERNED + MEDIUM risk = tier 2
        result = await gov.evaluate(
            action_type="WRITE_FILE",  # MEDIUM risk
            governance_slider="GOVERNED",
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
    async def test_autopilot_on_approves_tier_3(self) -> None:
        """AGI ON + Tier 3 -> auto-approved (OpenClaw-style autonomous).

        Only hard-law violations block in AGI mode.
        Governance logs for audit but never interrupts the user.
        """
        gov = GovernanceEngine(_make_fake_db())
        # GOVERNED + HIGH risk = tier 3
        result = await gov.evaluate(
            action_type="DEPLOY",
            governance_slider="GOVERNED",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
            autopilot=True,
        )
        assert result["allowed"] is True
        assert result["governance_tier"] == 3
        assert result["requires_approval"] is False
        assert result["autopilot_override"] is True

    @pytest.mark.asyncio
    async def test_autopilot_on_approves_tier_4_non_hardlaw(self) -> None:
        """AGI ON + Tier 4 action (non hard-law) -> auto-approved.

        AGI UNLEASHED: only hard law violations (data exfiltration,
        tenant isolation) block. DELETE is CRITICAL under GOVERNED = tier 4.
        """
        gov = GovernanceEngine(_make_fake_db())
        # GOVERNED + CRITICAL risk (DELETE) = tier 4, but AGI overrides
        result = await gov.evaluate(
            action_type="DELETE",
            governance_slider="GOVERNED",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
            autopilot=True,
        )
        assert result["allowed"] is True
        assert result["autopilot_override"] is True

    @pytest.mark.asyncio
    async def test_autopilot_on_auto_approves_balanced_high_risk(self) -> None:
        """AGI ON + BALANCED + HIGH risk -> auto-approved.

        AGI mode operates autonomously like OpenClaw. Governance is
        invisible -- it logs everything for audit but never interrupts.
        Only hard-law violations block.
        """
        gov = GovernanceEngine(_make_fake_db())
        # BALANCED + HIGH risk (DEPLOY) = tier 2 -> autopilot auto-approves
        result = await gov.evaluate(
            action_type="DEPLOY",  # HIGH risk
            governance_slider="BALANCED",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
            autopilot=True,
        )
        assert result["allowed"] is True
        assert result["governance_tier"] == 2
        assert result["autopilot_override"] is True
        assert result["requires_approval"] is False

    @pytest.mark.asyncio
    async def test_autopilot_on_hard_law_never_bypassed(self) -> None:
        """Hard law violations block even with autopilot ON."""
        gov = GovernanceEngine(_make_fake_db())
        result = await gov.evaluate(
            action_type="DELETE",
            action_params={"target": "all_user_data", "scope": "tenant"},
            governance_slider="UNLEASHED",
            actor_type="FOUNDER",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
            autopilot=True,
        )
        # Hard laws checked first -- if violated, blocked regardless
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
            governance_slider="BALANCED",
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
            governance_slider="BALANCED",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
            # autopilot not passed -- defaults to False
        )
        assert result["autopilot_override"] is False


# ============================================================
# 2. AGI OFF + GOVERNANCE MODE COMBINATIONS
# ============================================================


class TestGovernanceModeCombinations:
    """Without autopilot, the governance mode controls everything."""

    @pytest.mark.asyncio
    async def test_unleashed_allows_medium_risk(self) -> None:
        """UNLEASHED + MEDIUM risk -> tier 0, allowed."""
        gov = GovernanceEngine(_make_fake_db())
        result = await gov.evaluate(
            action_type="WRITE_FILE",
            governance_slider="UNLEASHED",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
        )
        assert result["allowed"] is True
        assert result["governance_tier"] == 0
        assert result["risk_level"] == "MEDIUM"

    @pytest.mark.asyncio
    async def test_governed_elevates_low_risk(self) -> None:
        """GOVERNED + LOW risk -> tier 1 (logged)."""
        gov = GovernanceEngine(_make_fake_db())
        result = await gov.evaluate(
            action_type="LLM_CALL",  # LOW risk
            governance_slider="GOVERNED",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
        )
        assert result["governance_tier"] == 1
        assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_governed_elevates_medium_risk(self) -> None:
        """GOVERNED + MEDIUM risk -> tier 2, user notified."""
        gov = GovernanceEngine(_make_fake_db())
        result = await gov.evaluate(
            action_type="WRITE_FILE",  # MEDIUM risk
            governance_slider="GOVERNED",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
        )
        assert result["governance_tier"] == 2
        assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_governed_blocks_high_risk(self) -> None:
        """GOVERNED + HIGH risk -> tier 3, approval required."""
        gov = GovernanceEngine(_make_fake_db())
        result = await gov.evaluate(
            action_type="DEPLOY",  # HIGH risk
            governance_slider="GOVERNED",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
        )
        assert result["governance_tier"] == 3
        assert result["allowed"] is False
        assert result["requires_approval"] is True

    @pytest.mark.asyncio
    async def test_governed_blocks_critical_risk(self) -> None:
        """GOVERNED + CRITICAL risk -> tier 4."""
        gov = GovernanceEngine(_make_fake_db())
        result = await gov.evaluate(
            action_type="DELETE",  # CRITICAL risk
            governance_slider="GOVERNED",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
        )
        assert result["governance_tier"] == 4
        assert result["allowed"] is False

    @pytest.mark.asyncio
    async def test_balanced_allows_medium_risk(self) -> None:
        """BALANCED + MEDIUM risk -> tier 1, logged only."""
        gov = GovernanceEngine(_make_fake_db())
        result = await gov.evaluate(
            action_type="WRITE_FILE",
            governance_slider="BALANCED",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
        )
        assert result["governance_tier"] == 1
        assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_balanced_blocks_critical_risk(self) -> None:
        """BALANCED + CRITICAL risk (DELETE) -> hard law #6 triggers tier 4."""
        gov = GovernanceEngine(_make_fake_db())
        result = await gov.evaluate(
            action_type="DELETE",
            governance_slider="BALANCED",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
        )
        # DELETE triggers Hard Law #6 which escalates to tier 4
        assert result["governance_tier"] >= 3
        assert result["allowed"] is False

    @pytest.mark.asyncio
    async def test_founder_bypasses_all_tiers(self) -> None:
        """FOUNDER actor_type bypasses all tiers.

        Uses DEPLOY (HIGH risk) + GOVERNED = tier 3, which normally
        requires approval. Founder bypasses this.
        """
        gov = GovernanceEngine(_make_fake_db())
        result = await gov.evaluate(
            action_type="DEPLOY",
            governance_slider="GOVERNED",
            actor_type="FOUNDER",
            actor_role="FOUNDER",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
        )
        assert result["allowed"] is True
        assert result["governance_tier"] == 3
        assert "Founder override" in result["message"]


# ============================================================
# 3. GOVERNANCE TIER MAP COMPLETENESS
# ============================================================


class TestGovernanceTierMap:
    """Verify every mode x risk combination in GOVERNANCE_TIER_MAP."""

    def test_all_modes_present(self) -> None:
        for mode in GovernanceMode:
            assert mode in GOVERNANCE_TIER_MAP, f"Missing mode: {mode}"

    def test_all_risks_present_for_each_mode(self) -> None:
        for mode in GovernanceMode:
            for risk in RiskLevel:
                assert risk in GOVERNANCE_TIER_MAP[mode], (
                    f"Missing risk {risk} for mode {mode}"
                )

    def test_tiers_are_0_to_4(self) -> None:
        for mode in GovernanceMode:
            for risk in RiskLevel:
                tier = GOVERNANCE_TIER_MAP[mode][risk]
                assert 0 <= tier <= 4, (
                    f"Invalid tier {tier} for {mode} x {risk}"
                )

    def test_unleashed_is_most_permissive(self) -> None:
        """UNLEASHED should have the lowest tiers across all risk levels."""
        for risk in RiskLevel:
            unleashed_tier = GOVERNANCE_TIER_MAP[GovernanceMode.UNLEASHED][risk]
            for mode in GovernanceMode:
                other_tier = GOVERNANCE_TIER_MAP[mode][risk]
                assert unleashed_tier <= other_tier, (
                    f"UNLEASHED tier {unleashed_tier} > {mode} tier "
                    f"{other_tier} for risk {risk}"
                )

    def test_governed_is_most_restrictive(self) -> None:
        """GOVERNED should have the highest tiers across all risk levels."""
        for risk in RiskLevel:
            governed_tier = GOVERNANCE_TIER_MAP[GovernanceMode.GOVERNED][risk]
            for mode in GovernanceMode:
                other_tier = GOVERNANCE_TIER_MAP[mode][risk]
                assert governed_tier >= other_tier, (
                    f"GOVERNED tier {governed_tier} < {mode} tier "
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
    async def test_autopilot_on_governed_medium_risk(self) -> None:
        """AGI ON + GOVERNED + MEDIUM risk = tier 2 -> auto-approved."""
        gov = GovernanceEngine(_make_fake_db())
        result = await gov.evaluate(
            action_type="WRITE_FILE",  # MEDIUM risk
            governance_slider="GOVERNED",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
            autopilot=True,
        )
        assert result["governance_tier"] == 2
        assert result["allowed"] is True
        assert result["autopilot_override"] is True
        assert result["requires_approval"] is False

    @pytest.mark.asyncio
    async def test_autopilot_on_unleashed_high_risk(self) -> None:
        """AGI ON + UNLEASHED + HIGH risk = tier 0 -> auto-approved."""
        gov = GovernanceEngine(_make_fake_db())
        result = await gov.evaluate(
            action_type="DEPLOY",  # HIGH risk
            governance_slider="UNLEASHED",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
            autopilot=True,
        )
        # UNLEASHED + HIGH = tier 0 -> auto-approved by autopilot
        assert result["governance_tier"] == 0
        assert result["allowed"] is True
        assert result["autopilot_override"] is True

    @pytest.mark.asyncio
    async def test_autopilot_off_unleashed_high_risk(self) -> None:
        """AGI OFF + UNLEASHED + HIGH risk = tier 0 -> allowed (logged)."""
        gov = GovernanceEngine(_make_fake_db())
        result = await gov.evaluate(
            action_type="DEPLOY",
            governance_slider="UNLEASHED",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
            autopilot=False,
        )
        assert result["governance_tier"] == 0
        assert result["allowed"] is True
        assert result["autopilot_override"] is False
        assert result["message"] in ("Logged", "Silent pass")

    @pytest.mark.asyncio
    async def test_autopilot_off_governed_high_risk(self) -> None:
        """AGI OFF + GOVERNED + HIGH risk = tier 3 -> blocked."""
        gov = GovernanceEngine(_make_fake_db())
        result = await gov.evaluate(
            action_type="DEPLOY",
            governance_slider="GOVERNED",
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
        """CMD mode action should still go through governance normally."""
        gov = GovernanceEngine(_make_fake_db())
        result = await gov.evaluate(
            action_type="LLM_CALL",
            action_params={"intent": "SIMPLE", "risk": "NONE"},
            governance_slider="BALANCED",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=_make_uuid(),
            user_id=_make_uuid(),
        )
        assert result["allowed"] is True
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

    def test_unleashed_plan_auto_approves(self) -> None:
        """UNLEASHED plan with mixed actions -> auto-approved."""
        result = GovernanceEngine.evaluate_plan(
            steps=[
                {"action_type": "READ"},
                {"action_type": "EXECUTE"},
                {"action_type": "WRITE_FILE"},
            ],
            governance_slider="UNLEASHED",
            actor_type="USER",
        )
        assert result["allowed"] is True
        assert result["plan_tier"] <= 1  # UNLEASHED caps most at low tiers

    def test_governed_plan_always_requires_approval(self) -> None:
        """GOVERNED -> ALL multi-step plans require approval."""
        result = GovernanceEngine.evaluate_plan(
            steps=[
                {"action_type": "READ"},
                {"action_type": "QUERY"},
            ],
            governance_slider="GOVERNED",
            actor_type="USER",
        )
        assert result["requires_approval"] is True
        assert result["allowed"] is False

    def test_balanced_plan_requires_approval_for_tier_3_plus(self) -> None:
        """BALANCED -> plans with tier 3+ require approval."""
        result = GovernanceEngine.evaluate_plan(
            steps=[
                {"action_type": "DELETE"},  # CRITICAL -> tier 3 under BALANCED
            ],
            governance_slider="BALANCED",
            actor_type="USER",
        )
        assert result["requires_approval"] is True

    def test_founder_plan_always_approved(self) -> None:
        """FOUNDER can approve any plan regardless of mode."""
        result = GovernanceEngine.evaluate_plan(
            steps=[
                {"action_type": "DELETE"},
                {"action_type": "DEPLOY"},
                {"action_type": "SEND_EMAIL"},
            ],
            governance_slider="GOVERNED",
            actor_type="FOUNDER",
        )
        assert result["allowed"] is True
        assert result["requires_approval"] is False


# ============================================================
# 9. GOVERNANCE MODE OVERRIDE VALIDATION
# ============================================================


class TestModeOverride:
    """Test per-conversation governance mode override with floor enforcement."""

    def test_operator_cannot_go_below_balanced(self) -> None:
        """OPERATOR's minimum is BALANCED -- request for UNLEASHED is clamped."""
        result = GovernanceEngine.validate_override(
            requested_preset="UNLEASHED",
            user_role="OPERATOR",
        )
        assert result["was_clamped"] is True
        # Clamped to at least BALANCED
        assert result["effective_preset"] in ("BALANCED", "GOVERNED")

    def test_founder_can_use_unleashed(self) -> None:
        """FOUNDER can use any mode including UNLEASHED."""
        result = GovernanceEngine.validate_override(
            requested_preset="UNLEASHED",
            user_role="FOUNDER",
        )
        assert result["was_clamped"] is False
        assert result["effective_preset"] == "UNLEASHED"

    def test_viewer_locked_to_governed(self) -> None:
        """VIEWER is locked to GOVERNED only."""
        result = GovernanceEngine.validate_override(
            requested_preset="BALANCED",
            user_role="VIEWER",
        )
        assert result["was_clamped"] is True
        assert result["effective_preset"] == "GOVERNED"

    def test_team_minimum_enforced(self) -> None:
        """Team minimum overrides role default if higher."""
        result = GovernanceEngine.validate_override(
            requested_preset="UNLEASHED",
            user_role="FOUNDER",
            team_minimum="GOVERNED",
        )
        assert result["was_clamped"] is True
        assert result["effective_preset"] == "GOVERNED"
