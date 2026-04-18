"""Cognitive Forcing Engine -- the core intelligence amplification mechanism.

This module is the fundamental fix to the Laevateinn pipeline.
Instead of sending one bare LLM call ("answer this question"), it forces
the model through a structured cognitive process via SEPARATE LLM calls.

The model cannot skip any step because each step is a distinct API call
whose output feeds the next step. This is what makes the pipeline force
LLMs to "think through the pipeline, not with their mindset."

Three-stage Cognitive Forcing Protocol:
    1. DECOMPOSE: Break the problem into sub-problems and identify approach
    2. EXECUTE: Solve step-by-step following the decomposition exactly
    3. VERIFY: Check the answer by an alternate method, catch errors

Why this works:
    - Models default to pattern-matching (fast, often wrong on hard problems)
    - Decomposition FORCES problem analysis before solving
    - Step-by-step execution with decomposition prevents skipping logic
    - Independent verification catches errors the solver wouldn't see
    - Each stage is a SEPARATE LLM call -- the model cannot skip stages

Performance:
    - 3 LLM calls per model instead of 1
    - Each call is shorter and more focused (lower max_tokens per call)
    - Net token cost: ~1.5x a single call (decompose+verify are short)
    - Intelligence gain: proven on AIME 2025 I (see benchmarks)
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.services.llm_service import LLMService

logger = get_logger(__name__)

# ── Stage 1: DECOMPOSE ─────────────────────────────────────────────
# Forces the model to analyze before solving.
# The model MUST output sub-problems and approach -- it cannot jump
# to a final answer because the prompt explicitly forbids it.

_DECOMPOSE_SYSTEM = (
    "You are a problem decomposer. Your ONLY job is to break this problem "
    "into sub-problems and identify the mathematical/logical approach for each. "
    "Do NOT solve the problem. Do NOT compute any answers.\n\n"
    "Output format:\n"
    "SUB-PROBLEMS:\n"
    "1. [description] -- Approach: [method]\n"
    "2. [description] -- Approach: [method]\n"
    "...\n\n"
    "CONSTRAINTS:\n"
    "- [any constraints or edge cases to watch for]\n\n"
    "STRATEGY:\n"
    "- [overall approach: which sub-problems feed into which]\n"
    "- [what to verify at the end]"
)

# ── Stage 2: EXECUTE ───────────────────────────────────────────────
# Follows the decomposition exactly. Cannot skip steps because
# the decomposition is provided as structured input.

_EXECUTE_SYSTEM = (
    "You are solving a problem that has been decomposed into sub-problems. "
    "Follow the decomposition EXACTLY. Solve each sub-problem in order.\n\n"
    "Rules:\n"
    "1. Solve EACH sub-problem separately, showing all work\n"
    "2. After each sub-problem, state the intermediate result clearly\n"
    "3. When combining results, show the combination step explicitly\n"
    "4. At the end, state your FINAL ANSWER clearly\n"
    "5. For numeric answers, put the final number in \\boxed{}\n\n"
    "Do not skip steps. Do not combine sub-problems. Show everything."
)

# ── Stage 3: VERIFY ────────────────────────────────────────────────
# Independent verification. The verifier sees the question and the
# proposed solution, and checks it by a DIFFERENT method.

_VERIFY_SYSTEM = (
    "You are a verification agent. You are given a question and a "
    "proposed solution. Your job is to verify the solution is correct.\n\n"
    "Verification methods (use at least one):\n"
    "1. Plug the answer back into the original problem to check\n"
    "2. Solve using a completely different approach\n"
    "3. Check each step of the reasoning for errors\n"
    "4. Test boundary conditions or special cases\n\n"
    "Output format:\n"
    "VERIFICATION METHOD: [which method you used]\n"
    "CHECK: [your verification work]\n"
    "ERRORS FOUND: [none, or list specific errors]\n"
    "CORRECTED ANSWER: [the answer after correction, or same if no errors]\n"
    "FINAL ANSWER: \\boxed{[answer]}\n"
    "CONFIDENCE: [0.0-1.0 based on how well verification confirms the answer]"
)

# ── Compact mode for simpler problems ──────────────────────────────
# Combines decompose+execute into one call for STANDARD difficulty.
# Still forces structured thinking, but uses 2 calls instead of 3.

_STRUCTURED_SOLVE_SYSTEM = (
    "Solve this problem using structured reasoning.\n\n"
    "You MUST follow this format:\n\n"
    "STEP 1 - UNDERSTAND: What is the problem actually asking? "
    "What are the constraints?\n\n"
    "STEP 2 - APPROACH: What method will you use? Why this method?\n\n"
    "STEP 3 - SOLVE: Show all work step by step. After each sub-step, "
    "verify the intermediate result makes sense.\n\n"
    "STEP 4 - CHECK: Verify your answer by plugging it back in or "
    "using an alternate method.\n\n"
    "FINAL ANSWER: \\boxed{[your answer]}\n\n"
    "Do NOT skip any step. Show all work."
)


class CognitiveForcingEngine:
    """Forces LLMs through structured cognitive stages.

    Instead of one bare LLM call, this engine runs 2-3 focused calls
    that each build on the previous output. The model cannot skip
    decomposition, execution, or verification because each is a
    separate API invocation.

    Modes:
        FULL (3 calls): DECOMPOSE -> EXECUTE -> VERIFY
            Best for: hard math, multi-step reasoning, competition problems
            Cost: ~1.5x a single call

        COMPACT (2 calls): STRUCTURED_SOLVE -> VERIFY
            Best for: standard difficulty, clearer problems
            Cost: ~1.2x a single call

    Args:
        llm_service: Daena's LLM service for model calls.
    """

    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service

    async def solve(
        self,
        query: str,
        model_id: str,
        *,
        system_prompt: str = "",
        full_mode: bool = True,
        max_tokens_per_stage: int = 2048,
    ) -> CognitiveForcingResult:
        """Run the cognitive forcing pipeline on a single question.

        Args:
            query: The question to solve.
            model_id: Which model to use.
            system_prompt: Additional context (benchmark instructions etc).
            full_mode: True = 3 stages (DECOMPOSE+EXECUTE+VERIFY).
                      False = 2 stages (STRUCTURED_SOLVE+VERIFY).
            max_tokens_per_stage: Token budget per stage.

        Returns:
            CognitiveForcingResult with the final answer and all stage outputs.
        """
        start = time.perf_counter_ns()

        if full_mode:
            result = await self._full_mode(
                query, model_id, system_prompt, max_tokens_per_stage,
            )
        else:
            result = await self._compact_mode(
                query, model_id, system_prompt, max_tokens_per_stage,
            )

        result.total_latency_ms = int(
            (time.perf_counter_ns() - start) / 1_000_000
        )
        return result

    async def _full_mode(
        self,
        query: str,
        model_id: str,
        system_prompt: str,
        max_tokens: int,
    ) -> CognitiveForcingResult:
        """3-stage: DECOMPOSE -> EXECUTE -> VERIFY."""
        from app.services.providers.base import GenerateRequest, LLMMessage

        result = CognitiveForcingResult(mode="full")

        # ── Stage 1: DECOMPOSE ─────────────────────────────────
        logger.info("cognitive_forcing.decompose", model=model_id)
        decompose_messages = []
        if system_prompt:
            decompose_messages.append(
                LLMMessage(role="system", content=system_prompt)
            )
        decompose_messages.append(
            LLMMessage(role="system", content=_DECOMPOSE_SYSTEM)
        )
        decompose_messages.append(
            LLMMessage(role="user", content=query)
        )

        try:
            decompose_resp = await self._llm.generate_direct(GenerateRequest(
                messages=decompose_messages,
                model_id=model_id,
                temperature=0.3,  # Low temp for analytical decomposition
                max_tokens=max_tokens // 2,  # Decomposition is shorter
            ))
            result.decomposition = decompose_resp.content
            result.stages_completed.append("decompose")
        except Exception as exc:
            logger.warning("cognitive_forcing.decompose_failed", error=str(exc))
            # Fallback: skip decomposition, go to structured solve
            result.decomposition = ""

        # ── Stage 2: EXECUTE ───────────────────────────────────
        logger.info("cognitive_forcing.execute", model=model_id)
        execute_messages = []
        if system_prompt:
            execute_messages.append(
                LLMMessage(role="system", content=system_prompt)
            )
        execute_messages.append(
            LLMMessage(role="system", content=_EXECUTE_SYSTEM)
        )

        if result.decomposition:
            execute_messages.append(LLMMessage(
                role="user",
                content=(
                    f"Problem: {query}\n\n"
                    f"Decomposition (follow this exactly):\n"
                    f"{result.decomposition}\n\n"
                    f"Now solve each sub-problem in order. Show all work."
                ),
            ))
        else:
            # No decomposition available -- use structured solve prompt
            execute_messages.append(LLMMessage(
                role="user",
                content=(
                    f"Problem: {query}\n\n"
                    "Break this into clear steps and solve each one. "
                    "Show all work. Put final answer in \\boxed{{}}."
                ),
            ))

        try:
            execute_resp = await self._llm.generate_direct(GenerateRequest(
                messages=execute_messages,
                model_id=model_id,
                temperature=0.2,  # Low temp for precise execution
                max_tokens=max_tokens,
            ))
            result.execution = execute_resp.content
            result.stages_completed.append("execute")
        except Exception as exc:
            logger.warning("cognitive_forcing.execute_failed", error=str(exc))
            result.execution = ""
            return result  # Can't verify without execution

        # ── Stage 3: VERIFY ────────────────────────────────────
        logger.info("cognitive_forcing.verify", model=model_id)
        verify_messages = [
            LLMMessage(role="system", content=_VERIFY_SYSTEM),
            LLMMessage(
                role="user",
                content=(
                    f"Question: {query}\n\n"
                    f"Proposed solution:\n{result.execution}\n\n"
                    "Verify this solution. Use a different method if possible. "
                    "If you find errors, provide the corrected answer."
                ),
            ),
        ]

        try:
            verify_resp = await self._llm.generate_direct(GenerateRequest(
                messages=verify_messages,
                model_id=model_id,
                temperature=0.1,  # Very low temp for verification
                max_tokens=max_tokens,
            ))
            result.verification = verify_resp.content
            result.stages_completed.append("verify")
        except Exception as exc:
            logger.warning("cognitive_forcing.verify_failed", error=str(exc))
            result.verification = ""

        # Build final answer from verification if available, else execution
        result.final_answer = self._extract_final(
            result.verification or result.execution
        )
        result.full_response = self._build_full_response(result)

        return result

    async def _compact_mode(
        self,
        query: str,
        model_id: str,
        system_prompt: str,
        max_tokens: int,
    ) -> CognitiveForcingResult:
        """2-stage: STRUCTURED_SOLVE -> VERIFY."""
        from app.services.providers.base import GenerateRequest, LLMMessage

        result = CognitiveForcingResult(mode="compact")

        # ── Stage 1: Structured Solve ──────────────────────────
        logger.info("cognitive_forcing.structured_solve", model=model_id)
        solve_messages = []
        if system_prompt:
            solve_messages.append(
                LLMMessage(role="system", content=system_prompt)
            )
        solve_messages.append(
            LLMMessage(role="system", content=_STRUCTURED_SOLVE_SYSTEM)
        )
        solve_messages.append(
            LLMMessage(role="user", content=query)
        )

        try:
            solve_resp = await self._llm.generate_direct(GenerateRequest(
                messages=solve_messages,
                model_id=model_id,
                temperature=0.2,
                max_tokens=max_tokens,
            ))
            result.execution = solve_resp.content
            result.stages_completed.append("structured_solve")
        except Exception as exc:
            logger.warning("cognitive_forcing.solve_failed", error=str(exc))
            result.execution = ""
            return result

        # ── Stage 2: Verify ────────────────────────────────────
        logger.info("cognitive_forcing.verify", model=model_id)
        verify_messages = [
            LLMMessage(role="system", content=_VERIFY_SYSTEM),
            LLMMessage(
                role="user",
                content=(
                    f"Question: {query}\n\n"
                    f"Proposed solution:\n{result.execution}\n\n"
                    "Verify this solution. Use a different method if possible. "
                    "If you find errors, provide the corrected answer."
                ),
            ),
        ]

        try:
            verify_resp = await self._llm.generate_direct(GenerateRequest(
                messages=verify_messages,
                model_id=model_id,
                temperature=0.1,
                max_tokens=max_tokens,
            ))
            result.verification = verify_resp.content
            result.stages_completed.append("verify")
        except Exception as exc:
            logger.warning("cognitive_forcing.verify_failed", error=str(exc))
            result.verification = ""

        result.final_answer = self._extract_final(
            result.verification or result.execution
        )
        result.full_response = self._build_full_response(result)

        return result

    def _extract_final(self, text: str) -> str:
        """Extract the final answer from cognitive forcing output."""
        import re

        if not text:
            return ""

        # Priority 1: CORRECTED ANSWER from verification
        corrected = re.findall(
            r'CORRECTED ANSWER[:\s]+(.+?)(?:\n|$)', text, re.IGNORECASE,
        )
        if corrected:
            # Extract number from corrected answer
            nums = re.findall(r'-?\d+', corrected[-1])
            if nums:
                return nums[-1]

        # Priority 2: FINAL ANSWER from verification
        final = re.findall(
            r'FINAL[_ ]ANSWER[:\s]+(.+?)(?:\n|$)', text, re.IGNORECASE,
        )
        if final:
            nums = re.findall(r'-?\d+', final[-1])
            if nums:
                return nums[-1]

        # Priority 3: \boxed{} notation
        boxed = re.findall(r'\\boxed\{([^}]+)\}', text)
        if boxed:
            nums = re.findall(r'-?\d+', boxed[-1])
            if nums:
                return nums[-1]

        # Priority 4: Last number in text (fallback)
        all_nums = re.findall(r'-?\d+', text)
        if all_nums:
            return all_nums[-1]

        return text.strip()[-200:]  # Last 200 chars as final fallback

    def _build_full_response(self, result: CognitiveForcingResult) -> str:
        """Build the full response text from all stages."""
        parts = []
        if result.decomposition:
            parts.append(f"[Decomposition]\n{result.decomposition}")
        if result.execution:
            parts.append(f"[Solution]\n{result.execution}")
        if result.verification:
            parts.append(f"[Verification]\n{result.verification}")
        return "\n\n".join(parts)


class CognitiveForcingResult:
    """Result from the cognitive forcing pipeline."""

    def __init__(self, mode: str = "full") -> None:
        self.mode = mode
        self.decomposition: str = ""
        self.execution: str = ""
        self.verification: str = ""
        self.final_answer: str = ""
        self.full_response: str = ""
        self.stages_completed: list[str] = []
        self.total_latency_ms: int = 0
