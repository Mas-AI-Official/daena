"""Smoke tests for LLM Service orchestration."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.constants import ModelProvider, RoutingMode
from app.services.llm_service import LLMService, OrchestratedResponse
from app.services.model_router import ModelCandidate, RoutingDecision
from app.services.providers.base import (
    GenerateRequest,
    LLMChunk,
    LLMMessage,
    LLMResponse,
)

# ── Fixtures ──────────────────────────────────────────────────

def _make_candidate(
    model_id: str = "test-model",
    provider: ModelProvider = ModelProvider.OLLAMA,
    score: float = 0.8,
) -> ModelCandidate:
    return ModelCandidate(
        model_id=model_id,
        provider=provider,
        score=score,
    )


def _make_decision(
    mode: RoutingMode = RoutingMode.STANDARD,
    primary: ModelCandidate | None = None,
    fallbacks: list[ModelCandidate] | None = None,
    council: list[ModelCandidate] | None = None,
) -> RoutingDecision:
    return RoutingDecision(
        mode=mode,
        primary=primary or _make_candidate(),
        fallback_chain=fallbacks or [],
        council_models=council or [],
    )


def _make_request(content: str = "Hello") -> GenerateRequest:
    return GenerateRequest(
        messages=[LLMMessage(role="user", content=content)],
    )


def _make_response(
    content: str = "Hi there",
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


def _mock_registry(*providers: tuple[ModelProvider, LLMResponse | Exception]) -> MagicMock:
    """Create a mock registry with providers that return specific responses."""
    registry = MagicMock()
    provider_map: dict[ModelProvider, AsyncMock] = {}

    for mp, response_or_error in providers:
        mock_provider = AsyncMock()
        if isinstance(response_or_error, Exception):
            mock_provider.generate.side_effect = response_or_error
        else:
            mock_provider.generate.return_value = response_or_error
        provider_map[mp] = mock_provider

    def get_provider(mp: ModelProvider) -> AsyncMock | None:
        return provider_map.get(mp)

    registry.get_provider = get_provider
    return registry


# ── Tests: Standard generate ──────────────────────────────────

@pytest.mark.asyncio
async def test_generate_standard_success() -> None:
    """Primary model succeeds on first attempt."""
    expected = _make_response("Hello world")
    registry = _mock_registry((ModelProvider.OLLAMA, expected))
    svc = LLMService(registry)

    result = await svc.generate(_make_request(), _make_decision())

    assert isinstance(result, OrchestratedResponse)
    assert result.primary.content == "Hello world"
    assert result.mode == RoutingMode.STANDARD
    assert result.attempts == 1
    assert not result.fallback_used


@pytest.mark.asyncio
async def test_generate_fallback_on_primary_failure() -> None:
    """Primary fails, fallback succeeds."""
    fallback_candidate = _make_candidate(
        model_id="fallback-model",
        provider=ModelProvider.ANTHROPIC,
    )
    primary_error = RuntimeError("Connection refused")
    fallback_response = _make_response("Fallback answer", "fallback-model", ModelProvider.ANTHROPIC)

    registry = _mock_registry(
        (ModelProvider.OLLAMA, primary_error),
        (ModelProvider.ANTHROPIC, fallback_response),
    )
    svc = LLMService(registry)

    decision = _make_decision(fallbacks=[fallback_candidate])
    result = await svc.generate(_make_request(), decision)

    assert result.primary.content == "Fallback answer"
    assert result.attempts == 2
    assert result.fallback_used


@pytest.mark.asyncio
async def test_generate_all_fail_raises() -> None:
    """All providers fail — raises ProviderUnavailableError."""
    from app.core.exceptions import ProviderUnavailableError

    registry = _mock_registry(
        (ModelProvider.OLLAMA, RuntimeError("fail")),
    )
    svc = LLMService(registry)

    with pytest.raises(ProviderUnavailableError, match="failed"):
        await svc.generate(_make_request(), _make_decision())


# ── Tests: Council generate ───────────────────────────────────

@pytest.mark.asyncio
async def test_generate_council_parallel() -> None:
    """COUNCIL mode calls multiple models in parallel."""
    r1 = _make_response("Answer A", "model-a", ModelProvider.OLLAMA)
    r2 = _make_response("Answer B", "model-b", ModelProvider.ANTHROPIC)
    r3 = _make_response("Answer C", "model-c", ModelProvider.OPENAI)

    registry = _mock_registry(
        (ModelProvider.OLLAMA, r1),
        (ModelProvider.ANTHROPIC, r2),
        (ModelProvider.OPENAI, r3),
    )
    svc = LLMService(registry)

    council = [
        _make_candidate("model-a", ModelProvider.OLLAMA),
        _make_candidate("model-b", ModelProvider.ANTHROPIC),
        _make_candidate("model-c", ModelProvider.OPENAI),
    ]
    decision = _make_decision(
        mode=RoutingMode.COUNCIL,
        council=council,
    )

    result = await svc.generate(_make_request(), decision)

    assert result.mode == RoutingMode.COUNCIL
    # Primary + council_responses = all 3 responses
    total_responses = 1 + len(result.council_responses)
    assert total_responses == 3
    assert result.metadata["council_size"] == 3


@pytest.mark.asyncio
async def test_generate_council_partial_failure() -> None:
    """COUNCIL mode handles partial failures gracefully."""
    r1 = _make_response("Answer A", "model-a", ModelProvider.OLLAMA)
    r2 = RuntimeError("Anthropic down")

    registry = _mock_registry(
        (ModelProvider.OLLAMA, r1),
        (ModelProvider.ANTHROPIC, r2),
    )
    svc = LLMService(registry)

    council = [
        _make_candidate("model-a", ModelProvider.OLLAMA),
        _make_candidate("model-b", ModelProvider.ANTHROPIC),
    ]
    decision = _make_decision(
        mode=RoutingMode.COUNCIL,
        council=council,
    )

    result = await svc.generate(_make_request(), decision)

    # Should still succeed with 1 response
    assert result.primary.content == "Answer A"
    assert result.metadata["council_failed"] == 1


# ── Tests: Streaming ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_stream_success() -> None:
    """Streaming yields chunks from provider."""
    chunks = [
        LLMChunk(content="Hello", model_id="m", provider=ModelProvider.OLLAMA, token_index=0),
        LLMChunk(content=" world", model_id="m", provider=ModelProvider.OLLAMA, token_index=1),
        LLMChunk(
            content="", model_id="m", provider=ModelProvider.OLLAMA,
            finish_reason="stop", token_index=2,
        ),
    ]

    mock_provider = AsyncMock()

    async def fake_stream(_req: GenerateRequest) -> AsyncIterator[LLMChunk]:
        for c in chunks:
            yield c

    mock_provider.stream = fake_stream

    registry = MagicMock()
    registry.get_provider = lambda mp: mock_provider if mp == ModelProvider.OLLAMA else None

    svc = LLMService(registry)
    decision = _make_decision()

    collected: list[LLMChunk] = []
    async for chunk in svc.stream(_make_request(), decision):
        collected.append(chunk)

    assert len(collected) == 3
    assert collected[0].content == "Hello"
    assert collected[-1].finish_reason == "stop"


@pytest.mark.asyncio
async def test_stream_fallback_on_start_failure() -> None:
    """If primary stream fails to start, fallback is tried."""
    error_provider = AsyncMock()

    async def failing_stream(_req: GenerateRequest) -> AsyncIterator[LLMChunk]:
        raise ConnectionError("refused")
        yield  # type: ignore[misc]  # make it a generator

    error_provider.stream = failing_stream

    ok_provider = AsyncMock()

    async def ok_stream(_req: GenerateRequest) -> AsyncIterator[LLMChunk]:
        yield LLMChunk(
            content="OK", model_id="fb",
            provider=ModelProvider.ANTHROPIC, finish_reason="stop",
        )

    ok_provider.stream = ok_stream

    registry = MagicMock()

    def get_prov(mp: ModelProvider) -> AsyncMock | None:
        if mp == ModelProvider.OLLAMA:
            return error_provider
        if mp == ModelProvider.ANTHROPIC:
            return ok_provider
        return None

    registry.get_provider = get_prov

    svc = LLMService(registry)
    decision = _make_decision(
        fallbacks=[_make_candidate("fb", ModelProvider.ANTHROPIC)],
    )

    collected: list[LLMChunk] = []
    async for chunk in svc.stream(_make_request(), decision):
        collected.append(chunk)

    assert len(collected) == 1
    assert collected[0].content == "OK"


# ── Tests: Quintessence wiring ───────────────────────────────

@pytest.mark.asyncio
async def test_quintessence_not_wired_falls_back() -> None:
    """QUINTESSENCE without engine wired falls back to standard."""
    expected = _make_response("standard answer")
    registry = _mock_registry((ModelProvider.OLLAMA, expected))
    svc = LLMService(registry)

    decision = _make_decision(mode=RoutingMode.QUINTESSENCE)
    result = await svc.generate(_make_request(), decision)

    assert result.primary.content == "standard answer"
    # Mode stays as STANDARD because fallback was used
    assert result.mode == RoutingMode.STANDARD


@pytest.mark.asyncio
async def test_quintessence_no_council_models_falls_back() -> None:
    """QUINTESSENCE with no council_models falls back to standard."""
    expected = _make_response("standard answer")
    registry = _mock_registry((ModelProvider.OLLAMA, expected))
    svc = LLMService(registry)
    svc.set_quintessence_engine(MagicMock())  # wired but no council models

    decision = _make_decision(mode=RoutingMode.QUINTESSENCE)
    result = await svc.generate(_make_request(), decision)

    assert result.primary.content == "standard answer"


@pytest.mark.asyncio
async def test_quintessence_delegates_to_engine() -> None:
    """QUINTESSENCE delegates to QuintessenceEngine.deliberate()."""
    from dataclasses import dataclass, field

    @dataclass
    class FakeQuintResult:
        synthesis: str = "meta-answer"
        expert_syntheses: list = field(default_factory=list)
        meta_agreement: float = 0.85
        confidence: float = 0.9
        total_cost_usd: float = 0.005
        total_latency_ms: int = 200

    # Two council models
    r1 = _make_response("A", "m-a", ModelProvider.OLLAMA)
    r2 = _make_response("B", "m-b", ModelProvider.ANTHROPIC)
    registry = _mock_registry(
        (ModelProvider.OLLAMA, r1),
        (ModelProvider.ANTHROPIC, r2),
    )
    svc = LLMService(registry)

    mock_engine = AsyncMock()
    mock_engine.deliberate.return_value = FakeQuintResult()
    svc.set_quintessence_engine(mock_engine)

    council = [
        _make_candidate("m-a", ModelProvider.OLLAMA),
        _make_candidate("m-b", ModelProvider.ANTHROPIC),
    ]
    decision = _make_decision(mode=RoutingMode.QUINTESSENCE, council=council)
    result = await svc.generate(_make_request("Design auth"), decision)

    assert result.mode == RoutingMode.QUINTESSENCE
    assert result.primary.content == "meta-answer"
    assert result.metadata["quintessence_confidence"] == 0.9
    assert result.metadata["quintessence_agreement"] == 0.85
    mock_engine.deliberate.assert_called_once()


@pytest.mark.asyncio
async def test_quintessence_engine_failure_degrades_to_council() -> None:
    """If QuintessenceEngine raises, falls back to council result."""
    r1 = _make_response("A", "m-a", ModelProvider.OLLAMA)
    r2 = _make_response("B", "m-b", ModelProvider.ANTHROPIC)
    registry = _mock_registry(
        (ModelProvider.OLLAMA, r1),
        (ModelProvider.ANTHROPIC, r2),
    )
    svc = LLMService(registry)

    mock_engine = AsyncMock()
    mock_engine.deliberate.side_effect = RuntimeError("engine crash")
    svc.set_quintessence_engine(mock_engine)

    council = [
        _make_candidate("m-a", ModelProvider.OLLAMA),
        _make_candidate("m-b", ModelProvider.ANTHROPIC),
    ]
    decision = _make_decision(mode=RoutingMode.QUINTESSENCE, council=council)
    result = await svc.generate(_make_request(), decision)

    # Should degrade to COUNCIL result
    assert result.mode == RoutingMode.COUNCIL
    assert result.primary.content in ("A", "B")


# ── Tests: generate_direct failover model_id remap ────────────

@pytest.mark.asyncio
async def test_generate_direct_resets_model_id_on_cross_provider_failover() -> None:
    """Regression for the Session 11 benchmark crash.

    When the primary provider fails, the fallback provider must receive a
    request with model_id=None (so it picks its own default) rather than
    the primary's model_id. Without this, Groq asking for
    "moonshotai/kimi-k2-instruct" that then fails-over to Gemini causes
    Gemini to build /v1beta/models/moonshotai/kimi-k2-instruct:generateContent
    and 404.
    """
    # Primary = "kimi-k2" on GROQ, which will fail.
    # Fallback = GEMINI, which must NOT receive model_id="kimi-k2".
    primary_error = RuntimeError("groq 404: moonshotai/kimi-k2-instruct")
    fallback_response = _make_response("Fallback OK", "gemini-2.0-flash", ModelProvider.GEMINI)

    groq_mock = AsyncMock()
    groq_mock.generate.side_effect = primary_error

    gemini_mock = AsyncMock()
    gemini_mock.generate.return_value = fallback_response

    registry = MagicMock()

    def get_provider(mp: ModelProvider) -> AsyncMock | None:
        return {ModelProvider.GROQ: groq_mock, ModelProvider.GEMINI: gemini_mock}.get(mp)

    def get_provider_for_model(model_id: str) -> AsyncMock | None:
        if "kimi" in model_id:
            return groq_mock
        return None

    registry.get_provider = get_provider
    registry.get_provider_for_model = get_provider_for_model
    registry.available_providers = [ModelProvider.GROQ, ModelProvider.GEMINI]

    svc = LLMService(registry)

    request = GenerateRequest(
        messages=[LLMMessage(role="user", content="hi")],
        model_id="moonshotai/kimi-k2-instruct",
    )

    # Reset health tracker so GEMINI is available
    from app.services.runtimes.health_tracker import get_health_tracker
    get_health_tracker()._states.clear()

    result = await svc.generate_direct(request)

    # Gemini received the call (failover used).
    assert gemini_mock.generate.await_count == 1
    # The critical assertion: the request sent to Gemini had model_id=None,
    # NOT "moonshotai/kimi-k2-instruct".
    forwarded_req = gemini_mock.generate.await_args.args[0]
    assert forwarded_req.model_id is None, (
        f"Failover must reset model_id to None, got {forwarded_req.model_id!r}. "
        "This was the root cause of Session 11's Gemini 404."
    )
    # Original request object is unchanged.
    assert request.model_id == "moonshotai/kimi-k2-instruct"
    # Response returned.
    assert result.content == "Fallback OK"


@pytest.mark.asyncio
async def test_generate_direct_keeps_model_id_on_primary_success() -> None:
    """Non-failover case: primary keeps its own model_id."""
    primary_response = _make_response("Primary OK", "my-model", ModelProvider.ANTHROPIC)
    mock_primary = AsyncMock()
    mock_primary.generate.return_value = primary_response

    registry = MagicMock()
    registry.get_provider = lambda mp: mock_primary if mp == ModelProvider.ANTHROPIC else None
    registry.get_provider_for_model = lambda mid: mock_primary
    registry.available_providers = [ModelProvider.ANTHROPIC]

    svc = LLMService(registry)
    request = GenerateRequest(
        messages=[LLMMessage(role="user", content="hi")],
        model_id="my-model",
    )

    from app.services.runtimes.health_tracker import get_health_tracker
    get_health_tracker()._states.clear()

    await svc.generate_direct(request)

    forwarded_req = mock_primary.generate.await_args.args[0]
    assert forwarded_req.model_id == "my-model"
