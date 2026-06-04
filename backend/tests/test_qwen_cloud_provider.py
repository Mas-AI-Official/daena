"""Tests for the Qwen Cloud provider (Alibaba Model Studio / DashScope).

All tests mock httpx responses -- no network and no API key required.
Mirrors the OpenAI-compatible request/response shape used by the
Together and vLLM providers.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.core.constants import HealthStatus, ModelProvider
from app.services.model_registry import (
    _PROVIDER_DISPLAY_NAMES,
    _PROVIDER_KINDS,
    _PROVIDER_MAP,
)
from app.services.providers.base import GenerateRequest, LLMMessage
from app.services.providers.qwen_cloud import QwenCloudProvider


# -- Fixtures --


@pytest.fixture
def provider():
    return QwenCloudProvider(api_key="test-key", timeout=5.0)


def _make_request(content: str = "Hello") -> GenerateRequest:
    return GenerateRequest(
        messages=[LLMMessage(role="user", content=content)],
        model_id="qwen-plus",
    )


# -- Provider Tests --


@pytest.mark.asyncio
async def test_generate_success(provider: QwenCloudProvider):
    """generate() returns a valid LLMResponse with token counts and cost."""
    mock_response = httpx.Response(
        200,
        json={
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "model": "qwen-plus",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hi there!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": 4,
                "total_tokens": 16,
            },
        },
        request=httpx.Request("POST", provider._chat_url),
    )

    provider._client = AsyncMock()
    provider._client.post = AsyncMock(return_value=mock_response)

    result = await provider.generate(_make_request())

    assert result.content == "Hi there!"
    assert result.model_id == "qwen-plus"
    assert result.provider == ModelProvider.QWEN_CLOUD
    assert result.token_count_input == 12
    assert result.token_count_output == 4
    assert result.finish_reason == "stop"
    # qwen-plus: 0.40 in / 1.20 out per 1M tokens.
    expected = round((12 / 1_000_000) * 0.40 + (4 / 1_000_000) * 1.20, 8)
    assert result.cost_usd == expected


@pytest.mark.asyncio
async def test_generate_defaults_model_when_unset(provider: QwenCloudProvider):
    """generate() falls back to the default model when model_id is None."""
    mock_response = httpx.Response(
        200,
        json={
            "choices": [
                {"message": {"content": "ok"}, "finish_reason": "stop"}
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        },
        request=httpx.Request("POST", provider._chat_url),
    )
    provider._client = AsyncMock()
    provider._client.post = AsyncMock(return_value=mock_response)

    request = GenerateRequest(messages=[LLMMessage(role="user", content="hi")])
    result = await provider.generate(request)
    assert result.model_id == "qwen-plus"


@pytest.mark.asyncio
async def test_stream_success(provider: QwenCloudProvider):
    """stream() yields LLMChunks from the OpenAI-compatible SSE stream."""

    class MockAsyncLineIterator:
        def __init__(self):
            self.lines = [
                'data: {"choices":[{"delta":{"content":"Hel"},"finish_reason":null}]}',
                'data: {"choices":[{"delta":{"content":"lo"},"finish_reason":null}]}',
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

    chunks = [c async for c in provider.stream(_make_request())]

    assert len(chunks) == 3
    assert chunks[0].content == "Hel"
    assert chunks[0].provider == ModelProvider.QWEN_CLOUD
    assert chunks[1].content == "lo"
    assert chunks[2].finish_reason == "stop"


@pytest.mark.asyncio
async def test_health_check_healthy(provider: QwenCloudProvider):
    """health_check() returns HEALTHY when /models responds 200."""
    mock_response = httpx.Response(
        200,
        json={"data": [{"id": "qwen-plus", "object": "model"}]},
        request=httpx.Request("GET", provider._models_url),
    )
    provider._client = AsyncMock()
    provider._client.get = AsyncMock(return_value=mock_response)

    assert await provider.health_check() == HealthStatus.HEALTHY


@pytest.mark.asyncio
async def test_health_check_unavailable_on_connect_error(provider: QwenCloudProvider):
    """health_check() returns UNAVAILABLE when the endpoint is unreachable."""
    provider._client = AsyncMock()
    provider._client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

    assert await provider.health_check() == HealthStatus.UNAVAILABLE


@pytest.mark.asyncio
async def test_health_check_unavailable_without_key():
    """health_check() short-circuits to UNAVAILABLE when no key is set."""
    provider = QwenCloudProvider(api_key="", timeout=5.0)
    assert await provider.health_check() == HealthStatus.UNAVAILABLE


@pytest.mark.asyncio
async def test_list_models(provider: QwenCloudProvider):
    """list_models() returns the static Qwen Cloud catalog."""
    models = await provider.list_models()
    ids = {m.model_id for m in models}
    assert {"qwen-max", "qwen-plus", "qwen-turbo", "qwen3-coder-plus"} <= ids
    for m in models:
        assert m.provider == ModelProvider.QWEN_CLOUD
        assert m.context_window > 0
        assert m.supports_tools is True


def test_base_url_defaults_to_international_region():
    """Default base URL is the DashScope international compatible-mode endpoint."""
    provider = QwenCloudProvider(api_key="k")
    assert provider._base_url == (
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    )
    assert provider._chat_url.endswith("/chat/completions")
    assert provider._models_url.endswith("/models")


def test_base_url_override_is_trimmed():
    """A custom base URL with a trailing slash is normalised."""
    provider = QwenCloudProvider(
        api_key="k",
        base_url="https://dashscope-us.aliyuncs.com/compatible-mode/v1/",
    )
    assert provider._base_url == (
        "https://dashscope-us.aliyuncs.com/compatible-mode/v1"
    )


def test_registered_in_model_registry_maps():
    """Qwen Cloud must be wired into all three registry maps (no KeyError)."""
    assert ModelProvider.QWEN_CLOUD in _PROVIDER_MAP
    assert ModelProvider.QWEN_CLOUD in _PROVIDER_DISPLAY_NAMES
    assert ModelProvider.QWEN_CLOUD in _PROVIDER_KINDS
    module_path, class_name, config_key = _PROVIDER_MAP[ModelProvider.QWEN_CLOUD]
    assert class_name == "QwenCloudProvider"
    assert config_key == "qwen_cloud_api_key"
    assert _PROVIDER_KINDS[ModelProvider.QWEN_CLOUD] == "cloud"
