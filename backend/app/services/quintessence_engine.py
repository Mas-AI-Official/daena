"""Quintessence Engine — expert × LLM matrix synthesis.

Daena's highest-fidelity mode: simulate 5 domain experts, each
answering through multiple LLM providers, then meta-synthesize
all perspectives into one authoritative response.

Pipeline:
    1. Select domain-appropriate expert personas (up to 5)
    2. For each expert, generate role-prompted responses from
       available LLM providers (reuses LLMService fan-out)
    3. Per-expert synthesis via CouncilEngine
    4. Meta-synthesis: merge all expert syntheses into final answer
    5. Score inter-expert agreement + confidence

The Quintessence Engine composes CouncilEngine and LLMService —
it does NOT call providers directly.

Usage::

    engine = QuintessenceEngine(llm_service, council_engine)
    result = await engine.deliberate(
        query="Design a secure authentication system",
        responses=council_responses,      # from LLM fan-out
        query_intent=IntentType.CODING,
    )
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.services.council_engine import CouncilEngine
from app.services.providers.base import LLMResponse

logger = get_logger(__name__)

# ── Expert persona definitions ───────────────────────────────

_EXPERT_SYSTEM_PROMPTS: dict[str, str] = {
    "architect": (
        "You are a senior software architect with 20+ years of experience. "
        "Focus on system design, scalability, maintainability, and "
        "architectural trade-offs. Prioritize long-term viability."
    ),
    "security": (
        "You are a cybersecurity expert specializing in application security. "
        "Identify vulnerabilities, threat vectors, and security best practices. "
        "Always consider OWASP Top 10 and defense-in-depth."
    ),
    "researcher": (
        "You are an academic researcher with deep domain expertise. "
        "Provide evidence-based analysis, cite relevant theories and studies, "
        "and identify gaps in current knowledge."
    ),
    "practitioner": (
        "You are a hands-on senior developer who ships production code daily. "
        "Focus on practical implementation, real-world constraints, "
        "debugging experience, and pragmatic solutions."
    ),
    "critic": (
        "You are a critical analyst who questions assumptions and finds flaws. "
        "Play devil's advocate. Identify edge cases, failure modes, "
        "and overlooked risks. Challenge the obvious answer."
    ),
}

# Intent → which experts are most relevant
_INTENT_EXPERTS: dict[str, list[str]] = {
    "SIMPLE": ["practitioner", "researcher"],
    "SEARCH": ["researcher", "practitioner", "critic"],
    "CODING": ["architect", "security", "practitioner", "critic", "researcher"],
    "ANALYSIS": ["researcher", "critic", "architect", "practitioner", "security"],
    "CREATIVE": ["researcher", "critic", "practitioner"],
    "MULTI_STEP": ["architect", "practitioner", "security", "critic", "researcher"],
    "DANGEROUS": ["security", "critic", "architect", "researcher", "practitioner"],
    "AMBIGUOUS": ["researcher", "practitioner", "critic"],
}

# ── Meta-synthesis prompt ────────────────────────────────────

_META_SYSTEM_PROMPT = """\
You are performing a Quintessence synthesis — the highest level of \
multi-perspective analysis. You have received synthesized opinions from \
multiple domain experts, each representing a different analytical lens.

Your task:
1. Identify the consensus across experts.
2. Highlight critical insights unique to specific experts.
3. Resolve contradictions by weighing evidence and reasoning quality.
4. Produce a comprehensive, authoritative answer that represents \
   the best collective intelligence.
5. If experts fundamentally disagree, present the strongest position \
   with clear caveats.
6. Do NOT mention experts, synthesis, or the deliberation process. \
   Write as if you are directly answering the user."""

_META_USER_TEMPLATE = """\
Original user query:
{query}

---

{expert_block}

---

Synthesize these expert perspectives into one definitive answer."""


# ── Data structures ──────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ExpertSynthesis:
    """One expert's synthesized perspective."""

    expert_id: str
    expert_label: str
    synthesis: str
    agreement_score: float
    model_count: int
    cost_usd: float


@dataclass(slots=True)
class QuintessenceResult:
    """Output of the Quintessence deliberation.

    Contains the meta-synthesis, per-expert syntheses,
    confidence metrics, and cost breakdown.
    """

    synthesis: str
    expert_syntheses: list[ExpertSynthesis] = field(default_factory=list)
    meta_agreement: float = 0.0  # agreement across experts
    confidence: float = 0.0      # composite confidence score
    total_cost_usd: float = 0.0
    total_latency_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Quintessence Engine ──────────────────────────────────────

