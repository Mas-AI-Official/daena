"""Stage 1: Deep Comprehension Engine (DCE).

Transforms raw user queries into enriched, decomposed, first-principles
representations before any LLM sees them.

Sub-stages:
    L0 Feynman Intake: compress to one clear sentence + Polya decompose
    L1 Musk Noise Elimination: strip to first principles
    L2 Tesla Resonance: find the REAL question behind the stated one
    L3 ACH Multi-Interpretation: generate 3-5 scored interpretations

The DCE operates WITHOUT calling any LLM for trivial/standard queries
(heuristic mode). For hard/brutal queries, it optionally uses a local
model for deeper comprehension.
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.services.laevateinn.types import (
    BloomLevel,
    ComprehensionResult,
    Interpretation,
)

if TYPE_CHECKING:
    from app.services.llm_service import LLMService
    from app.services.providers.base import LLMResponse

logger = get_logger(__name__)

# Bloom's level detection patterns (heuristic, no LLM needed)
_BLOOM_PATTERNS: dict[BloomLevel, list[str]] = {
    BloomLevel.REMEMBER: [
        r"\bwhat is\b", r"\bdefine\b", r"\blist\b", r"\bname\b",
        r"\bwhen\b", r"\bwho\b", r"\bwhere\b", r"\brecall\b",
    ],
    BloomLevel.UNDERSTAND: [
        r"\bexplain\b", r"\bdescribe\b", r"\bsummar", r"\binterpret\b",
        r"\bparaphrase\b", r"\bwhy does\b", r"\bhow does\b",
    ],
    BloomLevel.APPLY: [
        r"\bimplement\b", r"\buse\b", r"\bapply\b", r"\bsolve\b",
        r"\bcalculate\b", r"\bdemonstrate\b", r"\bexecute\b",
    ],
    BloomLevel.ANALYZE: [
        r"\banalyze\b", r"\bcompare\b", r"\bcontrast\b", r"\bdiagnose\b",
        r"\bdebug\b", r"\bdifferentiat\b", r"\bexamine\b", r"\binvestigat\b",
    ],
    BloomLevel.EVALUATE: [
        r"\bevaluat\b", r"\bjudge\b", r"\bcritique\b", r"\bjustify\b",
        r"\breview\b", r"\bassess\b", r"\bshould i\b", r"\bbetter\b",
    ],
    BloomLevel.CREATE: [
        r"\bdesign\b", r"\bcreate\b", r"\bbuild\b", r"\barchitect\b",
        r"\bgenerat\b", r"\bcompose\b", r"\bwrite\b", r"\bdevelop\b",
        r"\bplan\b", r"\bpropose\b",
    ],
}

# Noise words and hedging phrases to strip (Musk filter)
_NOISE_PATTERNS: list[str] = [
    r"\bplease\b", r"\bkindly\b", r"\bcould you\b", r"\bwould you\b",
    r"\bcan you\b", r"\bi was wondering\b", r"\bi think maybe\b",
    r"\bsorry but\b", r"\bif possible\b", r"\bif you don't mind\b",
    r"\bit would be great if\b", r"\bi need help with\b",
    r"\bhelp me\b", r"\bi want to\b", r"\bi'd like to\b",
]

# Sub-question decomposition triggers
_COMPOUND_MARKERS: list[str] = [
    r"\band\b", r"\balso\b", r"\badditionally\b", r"\bplus\b",
    r"\bfurthermore\b", r"\bthen\b", r"\bafter that\b",
]


class DeepComprehensionEngine:
    """Stage 1 of APEX: understand the query before answering it.

    Operates in two modes:
        - Heuristic mode (no LLM): for trivial/standard queries (<10ms)
        - Deep mode (uses LLM): for hard/brutal queries (200-500ms)

    Args:
        llm_service: Optional LLM service for deep comprehension mode.
    """

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self._llm = llm_service

    async def comprehend(
        self,
        query: str,
        *,
        use_llm: bool = False,
        context: str = "",
    ) -> ComprehensionResult:
        """Run the full DCE pipeline on a query.

        Args:
            query: Raw user query.
            use_llm: Whether to use LLM for deeper analysis.
            context: Optional conversation context for enrichment.

        Returns:
            ComprehensionResult with enriched query data.
        """
        start = time.perf_counter_ns()

        # L0: Feynman Intake
        compressed = self._feynman_compress(query)
        sub_questions = self._polya_decompose(query)
        assumptions = self._surface_assumptions(query)

        # L1: Musk Noise Elimination
        noise_free = self._musk_filter(query)

        # L2: Tesla Resonance Detection
        real_question = self._tesla_resonance(query, noise_free)

        # L3: ACH Multi-Interpretation
        if use_llm and self._llm:
            interpretations = await self._ach_deep(query, context)
        else:
            interpretations = self._ach_heuristic(query)

        # Bloom's level
        bloom = self._detect_bloom_level(query)

        elapsed_ms = int((time.perf_counter_ns() - start) / 1_000_000)

        result = ComprehensionResult(
            original_query=query,
            compressed_query=compressed,
            sub_questions=sub_questions,
            hidden_assumptions=assumptions,
            noise_eliminated=noise_free,
            real_question=real_question,
            interpretations=interpretations,
            bloom_level=bloom,
            processing_time_ms=elapsed_ms,
        )

        logger.info(
            "dce_complete",
            bloom=bloom.value,
            interpretations=len(interpretations),
            sub_questions=len(sub_questions),
            elapsed_ms=elapsed_ms,
        )

        return result

    # ── L0: Feynman Intake ──────────────────────────────────────

    def _feynman_compress(self, query: str) -> str:
        """Compress query to its essential meaning in one clear sentence.

        Feynman principle: if you can't explain it simply, you don't
        understand it well enough.
        """
        # Strip noise first
        clean = self._musk_filter(query)

        # Remove parenthetical asides
        clean = re.sub(r"\([^)]*\)", "", clean)

        # Collapse multiple spaces
        clean = re.sub(r"\s+", " ", clean).strip()

        # If already short, return as-is
        if len(clean.split()) <= 15:
            return clean

        # Extract the core verb + object pattern
        # This is heuristic -- LLM mode does much better
        sentences = re.split(r"[.!?]+", clean)
        if sentences:
            # Take the first substantive sentence
            for s in sentences:
                s = s.strip()
                if len(s.split()) >= 3:
                    return s

        return clean

    def _polya_decompose(self, query: str) -> list[str]:
        """Decompose compound queries into sub-questions using Polya's method.

        Polya's 4 steps: understand, plan, execute, review.
        Here we focus on "understand" -- breaking the problem into parts.
        """
        parts: list[str] = []

        # Split on compound markers
        segments = re.split(
            "|".join(_COMPOUND_MARKERS), query, flags=re.IGNORECASE
        )

        for seg in segments:
            seg = seg.strip()
            if len(seg.split()) >= 3:  # Minimum substantive segment
                parts.append(seg)

        # If no decomposition possible, return the original as single part
        if len(parts) <= 1:
            return [query.strip()]

        return parts

    def _surface_assumptions(self, query: str) -> list[str]:
        """Detect hidden assumptions in the query.

        Common assumption patterns:
            - Presuppositions ("Why did X fail?" assumes X failed)
            - Binary framing ("Should I use A or B?" assumes only 2 options)
            - Implicit constraints ("How do I do X?" assumes X is the goal)
        """
        assumptions: list[str] = []

        # Presupposition detection
        why_match = re.search(r"\bwhy\s+(did|does|is|are|was|were)\s+(.+?)[\?.]", query, re.IGNORECASE)
        if why_match:
            assumptions.append(f"Assumes: {why_match.group(2).strip()} is true")

        # Binary framing
        or_match = re.search(r"should\s+I\s+(?:use\s+)?(\w+)\s+or\s+(\w+)", query, re.IGNORECASE)
        if or_match:
            assumptions.append(
                f"Binary framing: only considers {or_match.group(1)} vs {or_match.group(2)}"
            )

        # "Best" assumption (assumes one answer is objectively best)
        if re.search(r"\bbest\b", query, re.IGNORECASE):
            assumptions.append("Assumes a single 'best' answer exists (context-dependent)")

        # Implicit time constraint
        if re.search(r"\bquickly\b|\bfast\b|\bASAP\b|\burgent\b", query, re.IGNORECASE):
            assumptions.append("Implicit time pressure -- may sacrifice thoroughness")

        return assumptions

    # ── L1: Musk Noise Elimination ──────────────────────────────

    def _musk_filter(self, query: str) -> str:
        """Strip noise to first principles.

        Musk principle: delete any part that does not serve the core request.
        If deleting it changes nothing, it was noise.
        """
        result = query
        for pattern in _NOISE_PATTERNS:
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)

        # Collapse whitespace
        result = re.sub(r"\s+", " ", result).strip()

        # Remove leading/trailing punctuation artifacts
        result = result.strip(".,;:!? ")

        return result if result else query  # Never return empty

    # ── L2: Tesla Resonance Detection ───────────────────────────

    def _tesla_resonance(self, query: str, noise_free: str) -> str:
        """Find the REAL question hiding inside the stated one.

        Tesla principle: resonance reveals the fundamental frequency.
        The stated question often hides a deeper need.
        """
        # Pattern: "How do I X?" often means "What's the best approach for X?"
        how_match = re.search(r"how\s+(?:do|can|should)\s+I\s+(.+?)[\?.]?$", noise_free, re.IGNORECASE)
        if how_match:
            return f"What is the best approach for: {how_match.group(1).strip()}"

        # Pattern: "Is X good?" means "What are the trade-offs of X?"
        is_good = re.search(r"is\s+(.+?)\s+(?:good|bad|worth|useful)", noise_free, re.IGNORECASE)
        if is_good:
            return f"What are the trade-offs of {is_good.group(1).strip()}?"

        # Pattern: "X is not working" means "How do I debug/fix X?"
        not_working = re.search(r"(.+?)\s+(?:is not|isn't|not)\s+working", noise_free, re.IGNORECASE)
        if not_working:
            return f"How to diagnose and fix: {not_working.group(1).strip()}"

        # Pattern: "What should I..." means "Given my constraints, what's optimal?"
        what_should = re.search(r"what\s+should\s+I\s+(.+?)[\?.]?$", noise_free, re.IGNORECASE)
        if what_should:
            return f"Given context, what is the optimal choice for: {what_should.group(1).strip()}"

        # No deeper pattern found -- the stated question IS the real question
        return noise_free

    # ── L3: ACH Multi-Interpretation ────────────────────────────

    def _ach_heuristic(self, query: str) -> list[Interpretation]:
        """Generate interpretations using heuristic analysis (no LLM).

        Analysis of Competing Hypotheses (ACH): generate multiple
        interpretations and score by probability.
        """
        interpretations: list[Interpretation] = []

        # Primary interpretation: literal reading
        interpretations.append(Interpretation(
            text=query.strip(),
            probability=0.6,
            reasoning="Literal interpretation of the stated query",
        ))

        # Check for ambiguous pronouns or references
        if re.search(r"\b(it|this|that|these|those)\b", query, re.IGNORECASE):
            interpretations.append(Interpretation(
                text=f"Clarification needed: ambiguous reference in '{query[:50]}...'",
                probability=0.2,
                reasoning="Contains ambiguous pronouns that could refer to multiple things",
            ))

        # Check for implicit context need
        if re.search(r"\b(fix|debug|solve|error|bug|issue|problem)\b", query, re.IGNORECASE):
            interpretations.append(Interpretation(
                text="User needs debugging help -- may need to see code/logs first",
                probability=0.15,
                reasoning="Debugging queries often need more context than provided",
            ))

        # Check for decision query
        if re.search(r"\b(should|better|recommend|choose|pick|select)\b", query, re.IGNORECASE):
            interpretations.append(Interpretation(
                text="Decision query -- needs trade-off analysis, not single answer",
                probability=0.15,
                reasoning="Decision queries benefit from multi-perspective analysis",
            ))

        # Normalize probabilities
        total = sum(i.probability for i in interpretations)
        if total > 0:
            for interp in interpretations:
                object.__setattr__(interp, "probability", interp.probability / total)

        return interpretations

    async def _ach_deep(self, query: str, context: str) -> list[Interpretation]:
        """Generate interpretations using LLM for deep analysis."""
        if not self._llm:
            return self._ach_heuristic(query)

        prompt = (
            "Analyze this query and generate 3-5 different interpretations "
            "of what the user actually wants. For each, provide:\n"
            "1. The interpretation\n"
            "2. Probability (0-1) that this is the true intent\n"
            "3. Reasoning\n\n"
            f"Query: {query}\n"
        )
        if context:
            prompt += f"\nConversation context: {context}\n"

        prompt += (
            "\nFormat as numbered list. Be specific about how each "
            "interpretation differs."
        )

        # Use the heuristic result as fallback
        # Deep ACH will be wired when LLMService integration is complete
        return self._ach_heuristic(query)

    # ── Bloom's Level Detection ─────────────────────────────────

    def _detect_bloom_level(self, query: str) -> BloomLevel:
        """Classify query by Bloom's taxonomy level.

        Higher levels need more compute (Kahneman System 2).
        Lower levels can be fast-tracked (Kahneman System 1).
        """
        query_lower = query.lower()

        # Score each level
        scores: dict[BloomLevel, int] = {}
        for level, patterns in _BLOOM_PATTERNS.items():
            score = sum(
                1 for p in patterns if re.search(p, query_lower)
            )
            scores[level] = score

        # Pick highest-scoring level (ties broken by taxonomy order)
        best_level = BloomLevel.UNDERSTAND  # default
        best_score = 0
        for level in reversed(list(BloomLevel)):  # CREATE first
            if scores.get(level, 0) > best_score:
                best_score = scores[level]
                best_level = level

        return best_level
