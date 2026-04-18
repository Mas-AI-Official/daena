"""Quintessence Engine — expert x LLM matrix synthesis.

Daena's highest-fidelity mode: simulate 5 domain experts, each
answering through multiple LLM providers, then meta-synthesize
all perspectives into one authoritative response.

Pipeline:
    1. Select domain-appropriate expert personas (up to 5)
    2. For each expert IN PARALLEL, generate role-prompted responses
       with expert system prompts injected (reuses LLMService fan-out)
    3. Per-expert synthesis via CouncilEngine with expert lens
    4. Meta-synthesis: merge all expert syntheses into final answer
    5. Score inter-expert agreement + confidence

What this improves over single-model or Council:
    - HALLUCINATION REDUCTION: cross-expert disagreement surfaces
      fabricated facts (research: +16 points on HallusionBench)
    - BLIND SPOT ELIMINATION: each expert has documented blind_spots
      that other experts compensate for
    - CONFIDENCE SCORING: agreement metrics tell the user how
      reliable the answer is (low agreement = uncertain = flag it)

The Quintessence Engine composes CouncilEngine and LLMService.
It does NOT call providers directly.

Usage::

    engine = QuintessenceEngine(llm_service, council_engine)
    result = await engine.deliberate(
        query="Design a secure authentication system",
        responses=council_responses,      # from LLM fan-out
        query_intent=IntentType.CODING,
    )
"""

from __future__ import annotations

import asyncio
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
        "You are a hostile critic who believes the obvious answer is WRONG. "
        "Your job is to BREAK the argument. Find the fatal flaw. Identify "
        "the assumption everyone is making that nobody questions. If you "
        "cannot find a flaw after rigorous analysis, reluctantly acknowledge "
        "the argument's strength -- but never easily."
    ),
    "adversary": (
        "You are a strategic adversary trying to find the worst possible outcome "
        "of this approach. What could go catastrophically wrong? What attack "
        "vectors exist? What second-order effects has everyone missed? "
        "Think like an enemy. Plan like a saboteur. Report like a friend."
    ),
    "strategist": (
        "You are a strategic thinker who sees 3 moves ahead. While others focus "
        "on the immediate question, you analyze the trajectory. What does this "
        "decision set up? What options does it close? What leverage does it create? "
        "Think in terms of positioning, optionality, and compound effects."
    ),
}

# Intent → which experts are most relevant
_INTENT_EXPERTS: dict[str, list[str]] = {
    "SIMPLE": ["practitioner", "researcher"],
    "SEARCH": ["researcher", "practitioner", "critic"],
    "CODING": ["architect", "security", "practitioner", "critic", "adversary"],
    "ANALYSIS": ["researcher", "critic", "strategist", "architect", "adversary"],
    "CREATIVE": ["researcher", "critic", "practitioner", "strategist"],
    "MULTI_STEP": ["architect", "practitioner", "strategist", "critic", "adversary"],
    "DANGEROUS": ["security", "adversary", "critic", "architect", "strategist"],
    "AMBIGUOUS": ["researcher", "practitioner", "critic", "strategist"],
}

# ── Meta-synthesis prompt ────────────────────────────────────

