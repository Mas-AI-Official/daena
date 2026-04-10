"""Epistemic State Tracker -- knows WHAT it doesn't know and WHY.

Beyond Mythos: Mythos has metacognitive awareness but treats all
uncertainty the same way. Laevateinn tracks the SHAPE of uncertainty
and routes each shape to its optimal resolution strategy.

Four shapes of uncertainty:
    CONTRADICTORY -- evidence conflicts -> trigger deeper AMD debate
    ABSENT -- no evidence exists -> trigger tool use / web search
    AMBIGUOUS -- multiple valid interpretations -> re-comprehend via DCE
    COMPUTATIONAL -- can't verify analytically -> execute code
    CONFIDENT -- low uncertainty -> proceed normally

Integration: runs after DCE (Stage 1) to classify uncertainty,
then feeds into DCS (Stage 2) to adjust compute allocation.
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.services.laevateinn.types import (
    ComprehensionResult,
    EpistemicState,
    ReasoningStrategy,
    UncertaintyShape,
)

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# Signal patterns for each uncertainty shape
_CONTRADICTORY_SIGNALS: list[str] = [
    r"\bhowever\b", r"\bon the other hand\b", r"\bcontrovers",
    r"\bdebat", r"\bdisagree", r"\bconflict", r"\bcontraddict",
    r"\bsome say\b.*\bothers\b", r"\bvs\.?\b", r"\bversus\b",
]

_ABSENT_SIGNALS: list[str] = [
    r"\bunknown\b", r"\bno data\b", r"\bno research\b",
    r"\bnot well.?understood\b", r"\bunanswered\b",
    r"\bopen question\b", r"\bno consensus\b",
    r"\bnew\b.*\bfield\b", r"\bemerging\b",
]

_AMBIGUOUS_SIGNALS: list[str] = [
    r"\bdepends on\b", r"\bit depends\b", r"\bcontext.?dependent\b",
    r"\bsubjective\b", r"\bopinion\b", r"\bmultiple ways\b",
    r"\bvarious\b.*\bapproach", r"\bambiguous\b",
]

_COMPUTATIONAL_SIGNALS: list[str] = [
    r"\bcalculat", r"\bcompute\b", r"\brun\b.*\bcode\b",
    r"\bexecut", r"\bsimulat", r"\bbenchmark\b",
    r"\bperformance\b.*\btest", r"\bprofile\b",
]


class EpistemicStateTracker:
    """Tracks the shape of uncertainty in a reasoning pass.

    Unlike simple confidence scores (0.0-1.0), this tracks WHY
    confidence is low and what to DO about it.

    Usage::

        tracker = EpistemicStateTracker()
        state = tracker.analyze(comprehension_result)
        # state.shape tells you WHAT kind of uncertainty
        # state.recommended_action tells you WHAT TO DO

    The tracker also recommends which ReasoningStrategy to use
    based on the problem type and uncertainty shape.
    """

    def analyze(
        self,
        comprehension: ComprehensionResult,
        *,
        prior_failures: list[str] | None = None,
    ) -> EpistemicState:
        """Analyze a comprehended query for epistemic uncertainty.

        Args:
            comprehension: Output from DCE (Stage 1).
            prior_failures: Previous failure reasons (for reshaping strategy).

        Returns:
            EpistemicState with classified uncertainty and action.
        """
        query = comprehension.original_query
        query_lower = query.lower()

        # Score each uncertainty shape
        scores = {
            UncertaintyShape.CONTRADICTORY: self._score_signals(
                query_lower, _CONTRADICTORY_SIGNALS
            ),
            UncertaintyShape.ABSENT: self._score_signals(
                query_lower, _ABSENT_SIGNALS
            ),
            UncertaintyShape.AMBIGUOUS: self._score_signals(
                query_lower, _AMBIGUOUS_SIGNALS
            ),
            UncertaintyShape.COMPUTATIONAL: self._score_signals(
                query_lower, _COMPUTATIONAL_SIGNALS
            ),
        }

        # Boost ambiguity score if DCE found multiple high-probability interpretations
        high_prob_interps = [
            i for i in comprehension.interpretations if i.probability > 0.25
        ]
        if len(high_prob_interps) >= 2:
            scores[UncertaintyShape.AMBIGUOUS] += 2

        # Boost contradictory if assumptions were surfaced
        if comprehension.hidden_assumptions:
            scores[UncertaintyShape.CONTRADICTORY] += len(
                comprehension.hidden_assumptions
            )

        # Boost absent if sub-questions exist (complex, may lack evidence)
        if len(comprehension.sub_questions) > 2:
            scores[UncertaintyShape.ABSENT] += 1

        # Factor in prior failures
        if prior_failures:
            # Failures suggest current approach is wrong -> boost contradictory
            scores[UncertaintyShape.CONTRADICTORY] += len(prior_failures)

        # Select dominant shape
        best_shape = max(scores, key=lambda s: scores[s])
        best_score = scores[best_shape]

        # If no strong signal, we're confident
        if best_score < 2:
            best_shape = UncertaintyShape.CONFIDENT

        # Build evidence lists
        evidence_for, evidence_against, missing = self._gather_evidence(
            comprehension, best_shape
        )

        # Determine confidence bounds
        floor, ceiling = self._confidence_bounds(best_shape, best_score)

        # Recommend action
        action = self._recommend_action(best_shape, comprehension)

        state = EpistemicState(
            shape=best_shape,
            confidence_floor=floor,
            confidence_ceiling=ceiling,
            evidence_for=evidence_for,
            evidence_against=evidence_against,
            missing_evidence=missing,
            recommended_action=action,
        )

        logger.info(
            "epistemic_state",
            shape=best_shape.value,
            floor=floor,
            ceiling=ceiling,
            action=action,
        )

        return state

    def recommend_strategy(
        self,
        comprehension: ComprehensionResult,
        epistemic: EpistemicState,
    ) -> ReasoningStrategy:
        """Recommend a reasoning strategy based on problem + uncertainty.

        This is the Meta-Strategy Selector -- chooses HOW to reason
        before the reasoning starts.

        Args:
            comprehension: DCE output.
            epistemic: Analyzed epistemic state.

        Returns:
            ReasoningStrategy for the pipeline to use.
        """
        from app.services.laevateinn.types import BloomLevel

        # Contradictory evidence -> need depth-first to resolve conflicts
        if epistemic.shape == UncertaintyShape.CONTRADICTORY:
            return ReasoningStrategy.DEPTH_FIRST

        # Ambiguous query -> breadth-first to explore interpretations
        if epistemic.shape == UncertaintyShape.AMBIGUOUS:
            return ReasoningStrategy.BREADTH_FIRST

        # Computational uncertainty -> hypothesis-driven (test and check)
        if epistemic.shape == UncertaintyShape.COMPUTATIONAL:
            return ReasoningStrategy.HYPOTHESIS_DRIVEN

        # CREATE-level bloom -> analogical (import from other domains)
        if comprehension.bloom_level == BloomLevel.CREATE:
            return ReasoningStrategy.ANALOGICAL

        # ANALYZE-level with constraints -> constraint propagation
        if comprehension.bloom_level == BloomLevel.ANALYZE:
            if comprehension.hidden_assumptions:
                return ReasoningStrategy.CONSTRAINT_PROPAGATION

        return ReasoningStrategy.STANDARD

    def _score_signals(self, text: str, patterns: list[str]) -> int:
        """Count how many signal patterns match in the text."""
        return sum(1 for p in patterns if re.search(p, text, re.IGNORECASE))

    def _gather_evidence(
        self,
        comprehension: ComprehensionResult,
        shape: UncertaintyShape,
    ) -> tuple[list[str], list[str], list[str]]:
        """Gather evidence for/against/missing based on shape."""
        evidence_for: list[str] = []
        evidence_against: list[str] = []
        missing: list[str] = []

        if comprehension.hidden_assumptions:
            for a in comprehension.hidden_assumptions:
                evidence_against.append(f"Hidden assumption: {a}")

        if len(comprehension.sub_questions) > 1:
            for sq in comprehension.sub_questions[1:]:
                missing.append(f"Sub-question needs answer: {sq[:80]}")

        if comprehension.real_question != comprehension.noise_eliminated:
            evidence_for.append(
                f"Real question identified: {comprehension.real_question[:80]}"
            )

        if shape == UncertaintyShape.ABSENT:
            missing.append("Topic may lack established research or data")

        if shape == UncertaintyShape.CONTRADICTORY:
            evidence_against.append("Query contains conflicting signals")

        return evidence_for, evidence_against, missing

    def _confidence_bounds(
        self, shape: UncertaintyShape, signal_strength: int,
    ) -> tuple[float, float]:
        """Calculate confidence floor and ceiling based on uncertainty shape."""
        bounds = {
            UncertaintyShape.CONFIDENT: (0.7, 0.95),
            UncertaintyShape.AMBIGUOUS: (0.3, 0.7),
            UncertaintyShape.ABSENT: (0.2, 0.6),
            UncertaintyShape.CONTRADICTORY: (0.15, 0.55),
            UncertaintyShape.COMPUTATIONAL: (0.4, 0.8),
        }
        floor, ceiling = bounds.get(shape, (0.3, 0.7))

        # Stronger signals narrow the band downward
        penalty = min(signal_strength * 0.03, 0.15)
        return max(0.1, floor - penalty), max(floor, ceiling - penalty)

    def _recommend_action(
        self,
        shape: UncertaintyShape,
        comprehension: ComprehensionResult,
    ) -> str:
        """Recommend what to do about this type of uncertainty."""
        actions = {
            UncertaintyShape.CONFIDENT: "proceed_normal",
            UncertaintyShape.CONTRADICTORY: "deepen_debate",
            UncertaintyShape.ABSENT: "search_external",
            UncertaintyShape.AMBIGUOUS: "re_comprehend",
            UncertaintyShape.COMPUTATIONAL: "execute_code",
        }
        return actions.get(shape, "proceed_normal")
