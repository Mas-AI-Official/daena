"""OpenRouter provider adapter — model aggregator.

OpenRouter provides access to hundreds of models via a single
OpenAI-compatible API.  Useful as a fallback when primary
providers are unavailable or rate-limited.
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

_API_BASE = "https://openrouter.ai/api"
_DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct"


class OpenRouterProvider(BaseProvider):
    """OpenRouter aggregator (OpenAI-compatible API)."""

    def __init__(self, api_key: str | None = None, timeout: float = 120.0) -> None:
        super().__init__(ModelProvider.OPENROUTER)
        self._api_key = api_key or get_settings().openrouter_api_key
        self._client = httpx.AsyncClient(
            base_url=_API_BASE,
            timeout=httpx.Timeout(timeout, connect=10.0),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://daena.ai",
                "X-Title": "Daena",
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
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        return LLMResponse(
            content=choice.get("message", {}).get("content", ""),
            model_id=model_id,
            provider=self.provider,
            token_count_input=input_tokens,
            token_count_output=output_tokens,
            cost_usd=0.0,  # OpenRouter returns cost in response headers
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
        """Query OpenRouter for available models (dynamic catalog)."""
        try:
            resp = await self._client.get("/v1/models", timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, httpx.ConnectError):
            logger.warning("openrouter_list_models_failed")
            return []

        models: list[ModelInfo] = []
        for m in data.get("data", [])[:50]:  # cap at 50 to avoid bloat
            pricing = m.get("pricing", {})
            models.append(
                ModelInfo(
                    model_id=m.get("id", ""),
                    provider=self.provider,
                    display_name=m.get("name", ""),
                    context_window=m.get("context_length", 4096),
                    supports_streaming=True,
                    cost_per_1m_input=float(pricing.get("prompt", 0)) * 1_000_000,
                    cost_per_1m_output=float(pricing.get("completion", 0)) * 1_000_000,
                )
            )
        return models

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
