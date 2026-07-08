"""BUILD-NOW #2 gate: local runtime resurrection (vllm-first).

Locks three facts:
- select_runtime reaches vllm when cloud adapters are offline, including
  via the hardcoded local-fallback step (previously ollama-only).
- execute_with_fallback tries vllm (before ollama) in its priority chain.
- Settings default vllm_base_url points at the local llama-server
  (127.0.0.1:8080/v1) and .env.example documents all six new keys.
"""

from pathlib import Path

import pytest

from app.core.config import Settings
from app.services.runtimes.base_adapter import (
    BaseRuntimeAdapter,
    RuntimeCapability,
    RuntimeStatus,
)
from app.services.runtimes.registry import RuntimeRegistry

ENV_EXAMPLE = Path(__file__).resolve().parents[1] / ".env.example"

ENV_KEYS = (
    "VLLM_BASE_URL",
    "LLAMA_SERVER_MANAGED",
    "OLLAMA_ENABLED",
    "VAPID_PUBLIC_KEY",
    "VAPID_PRIVATE_KEY",
    "VAPID_SUBJECT",
)


class FakeAdapter(BaseRuntimeAdapter):
    """Minimal adapter with configurable install/health state."""

    def __init__(
        self,
        runtime_id: str,
        installed: bool = True,
        health: RuntimeStatus = RuntimeStatus.ONLINE,
    ):
        super().__init__(runtime_id, f"Fake ({runtime_id})")
        self._installed = installed
        self._health = health

    async def check_installed(self) -> bool:
        return self._installed

    async def check_health(self) -> RuntimeStatus:
        return self._health

    async def get_capabilities(self) -> RuntimeCapability:
        return RuntimeCapability(code_generation=5.0, simple_chat=5.0)

    async def execute(self, task, context):
        yield f"{self.runtime_id} output"

    async def cancel(self, session_id) -> bool:
        return True

    def get_auth_requirements(self):
        return {"type": "none"}


def _registry_clouds_offline_vllm_online() -> RuntimeRegistry:
    registry = RuntimeRegistry()
    for rid in ("claude_code", "codex", "gemini_cli", "grok_cli"):
        registry.register(FakeAdapter(rid, health=RuntimeStatus.OFFLINE))
    registry.register(FakeAdapter("vllm", health=RuntimeStatus.ONLINE))
    registry.register(FakeAdapter("ollama", health=RuntimeStatus.OFFLINE))
    return registry


class TestSelectRuntimeVllm:
    @pytest.mark.asyncio
    async def test_clouds_offline_vllm_online_selects_vllm(self):
        registry = _registry_clouds_offline_vllm_online()
        await registry.discover_all()
        await registry.check_health_all()
        # Must not raise NoRuntimeAvailableError
        assert await registry.select_runtime("code_generation") == "vllm"

    @pytest.mark.asyncio
    async def test_local_fallback_step_reaches_vllm(self):
        registry = _registry_clouds_offline_vllm_online()
        await registry.discover_all()
        await registry.check_health_all()
        # A negative cost ceiling filters every scored runtime (cost >= 0),
        # forcing the hardcoded local-fallback step that was ollama-only.
        selected = await registry.select_runtime(
            "code_generation", cost_ceiling=-1.0
        )
        assert selected == "vllm"


class TestExecuteWithFallbackVllm:
    @pytest.mark.asyncio
    async def test_vllm_in_priority_chain(self):
        registry = RuntimeRegistry()
        registry.register(FakeAdapter("vllm"))
        await registry.discover_all()
        result = await registry.execute_with_fallback("say hi")
        assert result["success"] is True
        assert result["runtime"] == "vllm"

    @pytest.mark.asyncio
    async def test_vllm_tried_before_ollama(self):
        registry = RuntimeRegistry()
        registry.register(FakeAdapter("ollama"))
        registry.register(FakeAdapter("vllm"))
        await registry.discover_all()
        result = await registry.execute_with_fallback("say hi")
        assert result["runtime"] == "vllm"


class TestLocalRuntimeConfig:
    def test_settings_default_vllm_base_url(self):
        # Field default, independent of .env / process env
        default = Settings.model_fields["vllm_base_url"].default
        assert default == "http://127.0.0.1:8080/v1"

    def test_env_example_documents_all_keys(self):
        text = ENV_EXAMPLE.read_text(encoding="utf-8")
        for key in ENV_KEYS:
            assert f"\n{key}=" in text, f".env.example missing {key}="
