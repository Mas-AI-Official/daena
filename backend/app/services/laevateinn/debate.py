"""Stage 3: Adversarial Model Debate (AMD).

Models don't just answer -- they debate. The surviving answer has been
stress-tested by multiple perspectives.

Why this beats single-model self-correction:
    - A model's blind spots are invisible to itself
    - AMD eliminates blind spots by making models attack each other
    - The winning answer survives multi-perspective scrutiny

Research basis: "LM vs LM" (Cohen et al., 2023) -- one LLM acts as
examiner, tests another's output. Proven to catch errors that
self-critique misses.

Integrates with Daena's CouncilEngine for multi-model synthesis,
extending it with adversarial cross-critique rounds.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.services.laevateinn.types import (
    ComputeProfile,
    DebateResult,
    DebateRound,
    Difficulty,
)

if TYPE_CHECKING:
    from app.services.llm_service import LLMService
    from app.services.providers.base import GenerateRequest, LLMMessage, LLMResponse

logger = get_logger(__name__)

# Debate prompts
_CRITIQUE_SYSTEM = (
    "You are a rigorous critic. You have been given another AI model's answer "
    "to a question. Your job is to find flaws, errors, omissions, and weak "
    "reasoning in that answer. Be specific and constructive. Point out exactly "
    "what is wrong and why. If the answer is actually correct and well-reasoned, "
    "say so -- do not invent flaws."
)

_DEFENSE_SYSTEM = (
    "You previously answered a question and received critiques from other AI "
    "models. Review the critiques carefully. If a critique identifies a genuine "
    "error, revise your answer. If a critique is wrong or misguided, defend "
    "your original answer with clear reasoning. Output your revised or "
    "defended answer."
)

_JUDGE_SYSTEM = (
    "You are an impartial judge evaluating answers from multiple AI models "
    "that debated a question. You have seen their original answers, critiques, "
    "and defenses. Select the best answer based on:\n"
    "1. Factual accuracy\n"
    "2. Logical reasoning quality\n"
    "3. Completeness of the answer\n"
    "4. Response to critiques (did they defend well or revise appropriately?)\n\n"
    "Output the winning model's name and the best final answer. Include a "
    "confidence score from 0.0 to 1.0."
)


class AdversarialModelDebate:
    """Stage 3 of APEX: multi-model adversarial debate.

    Protocol:
        Round 1: All models answer independently
        Round 2: Each model critiques the OTHER models' answers
        Round 3: Each model defends or revises based on critiques
        Round 4: Judge model selects winner with reasoning

    Args:
        llm_service: Daena's LLM service for making model calls.
    """

    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service

    async def debate(
        self,
        query: str,
        model_ids: list[str],
        compute: ComputeProfile,
        *,
        system_prompt: str = "",
    ) -> DebateResult:
        """Run a full adversarial debate.

        Args:
            query: The processed query from DCE.
            model_ids: List of model IDs to participate in debate.
            compute: Compute profile determining debate depth.
            system_prompt: Optional system prompt context.

        Returns:
            DebateResult with the winning answer and full trace.
        """
        start = time.perf_counter_ns()
        rounds: list[DebateRound] = []
        all_answers: dict[str, str] = {}

        max_rounds = compute.amd_rounds
        if max_rounds == 0 or len(model_ids) < 2:
            # No debate needed -- single model, single answer
            return await self._single_model_answer(query, model_ids[0], system_prompt)

        # Cap participants to available models
        participants = model_ids[:compute.num_models]

        # ── Round 1: Independent answers ────────────────────────
        logger.info("amd_round_1", models=participants)
        round1_tasks = [
            self._generate_answer(query, mid, system_prompt)
            for mid in participants
        ]
        round1_results = await asyncio.gather(*round1_tasks, return_exceptions=True)

        for mid, result in zip(participants, round1_results):
            if isinstance(result, Exception):
                logger.warning("amd_round1_failed", model=mid, error=str(result))
                continue
            content = result.content if hasattr(result, "content") else str(result)
            all_answers[mid] = content
            rounds.append(DebateRound(
                round_num=1, model_id=mid, content=content,
                role="answer", confidence=0.5,
            ))

        # Need at least 2 answers to debate
        if len(all_answers) < 2:
            # Fall back to best available
            if all_answers:
                mid, answer = next(iter(all_answers.items()))
                return DebateResult(
                    winner_model=mid, winner_answer=answer,
                    winner_reasoning="Only one model responded",
                    confidence=0.5, rounds=rounds, all_answers=all_answers,
                )
            return self._empty_result("No models responded", rounds)

        if max_rounds < 2:
            # Quick debate: just pick the answer (no critique phase)
            return self._select_by_length_heuristic(all_answers, rounds)

        # ── Round 2: Cross-critique ───────���─────────────────────
        logger.info("amd_round_2")
        critiques: dict[str, str] = {}
        critique_tasks = []
        for mid in all_answers:
            other_answers = {k: v for k, v in all_answers.items() if k != mid}
            critique_tasks.append(
                self._generate_critique(query, mid, other_answers)
            )

        critique_results = await asyncio.gather(*critique_tasks, return_exceptions=True)
        for mid, result in zip(all_answers.keys(), critique_results):
            if isinstance(result, Exception):
                logger.warning("amd_round2_failed", model=mid, error=str(result))
                continue
            content = result.content if hasattr(result, "content") else str(result)
            critiques[mid] = content
            rounds.append(DebateRound(
                round_num=2, model_id=mid, content=content,
                role="critique", confidence=0.0,
            ))

        if max_rounds < 3:
            return self._select_by_length_heuristic(all_answers, rounds)

        # ── Round 3: Defense or revision ────────────────────────
        logger.info("amd_round_3")
        revised: dict[str, str] = {}
        defense_tasks = []
        for mid in all_answers:
            attacks = [c for m, c in critiques.items() if m != mid]
            defense_tasks.append(
                self._generate_defense(query, mid, all_answers[mid], attacks)
            )

        defense_results = await asyncio.gather(*defense_tasks, return_exceptions=True)
        for mid, result in zip(all_answers.keys(), defense_results):
            if isinstance(result, Exception):
                logger.warning("amd_round3_failed", model=mid, error=str(result))
                revised[mid] = all_answers[mid]  # Keep original
                continue
            content = result.content if hasattr(result, "content") else str(result)
            revised[mid] = content
            rounds.append(DebateRound(
                round_num=3, model_id=mid, content=content,
                role="defense", confidence=0.0,
            ))

        # ── Round 4: Judgment ───────────────────────────────────
        logger.info("amd_round_4")
        judge_model = self._select_judge(participants)
        winner = await self._judge_debate(
            query, revised, critiques, judge_model
        )

        elapsed_ms = int((time.perf_counter_ns() - start) / 1_000_000)

        winner.rounds = rounds
        winner.all_answers = all_answers
        winner.total_latency_ms = elapsed_ms

        logger.info(
            "amd_complete",
            winner=winner.winner_model,
            confidence=winner.confidence,
            rounds=len(rounds),
            elapsed_ms=elapsed_ms,
        )

        return winner

    # ── Internal methods ─────────���──────────────────────────────

    async def _generate_answer(
        self, query: str, model_id: str, system_prompt: str,
    ) -> LLMResponse:
        """Generate an independent answer from a single model."""
        from app.services.providers.base import GenerateRequest, LLMMessage

        messages = []
        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))
        messages.append(LLMMessage(role="user", content=query))

        request = GenerateRequest(
            messages=messages,
            model_id=model_id,
            temperature=0.7,
            max_tokens=2048,
        )
        return await self._llm.generate_direct(request)

    async def _generate_critique(
        self, query: str, critic_model: str, other_answers: dict[str, str],
    ) -> LLMResponse:
        """Have a model critique other models' answers."""
        from app.services.providers.base import GenerateRequest, LLMMessage

        answers_text = "\n\n".join(
            f"--- {model} ---\n{answer}" for model, answer in other_answers.items()
        )

        messages = [
            LLMMessage(role="system", content=_CRITIQUE_SYSTEM),
            LLMMessage(
                role="user",
                content=(
                    f"Original question: {query}\n\n"
                    f"Answers to critique:\n{answers_text}"
                ),
            ),
        ]

        request = GenerateRequest(
            messages=messages,
            model_id=critic_model,
            temperature=0.5,
            max_tokens=1024,
        )
        return await self._llm.generate_direct(request)

    async def _generate_defense(
        self,
        query: str,
        model_id: str,
        original_answer: str,
        critiques: list[str],
    ) -> LLMResponse:
        """Have a model defend or revise its answer based on critiques."""
        from app.services.providers.base import GenerateRequest, LLMMessage

        critiques_text = "\n\n".join(
            f"Critique {i+1}:\n{c}" for i, c in enumerate(critiques)
        )

        messages = [
            LLMMessage(role="system", content=_DEFENSE_SYSTEM),
            LLMMessage(
                role="user",
                content=(
                    f"Question: {query}\n\n"
                    f"Your original answer:\n{original_answer}\n\n"
                    f"Critiques received:\n{critiques_text}\n\n"
                    "Defend or revise your answer."
                ),
            ),
        ]

        request = GenerateRequest(
            messages=messages,
            model_id=model_id,
            temperature=0.4,
            max_tokens=2048,
        )
        return await self._llm.generate_direct(request)

    async def _judge_debate(
        self,
        query: str,
        revised_answers: dict[str, str],
        critiques: dict[str, str],
        judge_model: str,
    ) -> DebateResult:
        """Have a judge model select the winning answer."""
        from app.services.providers.base import GenerateRequest, LLMMessage

        answers_text = "\n\n".join(
            f"=== {model} (final answer) ===\n{answer}"
            for model, answer in revised_answers.items()
        )

        messages = [
            LLMMessage(role="system", content=_JUDGE_SYSTEM),
            LLMMessage(
                role="user",
                content=(
                    f"Question: {query}\n\n"
                    f"Final answers after debate:\n{answers_text}\n\n"
                    "Select the winner. State the model name, the winning answer, "
                    "and your confidence (0.0-1.0)."
                ),
            ),
        ]

        request = GenerateRequest(
            messages=messages,
            model_id=judge_model,
            temperature=0.2,
            max_tokens=2048,
        )

        try:
            result = await self._llm.generate_direct(request)
            # Parse judge response -- extract winner model and confidence
            return self._parse_judgment(result.content, revised_answers)
        except Exception as e:
            logger.warning("amd_judge_failed", error=str(e))
            # Fallback: pick by length heuristic
            return self._select_by_length_heuristic(revised_answers, [])

    def _parse_judgment(
        self, judgment: str, answers: dict[str, str],
    ) -> DebateResult:
        """Parse the judge's response to extract winner."""
        import re

        # Try to find model name in judgment
        for model_id in answers:
            if model_id.lower() in judgment.lower():
                # Try to extract confidence
                conf_match = re.search(r"confidence[:\s]*([0-9.]+)", judgment, re.IGNORECASE)
                confidence = float(conf_match.group(1)) if conf_match else 0.7

                return DebateResult(
                    winner_model=model_id,
                    winner_answer=answers[model_id],
                    winner_reasoning=judgment,
                    confidence=min(confidence, 1.0),
                )

        # Could not parse -- use first answer
        first_model = next(iter(answers))
        return DebateResult(
            winner_model=first_model,
            winner_answer=answers[first_model],
            winner_reasoning=f"Judge output unparseable, defaulting to first model. Judge said: {judgment[:200]}",
            confidence=0.5,
        )

    async def _single_model_answer(
        self, query: str, model_id: str, system_prompt: str,
    ) -> DebateResult:
        """Shortcut when only one model is available."""
        result = await self._generate_answer(query, model_id, system_prompt)
        return DebateResult(
            winner_model=model_id,
            winner_answer=result.content,
            winner_reasoning="Single model -- no debate needed",
            confidence=0.6,
            all_answers={model_id: result.content},
        )

    def _select_judge(self, model_ids: list[str]) -> str:
        """Select the best available model as judge.

        Preference: reasoning models > large models > any model.
        """
        # Prefer reasoning-focused models as judges
        judge_preferences = ["deepseek-r1", "claude", "gpt-4", "qwen"]
        for pref in judge_preferences:
            for mid in model_ids:
                if pref in mid.lower():
                    return mid
        return model_ids[0]

    def _select_by_length_heuristic(
        self,
        answers: dict[str, str],
        rounds: list[DebateRound],
    ) -> DebateResult:
        """Heuristic winner selection: prefer longer, more detailed answers."""
        best_model = max(answers, key=lambda m: len(answers[m]))
        return DebateResult(
            winner_model=best_model,
            winner_answer=answers[best_model],
            winner_reasoning="Selected by detail heuristic (most comprehensive answer)",
            confidence=0.5,
            rounds=rounds,
            all_answers=answers,
        )

    def _empty_result(self, reason: str, rounds: list[DebateRound]) -> DebateResult:
        """Return an empty result when debate fails entirely."""
        return DebateResult(
            winner_model="none",
            winner_answer="",
            winner_reasoning=reason,
            confidence=0.0,
            rounds=rounds,
        )
