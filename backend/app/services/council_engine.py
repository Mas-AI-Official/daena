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
You are the Council Judge. The responses below come from independent AI \
models who do NOT know each other's answers. Your identity is NOT privileged: \
you are a judge, not a debater. You did NOT produce these answers.

HARD RULES (violations invalidate your verdict):
1. Anonymity: responses are labeled A, B, C, ... -- identities are hidden on \
   purpose. Do not guess which model wrote which response. Do not favor a \
   response because it sounds like your style.
2. PICK, don't INVENT: your verdict must be supported by at least one \
   council response. You may combine compatible reasoning from multiple \
   responses, but you may NOT introduce a new claim, number, name, or \
   fact that no response contains. If every response is wrong, say so \
   and explain the gap -- do not paper over it.
3. Verify before you pick: for any claim that is verifiable (math, code \
   correctness, cited facts), re-derive it briefly. If two responses give \
   different numeric or factual answers, you MUST identify which derivation \
   is correct and cite the specific step that decides it. Never pick by \
   popularity or tone.

YOUR DELIVERABLE has three parts, in this order:

## DISAGREEMENT ANALYSIS
What do the responses agree on? Where do they diverge? For each divergence, \
state WHY they diverge (different assumption? different method? arithmetic \
error? different interpretation of the prompt?). If they agree on everything \
material, say so explicitly.

## VERIFICATION
For each divergent claim that matters, show a one-line verification: \
re-derive the math, sanity-check the code, cross-reference the fact. If \
verification is impossible from the information given, say so and label \
the remaining uncertainty.

## VERDICT
The final answer for the user. Cite which response(s) your verdict comes \
from using their anonymous labels (A, B, C, ...). Example: \
"Verdict draws from Response B's derivation (verified correct in step 2 \
above) with A's context framing." If no response is correct, say the answer \
is unknown and explain what additional evidence would resolve it.

End with: Confidence: N/10. Below 7 means something is unverified -- name \
it in one sentence.

Do NOT write prose that hides the disagreement. Do NOT pretend consensus. \
Do NOT default to your own prior answer. Your job is to find the correct \
answer inside the council, not to replace it with yours."""

_SYNTHESIS_USER_TEMPLATE = """\
Original user query:
{query}

---

{responses_block}

---

Produce your DISAGREEMENT ANALYSIS, VERIFICATION, and VERDICT in that order. \
Anonymous labels only (A/B/C/...). Your verdict must be supported by at least \
one of the council responses; if none are correct, say so explicitly."""


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
    disagreement_value: float = 0.0  # How valuable the disagreement is (high = rich insight)
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

        The judge (Primary Mind) is a CONSTRAINED SYNTHESIZER, not a dictator:
          1. Responses are anonymized to A/B/C/... before the judge sees them
             (see ``_format_responses``), so it cannot favor its own brand.
          2. The judge must produce DISAGREEMENT ANALYSIS + VERIFICATION
             before the VERDICT (see ``_SYNTHESIS_SYSTEM_PROMPT``), forcing
             it to understand why members differ instead of replacing them.
          3. The verdict must be grounded in at least one council response;
             the judge may combine compatible reasoning but may not introduce
             new claims. If every response is wrong, the judge must say so
             rather than paper over the gap with its own prior answer.

        Replaces the pre-2026-04-16 pattern where the judge had "the final
        word" by silently generating a fresh answer, which caused the AIME
        Q15 regression (Gemini's correct answer was discarded).

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

        # Disagreement value: inverse of agreement, scaled by council size.
        # Low agreement with many models = highly valuable disagreement.
        disagreement_value = (1.0 - agreement) * min(len(responses) / 3.0, 1.0)

        result = CouncilResult(
            synthesis=synthesis_text,
            members=members,
            synthesizer_model=synthesizer_model_id,
            agreement_score=agreement,
            disagreement_value=round(disagreement_value, 3),
            total_cost_usd=total_cost,
            total_latency_ms=elapsed,
            metadata={
                "council_size": len(responses),
                "synthesis_cost": synthesis_cost,
                "member_cost": member_cost,
                "disagreement_exploited": disagreement_value > 0.5,
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
        """Format council responses for the synthesis prompt.

        Responses are ANONYMIZED (A, B, C, ...) so the judge cannot anchor
        on its own brand or a preferred debater. This is the first of three
        defenses against the dictator-judge pattern that caused the 2026-04-12
        AIME Q15 regression (where Gemini's correct answer was discarded
        because the judge silently preferred its own derivation). The judge
        sees no model_id or provider until after the verdict is committed.
        """
        blocks: list[str] = []
        for i, r in enumerate(responses):
            label = chr(ord("A") + i)  # A, B, C, ...
            blocks.append(
                f"Response {label}:\n"
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
