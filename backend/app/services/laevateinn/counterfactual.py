"""P2: Counterfactual Engine -- "What if the answer were different?"

Beyond Mythos: after generating an answer, ask what conditions would need
to be true for a DIFFERENT answer to be correct. This reveals:
    - Hidden assumptions you didn't know you were making
    - Alternative solutions you didn't consider
    - Unstated requirements that constrain the solution space

If the counterfactual conditions are plausible, the original answer
needs revision or at minimum a confidence penalty.

Integration: runs between Validation Gauntlet and Adversarial Gate.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.services.laevateinn.types import (
    ComputeProfile,
    CounterfactualBranch,
    CounterfactualResult,
    Difficulty,
)

if TYPE_CHECKING:
    from app.services.llm_service import LLMService

logger = get_logger(__name__)

_COUNTERFACTUAL_PROMPT = (
    "You answered a question. Now explore ALTERNATIVE conclusions.\n\n"
    "Question: {query}\n"
    "Your answer/conclusion: {answer}\n\n"
    "Generate 2-3 alternative conclusions that are DIFFERENT from yours. "
    "For each alternative:\n"
    "ALTERNATIVE: [a different conclusion]\n"
    "CONDITIONS: [what would have to be true for this to be the right answer]\n"
    "PLAUSIBILITY: [0.0-1.0 how plausible are these conditions]\n"
    "REVEALS: [what hidden assumption in the original answer this exposes]\n\n"
    "Focus on alternatives that are genuinely plausible, not strawmen."
)


class CounterfactualEngine:
    """Generates alternative conclusions and traces conditions for each.

    The power of counterfactual reasoning: if a DIFFERENT answer is
    plausible, the original answer's confidence should decrease.
    If no plausible alternatives exist, confidence increases.

    This catches the failure mode where an answer is correct but
    FRAGILE -- small changes in assumptions would flip the conclusion.

    Args:
        llm_service: Daena's LLM service.
    """

    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service

    async def analyze(
        self,
        query: str,
        answer: str,
        compute: ComputeProfile,
        *,
        model_id: str = "",
    ) -> CounterfactualResult:
        """Generate counterfactual branches for an answer.

        Args:
            query: Original question.
            answer: The answer to analyze counterfactually.
            compute: Compute profile for budget awareness.
            model_id: Model to use.

        Returns:
            CounterfactualResult with alternatives and hidden assumptions.
        """
        start = time.perf_counter_ns()

        if compute.difficulty == Difficulty.TRIVIAL:
            return CounterfactualResult(
                original_conclusion=answer[:200],
                confidence_impact=0.0,
            )

        # Generate counterfactual branches
        branches = await self._generate_branches(query, answer, model_id)

        # Analyze impact on confidence
        hidden_assumptions: list[str] = []
        max_plausibility = 0.0

        for branch in branches:
            if branch.reveals:
                hidden_assumptions.append(branch.reveals)
            max_plausibility = max(max_plausibility, branch.plausibility)

        # High plausibility alternatives = lower confidence in original
        # Low plausibility alternatives = confirmation of original
        if max_plausibility > 0.6:
            confidence_impact = -(max_plausibility * 0.2)
        elif max_plausibility < 0.2:
            confidence_impact = 0.05  # Slight boost -- no plausible alternatives
        else:
            confidence_impact = 0.0

        elapsed = int((time.perf_counter_ns() - start) / 1_000_000)

        logger.info(
            "counterfactual_complete",
            branches=len(branches),
            max_plausibility=max_plausibility,
            hidden_assumptions=len(hidden_assumptions),
            confidence_impact=confidence_impact,
            elapsed_ms=elapsed,
        )

        return CounterfactualResult(
            original_conclusion=answer[:200],
            alternatives=branches,
            hidden_assumptions_found=hidden_assumptions,
            confidence_impact=confidence_impact,
            total_latency_ms=elapsed,
        )

    async def _generate_branches(
        self, query: str, answer: str, model_id: str,
    ) -> list[CounterfactualBranch]:
        """Generate counterfactual branches using LLM."""
        from app.services.providers.base import GenerateRequest, LLMMessage

        prompt = _COUNTERFACTUAL_PROMPT.format(
            query=query, answer=answer[:500],
        )
        messages = [LLMMessage(role="user", content=prompt)]

        request = GenerateRequest(
            messages=messages,
            model_id=model_id,
            temperature=0.5,  # Higher temp for creative alternatives
            max_tokens=1024,
        )

        try:
            result = await self._llm.generate_direct(request)
            return self._parse_branches(result.content)
        except Exception as e:
            logger.warning("counterfactual_generate_failed", error=str(e))
            return []

    def _parse_branches(self, text: str) -> list[CounterfactualBranch]:
        """Parse LLM output into counterfactual branches."""
        import re
        branches: list[CounterfactualBranch] = []

        # Split by ALTERNATIVE markers
        blocks = re.split(r"ALTERNATIVE:\s*", text, flags=re.IGNORECASE)

        for block in blocks[1:]:  # Skip first empty split
            alt_text = block.split("\n")[0].strip()

            conditions_match = re.search(
                r"CONDITIONS?:\s*(.+?)(?:\n|$)", block, re.IGNORECASE
            )
            conditions = []
            if conditions_match:
                cond_text = conditions_match.group(1).strip()
                conditions = [c.strip() for c in re.split(r"[;,]|\band\b", cond_text) if c.strip()]

            plausibility_match = re.search(
                r"PLAUSIBILITY:\s*([0-9.]+)", block, re.IGNORECASE
            )
            plausibility = float(plausibility_match.group(1)) if plausibility_match else 0.3

            reveals_match = re.search(
                r"REVEALS?:\s*(.+?)(?:\n|$)", block, re.IGNORECASE
            )
            reveals = reveals_match.group(1).strip() if reveals_match else ""

            if alt_text:
                branches.append(CounterfactualBranch(
                    alternative_conclusion=alt_text,
                    required_conditions=conditions,
                    plausibility=min(plausibility, 1.0),
                    reveals=reveals,
                ))

        return branches[:3]  # Cap at 3 branches
