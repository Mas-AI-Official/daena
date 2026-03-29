"""Tests for DriftDetector — anti-drift scoring, checkpoints, response actions."""

from __future__ import annotations

from app.core.constants import GovernanceSlider
from app.services.drift_detector import (
    CHECKPOINT_INTERVALS,
    DriftAction,
    DriftDetector,
    DriftSeverity,
    ExecutionState,
    ResourceBudget,
)

# ── Fixtures ──────────────────────────────────────────────────────

def _perfect_state() -> ExecutionState:
    """Execution state with zero drift."""
    return ExecutionState(
        summary="deploy user authentication to staging environment",
        total_steps=10,
        off_plan_steps=0,
        actual_cost=0.05,
        total_effects=5,
        unplanned_effects=0,
    )


def _drifting_state() -> ExecutionState:
    """Moderate drift: some off-plan steps and cost overrun."""
    return ExecutionState(
        summary="refactoring database schema",
        total_steps=10,
        off_plan_steps=4,
        actual_cost=0.15,
        total_effects=8,
        unplanned_effects=3,
    )


def _lost_state() -> ExecutionState:
    """Severe drift: completely off-plan."""
    return ExecutionState(
        summary="generating marketing copy",
        total_steps=10,
        off_plan_steps=9,
        actual_cost=0.50,
        total_effects=12,
        unplanned_effects=10,
    )


def _budget() -> ResourceBudget:
    return ResourceBudget(estimated_cost=0.10, estimated_steps=10)


# ── should_checkpoint ─────────────────────────────────────────────

class TestShouldCheckpoint:
    def test_yolo_every_10(self) -> None:
        assert not DriftDetector.should_checkpoint(5, "YOLO")
        assert DriftDetector.should_checkpoint(10, "YOLO")
        assert DriftDetector.should_checkpoint(20, "YOLO")

    def test_standard_every_5(self) -> None:
        assert not DriftDetector.should_checkpoint(3, "STANDARD")
        assert DriftDetector.should_checkpoint(5, "STANDARD")
        assert DriftDetector.should_checkpoint(15, "STANDARD")

    def test_paranoid_every_step(self) -> None:
        for step in range(1, 11):
            assert DriftDetector.should_checkpoint(step, "PARANOID")

    def test_strict_every_3(self) -> None:
        assert not DriftDetector.should_checkpoint(2, "STRICT")
        assert DriftDetector.should_checkpoint(3, "STRICT")
        assert DriftDetector.should_checkpoint(6, "STRICT")

    def test_step_zero_never_checkpoints(self) -> None:
        assert not DriftDetector.should_checkpoint(0, "PARANOID")

    def test_negative_step_never_checkpoints(self) -> None:
        assert not DriftDetector.should_checkpoint(-1, "PARANOID")

    def test_all_presets_have_intervals(self) -> None:
        """Every GovernanceSlider has a checkpoint interval defined."""
        for slider in GovernanceSlider:
            assert slider in CHECKPOINT_INTERVALS


# ── Drift score computation ───────────────────────────────────────

