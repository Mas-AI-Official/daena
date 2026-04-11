"""Council Engine — multi-model debate and synthesis.

Implements Daena's COUNCIL mode: 3+ models from different providers
independently answer the same query, then a synthesizer merges their
responses into one coherent, higher-quality answer.

Pipeline:
    1. Receive independent responses from LLMService._generate_council()
    2. Build a synthesis prompt containing all council responses
    3. Call the synthesizer model to produce a merged answer
    4. Score agreement between council members
    5. Return CouncilResult with synthesis + individual responses

The Council Engine does NOT call providers directly — it relies on
LLMService for the actual LLM calls.  It owns only the synthesis
logic and agreement scoring.

Usage::

    engine = CouncilEngine(llm_service)
    result = await engine.synthesize(
        original_query="Explain quantum computing",
        responses=[response_a, response_b, response_c],
        synthesizer_candidate=best_candidate,
    )
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.services.providers.base import (
    GenerateRequest,
    LLMMessage,
    LLMResponse,
)

logger = get_logger(__name__)

# ── Synthesis prompt template ─────────────────────────────────

_SYNTHESIS_SYSTEM_PROMPT = """\
You are a synthesis expert. You have received responses from multiple \
independent AI models to the same user query. Your task:

1. Identify the key insights, facts, and reasoning from each response.
2. Resolve any contradictions by choosing the most well-supported answer.
3. Combine the best elements into a single, coherent, comprehensive response.
4. If the models strongly disagree, note the disagreement and present \
   the strongest position with caveats.
5. Do NOT mention that you are synthesizing multiple responses. \
   Write as if you are directly answering the user.

Provide a clear, well-structured answer that represents the best \
collective intelligence of all models."""

_SYNTHESIS_USER_TEMPLATE = """\
Original user query:
{query}

---

{responses_block}

---

Synthesize these responses into one high-quality answer."""


# ── Data structures ───────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class MemberResponse:
    """A single council member's contribution."""

    model_id: str
    provider: str
    content: str
    latency_ms: int = 0
    cost_usd: float = 0.0


@dataclass(slots=True)
class CouncilResult:
    """Output of the council deliberation.

    Contains the synthesized answer, individual member responses,
    and agreement metrics.
    """

    synthesis: str
    members: list[MemberResponse] = field(default_factory=list)
    synthesizer_model: str = ""
    agreement_score: float = 0.0  # 0.0 = full disagreement, 1.0 = consensus
    total_cost_usd: float = 0.0
    total_latency_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Council Engine ────────────────────────────────────────────

