"""vLLM provider adapter -- local GPU-accelerated LLM inference.

vLLM runs as an OpenAI-compatible API server on Linux with GPU
acceleration (default: http://localhost:8100/v1). Provides free
inference with no API key required, optimized for high-throughput
batch and streaming generation.

API docs: https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import json
import httpx

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

# vLLM is free local inference -- $0 per token
_COST_PER_1M_INPUT = 0.0
_COST_PER_1M_OUTPUT = 0.0


def _get_default_model() -> str:
    return get_settings().vllm_default_model


class VLLMProvider(BaseProvider):
    """Local vLLM LLM provider.

    Connects to the vLLM OpenAI-compatible API for chat completions.
    All inference is free and runs on the user's GPU hardware.
    Designed for Linux dual-boot systems with NVIDIA GPUs.
    """

    def __init__(self, base_url: str | None = None, timeout: float = 120.0) -> None:
        super().__init__(ModelProvider.VLLM)
        self._base_url = (base_url or get_settings().vllm_base_url).rstrip("/")
        self._default_timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(timeout, connect=10.0),
        )

    async def _post_with_retry(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        max_retries: int = 3,
        timeout: httpx.Timeout | None = None,
    ) -> httpx.Response:
        """POST with exponential backoff for overloaded and connection errors."""
        delays = [1.0, 2.0, 4.0]
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                resp = await self._client.post(path, json=payload, timeout=timeout)
                if resp.status_code == 529 and attempt < max_retries:
                    logger.warning(
                        "vllm_overloaded_retry",
                        attempt=attempt + 1,
                        delay=delays[attempt],
                    )
                    await asyncio.sleep(delays[attempt])
                    continue
                resp.raise_for_status()
                return resp
            except httpx.ConnectError as exc:
                raise RuntimeError(
                    "vLLM server is offline. Start the vLLM server and try again."
                ) from exc
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 529 and attempt < max_retries:
                    logger.warning(
                        "vllm_overloaded_retry",
                        attempt=attempt + 1,
                        delay=delays[attempt],
                    )
                    await asyncio.sleep(delays[attempt])
                    last_exc = exc
                    continue
                raise
        if last_exc:
            raise last_exc
        raise RuntimeError("vLLM request failed after retries")  # pragma: no cover

    async def _resolve_model(self, requested: str | None) -> str:
        """Resolve model to use: requested > default > auto-detect first available.

        When the requested model matches a GGUF catalog key and the
        LlamaServerManager is in a managed mode, ensure that exact
        model is loaded on llama-server before returning. Swap cost
        (~5s cold start) is absorbed here and amortized across the
        subsequent request + any follow-ups that reuse the same model.
        """
        default = _get_default_model()
        model_id = requested or default

        # LlamaServerManager integration. When requested matches a
        # GGUF catalog key (qwen3-8b / coder / gemma), the manager
        # guarantees that exact file is loaded before we make the
        # HTTP call. Short-circuits when mode is "off" so behavior
        # is unchanged for users who manage llama-server manually.
        if model_id and model_id not in ("auto", ""):
            await self._ensure_gguf_if_managed(model_id)
            return model_id

        # Auto-detect: pick the first available model
        try:
            models = await self.list_models()
            if models:
                best = models[0]
                logger.info(
                    "vllm_model_auto",
                    selected=best.model_id,
                    total_available=len(models),
                )
                return best.model_id
            raise RuntimeError(
                "No vLLM models loaded. Start vLLM with a model: "
                "vllm serve <model-name> --port 8100"
            )
        except RuntimeError:
            raise
        except Exception:
            if model_id:
                return model_id
            raise RuntimeError(
                "Cannot connect to vLLM to discover models. "
                "Set VLLM_DEFAULT_MODEL or start the vLLM server."
            )

    async def _ensure_gguf_if_managed(self, model_id: str) -> None:
        """Delegate to LlamaServerManager if the model maps to a GGUF key.

        Fail-safe: any manager error is logged but does NOT abort the
        request. The downstream HTTP call will still fail cleanly
        with llama-server's own error if the model is not loaded.
        """
        try:
            from app.services.providers.gguf_catalog import (
                find_by_served_name, get_model,
            )
            from app.services.providers.llama_server_manager import (
                ManagedMode, get_manager,
            )
            manager = get_manager()
            if manager.mode == ManagedMode.OFF:
                return
            target = get_model(model_id) or find_by_served_name(model_id)
            if target is None:
                return  # Not a GGUF we know about; leave it alone.
            await manager.ensure_loaded(target.key)
        except Exception as exc:  # pragma: no cover - never raise from pre-hook
            logger.warning(
                "vllm.manager_prehook_failed",
                model_id=model_id,
                error=str(exc),
            )

    async def generate(self, request: GenerateRequest) -> LLMResponse:
        """Send chat completion request to vLLM (OpenAI-compatible)."""
        model_id = await self._resolve_model(request.model_id)
        start = self._start_timer()

        payload = self._build_payload(request, model_id, stream=False)
        timeout = httpx.Timeout(self._default_timeout, connect=10.0)
        try:
            resp = await self._post_with_retry("/chat/completions", payload, timeout=timeout)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise RuntimeError(
                    f"vLLM model '{model_id}' not found. "
                    f"Start vLLM with: vllm serve {model_id} --port 8100"
                ) from exc
            raise
        data = resp.json()

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        return LLMResponse(
            content=message.get("content", ""),
            model_id=model_id,
            provider=self.provider,
            token_count_input=input_tokens,
            token_count_output=output_tokens,
            cost_usd=0.0,
            latency_ms=self._elapsed_ms(start),
            finish_reason=choice.get("finish_reason", "stop"),
            raw=data,
        )

    async def stream(self, request: GenerateRequest) -> AsyncIterator[LLMChunk]:
        """Stream tokens from vLLM one at a time via SSE.

        Uses the OpenAI-compatible streaming format (data: {...} lines).
        """
        model_id = await self._resolve_model(request.model_id)
        payload = self._build_payload(request, model_id, stream=True)
        timeout = httpx.Timeout(self._default_timeout, connect=10.0)

        try:
            resp_cm = self._client.stream(
                "POST", "/chat/completions", json=payload, timeout=timeout,
            )
        except httpx.ConnectError as exc:
            raise RuntimeError(
                "vLLM server is offline. Start the vLLM server and try again."
            ) from exc

        token_index = 0
        async with resp_cm as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                # OpenAI SSE format: "data: {...}" or "data: [DONE]"
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    import orjson
                    chunk_data = orjson.loads(data_str)

                    choice = chunk_data.get("choices", [{}])[0]
                    delta = choice.get("delta", {})
                    content = delta.get("content", "")
                    finish_reason = choice.get("finish_reason")

                    if content or finish_reason:
                        yield LLMChunk(
                            content=content or "",
                            model_id=model_id,
                            provider=self.provider,
                            finish_reason=finish_reason,
                            token_index=token_index,
                        )
                        token_index += 1

    async def health_check(self) -> HealthStatus:
        """Ping vLLM server and check for available models.

        Hardened 2026-04-22: when something OTHER than llama-server /
        vLLM is holding the configured port (common in WSL: port 8080
        often maps to the Windows-side landing page), resp.json() used
        to raise JSONDecodeError -- crashed the health refresh and
        spammed logs. Now we verify content-type + catch JSON errors
        before propagating.
        """
        try:
            resp = await self._client.get("/models", timeout=5.0)
            if resp.status_code == 200:
                ctype = resp.headers.get("content-type", "").lower()
                if "application/json" not in ctype:
                    logger.warning(
                        "vllm_non_json_response",
                        base_url=self._base_url,
                        content_type=ctype,
                        hint="Port may be held by a non-LLM service.",
                    )
                    self._healthy = HealthStatus.UNAVAILABLE
                    return self._healthy
                try:
                    data = resp.json()
                except (json.JSONDecodeError, ValueError):
                    self._healthy = HealthStatus.UNAVAILABLE
                    return self._healthy
                models = data.get("data", [])
                if models:
                    self._healthy = HealthStatus.HEALTHY
                else:
                    logger.warning(
                        "vllm_no_models",
                        impact="Chat will fail. Start vLLM with a model loaded.",
                    )
                    self._healthy = HealthStatus.DEGRADED
            else:
                self._healthy = HealthStatus.DEGRADED
        except (httpx.ConnectError, httpx.TimeoutException):
            self._healthy = HealthStatus.UNAVAILABLE
        return self._healthy

    async def list_models(self) -> list[ModelInfo]:
        """Query vLLM for currently loaded models via /v1/models.

        Same hardening as health_check: graceful empty-list when the
        port is held by a non-LLM service returning HTML.
        """
        try:
            resp = await self._client.get("/models", timeout=10.0)
            resp.raise_for_status()
            ctype = resp.headers.get("content-type", "").lower()
            if "application/json" not in ctype:
                logger.warning(
                    "vllm_list_models_non_json",
                    base_url=self._base_url,
                    content_type=ctype,
                )
                return []
            data = resp.json()
        except (httpx.HTTPError, httpx.ConnectError, json.JSONDecodeError, ValueError):
            logger.warning("vllm_list_models_failed", base_url=self._base_url)
            return []

        models: list[ModelInfo] = []
        for m in data.get("data", []):
            model_id = m.get("id", "unknown")
            models.append(
                ModelInfo(
                    model_id=model_id,
                    provider=self.provider,
                    display_name=model_id,
                    context_window=m.get("max_model_len", 4096),
                    supports_streaming=True,
                    supports_vision=False,
                    cost_per_1m_input=_COST_PER_1M_INPUT,
                    cost_per_1m_output=_COST_PER_1M_OUTPUT,
                    tags=["vllm", "local", "gpu"],
                )
            )
        return models

    # -- Internal helpers --

    @staticmethod
    def _build_payload(
        request: GenerateRequest, model_id: str, *, stream: bool
    ) -> dict[str, Any]:
        """Convert GenerateRequest to OpenAI-compatible API payload."""
        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        for msg in request.messages:
            messages.append({"role": msg.role, "content": msg.content})

        payload: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "stream": stream,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "max_tokens": request.max_tokens,
        }
        if request.stop_sequences:
            payload["stop"] = request.stop_sequences
        return payload

    async def close(self) -> None:
        """Clean up HTTP client."""
        await self._client.aclose()
