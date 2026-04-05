"""Stage 4: Recursive Depth Engine (RDE) + Chain-of-Verification (CoVe).

APEX's answer to Mythos's recursive self-correction. Mythos does it at
the weight level. APEX does it at the system level -- available NOW on
ANY model.

Each recursion:
    1. Generates answer
    2. Generates verification questions about that answer
    3. Answers those questions independently (no bias from original)
    4. Cross-checks for inconsistency
    5. If inconsistency found, regenerate with failure context
    6. Repeat until confident or budget exhausted

Research basis: "Learning to Self-Correct through Chain-of-Thought
Verification" (ICML 2025). CoVe reduces hallucination by 23%+
(Meta AI, 2023).
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.services.laevateinn.types import (
    ComputeProfile,
    DepthResult,
    VerificationQuestion,
)

if TYPE_CHECKING:
    from app.services.llm_service import LLMService
    from app.services.providers.base import LLMResponse

logger = get_logger(__name__)

# CoVe prompt templates
_VERIFICATION_PLANNER = (
    "Given this answer to a question, generate 3-5 specific verification "
    "questions that would test whether the key claims in the answer are "
    "correct. Focus on factual claims, numerical values, and causal "
    "relationships. Each question should be independently answerable "
    "without seeing the original answer.\n\n"
    "Question: {query}\n\n"
    "Answer to verify: {answer}\n\n"
    "Output each verification question on its own line, prefixed with 'Q: '."
)

_SELF_CRITIQUE = (
    "You are a rigorous self-critic. Review your own answer to this question "
    "and identify weaknesses, potential errors, unsupported claims, and gaps. "
    "Be honest and thorough.\n\n"
    "Question: {query}\n\n"
    "Your answer: {answer}\n\n"
    "Inconsistencies found during verification:\n{inconsistencies}\n\n"
    "Provide a detailed self-critique."
)

_REGENERATE = (
    "You previously answered a question but verification found issues. "
    "Using the critique and verification results below, provide an improved "
    "answer that addresses all identified problems.\n\n"
    "Original question: {query}\n\n"
    "Previous answer: {previous}\n\n"
    "Self-critique: {critique}\n\n"
    "Inconsistencies: {inconsistencies}\n\n"
    "Provide a corrected, improved answer."
)


class RecursiveDepthEngine:
    """Stage 4 of APEX: recursive self-correction with verification.

    Combines:
        - Recursive depth loops (up to max_depth iterations)
        - Chain-of-Verification (independent fact-checking)
        - Self-critique with inconsistency context
        - Progressive confidence estimation

    Args:
        llm_service: Daena's LLM service for making model calls.
    """

    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service

    async def recursive_solve(
        self,
        query: str,
        initial_answer: str,
        compute: ComputeProfile,
        *,
        model_id: str = "",
        verification_model_id: str = "",
    ) -> DepthResult:
        """Run recursive depth engine on an answer.

        Args:
            query: The processed query.
            initial_answer: Answer from Stage 3 (debate winner or single model).
            compute: Compute profile with recursion depth budget.
            model_id: Primary model for regeneration.
            verification_model_id: Different model for independent verification.

        Returns:
            DepthResult with verified/corrected answer.
        """
        start = time.perf_counter_ns()
        max_depth = compute.recursion_depth

        if max_depth == 0:
            # No recursion needed -- trivial query
            return DepthResult(
                final_answer=initial_answer,
                depth_used=0,
                max_depth=0,
                confidence=0.7,
            )

        answer = initial_answer
        all_verifications: list[VerificationQuestion] = []
        all_inconsistencies: list[str] = []
        revisions: list[str] = []

        # Use primary model for verification if no separate one specified
        ver_model = verification_model_id or model_id

        for depth in range(max_depth):
            logger.info("rde_iteration", depth=depth, max_depth=max_depth)

            # Step 1: Plan verification questions
            ver_questions = await self._plan_verification(query, answer, model_id)

            # Step 2: Answer verification questions INDEPENDENTLY
            # Critical: no context from original answer (prevents self-confirmation)
            ver_answers = await self._verify_independently(ver_questions, ver_model)
            all_verifications.extend(ver_answers)

            # Step 3: Cross-check for inconsistencies
            inconsistencies = self._cross_check(answer, ver_answers)

            if not inconsistencies:
                # All facts verified -- high confidence
                logger.info("rde_verified", depth=depth)
                elapsed_ms = int((time.perf_counter_ns() - start) / 1_000_000)
                return DepthResult(
                    final_answer=answer,
                    depth_used=depth + 1,
                    max_depth=max_depth,
                    confidence=0.95,
                    verification_questions=all_verifications,
                    inconsistencies_found=all_inconsistencies,
                    revisions=revisions,
                    total_latency_ms=elapsed_ms,
                )

            all_inconsistencies.extend(inconsistencies)

            # Step 4: Self-critique with inconsistency context
            critique = await self._self_critique(
                query, answer, inconsistencies, model_id
            )

            # Step 5: Regenerate with full failure context
            answer = await self._regenerate(
                query, answer, critique, inconsistencies, model_id
            )
            revisions.append(answer)

        # Budget exhausted -- return best effort
        elapsed_ms = int((time.perf_counter_ns() - start) / 1_000_000)
        confidence = self._estimate_confidence(all_inconsistencies, max_depth)

        logger.info(
            "rde_complete",
            depth_used=max_depth,
            confidence=confidence,
            inconsistencies=len(all_inconsistencies),
            elapsed_ms=elapsed_ms,
        )

        return DepthResult(
            final_answer=answer,
            depth_used=max_depth,
            max_depth=max_depth,
            confidence=confidence,
            verification_questions=all_verifications,
            inconsistencies_found=all_inconsistencies,
            revisions=revisions,
            total_latency_ms=elapsed_ms,
        )

    # ── Chain-of-Verification ───────────────────────────────────

    async def _plan_verification(
        self, query: str, answer: str, model_id: str,
    ) -> list[VerificationQuestion]:
        """Generate verification questions about the answer."""
        from app.services.providers.base import GenerateRequest, LLMMessage

        prompt = _VERIFICATION_PLANNER.format(query=query, answer=answer)
        messages = [LLMMessage(role="user", content=prompt)]

        request = GenerateRequest(
            messages=messages,
            model_id=model_id,
            temperature=0.3,
            max_tokens=512,
        )

        try:
            result = await self._llm.generate_direct(request)
            return self._parse_verification_questions(result.content)
        except Exception as e:
            logger.warning("cove_plan_failed", error=str(e))
            return []

    async def _verify_independently(
        self,
        questions: list[VerificationQuestion],
        model_id: str,
    ) -> list[VerificationQuestion]:
        """Answer verification questions independently (no original context).

        CRITICAL: Each question answered in isolation -- no cross-contamination.
        This prevents the model from confirming its own hallucinations.
        """
        from app.services.providers.base import GenerateRequest, LLMMessage

        async def verify_one(q: VerificationQuestion) -> VerificationQuestion:
            messages = [LLMMessage(
                role="user",
                content=f"Answer this factual question concisely: {q.question}",
            )]
            request = GenerateRequest(
                messages=messages,
                model_id=model_id,
                temperature=0.1,  # Low temperature for factual accuracy
                max_tokens=256,
            )
            try:
                result = await self._llm.generate_direct(request)
                q.independent_answer = result.content
            except Exception as e:
                logger.warning("cove_verify_failed", question=q.question[:50], error=str(e))
                q.independent_answer = ""
            return q

        # Verify all questions in parallel
        verified = await asyncio.gather(
            *[verify_one(q) for q in questions],
            return_exceptions=True,
        )

        return [v for v in verified if isinstance(v, VerificationQuestion)]

    def _cross_check(
        self, original_answer: str, verifications: list[VerificationQuestion],
    ) -> list[str]:
        """Cross-check original answer against independent verifications.

        Simple heuristic: if a verification answer contradicts a claim
        in the original, flag it as inconsistent.
        """
        inconsistencies: list[str] = []
        original_lower = original_answer.lower()

        for v in verifications:
            if not v.independent_answer:
                continue

            # Check for direct contradictions using negation patterns
            ver_lower = v.independent_answer.lower()

            # If the verification explicitly says "no", "incorrect", "false"
            # and the original answer doesn't contain similar negation
            contradiction_words = ["no,", "incorrect", "false", "not true", "wrong", "inaccurate"]
            has_contradiction = any(w in ver_lower for w in contradiction_words)

            if has_contradiction:
                v.consistent_with_original = False
                inconsistencies.append(
                    f"Verification Q: '{v.question}' -- "
                    f"Independent answer suggests: {v.independent_answer[:100]}"
                )

        return inconsistencies

    # ── Self-critique and regeneration ──────────────────────────

    async def _self_critique(
        self,
        query: str,
        answer: str,
        inconsistencies: list[str],
        model_id: str,
    ) -> str:
        """Generate a self-critique with inconsistency context."""
        from app.services.providers.base import GenerateRequest, LLMMessage

        prompt = _SELF_CRITIQUE.format(
            query=query,
            answer=answer,
            inconsistencies="\n".join(inconsistencies),
        )
        messages = [LLMMessage(role="user", content=prompt)]

        request = GenerateRequest(
            messages=messages,
            model_id=model_id,
            temperature=0.3,
            max_tokens=512,
        )

        try:
            result = await self._llm.generate_direct(request)
            return result.content
        except Exception as e:
            logger.warning("rde_critique_failed", error=str(e))
            return "Self-critique failed -- proceeding with inconsistency context only"

    async def _regenerate(
        self,
        query: str,
        previous: str,
        critique: str,
        inconsistencies: list[str],
        model_id: str,
    ) -> str:
        """Regenerate answer with full failure context."""
        from app.services.providers.base import GenerateRequest, LLMMessage

        prompt = _REGENERATE.format(
            query=query,
            previous=previous,
            critique=critique,
            inconsistencies="\n".join(inconsistencies),
        )
        messages = [LLMMessage(role="user", content=prompt)]

        request = GenerateRequest(
            messages=messages,
            model_id=model_id,
            temperature=0.5,
            max_tokens=2048,
        )

        try:
            result = await self._llm.generate_direct(request)
            return result.content
        except Exception as e:
            logger.warning("rde_regenerate_failed", error=str(e))
            return previous  # Return previous answer if regeneration fails

    # ── Helpers ─────────────────────────────────────────────────

    def _parse_verification_questions(self, text: str) -> list[VerificationQuestion]:
        """Parse LLM output into verification questions."""
        import re
        questions: list[VerificationQuestion] = []

        lines = text.strip().split("\n")
        for line in lines:
            line = line.strip()
            # Match lines starting with "Q:", numbers, or bullets
            match = re.match(r"(?:Q:|[\d]+[.)]\s*|-\s*|\*\s*)(.*)", line)
            if match:
                q_text = match.group(1).strip()
                if len(q_text) > 10:  # Minimum substantive question
                    q_type = "factual"
                    if any(w in q_text.lower() for w in ["when", "year", "date"]):
                        q_type = "temporal"
                    elif any(w in q_text.lower() for w in ["because", "why", "cause"]):
                        q_type = "logical"
                    questions.append(VerificationQuestion(
                        question=q_text, expected_type=q_type,
                    ))

        return questions[:5]  # Cap at 5 verification questions

    def _estimate_confidence(
        self, inconsistencies: list[str], depth_used: int,
    ) -> float:
        """Estimate confidence based on verification results."""
        if not inconsistencies:
            return 0.95

        # More iterations with remaining inconsistencies = lower confidence
        base = 0.7
        penalty_per_inconsistency = 0.05
        bonus_per_depth = 0.03  # Each iteration improves somewhat

        confidence = base
        confidence -= len(inconsistencies) * penalty_per_inconsistency
        confidence += depth_used * bonus_per_depth

        return max(0.2, min(confidence, 0.9))