class TestDriftScore:
    def test_perfect_state_low_score(self) -> None:
        """Zero drift in all dimensions → low score."""
        detector = DriftDetector()
        resp = detector.evaluate(
            state=_perfect_state(),
            original_goal="deploy user authentication to staging environment",
            budget=_budget(),
            goal_similarity=1.0,  # perfect alignment
            step_number=5,
        )
        assert resp.drift_score < 0.3
        assert resp.severity == DriftSeverity.ON_TRACK

    def test_drifting_state_medium_score(self) -> None:
        """Moderate drift → DRIFTING severity."""
        detector = DriftDetector()
        resp = detector.evaluate(
            state=_drifting_state(),
            original_goal="deploy user authentication to staging environment",
            budget=_budget(),
            goal_similarity=0.3,  # low alignment
            step_number=10,
        )
        assert 0.3 <= resp.drift_score < 0.7
        assert resp.severity == DriftSeverity.DRIFTING

    def test_lost_state_high_score(self) -> None:
        """Severe drift → LOST severity."""
        detector = DriftDetector()
        resp = detector.evaluate(
            state=_lost_state(),
            original_goal="deploy user authentication to staging environment",
            budget=_budget(),
            goal_similarity=0.0,  # no alignment
            step_number=10,
        )
        assert resp.drift_score >= 0.7
        assert resp.severity == DriftSeverity.LOST

    def test_score_in_range(self) -> None:
        """Score is always in [0.0, 1.0]."""
        detector = DriftDetector()
        for sim in (0.0, 0.5, 1.0):
            resp = detector.evaluate(
                state=_perfect_state(),
                original_goal="test",
                budget=_budget(),
                goal_similarity=sim,
                step_number=1,
            )
            assert 0.0 <= resp.drift_score <= 1.0

    def test_four_dimensions_present(self) -> None:
        """Checkpoint stores all four dimension values."""
        detector = DriftDetector()
        resp = detector.evaluate(
            state=_drifting_state(),
            original_goal="test",
            budget=_budget(),
            goal_similarity=0.5,
            step_number=1,
        )
        dims = resp.checkpoint.dimensions
        assert "goal_alignment_loss" in dims
        assert "plan_deviation_ratio" in dims
        assert "resource_overrun_ratio" in dims
        assert "side_effect_ratio" in dims


# ── Drift response actions ────────────────────────────────────────

class TestDriftResponseActions:
    def test_yolo_on_track_continues(self) -> None:
        detector = DriftDetector()
        resp = detector.evaluate(
            state=_perfect_state(),
            original_goal="deploy auth",
            budget=_budget(),
            governance_slider="YOLO",
            goal_similarity=1.0,
            step_number=10,
        )
        assert resp.should_continue is True
        assert resp.action == DriftAction.CONTINUE
        assert resp.requires_human is False

    def test_standard_drifting_pauses_and_notifies(self) -> None:
        detector = DriftDetector()
        resp = detector.evaluate(
            state=_drifting_state(),
            original_goal="deploy auth",
            budget=_budget(),
            governance_slider="STANDARD",
            goal_similarity=0.3,
            step_number=5,
        )
        assert resp.should_continue is False
        assert resp.action == DriftAction.PAUSE_NOTIFY_REALIGN
        assert resp.requires_human is False

    def test_strict_drifting_waits_for_human(self) -> None:
        detector = DriftDetector()
        resp = detector.evaluate(
            state=_drifting_state(),
            original_goal="deploy auth",
            budget=_budget(),
            governance_slider="STRICT",
            goal_similarity=0.3,
            step_number=3,
        )
        assert resp.should_continue is False
        assert resp.action == DriftAction.PAUSE_ALERT_WAIT
        assert resp.requires_human is True

    def test_paranoid_on_track_needs_acknowledgment(self) -> None:
        detector = DriftDetector()
        resp = detector.evaluate(
            state=_perfect_state(),
            original_goal="deploy auth",
            budget=_budget(),
            governance_slider="PARANOID",
            goal_similarity=1.0,
            step_number=1,
        )
        assert resp.should_continue is True
        assert resp.action == DriftAction.CONTINUE_ACKNOWLEDGE
        assert resp.requires_human is True

    def test_lost_on_standard_escalates_to_council(self) -> None:
        detector = DriftDetector()
        resp = detector.evaluate(
            state=_lost_state(),
            original_goal="deploy auth",
            budget=_budget(),
            governance_slider="STANDARD",
            goal_similarity=0.0,
            step_number=5,
        )
        assert resp.severity == DriftSeverity.LOST
        assert resp.action == DriftAction.ESCALATE_COUNCIL_REVIEW
        assert resp.requires_council is True
        assert resp.requires_new_plan is True
        assert resp.should_continue is False

    def test_lost_on_paranoid_escalates_to_founder(self) -> None:
        detector = DriftDetector()
        resp = detector.evaluate(
            state=_lost_state(),
            original_goal="deploy auth",
            budget=_budget(),
            governance_slider="PARANOID",
            goal_similarity=0.0,
            step_number=1,
        )
        assert resp.action == DriftAction.ESCALATE_FULL_STOP_FOUNDER
        assert resp.requires_human is True
        assert resp.requires_council is True
        assert resp.requires_new_plan is True


