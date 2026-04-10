"""Stage 1.75: Question Quality Auditor -- Meta-Level 3 cognition.

The gap nobody talks about: AI systems generate verification questions
about their answers, but never audit the QUALITY of those questions.

Mythos verifies: "Is this answer correct?" (Level 1)
Laevateinn verifies: "Am I asking the right questions to check?" (Level 2)
This engine verifies: "Is my METHOD of generating questions effective
for THIS type of problem?" (Level 3)

Uses information-theoretic and falsificationist metrics:
    Shannon:    Information gain -- does this question reduce uncertainty?
    Popper:     Falsifiability -- can this question distinguish hypotheses?
    de Bono:    Frame coverage -- are all thinking perspectives represented?
    Hofstadter: Meta-level tracking -- how deep is our self-questioning?
    Taleb:      Via negativa -- remove bad questions to find good ones
    Feynman:    Gap detection -- where is fluency masking ignorance?

Integration: runs AFTER DCE + Epistemic (Stage 1.5), BEFORE DCS (Stage 2).
Acts as a quality gate on the comprehension output. Can loop back to
DCE or Socratic Inversion if question quality is too low.
"""

from __future__ import annotations

import math
import re
import time
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.services.laevateinn.types import (
    ComprehensionResult,
    EpistemicState,
    QuestionAssessment,
    QuestionAuditResult,
    QuestionDefect,
    SocraticInversionResult,
)

if TYPE_CHECKING:
    from app.services.llm_service import LLMService

logger = get_logger(__name__)

# ── de Bono Six Hats: question type classification ────────────
_HAT_QUESTION_PATTERNS = {
    "white": [r"\bwhat data\b", r"\bwhat evidence\b", r"\bwhat facts\b", r"\bhow many\b", r"\bwhat is the\b"],
    "red": [r"\bfeel\b", r"\bintuition\b", r"\bgut\b", r"\bsense\b", r"\bemotion"],
    "black": [r"\bwhat could go wrong\b", r"\brisk\b", r"\bdanger\b", r"\bfail\b", r"\bproblem\b"],
    "yellow": [r"\bbenefit\b", r"\bopportunit\b", r"\badvantage\b", r"\bvalue\b", r"\bupside\b"],
    "green": [r"\balternativ\b", r"\bwhat if\b", r"\bcreativ\b", r"\binnovate\b", r"\bdifferent\b"],
    "blue": [r"\bprocess\b", r"\bmethod\b", r"\bapproach\b", r"\bstrateg\b", r"\bthinking\b"],
}

# ── Unfalsifiable question patterns (Popper) ──────────────────
_UNFALSIFIABLE_PATTERNS: list[str] = [
    r"^is (?:it|this) (?:good|bad|right|wrong)\?$",  # Too vague to test
    r"\b(?:always|never|every|all|none)\b",  # Universal claims (can't prove all)
    r"\b(?:should|ought|must)\b.*\?$",  # Normative questions without criteria
]

# ── Derivative question patterns ──────────────────────────────
# Questions that just restate the answer in question form
_DERIVATIVE_INDICATORS: list[str] = [
    r"^is (?:it|this) (?:true|correct|right) that\b",
    r"^does (?:this|the) answer\b",
    r"^is the (?:response|answer|solution)\b",
]