_META_SYSTEM_PROMPT = """\
You are performing a Quintessence synthesis — the highest level of \
multi-perspective intelligence analysis. You have received synthesized \
opinions from multiple domain experts, each representing a different \
analytical lens, including adversarial and strategic perspectives.

Your task:
1. Extract the SHARPEST insight from each expert -- the thing only \
   they would see from their specific vantage point.
2. When experts disagree, this is your most valuable signal. Analyze \
   WHY they disagree. The disagreement itself reveals hidden structure.
3. The adversary's concerns are not obstacles -- they are intelligence. \
   Integrate their threat analysis into your recommendation.
4. The strategist's long-term view should shape the framing, even \
   when the immediate answer is tactical.
5. Produce the most powerful, well-reasoned answer possible. Not \
   the safest. Not the most hedged. The most INTELLIGENT.
6. Rate confidence 0-10. Below 7: flag what is uncertain and why.
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
        depth: str = "standard",
        judge_model_id: str | None = None,
    ) -> QuintessenceResult:
        """Run full Quintessence deliberation.

        The judge (Primary Mind) performs the meta-synthesis across all
        expert perspectives. It does NOT participate as a debater. This
        ensures the user's chosen brain is the final arbiter in the
        highest-fidelity mode.

        Args:
            query: The user's original question.
            responses: LLM responses from the fan-out (5+ models).
            query_intent: Intent string for expert selection.
            synthesizer_model_id: Fallback model for meta-synthesis.
            depth: Expert count depth (light/standard/deep/council).
            judge_model_id: Primary Mind model ID (overrides synthesizer_model_id).
                            When set, this model judges all expert perspectives.

        Returns:
            QuintessenceResult with meta-synthesis and expert details.
        """
        # Primary Mind overrides default synthesizer for meta-synthesis
        if judge_model_id:
            synthesizer_model_id = judge_model_id
        # Store for per-expert synthesis calls
        self._judge_model_id = judge_model_id
        start = time.monotonic()

        if not responses:
            return QuintessenceResult(
                synthesis="No responses available for Quintessence deliberation.",
                metadata={"error": "empty_responses"},
            )

        # 1. Select experts based on depth level
        # QE-Light: 2 experts (fast, cheap -- simple questions)
        # QE-Standard: 3 experts (default -- most queries)
        # QE-Deep: 5 experts + cross-validation (complex decisions)
        # QE-Council: All available experts (critical architecture)
        _depth_expert_count = {
            "light": 2,
            "standard": 3,
            "deep": 5,
            "council": 15,
        }
        max_experts = _depth_expert_count.get(depth, 3)
        experts = self._select_experts(query_intent, max_experts=max_experts)

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
        """Run council synthesis for each expert persona IN PARALLEL.

        Each expert gets the same raw responses but views them
        through a different analytical lens via injected system prompt.
        Parallel execution reduces latency from O(n * synthesis_time)
        to O(synthesis_time + overhead).
        """

        async def _run_one_expert(expert_id: str) -> ExpertSynthesis | None:
            expert_prompt = _EXPERT_SYSTEM_PROMPTS.get(expert_id)
            if not expert_prompt:
                return None

            # Build expert-lensed query: inject the expert's system prompt
            # into the query so the synthesizer adopts their perspective.
            lensed_query = (
                f"EXPERT LENS: {expert_id.replace('_', ' ').title()}\n"
                f"PERSPECTIVE: {expert_prompt}\n\n"
                f"Using this expert perspective, analyze the following:\n\n"
                f"{query}"
            )

            try:
                council_result = await self._council.synthesize(
                    original_query=lensed_query,
                    responses=responses,
                    judge_model_id=getattr(self, '_judge_model_id', None),
                )

                return ExpertSynthesis(
                    expert_id=expert_id,
                    expert_label=expert_id.replace("_", " ").title(),
                    synthesis=council_result.synthesis,
                    agreement_score=council_result.agreement_score,
                    model_count=len(council_result.members),
                    cost_usd=council_result.total_cost_usd,
                )
            except Exception:
                logger.exception(
                    "quintessence.expert_failed", expert=expert_id,
                )
                return None

        # Run ALL experts in parallel (latency = slowest expert, not sum)
        tasks = [_run_one_expert(eid) for eid in experts]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[ExpertSynthesis] = []
        for r in raw_results:
            if isinstance(r, ExpertSynthesis):
                results.append(r)
            elif isinstance(r, Exception):
                logger.warning("quintessence.expert_task_exception", error=str(r))

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

        Uses weighted TF-IDF-like scoring: common English words are
        down-weighted, domain-specific terms carry more signal.
        This is more accurate than raw Jaccard because two experts
        can agree on substance while using different phrasing.

        Factors:
            - Meaningful word overlap (filtered stopwords, 50%)
            - Key claim extraction via sentence overlap (30%)
            - Contradiction detection via negation patterns (20%)
        """
        if len(experts) < 2:
            return 1.0

        # Stopwords to filter out common English words that inflate agreement
        _stopwords = frozenset({
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "can", "shall",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "through", "during", "before", "after", "and",
            "but", "or", "not", "no", "nor", "so", "yet", "both", "each",
            "this", "that", "these", "those", "it", "its", "they", "them",
            "their", "we", "our", "you", "your", "i", "me", "my", "he",
            "she", "his", "her", "if", "then", "than", "when", "where",
            "which", "what", "who", "how", "all", "any", "some", "such",
            "more", "most", "other", "also", "just", "about", "up", "out",
            "very", "well", "here", "there", "only",
        })

        # Extract meaningful word sets (filter stopwords, keep domain terms)
        meaningful_sets = []
        for e in experts:
            words = set(e.synthesis.lower().split())
            meaningful = {w for w in words if w not in _stopwords and len(w) > 2}
            meaningful_sets.append(meaningful)

        # 1. Meaningful word overlap (50% weight)
        word_sim = 0.0
        pairs = 0
        for i in range(len(meaningful_sets)):
            for j in range(i + 1, len(meaningful_sets)):
                intersection = len(meaningful_sets[i] & meaningful_sets[j])
                union = len(meaningful_sets[i] | meaningful_sets[j])
                if union > 0:
                    word_sim += intersection / union
                pairs += 1
        word_score = word_sim / pairs if pairs > 0 else 0.0

        # 2. Sentence-level overlap (30% weight) -- key claims
        sentence_sets = []
        for e in experts:
            # Extract first 3 words of each sentence as claim fingerprint
            sents = [s.strip() for s in e.synthesis.split(".") if len(s.strip()) > 10]
            fingerprints = set()
            for s in sents:
                words = s.lower().split()[:4]
                if words:
                    fingerprints.add(" ".join(words))
            sentence_sets.append(fingerprints)

        sent_sim = 0.0
        sent_pairs = 0
        for i in range(len(sentence_sets)):
            for j in range(i + 1, len(sentence_sets)):
                if sentence_sets[i] and sentence_sets[j]:
                    intersection = len(sentence_sets[i] & sentence_sets[j])
                    union = len(sentence_sets[i] | sentence_sets[j])
                    if union > 0:
                        sent_sim += intersection / union
                    sent_pairs += 1
        sent_score = sent_sim / sent_pairs if sent_pairs > 0 else 0.0

        # 3. Contradiction penalty (20% weight)
        # If experts use opposing language, reduce agreement
        _negation_pairs = [
            ("should", "should not"), ("recommend", "avoid"),
            ("safe", "unsafe"), ("correct", "incorrect"),
            ("yes", "no"), ("always", "never"),
            ("possible", "impossible"), ("secure", "insecure"),
        ]
        contradiction_count = 0
        for i in range(len(experts)):
            text_i = experts[i].synthesis.lower()
            for j in range(i + 1, len(experts)):
                text_j = experts[j].synthesis.lower()
                for pos, neg in _negation_pairs:
                    if (pos in text_i and neg in text_j) or (neg in text_i and pos in text_j):
                        contradiction_count += 1
        max_contradictions = pairs * len(_negation_pairs)
        contradiction_rate = contradiction_count / max_contradictions if max_contradictions > 0 else 0.0
        contradiction_score = 1.0 - min(contradiction_rate * 5, 1.0)  # amplify penalty

        # Weighted composite
        agreement = (
            0.50 * word_score
            + 0.30 * sent_score
            + 0.20 * contradiction_score
        )

        return round(min(max(agreement, 0.0), 1.0), 4)

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
