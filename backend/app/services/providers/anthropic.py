"""Anthropic provider adapter — Claude models.

Premium reasoning and coding provider.  Uses the Anthropic Messages API
directly via httpx (no SDK dependency).

Pricing (March 2026):
    Haiku:  $1 / $5  per 1M tokens
    Sonnet: $3 / $15 per 1M tokens
    Opus:   $5 / $25 per 1M tokens
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

_API_BASE = "https://api.anthropic.com"
_API_VERSION = "2023-06-01"
# 2026-04-18: Primary Mind for Anthropic is Sonnet 4.7 Max -- the
# founder-specified top-tier Claude. Sonnet 4 / Opus 4 / Haiku 4.5
# kept in the catalog as cheaper fallbacks, but when the router has
# no cost pressure it picks 4.7 Max first (priority tag).
_DEFAULT_MODEL = "claude-sonnet-4-7-max"

# Model catalog with pricing per 1M tokens. Priority tag drives
# "best of the best" selection when no cost cap forces a cheaper
# pick -- see model_router.py scoring.
_MODELS: list[dict[str, Any]] = [
    {
        "id": "claude-sonnet-4-7-max",
        "name": "Claude Sonnet 4.7 Max",
        "ctx": 1_000_000,
        "in": 3.0,
        "out": 15.0,
        "tags": ["reasoning", "coding", "frontier", "priority"],
    },
    {
        "id": "claude-opus-4-20250514",
        "name": "Claude Opus 4",
        "ctx": 200_000,
        "in": 15.0,
        "out": 75.0,
        "tags": ["reasoning", "premium"],
    },
    {
        "id": "claude-sonnet-4-20250514",
        "name": "Claude Sonnet 4",
        "ctx": 200_000,
        "in": 3.0,
        "out": 15.0,
        "tags": ["reasoning", "coding", "balanced"],
    },
    {
        "id": "claude-haiku-4-5-20251001",
        "name": "Claude Haiku 4.5",
        "ctx": 200_000,
        "in": 1.0,
        "out": 5.0,
        "tags": ["fast", "cheap"],
    },
]


class AnthropicProvider(BaseProvider):
    """Anthropic Claude provider via Messages API."""

    def __init__(self, api_key: str | None = None, timeout: float = 120.0) -> None:
        super().__init__(ModelProvider.ANTHROPIC)
        self._api_key = api_key or get_settings().anthropic_api_key
        self._client = httpx.AsyncClient(
            base_url=_API_BASE,
            timeout=httpx.Timeout(timeout, connect=10.0),
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": _API_VERSION,
                "content-type": "application/json",
            },
        )

    async def generate(self, request: GenerateRequest) -> LLMResponse:
        """Send a Messages API request and return full response."""
        model_id = request.model_id or _DEFAULT_MODEL
        start = self._start_timer()

        payload = self._build_payload(request, model_id, stream=False)
        resp = await self._client.post("/v1/messages", json=payload)
        resp.raise_for_status()
        data = resp.json()

        content_blocks = data.get("content", [])
        text = "".join(
            block.get("text", "") for block in content_blocks if block.get("type") == "text"
        )

        usage = data.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        model_info = self._find_model(model_id)
        cost = self._compute_cost(model_info, input_tokens, output_tokens)

        return LLMResponse(
            content=text,
            model_id=model_id,
            provider=self.provider,
            token_count_input=input_tokens,
            token_count_output=output_tokens,
            cost_usd=cost,
            latency_ms=self._elapsed_ms(start),
            finish_reason=data.get("stop_reason", "end_turn"),
            raw=data,
        )

    async def stream(self, request: GenerateRequest) -> AsyncIterator[LLMChunk]:
        """Stream tokens via Anthropic's SSE streaming."""
        model_id = request.model_id or _DEFAULT_MODEL
        payload = self._build_payload(request, model_id, stream=True)

        token_index = 0
        async with self._client.stream("POST", "/v1/messages", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                raw = line[6:]
                if raw == "[DONE]":
                    break
                event = orjson.loads(raw)
                event_type = event.get("type", "")

                if event_type == "content_block_delta":
                    delta = event.get("delta", {})
                    text = delta.get("text", "")
                    if text:
                        yield LLMChunk(
                            content=text,
                            model_id=model_id,
                            provider=self.provider,
                            token_index=token_index,
                        )
                        token_index += 1
                elif event_type == "message_stop":
                    yield LLMChunk(
                        content="",
                        model_id=model_id,
                        provider=self.provider,
                        finish_reason="end_turn",
                        token_index=token_index,
                    )

    async def health_check(self) -> HealthStatus:
        """Check API reachability (lightweight model list call)."""
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
        """Return hardcoded Claude model catalog."""
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

    # ── Internal helpers ──────────────────────────────────────

    def _find_model(self, model_id: str) -> ModelInfo:
        """Look up model info from catalog, with fallback defaults."""
        for m in _MODELS:
            if m["id"] == model_id:
                return ModelInfo(
                    model_id=m["id"],
                    provider=self.provider,
                    cost_per_1m_input=m["in"],
                    cost_per_1m_output=m["out"],
                )
        # Unknown model — use Sonnet pricing as conservative default
        return ModelInfo(
            model_id=model_id,
            provider=self.provider,
            cost_per_1m_input=3.0,
            cost_per_1m_output=15.0,
        )

    @staticmethod
    def _build_payload(
        request: GenerateRequest, model_id: str, *, stream: bool
    ) -> dict[str, Any]:
        """Convert GenerateRequest to Anthropic Messages API payload."""
        messages: list[dict[str, str]] = []
        for msg in request.messages:
            if msg.role != "system":
                messages.append({"role": msg.role, "content": msg.content})

        payload: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "stream": stream,
        }
        # System prompt goes as top-level field in Anthropic API
        system_text = request.system_prompt
        if not system_text:
            system_msgs = [m for m in request.messages if m.role == "system"]
            if system_msgs:
                system_text = "\n".join(m.content for m in system_msgs)
        if system_text:
            payload["system"] = system_text

        if request.stop_sequences:
            payload["stop_sequences"] = request.stop_sequences

        return payload

    async def close(self) -> None:
        """Clean up HTTP client."""
        await self._client.aclose()
