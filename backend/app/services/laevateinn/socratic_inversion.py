"""Stage 0.5: Socratic Inversion Engine -- upgrade the question before answering.

The deepest gap in AI reasoning: systems verify ANSWERS but never verify QUESTIONS.
Mythos asks "is my answer right?" (Level 1). This engine asks "am I asking the
RIGHT question?" (Level 2) and "is my METHOD of generating questions effective
for THIS type of problem?" (Level 3).

Instead of: question -> answer -> verify answer
Does: question -> upgrade question -> THEN answer the upgraded question

Implements thinking systems from:
    Socrates:  Elenchus -- extract entailments, test contradictions
    Musk:      First principles -- decompose to physics, rebuild from scratch
    Polya:     Decomposition -- have I seen this before? simpler version?
    Shannon:   Information gain -- which question maximally reduces uncertainty?
    Kahneman:  Substitution detection -- am I answering an easier question?
    Munger:    Inversion -- what would guarantee failure?
    Taleb:     Via negativa -- eliminate bad questions to find good ones
    Feynman:   Gap detection -- where does my fluency exceed my understanding?

Integration: runs BEFORE DCE (Stage 1) to upgrade the raw query.
The upgraded query is what DCE and all downstream stages actually process.
"""

from __future__ import annotations

import math
import re
import time
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.services.laevateinn.types import (
    QuestionLevel,
    QuestionUpgrade,
    SocraticInversionResult,
)

if TYPE_CHECKING:
    from app.services.llm_service import LLMService

logger = get_logger(__name__)

# ── Substitution detection patterns (Kahneman) ────────────────
# When users ask a hard question, they often substitute an easier one.
# "Should I use Redis or Postgres for caching?" is easier than
# "Do I actually need caching, or is my real problem a slow query?"
_SUBSTITUTION_PATTERNS: list[tuple[str, str]] = [
    # (surface question pattern, deeper question it masks)
    (r"\bwhich (?:is|are) better\b", "What are the actual requirements that determine the choice?"),
    (r"\bshould I use (\w+) or (\w+)\b", "What problem am I actually solving, and does either tool address it?"),
    (r"\bwhat is the best\b", "Best by what criteria, and are those the right criteria?"),
    (r"\bhow do I fix\b", "What is the root cause, not just the symptom?"),
    (r"\bwhy (?:is|does|do)\b.*(?:not work|fail|error|break)", "What assumptions am I making about how it should work?"),
    (r"\bcan you (?:help|write|create|build)\b", "What am I actually trying to achieve with this?"),
    (r"\bwhat (?:is|are) the (?:pros|cons|advantages|disadvantages)\b", "What is the decision I am actually facing?"),
]

# ── Anchoring detection patterns (Kahneman) ────────────────────
_ANCHOR_PATTERNS: list[str] = [
    r"\b(?:I think|I believe|I heard|someone said|I read that)\b",
    r"\b(?:usually|typically|normally|traditionally|most people)\b",
    r"\b(?:\d+(?:\.\d+)?%)\b",  # Specific numbers can anchor
    r"\b(?:my colleague|my boss|my friend) (?:said|told|suggested)\b",
]

# ── First principles decomposition triggers (Musk) ────────────
_CONVENTION_SIGNALS: list[str] = [
    r"\b(?:everyone does|standard practice|industry standard|best practice)\b",
    r"\b(?:traditionally|historically|conventionally|usually done)\b",
    r"\b(?:the way it's done|how it's always been|common approach)\b",
]

# ── De Bono frame indicators ──────────────────────────────────
_THINKING_HATS = {
    "white": r"\b(?:data|facts|numbers|evidence|statistics|measured)\b",
    "red": r"\b(?:feel|gut|intuition|sense|emotion|worry|excited)\b",
    "black": r"\b(?:risk|danger|problem|fail|wrong|bad|concern)\b",
    "yellow": r"\b(?:benefit|opportunity|advantage|value|upside|positive)\b",
    "green": r"\b(?:alternative|creative|different|new|innovate|what if)\b",
    "blue": r"\b(?:process|approach|method|strategy|framework|thinking)\b",
}


