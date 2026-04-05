"""Gap 2: Extended Thinking Engine (DeepThink).

Allows a single model to spend extended time reasoning before answering,
exploring multiple paths, backtracking, and self-correcting. This is NOT
multi-model debate (that is AMD/debate.py). This is one model going deep.

Supports two modes:
    1. Native thinking: DeepSeek R1 emits <think>...</think> tags natively.
       We parse those directly.
    2. Prompted thinking: For models without native thinking support, we
       craft a meta-prompt that forces structured reasoning with explicit
       markers (Approach 1:, Wait, Actually, ANSWER:).

The engine returns both the thinking trace and the final answer as
separate fields, along with metrics on reasoning quality (paths explored,
backtracks, confidence).
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.services.llm_service import LLMService
    from app.services.providers.base import LLMResponse

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns for parsing thinking traces
# ---------------------------------------------------------------------------

_THINK_TAG_RE = re.compile(
    r"<think>(.*?)</think>",
    re.DOTALL,
)

_ANSWER_MARKER_RE = re.compile(
    r"(?:^|\n)\s*ANSWER\s*:\s*",
    re.IGNORECASE,
)

_APPROACH_RE = re.compile(
    r"(?:^|\n)\s*(?:Approach|Option|Path|Method|Strategy)\s+\d+\s*:",
    re.IGNORECASE,
)

_BACKTRACK_RE = re.compile(
    r"(?:^|\n)\s*(?:"
    r"Wait(?:,|\s)"
    r"|Actually(?:,|\s)"
    r"|No(?:,|\s)that(?:'s| is) (?:wrong|incorrect|not right)"
    r"|Let me (?:reconsider|rethink|try again|revise)"
    r"|On second thought"
    r"|I was wrong"
    r"|Correction:"
    r"|Hmm(?:,|\s)that doesn(?:'t| not) work"
    r"|That(?:'s| is) (?:wrong|incorrect) because"
    r")",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class DeepThinkResult:
    """Output of the Deep Think Engine."""

    thinking_trace: str
    answer: str
    thinking_tokens: int
    answer_tokens: int
    paths_explored: int
    backtrack_count: int
    confidence: float
    total_latency_ms: int


# ---------------------------------------------------------------------------
# Meta-prompt template
# ---------------------------------------------------------------------------

_THINKING_META_PROMPT = """\
You are solving a problem that requires deep, careful reasoning. Follow this \
exact protocol:

1. EXPLORE at least 3 different approaches before committing to one. Label \
them "Approach 1:", "Approach 2:", "Approach 3:", etc.

2. For each approach, IDENTIFY where you might be wrong. Explicitly state \
potential pitfalls or errors.

3. If you realize an approach is flawed, SAY SO explicitly. Use phrases like \
"Wait, that's wrong because...", "Actually, let me reconsider...", or \
"No, that doesn't work because...". Then backtrack and try a different path.

4. Show your FULL reasoning chain with explicit numbered steps within each \
approach.

5. After exploring approaches, CHOOSE the best one and explain why the \
others are inferior.

6. End with a clear final answer on its own line, prefixed EXACTLY with:
ANSWER: <your final answer here>

The ANSWER section must contain ONLY the final, clean answer -- no reasoning, \
no hedging, no meta-commentary. Everything before ANSWER: is your thinking \
trace. Everything after is the delivered answer.

Here is the problem to solve:

