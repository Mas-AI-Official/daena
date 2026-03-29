"""Drift Detector — anti-drift system for agent execution monitoring.

Detects when an autopilot or multi-step execution has deviated from
the original goal.  Integrates directly with the governance slider.

Four-dimension weighted drift scoring:

    drift = (goal_alignment_loss  × 0.40
           + plan_deviation_ratio × 0.30
           + resource_overrun     × 0.15
           + side_effect_ratio    × 0.15)

Drift is assessed at checkpoint intervals determined by the governance
preset (YOLO=10, LIGHT=7, STANDARD=5, STRICT=3, PARANOID=1).

Anti-drift is MANDATORY in Autopilot mode regardless of slider position.
In non-Autopilot modes it is advisory — logs but does not block unless
the drift score exceeds the escalation threshold.

Patent-pending: Sunflower-Honeycomb governance architecture.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.core.constants import GovernanceSlider
from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Checkpoint intervals per preset (from governance.py) ──────────

CHECKPOINT_INTERVALS: dict[GovernanceSlider, int] = {
    GovernanceSlider.YOLO: 10,
    GovernanceSlider.LIGHT: 7,
    GovernanceSlider.STANDARD: 5,
    GovernanceSlider.STRICT: 3,
    GovernanceSlider.PARANOID: 1,
}


# ── Drift classification ─────────────────────────────────────────

class DriftSeverity(str, Enum):
    """Drift classification buckets."""

    ON_TRACK = "ON_TRACK"   # drift < 0.3
    DRIFTING = "DRIFTING"   # 0.3 <= drift < 0.7
    LOST = "LOST"           # drift >= 0.7


class DriftAction(str, Enum):
    """Action to take when drift is detected."""

    CONTINUE = "CONTINUE"
    CONTINUE_LOG = "CONTINUE_LOG"
    CONTINUE_NOTIFY = "CONTINUE_NOTIFY"
    CONTINUE_ACKNOWLEDGE = "CONTINUE_ACKNOWLEDGE"
    PAUSE_AUTO_REALIGN = "PAUSE_AUTO_REALIGN"
    PAUSE_NOTIFY_REALIGN = "PAUSE_NOTIFY_REALIGN"
    PAUSE_ALERT_WAIT = "PAUSE_ALERT_WAIT"
    ESCALATE_TOAST = "ESCALATE_TOAST"
    ESCALATE_PAUSE_WAIT = "ESCALATE_PAUSE_WAIT"
    ESCALATE_COUNCIL_REVIEW = "ESCALATE_COUNCIL_REVIEW"
    ESCALATE_FULL_STOP_ADMIN = "ESCALATE_FULL_STOP_ADMIN"
    ESCALATE_FULL_STOP_FOUNDER = "ESCALATE_FULL_STOP_FOUNDER"


# ── Data structures ──────────────────────────────────────────────

@dataclass(slots=True)
class ExecutionState:
    """Snapshot of the current multi-step execution.

    Tracks progress, deviations, and side effects for drift
    scoring.
    """

    summary: str = ""
    """Natural-language summary of current execution state."""

    total_steps: int = 0
    """Total steps executed so far."""

    off_plan_steps: int = 0
    """Steps that deviated from the approved plan."""

    actual_cost: float = 0.0
    """Actual cost incurred so far (USD)."""

    total_effects: int = 0
    """Total observable effects (files written, APIs called, etc.)."""

    unplanned_effects: int = 0
    """Effects not in the original plan."""


@dataclass(slots=True)
class ResourceBudget:
    """Estimated resource budget for a plan execution."""

    estimated_cost: float = 0.0
    """Estimated total cost in USD."""

    estimated_steps: int = 0
    """Estimated total step count."""

    max_time_seconds: float = 0.0
    """Maximum allowed execution time."""


@dataclass(slots=True)
class DriftCheckpoint:
    """Record of a drift checkpoint evaluation."""

    step_number: int
    drift_score: float
    severity: DriftSeverity
    action: DriftAction
    dimensions: dict[str, float] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    message: str = ""


@dataclass(slots=True)
class DriftResponse:
    """Response from the drift detector after evaluation."""

    should_continue: bool
    """Whether execution should continue."""

    severity: DriftSeverity
    action: DriftAction
    drift_score: float
    checkpoint: DriftCheckpoint
    message: str = ""

    requires_human: bool = False
    """Whether a human must acknowledge before resuming."""

    requires_council: bool = False
    """Whether council review is needed."""

    requires_new_plan: bool = False
    """Whether a new plan should be generated."""


# ── Drift response matrix ────────────────────────────────────────
# Maps (GovernanceSlider, DriftSeverity) → DriftAction
# Per spec Section 6.3

_DRIFT_RESPONSE_MATRIX: dict[
    GovernanceSlider, dict[DriftSeverity, DriftAction]
] = {
    GovernanceSlider.YOLO: {
        DriftSeverity.ON_TRACK: DriftAction.CONTINUE,
        DriftSeverity.DRIFTING: DriftAction.PAUSE_AUTO_REALIGN,
        DriftSeverity.LOST: DriftAction.ESCALATE_TOAST,
    },
    GovernanceSlider.LIGHT: {
        DriftSeverity.ON_TRACK: DriftAction.CONTINUE_LOG,
        DriftSeverity.DRIFTING: DriftAction.PAUSE_AUTO_REALIGN,
        DriftSeverity.LOST: DriftAction.ESCALATE_PAUSE_WAIT,
    },
    GovernanceSlider.STANDARD: {
        DriftSeverity.ON_TRACK: DriftAction.CONTINUE_LOG,
        DriftSeverity.DRIFTING: DriftAction.PAUSE_NOTIFY_REALIGN,
        DriftSeverity.LOST: DriftAction.ESCALATE_COUNCIL_REVIEW,
    },
    GovernanceSlider.STRICT: {
        DriftSeverity.ON_TRACK: DriftAction.CONTINUE_NOTIFY,
        DriftSeverity.DRIFTING: DriftAction.PAUSE_ALERT_WAIT,
        DriftSeverity.LOST: DriftAction.ESCALATE_FULL_STOP_ADMIN,
    },
    GovernanceSlider.PARANOID: {
        DriftSeverity.ON_TRACK: DriftAction.CONTINUE_ACKNOWLEDGE,
        DriftSeverity.DRIFTING: DriftAction.PAUSE_ALERT_WAIT,
        DriftSeverity.LOST: DriftAction.ESCALATE_FULL_STOP_FOUNDER,
    },
}

# Actions that block execution until a human responds
_HUMAN_REQUIRED_ACTIONS: frozenset[DriftAction] = frozenset({
    DriftAction.PAUSE_ALERT_WAIT,
    DriftAction.CONTINUE_ACKNOWLEDGE,
    DriftAction.ESCALATE_PAUSE_WAIT,
    DriftAction.ESCALATE_FULL_STOP_ADMIN,
    DriftAction.ESCALATE_FULL_STOP_FOUNDER,
})

# Actions that require council review
_COUNCIL_REQUIRED_ACTIONS: frozenset[DriftAction] = frozenset({
    DriftAction.ESCALATE_COUNCIL_REVIEW,
    DriftAction.ESCALATE_FULL_STOP_ADMIN,
    DriftAction.ESCALATE_FULL_STOP_FOUNDER,
})

# Actions where a new plan should be generated
_NEW_PLAN_ACTIONS: frozenset[DriftAction] = frozenset({
    DriftAction.ESCALATE_COUNCIL_REVIEW,
    DriftAction.ESCALATE_FULL_STOP_FOUNDER,
})


# ── Drift Detector ───────────────────────────────────────────────

class DriftDetector:
    """Anti-drift monitoring for multi-step agent execution.

    Evaluates execution state against the original plan and goal,
    producing a drift score and recommending an action based on the
    active governance preset.

    Usage::

        detector = DriftDetector()

        # At each checkpoint:
        response = detector.evaluate(
            state=current_state,
            original_goal="Deploy user auth to staging",
            budget=resource_budget,
            governance_slider="STANDARD",
            step_number=7,
        )

        if not response.should_continue:
            # Handle pause/escalation
            ...
    """

    def __init__(self) -> None:
        self._checkpoints: list[DriftCheckpoint] = []

    @property
    def checkpoints(self) -> list[DriftCheckpoint]:
        """All checkpoints recorded during this execution."""
        return list(self._checkpoints)

    # ── Public: should we checkpoint now? ─────────────────────

    @staticmethod
    def should_checkpoint(
        step_number: int,
        governance_slider: str,
        *,
        is_autopilot: bool = False,
    ) -> bool:
        """Determine if a drift checkpoint is needed at this step.

        Args:
            step_number: Current step number (1-based).
            governance_slider: Active governance preset string.
            is_autopilot: If True, forces checkpoint per preset
                interval even if slider would not normally require it.

        Returns:
            True if a drift checkpoint should be performed.
        """
        if step_number < 1:
            return False

        slider = GovernanceSlider(governance_slider)
        interval = CHECKPOINT_INTERVALS[slider]

        return step_number % interval == 0

    # ── Public: evaluate drift ────────────────────────────────

    def evaluate(
        self,
        *,
        state: ExecutionState,
        original_goal: str,
        budget: ResourceBudget,
        governance_slider: str = "STANDARD",
        step_number: int = 0,
        goal_similarity: float | None = None,
    ) -> DriftResponse:
        """Evaluate drift and produce a response action.

        Args:
            state: Current execution state snapshot.
            original_goal: The user's original goal/instruction.
            budget: Resource budget for the execution.
            governance_slider: Active governance preset.
            step_number: Current step number.
            goal_similarity: Pre-computed semantic similarity (0-1)
                between state summary and original goal.  If None,
                uses a simple word-overlap heuristic.

        Returns:
            DriftResponse with action, severity, and flags.
        """
        # Compute drift score
        dimensions = self._compute_dimensions(
            state, original_goal, budget, goal_similarity,
        )
        drift_score = self._weighted_score(dimensions)

        # Classify severity
        severity = self._classify(drift_score)

        # Look up action from matrix
        slider = GovernanceSlider(governance_slider)
        action = _DRIFT_RESPONSE_MATRIX[slider][severity]

        # Build checkpoint record
        checkpoint = DriftCheckpoint(
            step_number=step_number,
            drift_score=round(drift_score, 4),
            severity=severity,
            action=action,
            dimensions={k: round(v, 4) for k, v in dimensions.items()},
            message=self._build_message(severity, drift_score, action),
        )
        self._checkpoints.append(checkpoint)

        # Determine flags
        should_continue = action in (
            DriftAction.CONTINUE,
            DriftAction.CONTINUE_LOG,
            DriftAction.CONTINUE_NOTIFY,
            DriftAction.CONTINUE_ACKNOWLEDGE,
        )
        requires_human = action in _HUMAN_REQUIRED_ACTIONS
        requires_council = action in _COUNCIL_REQUIRED_ACTIONS
        requires_new_plan = action in _NEW_PLAN_ACTIONS

        logger.info(
            "drift.checkpoint",
            step=step_number,
            score=round(drift_score, 4),
            severity=severity.value,
            action=action.value,
            slider=slider.value,
            continue_=should_continue,
        )

        return DriftResponse(
            should_continue=should_continue,
            severity=severity,
            action=action,
            drift_score=round(drift_score, 4),
            checkpoint=checkpoint,
            message=checkpoint.message,
            requires_human=requires_human,
            requires_council=requires_council,
            requires_new_plan=requires_new_plan,
        )

    # ── Public: reset for new execution ───────────────────────

    def reset(self) -> None:
        """Clear checkpoint history for a new execution."""
        self._checkpoints.clear()

    # ── Public: get drift trend ───────────────────────────────

    def get_drift_trend(self) -> dict[str, Any]:
        """Analyze drift trend across recorded checkpoints.

        Returns:
            Dict with: checkpoint_count, scores, avg_score,
            trend (improving/stable/worsening), latest_severity.
        """
        if not self._checkpoints:
            return {
                "checkpoint_count": 0,
                "scores": [],
                "avg_score": 0.0,
                "trend": "no_data",
                "latest_severity": None,
            }

        scores = [c.drift_score for c in self._checkpoints]
        avg = sum(scores) / len(scores)

        # Trend: compare first half avg to second half avg
        if len(scores) >= 4:
            mid = len(scores) // 2
            first_half = sum(scores[:mid]) / mid
            second_half = sum(scores[mid:]) / (len(scores) - mid)
            delta = second_half - first_half
            if delta > 0.05:
                trend = "worsening"
            elif delta < -0.05:
                trend = "improving"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        return {
            "checkpoint_count": len(self._checkpoints),
            "scores": scores,
            "avg_score": round(avg, 4),
            "trend": trend,
            "latest_severity": self._checkpoints[-1].severity.value,
        }

    # ── Drift computation ─────────────────────────────────────

    @staticmethod
    def _compute_dimensions(
        state: ExecutionState,
        original_goal: str,
        budget: ResourceBudget,
        goal_similarity: float | None,
    ) -> dict[str, float]:
        """Compute the four drift dimensions.

        Returns dict with keys: goal_alignment_loss,
        plan_deviation_ratio, resource_overrun_ratio,
        side_effect_ratio.
        """
        # 1. Goal alignment loss (40% weight)
        if goal_similarity is not None:
            # Pre-computed embedding similarity provided
            goal_alignment_loss = 1.0 - max(0.0, min(1.0, goal_similarity))
        else:
            # Heuristic fallback: word overlap Jaccard
            goal_alignment_loss = 1.0 - DriftDetector._word_overlap(
                state.summary, original_goal,
            )

        # 2. Plan deviation ratio (30% weight)
        if state.total_steps > 0:
            plan_deviation_ratio = state.off_plan_steps / state.total_steps
        else:
            plan_deviation_ratio = 0.0

        # 3. Resource overrun ratio (15% weight)
        # Capped at 2x overrun → normalized to [0, 1]
        if budget.estimated_cost > 0.01:
            raw_overrun = state.actual_cost / budget.estimated_cost
        else:
            raw_overrun = 0.0
        resource_overrun_ratio = min(raw_overrun, 2.0) / 2.0

        # 4. Side effect ratio (15% weight)
        if state.total_effects > 0:
            side_effect_ratio = state.unplanned_effects / state.total_effects
        else:
            side_effect_ratio = 0.0

        return {
            "goal_alignment_loss": max(0.0, min(1.0, goal_alignment_loss)),
            "plan_deviation_ratio": max(0.0, min(1.0, plan_deviation_ratio)),
            "resource_overrun_ratio": max(0.0, min(1.0, resource_overrun_ratio)),
            "side_effect_ratio": max(0.0, min(1.0, side_effect_ratio)),
        }

    @staticmethod
    def _weighted_score(dimensions: dict[str, float]) -> float:
        """Apply the 4-dimension weighted formula.

        drift = goal_alignment_loss × 0.40
              + plan_deviation_ratio × 0.30
              + resource_overrun_ratio × 0.15
              + side_effect_ratio × 0.15
        """
        return (
            dimensions["goal_alignment_loss"] * 0.40
            + dimensions["plan_deviation_ratio"] * 0.30
            + dimensions["resource_overrun_ratio"] * 0.15
            + dimensions["side_effect_ratio"] * 0.15
        )

    @staticmethod
    def _classify(drift_score: float) -> DriftSeverity:
        """Classify drift score into severity bucket."""
        if drift_score < 0.3:
            return DriftSeverity.ON_TRACK
        if drift_score < 0.7:
            return DriftSeverity.DRIFTING
        return DriftSeverity.LOST

    # ── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _word_overlap(text_a: str, text_b: str) -> float:
        """Simple Jaccard word overlap as a goal-similarity heuristic.

        Returns a float in [0.0, 1.0].  This is a fallback for when
        no embedding similarity is available.
        """
        words_a = set(text_a.lower().split())
        words_b = set(text_b.lower().split())

        if not words_a or not words_b:
            return 0.0

        intersection = len(words_a & words_b)
        union = len(words_a | words_b)

        return intersection / union if union > 0 else 0.0

    @staticmethod
    def _build_message(
        severity: DriftSeverity,
        score: float,
        action: DriftAction,
    ) -> str:
        """Build a human-readable checkpoint message."""
        score_pct = f"{score:.1%}"

        if severity == DriftSeverity.ON_TRACK:
            return f"Checkpoint passed — drift {score_pct}, on track."
        if severity == DriftSeverity.DRIFTING:
            return (
                f"Drift detected ({score_pct}). "
                f"Action: {action.value.replace('_', ' ').lower()}."
            )
        return (
            f"Execution lost ({score_pct}). "
            f"Action: {action.value.replace('_', ' ').lower()}. "
            f"Immediate intervention required."
        )
