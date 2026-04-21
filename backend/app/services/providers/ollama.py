"""Ollama provider adapter — local LLM inference.

Ollama runs locally (default: http://localhost:11434) and provides
free inference with no API key required.  Primary model source for
Daena (target: 70% of queries via Ollama).

WSL host resolution (added 2026-04-18):
    When Daena runs inside WSL2 but Ollama runs on the Windows host,
    ``localhost:11434`` points at WSL's own loopback and nothing's
    listening there. The user's actual Ollama daemon is reachable via
    either ``host.docker.internal`` (auto-populated in /etc/hosts on
    Windows 11 / recent WSL2) or the Windows host IP found in
    /etc/resolv.conf. ``_resolve_ollama_base_url`` probes the
    user-configured URL first; if it's unreachable AND we're on WSL,
    it falls back to these WSL-aware alternatives before giving up.
    This fixes the "Ollama installed but backend says unavailable"
    state that looked like the daemon was broken.

API docs: https://github.com/ollama/ollama/blob/main/docs/api.md
"""

from __future__ import annotations

import asyncio
import os
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


# WSL/Ollama URL resolution with a short TTL. Caching forever was
# wrong: when the user starts Ollama on Windows AFTER the backend
# booted, the cached ``None``/failure wedged every fallback request.
# And if they switch between systems / stop & restart Ollama on a
# different port, the cached URL was wrong forever.
#
# 60s TTL is short enough to feel instant ("turn Ollama on, wait a
# minute, it works") but long enough that no request pays a probe
# cost on the hot path.
_RESOLVED_BASE_URL: str | None = None
_RESOLVED_AT: float = 0.0
_RESOLVE_TTL_SECONDS: float = 60.0


def _is_wsl() -> bool:
    """Return True if the process is running inside WSL (1 or 2)."""
    try:
        with open("/proc/version", encoding="utf-8") as fh:
            return "microsoft" in fh.read().lower()
    except OSError:
        return False


def _read_windows_host_ip() -> str | None:
    """Best-effort: return the Windows host IP as seen from WSL.

    On WSL2, /etc/resolv.conf contains a ``nameserver <windows-host-ip>``
    line. Older WSL2 layouts use 10.255.255.254 for a DNS forwarder
    rather than the actual host, so this hint is not always correct --
    ``host.docker.internal`` remains the authoritative probe target.
    """
    try:
        with open("/etc/resolv.conf", encoding="utf-8") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) >= 2 and parts[0] == "nameserver":
                    return parts[1]
    except OSError:
        return None
    return None


def _probe_url_sync(url: str, timeout: float = 1.5) -> bool:
    """Tiny synchronous reachability probe. Used only at import time
    so we don't need an event loop just to resolve a base URL."""
    try:
        with httpx.Client(timeout=timeout) as c:
            return c.get(f"{url.rstrip('/')}/api/tags").status_code == 200
    except Exception:
        return False


