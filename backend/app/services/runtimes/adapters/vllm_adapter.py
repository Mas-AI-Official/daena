"""vLLM runtime adapter.

Bridges the VLLMProvider (OpenAI-compatible HTTP API for LLM chat)
with the Runtime Adapter Layer. vLLM provides GPU-accelerated local
inference on Linux systems, serving as a high-performance alternative
to Ollama for users with NVIDIA GPUs.

Like the Ollama adapter, this uses the HTTP API directly since vLLM
is a server, not a CLI task executor.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.runtimes.base_adapter import (
    BaseRuntimeAdapter,
    RuntimeCapability,
    RuntimeStatus,
)

logger = get_logger(__name__)


class VLLMRuntimeAdapter(BaseRuntimeAdapter):
    """Runtime adapter for local vLLM GPU inference.

    Uses vLLM's OpenAI-compatible API. Designed for Linux dual-boot
    systems with NVIDIA GPUs. Higher capability scores than Ollama
    because vLLM can serve larger models with better throughput.
    """

    def __init__(self, base_url: str | None = None) -> None:
        super().__init__(
            runtime_id="vllm",
            display_name="vLLM (Local GPU)",
        )
        self._base_url = (base_url or get_settings().vllm_base_url).rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(120.0, connect=5.0),
        )

    async def check_installed(self) -> bool:
        """Check if vLLM server is reachable."""
        try:
            resp = await self._client.get("/models", timeout=5.0)
            return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException, OSError):
            return False

    async def check_health(self) -> RuntimeStatus:
        """Check vLLM server health via /v1/models."""
        try:
            resp = await self._client.get("/models", timeout=5.0)
            if resp.status_code == 200:
                models = resp.json().get("data", [])
                if models:
                    return RuntimeStatus.ONLINE
                return RuntimeStatus.ONLINE  # running but no models loaded yet
            return RuntimeStatus.ERROR
        except (httpx.ConnectError, httpx.TimeoutException):
            return RuntimeStatus.OFFLINE
        except OSError:
            return RuntimeStatus.NOT_INSTALLED

    async def get_capabilities(self) -> RuntimeCapability:
        """vLLM is free, local GPU, high capability for large models."""
        return RuntimeCapability(
            complex_reasoning=9.0,
            code_generation=8.0,
            code_editing=7.0,
            file_operations=2.0,
            web_research=1.0,
            data_analysis=8.0,
            browser_automation=0.0,
            simple_chat=8.0,
            bulk_operations=7.0,
            cost_per_1k_tokens=0.0,
        )

    async def execute(
        self, task: str, context: dict[str, Any],
    ) -> AsyncIterator[str]:
        """Execute via vLLM OpenAI-compatible chat API with streaming."""
        model = context.get("model", get_settings().vllm_default_model)
        system_prompt = context.get(
            "system_prompt", "You are Daena, a helpful AI assistant."
        )

        # If no model configured, try to auto-detect
        if not model:
            try:
                resp = await self._client.get("/models", timeout=5.0)
                if resp.status_code == 200:
                    models = resp.json().get("data", [])
                    if models:
                        model = models[0].get("id", "")
            except (httpx.ConnectError, httpx.TimeoutException):
                yield "[ERROR] vLLM server is offline. Start vLLM and try again."
                return

        if not model:
            yield "[ERROR] No vLLM model available. Start vLLM with a model loaded."
            return

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task},
            ],
            "stream": True,
            "max_tokens": context.get("max_tokens", 2048),
        }

        try:
            async with self._client.stream(
                "POST", "/chat/completions", json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        import orjson
                        chunk = orjson.loads(data_str)
                        choice = chunk.get("choices", [{}])[0]
                        delta = choice.get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
        except httpx.ConnectError:
            yield "[ERROR] vLLM server is offline. Start vLLM and try again."
        except httpx.HTTPStatusError as e:
            yield f"[ERROR] vLLM returned status {e.response.status_code}"

    async def cancel(self, session_id: str) -> bool:
        """vLLM doesn't have persistent sessions to cancel."""
        return False

    def get_auth_requirements(self) -> dict[str, Any]:
        return {
            "type": "local",
            "description": (
                "vLLM runs locally on Linux with GPU acceleration, "
                "no auth or subscription required"
            ),
            "setup_command": "vllm serve <model-name> --port 8100",
            "cost_to_user": "$0 (runs on your hardware)",
            "subscription_plans": [],
        }

    async def check_subscription(self):
        """vLLM is local -- always authenticated if installed."""
        from app.services.runtimes.subscription_auth import (
            AuthMethod,
            SubscriptionAuth,
            SubscriptionStatus,
        )

        installed = await self.check_installed()
        return SubscriptionAuth(
            method=AuthMethod.LOCAL,
            status=(
                SubscriptionStatus.AUTHENTICATED if installed
                else SubscriptionStatus.NOT_AUTHENTICATED
            ),
            plan_name="Local (free)",
            setup_command="vllm serve <model-name> --port 8100",
        )

    async def close(self) -> None:
        """Clean up HTTP client."""
        await self._client.aclose()
