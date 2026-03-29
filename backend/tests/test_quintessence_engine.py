"""Tests for the Quintessence Engine — expert × LLM matrix."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.constants import ModelProvider, RoutingMode
from app.services.council_engine import CouncilEngine, CouncilResult, MemberResponse
from app.services.providers.base import LLMResponse
from app.services.quintessence_engine import (
    ExpertSynthesis,
    QuintessenceEngine,
    QuintessenceResult,
)

# ── Helpers ──────────────────────────────────────────────────

def _make_response(
    content: str,
    model_id: str = "test-model",
    provider: ModelProvider = ModelProvider.OLLAMA,
) -> LLMResponse:
    return LLMResponse(
        content=content,
        model_id=model_id,
        provider=provider,
        token_count_input=10,
        token_count_output=5,
        cost_usd=0.001,
        latency_ms=50,
    )


def _mock_council(synthesis: str = "Expert synthesis") -> MagicMock:
    """Mock CouncilEngine that returns a fixed synthesis."""
    mock = MagicMock(spec=CouncilEngine)
    mock.synthesize = AsyncMock(
        return_value=CouncilResult(
            synthesis=synthesis,
            members=[
                MemberResponse(
                    model_id="m1", provider="ollama",
                    content="raw1", latency_ms=50, cost_usd=0.001,
                ),
            ],
            synthesizer_model="synth",
            agreement_score=0.75,
            total_cost_usd=0.003,
            total_latency_ms=100,
        ),
    )
    return mock


def _mock_llm_service(content: str = "Meta synthesis") -> MagicMock:
    """Mock LLMService for meta-synthesis."""
    from app.services.llm_service import OrchestratedResponse
    from app.services.model_router import ModelCandidate, RoutingDecision

    synth = _make_response(content, "synth-model")
    mock = MagicMock()
    mock.generate = AsyncMock(
        return_value=OrchestratedResponse(
            primary=synth,
            mode=RoutingMode.STANDARD,
            routing_decision=RoutingDecision(
                mode=RoutingMode.STANDARD,
                primary=ModelCandidate(
                    model_id="synth-model",
                    provider=ModelProvider.ANTHROPIC,
                    score=1.0,
                ),
            ),
        ),
    )
    return mock


# ── Tests: empty input ───────────────────────────────────────

@pytest.mark.asyncio
async def test_deliberate_empty_responses() -> None:
    """No responses → error result."""
    engine = QuintessenceEngine(_mock_llm_service(), _mock_council())
    result = await engine.deliberate("Hello?", [])

    assert isinstance(result, QuintessenceResult)
    assert result.metadata.get("error") == "empty_responses"


# ── Tests: expert selection ──────────────────────────────────

def test_select_experts_coding() -> None:
    """CODING intent selects architecture-focused experts."""
    experts = QuintessenceEngine._select_experts("CODING")
    assert "architect" in experts
    assert "security" in experts
    assert "practitioner" in experts
    assert len(experts) <= 5


def test_select_experts_unknown_intent() -> None:
    """Unknown intent falls back to AMBIGUOUS experts."""
    experts = QuintessenceEngine._select_experts("NONEXISTENT")
    assert "researcher" in experts
    assert "practitioner" in experts


def test_select_experts_max_limit() -> None:
    """Expert count is capped."""
    experts = QuintessenceEngine._select_experts("CODING", max_experts=2)
    assert len(experts) == 2


# ── Tests: full deliberation ────────────────────────────────

@pytest.mark.asyncio
async def test_deliberate_success() -> None:
    """Full deliberation with multiple responses and experts."""
    mock_llm = _mock_llm_service("The definitive meta-answer")
    mock_council = _mock_council("Expert perspective")
    engine = QuintessenceEngine(mock_llm, mock_council)

    responses = [
        _make_response("Answer A", "model-a", ModelProvider.OLLAMA),
        _make_response("Answer B", "model-b", ModelProvider.ANTHROPIC),
        _make_response("Answer C", "model-c", ModelProvider.OPENAI),
    ]

    result = await engine.deliberate(
        "Design a secure auth system",
        responses,
        query_intent="CODING",
    )

    assert result.synthesis == "The definitive meta-answer"
    assert len(result.expert_syntheses) > 0
    assert result.metadata["model_count"] == 3
    assert result.metadata["intent"] == "CODING"
    assert result.total_cost_usd > 0
    assert result.confidence > 0


@pytest.mark.asyncio
async def test_deliberate_fallback_on_all_experts_fail() -> None:
    """All experts fail → falls back to plain council synthesis."""
    mock_council = MagicMock(spec=CouncilEngine)
    # First N calls fail (expert syntheses), last call succeeds (fallback)
    mock_council.synthesize = AsyncMock(
        side_effect=[
            RuntimeError("fail"),
            RuntimeError("fail"),
            RuntimeError("fail"),
            CouncilResult(  # fallback council call
                synthesis="Fallback council answer",
                agreement_score=0.5,
                total_cost_usd=0.005,
                total_latency_ms=200,
            ),
        ],
    )

    mock_llm = _mock_llm_service()
    engine = QuintessenceEngine(mock_llm, mock_council)

    result = await engine.deliberate(
        "Query?",
        [_make_response("Answer A")],
        query_intent="AMBIGUOUS",
    )

    assert result.synthesis == "Fallback council answer"
    assert result.metadata.get("fallback") == "council_only"


@pytest.mark.asyncio
async def test_deliberate_meta_synthesis_failure_uses_fallback() -> None:
    """If meta-synthesis LLM call fails, uses concatenated fallback."""
    mock_llm = _mock_llm_service()
    mock_llm.generate = AsyncMock(side_effect=RuntimeError("LLM down"))
    mock_council = _mock_council("Expert view")
    engine = QuintessenceEngine(mock_llm, mock_council)

    responses = [_make_response("A"), _make_response("B")]
    result = await engine.deliberate("Q?", responses, query_intent="SIMPLE")

    # Fallback concatenation includes expert labels
    assert "Perspective" in result.synthesis


# ── Tests: agreement & confidence scoring ────────────────────

def test_expert_agreement_identical() -> None:
    """Identical expert texts → perfect agreement."""
    experts = [
        ExpertSynthesis("a", "A", "Same text here", 0.8, 3, 0.01),
        ExpertSynthesis("b", "B", "Same text here", 0.8, 3, 0.01),
    ]
    score = QuintessenceEngine._score_expert_agreement(experts)
    assert score == 1.0


def test_expert_agreement_different() -> None:
    """Very different experts → low agreement."""
    experts = [
        ExpertSynthesis("a", "A", "alpha beta gamma delta", 0.8, 3, 0.01),
        ExpertSynthesis("b", "B", "one two three four five", 0.8, 3, 0.01),
    ]
    score = QuintessenceEngine._score_expert_agreement(experts)
    assert score < 0.3


def test_confidence_scoring() -> None:
    """Confidence combines agreement, intra-agreement, and coverage."""
    experts = [
        ExpertSynthesis("a", "A", "text", 0.9, 3, 0.01),
        ExpertSynthesis("b", "B", "text", 0.8, 3, 0.01),
        ExpertSynthesis("c", "C", "text", 0.7, 3, 0.01),
    ]
    conf = QuintessenceEngine._compute_confidence(experts, meta_agreement=0.8)
    assert 0.0 < conf <= 1.0


def test_confidence_empty_experts() -> None:
    """No experts → zero confidence."""
    assert QuintessenceEngine._compute_confidence([], 0.5) == 0.0


def test_confidence_full_coverage() -> None:
    """5 experts with high agreement → high confidence."""
    experts = [
        ExpertSynthesis(f"e{i}", f"E{i}", "similar text", 0.9, 3, 0.01)
        for i in range(5)
    ]
    conf = QuintessenceEngine._compute_confidence(experts, meta_agreement=0.9)
    assert conf > 0.8


# ── Tests: formatting ────────────────────────────────────────

def test_format_expert_block() -> None:
    """Expert block includes labels and agreement scores."""
    experts = [
        ExpertSynthesis("arch", "Architect", "Design well", 0.85, 3, 0.01),
        ExpertSynthesis("sec", "Security", "Lock it down", 0.90, 3, 0.01),
    ]
    block = QuintessenceEngine._format_expert_block(experts)

    assert "Architect" in block
    assert "Security" in block
    assert "Design well" in block
    assert "0.85" in block