def resolve_ollama_base_url(
    configured: str | None = None,
    *,
    force: bool = False,
) -> str:
    """Pick the first working Ollama base URL.

    Priority:
        1. Environment override (``OLLAMA_BASE_URL``) when explicitly set.
        2. The caller-provided / settings-provided URL.
        3. If we're on WSL AND the above didn't answer, try
           ``http://host.docker.internal:11434`` (Windows host).
        4. If still nothing, try the Windows host IP from resolv.conf.
        5. Give up and return the default -- the later code will log
           "skipped" instead of wasting a full request.

    Cached with a ``_RESOLVE_TTL_SECONDS`` TTL so transient failures
    (Ollama not yet started, network flap) don't wedge the resolver
    forever. ``force=True`` bypasses the cache entirely -- use from
    manual refresh UI / health endpoints.
    """
    import time as _time

    global _RESOLVED_BASE_URL, _RESOLVED_AT
    now = _time.monotonic()
    if (
        not force
        and _RESOLVED_BASE_URL is not None
        and (now - _RESOLVED_AT) < _RESOLVE_TTL_SECONDS
    ):
        return _RESOLVED_BASE_URL

    candidates: list[str] = []
    env_override = os.environ.get("OLLAMA_BASE_URL", "").strip()
    if env_override:
        candidates.append(env_override)
    if configured:
        candidates.append(configured)
    default_local = "http://localhost:11434"
    if default_local not in candidates:
        candidates.append(default_local)

    if _is_wsl():
        wsl_fallbacks = ["http://host.docker.internal:11434"]
        host_ip = _read_windows_host_ip()
        if host_ip:
            wsl_fallbacks.append(f"http://{host_ip}:11434")
        for fb in wsl_fallbacks:
            if fb not in candidates:
                candidates.append(fb)

    for url in candidates:
        if _probe_url_sync(url):
            previous = _RESOLVED_BASE_URL
            _RESOLVED_BASE_URL = url
            _RESOLVED_AT = now
            # Log when chosen URL changes OR on first success. A TTL
            # re-probe that picks the same URL stays quiet.
            if previous != url:
                logger.info(
                    "ollama_base_url_resolved",
                    chosen=url,
                    previous=previous,
                    reason="wsl_fallback" if "host.docker.internal" in url or (
                        _read_windows_host_ip() and url.startswith(
                            f"http://{_read_windows_host_ip()}"
                        )
                    ) else "configured",
                )
            return url

    # Nothing reachable. DO NOT lock in a dead URL as a permanent
    # cache -- mark it as recently-probed so we don't re-probe every
    # request, but also don't advertise it as "resolved". Callers
    # that check health will still see nothing listens there. Next
    # TTL window we re-probe, so Ollama coming up between boots is
    # picked up within ~60s with zero manual refresh.
    _RESOLVED_BASE_URL = candidates[0]
    _RESOLVED_AT = now
    return _RESOLVED_BASE_URL


def invalidate_ollama_resolver_cache() -> None:
    """Force the resolver to re-probe on its next call.

    Called from manual "refresh" API endpoints so the user can nudge
    the backend after starting Ollama, rather than waiting up to 60s
    for the TTL window.
    """
    global _RESOLVED_BASE_URL, _RESOLVED_AT
    _RESOLVED_BASE_URL = None
    _RESOLVED_AT = 0.0

# Ollama is free — $0 per token
_COST_PER_1M_INPUT = 0.0
_COST_PER_1M_OUTPUT = 0.0

# Default model when none specified — reads from OLLAMA_DEFAULT_MODEL env var
def _get_default_model() -> str:
    return get_settings().ollama_default_model


def _pick_best_model(models: list) -> object:
    """Pick the best model from available models.

    Strategy: prefer the largest model that fits comfortably in RAM.
    Models above 27B params often OOM on consumer hardware (32GB RAM).
    Sort by: models 8-27B first (sweet spot), then smaller, then larger.
    """
    sorted_models = sorted(
        models,
        key=lambda m: _model_preference_score(_estimate_param_size(m.model_id)),
        reverse=True,
    )
    return sorted_models[0]


