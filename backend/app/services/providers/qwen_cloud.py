"""Qwen Cloud provider adapter -- Alibaba Cloud Model Studio (DashScope).

Qwen Cloud exposes an OpenAI-compatible Chat Completions API via the
DashScope "compatible-mode" endpoint, so this adapter reuses the same
request/response shape as the OpenAI and Together providers. The only
differences are the base URL (region-selectable) and the model catalog.

Activation is credential-gated: the model registry instantiates this
provider only when ``qwen_cloud_api_key`` is configured, identical to
every other cloud provider. No separate feature flag is required.

Default region is the international (Singapore) endpoint
``https://dashscope-intl.aliyuncs.com/compatible-mode/v1``. Override
with ``QWEN_CLOUD_BASE_URL`` (e.g. the US-Virginia or Beijing region).

Docs: https://www.alibabacloud.com/help/en/model-studio/compatibility-of-openai-with-dashscope
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
import orjson

from app.core.config import get_settings
from app.core.constants import HealthStatus, ModelProvider
from app.core.logging import get_logger
from app.services.providers.base import (
    BaseProvider,
    GenerateRequest,
    LLMChunk,
    LLMResponse,
    ModelInfo,
)

logger = get_logger(__name__)

_DEFAULT_MODEL = "qwen-plus"

# Catalog uses the stable model aliases (qwen-max / qwen-plus /
# qwen-turbo) so it does not go stale as Alibaba rolls dated
# snapshots, plus one coding-specialised model. Prices are indicative
# international-region USD list prices as of 2026-06 and are used only
# for best-effort cost tracking; confirm current pricing in the
# Model Studio console before relying on the figures.
_MODELS: list[dict[str, Any]] = [
    {
        "id": "qwen-max",
        "name": "Qwen Max",
        "ctx": 32_768,
        "in": 1.60,
        "out": 6.40,
        "tags": ["flagship", "reasoning", "qwen", "cloud"],
    },
    {
        "id": "qwen-plus",
        "name": "Qwen Plus",
        "ctx": 131_072,
        "in": 0.40,
        "out": 1.20,
        "tags": ["balanced", "qwen", "cloud"],
    },
    {
        "id": "qwen-turbo",
        "name": "Qwen Turbo",
        "ctx": 1_000_000,
        "in": 0.05,
        "out": 0.20,
        "tags": ["fast", "cheapest", "long-context", "qwen", "cloud"],
    },
    {
        "id": "qwen3-coder-plus",
        "name": "Qwen3 Coder Plus",
        "ctx": 262_144,
        "in": 1.00,
        "out": 5.00,
        "tags": ["coding", "qwen", "cloud"],
    },
]


class QwenCloudProvider(BaseProvider):
    """Qwen Cloud provider (OpenAI-compatible DashScope API)."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        super().__init__(ModelProvider.QWEN_CLOUD)
        settings = get_settings()
        self._api_key = api_key or settings.qwen_cloud_api_key
        self._base_url = (base_url or settings.qwen_cloud_base_url).rstrip("/")
        # Fully-qualified URLs avoid httpx base_url path-merge ambiguity
        # for a base that already carries the /compatible-mode/v1 path.
        self._chat_url = f"{self._base_url}/chat/completions"
        self._models_url = f"{self._base_url}/models"
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=10.0),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )

    async def generate(self, request: GenerateRequest) -> LLMResponse:
        model_id = request.model_id or _DEFAULT_MODEL
        start = self._start_timer()

        payload = self._build_payload(request, model_id, stream=False)
        resp = await self._client.post(self._chat_url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        choice = data.get("choices", [{}])[0]
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        model_info = self._find_model(model_id)

        return LLMResponse(
            content=choice.get("message", {}).get("content", ""),
            model_id=model_id,
            provider=self.provider,
            token_count_input=input_tokens,
            token_count_output=output_tokens,
            cost_usd=self._compute_cost(model_info, input_tokens, output_tokens),
            latency_ms=self._elapsed_ms(start),
            finish_reason=choice.get("finish_reason", "stop"),
            raw=data,
        )

    async def stream(self, request: GenerateRequest) -> AsyncIterator[LLMChunk]:
        model_id = request.model_id or _DEFAULT_MODEL
        payload = self._build_payload(request, model_id, stream=True)

        token_index = 0
        async with self._client.stream("POST", self._chat_url, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                raw = line[6:]
                if raw == "[DONE]":
                    break
                chunk = orjson.loads(raw)
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content", "")
                finish = chunk.get("choices", [{}])[0].get("finish_reason")

                if content or finish:
                    yield LLMChunk(
                        content=content or "",
                        model_id=model_id,
                        provider=self.provider,
                        finish_reason=finish,
                        token_index=token_index,
                    )
                    token_index += 1

    async def health_check(self) -> HealthStatus:
        if not self._api_key:
            self._healthy = HealthStatus.UNAVAILABLE
            return self._healthy
        try:
            resp = await self._client.get(self._models_url, timeout=5.0)
            self._healthy = (
                HealthStatus.HEALTHY if resp.status_code == 200 else HealthStatus.DEGRADED
            )
        except (httpx.ConnectError, httpx.TimeoutException):
            self._healthy = HealthStatus.UNAVAILABLE
        return self._healthy

    async def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(
                model_id=m["id"],
                provider=self.provider,
                display_name=m["name"],
                context_window=m["ctx"],
                supports_streaming=True,
                supports_tools=True,
                cost_per_1m_input=m["in"],
                cost_per_1m_output=m["out"],
                tags=m["tags"],
            )
            for m in _MODELS
        ]

    def _find_model(self, model_id: str) -> ModelInfo:
        for m in _MODELS:
            if m["id"] == model_id:
                return ModelInfo(
                    model_id=m["id"],
                    provider=self.provider,
                    cost_per_1m_input=m["in"],
                    cost_per_1m_output=m["out"],
                )
        return ModelInfo(
            model_id=model_id, provider=self.provider,
            cost_per_1m_input=0.40, cost_per_1m_output=1.20,
        )

    @staticmethod
    def _build_payload(
        request: GenerateRequest, model_id: str, *, stream: bool
    ) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        for msg in request.messages:
            messages.append({"role": msg.role, "content": msg.content})

        payload: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "stream": stream,
        }
        if request.stop_sequences:
            payload["stop"] = request.stop_sequences
        return payload

    async def close(self) -> None:
        await self._client.aclose()