class SocraticInversionEngine:
    """Stage 0.5: Upgrade the question before answering it.

    This is the highest-leverage stage in the entire pipeline because
    every downstream stage benefits from a better question.

    The engine applies 5 upgrade passes in sequence:
    1. Substitution detection (Kahneman): is the user asking an easier question?
    2. First principles decomposition (Musk): strip to fundamentals
    3. Inversion (Munger): what would guarantee failure?
    4. Via negativa (Taleb): eliminate clearly wrong questions
    5. Information gain scoring (Shannon): which upgraded question reduces
       uncertainty the most?

    The output is the single best upgraded question plus the full upgrade chain.

    Args:
        llm_service: Daena's LLM service (used for HARD+ difficulty only).
    """

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self._llm = llm_service

    async def upgrade(
        self,
        query: str,
        *,
        context: str = "",
        use_llm: bool = False,
        model_id: str = "",
    ) -> SocraticInversionResult:
        """Run the full Socratic Inversion pipeline on a query.

        Args:
            query: Raw user query.
            context: Conversation context (for anchoring detection).
            use_llm: Whether to use LLM for deep upgrades (HARD+ only).
            model_id: Which model to use for LLM upgrades.

        Returns:
            SocraticInversionResult with the upgraded question and chain.
        """
        start = time.perf_counter_ns()
        upgrades: list[QuestionUpgrade] = []
        current = query
        eliminated: list[str] = []

        # ── Pass 1: Substitution Detection (Kahneman) ─────────
        substitution_detected, substitution_explanation, deeper = (
            self._detect_substitution(query)
        )
        if substitution_detected and deeper:
            upgrade = QuestionUpgrade(
                original=current,
                upgraded=deeper,
                level=QuestionLevel.IMPLICIT,
                technique_used="kahneman_substitution",
                information_gain=self._estimate_info_gain(current, deeper),
                reasoning=substitution_explanation,
            )
            upgrades.append(upgrade)
            current = deeper

        # ── Pass 2: Anchoring Detection (Kahneman) ────────────
        anchor_detected = self._detect_anchor(query, context)

        # ── Pass 3: First Principles Decomposition (Musk) ─────
        fp_question = self._first_principles_decompose(current)
        if fp_question and fp_question != current:
            upgrade = QuestionUpgrade(
                original=current,
                upgraded=fp_question,
                level=QuestionLevel.STRUCTURAL,
                technique_used="musk_first_principles",
                information_gain=self._estimate_info_gain(current, fp_question),
                reasoning="Stripped conventional assumptions to reveal fundamental question",
            )
            upgrades.append(upgrade)
            current = fp_question

        # ── Pass 4: Inversion (Munger) ────────────────────────
        inverted = self._invert_question(current)

        # ── Pass 5: Via Negativa (Taleb) ──────────────────────
        bad_questions = self._via_negativa(query, current)
        eliminated.extend(bad_questions)

        # ── Pass 6: Frame Analysis (de Bono) ──────────────────
        missing_frames = self._detect_missing_frames(current)
        if missing_frames and len(missing_frames) >= 3:
            # Question is missing too many perspectives -- upgrade
            frame_upgrade = self._upgrade_for_missing_frames(
                current, missing_frames,
            )
            if frame_upgrade:
                upgrade = QuestionUpgrade(
                    original=current,
                    upgraded=frame_upgrade,
                    level=QuestionLevel.STRUCTURAL,
                    technique_used="debono_frame_rotation",
                    information_gain=self._estimate_info_gain(
                        current, frame_upgrade,
                    ),
                    reasoning=f"Missing frames: {', '.join(missing_frames)}",
                )
                upgrades.append(upgrade)
                current = frame_upgrade

        # ── Pass 7: LLM-powered deep upgrade (HARD+ only) ────
        if use_llm and self._llm and model_id:
            llm_upgrade = await self._llm_deep_upgrade(
                query, current, context, model_id,
            )
            if llm_upgrade and llm_upgrade != current:
                upgrade = QuestionUpgrade(
                    original=current,
                    upgraded=llm_upgrade,
                    level=QuestionLevel.GENERATIVE,
                    technique_used="socratic_elenchus_llm",
                    information_gain=self._estimate_info_gain(
                        current, llm_upgrade,
                    ),
                    reasoning="LLM-powered Socratic deepening",
                )
                upgrades.append(upgrade)
                current = llm_upgrade

        # ── Select best upgrade by information gain ───────────
        best = current
        depth = QuestionLevel.SURFACE
        if upgrades:
            best_upgrade = max(upgrades, key=lambda u: u.information_gain)
            best = best_upgrade.upgraded
            depth = best_upgrade.level

        elapsed_ms = int((time.perf_counter_ns() - start) / 1_000_000)

        result = SocraticInversionResult(
            original_question=query,
            upgraded_question=best,
            upgrade_chain=upgrades,
            depth_reached=depth,
            substitution_detected=substitution_detected,
            substitution_explanation=substitution_explanation,
            inverted_form=inverted,
            eliminated_questions=eliminated,
            anchor_detected=anchor_detected,
            total_latency_ms=elapsed_ms,
        )

        if upgrades:
            logger.info(
                "socratic_inversion_complete",
                upgrades=len(upgrades),
                depth=depth.value,
                substitution=substitution_detected,
                anchor=anchor_detected,
                eliminated=len(eliminated),
                latency_ms=elapsed_ms,
            )

        return result

    # ── Private methods ────────────────────────────────────────

    def _detect_substitution(
        self, query: str,
    ) -> tuple[bool, str, str]:
        """Kahneman: detect when the user is asking an easier question.

        Returns (detected, explanation, deeper_question).
        """
        query_lower = query.lower()
        for pattern, deeper_template in _SUBSTITUTION_PATTERNS:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return (
                    True,
                    f"Surface question matches substitution pattern: {pattern}",
                    deeper_template,
                )
        return False, "", ""

    def _detect_anchor(self, query: str, context: str) -> bool:
        """Kahneman: detect anchoring bias in the question."""
        combined = f"{context} {query}".lower()
        matches = sum(
            1 for p in _ANCHOR_PATTERNS
            if re.search(p, combined, re.IGNORECASE)
        )
        return matches >= 2

    def _first_principles_decompose(self, query: str) -> str:
        """Musk: strip conventional assumptions from the question.

        Detects when the question assumes a convention ("best practice",
        "industry standard") and reformulates to ask about the underlying
        physics/constraints instead.
        """
        query_lower = query.lower()
        has_convention = any(
            re.search(p, query_lower) for p in _CONVENTION_SIGNALS
        )
        if not has_convention:
            return query

        # Strip the convention and ask about fundamentals
        stripped = query
        for pattern in _CONVENTION_SIGNALS:
            stripped = re.sub(pattern, "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s+", " ", stripped).strip()

        if len(stripped) > 10:
            return (
                f"Setting aside standard practice: what do the actual "
                f"constraints and requirements demand? {stripped}"
            )
        return query

    def _invert_question(self, query: str) -> str:
        """Munger: generate the inverted form of the question.

        Instead of "How to succeed at X?", generate "What would guarantee
        failure at X?"
        """
        query_lower = query.lower()

        # Pattern matching for common question forms
        if re.search(r"\bhow (?:to|do I|can I|should I)\b", query_lower):
            core = re.sub(
                r"^.*?\bhow (?:to|do I|can I|should I)\b\s*",
                "", query, flags=re.IGNORECASE,
            ).strip().rstrip("?")
            return f"What would guarantee failure at {core}?"

        if re.search(r"\bwhat is the best\b", query_lower):
            core = re.sub(
                r"^.*?\bwhat is the best\b\s*",
                "", query, flags=re.IGNORECASE,
            ).strip().rstrip("?")
            return f"What is the worst possible choice for {core}?"

        if re.search(r"\bshould I\b", query_lower):
            core = re.sub(
                r"^.*?\bshould I\b\s*",
                "", query, flags=re.IGNORECASE,
            ).strip().rstrip("?")
            return f"What conditions would make it a disaster to {core}?"

        # Generic inversion
        return f"What would make '{query}' lead to the worst possible outcome?"

    def _via_negativa(self, original: str, current: str) -> list[str]:
        """Taleb: eliminate clearly wrong question framings.

        Intelligence by subtraction: identify question framings that are
        definitely wrong and remove them from consideration.
        """
        eliminated: list[str] = []
        original_lower = original.lower()

        # Eliminate yes/no framings of nuanced questions
        if re.search(r"^(?:is|are|does|do|can|will|should)\b", original_lower):
            word_count = len(original.split())
            if word_count > 8:
                eliminated.append(
                    f"Yes/no framing of complex question: '{original[:60]}...' "
                    f"-- binary answer would lose nuance"
                )

        # Eliminate "which is better" without criteria
        if re.search(r"\bwhich (?:is|are) better\b", original_lower):
            if not re.search(r"\bfor\b|\bwhen\b|\bgiven\b", original_lower):
                eliminated.append(
                    "Comparison without criteria: 'which is better' needs "
                    "'for what purpose' to be answerable"
                )

        # Eliminate vague "how to" without constraints
        if re.search(r"\bhow to\b", original_lower):
            if len(original.split()) < 6:
                eliminated.append(
                    f"Underconstrained question: '{original}' -- too vague "
                    f"to produce a specific, useful answer"
                )

        return eliminated

    def _detect_missing_frames(self, query: str) -> list[str]:
        """de Bono: detect which thinking hats are missing from the question."""
        query_lower = query.lower()
        missing = []
        for hat, pattern in _THINKING_HATS.items():
            if not re.search(pattern, query_lower):
                missing.append(hat)
        return missing

    def _upgrade_for_missing_frames(
        self, query: str, missing: list[str],
    ) -> str:
        """Upgrade a question to cover missing thinking frames."""
        additions = []
        if "black" in missing:
            additions.append("What could go wrong?")
        if "green" in missing:
            additions.append("What alternatives exist?")
        if "red" in missing:
            additions.append("What does intuition suggest?")
        if "white" in missing:
            additions.append("What data would inform this?")

        if additions:
            return f"{query} (Also consider: {' '.join(additions[:2])})"
        return query

    def _estimate_info_gain(self, original: str, upgraded: str) -> float:
        """Shannon: estimate how much the upgrade reduces uncertainty.

        Uses a heuristic based on:
        1. Semantic distance (different words = different question = higher gain)
        2. Specificity increase (more constrained = less entropy)
        3. Depth increase (structural/generative > surface > implicit)

        Full Shannon computation would require a hypothesis space model.
        This heuristic approximates it.
        """
        orig_words = set(original.lower().split())
        up_words = set(upgraded.lower().split())

        if not orig_words or not up_words:
            return 0.0

        # Jaccard distance (how different are the questions)
        intersection = orig_words & up_words
        union = orig_words | up_words
        semantic_distance = 1.0 - (len(intersection) / max(len(union), 1))

        # Specificity: longer, more constrained questions have higher info gain
        specificity_bonus = min(
            0.3,
            max(0, len(up_words) - len(orig_words)) * 0.05,
        )

        # Constraint indicators
        constraint_words = {
            "when", "given", "assuming", "if", "for", "because",
            "constraint", "requirement", "criteria",
        }
        constraint_bonus = min(
            0.2,
            len(up_words & constraint_words) * 0.05,
        )

        gain = min(1.0, semantic_distance * 0.5 + specificity_bonus + constraint_bonus)
        return round(gain, 3)

    async def _llm_deep_upgrade(
        self,
        original: str,
        current_best: str,
        context: str,
        model_id: str,
    ) -> str:
        """Use an LLM for deep Socratic question upgrading.

        Only called for HARD+ difficulty queries.
        """
        if not self._llm:
            return current_best

        prompt = (
            "You are a Socratic questioning engine. Your job is to find "
            "the REAL question behind the stated question.\n\n"
            "The user asked: {original}\n\n"
            "Current best reformulation: {current}\n\n"
            "Context: {context}\n\n"
            "Apply these tests:\n"
            "1. SUBSTITUTION: Is the user asking an easier question to avoid "
            "a harder one? What is the harder question?\n"
            "2. FIRST PRINCIPLES: What assumptions does this question make? "
            "Which are conventions (breakable) vs. physics (unbreakable)?\n"
            "3. GENERATIVE: What single question, if answered, would unlock "
            "the most downstream insight?\n\n"
            "Return ONLY the single best upgraded question. No explanation."
        ).format(
            original=original,
            current=current_best,
            context=context[:500] if context else "none",
        )

        from app.services.providers.base import GenerateRequest, LLMMessage

        request = GenerateRequest(
            messages=[LLMMessage(role="user", content=prompt)],
            model_id=model_id,
            temperature=0.3,
            max_tokens=256,
        )
        try:
            result = await self._llm.generate_direct(request)
            upgraded = result.content.strip().strip('"').strip("'")
            if 10 < len(upgraded) < 500:
                return upgraded
        except Exception:
            logger.warning("socratic_llm_upgrade_failed", exc_info=True)

        return current_best
