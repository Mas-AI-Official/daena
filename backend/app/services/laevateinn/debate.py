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
    DisagreementPoint,
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

_DISAGREEMENT_IDENTIFY = (
    "Compare these answers to the same question and identify SPECIFIC points "
    "where they DISAGREE. Focus on factual claims, recommendations, or "
    "reasoning that conflicts between the answers.\n\n"
    "Question: {query}\n\n{answers_text}\n\n"
    "For each disagreement, output:\n"
    "TOPIC: [what they disagree about]\n"
    "MODEL_A ({model_a}): [their position]\n"
    "MODEL_B ({model_b}): [their position]\n\n"
    "List only genuine disagreements, not differences in phrasing."
)

# ── Council Synthesis Prompts ────────────────────────────────────
# These implement the human council model: find blind spots, understand
# WHY models disagree, synthesize covering ALL blind spots.

_COUNCIL_BLIND_SPOT = (
    "You are analyzing a disagreement between AI models on a math/reasoning problem.\n\n"
    "Question: {query}\n\n"
    "Model answers (with reasoning):\n{answers_text}\n\n"
    "The models produced these final answers: {answer_summary}\n\n"
    "Your job is NOT to pick a winner. Your job is to:\n"
    "1. Find the EXACT STEP where each model's reasoning diverges\n"
    "2. For each divergence: which model's logic is SOUND and which has a FLAW?\n"
    "3. Did any model catch an edge case or constraint that others MISSED?\n"
    "4. Did any model use a VERIFICATION method (plugging back in, alternate approach)?\n\n"
    "Output format:\n"
    "DIVERGENCE_POINT: [where the reasoning chains split]\n"
    "MODEL_A_LOGIC: [sound/flawed] -- [explain why]\n"
    "MODEL_B_LOGIC: [sound/flawed] -- [explain why]\n"
    "BLIND_SPOT: [what one model saw that others missed]\n"
    "VERIFICATION: [which model verified their answer, how]\n"
    "BEST_REASONING_PATH: [which chain of logic is most reliable and why]\n"
    "FINAL_ANSWER: [the answer supported by the strongest reasoning]\n"
    "CONFIDENCE: [0.0-1.0 based on reasoning quality, not popularity]"
)

_DISAGREEMENT_ARGUE = (
    "You previously answered a question. Another model DISAGREES with you "
    "on a specific point. Argue your case with EVIDENCE and clear reasoning. "
    "If the other model is right, admit it and revise.\n\n"
    "Question: {query}\n\n"
    "The disagreement:\n"
    "Topic: {topic}\n"
    "Your position: {your_position}\n"
    "Their position: {their_position}\n\n"
    "Argue your case with evidence, or concede if they are correct:"
)


