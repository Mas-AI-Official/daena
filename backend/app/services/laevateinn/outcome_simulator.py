"""P3: Outcome Simulator -- predict what happens if you follow the advice.

Beyond Mythos: before delivering, simulate 2-3 scenarios of what happens
if the user follows this advice. Flag catastrophic outcomes BEFORE they
happen. This is predictive safety -- catching bad advice at generation
time, not after the user acts on it.

Integration: runs after Adversarial Gate, before Delivery.
Can BLOCK delivery if catastrophic risk detected.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.services.laevateinn.types import (
    ComputeProfile,
    Difficulty,
    OutcomeSimulationResult,
    SimulatedOutcome,
)

if TYPE_CHECKING:
    from app.services.llm_service import LLMService

logger = get_logger(__name__)

_SIMULATE_PROMPT = (
    "You gave advice in response to a question. Now SIMULATE what happens "
    "if the user follows your advice exactly as given.\n\n"
    "Question: {query}\n"
    "Your advice: {answer}\n\n"
    "Generate 3 scenarios:\n"
    "1. BEST CASE: what happens if everything goes right\n"
    "2. LIKELY CASE: what realistically happens\n"
    "3. WORST CASE: what happens if things go wrong\n\n"
    "For each scenario:\n"
    "SCENARIO: [brief description]\n"
    "OUTCOME: [what results from following the advice]\n"
    "SEVERITY: [low|medium|high|catastrophic]\n"
    "PROBABILITY: [0.0-1.0]\n"
    "MITIGATION: [how to prevent the worst case, if applicable]"
)

# Heuristic patterns that suggest dangerous advice
_DANGER_PATTERNS = {
    "catastrophic": [
        r"\bdelete\b.*\bproduction\b", r"\bdrop\b.*\btable\b",
        r"\brm\s+-rf\b", r"\bforce\s+push\b.*\bmain\b",
        r"\bformat\b.*\bdisk\b", r"\bdisable\b.*\bfirewall\b",
        r"\bshare\b.*\bpassword\b", r"\bexpose\b.*\bsecret\b",
    ],
    "high": [
        r"\boverwrite\b", r"\breplace\b.*\ball\b",
        r"\bdeploy\b.*\bwithout\b.*\btest\b",
        r"\bskip\b.*\bvalidat\b", r"\bdisable\b.*\blog\b",
        r"\bignore\b.*\berror\b", r"\bcatch\b.*\bpass\b",
    ],
    "medium": [
        r"\bdowngrade\b", r"\bremove\b.*\bdependen\b",
        r"\bchange\b.*\bschema\b", r"\bmigrat\b",
        r"\bglobal\b.*\binstall\b",
    ],
}


class OutcomeSimulator:
    """Simulates what happens if the user follows the advice.

    Three simulation modes:
    1. Heuristic: pattern-match for dangerous operations (free, instant)
    2. LLM: generate best/likely/worst case scenarios (cheap model)
    3. Combined: heuristic flags + LLM scenarios (for HARD/BRUTAL)

    If a catastrophic outcome is detected, the answer can be flagged
    for human review before delivery.

    Args:
        llm_service: Daena's LLM service.
    """

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self._llm = llm_service

    async def simulate(
        self,
        query: str,
        answer: str,
        compute: ComputeProfile,
        *,
        model_id: str = "",
    ) -> OutcomeSimulationResult:
        """Simulate outcomes of following the answer.

        Args:
            query: Original question.
            answer: The advice/answer to simulate.
            compute: Compute profile.
            model_id: Model for LLM simulation.

        Returns:
            OutcomeSimulationResult with scenarios and risk flags.
        """
        start = time.perf_counter_ns()

        # Always run heuristic scan (free)
        heuristic_outcomes = self._heuristic_scan(query, answer)
        catastrophic_risks = [
            o.scenario for o in heuristic_outcomes
            if o.severity == "catastrophic"
        ]

        outcomes = heuristic_outcomes

        # LLM simulation for non-trivial queries
        if (
            compute.difficulty in (Difficulty.HARD, Difficulty.BRUTAL)
            and self._llm and model_id
        ):
            llm_outcomes = await self._llm_simulate(query, answer, model_id)
            outcomes.extend(llm_outcomes)

            # Check LLM outcomes for catastrophic risks
            for o in llm_outcomes:
                if o.severity == "catastrophic":
                    catastrophic_risks.append(o.scenario)

        safe = len(catastrophic_risks) == 0
        worst = ""
        if outcomes:
            worst_outcome = max(
                outcomes,
                key=lambda o: {"low": 0, "medium": 1, "high": 2, "catastrophic": 3}.get(o.severity, 0),
            )
            worst = f"{worst_outcome.scenario}: {worst_outcome.outcome}"

        elapsed = int((time.perf_counter_ns() - start) / 1_000_000)

        logger.info(
            "outcome_simulation_complete",
            outcomes=len(outcomes),
            catastrophic=len(catastrophic_risks),
            safe=safe,
            elapsed_ms=elapsed,
        )

        return OutcomeSimulationResult(
            outcomes=outcomes,
            catastrophic_risks=catastrophic_risks,
            safe_to_deliver=safe,
            worst_case=worst,
            total_latency_ms=elapsed,
        )

    def _heuristic_scan(
        self, query: str, answer: str,
    ) -> list[SimulatedOutcome]:
        """Scan for dangerous patterns without LLM (instant, free)."""
        import re
        outcomes: list[SimulatedOutcome] = []
        combined = (query + " " + answer).lower()

        for severity, patterns in _DANGER_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, combined, re.IGNORECASE):
                    match_text = re.search(pattern, combined, re.IGNORECASE)
                    context = combined[max(0, match_text.start()-20):match_text.end()+20] if match_text else ""
                    outcomes.append(SimulatedOutcome(
                        scenario=f"Dangerous operation detected: {pattern}",
                        outcome=f"Following this advice could cause {severity} impact near: ...{context}...",
                        severity=severity,
                        probability=0.3 if severity == "catastrophic" else 0.5,
                        mitigation=f"Review and confirm before executing any {severity}-risk operations",
                    ))

        return outcomes

    async def _llm_simulate(
        self, query: str, answer: str, model_id: str,
    ) -> list[SimulatedOutcome]:
        """Generate outcome scenarios using LLM."""
        from app.services.providers.base import GenerateRequest, LLMMessage

        prompt = _SIMULATE_PROMPT.format(
            query=query[:300], answer=answer[:500],
        )
        messages = [LLMMessage(role="user", content=prompt)]

        request = GenerateRequest(
            messages=messages,
            model_id=model_id,
            temperature=0.4,
            max_tokens=768,
        )

        try:
            result = await self._llm.generate_direct(request)
            return self._parse_outcomes(result.content)
        except Exception as e:
            logger.warning("outcome_simulate_failed", error=str(e))
            return []

    def _parse_outcomes(self, text: str) -> list[SimulatedOutcome]:
        """Parse LLM outcome simulation output."""
        import re
        outcomes: list[SimulatedOutcome] = []

        blocks = re.split(r"SCENARIO:\s*", text, flags=re.IGNORECASE)

        for block in blocks[1:]:
            scenario = block.split("\n")[0].strip()

            outcome_match = re.search(r"OUTCOME:\s*(.+?)(?:\n|$)", block, re.IGNORECASE)
            outcome = outcome_match.group(1).strip() if outcome_match else ""

            severity_match = re.search(r"SEVERITY:\s*(\w+)", block, re.IGNORECASE)
            severity = severity_match.group(1).strip().lower() if severity_match else "medium"
            if severity not in ("low", "medium", "high", "catastrophic"):
                severity = "medium"

            prob_match = re.search(r"PROBABILITY:\s*([0-9.]+)", block, re.IGNORECASE)
            probability = float(prob_match.group(1)) if prob_match else 0.5

            mit_match = re.search(r"MITIGATION:\s*(.+?)(?:\n|$)", block, re.IGNORECASE)
            mitigation = mit_match.group(1).strip() if mit_match else ""

            if scenario and outcome:
                outcomes.append(SimulatedOutcome(
                    scenario=scenario,
                    outcome=outcome,
                    severity=severity,
                    probability=min(probability, 1.0),
                    mitigation=mitigation,
                ))

        return outcomes[:3]