# ── Checkpoint history & trend ────────────────────────────────────

class TestCheckpointHistory:
    def test_checkpoints_accumulate(self) -> None:
        detector = DriftDetector()
        for i in range(1, 4):
            detector.evaluate(
                state=_perfect_state(),
                original_goal="test",
                budget=_budget(),
                goal_similarity=1.0,
                step_number=i,
            )
        assert len(detector.checkpoints) == 3

    def test_reset_clears_history(self) -> None:
        detector = DriftDetector()
        detector.evaluate(
            state=_perfect_state(),
            original_goal="test",
            budget=_budget(),
            goal_similarity=1.0,
            step_number=1,
        )
        assert len(detector.checkpoints) == 1
        detector.reset()
        assert len(detector.checkpoints) == 0

    def test_drift_trend_no_data(self) -> None:
        detector = DriftDetector()
        trend = detector.get_drift_trend()
        assert trend["checkpoint_count"] == 0
        assert trend["trend"] == "no_data"

    def test_drift_trend_worsening(self) -> None:
        """Scores increasing over time → worsening trend."""
        detector = DriftDetector()
        # Simulate worsening drift by decreasing goal_similarity
        similarities = [0.9, 0.85, 0.7, 0.5, 0.3, 0.2]
        for i, sim in enumerate(similarities, 1):
            detector.evaluate(
                state=ExecutionState(
                    summary="gradually drifting",
                    total_steps=i,
                    off_plan_steps=max(0, i - 3),
                    actual_cost=0.01 * i,
                    total_effects=i,
                    unplanned_effects=max(0, i - 4),
                ),
                original_goal="deploy auth",
                budget=_budget(),
                goal_similarity=sim,
                step_number=i,
            )

        trend = detector.get_drift_trend()
        assert trend["checkpoint_count"] == 6
        assert trend["trend"] == "worsening"


# ── Word overlap heuristic ────────────────────────────────────────

class TestWordOverlap:
    def test_identical_strings(self) -> None:
        assert DriftDetector._word_overlap("hello world", "hello world") == 1.0

    def test_no_overlap(self) -> None:
        assert DriftDetector._word_overlap("hello world", "foo bar") == 0.0

    def test_partial_overlap(self) -> None:
        result = DriftDetector._word_overlap(
            "deploy auth to staging", "deploy auth to production",
        )
        assert 0.0 < result < 1.0

    def test_empty_string(self) -> None:
        assert DriftDetector._word_overlap("", "hello") == 0.0
        assert DriftDetector._word_overlap("hello", "") == 0.0


# ── Resource overrun edge cases ───────────────────────────────────

class TestResourceOverrun:
    def test_zero_budget_no_division_error(self) -> None:
        """Zero estimated_cost should not cause division by zero."""
        detector = DriftDetector()
        resp = detector.evaluate(
            state=ExecutionState(
                summary="test", total_steps=1, actual_cost=1.0,
            ),
            original_goal="test",
            budget=ResourceBudget(estimated_cost=0.0),
            goal_similarity=1.0,
            step_number=1,
        )
        # Should not raise
        assert resp.drift_score >= 0.0

    def test_overrun_capped_at_2x(self) -> None:
        """Resource overrun ratio is capped at 2x, normalized to [0, 1]."""
        detector = DriftDetector()
        resp = detector.evaluate(
            state=ExecutionState(
                summary="test", total_steps=1, actual_cost=10.0,
            ),
            original_goal="test",
            budget=ResourceBudget(estimated_cost=0.10),
            goal_similarity=1.0,
            step_number=1,
        )
        dims = resp.checkpoint.dimensions
        # 10.0 / 0.10 = 100x → capped at 2.0 → /2 = 1.0
        assert dims["resource_overrun_ratio"] == 1.0