class AdversarialModelDebate:
    """Stage 3 of APEX: multi-model adversarial debate.

    Protocol:
        Round 1: All models answer independently (with cognitive forcing)
        Round 2: Each model critiques the OTHER models' answers
        Round 3: Each model defends or revises based on critiques
        Round 4: Judge model selects winner with reasoning

    Cognitive Forcing (v2):
        When enabled, Round 1 uses CognitiveForcingEngine instead of bare
        LLM calls. Each model is forced through DECOMPOSE -> EXECUTE -> VERIFY
        stages, producing higher-quality independent answers before debate.

    Args:
        llm_service: Daena's LLM service for making model calls.
    """

    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service
        self._cognitive = None  # Lazy-init to avoid circular imports

    async def debate(
        self,
        query: str,
        model_ids: list[str],
        compute: ComputeProfile,
        *,
        system_prompt: str = "",
        use_cognitive_forcing: bool = False,
    ) -> DebateResult:
        """Run a full adversarial debate.

        Args:
            query: The processed query from DCE.
            model_ids: List of model IDs to participate in debate.
            compute: Compute profile determining debate depth.
            system_prompt: Optional system prompt context.
            use_cognitive_forcing: If True, Round 1 uses cognitive forcing
                instead of bare LLM calls. Each model goes through
                DECOMPOSE -> EXECUTE -> VERIFY before debate begins.

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

        # ── Round 1: Independent answers (with optional cognitive forcing) ──
        if use_cognitive_forcing:
            logger.info("amd_round_1_cognitive_forced", models=participants)
            round1_tasks = [
                self._cognitive_forced_answer(query, mid, system_prompt)
                for mid in participants
            ]
        else:
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
                role="cognitive_forced_answer" if use_cognitive_forcing else "answer",
                confidence=0.5,
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

        # ── Round 1.5: Identify disagreements (NEW) ────────────
        logger.info("amd_round_1_5_disagreements")
        disagreements = await self._identify_disagreements(
            query, all_answers, participants[0]
        )

        # ── Round 2: Disagreement-focused critique ─────────────
        logger.info("amd_round_2", disagreements=len(disagreements))
        critiques: dict[str, str] = {}

        if disagreements:
            # NEW: focused debate on specific disagreement points
            critique_tasks = []
            for mid in all_answers:
                critique_tasks.append(
                    self._argue_disagreements(
                        query, mid, all_answers[mid], disagreements
                    )
                )
            critique_results = await asyncio.gather(
                *critique_tasks, return_exceptions=True
            )
            for mid, result in zip(all_answers.keys(), critique_results):
                if isinstance(result, Exception):
                    logger.warning("amd_round2_failed", model=mid, error=str(result))
                    continue
                content = result.content if hasattr(result, "content") else str(result)
                critiques[mid] = content
                rounds.append(DebateRound(
                    round_num=2, model_id=mid, content=content,
                    role="disagreement_argument", confidence=0.0,
                ))
        else:
            # Fallback: broad critique (original behavior)
            critique_tasks = []
            for mid in all_answers:
                other_answers = {k: v for k, v in all_answers.items() if k != mid}
                critique_tasks.append(
                    self._generate_critique(query, mid, other_answers)
                )
            critique_results = await asyncio.gather(
                *critique_tasks, return_exceptions=True
            )
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
        winner.disagreement_points = disagreements

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

    async def _cognitive_forced_answer(
        self, query: str, model_id: str, system_prompt: str,
    ) -> LLMResponse:
        """Generate an answer using cognitive forcing (3-stage structured solve).

        Instead of one bare LLM call, this runs the model through:
        1. DECOMPOSE: break problem into sub-problems
        2. EXECUTE: solve step-by-step following decomposition
        3. VERIFY: check answer by alternate method

        Returns an LLMResponse-compatible object with the full response.
        """
        from app.services.laevateinn.cognitive_forcing import CognitiveForcingEngine

        if self._cognitive is None:
            self._cognitive = CognitiveForcingEngine(self._llm)

        result = await self._cognitive.solve(
            query, model_id,
            system_prompt=system_prompt,
            full_mode=True,
        )

        # Return a simple object with .content attribute
        # (debate code only accesses result.content)
        class _CognitiveResponse:
            def __init__(self, content: str) -> None:
                self.content = content
        return _CognitiveResponse(result.full_response)

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

    # ── Council Synthesis (human council model) ────────────────
    # Unlike judge-picks-winner, this finds blind spots and synthesizes.

    async def council_synthesis(
        self,
        query: str,
        model_ids: list[str],
        *,
        system_prompt: str = "",
        analyst_model: str | None = None,
        use_cognitive_forcing: bool = False,
    ) -> DebateResult:
        """Human council model: independent reasoning + blind spot synthesis.

        How it works (like a real human council):
        1. Each model solves independently (no groupthink)
        2. Extract concrete answers from each
        3. If all agree -> high confidence, done
        4. If they disagree -> analyze WHERE reasoning diverges
        5. Find who caught blind spots others missed
        6. Final answer = strongest reasoning chain, not popular vote

        The analyst (who examines the reasoning) is DIFFERENT from the
        debaters. This prevents the dictator problem -- no model judges
        its own answer.

        Args:
            query: The problem to solve.
            model_ids: Models to participate (first = primary, rest = council).
            system_prompt: Additional context.
            analyst_model: Model for blind spot analysis. If None, uses the
                LEAST likely to be biased (not the primary model).
        """
        import re
        start = time.perf_counter_ns()
        rounds: list[DebateRound] = []

        if len(model_ids) < 2:
            return await self._single_model_answer(
                query, model_ids[0], system_prompt,
            )

        # ── Step 1: Independent reasoning (parallel, with optional cognitive forcing)
        if use_cognitive_forcing:
            logger.info("council.step1_cognitive_forced", models=model_ids)
            answer_tasks = [
                self._cognitive_forced_answer(query, mid, system_prompt)
                for mid in model_ids
            ]
        else:
            logger.info("council.step1_independent", models=model_ids)
            answer_tasks = [
                self._generate_answer(query, mid, system_prompt)
                for mid in model_ids
            ]
        results = await asyncio.gather(*answer_tasks, return_exceptions=True)

        all_answers: dict[str, str] = {}
        for mid, result in zip(model_ids, results):
            if isinstance(result, Exception):
                logger.warning("council.model_failed", model=mid, error=str(result))
                continue
            content = result.content if hasattr(result, "content") else str(result)
            all_answers[mid] = content
            rounds.append(DebateRound(
                round_num=1, model_id=mid, content=content,
                role="independent_answer", confidence=0.5,
            ))

        if len(all_answers) < 2:
            if all_answers:
                mid, answer = next(iter(all_answers.items()))
                return DebateResult(
                    winner_model=mid, winner_answer=answer,
                    winner_reasoning="Only one model responded",
                    confidence=0.5, rounds=rounds, all_answers=all_answers,
                )
            return self._empty_result("No models responded", rounds)

        # ── Step 2: Extract concrete answers ──────────────────
        def _extract_numeric(text: str) -> str | None:
            """Extract final numeric answer with cognitive forcing awareness.

            Priority order (highest to lowest):
            1. CORRECTED ANSWER from verification stage (cognitive forcing)
            2. FINAL ANSWER from verification stage (cognitive forcing)
            3. \\boxed{} notation (standard math output)
            4. "answer/Answer/ANSWER: N" pattern
            5. Last number in text (fallback)
            """
            # Priority 1: CORRECTED ANSWER from cognitive forcing verify
            corrected = re.findall(
                r'CORRECTED ANSWER[:\s]+.*?(-?\d+)', text, re.IGNORECASE,
            )
            if corrected:
                return corrected[-1]

            # Priority 2: FINAL ANSWER (from verify stage or analyst)
            final = re.findall(
                r'FINAL[_ ]ANSWER[:\s]+.*?(-?\d+)', text, re.IGNORECASE,
            )
            if final:
                return final[-1]

            # Priority 3: \boxed{} (standard math notation)
            boxed = re.findall(r'\\boxed\{([^}]+)\}', text)
            if boxed:
                nums = re.findall(r'-?\d+', boxed[-1])
                if nums:
                    return nums[-1]

            # Priority 4: "answer: N" pattern
            answer_pat = re.findall(
                r'(?:answer|Answer|ANSWER|result|Result)[:\s]+\*?\*?(-?\d+)',
                text,
            )
            if answer_pat:
                return answer_pat[-1]

            # Priority 5: Last number in [Verification] section if present,
            # otherwise last number in full text
            verify_section = re.split(
                r'\[Verification\]', text, flags=re.IGNORECASE,
            )
            if len(verify_section) > 1:
                verify_nums = re.findall(r'-?\d+', verify_section[-1])
                if verify_nums:
                    return verify_nums[-1]

            all_nums = re.findall(r'-?\d+', text)
            if all_nums:
                return all_nums[-1]
            return None

        extracted: dict[str, str | None] = {}
        for mid, text in all_answers.items():
            extracted[mid] = _extract_numeric(text)

        answer_summary = ", ".join(
            f"{mid}={ans}" for mid, ans in extracted.items() if ans
        )
        logger.info("council.step2_extracted", answers=answer_summary)

        # ── Step 3: Check agreement ───────────────────────────
        concrete_answers = {mid: ans for mid, ans in extracted.items() if ans}
        if concrete_answers:
            unique_answers = set(concrete_answers.values())

            if len(unique_answers) == 1:
                # ALL AGREE -- high confidence, no debate needed
                consensus_answer = unique_answers.pop()
                consensus_model = next(iter(concrete_answers))
                elapsed = int((time.perf_counter_ns() - start) / 1_000_000)

                logger.info(
                    "council.unanimous",
                    answer=consensus_answer,
                    models=len(concrete_answers),
                )
                return DebateResult(
                    winner_model=f"council_unanimous({len(concrete_answers)})",
                    winner_answer=all_answers[consensus_model],
                    winner_reasoning=(
                        f"All {len(concrete_answers)} models independently "
                        f"agreed on answer {consensus_answer}. "
                        f"No debate needed -- unanimous consensus."
                    ),
                    confidence=min(0.95, 0.7 + 0.1 * len(concrete_answers)),
                    rounds=rounds,
                    all_answers=all_answers,
                    total_latency_ms=elapsed,
                )

        # ── Step 3.5: Anonymize FIRST (needed by peer ranking) ──
        # ANONYMIZE: use "Reasoner A, B, C..." so models can't favor
        # any model by name (Karpathy insight: prevents self-bias)
        labels = [chr(65 + i) for i in range(len(all_answers))]
        label_map = dict(zip(labels, all_answers.keys()))
        reverse_map = {v: k for k, v in label_map.items()}

        answers_text = "\n\n".join(
            f"=== Reasoner {reverse_map[mid]} "
            f"(answer: {extracted.get(mid, '?')}) ===\n{text[:2000]}"
            for mid, text in all_answers.items()
        )
        answer_summary_anon = ", ".join(
            f"Reasoner {reverse_map[mid]}={ans}"
            for mid, ans in extracted.items() if ans
        )

        # ── Step 4: Select analyst ────────────────────────────
        # Use a DIFFERENT model as analyst (not the primary)
        # to prevent dictator bias
        if analyst_model is None:
            from collections import Counter
            vote_counts = Counter(
                ans for ans in concrete_answers.values() if ans
            )
            if vote_counts:
                majority_answer = vote_counts.most_common(1)[0][0]
                dissenters = [
                    mid for mid, ans in concrete_answers.items()
                    if ans != majority_answer
                ]
                if dissenters:
                    analyst_model = dissenters[0]
                else:
                    analyst_model = model_ids[-1] if len(model_ids) > 1 else model_ids[0]
            else:
                analyst_model = model_ids[-1]

        # ── Step 5: Peer ranking (Karpathy insight) ───────────
        # Each model ranks the anonymized answers. Aggregate rank
        # gives a quality signal BEFORE deep analysis.
        logger.info("council.step5_peer_ranking", models=len(all_answers))

        from app.services.providers.base import GenerateRequest, LLMMessage

        # Build ranking prompt with already-anonymized text
        _rank_prompt_text = (
            "You solved this problem and produced your own answer. Now review "
            "the other reasoners' solutions (anonymized). Rank ALL solutions "
            "from best to worst based on reasoning quality, not just final answer.\n\n"
            f"Question: {query}\n\n{answers_text}\n\n"
            "Output ONLY a ranking like:\n"
            "FINAL RANKING:\n"
            "1. Reasoner B\n"
            "2. Reasoner A\n"
            "3. Reasoner C\n"
        )

        rank_scores: dict[str, float] = {mid: 0.0 for mid in all_answers}
        rank_count = 0

        async def _peer_rank(ranker_mid: str) -> dict[str, int] | None:
            try:
                resp = await self._llm.generate_direct(GenerateRequest(
                    messages=[LLMMessage(role="user", content=_rank_prompt_text)],
                    model_id=ranker_mid,
                    temperature=0.1,
                    max_tokens=512,
                ))
                ranks = re.findall(r'(\d+)\.\s*Reasoner\s+([A-Z])', resp.content)
                return {label_map.get(letter, ""): int(pos) for pos, letter in ranks}
            except Exception:
                return None

        rank_results = await asyncio.gather(
            *[_peer_rank(mid) for mid in all_answers],
            return_exceptions=True,
        )

        for ranking in rank_results:
            if isinstance(ranking, dict) and ranking:
                rank_count += 1
                for mid, position in ranking.items():
                    if mid in rank_scores:
                        rank_scores[mid] += (len(all_answers) + 1 - position)

        if rank_count > 0:
            for mid in rank_scores:
                rank_scores[mid] /= rank_count

        peer_ranking_summary = ", ".join(
            f"{reverse_map.get(mid, '?')}={score:.1f}"
            for mid, score in sorted(rank_scores.items(), key=lambda x: -x[1])
        )
        logger.info(
            "council.peer_ranking",
            scores=peer_ranking_summary,
            rankers=rank_count,
        )

        # ── Step 6: Blind spot analysis ───────────────────────
        logger.info(
            "council.step6_blind_spot_analysis",
            analyst=analyst_model,
            disagreement=answer_summary,
            peer_ranking=peer_ranking_summary,
        )

        blind_spot_prompt = _COUNCIL_BLIND_SPOT.format(
            query=query,
            answers_text=answers_text,
            answer_summary=answer_summary_anon,
        )

        try:
            analysis_result = await self._llm.generate_direct(GenerateRequest(
                messages=[
                    LLMMessage(role="user", content=blind_spot_prompt),
                ],
                model_id=analyst_model,
                temperature=0.1,
                max_tokens=2048,
            ))
            analysis = analysis_result.content
        except Exception as exc:
            logger.warning("council.analysis_failed", error=str(exc))
            analysis = ""

        rounds.append(DebateRound(
            round_num=2, model_id=analyst_model,
            content=analysis, role="blind_spot_analysis", confidence=0.0,
        ))

        # ── Step 5: Extract the council's conclusion ──────────
        # Parse the analyst's FINAL_ANSWER and CONFIDENCE
        council_answer = None
        council_confidence = 0.6

        if analysis:
            final_match = re.search(
                r'FINAL_ANSWER[:\s]+(\S+)', analysis, re.IGNORECASE,
            )
            if final_match:
                nums = re.findall(r'-?\d+', final_match.group(1))
                if nums:
                    council_answer = nums[0]

            conf_match = re.search(
                r'CONFIDENCE[:\s]+([0-9.]+)', analysis, re.IGNORECASE,
            )
            if conf_match:
                council_confidence = min(float(conf_match.group(1)), 1.0)

        # If analyst couldn't determine, fall back to majority vote
        if council_answer is None and concrete_answers:
            from collections import Counter
            vote_counts = Counter(concrete_answers.values())
            council_answer = vote_counts.most_common(1)[0][0]
            council_confidence = vote_counts.most_common(1)[0][1] / len(concrete_answers)
            logger.info("council.fallback_to_majority", answer=council_answer)

        # Find which model's full response best matches the council answer
        best_model = model_ids[0]
        for mid, ans in extracted.items():
            if ans == council_answer:
                best_model = mid
                break

        elapsed = int((time.perf_counter_ns() - start) / 1_000_000)

        reasoning = (
            f"Council of {len(all_answers)} models. "
            f"Answers: {answer_summary}. "
            f"Analyst ({analyst_model}) examined reasoning chains. "
            f"Council answer: {council_answer} (conf={council_confidence:.0%})"
        )

        logger.info(
            "council.complete",
            answer=council_answer,
            confidence=council_confidence,
            analyst=analyst_model,
            elapsed_ms=elapsed,
        )

        return DebateResult(
            winner_model=f"council({best_model})",
            winner_answer=all_answers.get(best_model, str(council_answer)),
            winner_reasoning=reasoning,
            confidence=council_confidence,
            rounds=rounds,
            all_answers=all_answers,
            total_latency_ms=elapsed,
        )

    # ── Disagreement-focused debate (beyond Mythos) ────────────

    async def _identify_disagreements(
        self,
        query: str,
        all_answers: dict[str, str],
        analyzer_model: str,
    ) -> list[DisagreementPoint]:
        """Identify specific points where models disagree.

        Instead of broad critiques, find the EXACT claims that conflict
        between model answers. This focuses the debate on what matters.
        """
        from app.services.providers.base import GenerateRequest, LLMMessage

        models = list(all_answers.keys())
        if len(models) < 2:
            return []

        answers_text = "\n\n".join(
            f"--- {model} ---\n{answer}" for model, answer in all_answers.items()
        )

        prompt = _DISAGREEMENT_IDENTIFY.format(
            query=query,
            answers_text=answers_text,
            model_a=models[0],
            model_b=models[1],
        )
        messages = [LLMMessage(role="user", content=prompt)]

        request = GenerateRequest(
            messages=messages,
            model_id=analyzer_model,
            temperature=0.2,
            max_tokens=768,
        )

        try:
            result = await self._llm.generate_direct(request)
            return self._parse_disagreements(result.content, models)
        except Exception as e:
            logger.warning("amd_disagreement_id_failed", error=str(e))
            return []

    async def _argue_disagreements(
        self,
        query: str,
        model_id: str,
        model_answer: str,
        disagreements: list[DisagreementPoint],
    ) -> LLMResponse:
        """Have a model argue its case on specific disagreement points."""
        from app.services.providers.base import GenerateRequest, LLMMessage

        # Build focused argument prompt from disagreement points
        argument_parts = []
        for dp in disagreements[:3]:  # Cap at 3 disagreement points
            my_position = dp.positions.get(model_id, model_answer[:200])
            other_positions = {
                m: p for m, p in dp.positions.items() if m != model_id
            }
            if other_positions:
                other_model, other_pos = next(iter(other_positions.items()))
                argument_parts.append(
                    _DISAGREEMENT_ARGUE.format(
                        query=query,
                        topic=dp.topic,
                        your_position=my_position,
                        their_position=other_pos,
                    )
                )

        if not argument_parts:
            # No specific disagreements to argue -- fall back to general critique
            return await self._generate_answer(query, model_id, "")

        combined_prompt = "\n\n---\n\n".join(argument_parts)
        messages = [LLMMessage(role="user", content=combined_prompt)]

        request = GenerateRequest(
            messages=messages,
            model_id=model_id,
            temperature=0.4,
            max_tokens=1024,
        )
        return await self._llm.generate_direct(request)

    def _parse_disagreements(
        self, text: str, models: list[str],
    ) -> list[DisagreementPoint]:
        """Parse LLM output into structured disagreement points."""
        import re
        disagreements: list[DisagreementPoint] = []

        # Split by TOPIC markers
        blocks = re.split(r"TOPIC:\s*", text, flags=re.IGNORECASE)

        for block in blocks[1:]:  # Skip first empty split
            lines = block.strip().split("\n")
            if not lines:
                continue

            topic = lines[0].strip()
            positions: dict[str, str] = {}

            for line in lines[1:]:
                line = line.strip()
                for model_id in models:
                    # Match "MODEL_A (model_name): position" or "model_name: position"
                    pattern = rf"(?:MODEL_[A-Z]\s*\()?{re.escape(model_id)}\)?:\s*(.+)"
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        positions[model_id] = match.group(1).strip()

            if topic and len(positions) >= 2:
                disagreements.append(DisagreementPoint(
                    topic=topic,
                    positions=positions,
                ))

        return disagreements[:5]  # Cap at 5 disagreement points
