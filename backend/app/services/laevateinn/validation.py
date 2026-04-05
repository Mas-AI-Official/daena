"""Stage 5: Validation Gauntlet.

Six independent tests that every non-trivial answer must survive:
    1. Feynman Test: can you explain it simply?
    2. Popper Test: 3 ways this could be wrong
    3. Buffett Inversion: map failure modes
    4. Hacker Test: 5 adversarial challenges
    5. CoVe Test: fact-check own claims (from Stage 4)
    6. Temporal Test: is this answer time-sensitive?

FAIL feeds back to Stage 4 (recursive). PASS proceeds to delivery.

Integrates with Daena's Quintessence for expert-level validation
when governance slider is STRICT or PARANOID.
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.services.laevateinn.types import (
    ComputeProfile,
    DepthResult,
    ValidationResult,
)

if TYPE_CHECKING:
    from app.services.llm_service import LLMService

logger = get_logger(__name__)

_FEYNMAN_PROMPT = (
    "Explain this answer in 2 simple sentences that a junior developer "
    "would understand. If you cannot explain it simply, the answer may "
    "be confused or incorrect.\n\n"
    "Question: {query}\nAnswer: {answer}\n\n"
    "Simple explanation:"
)

_POPPER_PROMPT = (
    "For this answer, identify exactly 3 ways it could be wrong or "
    "misleading. Be specific -- point to concrete claims that could "
    "fail under different conditions.\n\n"
    "Question: {query}\nAnswer: {answer}\n\n"
    "Three falsification scenarios:"
)

_BUFFETT_PROMPT = (
    "Using Buffett's inversion principle ('tell me where I'm going to die "
    "so I never go there'), identify the failure modes of this answer. "
    "What could go wrong if someone follows this advice?\n\n"
    "Question: {query}\nAnswer: {answer}\n\n"
    "Failure mode analysis:"
)

_HACKER_PROMPT = (
    "As a security-minded adversary, generate 5 challenges to this answer. "
    "Try to find edge cases, security vulnerabilities, logical flaws, "
    "or scenarios where the answer breaks down.\n\n"
    "Question: {query}\nAnswer: {answer}\n\n"
    "Adversarial challenges:"
)


class ValidationGauntlet:
    """Stage 5 of APEX: multi-test validation before delivery.

    Runs 6 independent validation tests. Each test can PASS or FAIL.
    If any critical test fails, the answer is sent back to Stage 4
    for recursive correction.

    Args:
        llm_service: Daena's LLM service for LLM-based validation tests.
    """

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self._llm = llm_service

    async def validate(
        self,
        query: str,
        answer: str,
        depth_result: DepthResult | None = None,
        compute: ComputeProfile | None = None,
        *,
        model_id: str = "",
    ) -> ValidationResult:
        """Run the full validation gauntlet.

        Args:
            query: The processed query.
            answer: The answer to validate.
            depth_result: Optional output from Stage 4 (for CoVe status).
            compute: Compute profile determining validation level.
            model_id: Model to use for LLM-based tests.

        Returns:
            ValidationResult with test outcomes and confidence.
        """
        start = time.perf_counter_ns()
        validation_level = "full_gauntlet"
        if compute:
            validation_level = compute.validation_level

        result = ValidationResult(passed=True, confidence=0.0)

        if validation_level == "none":
            result.confidence = 0.5  # No validation -- low confidence
            return result

        # ── Test 1: Feynman ─────────────────────────────────────
        result.feynman_explanation = self._feynman_test_heuristic(answer)
        if not result.feynman_explanation:
            result.failure_reasons.append("Feynman: answer too complex to simplify")

        if validation_level == "feynman_only":
            result.confidence = 0.6
            return result

        # ── Test 2: Popper (falsifiability) ─────────────────────
        result.popper_falsifications = self._popper_test_heuristic(answer)

        # ── Test 3: Buffett Inversion ───────────────────────────
        result.buffett_failure_modes = self._buffett_test_heuristic(answer)

        # ── Test 4: Hacker Test ─────────────────────────────────
        result.hacker_challenges = self._hacker_test_heuristic(query, answer)

        # ── Test 5: CoVe (from Stage 4) ────────────────────────
        if depth_result:
            result.cove_verified = len(depth_result.inconsistencies_found) == 0
            if not result.cove_verified:
                result.failure_reasons.append(
                    f"CoVe: {len(depth_result.inconsistencies_found)} inconsistencies remain"
                )
        else:
            result.cove_verified = False

        # ── Test 6: Temporal Validity ──────────────────────────
        result.temporal_valid = self._temporal_test(answer)
        if not result.temporal_valid:
            result.failure_reasons.append("Temporal: answer may be time-sensitive/outdated")

        # ── LLM-powered deep validation (for full_gauntlet_with_cove) ──
        if (
            validation_level == "full_gauntlet_with_cove"
            and self._llm
            and model_id
        ):
            await self._deep_validate(query, answer, result, model_id)

        # ── Calculate overall confidence ────────────────────────
        result.confidence = self._calculate_confidence(result)
        result.passed = result.confidence >= 0.6 and len(result.failure_reasons) <= 1

        elapsed_ms = int((time.perf_counter_ns() - start) / 1_000_000)

        logger.info(
            "validation_complete",
            passed=result.passed,
            confidence=result.confidence,
            failures=len(result.failure_reasons),
            elapsed_ms=elapsed_ms,
        )

        return result

    # ── Heuristic tests (no LLM needed) ────────────────────────

    def _feynman_test_heuristic(self, answer: str) -> str:
        """Feynman test: can the answer be explained simply?

        Heuristic: extract the first 2 sentences as the "simple explanation."
        If the answer is too short or too jargon-heavy, flag it.
        """
        sentences = re.split(r"(?<=[.!?])\s+", answer.strip())
        if not sentences:
            return ""

        # Take first 2 substantive sentences
        simple = " ".join(sentences[:2])

        # Check for excessive jargon density
        words = simple.split()
        long_words = [w for w in words if len(w) > 12]
        jargon_ratio = len(long_words) / max(len(words), 1)

        if jargon_ratio > 0.3:
            return ""  # Too jargon-heavy to explain simply

        return simple

    def _popper_test_heuristic(self, answer: str) -> list[str]:
        """Popper test: identify falsifiable claims.

        Heuristic: look for absolute claims (always, never, all, none)
        that are inherently falsifiable.
        """
        falsifications: list[str] = []
        answer_lower = answer.lower()

        absolute_patterns = [
            (r"\balways\b", "Claim uses 'always' -- edge cases may exist"),
            (r"\bnever\b", "Claim uses 'never' -- exceptions may exist"),
            (r"\ball\b", "Claim uses 'all' -- may not be universal"),
            (r"\bnone\b", "Claim uses 'none' -- counterexamples may exist"),
            (r"\bbest\b", "Claim implies a single 'best' -- context-dependent"),
            (r"\bonly\b", "Claim uses 'only' -- alternatives may exist"),
            (r"\bguarantee\b", "Claim implies guarantee -- conditions may fail"),
        ]

        for pattern, reason in absolute_patterns:
            if re.search(pattern, answer_lower):
                falsifications.append(reason)

        return falsifications[:3]  # Cap at 3

    def _buffett_test_heuristic(self, answer: str) -> list[str]:
        """Buffett inversion: map failure modes.

        Heuristic: identify risks, assumptions, and dependencies.
        """
        failure_modes: list[str] = []
        answer_lower = answer.lower()

        # Check for unstated dependencies
        if re.search(r"\binstall\b|\bsetup\b|\bconfigure\b", answer_lower):
            failure_modes.append("Depends on correct installation/configuration")

        if re.search(r"\bapi\b|\bendpoint\b|\bservice\b", answer_lower):
            failure_modes.append("Depends on external service availability")

        if re.search(r"\bversion\b|\bupdate\b|\bupgrade\b", answer_lower):
            failure_modes.append("May break with version changes")

        if re.search(r"\bassum\b", answer_lower):
            failure_modes.append("Contains explicit assumptions that may not hold")

        return failure_modes

    def _hacker_test_heuristic(self, query: str, answer: str) -> list[str]:
        """Hacker test: find attack vectors and edge cases.

        Heuristic: look for security-sensitive patterns.
        """
        challenges: list[str] = []
        combined = (query + " " + answer).lower()

        security_patterns = [
            (r"\binput\b.*\buser\b|\buser\b.*\binput\b", "User input handling -- injection risk"),
            (r"\bpassword\b|\bsecret\b|\btoken\b|\bkey\b", "Credential handling -- exposure risk"),
            (r"\bexec\b|\beval\b|\bsystem\b|\bshell\b", "Code execution -- command injection risk"),
            (r"\bsql\b|\bquery\b|\bdatabase\b", "Database operations -- SQL injection risk"),
            (r"\bfile\b.*\bpath\b|\bpath\b.*\bfile\b", "File path handling -- traversal risk"),
        ]

        for pattern, challenge in security_patterns:
            if re.search(pattern, combined):
                challenges.append(challenge)

        # Generic edge cases
        if len(answer) > 500:
            challenges.append("Long answer may have buried errors in details")

        return challenges[:5]

    def _temporal_test(self, answer: str) -> bool:
        """Temporal test: is the answer time-sensitive?

        Answers referencing specific dates, versions, or "current" state
        may become outdated.
        """
        temporal_patterns = [
            r"\b20\d{2}\b",  # Year references
            r"\bcurrently\b", r"\bas of\b", r"\brecently\b",
            r"\blatest\b", r"\bnew\b.*\bversion\b",
            r"\bdeprecated\b", r"\bwill be\b",
        ]

        for pattern in temporal_patterns:
            if re.search(pattern, answer, re.IGNORECASE):
                return False  # Time-sensitive content detected

        return True

    # ── LLM-powered deep validation ────────────────────────────

    async def _deep_validate(
        self,
        query: str,
        answer: str,
        result: ValidationResult,
        model_id: str,
    ) -> None:
        """Run LLM-powered validation tests (for brutal difficulty)."""
        if not self._llm:
            return

        from app.services.providers.base import GenerateRequest, LLMMessage
        import asyncio

        prompts = {
            "feynman": _FEYNMAN_PROMPT.format(query=query, answer=answer),
            "popper": _POPPER_PROMPT.format(query=query, answer=answer),
        }

        async def run_test(name: str, prompt: str) -> tuple[str, str]:
            messages = [LLMMessage(role="user", content=prompt)]
            request = GenerateRequest(
                messages=messages, model_id=model_id,
                temperature=0.3, max_tokens=512,
            )
            try:
                resp = await self._llm.generate_direct(request)
                return name, resp.content
            except Exception as e:
                logger.warning(f"deep_validate_{name}_failed", error=str(e))
                return name, ""

        tasks = [run_test(n, p) for n, p in prompts.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, Exception):
                continue
            name, content = r
            if name == "feynman" and content:
                result.feynman_explanation = content
            elif name == "popper" and content:
                result.popper_falsifications = [
                    line.strip() for line in content.split("\n")
                    if line.strip() and len(line.strip()) > 10
                ][:3]

    # ── Confidence calculation ──────────────────────────────────

    def _calculate_confidence(self, result: ValidationResult) -> float:
        """Calculate overall confidence from test results."""
        score = 0.5  # Base score

        # Feynman pass: +0.1
        if result.feynman_explanation:
            score += 0.1

        # CoVe verified: +0.15
        if result.cove_verified:
            score += 0.15

        # Temporal valid: +0.05
        if result.temporal_valid:
            score += 0.05

        # Penalties
        score -= len(result.failure_reasons) * 0.08
        score -= len(result.popper_falsifications) * 0.03
        score -= len(result.hacker_challenges) * 0.02

        return max(0.1, min(score, 1.0))
