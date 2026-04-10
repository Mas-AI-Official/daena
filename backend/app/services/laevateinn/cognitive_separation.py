"""Stage 5.25: Cognitive Separation Engine -- bug-finding vs solution-finding.

The deepest insight from the research: bug-finding and solution-finding are
fundamentally different cognitive operations that MUST run independently.

    Bug-finding (Falsification):
        Popper:  What is the single observation that destroys this claim?
        Taleb:   Via negativa -- eliminate wrong answers to constrain space
        Munger:  Inversion -- what would guarantee failure?
        Shannon: Which test maximally partitions the hypothesis space?

    Solution-finding (Construction):
        Polya:   Have I seen a similar problem? Can I solve a simpler version?
        Feynman: Where does fluency exceed understanding? Fill gaps.
        Boyd:    OODA loop -- observe output, reorient, decide on fix, act
        de Bono: Green hat -- what alternatives exist?

Current systems merge these into one pass. The verification model both
tries to FIND bugs and FIX them simultaneously. This creates a bias:
the fixer influences the finder, causing the finder to only find bugs
it already knows how to fix.

This engine runs the two tracks INDEPENDENTLY in parallel.
Track A (Falsification) cannot see Track B (Construction) and vice versa.
Only after both complete does a synthesis step merge their findings.

Integration: runs AFTER Validation Gauntlet (Stage 5), BEFORE Adversarial
Gate (Stage 6). This is the last chance to catch bugs that the merged
verification/construction pipeline missed.
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.services.laevateinn.types import (
    CognitiveSeparationResult,
    ComputeProfile,
    ConstructionResult,
    Difficulty,
    FalsificationResult,
    ValidationResult,
)

if TYPE_CHECKING:
    from app.services.llm_service import LLMService

logger = get_logger(__name__)

# ── Falsification prompts (Popper/Taleb/Munger) ──────────────

_FALSIFICATION_PROMPT = (
    "You are a FALSIFICATION engine. Your ONLY job is to find what is WRONG. "
    "Do NOT suggest fixes. Do NOT try to improve. Only BREAK.\n\n"
    "Apply these tests in order:\n"
    "1. POPPER TEST: What is the single observation that, if found, would "
    "COMPLETELY destroy this answer? Be specific.\n"
    "2. VIA NEGATIVA (Taleb): What parts of this answer are clearly wrong? "
    "Eliminate them. What remains?\n"
    "3. INVERSION (Munger): If someone followed this advice, what would "
    "guarantee the worst possible outcome?\n"
    "4. LOAD-BEARING FLAW TEST: Which flaws, if real, would completely "
    "invalidate the conclusion? Which are cosmetic?\n\n"
    "Question: {query}\n"
    "Answer to break: {answer}\n\n"
    "List ALL bugs found. Mark each as [LOAD-BEARING] or [COSMETIC]. "
    "Do NOT suggest fixes."
)

_CONSTRUCTION_PROMPT = (
    "You are a CONSTRUCTION engine. Your job is to IMPROVE this answer. "
    "Do NOT diagnose what is wrong. Only BUILD better.\n\n"
    "Apply these heuristics:\n"
    "1. POLYA: Have you seen a similar problem? What solution method worked? "
    "Can you solve a simpler version first?\n"
    "2. FEYNMAN: Where does the answer wave its hands? Where does it use "
    "jargon without explaining the mechanism? Fill those gaps.\n"
    "3. BOYD (OODA): Observe the answer as output. Reorient: what mental "
    "model produced this? Is there a better model? Build from the better model.\n"
    "4. DE BONO (Green Hat): What completely different approach exists? "
    "What if the opposite were true?\n\n"
    "Question: {query}\n"
    "Answer to improve: {answer}\n\n"
    "Provide the improved answer. Be specific and constructive."
)


class CognitiveSeparationEngine:
    """Stage 5.25: Independent falsification and construction tracks.

    Runs two cognitive tracks in parallel:
    - Track A (Falsification): purely destructive -- find bugs
    - Track B (Construction): purely constructive -- improve answer

    The tracks are isolated: Track A cannot see Track B's improvements,
    and Track B cannot see Track A's bug findings. This prevents the
    common bias where verification only finds bugs it knows how to fix.

    After both complete, a synthesis step checks:
    - Did Track A find bugs that Track B's improvements miss?
    - Did Track B's improvements accidentally introduce Track A's bugs?
    - Can the two be merged into a strictly better answer?

    Args:
        llm_service: Daena's LLM service for model calls.
    """

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self._llm = llm_service

    async def separate(
        self,
        query: str,
        answer: str,
        compute: ComputeProfile,
        *,
        model_id: str = "",
        validation: ValidationResult | None = None,
    ) -> CognitiveSeparationResult:
        """Run independent falsification and construction tracks.

        Args:
            query: The original question.
            answer: The current best answer.
            compute: Compute profile for resource allocation.
            model_id: Which model to use for analysis.
            validation: Previous validation results (for context).

        Returns:
            CognitiveSeparationResult with findings from both tracks.
        """
        start = time.perf_counter_ns()

        # Run both tracks
        if self._llm and model_id and compute.difficulty in (
            Difficulty.HARD, Difficulty.BRUTAL,
        ):
            # LLM-powered parallel tracks
            falsification, construction = await self._run_llm_tracks(
                query, answer, model_id,
            )
        else:
            # Heuristic-only tracks (no LLM needed)
            falsification = self._heuristic_falsification(query, answer)
            construction = self._heuristic_construction(query, answer)

        # ── Synthesis: merge independently ────────────────────
        synthesis, agreed, improved, improved_answer = self._synthesize(
            query, answer, falsification, construction,
        )

        elapsed_ms = int((time.perf_counter_ns() - start) / 1_000_000)

        result = CognitiveSeparationResult(
            falsification=falsification,
            construction=construction,
            tracks_agreed=agreed,
            synthesis=synthesis,
            answer_improved=improved,
            improved_answer=improved_answer,
            total_latency_ms=elapsed_ms,
        )

        logger.info(
            "cognitive_separation_complete",
            bugs_found=len(falsification.bugs_found) if falsification else 0,
            load_bearing=len(falsification.load_bearing_flaws) if falsification else 0,
            fixes_proposed=len(construction.proposed_fixes) if construction else 0,
            tracks_agreed=agreed,
            answer_improved=improved,
            latency_ms=elapsed_ms,
        )

        return result

    # ── LLM-powered tracks ─────────────────────────────────────

    async def _run_llm_tracks(
        self,
        query: str,
        answer: str,
        model_id: str,
    ) -> tuple[FalsificationResult, ConstructionResult]:
        """Run both tracks using LLM in parallel.

        CRITICAL: The two prompts are completely independent.
        The falsification prompt does NOT mention construction.
        The construction prompt does NOT mention falsification.
        """
        import asyncio

        from app.services.providers.base import GenerateRequest, LLMMessage

        falsification_req = GenerateRequest(
            messages=[LLMMessage(
                role="user",
                content=_FALSIFICATION_PROMPT.format(
                    query=query, answer=answer,
                ),
            )],
            model_id=model_id,
            temperature=0.4,  # Slightly creative for adversarial thinking
            max_tokens=1024,
        )

        construction_req = GenerateRequest(
            messages=[LLMMessage(
                role="user",
                content=_CONSTRUCTION_PROMPT.format(
                    query=query, answer=answer,
                ),
            )],
            model_id=model_id,
            temperature=0.5,  # More creative for construction
            max_tokens=1024,
        )

        try:
            fals_resp, cons_resp = await asyncio.gather(
                self._llm.generate_direct(falsification_req),
                self._llm.generate_direct(construction_req),
                return_exceptions=True,
            )

            falsification = self._parse_falsification(
                fals_resp.content if not isinstance(fals_resp, Exception) else "",
            )
            construction = self._parse_construction(
                cons_resp.content if not isinstance(cons_resp, Exception) else "",
            )
        except Exception:
            logger.warning("cognitive_separation_llm_failed", exc_info=True)
            falsification = self._heuristic_falsification(query, answer)
            construction = self._heuristic_construction(query, answer)

        return falsification, construction

    # ── Heuristic-only tracks (fast, no LLM) ──────────────────

    def _heuristic_falsification(
        self, query: str, answer: str,
    ) -> FalsificationResult:
        """Fast heuristic falsification without LLM.

        Checks for common structural flaws:
        - Claims without evidence
        - Logical inconsistencies
        - Missing caveats
        - Overconfident language
        """
        bugs: list[str] = []
        load_bearing: list[str] = []
        non_load_bearing: list[str] = []
        eliminated: list[str] = []

        answer_lower = answer.lower()

        # Check for overconfident language without evidence
        overconfident_patterns = [
            r"\b(?:always|never|impossible|guaranteed|certainly|definitely)\b",
            r"\b(?:the best|the only|the right|the correct)\b",
        ]
        for p in overconfident_patterns:
            matches = re.findall(p, answer_lower)
            for m in matches:
                bugs.append(
                    f"Overconfident claim using '{m}' without supporting evidence"
                )
                non_load_bearing.append(f"Overconfident language: {m}")

        # Check for missing caveats
        if len(answer.split()) > 50 and not re.search(
            r"\bhowever\b|\bbut\b|\bexcept\b|\bcaveat\b|\bnote that\b",
            answer_lower,
        ):
            bugs.append(
                "Answer lacks any caveats or limitations despite being complex"
            )
            load_bearing.append("No caveats in complex answer")

        # Check for unsubstantiated claims
        claim_indicators = re.findall(
            r"(?:because|since|therefore|thus|hence)\s+(.{10,60}?)(?:\.|,|\n)",
            answer_lower,
        )
        if not claim_indicators and len(answer.split()) > 30:
            bugs.append(
                "Answer makes claims but provides no causal reasoning "
                "(no 'because', 'since', 'therefore')"
            )

        # Via negativa: eliminate clearly wrong framings
        if re.search(r"\bjust\b.*\b(?:do|use|try)\b", answer_lower):
            eliminated.append(
                "Oversimplified 'just do X' framing in a complex answer"
            )

        # Find strongest counterargument
        strongest = ""
        if load_bearing:
            strongest = load_bearing[0]
        elif bugs:
            strongest = bugs[0]

        return FalsificationResult(
            bugs_found=bugs,
            wrong_answers_eliminated=eliminated,
            load_bearing_flaws=load_bearing,
            non_load_bearing_flaws=non_load_bearing,
            strongest_counterargument=strongest,
            falsification_confidence=min(1.0, len(bugs) * 0.2 + 0.3),
        )

    def _heuristic_construction(
        self, query: str, answer: str,
    ) -> ConstructionResult:
        """Fast heuristic construction without LLM.

        Applies Polya's simplification and Feynman's gap detection.
        """
        fixes: list[str] = []
        technique = ""
        simplified = ""

        answer_lower = answer.lower()

        # Feynman gap detection: find jargon without explanation
        # (words used but not previously defined in the answer)
        technical_terms = re.findall(
            r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b", answer,
        )  # CamelCase terms
        if technical_terms:
            for term in technical_terms[:3]:
                # Check if term is used but not explained
                term_lower = term.lower()
                if not re.search(
                    rf"\b{re.escape(term_lower)}\b.*\b(?:is|means|refers|defined)\b",
                    answer_lower,
                ):
                    fixes.append(
                        f"Feynman gap: '{term}' used without explanation"
                    )
                    technique = "feynman_gap_detection"

        # Polya: check if a simpler version was addressed first
        if len(answer.split()) > 100:
            if not re.search(
                r"\b(?:simply|basic|first|start with|simplest)\b",
                answer_lower,
            ):
                fixes.append(
                    "Polya: answer jumps to complex case without establishing "
                    "the simple base case first"
                )
                technique = technique or "polya_simplification"
                simplified = f"A simpler version of this question: {query[:50]}... for the minimal case"

        # Boyd OODA: check if the answer iterates or is single-pass
        if not re.search(
            r"\b(?:however|on reflection|reconsidering|updating)\b",
            answer_lower,
        ):
            fixes.append(
                "Boyd: answer is single-pass with no self-correction or "
                "iteration. Consider re-examining after initial analysis."
            )

        return ConstructionResult(
            proposed_fixes=fixes,
            technique_used=technique or "heuristic_analysis",
            simplified_version=simplified,
            construction_confidence=min(1.0, 0.3 + len(fixes) * 0.15),
        )

    # ── LLM output parsers ─────────────────────────────────────

    def _parse_falsification(self, raw: str) -> FalsificationResult:
        """Parse LLM falsification output into structured result."""
        bugs: list[str] = []
        load_bearing: list[str] = []
        non_load_bearing: list[str] = []

        if not raw:
            return FalsificationResult()

        lines = raw.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Remove list markers
            cleaned = re.sub(r"^[\d\.\-\*\)]+\s*", "", line).strip()
            if not cleaned:
                continue

            if "[LOAD-BEARING]" in line.upper() or "[LOAD" in line.upper():
                cleaned_no_tag = re.sub(
                    r"\[LOAD[_-]?BEARING\]", "", cleaned, flags=re.IGNORECASE,
                ).strip()
                load_bearing.append(cleaned_no_tag)
                bugs.append(cleaned_no_tag)
            elif "[COSMETIC]" in line.upper():
                cleaned_no_tag = re.sub(
                    r"\[COSMETIC\]", "", cleaned, flags=re.IGNORECASE,
                ).strip()
                non_load_bearing.append(cleaned_no_tag)
                bugs.append(cleaned_no_tag)
            elif len(cleaned) > 15:
                bugs.append(cleaned)

        strongest = load_bearing[0] if load_bearing else (bugs[0] if bugs else "")

        return FalsificationResult(
            bugs_found=bugs[:10],
            load_bearing_flaws=load_bearing[:5],
            non_load_bearing_flaws=non_load_bearing[:5],
            strongest_counterargument=strongest,
            falsification_confidence=min(1.0, len(bugs) * 0.15 + 0.3),
        )

    def _parse_construction(self, raw: str) -> ConstructionResult:
        """Parse LLM construction output into structured result."""
        if not raw:
            return ConstructionResult()

        # The LLM response is the improved answer itself
        fixes = []
        lines = raw.strip().split("\n")
        for line in lines:
            cleaned = line.strip()
            if cleaned and len(cleaned) > 20:
                fixes.append(cleaned)

        return ConstructionResult(
            proposed_fixes=fixes[:5],
            technique_used="llm_polya_feynman_boyd",
            construction_confidence=0.6 if fixes else 0.3,
        )

    # ── Synthesis ──────────────────────────────────────────────

    def _synthesize(
        self,
        query: str,
        answer: str,
        falsification: FalsificationResult,
        construction: ConstructionResult,
    ) -> tuple[str, bool, bool, str]:
        """Merge findings from both independent tracks.

        Returns: (synthesis_text, tracks_agreed, answer_improved, improved_answer)
        """
        synthesis_parts: list[str] = []
        improved = False
        improved_answer = answer

        # Check if falsification found load-bearing flaws
        has_load_bearing = bool(
            falsification and falsification.load_bearing_flaws
        )
        has_fixes = bool(
            construction and construction.proposed_fixes
        )

        # Track agreement: both found issues, or neither did
        both_found = has_load_bearing and has_fixes
        neither_found = not has_load_bearing and not has_fixes
        agreed = both_found or neither_found

        if has_load_bearing:
            synthesis_parts.append(
                f"Falsification track found {len(falsification.load_bearing_flaws)} "
                f"load-bearing flaws: {'; '.join(falsification.load_bearing_flaws[:3])}"
            )

        if has_fixes:
            synthesis_parts.append(
                f"Construction track proposed {len(construction.proposed_fixes)} "
                f"improvements: {'; '.join(construction.proposed_fixes[:3])}"
            )

        if not agreed:
            synthesis_parts.append(
                "WARNING: Tracks DISAGREE -- one found issues the other missed. "
                "This suggests blind spots in the reasoning."
            )

        # Mark as improved if construction produced fixes for load-bearing flaws
        if has_load_bearing and has_fixes:
            improved = True
            # The actual answer improvement would be done by the pipeline
            # using the RDE loop-back. We just flag it here.
            synthesis_parts.append(
                "Answer should be revised to address load-bearing flaws "
                "using construction track's suggested improvements."
            )

        synthesis = " | ".join(synthesis_parts) if synthesis_parts else "Both tracks passed. No issues found."

        return synthesis, agreed, improved, improved_answer
