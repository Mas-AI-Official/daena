"""Cost-aware model selection for Daena's routing pipeline.

Picks the best models for each reasoning mode based on cost efficiency.
NEVER changes the reasoning mode itself -- that is the user's sacred choice.

Classification uses zero-cost keyword matching, not LLM calls.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Task type keywords for zero-cost classification
_SIMPLE_KEYWORDS = frozenset([
    "hello", "hi", "hey", "thanks", "ok", "yes", "no", "what time",
    "who are you", "help", "good morning", "goodbye", "thank you",
])
_CODE_KEYWORDS = frozenset([
    "code", "function", "class", "debug", "error", "fix", "implement",
    "python", "javascript", "typescript", "react", "api", "endpoint",
    "bug", "compile", "syntax", "refactor", "test", "deploy",
])
_RESEARCH_KEYWORDS = frozenset([
    "research", "compare", "analyze", "study", "review", "report",
    "summarize", "investigate", "find", "search", "explain",
])


class CostAwareRouter:
    """Picks the best models for each reasoning mode based on cost.

    NEVER changes the reasoning mode. That is the user's choice.
    Only decides WHICH MODELS serve the chosen mode.
    """

    def classify_task(self, message: str) -> str:
        """Classify task type using keyword matching (0 tokens, instant).

        Returns: SIMPLE, CODE, RESEARCH, or REASONING.
        """
        msg_lower = message.lower().strip()

        # Simple: exact or near-exact matches
        for kw in _SIMPLE_KEYWORDS:
            if msg_lower == kw or msg_lower.startswith(kw + " ") or msg_lower.startswith(kw + ","):
                return "SIMPLE"

        # Code: 2+ code keywords
        code_score = sum(1 for kw in _CODE_KEYWORDS if kw in msg_lower)
        if code_score >= 2:
            return "CODE"

        # Research: 2+ research keywords
        research_score = sum(1 for kw in _RESEARCH_KEYWORDS if kw in msg_lower)
        if research_score >= 2:
            return "RESEARCH"

        return "REASONING"

    def select_models_for_mode(
        self,
        reasoning_mode: str,
        task_type: str,
        available_models: list[dict[str, Any]],
        primary_mind: str | None = None,
    ) -> list[str]:
        """Select models based on reasoning mode and task type.

        Args:
            reasoning_mode: STANDARD, COUNCIL, QUINTESSENCE, or AUTO
            task_type: SIMPLE, CODE, RESEARCH, REASONING
            available_models: [{"id": "model_name", "provider": "ollama/claude/..."}]
            primary_mind: user's preferred primary runtime

        Returns:
            List of model IDs. Length depends on mode:
            - STANDARD: [1 model]
            - COUNCIL/QUINTESSENCE: [3 models]
        """
        if not available_models:
            return []

        ollama = [m for m in available_models if m.get("provider") == "ollama"]
        cli = [m for m in available_models if m.get("provider") in ("claude_code", "codex", "gemini")]

        def _cheapest() -> str:
            if ollama:
                for pref in ["mistral:7b", "llama3.1:latest", "llama3.1:8b"]:
                    if any(m["id"] == pref for m in ollama):
                        return pref
                return ollama[0]["id"]
            return available_models[0]["id"]

        def _smartest() -> str:
            if primary_mind and any(m["id"] == primary_mind for m in available_models):
                return primary_mind
            for pref in ["deepseek-r1:14b", "qwen3.5:27b", "qwen3-coder:30b"]:
                if any(m["id"] == pref for m in ollama):
                    return pref
            if cli:
                return cli[0]["id"]
            return available_models[0]["id"]

        def _best_code() -> str:
            for pref in ["qwen2.5-coder:14b", "qwen3-coder:30b"]:
                if any(m["id"] == pref for m in ollama):
                    return pref
            codex = [m for m in cli if m.get("provider") == "codex"]
            if codex:
                return codex[0]["id"]
            return _smartest()

        def _diverse_three() -> list[str]:
            """Pick 3 different models for diverse perspectives."""
            candidates: list[str] = []

            # 1. Reasoning model
            for m_id in ["deepseek-r1:14b", "qwen3.5:27b"]:
                if any(mod["id"] == m_id for mod in ollama):
                    candidates.append(m_id)
                    break
            if not candidates:
                candidates.append(_smartest())

            # 2. Code/technical model
            for m_id in ["qwen2.5-coder:14b", "qwen3-coder:30b"]:
                if any(mod["id"] == m_id for mod in ollama) and m_id not in candidates:
                    candidates.append(m_id)
                    break
            if len(candidates) < 2:
                remaining = [m["id"] for m in ollama if m["id"] not in candidates]
                if remaining:
                    candidates.append(remaining[0])

            # 3. General/different model
            for m_id in ["mistral:7b", "llama3.1:latest"]:
                if any(mod["id"] == m_id for mod in ollama) and m_id not in candidates:
                    candidates.append(m_id)
                    break
            if len(candidates) < 3:
                remaining = [m["id"] for m in available_models if m["id"] not in candidates]
                if remaining:
                    candidates.append(remaining[0])

            # Pad if needed (single-model Council still works)
            while len(candidates) < 3:
                candidates.append(candidates[0])

            return candidates[:3]

        # Mode-based selection (the sacred part)
        if reasoning_mode == "STANDARD":
            if task_type == "SIMPLE":
                return [_cheapest()]
            elif task_type == "CODE":
                return [_best_code()]
            return [_smartest()]

        if reasoning_mode in ("COUNCIL", "QUINTESSENCE"):
            return _diverse_three()

        if reasoning_mode == "AUTO":
            if task_type == "SIMPLE":
                return [_cheapest()]
            if len(available_models) >= 3:
                return _diverse_three()
            return [_smartest()]

        return [_smartest()]

    def get_auto_reasoning_mode(self, task_type: str, model_count: int) -> str:
        """When user selects AUTO, determine reasoning mode from task type."""
        if task_type == "SIMPLE":
            return "STANDARD"
        if model_count >= 3:
            return "COUNCIL"
        return "STANDARD"
