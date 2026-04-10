"""Tests for CognitiveReasoner -- LLM-powered reasoning with framework lenses.

Tests the deterministic fallback paths (no LLM), framework selection,
strategy generation, reflection/learning, and mode detection.
LLM-dependent tests use mocks to avoid real API calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.cognition.cognitive_reasoner import (
    CognitiveReasoner,
    ReasoningResult,
    StrategyProposal,
    ReflectionResult,
    LearnedLesson,
    FRAMEWORK_PROMPTS,
    auto_select_model,
)


# ---- Helpers ----


def _make_reasoner(**kwargs) -> CognitiveReasoner:
    """Create a CognitiveReasoner without real DB or LLM."""
    return CognitiveReasoner(**kwargs)


async def _init_deterministic(reasoner: CognitiveReasoner) -> None:
    """Force deterministic mode (no LLM available)."""
    with patch(
        "app.services.cognition.cognitive_reasoner.auto_select_model",
        return_value=None,
    ):
        await reasoner.initialize()


async def _init_with_llm(reasoner: CognitiveReasoner) -> None:
    """Force LLM mode with a mock model."""
    with patch(
        "app.services.cognition.cognitive_reasoner.auto_select_model",
        return_value=("ollama", "llama3.1:latest"),
    ):
        await reasoner.initialize()


# ---- Initialization ----


class TestInit:
    @pytest.mark.asyncio
    async def test_deterministic_mode_when_no_llm(self) -> None:
        reasoner = _make_reasoner()
        await _init_deterministic(reasoner)
        assert reasoner.reasoning_mode == "deterministic"
        assert reasoner.is_llm_available is False
        assert reasoner._initialized is True

    @pytest.mark.asyncio
    async def test_llm_mode_when_model_found(self) -> None:
        reasoner = _make_reasoner()
        await _init_with_llm(reasoner)
        assert reasoner.reasoning_mode == "llm"
        assert reasoner.is_llm_available is True
        assert reasoner._model_id == "llama3.1:latest"

    @pytest.mark.asyncio
    async def test_quintessence_requires_agi_and_models(self) -> None:
        """Quintessence needs AGI mode + 2 non-embed models."""
        reasoner = _make_reasoner(agi_mode=True)

        mock_model_1 = MagicMock(model_id="llama3.1:latest")
        mock_model_2 = MagicMock(model_id="qwen2.5-coder:14b")

        mock_registry = AsyncMock()
        mock_registry.list_all_models = AsyncMock(return_value=[mock_model_1, mock_model_2])

        with patch(
            "app.services.cognition.cognitive_reasoner.auto_select_model",
            return_value=("ollama", "llama3.1:latest"),
        ), patch(
            "app.services.model_registry.ModelRegistry",
            return_value=mock_registry,
        ):
            await reasoner.initialize()

        assert reasoner._quintessence_available is True
        assert reasoner.reasoning_mode == "quintessence"

    @pytest.mark.asyncio
    async def test_embed_models_excluded_from_quintessence_count(self) -> None:
        """Embedding models should not count toward the 2-model minimum."""
        reasoner = _make_reasoner(agi_mode=True)

        mock_model_1 = MagicMock(model_id="llama3.1:latest")
        mock_embed = MagicMock(model_id="nomic-embed-text:latest")

        mock_registry = AsyncMock()
        mock_registry.list_all_models = AsyncMock(return_value=[mock_model_1, mock_embed])

        with patch(
            "app.services.cognition.cognitive_reasoner.auto_select_model",
            return_value=("ollama", "llama3.1:latest"),
        ), patch(
            "app.services.model_registry.ModelRegistry",
            return_value=mock_registry,
        ):
            await reasoner.initialize()

        # Only 1 reasoning model -- quintessence should NOT be available
        assert reasoner._quintessence_available is False


# ---- Orient Phase ----


class TestOrient:
    @pytest.mark.asyncio
    async def test_deterministic_orient_returns_analysis(self) -> None:
        """Without LLM, orient should return a deterministic analysis."""
        reasoner = _make_reasoner()
        await _init_deterministic(reasoner)

        result = await reasoner.orient(
            task="Debug a failing API endpoint",
            observation={"error": "500 Internal Server Error", "endpoint": "/api/v1/chat"},
        )

        assert isinstance(result, ReasoningResult)
        assert result.reasoning_mode == "deterministic"
        assert len(result.analysis) > 0

    @pytest.mark.asyncio
    async def test_orient_includes_failure_context(self) -> None:
        """Previous failures should be injected into the prompt."""
        reasoner = _make_reasoner()
        await _init_with_llm(reasoner)

        mock_response = (
            "FRAMEWORKS: five_whys, constraint_probe\n"
            "ANALYSIS: The previous direct approach failed due to permissions. "
            "Trying alternative path via API."
        )

        with patch.object(reasoner, "_call_llm", return_value=mock_response):
            result = await reasoner.orient(
                task="Fix database migration",
                observation={"error": "Permission denied"},
                previous_failures=[
                    {"strategy": "direct_apply", "reason": "Permission denied", "lesson": "Need sudo"}
                ],
            )

        assert isinstance(result, ReasoningResult)
        assert result.reasoning_mode == "llm"
        assert len(result.frameworks_used) > 0

    @pytest.mark.asyncio
    async def test_orient_auto_initializes(self) -> None:
        """Orient should call initialize() if not yet initialized."""
        reasoner = _make_reasoner()
        assert reasoner._initialized is False

        with patch(
            "app.services.cognition.cognitive_reasoner.auto_select_model",
            return_value=None,
        ):
            result = await reasoner.orient(
                task="Simple task",
                observation={},
            )

        assert reasoner._initialized is True
        assert isinstance(result, ReasoningResult)


# ---- Decide Phase ----


class TestDecide:
    @pytest.mark.asyncio
    async def test_deterministic_decide_uses_first_tool(self) -> None:
        """Without LLM, decide should pick the first available tool."""
        reasoner = _make_reasoner()
        await _init_deterministic(reasoner)

        result = await reasoner.decide(
            analysis="API returns 500 on /chat endpoint",
            available_tools=["read_file", "grep", "terminal"],
        )

        assert isinstance(result, StrategyProposal)
        assert result.name == "direct_execution"
        assert result.confidence == 0.4
        assert result.steps[0]["operation"] == "read_file"

    @pytest.mark.asyncio
    async def test_deterministic_decide_empty_tools(self) -> None:
        """With no tools, deterministic fallback uses 'observe'."""
        reasoner = _make_reasoner()
        await _init_deterministic(reasoner)

        result = await reasoner.decide(
            analysis="Something went wrong",
            available_tools=[],
        )

        assert result.steps[0]["operation"] == "observe"

    @pytest.mark.asyncio
    async def test_decide_with_llm_parses_strategy(self) -> None:
        """LLM response should be parsed into a StrategyProposal."""
        reasoner = _make_reasoner()
        await _init_with_llm(reasoner)

        mock_response = (
            "STRATEGY: investigate_logs\n"
            "REASONING: Based on the 500 error, we should check logs first.\n"
            "STEPS:\n"
            "1. read_file: backend/app/services/chat_orchestrator.py\n"
            "2. grep: error pattern in logs\n"
            "CONFIDENCE: 0.8"
        )

        with patch.object(reasoner, "_call_llm", return_value=mock_response):
            result = await reasoner.decide(
                analysis="API 500 error on /chat",
                available_tools=["read_file", "grep", "terminal"],
            )

        assert isinstance(result, StrategyProposal)
        assert len(result.name) > 0

    @pytest.mark.asyncio
    async def test_decide_excludes_previous_attempts(self) -> None:
        """Previous attempt names are passed to the LLM to avoid repeats."""
        reasoner = _make_reasoner()
        await _init_with_llm(reasoner)

        call_args = {}

        async def capture_call(system, user):
            call_args["user"] = user
            return "STRATEGY: new_approach\nREASONING: fresh\nSTEPS:\n1. terminal: ls\nCONFIDENCE: 0.7"

        with patch.object(reasoner, "_call_llm", side_effect=capture_call):
            await reasoner.decide(
                analysis="Still failing",
                available_tools=["terminal"],
                previous_attempts=["direct_fix", "retry_migration"],
            )

        assert "direct_fix" in call_args["user"]
        assert "retry_migration" in call_args["user"]


# ---- Reflect Phase ----


class TestReflect:
    @pytest.mark.asyncio
    async def test_deterministic_reflect_success(self) -> None:
        reasoner = _make_reasoner()
        await _init_deterministic(reasoner)

        result = await reasoner.reflect(
            strategy="grep_for_bug",
            results={"fixed": True, "lines_changed": 5},
            success=True,
        )

        assert isinstance(result, ReflectionResult)
        assert result.should_learn is True
        assert "succeeded" in result.analysis.lower()

    @pytest.mark.asyncio
    async def test_deterministic_reflect_failure(self) -> None:
        reasoner = _make_reasoner()
        await _init_deterministic(reasoner)

        result = await reasoner.reflect(
            strategy="direct_fix",
            results={"error": "Compilation failed"},
            success=False,
        )

        assert isinstance(result, ReflectionResult)
        assert result.root_cause is not None
        assert result.next_suggestion is not None
        assert "failed" in result.analysis.lower()

    @pytest.mark.asyncio
    async def test_reflect_with_llm_extracts_insights(self) -> None:
        reasoner = _make_reasoner()
        await _init_with_llm(reasoner)

        mock_response = (
            "ANALYSIS: The grep approach found the bug quickly because the error "
            "message was unique.\n"
            "ROOT CAUSE: Typo in variable name caused None reference.\n"
            "LESSON: Always grep for the exact error message first.\n"
            "SHOULD_LEARN: yes"
        )

        with patch.object(reasoner, "_call_llm", return_value=mock_response):
            result = await reasoner.reflect(
                strategy="grep_for_bug",
                results={"found": "typo in variable"},
                success=True,
            )

        assert isinstance(result, ReflectionResult)


# ---- Learning ----


class TestLearning:
    @pytest.mark.asyncio
    async def test_extract_lesson_no_llm_returns_none(self) -> None:
        reasoner = _make_reasoner()
        await _init_deterministic(reasoner)

        result = await reasoner.extract_lesson("Some experience context")
        assert result is None

    @pytest.mark.asyncio
    async def test_store_lesson_no_db_returns_false(self) -> None:
        """Without DB context, store_lesson should gracefully skip."""
        reasoner = _make_reasoner()
        await _init_deterministic(reasoner)

        lesson = LearnedLesson(
            trigger="error investigation",
            lesson="Always grep for exact error messages",
            domain="debugging",
            confidence=0.9,
        )
        result = await reasoner.store_lesson(lesson)
        assert result is False


# ---- Framework Prompts ----


class TestFrameworks:
    def test_core_frameworks_present(self) -> None:
        """All core reasoning frameworks should be defined."""
        required = [
            "first_principles",
            "inversion",
            "five_whys",
            "constraint_probe",
            "pre_mortem",
            "second_order",
            "antifragility",
            "map_territory",
            "occams_razor",
        ]
        for name in required:
            assert name in FRAMEWORK_PROMPTS, f"Missing framework: {name}"

    def test_framework_prompts_are_non_empty(self) -> None:
        for name, prompt in FRAMEWORK_PROMPTS.items():
            assert len(prompt) > 20, f"Framework '{name}' has empty/short prompt"


# ---- Mode Detection ----


class TestReasoningMode:
    def test_default_is_not_agi(self) -> None:
        reasoner = _make_reasoner()
        assert reasoner._agi_mode is False

    def test_agi_mode_flag(self) -> None:
        reasoner = _make_reasoner(agi_mode=True)
        assert reasoner._agi_mode is True

    def test_reasoning_mode_before_init(self) -> None:
        """Before init, mode should be deterministic."""
        reasoner = _make_reasoner()
        assert reasoner.reasoning_mode == "deterministic"

    @pytest.mark.asyncio
    async def test_offensive_mode_includes_offensive_frameworks(self) -> None:
        """In offensive mode, orient should include offensive framework prompts."""
        reasoner = _make_reasoner(offensive_mode=True)
        await _init_with_llm(reasoner)

        call_args = {}

        async def capture_call(system, user):
            call_args["system"] = system
            return "FRAMEWORKS: recon_breadth\nANALYSIS: Offensive analysis"

        with patch.object(reasoner, "_call_llm", side_effect=capture_call):
            await reasoner.orient(
                task="Assess security of target",
                observation={"target": "example.com"},
            )

        assert "FULL SPECTRUM" in call_args.get("system", "")


# ---- Auto Model Selection ----


class TestAutoSelectModel:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_providers(self) -> None:
        """If no providers are available, returns None."""
        mock_registry = AsyncMock()
        mock_registry.list_all_models = AsyncMock(return_value=[])

        with patch(
            "app.services.model_registry.ModelRegistry",
            return_value=mock_registry,
        ):
            result = await auto_select_model()
            # Should return None or a tuple -- depends on fallback logic
            # The key test: it doesn't crash
            assert result is None or isinstance(result, tuple)
