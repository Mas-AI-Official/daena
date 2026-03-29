"""OpenAI provider adapter — GPT models.

Uses the Chat Completions API directly via httpx.

Pricing (March 2026):
    GPT-4o-mini: $0.15 / $0.60 per 1M tokens
    GPT-4o:      $2.50 / $10   per 1M tokens
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

_API_BASE = "https://api.openai.com"
_DEFAULT_MODEL = "gpt-4o-mini"

_MODELS: list[dict[str, Any]] = [
    {
        "id": "gpt-4o-mini",
        "name": "GPT-4o Mini",
        "ctx": 128_000,
        "in": 0.15,
        "out": 0.60,
        "tags": ["fast", "cheap"],
    },
    {
        "id": "gpt-4o",
        "name": "GPT-4o",
        "ctx": 128_000,
        "in": 2.50,
        "out": 10.0,
        "tags": ["reasoning", "vision"],
    },
]


class OpenAIProvider(BaseProvider):
    """OpenAI GPT provider via Chat Completions API."""

    def __init__(self, api_key: str | None = None, timeout: float = 120.0) -> None:
        super().__init__(ModelProvider.OPENAI)
        self._api_key = api_key or get_settings().openai_api_key
        self._client = httpx.AsyncClient(
            base_url=_API_BASE,
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
        resp = await self._client.post("/v1/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        model_info = self._find_model(model_id)

        return LLMResponse(
            content=message.get("content", ""),
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
        async with self._client.stream("POST", "/v1/chat/completions", json=payload) as resp:
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
            resp = await self._client.get("/v1/models", timeout=5.0)
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
                supports_vision=True,
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
            cost_per_1m_input=2.5, cost_per_1m_output=10.0,
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
