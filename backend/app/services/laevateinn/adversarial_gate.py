"""Stage 5.5: Adversarial Verification Gate.

The capability NO other agent system has. After validation passes,
before delivery, this gate asks:

    "If this answer is WRONG, what evidence would I expect to see?"

Then it CHECKS for that evidence using the cheapest available model.
If counter-evidence is found, the answer loops back to RDE for correction.
If not found, confidence gets a boost and the answer ships.

This is the difference between "I think I'm right" (every other agent)
and "I tried to prove myself wrong and couldn't" (Laevateinn).

Research basis: Modus tollens verification -- instead of confirming
the answer (confirmation bias), actively seek disconfirming evidence.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.services.laevateinn.types import (
    AdversarialGateResult,
    ComputeProfile,
    Difficulty,
)

if TYPE_CHECKING:
    from app.services.llm_service import LLMService

logger = get_logger(__name__)

_COUNTER_EVIDENCE_PROMPT = (
    "You are a rigorous falsification engine. Given this answer to a question, "
    "generate a SPECIFIC prediction: if this answer is WRONG, what observable "
    "evidence would you expect to find? Be concrete -- name specific things "
    "that would be true if the answer is incorrect.\n\n"
    "Question: {query}\n"
    "Answer: {answer}\n\n"
    "If this answer is wrong, I would expect to see:\n"
    "(List 2-4 specific, checkable predictions)"
)

_EVIDENCE_CHECK_PROMPT = (
    "Check whether the following counter-evidence claims are true or false. "
    "For each, state TRUE (evidence exists) or FALSE (evidence does not exist) "
    "with a one-line explanation.\n\n"
    "Counter-evidence to check:\n{predictions}\n\n"
    "Context (original question): {query}\n"
    "Context (original answer): {answer}\n\n"
    "For each prediction, respond with:\n"
    "PREDICTION: [the prediction]\n"
    "VERDICT: TRUE or FALSE\n"
    "REASON: [one line]"
)


class AdversarialVerificationGate:
    """Stage 5.5: the final gate between validation and delivery.

    Protocol:
        1. Generate counter-evidence predictions (what would be true if wrong?)
        2. Check each prediction using cheapest model
        3. If any counter-evidence confirmed: loop back to RDE
        4. If all predictions fail to find evidence: boost confidence, deliver

    This gate uses the CHEAPEST available model for checking (Ollama 7B)
    to keep costs near zero. The expensive model already generated the answer;
    the cheap model just tries to poke holes in it.

    Args:
        llm_service: Daena's LLM service for model calls.
    """

    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service

    async def verify(
        self,
        query: str,
        answer: str,
        compute: ComputeProfile,
        *,
        model_id: str = "",
        cheap_model_id: str = "",
    ) -> AdversarialGateResult:
        """Run the adversarial verification gate.

        Args:
            query: Original user query.
            answer: The answer that passed validation.
            compute: Compute profile for budget awareness.
            model_id: Primary model (used for prediction generation).
            cheap_model_id: Cheapest model (used for evidence checking).

        Returns:
            AdversarialGateResult with pass/fail and evidence details.
        """
        start = time.perf_counter_ns()

        # Skip for trivial queries -- not worth the cost
        if compute.difficulty == Difficulty.TRIVIAL:
            return AdversarialGateResult(
                passed=True,
                counter_evidence_absent=True,
                confidence_boost=0.0,
            )

        # Use cheap model for checking, primary for prediction
        check_model = cheap_model_id or model_id

        # Step 1: Generate counter-evidence predictions
        predictions = await self._generate_counter_predictions(
            query, answer, model_id
        )

        if not predictions:
            # Could not generate predictions -- pass by default
            elapsed = int((time.perf_counter_ns() - start) / 1_000_000)
            return AdversarialGateResult(
                passed=True,
                counter_evidence_absent=True,
                confidence_boost=0.05,
                total_latency_ms=elapsed,
            )

        counter_query = "\n".join(f"- {p}" for p in predictions)

        # Step 2: Check each prediction using cheap model
        evidence_found = await self._check_evidence(
            query, answer, predictions, check_model
        )

        elapsed = int((time.perf_counter_ns() - start) / 1_000_000)

        if evidence_found:
            # Counter-evidence confirmed -- answer may be wrong
            logger.warning(
                "adversarial_gate_failed",
                evidence_count=len(evidence_found),
                evidence=evidence_found[:2],
                elapsed_ms=elapsed,
            )
            return AdversarialGateResult(
                passed=False,
                counter_evidence_query=counter_query,
                counter_evidence_found=evidence_found,
                counter_evidence_absent=False,
                confidence_boost=-0.15,
                loops_back=True,
                total_latency_ms=elapsed,
            )

        # No counter-evidence found -- answer survives falsification
        logger.info(
            "adversarial_gate_passed",
            predictions_checked=len(predictions),
            elapsed_ms=elapsed,
        )

        # Confidence boost scales with difficulty
        boost_map = {
            Difficulty.STANDARD: 0.05,
            Difficulty.HARD: 0.10,
            Difficulty.BRUTAL: 0.15,
        }
        boost = boost_map.get(compute.difficulty, 0.05)

        return AdversarialGateResult(
            passed=True,
            counter_evidence_query=counter_query,
            counter_evidence_found=[],
            counter_evidence_absent=True,
            confidence_boost=boost,
            loops_back=False,
            total_latency_ms=elapsed,
        )

    async def _generate_counter_predictions(
        self, query: str, answer: str, model_id: str,
    ) -> list[str]:
        """Generate specific predictions of what would be true if answer is wrong."""
        from app.services.providers.base import GenerateRequest, LLMMessage

        prompt = _COUNTER_EVIDENCE_PROMPT.format(query=query, answer=answer)
        messages = [LLMMessage(role="user", content=prompt)]

        request = GenerateRequest(
            messages=messages,
            model_id=model_id,
            temperature=0.3,
            max_tokens=512,
        )

        try:
            result = await self._llm.generate_direct(request)
            return self._parse_predictions(result.content)
        except Exception as e:
            logger.warning("adversarial_gate_predict_failed", error=str(e))
            return []

    async def _check_evidence(
        self,
        query: str,
        answer: str,
        predictions: list[str],
        check_model: str,
    ) -> list[str]:
        """Check each prediction using cheap model. Returns confirmed evidence."""
        from app.services.providers.base import GenerateRequest, LLMMessage

        predictions_text = "\n".join(f"{i+1}. {p}" for i, p in enumerate(predictions))

        prompt = _EVIDENCE_CHECK_PROMPT.format(
            predictions=predictions_text,
            query=query,
            answer=answer,
        )
        messages = [LLMMessage(role="user", content=prompt)]

        request = GenerateRequest(
            messages=messages,
            model_id=check_model,
            temperature=0.1,  # Very low -- factual checking
            max_tokens=512,
        )

        try:
            result = await self._llm.generate_direct(request)
            return self._parse_evidence_check(result.content)
        except Exception as e:
            logger.warning("adversarial_gate_check_failed", error=str(e))
            return []  # Fail open -- if check fails, pass the gate

    def _parse_predictions(self, text: str) -> list[str]:
        """Parse LLM output into counter-evidence predictions."""
        import re
        predictions: list[str] = []

        lines = text.strip().split("\n")
        for line in lines:
            line = line.strip()
            match = re.match(r"(?:[\d]+[.)]\s*|-\s*|\*\s*)(.*)", line)
            if match:
                pred = match.group(1).strip()
                if len(pred) > 15:
                    predictions.append(pred)

        return predictions[:4]  # Cap at 4 predictions

    def _parse_evidence_check(self, text: str) -> list[str]:
        """Parse evidence check results. Returns list of confirmed evidence."""
        import re
        confirmed: list[str] = []

        # Look for VERDICT: TRUE patterns
        blocks = re.split(r"PREDICTION:", text, flags=re.IGNORECASE)
        for block in blocks[1:]:  # Skip first empty split
            verdict_match = re.search(
                r"VERDICT:\s*(TRUE|FALSE)", block, re.IGNORECASE
            )
            if verdict_match and verdict_match.group(1).upper() == "TRUE":
                # Extract the prediction text
                pred_text = block.split("\n")[0].strip()
                if pred_text:
                    confirmed.append(pred_text)

        return confirmed
