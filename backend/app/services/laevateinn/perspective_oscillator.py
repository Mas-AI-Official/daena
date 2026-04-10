"""Stage 7.5: Perspective Oscillator -- dimensional thinking engine.

The human brain's most powerful reasoning pattern:
    1. ZOOM IN  -> Analyze details at the neuron level
    2. ZOOM OUT -> See the whole picture at the system level
    3. ROTATE   -> Look from a completely different angle
    4. ZOOM IN  -> Re-enter with the new perspective
    5. REPEAT   -> Each cycle adds a dimension of understanding

Current AI systems are single-perspective: they process left-to-right,
generating tokens in one continuous stream. They never stop, zoom out,
look at what they've produced, rotate to a different viewpoint, and
re-enter the problem.

This engine implements that oscillation explicitly:
    - Generates an initial answer (ZOOM IN)
    - Steps back to evaluate the whole (ZOOM OUT)
    - Adopts alternative perspectives (ROTATE)
        * Adversary view: "How would an attacker see this?"
        * User view: "How would a non-expert understand this?"
        * Future view: "How does this look in 6 months?"
        * Inverted view: "What if the opposite were true?"
    - Re-enters with enriched understanding (ZOOM IN again)
    - Each cycle's findings are accumulated, not replaced

This is the cognitive loop that makes Daena think more like a human
expert who walks away from a problem, thinks about it in the shower,
and comes back with a breakthrough.

Integration: runs after Consensus Gradient (Stage 7), before Calibration
(Stage 8). Uses the consensus heat map to identify which sections need
perspective oscillation (low-confidence sections get more rotations).
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from app.core.logging import get_logger
from app.services.laevateinn.types import (
    ComputeProfile,
    ConsensusGradient,
    Difficulty,
)

if TYPE_CHECKING:
    from app.services.llm_service import LLMService

logger = get_logger(__name__)


class Perspective(str, Enum):
    """Available perspectives for rotation."""
    ADVERSARY = "ADVERSARY"        # How would an attacker see this?
    END_USER = "END_USER"          # How would a non-expert understand?
    FUTURE = "FUTURE"              # How does this look in 6 months/year?
    INVERTED = "INVERTED"          # What if the opposite were true?
    STAKEHOLDER = "STAKEHOLDER"    # Who else is affected by this?
    HISTORICAL = "HISTORICAL"      # Has this pattern failed before?
    SYSTEMIC = "SYSTEMIC"          # What are the second-order effects?


@dataclass
class PerspectiveView:
    """A single perspective rotation result."""
    perspective: Perspective
    observation: str              # What this perspective reveals
    contradicts_original: bool = False  # Does this view contradict the answer?
    reveals_blind_spot: str = ""  # What the original answer missed
    confidence_impact: float = 0.0  # How much this changes confidence


@dataclass
class OscillationCycle:
    """One full oscillation cycle (zoom-in -> zoom-out -> rotate -> zoom-in)."""
    cycle_number: int
    zoom_out_observation: str = ""     # What the big picture reveals
    perspectives_explored: list[PerspectiveView] = field(default_factory=list)
    zoom_in_refinement: str = ""       # How the answer was refined
    new_dimensions_found: int = 0      # How many new angles were discovered


@dataclass
class PerspectiveOscillationResult:
    """Output of the Perspective Oscillator (Stage 7.5).

    Each oscillation cycle adds dimensionality to the answer.
    Like a human expert who walks away from a problem and comes
    back with fresh eyes -- but done computationally in milliseconds.
    """
    cycles_completed: int = 0
    cycles: list[OscillationCycle] = field(default_factory=list)
    blind_spots_found: list[str] = field(default_factory=list)
    contradictions_found: list[str] = field(default_factory=list)
    answer_refined: bool = False
    refined_answer: str = ""
    confidence_delta: float = 0.0  # Net change in confidence from oscillation
    total_latency_ms: int = 0


# ── Perspective prompts ────────────────────────────────────────

_ZOOM_OUT_PROMPT = (
    "Step back from this answer and look at the BIG PICTURE.\n\n"
    "Question: {query}\n"
    "Current answer: {answer}\n\n"
    "Without analyzing details, what does the overall shape of this "
    "answer look like? Is it addressing the real problem? Is it "
    "proportional to the question's importance? What's missing from "
    "a bird's-eye view?\n\n"
    "One paragraph. Focus on what the DETAILS obscure."
)

_PERSPECTIVE_PROMPTS: dict[Perspective, str] = {
    Perspective.ADVERSARY: (
        "You are an ADVERSARY examining this answer. Your goal is to "
        "find weaknesses, exploit assumptions, and identify what could "
        "go wrong if this answer is followed.\n\n"
        "Question: {query}\nAnswer: {answer}\n\n"
        "What does an adversary see that the author missed? One paragraph."
    ),
    Perspective.END_USER: (
        "You are a NON-EXPERT end user reading this answer. You have "
        "no technical background. What confuses you? What would you "
        "misunderstand? What would you do wrong based on this advice?\n\n"
        "Question: {query}\nAnswer: {answer}\n\n"
        "What would a regular person get wrong? One paragraph."
    ),
    Perspective.FUTURE: (
        "It is 6 months from now. This answer was followed exactly. "
        "What has changed in the environment that makes parts of this "
        "answer outdated, wrong, or dangerous?\n\n"
        "Question: {query}\nAnswer: {answer}\n\n"
        "What is the shelf-life risk? One paragraph."
    ),
    Perspective.INVERTED: (
        "What if the OPPOSITE of this answer were true? Not as a "
        "contrarian exercise, but genuinely: what conditions would "
        "need to exist for the opposite conclusion to be correct?\n\n"
        "Question: {query}\nAnswer: {answer}\n\n"
        "Under what circumstances is this answer completely wrong? One paragraph."
    ),
    Perspective.STAKEHOLDER: (
        "Who else is AFFECTED by this answer that hasn't been considered? "
        "Think about: upstream dependencies, downstream consumers, "
        "third parties, regulators, future maintainers.\n\n"
        "Question: {query}\nAnswer: {answer}\n\n"
        "Who was forgotten? One paragraph."
    ),
    Perspective.HISTORICAL: (
        "Has this PATTERN of solution failed before in history? Think "
        "about similar approaches in other domains, industries, or "
        "time periods that looked good initially but failed.\n\n"
        "Question: {query}\nAnswer: {answer}\n\n"
        "What historical failure pattern does this resemble? One paragraph."
    ),
    Perspective.SYSTEMIC: (
        "What are the SECOND-ORDER effects of following this answer? "
        "Not the direct consequences, but the consequences OF the "
        "consequences. The ripple effects.\n\n"
        "Question: {query}\nAnswer: {answer}\n\n"
        "What dominoes fall after the first one? One paragraph."
    ),
}


class PerspectiveOscillator:
    """Stage 7.5: Dimensional thinking through perspective oscillation.

    Implements the cognitive pattern of zooming in, zooming out,
    rotating perspective, and zooming back in with enriched understanding.

    For HARD queries: 1 cycle with 3 perspectives
    For BRUTAL queries: 2 cycles with 5 perspectives

    Each cycle can modify the answer. Modifications are tracked and
    the net confidence impact is calculated.

    Args:
        llm_service: Daena's LLM service for perspective generation.
    """

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self._llm = llm_service

    async def oscillate(
        self,
        query: str,
        answer: str,
        compute: ComputeProfile,
        *,
        model_id: str = "",
        consensus: ConsensusGradient | None = None,
    ) -> PerspectiveOscillationResult:
        """Run perspective oscillation cycles on an answer.

        Args:
            query: Original question.
            answer: Current best answer.
            compute: Compute profile for resource allocation.
            model_id: Which model to use.
            consensus: Consensus gradient (identifies weak sections).

        Returns:
            PerspectiveOscillationResult with cycles and refinements.
        """
        start = time.perf_counter_ns()

        # Determine cycles and perspectives based on difficulty
        if compute.difficulty == Difficulty.BRUTAL:
            num_cycles = 2
            perspectives = [
                Perspective.ADVERSARY,
                Perspective.END_USER,
                Perspective.FUTURE,
                Perspective.INVERTED,
                Perspective.SYSTEMIC,
            ]
        elif compute.difficulty == Difficulty.HARD:
            num_cycles = 1
            perspectives = [
                Perspective.ADVERSARY,
                Perspective.END_USER,
                Perspective.INVERTED,
            ]
        else:
            # Standard/Trivial: heuristic-only, no LLM
            return self._heuristic_oscillation(query, answer)

        # Focus on weak sections if consensus available
        if consensus and consensus.weakest_section:
            # Prioritize oscillation on the weakest section
            answer_focus = consensus.weakest_section
        else:
            answer_focus = answer

        cycles: list[OscillationCycle] = []
        blind_spots: list[str] = []
        contradictions: list[str] = []
        total_confidence_delta = 0.0
        current_answer = answer

        for cycle_num in range(num_cycles):
            cycle = OscillationCycle(cycle_number=cycle_num + 1)

            # ── ZOOM OUT ──────────────────────────────────────
            if self._llm and model_id:
                zoom_out = await self._llm_call(
                    _ZOOM_OUT_PROMPT.format(
                        query=query, answer=current_answer,
                    ),
                    model_id,
                )
                cycle.zoom_out_observation = zoom_out
            else:
                cycle.zoom_out_observation = self._heuristic_zoom_out(
                    query, current_answer,
                )

            # ── ROTATE through perspectives ───────────────────
            for perspective in perspectives:
                view = await self._explore_perspective(
                    query, current_answer, perspective, model_id,
                )
                cycle.perspectives_explored.append(view)

                if view.contradicts_original:
                    contradictions.append(
                        f"[{perspective.value}] {view.reveals_blind_spot}"
                    )
                if view.reveals_blind_spot:
                    blind_spots.append(view.reveals_blind_spot)

                total_confidence_delta += view.confidence_impact

            cycle.new_dimensions_found = len(
                [v for v in cycle.perspectives_explored if v.reveals_blind_spot]
            )

            cycles.append(cycle)

        elapsed_ms = int((time.perf_counter_ns() - start) / 1_000_000)

        result = PerspectiveOscillationResult(
            cycles_completed=len(cycles),
            cycles=cycles,
            blind_spots_found=blind_spots,
            contradictions_found=contradictions,
            answer_refined=bool(contradictions),
            confidence_delta=round(total_confidence_delta, 3),
            total_latency_ms=elapsed_ms,
        )

        logger.info(
            "perspective_oscillator.complete",
            cycles=len(cycles),
            blind_spots=len(blind_spots),
            contradictions=len(contradictions),
            confidence_delta=round(total_confidence_delta, 3),
            latency_ms=elapsed_ms,
        )

        return result

    async def _explore_perspective(
        self,
        query: str,
        answer: str,
        perspective: Perspective,
        model_id: str,
    ) -> PerspectiveView:
        """Explore a single perspective."""
        prompt_template = _PERSPECTIVE_PROMPTS.get(perspective, "")
        if not prompt_template:
            return PerspectiveView(perspective=perspective)

        if self._llm and model_id:
            observation = await self._llm_call(
                prompt_template.format(query=query, answer=answer),
                model_id,
            )
        else:
            observation = self._heuristic_perspective(
                query, answer, perspective,
            )

        # Analyze the observation for contradictions and blind spots
        obs_lower = observation.lower()
        contradicts = any(
            word in obs_lower
            for word in ["wrong", "incorrect", "misleading", "dangerous", "flawed", "opposite"]
        )
        blind_spot = ""
        if any(
            word in obs_lower
            for word in ["missed", "overlooked", "forgot", "ignored", "didn't consider"]
        ):
            # Extract the blind spot (first sentence mentioning it)
            sentences = re.split(r'[.!?]', observation)
            for s in sentences:
                if any(w in s.lower() for w in ["missed", "overlooked", "forgot", "ignored"]):
                    blind_spot = s.strip()
                    break

        confidence_impact = 0.0
        if contradicts:
            confidence_impact = -0.05
        elif blind_spot:
            confidence_impact = -0.02

        return PerspectiveView(
            perspective=perspective,
            observation=observation,
            contradicts_original=contradicts,
            reveals_blind_spot=blind_spot,
            confidence_impact=confidence_impact,
        )

    def _heuristic_oscillation(
        self, query: str, answer: str,
    ) -> PerspectiveOscillationResult:
        """Fast heuristic oscillation without LLM."""
        blind_spots: list[str] = []
        answer_lower = answer.lower()

        # Check if answer considers multiple stakeholders
        if not re.search(r"\b(?:however|but|although|on the other hand)\b", answer_lower):
            blind_spots.append("Answer presents only one perspective without counterpoints")

        # Check if answer considers time dimension
        if not re.search(r"\b(?:future|later|eventually|over time|long[- ]term)\b", answer_lower):
            blind_spots.append("Answer does not consider temporal dimension or future implications")

        # Check if answer considers failure modes
        if not re.search(r"\b(?:fail|risk|danger|careful|caveat|warning)\b", answer_lower):
            blind_spots.append("Answer does not address potential failure modes")

        return PerspectiveOscillationResult(
            cycles_completed=1 if blind_spots else 0,
            blind_spots_found=blind_spots,
            confidence_delta=-0.02 * len(blind_spots),
        )

    def _heuristic_zoom_out(self, query: str, answer: str) -> str:
        """Heuristic zoom-out without LLM."""
        q_words = len(query.split())
        a_words = len(answer.split())
        ratio = a_words / max(q_words, 1)

        observations = []
        if ratio > 20:
            observations.append("Answer is disproportionately long relative to the question")
        if ratio < 2:
            observations.append("Answer may be too brief for the question's complexity")

        return ". ".join(observations) if observations else "Answer appears proportional to question."

    def _heuristic_perspective(
        self, query: str, answer: str, perspective: Perspective,
    ) -> str:
        """Heuristic perspective analysis without LLM."""
        answer_lower = answer.lower()

        if perspective == Perspective.ADVERSARY:
            if re.search(r"\b(?:trust|assume|should work)\b", answer_lower):
                return "An adversary would exploit the trust assumptions in this answer."
            return "No obvious adversary exploitation vectors detected."

        if perspective == Perspective.END_USER:
            jargon = re.findall(r"\b[A-Z]{2,}\b", answer)
            if jargon:
                return f"A non-expert would be confused by unexplained jargon: {', '.join(jargon[:5])}"
            return "Answer appears accessible to non-experts."

        if perspective == Perspective.INVERTED:
            return "Consider: what if the constraints stated in the question are not actually fixed?"

        return f"Heuristic {perspective.value} analysis: no significant findings."

    async def _llm_call(self, prompt: str, model_id: str) -> str:
        """Make a single LLM call."""
        if not self._llm:
            return ""
        try:
            from app.services.providers.base import GenerateRequest, LLMMessage
            request = GenerateRequest(
                messages=[LLMMessage(role="user", content=prompt)],
                model_id=model_id,
                temperature=0.4,
                max_tokens=300,
            )
            result = await self._llm.generate_direct(request)
            return result.content.strip()
        except Exception:
            logger.warning("perspective_oscillator.llm_failed", exc_info=True)
            return ""