class CouncilEngine:
    """Synthesize responses from multiple LLM models.

    Requires an LLMService for making the synthesis call.
    The individual council responses are produced upstream
    by LLMService._generate_council() and passed in here.
    """

    def __init__(self, llm_service: Any) -> None:
        # Type is Any to avoid circular import; expects LLMService
        self._llm = llm_service

    async def synthesize(
        self,
        original_query: str,
        responses: list[LLMResponse],
        synthesizer_model_id: str = "claude-sonnet-4-20250514",
        judge_model_id: str | None = None,
    ) -> CouncilResult:
        """Merge multiple model responses into one synthesis.

        The judge (Primary Mind) synthesizes the debate. It does NOT
        participate as a debater. This ensures the user's chosen brain
        always has the final word on Council decisions.

        Args:
            original_query: The user's original question.
            responses: Independent responses from council members.
            synthesizer_model_id: Fallback model for synthesis.
            judge_model_id: Primary Mind model ID (overrides synthesizer_model_id).
                            When set, this model acts as the judge who weighs
                            all debater perspectives and produces the final answer.

        Returns:
            CouncilResult with the synthesized answer.
        """
        # Primary Mind overrides default synthesizer
        if judge_model_id:
            synthesizer_model_id = judge_model_id
        start = time.monotonic()

        if not responses:
            return CouncilResult(
                synthesis="No council responses to synthesize.",
                metadata={"error": "empty_council"},
            )

        # Single response → no synthesis needed
        if len(responses) == 1:
            r = responses[0]
            return CouncilResult(
                synthesis=r.content,
                members=[
                    MemberResponse(
                        model_id=r.model_id,
                        provider=r.provider.value,
                        content=r.content,
                        latency_ms=r.latency_ms,
                        cost_usd=r.cost_usd,
                    ),
                ],
                synthesizer_model=r.model_id,
                agreement_score=1.0,
                total_cost_usd=r.cost_usd,
                total_latency_ms=r.latency_ms,
                metadata={"single_response": True},
            )

        # Build member list
        members = [
            MemberResponse(
                model_id=r.model_id,
                provider=r.provider.value,
                content=r.content,
                latency_ms=r.latency_ms,
                cost_usd=r.cost_usd,
            )
            for r in responses
        ]

        # Build synthesis prompt
        responses_block = self._format_responses(responses)
        synthesis_prompt = _SYNTHESIS_USER_TEMPLATE.format(
            query=original_query,
            responses_block=responses_block,
        )

        # Call synthesizer
        request = GenerateRequest(
            messages=[LLMMessage(role="user", content=synthesis_prompt)],
            model_id=synthesizer_model_id,
            system_prompt=_SYNTHESIS_SYSTEM_PROMPT,
            temperature=0.3,  # low temp for faithful synthesis
            max_tokens=4096,
        )

        try:
            from app.core.constants import RoutingMode
            from app.services.model_router import ModelCandidate, RoutingDecision

            # Create a minimal routing decision for the synthesizer
            synth_candidate = ModelCandidate(
                model_id=synthesizer_model_id,
                provider=responses[0].provider,  # use first provider as default
                score=1.0,
            )
            decision = RoutingDecision(
                mode=RoutingMode.STANDARD,
                primary=synth_candidate,
            )

            orchestrated = await self._llm.generate(request, decision)
            synthesis_text = orchestrated.primary.content
            synthesis_cost = orchestrated.primary.cost_usd
        except Exception:
            logger.exception("council.synthesis_failed")
            # Fallback: concatenate responses with headers
            synthesis_text = self._fallback_synthesis(responses)
            synthesis_cost = 0.0

        # Score agreement
        agreement = self._score_agreement(responses)

        member_cost = sum(r.cost_usd for r in responses)
        total_cost = member_cost + synthesis_cost
        elapsed = int((time.monotonic() - start) * 1000)

        result = CouncilResult(
            synthesis=synthesis_text,
            members=members,
            synthesizer_model=synthesizer_model_id,
            agreement_score=agreement,
            total_cost_usd=total_cost,
            total_latency_ms=elapsed,
            metadata={
                "council_size": len(responses),
                "synthesis_cost": synthesis_cost,
                "member_cost": member_cost,
            },
        )

        logger.info(
            "council.synthesized",
            council_size=len(responses),
            agreement=round(agreement, 3),
            cost=round(total_cost, 6),
            ms=elapsed,
        )

        return result

    # ── Internal helpers ──────────────────────────────────────

    @staticmethod
    def _format_responses(responses: list[LLMResponse]) -> str:
        """Format council responses for the synthesis prompt."""
        blocks: list[str] = []
        for i, r in enumerate(responses, 1):
            blocks.append(
                f"Response {i} (from {r.provider.value}/{r.model_id}):\n"
                f"{r.content}"
            )
        return "\n\n---\n\n".join(blocks)

    @staticmethod
    def _fallback_synthesis(responses: list[LLMResponse]) -> str:
        """Simple concatenation fallback if synthesis call fails."""
        parts = []
        for i, r in enumerate(responses, 1):
            parts.append(f"**Perspective {i}** ({r.model_id}):\n{r.content}")
        return "\n\n---\n\n".join(parts)

    @staticmethod
    def _score_agreement(responses: list[LLMResponse]) -> float:
        """Score how much the council members agree.

        Simple heuristic: measure word overlap between responses.
        High overlap → high agreement.  Future: semantic similarity
        via embeddings.

        Returns 0.0 (total disagreement) to 1.0 (perfect consensus).
        """
        if len(responses) < 2:
            return 1.0

        # Extract word sets from each response
        word_sets = [
            set(r.content.lower().split()) for r in responses
        ]

        # Pairwise Jaccard similarity
        total_similarity = 0.0
        pair_count = 0

        for i in range(len(word_sets)):
            for j in range(i + 1, len(word_sets)):
                intersection = len(word_sets[i] & word_sets[j])
                union = len(word_sets[i] | word_sets[j])
                if union > 0:
                    total_similarity += intersection / union
                pair_count += 1

        if pair_count == 0:
            return 0.0

        return round(total_similarity / pair_count, 4)
