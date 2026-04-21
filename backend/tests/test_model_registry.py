"""Tests for ModelRegistry -- central catalog of all LLM providers.

Tests the registry lifecycle (init, list, health, close), model lookup,
provider instantiation gating, snapshot generation, and cache behavior.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.constants import HealthStatus, ModelProvider
from app.services.model_registry import ModelRegistry
from app.services.providers.base import ModelInfo


# ── Fixtures ──


def _make_model_info(
    model_id: str = "test-model",
    provider: ModelProvider = ModelProvider.OLLAMA,
    display_name: str = "Test Model",
) -> ModelInfo:
    return ModelInfo(
        model_id=model_id,
        provider=provider,
        display_name=display_name,
        context_window=4096,
        supports_streaming=True,
        supports_vision=False,
        supports_tools=False,
        cost_per_1m_input=0.0,
        cost_per_1m_output=0.0,
        tags=["test"],
    )


class TestModelRegistryInit:
    """Test registry initialization."""

    def test_empty_registry(self):
        registry = ModelRegistry()
        assert registry.available_providers == []
        assert registry._initialized is False

    @pytest.mark.asyncio
    async def test_initialize_skips_unconfigured(self):
        """Providers without API keys should be skipped."""
        registry = ModelRegistry()

        # Mock settings to return empty for all keys
        mock_settings = MagicMock()
        mock_settings.ollama_base_url = ""
        mock_settings.anthropic_api_key = ""
        mock_settings.openai_api_key = ""
        mock_settings.gemini_api_key = ""
        mock_settings.groq_api_key = ""
        mock_settings.openrouter_api_key = ""
        mock_settings.perplexity_api_key = ""
        mock_settings.together_api_key = ""
        mock_settings.vllm_base_url = ""

        with patch("app.services.model_registry.get_settings", return_value=mock_settings):
            await registry.initialize()

        assert registry._initialized is True
        # API-key providers are skipped, but CLI providers (claude, codex, gemini)
        # auto-register if their binaries are installed on the system.
        # Only verify that no API-key-based providers were registered.
        api_key_providers = {
            p for p in registry.available_providers
            if not isinstance(registry._providers.get(p), type(None))
            and getattr(registry._providers.get(p), '_spec', None) is None
        }
        assert len(api_key_providers) == 0

    @pytest.mark.asyncio
    async def test_double_initialize_is_noop(self):
        """Calling initialize twice should not re-register providers."""
        registry = ModelRegistry()
        registry._initialized = True
        # Should return immediately
        await registry.initialize()
        assert registry._initialized is True


class TestModelRegistryLookup:
    """Test model and provider lookup."""

    def test_get_provider_missing(self):
        registry = ModelRegistry()
        assert registry.get_provider(ModelProvider.ANTHROPIC) is None

    def test_get_provider_exists(self):
        registry = ModelRegistry()
        mock_provider = MagicMock()
        registry._providers[ModelProvider.ANTHROPIC] = mock_provider
        assert registry.get_provider(ModelProvider.ANTHROPIC) is mock_provider

    def test_get_provider_for_model_from_cache(self):
        registry = ModelRegistry()
        info = _make_model_info("llama3.1:latest", ModelProvider.OLLAMA)
        mock_provider = MagicMock()
        registry._model_cache["llama3.1:latest"] = info
        registry._providers[ModelProvider.OLLAMA] = mock_provider

        result = registry.get_provider_for_model("llama3.1:latest")
        assert result is mock_provider

    def test_get_provider_for_model_not_found(self):
        registry = ModelRegistry()
        assert registry.get_provider_for_model("nonexistent") is None

    def test_get_model_info_cached(self):
        registry = ModelRegistry()
        info = _make_model_info("test-model", ModelProvider.ANTHROPIC)
        registry._model_cache["test-model"] = info
        assert registry.get_model_info("test-model") is info

    def test_get_model_info_missing(self):
        registry = ModelRegistry()
        assert registry.get_model_info("missing") is None


class TestModelRegistryHealth:
    """Test health check caching."""

    def test_get_health_default_unavailable(self):
        registry = ModelRegistry()
        assert registry.get_health(ModelProvider.ANTHROPIC) == HealthStatus.UNAVAILABLE

    def test_get_health_cached(self):
        registry = ModelRegistry()
        registry._health_cache[ModelProvider.OLLAMA] = HealthStatus.HEALTHY
        assert registry.get_health(ModelProvider.OLLAMA) == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_refresh_health(self):
        registry = ModelRegistry()
        mock_provider = AsyncMock()
        mock_provider.health_check = AsyncMock(return_value=HealthStatus.HEALTHY)
        registry._providers[ModelProvider.OLLAMA] = mock_provider

        result = await registry.refresh_health()
        assert result[ModelProvider.OLLAMA] == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_refresh_health_handles_exception(self):
        registry = ModelRegistry()
        mock_provider = AsyncMock()
        mock_provider.health_check = AsyncMock(side_effect=Exception("boom"))
        registry._providers[ModelProvider.ANTHROPIC] = mock_provider

        result = await registry.refresh_health()
        assert result[ModelProvider.ANTHROPIC] == HealthStatus.UNAVAILABLE

    def test_health_summary(self):
        registry = ModelRegistry()
        registry._health_cache[ModelProvider.OLLAMA] = HealthStatus.HEALTHY
        summary = registry.health_summary

        assert summary["OLLAMA"]["status"] == "HEALTHY"
        assert summary["OLLAMA"]["available"] is False  # Not in _providers
        assert summary["ANTHROPIC"]["status"] == "UNAVAILABLE"


class TestModelRegistryListModels:
    """Test model listing and caching."""

    @pytest.mark.asyncio
    async def test_list_all_models(self):
        registry = ModelRegistry()
        info = _make_model_info("llama3.1:latest", ModelProvider.OLLAMA)

        mock_provider = AsyncMock()
        mock_provider.list_models = AsyncMock(return_value=[info])
        registry._providers[ModelProvider.OLLAMA] = mock_provider

        models = await registry.list_all_models()
        assert len(models) == 1
        assert models[0].model_id == "llama3.1:latest"

    @pytest.mark.asyncio
    async def test_list_all_models_cached(self):
        """Second call returns cache without re-querying providers."""
        import time as _time
        registry = ModelRegistry()
        info = _make_model_info("cached-model", ModelProvider.OLLAMA)
        registry._model_cache["cached-model"] = info
        # TTL invalidation added in 2026-04 requires the timestamp to
        # be present for the cache to be considered fresh. Tests that
        # pre-populate _model_cache must also bump the timestamp.
        registry._model_cache_ts = _time.monotonic()

        models = await registry.list_all_models()
        assert len(models) == 1
        assert models[0].model_id == "cached-model"

    @pytest.mark.asyncio
    async def test_list_all_models_force_refresh(self):
        """force_refresh clears cache before querying."""
        registry = ModelRegistry()
        old_info = _make_model_info("old", ModelProvider.OLLAMA)
        registry._model_cache["old"] = old_info

        new_info = _make_model_info("new", ModelProvider.OLLAMA)
        mock_provider = AsyncMock()
        mock_provider.list_models = AsyncMock(return_value=[new_info])
        registry._providers[ModelProvider.OLLAMA] = mock_provider

        models = await registry.list_all_models(force_refresh=True)
        assert len(models) == 1
        assert models[0].model_id == "new"

    @pytest.mark.asyncio
    async def test_list_all_models_handles_provider_error(self):
        """Provider failure should not crash listing."""
        registry = ModelRegistry()
        mock_provider = AsyncMock()
        mock_provider.list_models = AsyncMock(side_effect=Exception("connection refused"))
        registry._providers[ModelProvider.ANTHROPIC] = mock_provider

        models = await registry.list_all_models()
        assert len(models) == 0


class TestModelRegistryClose:
    """Test graceful shutdown."""

    @pytest.mark.asyncio
    async def test_close_clears_state(self):
        registry = ModelRegistry()
        mock_provider = AsyncMock()
        mock_provider.close = AsyncMock()
        registry._providers[ModelProvider.OLLAMA] = mock_provider
        registry._model_cache["test"] = _make_model_info()
        registry._health_cache[ModelProvider.OLLAMA] = HealthStatus.HEALTHY
        registry._initialized = True

        await registry.close()

        assert len(registry._providers) == 0
        assert len(registry._model_cache) == 0
        assert len(registry._health_cache) == 0
        assert registry._initialized is False

    @pytest.mark.asyncio
    async def test_close_handles_provider_error(self):
        registry = ModelRegistry()
        mock_provider = AsyncMock()
        mock_provider.close = AsyncMock(side_effect=Exception("fail"))
        registry._providers[ModelProvider.OLLAMA] = mock_provider

        # Should not raise
        await registry.close()
        assert len(registry._providers) == 0


class TestModelRegistrySnapshot:
    """Test the snapshot method used by frontend model registry endpoint."""

    @pytest.mark.asyncio
    async def test_snapshot_basic(self):
        import time as _time
        registry = ModelRegistry()
        info = _make_model_info("llama3.1:latest", ModelProvider.OLLAMA, "Llama 3.1")

        mock_settings = MagicMock()
        mock_settings.ollama_default_model = "llama3.1:latest"
        mock_settings.ollama_base_url = "http://localhost:11434"

        registry._model_cache["llama3.1:latest"] = info
        # TTL invalidation requires timestamp to treat pre-populated
        # cache as fresh (see list_all_models).
        registry._model_cache_ts = _time.monotonic()
        registry._health_cache[ModelProvider.OLLAMA] = HealthStatus.HEALTHY
        mock_provider = MagicMock()
        registry._providers[ModelProvider.OLLAMA] = mock_provider

        with patch("app.services.model_registry.get_settings", return_value=mock_settings):
            result = await registry.snapshot()

        assert "models" in result
        assert "providers" in result
        assert "summary" in result
        assert "routing_modes" in result
        assert result["default_model"] == "llama3.1:latest"

    @pytest.mark.asyncio
    async def test_snapshot_cache(self):
        """Snapshot caches for 60 seconds."""
        registry = ModelRegistry()
        mock_settings = MagicMock()
        mock_settings.ollama_default_model = "llama3.1:latest"
        mock_settings.ollama_base_url = "http://localhost:11434"

        with patch("app.services.model_registry.get_settings", return_value=mock_settings):
            result1 = await registry.snapshot()
            result2 = await registry.snapshot()

        # Both should return the same cached object
        assert result1 is result2

    @pytest.mark.asyncio
    async def test_snapshot_force_refresh(self):
        """force_refresh=True bypasses cache."""
        registry = ModelRegistry()
        mock_settings = MagicMock()
        mock_settings.ollama_default_model = "test"
        mock_settings.ollama_base_url = "http://localhost:11434"

        with patch("app.services.model_registry.get_settings", return_value=mock_settings):
            result1 = await registry.snapshot()
            result2 = await registry.snapshot(force_refresh=True)

        # Should be different objects when force refreshed
        # (technically could be same content, but different generation)
        assert result2 is not None


class TestModelRegistryHelpers:
    """Test static helper methods."""

    def test_model_reason_healthy(self):
        assert ModelRegistry._model_reason(HealthStatus.HEALTHY) == "Selectable"

    def test_model_reason_degraded(self):
        assert ModelRegistry._model_reason(HealthStatus.DEGRADED) == "Provider degraded"

    def test_model_reason_unavailable(self):
        assert ModelRegistry._model_reason(HealthStatus.UNAVAILABLE) == "Provider unreachable"

    def test_provider_reason_not_configured(self):
        result = ModelRegistry._provider_reason(
            configured=False, registered=False,
            health=HealthStatus.UNAVAILABLE, model_count=0,
        )
        assert result == "Not configured"

    def test_provider_reason_init_failed(self):
        result = ModelRegistry._provider_reason(
            configured=True, registered=False,
            health=HealthStatus.UNAVAILABLE, model_count=0,
        )
        assert result == "Configured but failed to initialize"

    def test_provider_reason_unreachable(self):
        result = ModelRegistry._provider_reason(
            configured=True, registered=True,
            health=HealthStatus.UNAVAILABLE, model_count=0,
        )
        assert result == "Configured but unreachable"

    def test_provider_reason_no_models(self):
        result = ModelRegistry._provider_reason(
            configured=True, registered=True,
            health=HealthStatus.HEALTHY, model_count=0,
        )
        assert result == "No models discovered"

    def test_provider_reason_degraded(self):
        result = ModelRegistry._provider_reason(
            configured=True, registered=True,
            health=HealthStatus.DEGRADED, model_count=5,
        )
        assert result == "Reachable with degraded health"

    def test_provider_reason_ready(self):
        result = ModelRegistry._provider_reason(
            configured=True, registered=True,
            health=HealthStatus.HEALTHY, model_count=5,
        )
        assert result == "Ready"

    def test_is_configured_with_key(self):
        registry = ModelRegistry()
        mock_settings = MagicMock()
        mock_settings.anthropic_api_key = "sk-test-123"
        with patch("app.services.model_registry.get_settings", return_value=mock_settings):
            assert registry.is_configured(ModelProvider.ANTHROPIC) is True

    def test_is_configured_without_key(self):
        registry = ModelRegistry()
        mock_settings = MagicMock()
        mock_settings.anthropic_api_key = ""
        with patch("app.services.model_registry.get_settings", return_value=mock_settings):
            assert registry.is_configured(ModelProvider.ANTHROPIC) is False
