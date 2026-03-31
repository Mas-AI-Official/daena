"""Ollama provider adapter — local LLM inference.

Ollama runs locally (default: http://localhost:11434) and provides
free inference with no API key required.  Primary model source for
Daena (target: 70% of queries via Ollama).

API docs: https://github.com/ollama/ollama/blob/main/docs/api.md
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

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

# Ollama is free — $0 per token
_COST_PER_1M_INPUT = 0.0
_COST_PER_1M_OUTPUT = 0.0

# Default model when none specified — reads from OLLAMA_DEFAULT_MODEL env var
def _get_default_model() -> str:
    return get_settings().ollama_default_model


def _estimate_param_size(model_id: str) -> float:
    """Estimate parameter count from model name for auto-selection.

    Parses size tags like :27b, :14b, :7b from model names.
    Larger models are preferred for auto-selection.
    """
    import re

    match = re.search(r":?(\d+\.?\d*)b", model_id.lower())
    if match:
        return float(match.group(1))
    # Heuristic for models without size tag
    if "70b" in model_id or "72b" in model_id:
        return 70.0
    if "large" in model_id:
        return 30.0
    return 7.0  # assume small if unknown


class OllamaProvider(BaseProvider):
    """Local Ollama LLM provider.

    Connects to the Ollama HTTP API for chat completions.
    All inference is free and runs on the user's hardware.
    """

    def __init__(self, base_url: str | None = None, timeout: float = 120.0) -> None:
        super().__init__(ModelProvider.OLLAMA)
        self._base_url = (base_url or get_settings().ollama_base_url).rstrip("/")
        self._timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(timeout, connect=10.0),
        )

    async def _post_with_retry(
        self, path: str, payload: dict[str, Any], *, max_retries: int = 3
    ) -> httpx.Response:
        """POST with exponential backoff for 529/overloaded and connection errors."""
        delays = [1.0, 2.0, 4.0]
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                resp = await self._client.post(path, json=payload)
                if resp.status_code == 529 and attempt < max_retries:
                    logger.warning(
                        "ollama_overloaded_retry",
                        attempt=attempt + 1,
                        delay=delays[attempt],
                    )
                    await asyncio.sleep(delays[attempt])
                    continue
                resp.raise_for_status()
                return resp
            except httpx.ConnectError as exc:
                raise RuntimeError(
                    "Ollama is offline. Start Ollama and try again."
                ) from exc
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 529 and attempt < max_retries:
                    logger.warning(
                        "ollama_overloaded_retry",
                        attempt=attempt + 1,
                        delay=delays[attempt],
                    )
                    await asyncio.sleep(delays[attempt])
                    last_exc = exc
                    continue
                raise
        if last_exc:
            raise last_exc
        raise RuntimeError("Ollama request failed after retries")  # pragma: no cover

    async def _resolve_model(self, requested: str | None) -> str:
        """Resolve model to use: requested > auto-detect best > any available.

        When OLLAMA_DEFAULT_MODEL=auto or no model specified, scans
        installed models and picks the largest/most capable one.
        Embedding models (nomic-embed-*) are excluded from auto-select.
        """
        default = _get_default_model()
        model_id = requested or default

        try:
            models = await self.list_models()
            available = [m for m in models if "embed" not in m.model_id]
            available_ids = {m.model_id for m in available}

            # Auto-detect: pick the best installed model by parameter size
            if model_id in ("auto", "") or model_id is None:
                if available:
                    best = max(available, key=lambda m: _estimate_param_size(m.model_id))
                    logger.info(
                        "ollama_model_auto",
                        selected=best.model_id,
                        context_window=best.context_window,
                        total_available=len(available),
                    )
                    return best.model_id
                raise RuntimeError("No Ollama models installed. Run 'ollama pull qwen3.5:27b'.")

            # CLI provider model IDs are not Ollama models — auto-select
            if model_id.endswith("-cli"):
                if available:
                    best = max(available, key=lambda m: _estimate_param_size(m.model_id))
                    logger.info("ollama_model_auto_cli_fallback", requested=model_id, selected=best.model_id)
                    return best.model_id
                raise RuntimeError("No Ollama models available for fallback.")

            if model_id in available_ids:
                return model_id

            # Try without tag (e.g., "llama3.1" matches "llama3.1:8b")
            for avail in available_ids:
                if avail.startswith(model_id.split(":")[0]):
                    logger.info("ollama_model_resolved", requested=model_id, resolved=avail)
                    return avail

            # Use best available as last resort
            if available:
                best = max(available, key=lambda m: _estimate_param_size(m.model_id))
                logger.warning("ollama_model_fallback", requested=model_id, fallback=best.model_id)
                return best.model_id

            raise RuntimeError(
                f"No Ollama models available. Run 'ollama pull {model_id}' to download one."
            )
        except RuntimeError:
            raise
        except Exception:
            return model_id

    async def generate(self, request: GenerateRequest) -> LLMResponse:
        """Send chat completion request to Ollama."""
        model_id = await self._resolve_model(request.model_id)
        start = self._start_timer()

        payload = self._build_payload(request, model_id, stream=False)
        try:
            resp = await self._post_with_retry("/api/chat", payload)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise RuntimeError(
                    f"Ollama model '{model_id}' not found. "
                    f"Run 'ollama pull {model_id}' to download it."
                ) from exc
            if exc.response.status_code == 500:
                body = exc.response.text
                if "requires more system memory" in body:
                    raise RuntimeError(
                        f"Model '{model_id}' needs more RAM than available. "
                        f"Try a smaller model (mistral:7b or llama3.1:8b)."
                    ) from exc
            raise
        data = resp.json()

        message = data.get("message", {})
        input_tokens = data.get("prompt_eval_count", 0)
        output_tokens = data.get("eval_count", 0)

        return LLMResponse(
            content=message.get("content", ""),
            model_id=model_id,
            provider=self.provider,
            token_count_input=input_tokens,
            token_count_output=output_tokens,
            cost_usd=0.0,
            latency_ms=self._elapsed_ms(start),
            finish_reason=data.get("done_reason", "stop"),
            raw=data,
        )

    async def stream(self, request: GenerateRequest) -> AsyncIterator[LLMChunk]:
        """Stream tokens from Ollama one at a time.

        Retries up to 3 times on 529/overloaded with exponential backoff.
        Raises a clear message if Ollama is unreachable.
        """
        model_id = await self._resolve_model(request.model_id)
        payload = self._build_payload(request, model_id, stream=True)

        # Retry loop for stream initialization
        delays = [1.0, 2.0, 4.0]
        resp_cm = None
        for attempt in range(4):
            try:
                resp_cm = self._client.stream("POST", "/api/chat", json=payload)
                break
            except httpx.ConnectError as exc:
                raise RuntimeError(
                    "Ollama is offline. Start Ollama and try again."
                ) from exc
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    raise RuntimeError(
                        f"Ollama model '{model_id}' not found. "
                        f"Run 'ollama pull {model_id}' to download it."
                    ) from exc
                if exc.response.status_code == 500:
                    body = exc.response.text
                    if "requires more system memory" in body:
                        raise RuntimeError(
                            f"Model '{model_id}' needs more RAM than available. "
                            f"Try a smaller model (mistral:7b or llama3.1:8b)."
                        ) from exc
                if exc.response.status_code == 529 and attempt < 3:
                    await asyncio.sleep(delays[attempt])
                    continue
                raise

        if resp_cm is None:
            raise RuntimeError("Ollama stream failed after retries")

        token_index = 0
        async with resp_cm as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                import orjson

                chunk_data = orjson.loads(line)

                # Check for error in stream body (e.g., OOM)
                if "error" in chunk_data:
                    err_msg = chunk_data["error"]
                    if "requires more system memory" in err_msg:
                        raise RuntimeError(
                            f"Model '{model_id}' needs more RAM than available. "
                            f"Try a smaller model (mistral:7b or llama3.1:8b)."
                        )
                    raise RuntimeError(f"Ollama error: {err_msg}")

                message = chunk_data.get("message", {})
                content = message.get("content", "")
                done = chunk_data.get("done", False)

                yield LLMChunk(
                    content=content,
                    model_id=model_id,
                    provider=self.provider,
                    finish_reason=chunk_data.get("done_reason") if done else None,
                    token_index=token_index,
                )
                token_index += 1

    async def health_check(self) -> HealthStatus:
        """Ping Ollama server and check for available models."""
        try:
            resp = await self._client.get("/api/tags", timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("models", [])
                if models:
                    self._healthy = HealthStatus.HEALTHY
                else:
                    # Server online but no models -- degraded, not healthy
                    logger.warning(
                        "ollama_no_models",
                        impact="Chat will fail. Run 'ollama pull llama3.1' to download a model.",
                    )
                    self._healthy = HealthStatus.DEGRADED
            else:
                self._healthy = HealthStatus.DEGRADED
        except (httpx.ConnectError, httpx.TimeoutException):
            self._healthy = HealthStatus.UNAVAILABLE
        return self._healthy

    async def list_models(self) -> list[ModelInfo]:
        """Query Ollama for locally available models."""
        try:
            resp = await self._client.get("/api/tags", timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, httpx.ConnectError):
            logger.warning("ollama_list_models_failed", base_url=self._base_url)
            return []

        models: list[ModelInfo] = []
        for m in data.get("models", []):
            name = m.get("name", "unknown")
            details = m.get("details", {})
            models.append(
                ModelInfo(
                    model_id=name,
                    provider=self.provider,
                    display_name=name,
                    context_window=details.get("context_length", 4096),
                    supports_streaming=True,
                    supports_vision="vision" in name.lower(),
                    cost_per_1m_input=_COST_PER_1M_INPUT,
                    cost_per_1m_output=_COST_PER_1M_OUTPUT,
                    tags=details.get("families", []),
                )
            )
        return models

    # ── Internal helpers ──────────────────────────────────────

    @staticmethod
    def _build_payload(
        request: GenerateRequest, model_id: str, *, stream: bool
    ) -> dict[str, Any]:
        """Convert GenerateRequest to Ollama API payload."""
        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        for msg in request.messages:
            messages.append({"role": msg.role, "content": msg.content})

        return {
            "model": model_id,
            "messages": messages,
            "stream": stream,
            "keep_alive": "30m",  # Keep model loaded in GPU memory between requests
            "options": {
                "temperature": request.temperature,
                "top_p": request.top_p,
                "num_predict": request.max_tokens,
                **({"stop": request.stop_sequences} if request.stop_sequences else {}),
            },
        }

    async def close(self) -> None:
        """Clean up HTTP client."""
        await self._client.aclose()
