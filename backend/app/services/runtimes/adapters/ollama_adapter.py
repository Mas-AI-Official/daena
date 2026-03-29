"""Ollama runtime adapter.

Bridges the existing OllamaProvider (HTTP API for LLM chat) with the
Runtime Adapter Layer (CLI-based task execution). Ollama is always the
local fallback: free, no auth, always available if running.

Unlike other adapters that wrap CLI subprocesses, this adapter uses
Ollama's HTTP API directly (since Ollama doesn't have a task-execution
CLI like Claude Code). For task execution, it sends the task as a chat
prompt and streams the response.
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


class OllamaRuntimeAdapter(BaseRuntimeAdapter):
    """Runtime adapter for local Ollama inference.

    Uses Ollama's HTTP API (not subprocess) since Ollama is a server,
    not a CLI task executor. This makes it the fastest adapter for
    simple chat and analysis tasks.
    """

    def __init__(self, base_url: str | None = None) -> None:
        super().__init__(
            runtime_id="ollama",
            display_name="Ollama (Local)",
        )
        self._base_url = (base_url or get_settings().ollama_base_url).rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(120.0, connect=5.0),
        )

    async def check_installed(self) -> bool:
        """Check if Ollama server is reachable."""
        try:
            resp = await self._client.get("/api/tags", timeout=5.0)
            return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException, OSError):
            return False

    async def check_health(self) -> RuntimeStatus:
        """Check Ollama server health."""
        try:
            resp = await self._client.get("/api/tags", timeout=5.0)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                if models:
                    return RuntimeStatus.ONLINE
                return RuntimeStatus.ONLINE  # running but no models
            return RuntimeStatus.ERROR
        except (httpx.ConnectError, httpx.TimeoutException):
            return RuntimeStatus.OFFLINE
        except OSError:
            return RuntimeStatus.NOT_INSTALLED

    async def get_capabilities(self) -> RuntimeCapability:
        """Ollama is free, local, moderate capability across the board."""
        return RuntimeCapability(
            complex_reasoning=6.0,
            code_generation=6.5,
            code_editing=5.0,
            file_operations=2.0,
            web_research=1.0,
            data_analysis=6.0,
            browser_automation=0.0,
            simple_chat=7.0,
            bulk_operations=3.0,
            cost_per_1k_tokens=0.0,
        )

    async def execute(
        self, task: str, context: dict[str, Any],
    ) -> AsyncIterator[str]:
        """Execute via Ollama chat API with streaming."""
        model = context.get("model", get_settings().ollama_default_model)
        system_prompt = context.get("system_prompt", "You are Daena, a helpful AI assistant.")

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task},
            ],
            "stream": True,
            "keep_alive": "30m",
        }

        try:
            async with self._client.stream(
                "POST", "/api/chat", json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    import orjson
                    chunk = orjson.loads(line)
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content
        except httpx.ConnectError:
            yield "[ERROR] Ollama is offline. Start Ollama and try again."
        except httpx.HTTPStatusError as e:
            yield f"[ERROR] Ollama returned status {e.response.status_code}"

    async def cancel(self, session_id: str) -> bool:
        """Ollama doesn't have persistent sessions to cancel."""
        return False

    def get_auth_requirements(self) -> dict[str, Any]:
        return {
            "type": "local",
            "description": "Ollama runs locally, no auth or subscription required",
            "setup_command": "ollama serve",
            "cost_to_user": "$0 (runs on your hardware)",
            "subscription_plans": [],
        }

    async def check_subscription(self):
        """Ollama is local -- always authenticated if installed."""
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
            setup_command="ollama serve",
        )

    async def close(self) -> None:
        """Clean up HTTP client."""
        await self._client.aclose()
