"""Tests for the Council Engine — synthesis and agreement scoring."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.constants import ModelProvider, RoutingMode
from app.services.council_engine import CouncilEngine, CouncilResult, MemberResponse
from app.services.providers.base import LLMResponse

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


def _mock_llm_service(synthesis_content: str = "Synthesized answer") -> MagicMock:
    """Create a mock LLMService whose generate() returns a synthesis."""
    from app.services.llm_service import OrchestratedResponse
    from app.services.model_router import ModelCandidate, RoutingDecision

    synth_response = _make_response(synthesis_content, "synthesizer")

    mock_svc = MagicMock()
    mock_svc.generate = AsyncMock(
        return_value=OrchestratedResponse(
            primary=synth_response,
            mode=RoutingMode.STANDARD,
            routing_decision=RoutingDecision(
                mode=RoutingMode.STANDARD,
                primary=ModelCandidate(
                    model_id="synthesizer",
                    provider=ModelProvider.OLLAMA,
                    score=1.0,
                ),
            ),
        ),
    )
    return mock_svc


# ── Tests: empty / single response ──────────────────────────

@pytest.mark.asyncio
async def test_synthesize_empty_returns_error() -> None:
    """No responses → error result."""
    engine = CouncilEngine(_mock_llm_service())
    result = await engine.synthesize("Hello?", [])

    assert isinstance(result, CouncilResult)
    assert result.metadata.get("error") == "empty_council"
    assert result.members == []


@pytest.mark.asyncio
async def test_synthesize_single_response_passthrough() -> None:
    """One response → returned directly, no synthesis call."""
    mock_svc = _mock_llm_service()
    engine = CouncilEngine(mock_svc)

    r = _make_response("Only answer", "model-a", ModelProvider.ANTHROPIC)
    result = await engine.synthesize("What is 2+2?", [r])

    assert result.synthesis == "Only answer"
    assert result.agreement_score == 1.0
    assert result.metadata.get("single_response") is True
    assert len(result.members) == 1
    assert result.members[0].model_id == "model-a"
    # LLM service should NOT be called for single response
    mock_svc.generate.assert_not_called()


# ── Tests: multi-response synthesis ──────────────────────────

@pytest.mark.asyncio
async def test_synthesize_multiple_responses() -> None:
    """Multiple responses → calls synthesizer, returns merged result."""
    mock_svc = _mock_llm_service("The best combined answer")
    engine = CouncilEngine(mock_svc)

    responses = [
        _make_response("Answer A about cats", "model-a", ModelProvider.OLLAMA),
        _make_response("Answer B about cats", "model-b", ModelProvider.ANTHROPIC),
        _make_response("Answer C about cats", "model-c", ModelProvider.OPENAI),
    ]

    result = await engine.synthesize("Tell me about cats", responses)

    assert result.synthesis == "The best combined answer"
    assert len(result.members) == 3
    assert result.synthesizer_model == "claude-sonnet-4-20250514"
    assert result.metadata["council_size"] == 3
    assert result.total_cost_usd > 0
    mock_svc.generate.assert_called_once()


@pytest.mark.asyncio
async def test_synthesize_fallback_on_failure() -> None:
    """If synthesis call fails, fallback concatenation is used."""
    mock_svc = _mock_llm_service()
    mock_svc.generate = AsyncMock(side_effect=RuntimeError("LLM down"))
    engine = CouncilEngine(mock_svc)

    responses = [
        _make_response("First answer", "model-a"),
        _make_response("Second answer", "model-b"),
    ]

    result = await engine.synthesize("Query?", responses)

    # Fallback concatenation includes model IDs
    assert "model-a" in result.synthesis
    assert "model-b" in result.synthesis
    assert "First answer" in result.synthesis
    assert "Second answer" in result.synthesis


# ── Tests: agreement scoring ─────────────────────────────────

def test_agreement_single_response() -> None:
    """Single response → perfect agreement."""
    score = CouncilEngine._score_agreement([_make_response("Hello")])
    assert score == 1.0


def test_agreement_identical_responses() -> None:
    """Identical responses → high agreement."""
    r = _make_response("The cat sat on the mat")
    score = CouncilEngine._score_agreement([r, r, r])
    assert score == 1.0


def test_agreement_different_responses() -> None:
    """Very different responses → low agreement."""
    r1 = _make_response("Alpha beta gamma delta epsilon zeta eta")
    r2 = _make_response("One two three four five six seven eight")
    score = CouncilEngine._score_agreement([r1, r2])
    assert score < 0.3


def test_agreement_partial_overlap() -> None:
    """Partially overlapping → mid-range agreement."""
    r1 = _make_response("The quick brown fox jumps over the lazy dog")
    r2 = _make_response("The quick red cat jumps over the sleepy dog")
    score = CouncilEngine._score_agreement([r1, r2])
    assert 0.3 < score < 0.9


# ── Tests: response formatting ───────────────────────────────

def test_system_prompt_has_four_required_sections() -> None:
    """Council judge must output DISAGREEMENT + VERIFICATION + VERDICT + SELF-CRITIQUE.

    Regression test for the Session 5 (2026-04-16) post-verdict self-critique
    pass. The SELF-CRITIQUE section is the output-side counterpart to the
    Stage 6.7 input-side lens router -- it hardens the judge against its
    own priors AFTER it commits to a verdict, allowing a revised verdict
    if the adversarial review surfaces a real flaw.
    """
    from app.services.council_engine import _SYNTHESIS_SYSTEM_PROMPT
    # All four structural sections must be named in the prompt.
    assert "## DISAGREEMENT ANALYSIS" in _SYNTHESIS_SYSTEM_PROMPT
    assert "## VERIFICATION" in _SYNTHESIS_SYSTEM_PROMPT
    assert "## VERDICT" in _SYNTHESIS_SYSTEM_PROMPT
    assert "## SELF-CRITIQUE" in _SYNTHESIS_SYSTEM_PROMPT
    # The revision escape hatch must exist.
    assert "REVISED VERDICT" in _SYNTHESIS_SYSTEM_PROMPT
    # AIME Q15 anchor for future debuggers.
    assert "Q15" in _SYNTHESIS_SYSTEM_PROMPT or "2026-04-12" in _SYNTHESIS_SYSTEM_PROMPT


def test_format_responses_anonymized() -> None:
    """Responses are anonymized (A/B/C) before the judge sees them.

    Prevents the dictator-judge pattern where the judge anchors on its own
    brand or a preferred debater. Regression test for the 2026-04-12 AIME
    Q15 bug.
    """
    responses = [
        _make_response("Answer A", "gpt-4", ModelProvider.OPENAI),
        _make_response("Answer B", "claude-3", ModelProvider.ANTHROPIC),
    ]
    formatted = CouncilEngine._format_responses(responses)

    # Anonymous labels used
    assert "Response A:" in formatted
    assert "Response B:" in formatted
    # Content preserved
    assert "Answer A" in formatted
    assert "Answer B" in formatted
    # Model identities are HIDDEN -- judge must not know who said what
    assert "gpt-4" not in formatted
    assert "claude-3" not in formatted
    assert "OPENAI" not in formatted
    assert "ANTHROPIC" not in formatted


def test_format_responses_anonymized_many() -> None:
    """Anonymization scales past 3 responses (A..Z)."""
    responses = [
        _make_response(f"content-{i}", f"model-{i}", ModelProvider.OLLAMA)
        for i in range(5)
    ]
    formatted = CouncilEngine._format_responses(responses)

    for label in ["A", "B", "C", "D", "E"]:
        assert f"Response {label}:" in formatted
    # No model-N leakage
    for i in range(5):
        assert f"model-{i}" not in formatted


def test_member_response_dataclass() -> None:
    """MemberResponse stores all fields correctly."""
    m = MemberResponse(
        model_id="test",
        provider="ollama",
        content="Hello",
        latency_ms=100,
        cost_usd=0.005,
    )
    assert m.model_id == "test"
    assert m.cost_usd == 0.005