class QuestionQualityAuditor:
    """Stage 1.75: Meta-Level 3 question quality auditing.

    Audits the quality of questions generated during comprehension
    and verification. Catches the case where all verification questions
    pass but they were the WRONG questions to ask.

    The auditor evaluates each question on:
    - Information gain (Shannon): expected uncertainty reduction
    - Falsifiability (Popper): can it distinguish competing hypotheses?
    - Independence (Hofstadter): is it independent of the answer?
    - Frame coverage (de Bono): are all perspectives represented?

    If overall quality is below threshold, the auditor triggers a
    loop-back to DCE or Socratic Inversion for re-comprehension.

    Args:
        llm_service: Daena's LLM service (for LLM-powered assessments).
        quality_threshold: Minimum acceptable question quality (0-1).
    """

    def __init__(
        self,
        llm_service: LLMService | None = None,
        quality_threshold: float = 0.4,
    ) -> None:
        self._llm = llm_service
        self._threshold = quality_threshold

    def audit(
        self,
        comprehension: ComprehensionResult,
        *,
        epistemic: EpistemicState | None = None,
        socratic: SocraticInversionResult | None = None,
        answer: str = "",
    ) -> QuestionAuditResult:
        """Audit the quality of questions generated so far.

        Examines:
        1. DCE's sub-questions
        2. DCE's hidden assumptions (as implicit questions)
        3. Any verification questions from depth engine
        4. The "real question" from Tesla resonance

        Args:
            comprehension: Output from DCE (Stage 1).
            epistemic: Output from Epistemic Tracker (Stage 1.5).
            socratic: Output from Socratic Inversion (Stage 0.5).
            answer: Current answer (for independence checking).

        Returns:
            QuestionAuditResult with assessments and improvement suggestions.
        """
        start = time.perf_counter_ns()
        assessments: list[QuestionAssessment] = []

        # ── Gather all questions to audit ─────────────────────
        questions_to_audit: list[str] = []

        if comprehension.sub_questions:
            questions_to_audit.extend(comprehension.sub_questions)

        # Hidden assumptions are implicit questions ("Is X actually true?")
        if comprehension.hidden_assumptions:
            for assumption in comprehension.hidden_assumptions:
                questions_to_audit.append(
                    f"Is the assumption '{assumption}' actually valid?"
                )

        # The real question itself
        if comprehension.real_question:
            questions_to_audit.append(comprehension.real_question)

        # Socratic upgrade chain questions
        if socratic and socratic.upgrade_chain:
            for upgrade in socratic.upgrade_chain:
                questions_to_audit.append(upgrade.upgraded)

        # ── Audit each question ───────────────────────────────
        via_negativa_count = 0
        for q in questions_to_audit:
            assessment = self._assess_question(q, answer, comprehension)
            assessments.append(assessment)
            if assessment.defects:
                via_negativa_count += 1

        # ── Frame coverage analysis (de Bono) ─────────────────
        frame_coverage = self._analyze_frame_coverage(questions_to_audit)

        # ── Missing question types ────────────────────────────
        missing_types = self._identify_missing_question_types(
            questions_to_audit, comprehension, epistemic,
        )

        # ── Meta-level assessment (Hofstadter) ────────────────
        meta_level = self._compute_meta_level(
            comprehension, socratic, assessments,
        )

        # ── Generate upgraded questions for bad ones ──────────
        upgraded = []
        for a in assessments:
            if a.suggested_replacement:
                upgraded.append(a.suggested_replacement)

        # ── Compute overall quality ───────────────────────────
        if assessments:
            scores = [
                (a.information_gain + a.falsifiability + a.independence) / 3.0
                for a in assessments
            ]
            overall = sum(scores) / len(scores)
        else:
            overall = 0.0

        # ── Should we loop back? ──────────────────────────────
        loops_back = overall < self._threshold and len(questions_to_audit) > 0

        elapsed_ms = int((time.perf_counter_ns() - start) / 1_000_000)

        result = QuestionAuditResult(
            questions_audited=len(questions_to_audit),
            assessments=assessments,
            overall_question_quality=round(overall, 3),
            missing_question_types=missing_types,
            frame_coverage=frame_coverage,
            meta_level_reached=meta_level,
            via_negativa_eliminations=via_negativa_count,
            upgraded_questions=upgraded,
            loops_back=loops_back,
            total_latency_ms=elapsed_ms,
        )

        logger.info(
            "question_audit_complete",
            audited=len(questions_to_audit),
            overall_quality=round(overall, 3),
            meta_level=meta_level,
            missing_types=len(missing_types),
            eliminated=via_negativa_count,
            loops_back=loops_back,
            latency_ms=elapsed_ms,
        )

        return result

    # ── Private methods ────────────────────────────────────────

    def _assess_question(
        self,
        question: str,
        answer: str,
        comprehension: ComprehensionResult,
    ) -> QuestionAssessment:
        """Assess a single question on Shannon/Popper/independence metrics."""
        defects: list[QuestionDefect] = []
        q_lower = question.lower()

        # ── Check for derivative questions ────────────────────
        independence = self._score_independence(question, answer)
        if independence < 0.3:
            defects.append(QuestionDefect.DERIVATIVE)

        # ── Check falsifiability (Popper) ─────────────────────
        falsifiability = self._score_falsifiability(question)
        if falsifiability < 0.2:
            defects.append(QuestionDefect.UNFALSIFIABLE)

        # ── Check information gain (Shannon) ──────────────────
        info_gain = self._score_information_gain(
            question, comprehension,
        )
        if info_gain < 0.15:
            defects.append(QuestionDefect.LOW_INFORMATION)

        # ── Check for redundancy ──────────────────────────────
        if comprehension.sub_questions:
            for sq in comprehension.sub_questions:
                if sq != question and self._semantic_overlap(question, sq) > 0.7:
                    defects.append(QuestionDefect.REDUNDANT)
                    break

        # ── Check question level (symptoms vs causes) ─────────
        if re.search(r"\bhow to fix\b|\bwhat error\b|\bwhy doesn't\b", q_lower):
            if not re.search(r"\broot cause\b|\bfundamental\b|\bwhy\b.*\bwhy\b", q_lower):
                defects.append(QuestionDefect.WRONG_LEVEL)

        # ── Missing frame detection ───────────────────────────
        missing = self._detect_missing_perspectives(question)

        # ── Suggest replacement if defective ──────────────────
        replacement = ""
        if defects:
            replacement = self._suggest_replacement(question, defects)

        return QuestionAssessment(
            question=question,
            information_gain=round(info_gain, 3),
            falsifiability=round(falsifiability, 3),
            independence=round(independence, 3),
            defects=defects,
            missing_perspectives=missing,
            suggested_replacement=replacement,
        )

    def _score_independence(self, question: str, answer: str) -> float:
        """Score how independent a question is from the answer.

        A verification question that just restates the answer in question
        form has zero independence. A truly independent question tests
        the answer from an angle the answer didn't address.
        """
        if not answer:
            return 0.8  # No answer to be dependent on

        q_lower = question.lower()

        # Check derivative patterns
        for pattern in _DERIVATIVE_INDICATORS:
            if re.search(pattern, q_lower):
                return 0.1

        # Word overlap: high overlap = low independence
        q_words = set(q_lower.split())
        a_words = set(answer.lower().split())

        if not q_words:
            return 0.5

        overlap = len(q_words & a_words) / len(q_words)
        return round(max(0.1, 1.0 - overlap), 3)

    def _score_falsifiability(self, question: str) -> float:
        """Popper: score how sharply a question can distinguish hypotheses.

        High falsifiability = the answer could clearly be wrong.
        Low falsifiability = any answer is equally valid.
        """
        q_lower = question.lower()

        # Check unfalsifiable patterns
        for pattern in _UNFALSIFIABLE_PATTERNS:
            if re.search(pattern, q_lower):
                return 0.1

        score = 0.5

        # Questions with specific criteria are more falsifiable
        if re.search(r"\bhow (?:many|much|often|long)\b", q_lower):
            score += 0.2
        if re.search(r"\bwhen\b|\bwhere\b|\bwhich specific\b", q_lower):
            score += 0.15
        if re.search(r"\bif\b.*\bthen\b", q_lower):
            score += 0.2  # Conditional questions are highly falsifiable

        # Questions with "always" or "never" are technically very falsifiable
        # (one counterexample disproves), but often unfalsifiable in practice
        if re.search(r"\b(?:always|never)\b", q_lower):
            score -= 0.1

        # Vague questions are less falsifiable
        if len(question.split()) < 5:
            score -= 0.15

        return round(min(1.0, max(0.1, score)), 3)

    def _score_information_gain(
        self,
        question: str,
        comprehension: ComprehensionResult,
    ) -> float:
        """Shannon: estimate expected uncertainty reduction.

        A question with high information gain would significantly
        change our beliefs regardless of which answer we get.
        A question with low information gain confirms what we already know.
        """
        q_lower = question.lower()
        score = 0.3  # Baseline

        # Questions about things we already know have low info gain
        known_terms = set(comprehension.compressed_query.lower().split())
        q_terms = set(q_lower.split())
        novelty = len(q_terms - known_terms) / max(len(q_terms), 1)
        score += novelty * 0.3

        # Questions about hidden assumptions have high info gain
        # (they test unstated beliefs)
        if comprehension.hidden_assumptions:
            for assumption in comprehension.hidden_assumptions:
                if any(
                    word in q_lower
                    for word in assumption.lower().split()[:3]
                ):
                    score += 0.2
                    break

        # "Why" questions generally have higher info gain than "what" questions
        if q_lower.startswith("why"):
            score += 0.15
        elif q_lower.startswith("what if"):
            score += 0.2  # Counterfactuals are high info gain

        return round(min(1.0, score), 3)

    def _semantic_overlap(self, q1: str, q2: str) -> float:
        """Simple word-overlap measure of semantic similarity."""
        w1 = set(q1.lower().split())
        w2 = set(q2.lower().split())
        if not w1 or not w2:
            return 0.0
        intersection = w1 & w2
        union = w1 | w2
        return len(intersection) / max(len(union), 1)

    def _detect_missing_perspectives(self, question: str) -> list[str]:
        """Detect which de Bono thinking perspectives are not covered."""
        q_lower = question.lower()
        missing = []
        for hat, patterns in _HAT_QUESTION_PATTERNS.items():
            if not any(re.search(p, q_lower) for p in patterns):
                missing.append(hat)
        return missing

    def _analyze_frame_coverage(
        self, questions: list[str],
    ) -> dict[str, bool]:
        """Analyze frame coverage across all questions collectively."""
        coverage: dict[str, bool] = {}
        combined = " ".join(questions).lower()
        for hat, patterns in _HAT_QUESTION_PATTERNS.items():
            coverage[hat] = any(
                re.search(p, combined) for p in patterns
            )
        return coverage

    def _identify_missing_question_types(
        self,
        questions: list[str],
        comprehension: ComprehensionResult,
        epistemic: EpistemicState | None,
    ) -> list[str]:
        """Identify which types of questions are missing entirely."""
        missing: list[str] = []
        combined = " ".join(questions).lower()

        # Check for causal questions ("why" questions)
        if not re.search(r"\bwhy\b", combined):
            missing.append("causal_why")

        # Check for counterfactual questions ("what if")
        if not re.search(r"\bwhat if\b|\bwhat would happen\b", combined):
            missing.append("counterfactual")

        # Check for constraint questions ("what prevents")
        if not re.search(
            r"\bwhat prevents\b|\bwhat limits\b|\bconstraint\b", combined,
        ):
            missing.append("constraint_probing")

        # Check for stakeholder questions ("who is affected")
        if not re.search(
            r"\bwho\b.*\baffect\b|\bstakeholder\b|\bimpact\b", combined,
        ):
            missing.append("stakeholder_impact")

        # Check for temporal questions ("when", "how long", "timeline")
        if not re.search(r"\bwhen\b|\btimeline\b|\bhow long\b", combined):
            missing.append("temporal")

        # Check for second-order effects
        if not re.search(r"\bthen what\b|\band then\b|\bdomino\b", combined):
            missing.append("second_order_effects")

        return missing

    def _compute_meta_level(
        self,
        comprehension: ComprehensionResult,
        socratic: SocraticInversionResult | None,
        assessments: list[QuestionAssessment],
    ) -> int:
        """Hofstadter: compute the highest meta-level reached.

        Level 0: Questions about the domain (sub_questions)
        Level 1: Questions about the question (real_question != original)
        Level 2: Questions about the questioning process (socratic upgrades)
        Level 3: Questions about the meta-questioning framework (this audit)
        """
        level = 0

        # Level 0: we have domain questions
        if comprehension.sub_questions:
            level = 0

        # Level 1: we found the real question behind the stated one
        if (
            comprehension.real_question
            and comprehension.real_question != comprehension.original_query
        ):
            level = 1

        # Level 2: Socratic Inversion upgraded the question
        if socratic and socratic.upgrade_chain:
            level = 2

        # Level 3: This audit is running (which it is if we're here)
        if assessments:
            level = 3

        return level

    def _suggest_replacement(
        self,
        question: str,
        defects: list[QuestionDefect],
    ) -> str:
        """Suggest a better question given detected defects."""
        q = question

        if QuestionDefect.DERIVATIVE in defects:
            return f"What evidence INDEPENDENT of the answer would confirm or refute: {q}"

        if QuestionDefect.UNFALSIFIABLE in defects:
            return f"What specific, observable outcome would we expect if '{q}' were false?"

        if QuestionDefect.LOW_INFORMATION in defects:
            return f"What is the most surprising thing that could be true about: {q}"

        if QuestionDefect.WRONG_LEVEL in defects:
            return f"What is the root cause underlying: {q}"

        if QuestionDefect.SUBSTITUTED in defects:
            return f"What harder question is being avoided by asking: {q}"

        return ""
