"""P4: Cross-Domain Analogy Engine -- import reasoning from unrelated domains.

The most powerful human insights come from analogies across domains:
    "This auth flow is like enzyme lock-and-key binding"
    "This distributed system problem is like traffic flow optimization"
    "This UI state management is like a finite state machine in electronics"

Once you see the structural match, the solution from the source domain
often transfers directly to the target domain. No AI system does this
systematically. Mythos reasons within-domain only. Laevateinn imports
from across domains.

Integration: runs for CREATE/ANALYZE-level queries, feeds insights
into RDE and Delivery.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.services.laevateinn.types import (
    Analogy,
    AnalogyResult,
    BloomLevel,
    ComprehensionResult,
    ComputeProfile,
    Difficulty,
)

if TYPE_CHECKING:
    from app.services.llm_service import LLMService

logger = get_logger(__name__)

_ANALOGY_PROMPT = (
    "Find structural analogies for this problem from UNRELATED domains. "
    "The best insights come from surprising connections.\n\n"
    "Problem domain: {domain}\n"
    "Problem: {query}\n\n"
    "Generate 2-3 analogies from DIFFERENT fields (biology, physics, "
    "economics, architecture, music, military strategy, ecology, etc.).\n\n"
    "For each:\n"
    "SOURCE_DOMAIN: [the unrelated field]\n"
    "STRUCTURAL_MATCH: [what is structurally similar]\n"
    "INSIGHT: [what solution pattern transfers to the original problem]\n"
    "CONFIDENCE: [0.0-1.0 how strong the analogy is]"
)

# Domain detection patterns
_DOMAIN_PATTERNS = {
    "software_engineering": [r"\bcode\b", r"\bfunction\b", r"\bapi\b", r"\bmodule\b", r"\brefactor\b"],
    "data_science": [r"\bmodel\b", r"\bdata\b", r"\btraining\b", r"\bfeature\b", r"\bprediction\b"],
    "systems_design": [r"\bscale\b", r"\blatency\b", r"\bthroughput\b", r"\bdistribut\b", r"\bload\b"],
    "security": [r"\bauth\b", r"\bpermission\b", r"\bencrypt\b", r"\bvulnerabil\b", r"\baccess\b"],
    "product": [r"\buser\b.*\bexperience\b", r"\bfeature\b", r"\bworkflow\b", r"\bonboarding\b"],
    "business": [r"\brevenue\b", r"\bcost\b", r"\bmarket\b", r"\bstrategy\b", r"\bgrowth\b"],
    "general": [],
}


class AnalogyEngine:
    """Cross-domain analogy engine for creative problem solving.

    Protocol:
    1. Detect the problem domain
    2. Generate structural analogies from unrelated domains
    3. Extract transferable insights
    4. Apply the best analogy to the original problem

    This is the most "human-like" reasoning capability in Laevateinn.
    Expert human problem-solvers routinely import solutions across
    domains. No other AI system does this explicitly.

    Args:
        llm_service: Daena's LLM service.
    """

    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service

    async def find_analogies(
        self,
        query: str,
        answer: str,
        comprehension: ComprehensionResult | None,
        compute: ComputeProfile,
        *,
        model_id: str = "",
    ) -> AnalogyResult:
        """Find cross-domain analogies for the problem.

        Only runs for HARD/BRUTAL difficulty at CREATE/ANALYZE/EVALUATE
        Bloom levels -- simple recall or application queries don't
        benefit from analogical reasoning.

        Args:
            query: The question.
            answer: Current answer to potentially enrich.
            comprehension: DCE output for domain detection.
            compute: Compute profile.
            model_id: Model to use.

        Returns:
            AnalogyResult with analogies and applied insight.
        """
        start = time.perf_counter_ns()

        # Only run for complex queries
        if compute.difficulty in (Difficulty.TRIVIAL, Difficulty.STANDARD):
            return AnalogyResult()

        # Only run for higher Bloom levels
        if comprehension and comprehension.bloom_level in (
            BloomLevel.REMEMBER, BloomLevel.UNDERSTAND,
        ):
            return AnalogyResult()

        # Detect domain
        domain = self._detect_domain(query)

        # Generate analogies
        analogies = await self._generate_analogies(query, domain, model_id)

        # Select best analogy
        best = ""
        insight = ""
        if analogies:
            best_analogy = max(analogies, key=lambda a: a.confidence)
            best = (
                f"[{best_analogy.source_domain}] "
                f"{best_analogy.structural_match}"
            )
            insight = best_analogy.imported_insight

        elapsed = int((time.perf_counter_ns() - start) / 1_000_000)

        logger.info(
            "analogy_complete",
            domain=domain,
            analogies=len(analogies),
            best_domain=analogies[0].source_domain if analogies else "none",
            elapsed_ms=elapsed,
        )

        return AnalogyResult(
            analogies=analogies,
            best_analogy=best,
            insight_applied=insight,
            total_latency_ms=elapsed,
        )

    def _detect_domain(self, query: str) -> str:
        """Detect the problem domain from the query."""
        import re
        query_lower = query.lower()

        scores = {}
        for domain, patterns in _DOMAIN_PATTERNS.items():
            scores[domain] = sum(
                1 for p in patterns if re.search(p, query_lower)
            )

        best = max(scores, key=lambda d: scores[d])
        return best if scores[best] > 0 else "general"

    async def _generate_analogies(
        self, query: str, domain: str, model_id: str,
    ) -> list[Analogy]:
        """Generate cross-domain analogies using LLM."""
        from app.services.providers.base import GenerateRequest, LLMMessage

        prompt = _ANALOGY_PROMPT.format(domain=domain, query=query)
        messages = [LLMMessage(role="user", content=prompt)]

        request = GenerateRequest(
            messages=messages,
            model_id=model_id,
            temperature=0.7,  # Higher temp for creative connections
            max_tokens=768,
        )

        try:
            result = await self._llm.generate_direct(request)
            return self._parse_analogies(result.content, domain)
        except Exception as e:
            logger.warning("analogy_generate_failed", error=str(e))
            return []

    def _parse_analogies(self, text: str, target_domain: str) -> list[Analogy]:
        """Parse LLM output into structured analogies."""
        import re
        analogies: list[Analogy] = []

        blocks = re.split(r"SOURCE_DOMAIN:\s*", text, flags=re.IGNORECASE)

        for block in blocks[1:]:
            source = block.split("\n")[0].strip()

            match_re = re.search(
                r"STRUCTURAL_MATCH:\s*(.+?)(?:\n|$)", block, re.IGNORECASE
            )
            structural = match_re.group(1).strip() if match_re else ""

            insight_re = re.search(
                r"INSIGHT:\s*(.+?)(?:\n|$)", block, re.IGNORECASE
            )
            insight = insight_re.group(1).strip() if insight_re else ""

            conf_re = re.search(
                r"CONFIDENCE:\s*([0-9.]+)", block, re.IGNORECASE
            )
            confidence = float(conf_re.group(1)) if conf_re else 0.5

            if source and (structural or insight):
                analogies.append(Analogy(
                    source_domain=source,
                    target_domain=target_domain,
                    structural_match=structural,
                    imported_insight=insight,
                    confidence=min(confidence, 1.0),
                ))

        return analogies[:3]
