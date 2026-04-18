"""Self-Critique Loop: generate -> critique -> refine -> output.

Implements recursive self-improvement of LLM responses. After the initial
response is generated, the same (or another) model critiques it, identifies
weaknesses, and produces a refined version.

Activation conditions (all must be true):
1. GovernanceMode is UNLEASHED or BALANCED
2. Query complexity is COMPLEX or MULTI_STEP
3. Response length > 200 characters
4. Max 1 refinement round (bounded latency)

This is Daena's equivalent of Constitutional AI's self-correction loop,
but optimized for intelligence rather than safety.

Usage::

    from app.services.self_critique import SelfCritiqueLoop

    loop = SelfCritiqueLoop(llm_service)
    refined = await loop.refine(
        original_response="The initial LLM response...",
        original_query="What the user asked...",
        model_id="anthropic/claude-sonnet-4-6",
    )
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.services.llm_service import LLMService

logger = get_logger(__name__)

_CRITIQUE_SYSTEM_PROMPT = """\
You are a sharp, unforgiving internal critic. You have been given a response \
to a user query. Your job is to find the WEAKNESSES:

1. What is factually wrong or unsupported?
2. What important aspect did the response miss entirely?
3. What assumption is the response making that it should question?
4. Where is the reasoning shallow or hand-wavy?
5. What would make this response genuinely excellent instead of just adequate?

Be specific. Point to exact weaknesses. Do not praise -- only critique.
If the response is genuinely excellent, say "NO SIGNIFICANT WEAKNESSES" \
and nothing else."""

_REFINE_SYSTEM_PROMPT = """\
You are refining a response based on a critical review. You have:
- The original user query
- The initial response
- A critique identifying specific weaknesses

Your task: produce an improved response that addresses the critique \
while preserving the strengths of the original. Do not mention the \
critique process. Write as if this is your first and only answer.

The refined response should be noticeably better -- sharper, more \
accurate, more complete. Not longer for the sake of length."""


class SelfCritiqueLoop:
    """Recursive self-improvement of LLM responses."""

    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service

    async def refine(
        self,
        original_response: str,
        original_query: str,
        model_id: str,
        max_rounds: int = 1,
    ) -> str | None:
        """Critique and refine a response.

        Args:
            original_response: The initial LLM response to improve.
            original_query: The user's original query.
            model_id: The model to use for critique and refinement.
            max_rounds: Maximum refinement iterations (default 1).

        Returns:
            Refined response string, or None if critique found no issues.
        """
        start = time.monotonic()
        current = original_response

        for round_num in range(max_rounds):
            # Step 1: Critique
            critique = await self._critique(current, original_query, model_id)

            if not critique or "NO SIGNIFICANT WEAKNESSES" in critique.upper():
                logger.info(
                    "self_critique.no_weaknesses",
                    round=round_num + 1,
                    time_ms=int((time.monotonic() - start) * 1000),
                )
                return None  # Original was good enough

            # Step 2: Refine
            refined = await self._refine(
                current, critique, original_query, model_id,
            )

            if not refined or len(refined) < len(current) * 0.3:
                # Refinement failed or produced something too short
                logger.warning(
                    "self_critique.refinement_failed",
                    round=round_num + 1,
                )
                return None

            current = refined
            logger.info(
                "self_critique.refined",
                round=round_num + 1,
                original_len=len(original_response),
                refined_len=len(current),
                time_ms=int((time.monotonic() - start) * 1000),
            )

        return current

    async def _critique(
        self, response: str, query: str, model_id: str,
    ) -> str | None:
        """Generate a critique of the response."""
        from app.services.providers.base import GenerateRequest, LLMMessage

        request = GenerateRequest(
            messages=[
                LLMMessage(role="system", content=_CRITIQUE_SYSTEM_PROMPT),
                LLMMessage(
                    role="user",
                    content=(
                        f"Original query: {query}\n\n"
                        f"---\n\nResponse to critique:\n{response}"
                    ),
                ),
            ],
            model=model_id,
            max_tokens=500,
            temperature=0.3,
        )

        try:
            result = await self._llm.generate(request)
            return result.content if result else None
        except Exception:
            logger.warning("self_critique.critique_failed", exc_info=True)
            return None

    async def _refine(
        self,
        response: str,
        critique: str,
        query: str,
        model_id: str,
    ) -> str | None:
        """Produce a refined response addressing the critique."""
        from app.services.providers.base import GenerateRequest, LLMMessage

        request = GenerateRequest(
            messages=[
                LLMMessage(role="system", content=_REFINE_SYSTEM_PROMPT),
                LLMMessage(
                    role="user",
                    content=(
                        f"Original query: {query}\n\n"
                        f"---\n\nInitial response:\n{response}\n\n"
                        f"---\n\nCritique:\n{critique}\n\n"
                        f"---\n\nProduce an improved response."
                    ),
                ),
            ],
            model=model_id,
            max_tokens=2000,
            temperature=0.4,
        )

        try:
            result = await self._llm.generate(request)
            return result.content if result else None
        except Exception:
            logger.warning("self_critique.refine_failed", exc_info=True)
            return None