def _model_preference_score(param_b: float) -> float:
    """Score a model by how preferable it is for auto-selection.

    Prefer models that fit in typical consumer RAM (16-32GB).
    7-8B models are the sweet spot: good quality, always fit.
    14B+ needs 32GB+, often OOM on real machines.
    """
    if 7 <= param_b <= 8:
        return param_b + 200  # best balance: quality + fits everywhere
    if 3 <= param_b < 7:
        return param_b + 150  # small but reliable
    if 8 < param_b <= 14:
        return param_b + 100  # good if RAM allows
    if 14 < param_b <= 27:
        return param_b + 50   # risky on 32GB
    if param_b > 27:
        return param_b        # likely OOM
    return param_b             # tiny, last resort


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

    # Reasoning models do internal chain-of-thought that can take 5-10 minutes.
    # Standard 120s timeout causes premature failures on deepseek-r1, qwen3 /think, etc.
    _REASONING_MODEL_PATTERNS = ("deepseek-r1", "deepseek-r2", "qwq", "o1", "o3")
    _REASONING_TIMEOUT = 600.0  # 10 minutes for reasoning models
    _STANDARD_TIMEOUT = 120.0   # 2 minutes for standard models

    def __init__(self, base_url: str | None = None, timeout: float = 120.0) -> None:
        super().__init__(ModelProvider.OLLAMA)
        configured = (base_url or get_settings().ollama_base_url or "").rstrip("/")
        # WSL-aware resolution: if configured URL is unreachable but
        # Ollama is running on the Windows host, this returns the
        # host.docker.internal form so the provider actually works.
        self._base_url = resolve_ollama_base_url(configured or None).rstrip("/")
        self._default_timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(timeout, connect=10.0),
        )

    def _timeout_for_model(self, model_id: str) -> httpx.Timeout:
        """Return an appropriate timeout for the model.

        Reasoning models (deepseek-r1, qwq, etc.) do internal
        chain-of-thought that can take 5-10 minutes. Standard
        models rarely exceed 2 minutes.
        """
        model_lower = model_id.lower()
        for pattern in self._REASONING_MODEL_PATTERNS:
            if pattern in model_lower:
                return httpx.Timeout(self._REASONING_TIMEOUT, connect=10.0)
        return httpx.Timeout(self._default_timeout, connect=10.0)

    async def _post_with_retry(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        max_retries: int = 3,
        timeout: httpx.Timeout | None = None,
    ) -> httpx.Response:
        """POST with exponential backoff for 529/overloaded and connection errors."""
        delays = [1.0, 2.0, 4.0]
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                resp = await self._client.post(path, json=payload, timeout=timeout)
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

            # Auto-detect: pick the best model that fits in memory.
            # Sort by size descending, prefer models in the 7-14B range
            # (most likely to fit in available RAM without OOM errors).
            if model_id in ("auto", "") or model_id is None:
                if available:
                    best = _pick_best_model(available)
                    logger.info(
                        "ollama_model_auto",
                        selected=best.model_id,
                        params_b=_estimate_param_size(best.model_id),
                        total_available=len(available),
                    )
                    return best.model_id
                raise RuntimeError("No Ollama models installed. Run 'ollama pull llama3.1:8b'.")

            # CLI provider model IDs are not Ollama models — auto-select
            if model_id.endswith("-cli"):
                if available:
                    best = _pick_best_model(available)
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

            # Use best available as last resort. Logged at info: this
            # is expected whenever the ``OLLAMA_DEFAULT_MODEL`` setting
            # names a model the user hasn't pulled yet; we pick
            # whatever's actually on disk. Warning-level would make
            # "just pull a different model" look like a defect.
            if available:
                best = _pick_best_model(available)
                logger.info(
                    "ollama_model_fallback",
                    requested=model_id,
                    fallback=best.model_id,
                    reason="requested_model_not_installed",
                )
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
        model_timeout = self._timeout_for_model(model_id)
        try:
            resp = await self._post_with_retry("/api/chat", payload, timeout=model_timeout)
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
        model_timeout = self._timeout_for_model(model_id)

        # Retry loop for stream initialization
        delays = [1.0, 2.0, 4.0]
        resp_cm = None
        for attempt in range(4):
            try:
                resp_cm = self._client.stream(
                    "POST", "/api/chat", json=payload, timeout=model_timeout,
                )
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
        """Query Ollama for locally available models.

        Logs at ``info`` (not ``warning``) when the daemon is simply
        absent -- that's the expected state for cloud-first users and
        shouldn't produce yellow "warning" lines in every request log
        that touches the model registry. Real errors (HTTP 5xx from a
        live daemon) still surface at warning level.
        """
        try:
            resp = await self._client.get("/api/tags", timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.ConnectError, httpx.ConnectTimeout):
            # Daemon not running -- expected for cloud-only deployments.
            logger.info(
                "ollama_list_models_skipped",
                reason="daemon_unreachable",
                base_url=self._base_url,
            )
            return []
        except httpx.HTTPError:
            # Daemon responded but something else went wrong -- worth warning.
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