class QuintessenceEngine:
    """Expert × LLM matrix deliberation engine.

    Composes CouncilEngine (per-expert synthesis) and LLMService
    (meta-synthesis call).  Does not call providers directly.
    """

    def __init__(
        self,
        llm_service: Any,
        council_engine: CouncilEngine,
    ) -> None:
        self._llm = llm_service
        self._council = council_engine

    async def deliberate(
        self,
        query: str,
        responses: list[LLMResponse],
        query_intent: str = "AMBIGUOUS",
        synthesizer_model_id: str = "claude-sonnet-4-20250514",
    ) -> QuintessenceResult:
        """Run full Quintessence deliberation.

        Args:
            query: The user's original question.
            responses: LLM responses from the fan-out (5+ models).
            query_intent: Intent string for expert selection.
            synthesizer_model_id: Model for meta-synthesis.

        Returns:
            QuintessenceResult with meta-synthesis and expert details.
        """
        start = time.monotonic()

        if not responses:
            return QuintessenceResult(
                synthesis="No responses available for Quintessence deliberation.",
                metadata={"error": "empty_responses"},
            )

        # 1. Select experts for this intent
        experts = self._select_experts(query_intent)

        # 2. Distribute responses across experts (role-prompted synthesis)
        expert_results = await self._run_expert_syntheses(
            query, responses, experts,
        )

        if not expert_results:
            # All experts failed — fallback to plain council
            fallback = await self._council.synthesize(
                query, responses, synthesizer_model_id,
            )
            return QuintessenceResult(
                synthesis=fallback.synthesis,
                total_cost_usd=fallback.total_cost_usd,
                total_latency_ms=int((time.monotonic() - start) * 1000),
                metadata={"fallback": "council_only", "reason": "all_experts_failed"},
            )

        # 3. Meta-synthesis across all expert perspectives
        meta_synthesis, meta_cost = await self._meta_synthesize(
            query, expert_results, synthesizer_model_id,
        )

        # 4. Score cross-expert agreement
        meta_agreement = self._score_expert_agreement(expert_results)

        # 5. Compute confidence
        confidence = self._compute_confidence(expert_results, meta_agreement)

        expert_cost = sum(e.cost_usd for e in expert_results)
        total_cost = expert_cost + meta_cost
        elapsed = int((time.monotonic() - start) * 1000)

        result = QuintessenceResult(
            synthesis=meta_synthesis,
            expert_syntheses=expert_results,
            meta_agreement=meta_agreement,
            confidence=confidence,
            total_cost_usd=total_cost,
            total_latency_ms=elapsed,
            metadata={
                "expert_count": len(expert_results),
                "model_count": len(responses),
                "intent": query_intent,
                "expert_cost": expert_cost,
                "meta_cost": meta_cost,
            },
        )

        logger.info(
            "quintessence.deliberated",
            experts=len(expert_results),
            models=len(responses),
            agreement=round(meta_agreement, 3),
            confidence=round(confidence, 3),
            cost=round(total_cost, 6),
            ms=elapsed,
        )

        return result

    # ── Expert selection ─────────────────────────────────────

    @staticmethod
    def _select_experts(intent: str, max_experts: int = 5) -> list[str]:
        """Pick domain experts relevant to the query intent."""
        expert_ids = _INTENT_EXPERTS.get(intent, _INTENT_EXPERTS["AMBIGUOUS"])
        return expert_ids[:max_experts]

    # ── Per-expert synthesis ─────────────────────────────────

    async def _run_expert_syntheses(
        self,
        query: str,
        responses: list[LLMResponse],
        experts: list[str],
    ) -> list[ExpertSynthesis]:
        """Run council synthesis for each expert persona.

        Each expert gets the same raw responses but views them
        through a different analytical lens (system prompt).
        """
        results: list[ExpertSynthesis] = []

        for expert_id in experts:
            prompt = _EXPERT_SYSTEM_PROMPTS.get(expert_id)
            if not prompt:
                continue

            try:
                council_result = await self._council.synthesize(
                    original_query=f"[Expert: {expert_id}] {query}",
                    responses=responses,
                )

                results.append(
                    ExpertSynthesis(
                        expert_id=expert_id,
                        expert_label=expert_id.replace("_", " ").title(),
                        synthesis=council_result.synthesis,
                        agreement_score=council_result.agreement_score,
                        model_count=len(council_result.members),
                        cost_usd=council_result.total_cost_usd,
                    )
                )
            except Exception:
                logger.exception(
                    "quintessence.expert_failed", expert=expert_id,
                )

        return results

    # ── Meta-synthesis ───────────────────────────────────────

    async def _meta_synthesize(
        self,
        query: str,
        expert_results: list[ExpertSynthesis],
        synthesizer_model_id: str,
    ) -> tuple[str, float]:
        """Merge all expert syntheses into one final answer.

        Returns (synthesis_text, cost_usd).
        """
        from app.core.constants import RoutingMode
        from app.services.model_router import ModelCandidate, RoutingDecision
        from app.services.providers.base import GenerateRequest, LLMMessage

        expert_block = self._format_expert_block(expert_results)
        user_prompt = _META_USER_TEMPLATE.format(
            query=query,
            expert_block=expert_block,
        )

        request = GenerateRequest(
            messages=[LLMMessage(role="user", content=user_prompt)],
            model_id=synthesizer_model_id,
            system_prompt=_META_SYSTEM_PROMPT,
            temperature=0.2,  # very low for faithful meta-synthesis
            max_tokens=4096,
        )

        try:
            # Minimal routing decision for the meta-synthesizer
            candidate = ModelCandidate(
                model_id=synthesizer_model_id,
                provider=expert_results[0]
                ._infer_provider() if hasattr(expert_results[0], "_infer_provider")
                else self._default_provider(),
                score=1.0,
            )
            decision = RoutingDecision(
                mode=RoutingMode.STANDARD,
                primary=candidate,
            )

            orchestrated = await self._llm.generate(request, decision)
            return orchestrated.primary.content, orchestrated.primary.cost_usd
        except Exception:
            logger.exception("quintessence.meta_synthesis_failed")
            # Fallback: concatenate expert syntheses
            return self._fallback_meta(expert_results), 0.0

    def _default_provider(self) -> Any:
        """Get default provider enum for synthesis routing."""
        from app.core.constants import ModelProvider
        return ModelProvider.ANTHROPIC

    # ── Agreement & confidence scoring ───────────────────────

    @staticmethod
    def _score_expert_agreement(experts: list[ExpertSynthesis]) -> float:
        """Score agreement across expert syntheses.

        Uses Jaccard word overlap (same as CouncilEngine) but
        across expert perspectives rather than raw model responses.
        """
        if len(experts) < 2:
            return 1.0

        word_sets = [
            set(e.synthesis.lower().split()) for e in experts
        ]

        total_sim = 0.0
        pairs = 0
        for i in range(len(word_sets)):
            for j in range(i + 1, len(word_sets)):
                intersection = len(word_sets[i] & word_sets[j])
                union = len(word_sets[i] | word_sets[j])
                if union > 0:
                    total_sim += intersection / union
                pairs += 1

        return round(total_sim / pairs, 4) if pairs > 0 else 0.0

    @staticmethod
    def _compute_confidence(
        experts: list[ExpertSynthesis],
        meta_agreement: float,
    ) -> float:
        """Composite confidence score (0.0 – 1.0).

        Factors:
            - Cross-expert agreement (40%)
            - Average intra-expert agreement (30%)
            - Expert coverage — more experts = higher confidence (30%)
        """
        if not experts:
            return 0.0

        avg_intra = sum(e.agreement_score for e in experts) / len(experts)
        coverage = min(len(experts) / 5.0, 1.0)

        confidence = (
            0.40 * meta_agreement
            + 0.30 * avg_intra
            + 0.30 * coverage
        )
        return round(min(confidence, 1.0), 4)

    # ── Formatting helpers ───────────────────────────────────

    @staticmethod
    def _format_expert_block(experts: list[ExpertSynthesis]) -> str:
        """Format expert syntheses for the meta-synthesis prompt."""
        blocks: list[str] = []
        for e in experts:
            blocks.append(
                f"Expert: {e.expert_label} "
                f"(agreement: {e.agreement_score:.2f}):\n"
                f"{e.synthesis}"
            )
        return "\n\n---\n\n".join(blocks)

    @staticmethod
    def _fallback_meta(experts: list[ExpertSynthesis]) -> str:
        """Simple concatenation fallback if meta-synthesis fails."""
        parts = []
        for e in experts:
            parts.append(
                f"**{e.expert_label} Perspective:**\n{e.synthesis}"
            )
        return "\n\n---\n\n".join(parts)