{query}"""


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class DeepThinkEngine:
    """Extended Thinking mode for single-model deep reasoning.

    Wraps an LLM call with structured meta-prompting that forces the model
    to explore multiple reasoning paths, self-correct, and produce a clear
    final answer. Supports both native thinking models (DeepSeek R1) and
    prompted thinking for any other model.
    """

    # Models known to emit native <think> tags
    _NATIVE_THINKING_MODELS = frozenset({
        "deepseek-r1",
        "deepseek-r1:14b",
        "deepseek-r1:32b",
        "deepseek-r1:70b",
        "deepseek-r1:latest",
    })

    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service

    async def think(
        self,
        query: str,
        *,
        model_id: str,
        thinking_budget: int = 4096,
        system_prompt: str = "",
    ) -> DeepThinkResult:
        """Run extended thinking on a query using a single model.

        Args:
            query: The user question or problem to reason about.
            model_id: Which model to use for thinking.
            thinking_budget: Maximum tokens to allocate for the thinking
                phase. The answer budget is implicitly the remainder up to
                the model's context window, capped at ``thinking_budget``.
            system_prompt: Optional system prompt prepended before the
                thinking meta-prompt.

        Returns:
            DeepThinkResult with separated thinking trace and answer.
        """
        from app.services.providers.base import GenerateRequest, LLMMessage

        start_ms = _now_ms()

        is_native = self._is_native_thinker(model_id)

        # For native thinkers, we send the raw query and let the model's
        # own <think> mechanism handle reasoning. For non-native models,
        # we wrap the query in our structured meta-prompt.
        if is_native:
            user_content = query
        else:
            user_content = self._build_thinking_prompt(query)

        messages: list[LLMMessage] = []
        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))
        messages.append(LLMMessage(role="user", content=user_content))

        # Allocate generous token budget: thinking + answer
        total_tokens = thinking_budget * 2

        request = GenerateRequest(
            messages=messages,
            model_id=model_id,
            temperature=0.7,
            max_tokens=total_tokens,
            metadata={"laevateinn_stage": "deep_think", "thinking_budget": thinking_budget},
        )

        response: LLMResponse = await self._llm.generate_direct(request)

        raw_text = response.content
        thinking, answer = self._parse_thinking_response(raw_text)

        paths_explored = self._count_paths(thinking)
        backtrack_count = self._count_backtracks(thinking)

        # Estimate token counts from the response metadata when available,
        # otherwise approximate from character length (rough 4 chars/token).
        thinking_tokens = self._estimate_tokens(thinking, response.token_count_output, raw_text)
        answer_tokens = self._estimate_tokens(answer, response.token_count_output, raw_text)

        # Confidence heuristic: higher when more paths explored and
        # backtracks occurred (indicates genuine self-correction).
        confidence = self._estimate_confidence(
            paths_explored=paths_explored,
            backtrack_count=backtrack_count,
            has_answer=bool(answer.strip()),
        )

        elapsed = _now_ms() - start_ms

        logger.info(
            "deep_think_complete",
            model_id=model_id,
            is_native=is_native,
            paths_explored=paths_explored,
            backtrack_count=backtrack_count,
            confidence=round(confidence, 3),
            latency_ms=elapsed,
        )

        return DeepThinkResult(
            thinking_trace=thinking,
            answer=answer,
            thinking_tokens=thinking_tokens,
            answer_tokens=answer_tokens,
            paths_explored=paths_explored,
            backtrack_count=backtrack_count,
            confidence=confidence,
            total_latency_ms=elapsed,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_thinking_prompt(self, query: str) -> str:
        """Craft the meta-prompt that forces structured thinking.

        This is used for models that do NOT have native extended thinking
        (i.e., everything except DeepSeek R1). The prompt instructs the
        model to explore multiple approaches, identify errors, backtrack,
        and conclude with a clear ANSWER: section.
        """
        return _THINKING_META_PROMPT.format(query=query)

    def _parse_thinking_response(self, raw: str) -> tuple[str, str]:
        """Separate thinking trace from final answer.

        Handles two formats:
            1. Native ``<think>...</think>`` tags (DeepSeek R1).
            2. Prompted ``ANSWER:`` marker from our meta-prompt.

        Falls back to treating the entire response as the answer if
        neither format is detected.

        Returns:
            (thinking_trace, answer) tuple.
        """
        # Strategy 1: Native <think> tags
        think_match = _THINK_TAG_RE.search(raw)
        if think_match:
            thinking = think_match.group(1).strip()
            # Everything after the closing </think> tag is the answer
            after_think = raw[think_match.end():].strip()
            # If there is also an ANSWER: marker within the post-think text,
            # use it to further refine
            answer_split = _ANSWER_MARKER_RE.split(after_think, maxsplit=1)
            if len(answer_split) > 1:
                answer = answer_split[-1].strip()
            else:
                answer = after_think
            return thinking, answer

        # Strategy 2: ANSWER: marker from prompted thinking
        answer_split = _ANSWER_MARKER_RE.split(raw, maxsplit=1)
        if len(answer_split) > 1:
            thinking = answer_split[0].strip()
            answer = answer_split[-1].strip()
            return thinking, answer

        # Strategy 3: No markers found. Treat the last paragraph as the
        # answer and everything before as thinking.
        paragraphs = [p.strip() for p in raw.split("\n\n") if p.strip()]
        if len(paragraphs) >= 2:
            answer = paragraphs[-1]
            thinking = "\n\n".join(paragraphs[:-1])
            return thinking, answer

        # Final fallback: entire response is the answer, no thinking trace
        return "", raw.strip()

    def _count_paths(self, thinking: str) -> int:
        """Count distinct reasoning paths explored in the thinking trace.

        Looks for explicit approach/option/path markers. If the model
        used our meta-prompt correctly, these will be clearly labeled.
        Returns at least 1 if there is any thinking content at all.
        """
        if not thinking.strip():
            return 0
        matches = _APPROACH_RE.findall(thinking)
        return max(len(matches), 1)

    def _count_backtracks(self, thinking: str) -> int:
        """Count how many times the model revised or corrected its reasoning.

        Looks for phrases indicating the model caught its own mistake
        and changed direction.
        """
        if not thinking.strip():
            return 0
        return len(_BACKTRACK_RE.findall(thinking))

    def _is_native_thinker(self, model_id: str) -> bool:
        """Check whether a model supports native <think> tags."""
        normalized = model_id.lower().strip()
        # Exact match first
        if normalized in self._NATIVE_THINKING_MODELS:
            return True
        # Prefix match for versioned variants (e.g., deepseek-r1:7b-q4_0)
        return any(normalized.startswith(prefix) for prefix in ("deepseek-r1:",))

    @staticmethod
    def _estimate_tokens(segment: str, total_output_tokens: int, full_text: str) -> int:
        """Estimate token count for a text segment.

        When the provider reports total output tokens, we proportionally
        allocate based on character ratio. Otherwise fall back to the
        rough 4-chars-per-token heuristic.
        """
        if not segment:
            return 0
        if total_output_tokens > 0 and full_text:
            ratio = len(segment) / max(len(full_text), 1)
            return max(1, int(total_output_tokens * ratio))
        return max(1, len(segment) // 4)

    @staticmethod
    def _estimate_confidence(
        *,
        paths_explored: int,
        backtrack_count: int,
        has_answer: bool,
    ) -> float:
        """Heuristic confidence score based on thinking quality.

        Higher confidence when:
            - Multiple paths were explored (breadth of reasoning)
            - Backtracks occurred (self-correction happened)
            - A clear answer was extracted

        The score is purely heuristic and not a calibrated probability.
        """
        if not has_answer:
            return 0.1

        # Base: exploring multiple paths is good
        path_score = min(paths_explored / 4.0, 1.0) * 0.4

        # Backtracking indicates genuine self-correction (diminishing returns)
        backtrack_score = min(backtrack_count / 3.0, 1.0) * 0.3

        # Having a clear answer section is worth a base amount
        answer_score = 0.3

        return round(min(path_score + backtrack_score + answer_score, 1.0), 3)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _now_ms() -> int:
    """Current time in milliseconds (monotonic clock)."""
    return int(time.monotonic() * 1000)
