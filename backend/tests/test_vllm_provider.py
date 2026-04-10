"""Tests for the vLLM provider and runtime adapter.

All tests mock httpx responses -- no running vLLM instance required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.constants import HealthStatus, ModelProvider
from app.services.providers.base import GenerateRequest, LLMMessage
from app.services.providers.vllm import VLLMProvider
from app.services.runtimes.adapters.vllm_adapter import VLLMRuntimeAdapter
from app.services.runtimes.base_adapter import RuntimeStatus


# -- Fixtures --


@pytest.fixture
def provider():
    return VLLMProvider(base_url="http://localhost:8100/v1", timeout=5.0)


@pytest.fixture
def adapter():
    return VLLMRuntimeAdapter(base_url="http://localhost:8100/v1")


def _make_request(content: str = "Hello") -> GenerateRequest:
    return GenerateRequest(
        messages=[LLMMessage(role="user", content=content)],
        model_id="meta-llama/Llama-3.1-8B-Instruct",
    )


# -- Provider Tests --


@pytest.mark.asyncio
async def test_generate_success(provider: VLLMProvider):
    """generate() returns a valid LLMResponse from vLLM."""
    mock_response = httpx.Response(
        200,
        json={
            "id": "cmpl-123",
            "object": "chat.completion",
            "model": "meta-llama/Llama-3.1-8B-Instruct",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello! How can I help?"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 7,
                "total_tokens": 17,
            },
        },
        request=httpx.Request("POST", "http://localhost:8100/v1/chat/completions"),
    )

    provider._client = AsyncMock()
    provider._client.post = AsyncMock(return_value=mock_response)

    request = _make_request()
    result = await provider.generate(request)

    assert result.content == "Hello! How can I help?"
    assert result.model_id == "meta-llama/Llama-3.1-8B-Instruct"
    assert result.provider == ModelProvider.VLLM
    assert result.token_count_input == 10
    assert result.token_count_output == 7
    assert result.cost_usd == 0.0
    assert result.finish_reason == "stop"


@pytest.mark.asyncio
async def test_stream_success(provider: VLLMProvider):
    """stream() yields LLMChunks from vLLM SSE responses."""

    class MockAsyncLineIterator:
        def __init__(self):
            self.lines = [
                'data: {"choices":[{"delta":{"content":"Hello"},"finish_reason":null}]}',
                'data: {"choices":[{"delta":{"content":" world"},"finish_reason":null}]}',
                'data: {"choices":[{"delta":{"content":""},"finish_reason":"stop"}]}',
                "data: [DONE]",
            ]
            self.index = 0

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.index >= len(self.lines):
                raise StopAsyncIteration
            line = self.lines[self.index]
            self.index += 1
            return line

    class MockStreamResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def aiter_lines(self):
            return MockAsyncLineIterator()

    class MockStreamCM:
        async def __aenter__(self):
            return MockStreamResponse()

        async def __aexit__(self, *args):
            pass

    provider._client = MagicMock()
    provider._client.stream = MagicMock(return_value=MockStreamCM())

    request = _make_request()
    chunks = []
    async for chunk in provider.stream(request):
        chunks.append(chunk)

    assert len(chunks) == 3
    assert chunks[0].content == "Hello"
    assert chunks[0].provider == ModelProvider.VLLM
    assert chunks[1].content == " world"
    assert chunks[2].finish_reason == "stop"


@pytest.mark.asyncio
async def test_health_check_online(provider: VLLMProvider):
    """health_check() returns HEALTHY when vLLM has models loaded."""
    mock_response = httpx.Response(
        200,
        json={
            "data": [
                {"id": "meta-llama/Llama-3.1-8B-Instruct", "object": "model"}
            ]
        },
        request=httpx.Request("GET", "http://localhost:8100/v1/models"),
    )

    provider._client = AsyncMock()
    provider._client.get = AsyncMock(return_value=mock_response)

    status = await provider.health_check()
    assert status == HealthStatus.HEALTHY


@pytest.mark.asyncio
async def test_health_check_offline(provider: VLLMProvider):
    """health_check() returns UNAVAILABLE when vLLM is unreachable."""
    provider._client = AsyncMock()
    provider._client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

    status = await provider.health_check()
    assert status == HealthStatus.UNAVAILABLE


@pytest.mark.asyncio
async def test_list_models(provider: VLLMProvider):
    """list_models() parses the OpenAI-compatible /v1/models response."""
    mock_response = httpx.Response(
        200,
        json={
            "data": [
                {
                    "id": "meta-llama/Llama-3.1-8B-Instruct",
                    "object": "model",
                    "max_model_len": 131072,
                },
                {
                    "id": "mistralai/Mistral-7B-Instruct-v0.3",
                    "object": "model",
                    "max_model_len": 32768,
                },
            ]
        },
        request=httpx.Request("GET", "http://localhost:8100/v1/models"),
    )

    provider._client = AsyncMock()
    provider._client.get = AsyncMock(return_value=mock_response)

    models = await provider.list_models()
    assert len(models) == 2
    assert models[0].model_id == "meta-llama/Llama-3.1-8B-Instruct"
    assert models[0].provider == ModelProvider.VLLM
    assert models[0].context_window == 131072
    assert models[0].cost_per_1m_input == 0.0
    assert "vllm" in models[0].tags
    assert models[1].model_id == "mistralai/Mistral-7B-Instruct-v0.3"
    assert models[1].context_window == 32768


# -- Adapter Tests --


@pytest.mark.asyncio
async def test_vllm_adapter_capabilities(adapter: VLLMRuntimeAdapter):
    """Adapter reports high capability scores for GPU inference."""
    caps = await adapter.get_capabilities()
    assert caps.complex_reasoning == 9.0
    assert caps.code_generation == 8.0
    assert caps.data_analysis == 8.0
    assert caps.cost_per_1k_tokens == 0.0
    assert caps.browser_automation == 0.0


@pytest.mark.asyncio
async def test_vllm_adapter_check_installed_offline(adapter: VLLMRuntimeAdapter):
    """check_installed() returns False when vLLM is unreachable."""
    adapter._client = AsyncMock()
    adapter._client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

    result = await adapter.check_installed()
    assert result is False


@pytest.mark.asyncio
async def test_vllm_adapter_check_health_online(adapter: VLLMRuntimeAdapter):
    """check_health() returns ONLINE when vLLM responds with models."""
    mock_response = httpx.Response(
        200,
        json={
            "data": [
                {"id": "meta-llama/Llama-3.1-8B-Instruct", "object": "model"}
            ]
        },
        request=httpx.Request("GET", "http://localhost:8100/v1/models"),
    )

    adapter._client = AsyncMock()
    adapter._client.get = AsyncMock(return_value=mock_response)

    status = await adapter.check_health()
    assert status == RuntimeStatus.ONLINE


@pytest.mark.asyncio
async def test_vllm_adapter_check_health_offline(adapter: VLLMRuntimeAdapter):
    """check_health() returns OFFLINE when vLLM is unreachable."""
    adapter._client = AsyncMock()
    adapter._client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

    status = await adapter.check_health()
    assert status == RuntimeStatus.OFFLINE
