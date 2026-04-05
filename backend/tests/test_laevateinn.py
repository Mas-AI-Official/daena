"""Tests for Laevateinn v2 cognitive pipeline.

Tests all stages: DCE, DCS, AMD, RDE, Validation, Delivery, and Pipeline.
Uses mock LLM service for unit tests (no real model calls).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.laevateinn.comprehension import DeepComprehensionEngine
from app.services.laevateinn.compute_scaler import DynamicComputeScaler
from app.services.laevateinn.debate import AdversarialModelDebate
from app.services.laevateinn.delivery import JobsDeliveryEngine
from app.services.laevateinn.depth_engine import RecursiveDepthEngine
from app.services.laevateinn.pipeline import LaevateinnPipeline
from app.services.laevateinn.types import (
    BloomLevel,
    CognitiveSystem,
    ComprehensionResult,
    ComputeProfile,
    DepthResult,
    Difficulty,
    Interpretation,
    ValidationResult,
)
from app.services.laevateinn.validation import ValidationGauntlet


# ── Fixtures ────────────────────────────────────────────────────

@dataclass
class FakeLLMResponse:
    content: str
    model_id: str = "test-model"
    provider: str = "OLLAMA"
    token_count_input: int = 100
    token_count_output: int = 200
    cost_usd: float = 0.0
    latency_ms: int = 50
    finish_reason: str = "stop"
    raw: dict = field(default_factory=dict)


def make_mock_llm(responses: list[str] | None = None) -> MagicMock:
    """Create a mock LLM service that returns predefined responses."""
    llm = MagicMock()
    if responses is None:
        responses = ["This is a test answer."]

    call_count = 0

    async def fake_generate_direct(request):
        nonlocal call_count
        idx = min(call_count, len(responses) - 1)
        call_count += 1
        return FakeLLMResponse(content=responses[idx], model_id=request.model_id or "test-model")

    llm.generate_direct = AsyncMock(side_effect=fake_generate_direct)
    return llm


# ══════════════════════════════════════════════════════════════
# Stage 1: Deep Comprehension Engine
# ══════════════════════════════════════════════════════════════

class TestDeepComprehensionEngine:
    """Test DCE heuristic mode (no LLM calls)."""

    @pytest.fixture
    def dce(self) -> DeepComprehensionEngine:
        return DeepComprehensionEngine()

    @pytest.mark.asyncio
    async def test_basic_comprehension(self, dce: DeepComprehensionEngine):
        result = await dce.comprehend("What is Python?")
        assert result.original_query == "What is Python?"
        assert result.compressed_query  # Not empty
        assert result.bloom_level == BloomLevel.REMEMBER
        assert len(result.interpretations) >= 1

    @pytest.mark.asyncio
    async def test_feynman_compress_short_query(self, dce: DeepComprehensionEngine):
        result = await dce.comprehend("Fix the bug")
        assert len(result.compressed_query.split()) <= 15

    @pytest.mark.asyncio
    async def test_musk_noise_removal(self, dce: DeepComprehensionEngine):
        result = await dce.comprehend(
            "Please could you kindly help me understand how Python works?"
        )
        # Noise words should be stripped
        assert "please" not in result.noise_eliminated.lower()
        assert "kindly" not in result.noise_eliminated.lower()

    @pytest.mark.asyncio
    async def test_tesla_resonance_how_question(self, dce: DeepComprehensionEngine):
        result = await dce.comprehend("How do I implement authentication?")
        assert "best approach" in result.real_question.lower() or "implement" in result.real_question.lower()

    @pytest.mark.asyncio
    async def test_tesla_resonance_not_working(self, dce: DeepComprehensionEngine):
        result = await dce.comprehend("My database is not working")
        assert "diagnose" in result.real_question.lower() or "fix" in result.real_question.lower()

    @pytest.mark.asyncio
    async def test_polya_decompose_compound(self, dce: DeepComprehensionEngine):
        result = await dce.comprehend(
            "Create the user model and then build the API endpoint"
        )
        assert len(result.sub_questions) >= 2

    @pytest.mark.asyncio
    async def test_polya_decompose_simple(self, dce: DeepComprehensionEngine):
        result = await dce.comprehend("What is Python?")
        assert len(result.sub_questions) == 1

    @pytest.mark.asyncio
    async def test_surface_assumptions_why(self, dce: DeepComprehensionEngine):
        result = await dce.comprehend("Why did the deployment fail?")
        assert any("assumes" in a.lower() for a in result.hidden_assumptions)

    @pytest.mark.asyncio
    async def test_surface_assumptions_binary(self, dce: DeepComprehensionEngine):
        result = await dce.comprehend("Should I use PostgreSQL or MongoDB?")
        assert any("binary" in a.lower() for a in result.hidden_assumptions)

    @pytest.mark.asyncio
    async def test_bloom_remember(self, dce: DeepComprehensionEngine):
        result = await dce.comprehend("What is a Python list?")
        assert result.bloom_level == BloomLevel.REMEMBER

    @pytest.mark.asyncio
    async def test_bloom_create(self, dce: DeepComprehensionEngine):
        result = await dce.comprehend("Design an authentication system")
        assert result.bloom_level == BloomLevel.CREATE

    @pytest.mark.asyncio
    async def test_bloom_analyze(self, dce: DeepComprehensionEngine):
        result = await dce.comprehend("Compare PostgreSQL and MongoDB")
        assert result.bloom_level == BloomLevel.ANALYZE

    @pytest.mark.asyncio
    async def test_bloom_evaluate(self, dce: DeepComprehensionEngine):
        result = await dce.comprehend("Should I use React or Vue?")
        assert result.bloom_level == BloomLevel.EVALUATE

    @pytest.mark.asyncio
    async def test_ach_heuristic_ambiguous(self, dce: DeepComprehensionEngine):
        result = await dce.comprehend("Fix it")
        # Should detect ambiguous reference
        assert any("ambiguous" in i.text.lower() or "ambiguous" in i.reasoning.lower()
                    for i in result.interpretations)

    @pytest.mark.asyncio
    async def test_ach_heuristic_debug(self, dce: DeepComprehensionEngine):
        result = await dce.comprehend("Debug the error in the login flow")
        assert any("debug" in i.reasoning.lower() for i in result.interpretations)

    @pytest.mark.asyncio
    async def test_processing_time_tracked(self, dce: DeepComprehensionEngine):
        result = await dce.comprehend("Simple query")
        assert result.processing_time_ms >= 0


# ══════════════════════════════════════════════════════════════
# Stage 2: Dynamic Compute Scaler
# ══════════════════════════════════════════════════════════════

class TestDynamicComputeScaler:

    @pytest.fixture
    def dcs(self) -> DynamicComputeScaler:
        return DynamicComputeScaler()

    def _make_comprehension(
        self,
        bloom: BloomLevel = BloomLevel.UNDERSTAND,
        interpretations: int = 1,
        sub_questions: int = 1,
    ) -> ComprehensionResult:
        return ComprehensionResult(
            original_query="test",
            compressed_query="test",
            sub_questions=["q"] * sub_questions,
            hidden_assumptions=[],
            noise_eliminated="test",
            real_question="test",
            interpretations=[
                Interpretation(text="t", probability=0.5, reasoning="r")
            ] * interpretations,
            bloom_level=bloom,
        )

    def test_trivial_query(self, dcs: DynamicComputeScaler):
        comp = self._make_comprehension(BloomLevel.REMEMBER)
        profile = dcs.scale(comp, "SIMPLE", available_models=3)
        assert profile.difficulty == Difficulty.TRIVIAL
        assert profile.system == CognitiveSystem.SYSTEM_1
        assert profile.num_models == 1
        assert profile.recursion_depth == 0

    def test_hard_query(self, dcs: DynamicComputeScaler):
        comp = self._make_comprehension(
            BloomLevel.ANALYZE, interpretations=4, sub_questions=3,
        )
        profile = dcs.scale(comp, "ANALYSIS", available_models=5)
        assert profile.difficulty in (Difficulty.HARD, Difficulty.BRUTAL)
        assert profile.system == CognitiveSystem.SYSTEM_2
        assert profile.num_models >= 3

    def test_brutal_query(self, dcs: DynamicComputeScaler):
        comp = self._make_comprehension(
            BloomLevel.CREATE, interpretations=5, sub_questions=4,
        )
        profile = dcs.scale(comp, "MULTI_STEP", available_models=5)
        assert profile.difficulty == Difficulty.BRUTAL
        assert profile.amd_rounds >= 2

    def test_force_difficulty(self, dcs: DynamicComputeScaler):
        comp = self._make_comprehension(BloomLevel.REMEMBER)
        profile = dcs.scale(
            comp, "SIMPLE", available_models=3,
            force_difficulty=Difficulty.BRUTAL,
        )
        assert profile.difficulty == Difficulty.BRUTAL

    def test_models_capped_by_available(self, dcs: DynamicComputeScaler):
        comp = self._make_comprehension(BloomLevel.CREATE, interpretations=5, sub_questions=4)
        profile = dcs.scale(comp, "MULTI_STEP", available_models=2)
        assert profile.num_models <= 2

    def test_kahneman_system1_for_remember(self, dcs: DynamicComputeScaler):
        comp = self._make_comprehension(BloomLevel.REMEMBER)
        profile = dcs.scale(comp, "SIMPLE", available_models=1)
        assert profile.system == CognitiveSystem.SYSTEM_1

    def test_kahneman_system2_for_create(self, dcs: DynamicComputeScaler):
        comp = self._make_comprehension(BloomLevel.CREATE)
        profile = dcs.scale(comp, "CODING", available_models=3)
        assert profile.system == CognitiveSystem.SYSTEM_2


# ══════════════════════════════════════════════════════════════
# Stage 3: Adversarial Model Debate
# ══════════════════════════════════════════════════════════════

class TestAdversarialModelDebate:

    @pytest.mark.asyncio
    async def test_single_model_no_debate(self):
        llm = make_mock_llm(["This is the answer."])
        amd = AdversarialModelDebate(llm)
        compute = ComputeProfile(
            difficulty=Difficulty.STANDARD,
            system=CognitiveSystem.SYSTEM_1,
            num_models=1, recursion_depth=0,
            validation_level="none", amd_rounds=0,
            target_latency_ms=500,
        )
        result = await amd.debate("What is Python?", ["model-a"], compute)
        assert result.winner_answer == "This is the answer."
        assert result.winner_model == "model-a"

    @pytest.mark.asyncio
    async def test_two_models_quick_debate(self):
        llm = make_mock_llm([
            "Answer from model A",
            "Answer from model B",
        ])
        amd = AdversarialModelDebate(llm)
        compute = ComputeProfile(
            difficulty=Difficulty.HARD,
            system=CognitiveSystem.SYSTEM_2,
            num_models=2, recursion_depth=0,
            validation_level="full_gauntlet", amd_rounds=1,
            target_latency_ms=15000,
        )
        result = await amd.debate(
            "Compare React vs Vue", ["model-a", "model-b"], compute,
        )
        assert result.winner_answer  # Has content
        assert len(result.all_answers) == 2

    @pytest.mark.asyncio
    async def test_zero_amd_rounds_returns_single(self):
        llm = make_mock_llm(["Direct answer"])
        amd = AdversarialModelDebate(llm)
        compute = ComputeProfile(
            difficulty=Difficulty.TRIVIAL,
            system=CognitiveSystem.SYSTEM_1,
            num_models=2, recursion_depth=0,
            validation_level="none", amd_rounds=0,
            target_latency_ms=500,
        )
        result = await amd.debate("Hello", ["model-a", "model-b"], compute)
        assert result.winner_answer == "Direct answer"


# ══════════════════════════════════════════════════════════════
# Stage 4: Recursive Depth Engine
# ══════════════════════════════════════════════════════════════

class TestRecursiveDepthEngine:

    @pytest.mark.asyncio
    async def test_zero_depth_passthrough(self):
        llm = make_mock_llm()
        rde = RecursiveDepthEngine(llm)
        compute = ComputeProfile(
            difficulty=Difficulty.TRIVIAL,
            system=CognitiveSystem.SYSTEM_1,
            num_models=1, recursion_depth=0,
            validation_level="none", amd_rounds=0,
            target_latency_ms=500,
        )
        result = await rde.recursive_solve(
            "What is Python?", "Python is a language.", compute,
            model_id="test-model",
        )
        assert result.final_answer == "Python is a language."
        assert result.depth_used == 0
        assert result.confidence == 0.7

    @pytest.mark.asyncio
    async def test_single_depth_verification(self):
        llm = make_mock_llm([
            "Q: When was Python created?\nQ: Who created Python?",  # verification questions
            "Python was created in 1991",  # independent answer 1
            "Guido van Rossum created Python",  # independent answer 2
            "No significant issues found",  # self-critique (if needed)
        ])
        rde = RecursiveDepthEngine(llm)
        compute = ComputeProfile(
            difficulty=Difficulty.STANDARD,
            system=CognitiveSystem.SYSTEM_2,
            num_models=1, recursion_depth=1,
            validation_level="feynman_only", amd_rounds=0,
            target_latency_ms=3000,
        )
        result = await rde.recursive_solve(
            "Tell me about Python",
            "Python is a programming language created by Guido.",
            compute,
            model_id="test-model",
        )
        assert result.depth_used >= 1
        assert result.final_answer  # Has content


# ══════════════════════════════════════════════════════════════
# Stage 5: Validation Gauntlet
# ══════════════════════════════════════════════════════════════

class TestValidationGauntlet:

    @pytest.fixture
    def gauntlet(self) -> ValidationGauntlet:
        return ValidationGauntlet()

    @pytest.mark.asyncio
    async def test_none_validation_level(self, gauntlet: ValidationGauntlet):
        compute = ComputeProfile(
            difficulty=Difficulty.TRIVIAL,
            system=CognitiveSystem.SYSTEM_1,
            num_models=1, recursion_depth=0,
            validation_level="none", amd_rounds=0,
            target_latency_ms=500,
        )
        result = await gauntlet.validate("q", "answer", compute=compute)
        assert result.confidence == 0.5

    @pytest.mark.asyncio
    async def test_feynman_only(self, gauntlet: ValidationGauntlet):
        compute = ComputeProfile(
            difficulty=Difficulty.STANDARD,
            system=CognitiveSystem.SYSTEM_2,
            num_models=1, recursion_depth=1,
            validation_level="feynman_only", amd_rounds=0,
            target_latency_ms=3000,
        )
        result = await gauntlet.validate(
            "What is Python?",
            "Python is a high-level programming language. It is widely used.",
            compute=compute,
        )
        assert result.confidence >= 0.5

    @pytest.mark.asyncio
    async def test_popper_detects_absolutes(self, gauntlet: ValidationGauntlet):
        result = await gauntlet.validate(
            "Is Python good?",
            "Python is always the best choice for every project.",
        )
        assert len(result.popper_falsifications) >= 2  # "always" and "best"

    @pytest.mark.asyncio
    async def test_temporal_detects_dates(self, gauntlet: ValidationGauntlet):
        result = await gauntlet.validate(
            "What is the latest Python?",
            "As of 2024, the latest Python version is 3.12.",
        )
        assert not result.temporal_valid

    @pytest.mark.asyncio
    async def test_hacker_detects_sql(self, gauntlet: ValidationGauntlet):
        result = await gauntlet.validate(
            "How to query the database?",
            "Use SQL queries to fetch user input from the database.",
        )
        assert any("SQL" in c or "injection" in c for c in result.hacker_challenges)

    @pytest.mark.asyncio
    async def test_cove_from_depth_result(self, gauntlet: ValidationGauntlet):
        depth = DepthResult(
            final_answer="test", depth_used=1, max_depth=1,
            confidence=0.95, inconsistencies_found=[],
        )
        result = await gauntlet.validate("q", "answer", depth_result=depth)
        assert result.cove_verified is True


# ══════════════════════════════════════════════════════════════
# Stage 6: Jobs Delivery Engine
# ══════════════════════════════════════════════════════════════

class TestJobsDeliveryEngine:

    @pytest.fixture
    def delivery(self) -> JobsDeliveryEngine:
        return JobsDeliveryEngine()

    def test_removes_hedges(self, delivery: JobsDeliveryEngine):
        result = delivery.deliver(
            "I think maybe Python is probably good.",
            "Is Python good?",
        )
        assert "I think" not in result.response
        assert "maybe" not in result.response

    def test_extracts_key_points(self, delivery: JobsDeliveryEngine):
        result = delivery.deliver(
            "1. Python is interpreted.\n2. Python has dynamic typing.\n3. Python supports OOP.",
            "Tell me about Python",
        )
        assert len(result.key_points) >= 2

    def test_predicts_followups_what(self, delivery: JobsDeliveryEngine):
        result = delivery.deliver(
            "Python is a programming language.",
            "What is Python?",
        )
        assert len(result.speculative_followups) == 3
        assert any("use" in f.lower() or "practice" in f.lower()
                    for f in result.speculative_followups)

    def test_predicts_followups_debug(self, delivery: JobsDeliveryEngine):
        result = delivery.deliver(
            "Check the error logs.",
            "Fix the bug in authentication",
        )
        assert any("prevent" in f.lower() for f in result.speculative_followups)

    def test_confidence_aggregation(self, delivery: JobsDeliveryEngine):
        validation = ValidationResult(passed=True, confidence=0.8)
        depth = DepthResult(
            final_answer="test", depth_used=1, max_depth=1, confidence=0.9,
        )
        result = delivery.deliver(
            "Answer", "Question",
            validation=validation, depth=depth,
        )
        # Should be between validation and depth confidence
        assert 0.7 <= result.confidence_score <= 1.0

    def test_format_type_concise_for_remember(self, delivery: JobsDeliveryEngine):
        comp = ComprehensionResult(
            original_query="What is X?",
            compressed_query="What is X?",
            sub_questions=["What is X?"],
            hidden_assumptions=[],
            noise_eliminated="What is X?",
            real_question="What is X?",
            interpretations=[],
            bloom_level=BloomLevel.REMEMBER,
        )
        result = delivery.deliver("X is Y.", "What is X?", comprehension=comp)
        assert result.format_type == "concise"

    def test_format_type_creative_for_create(self, delivery: JobsDeliveryEngine):
        comp = ComprehensionResult(
            original_query="Design a system",
            compressed_query="Design a system",
            sub_questions=["Design a system"],
            hidden_assumptions=[],
            noise_eliminated="Design a system",
            real_question="Design a system",
            interpretations=[],
            bloom_level=BloomLevel.CREATE,
        )
        result = delivery.deliver("Here is the design.", "Design a system", comprehension=comp)
        assert result.format_type == "creative"


# ══════════════════════════════════════════════════════════════
# Full Pipeline Integration
# ══════════════════════════════════════════════════════════════

class TestLaevateinnPipeline:

    @pytest.mark.asyncio
    async def test_trivial_pipeline(self):
        llm = make_mock_llm(["Python is a programming language."])
        pipeline = LaevateinnPipeline(llm)
        trace = await pipeline.process(
            "What is Python?",
            ["test-model"],
            intent_type="SIMPLE",
            force_difficulty=Difficulty.TRIVIAL,
        )
        assert "dce" in trace.stages_executed
        assert "dcs" in trace.stages_executed
        assert trace.compute_profile.difficulty == Difficulty.TRIVIAL
        assert trace.debate is not None

    @pytest.mark.asyncio
    async def test_quick_answer(self):
        llm = make_mock_llm(["Quick answer."])
        pipeline = LaevateinnPipeline(llm)
        result = await pipeline.quick_answer(
            "What time is it?", "test-model",
        )
        assert result.response == "Quick answer."
        assert result.confidence_score > 0

    @pytest.mark.asyncio
    async def test_pipeline_skip_stages(self):
        llm = make_mock_llm(["Answer."])
        pipeline = LaevateinnPipeline(llm)
        trace = await pipeline.process(
            "Test query",
            ["test-model"],
            skip_stages={"rde", "validation"},
        )
        assert "rde" not in trace.stages_executed
        assert "validation" not in trace.stages_executed

    @pytest.mark.asyncio
    async def test_pipeline_trace_has_latency(self):
        llm = make_mock_llm(["Answer."])
        pipeline = LaevateinnPipeline(llm)
        trace = await pipeline.process(
            "Test", ["test-model"], force_difficulty=Difficulty.TRIVIAL,
        )
        assert trace.total_latency_ms >= 0

    @pytest.mark.asyncio
    async def test_pipeline_empty_models(self):
        llm = make_mock_llm()
        pipeline = LaevateinnPipeline(llm)
        trace = await pipeline.process(
            "Test", [],
            skip_stages={"amd"},  # Skip AMD since no models
        )
        assert trace.debate is None  # No debate without models
