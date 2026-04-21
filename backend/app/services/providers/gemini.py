"""Google Gemini provider adapter.

Uses the Gemini REST API directly (no google-genai SDK dependency).

Pricing (March 2026):
    Flash: $0.30 / $2.50 per 1M tokens
    Pro:   $1.25 / $10   per 1M tokens
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

_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
# 2026-04-18: Primary Mind for Google is Gemini 3.1 Pro -- the
# founder-specified top-tier. 2.5 Pro / 2.0 Flash kept as fallbacks.
_DEFAULT_MODEL = "gemini-3.1-pro-preview"

_MODELS: list[dict[str, Any]] = [
    {
        "id": "gemini-3.1-pro-preview",
        "name": "Gemini 3.1 Pro",
        "ctx": 1_000_000,
        "in": 2.50,
        "out": 15.0,
        "tags": ["reasoning", "analysis", "vision", "large", "long-context", "frontier", "priority"],
    },
    {
        "id": "gemini-2.5-pro-preview-06-05",
        "name": "Gemini 2.5 Pro",
        "ctx": 1_000_000,
        "in": 1.25,
        "out": 10.0,
        "tags": ["reasoning", "vision", "long-context"],
    },
    {
        "id": "gemini-2.0-flash",
        "name": "Gemini 2.0 Flash",
        "ctx": 1_000_000,
        "in": 0.10,
        "out": 0.40,
        "tags": ["fast", "cheap", "vision"],
    },
]


class GeminiProvider(BaseProvider):
    """Google Gemini provider via REST API."""

    def __init__(self, api_key: str | None = None, timeout: float = 120.0) -> None:
        super().__init__(ModelProvider.GEMINI)
        self._api_key = api_key or get_settings().gemini_api_key
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=10.0),
        )

    async def generate(self, request: GenerateRequest) -> LLMResponse:
        model_id = request.model_id or _DEFAULT_MODEL
        start = self._start_timer()

        url = f"{_API_BASE}/models/{model_id}:generateContent?key={self._api_key}"
        payload = self._build_payload(request)
        resp = await self._client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        candidates = data.get("candidates", [{}])
        text = ""
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)

        usage = data.get("usageMetadata", {})
        input_tokens = usage.get("promptTokenCount", 0)
        output_tokens = usage.get("candidatesTokenCount", 0)
        model_info = self._find_model(model_id)

        return LLMResponse(
            content=text,
            model_id=model_id,
            provider=self.provider,
            token_count_input=input_tokens,
            token_count_output=output_tokens,
            cost_usd=self._compute_cost(model_info, input_tokens, output_tokens),
            latency_ms=self._elapsed_ms(start),
            finish_reason=(
                candidates[0].get("finishReason", "STOP").lower() if candidates else "stop"
            ),
            raw=data,
        )

    async def stream(self, request: GenerateRequest) -> AsyncIterator[LLMChunk]:
        model_id = request.model_id or _DEFAULT_MODEL
        url = f"{_API_BASE}/models/{model_id}:streamGenerateContent?alt=sse&key={self._api_key}"
        payload = self._build_payload(request)

        token_index = 0
        async with self._client.stream("POST", url, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                chunk_data = orjson.loads(line[6:])
                candidates = chunk_data.get("candidates", [])
                if not candidates:
                    continue
                parts = candidates[0].get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts)
                finish = candidates[0].get("finishReason")

                if text or finish:
                    yield LLMChunk(
                        content=text,
                        model_id=model_id,
                        provider=self.provider,
                        finish_reason=finish.lower() if finish else None,
                        token_index=token_index,
                    )
                    token_index += 1

    async def health_check(self) -> HealthStatus:
        if not self._api_key:
            self._healthy = HealthStatus.UNAVAILABLE
            return self._healthy
        try:
            url = f"{_API_BASE}/models?key={self._api_key}"
            resp = await self._client.get(url, timeout=5.0)
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
            cost_per_1m_input=0.30, cost_per_1m_output=2.50,
        )

    @staticmethod
    def _build_payload(request: GenerateRequest) -> dict[str, Any]:
        contents: list[dict[str, Any]] = []
        for msg in request.messages:
            if msg.role == "system":
                continue
            role = "model" if msg.role == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": msg.content}]})

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature,
                "topP": request.top_p,
                "maxOutputTokens": request.max_tokens,
            },
        }
        # System instruction
        system_text = request.system_prompt
        if not system_text:
            system_msgs = [m for m in request.messages if m.role == "system"]
            if system_msgs:
                system_text = "\n".join(m.content for m in system_msgs)
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}

        if request.stop_sequences:
            payload["generationConfig"]["stopSequences"] = request.stop_sequences

        return payload

    async def close(self) -> None:
        await self._client.aclose()
