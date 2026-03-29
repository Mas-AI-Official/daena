"""Unit tests for DynamicModelService: runtime LLM provider hot-add.

Pure unit tests with no database, no real API calls.
All provider interactions are mocked via unittest.mock.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.constants import HealthStatus, ModelProvider
from app.services.dynamic_model_service import (
    CONNECTOR_PROVIDER_MAP,
    PROVIDER_CONFIG_KEYS,
    DynamicModelService,
    ProvisionResult,
)
from app.services.providers.base import ModelInfo

# ── Helpers ────────────────────────────────────────────────────


def _make_mock_registry(
    *,
    providers: dict | None = None,
    model_cache: dict | None = None,
    health_cache: dict | None = None,
) -> MagicMock:
    """Build a mock ModelRegistry with controllable internal state."""
    registry = MagicMock()
    registry._providers = providers if providers is not None else {}
    registry._model_cache = model_cache if model_cache is not None else {}
    registry._health_cache = health_cache if health_cache is not None else {}
    registry._snapshot_cache = {"cached": True}
    registry._snapshot_cache_ts = 999.0
    return registry


def _make_model_info(
    model_id: str = "test-model",
    provider: ModelProvider = ModelProvider.ANTHROPIC,
    cost_input: float = 0.0,
    cost_output: float = 0.0,
) -> ModelInfo:
    """Create a ModelInfo for testing."""
    return ModelInfo(
        model_id=model_id,
        provider=provider,
        display_name=model_id,
        cost_per_1m_input=cost_input,
        cost_per_1m_output=cost_output,
    )


# ── Test: CONNECTOR_PROVIDER_MAP coverage ─────────────────────


def test_connector_provider_map_has_all_expected_providers() -> None:
    """Verify the connector map covers all expected cloud providers."""
    expected = {"anthropic", "openai", "google_gemini", "groq", "openrouter", "together", "perplexity"}
    assert set(CONNECTOR_PROVIDER_MAP.keys()) == expected


def test_connector_provider_map_values_are_model_provider_enums() -> None:
    """Every value in the map must be a valid ModelProvider."""
    for value in CONNECTOR_PROVIDER_MAP.values():
        assert isinstance(value, ModelProvider)


# ── Test: PROVIDER_CONFIG_KEYS coverage ───────────────────────


def test_provider_config_keys_covers_all_connector_providers() -> None:
    """Each mapped provider should have a config key entry."""
    for provider_enum in CONNECTOR_PROVIDER_MAP.values():
        assert provider_enum in PROVIDER_CONFIG_KEYS, (
            f"Missing config key for {provider_enum.value}"
        )


# ── Test: ProvisionResult dataclass ───────────────────────────


def test_provision_result_defaults() -> None:
    """ProvisionResult should have sensible defaults."""
    result = ProvisionResult(provider=ModelProvider.OPENAI, success=True)
    assert result.models_discovered == 0
    assert result.health == "UNAVAILABLE"
    assert result.error is None
    assert result.model_ids == []


def test_provision_result_with_values() -> None:
    """ProvisionResult should store all fields correctly."""
    result = ProvisionResult(
        provider=ModelProvider.ANTHROPIC,
        success=True,
        models_discovered=5,
        health="HEALTHY",
        error=None,
        model_ids=["a", "b", "c", "d", "e"],
    )
    assert result.provider == ModelProvider.ANTHROPIC
    assert result.models_discovered == 5
    assert len(result.model_ids) == 5


# ── Test: DynamicModelService.provision_provider ──────────────


@pytest.mark.asyncio
async def test_provision_unknown_provider_returns_error() -> None:
    """Provisioning a provider not in CONNECTOR_PROVIDER_MAP should fail."""
    registry = _make_mock_registry()
    svc = DynamicModelService(registry)

    result = await svc.provision_provider(
        provider_name="nonexistent_provider",
        api_key="sk-test",
    )

    assert result.success is False
    assert "Unknown provider" in (result.error or "")


@pytest.mark.asyncio
async def test_provision_existing_provider_rediscovers_models() -> None:
    """Re-provisioning an already registered provider triggers re-discovery."""
    mock_provider = AsyncMock()
    model_a = _make_model_info("claude-3", ModelProvider.ANTHROPIC)
    model_b = _make_model_info("claude-4", ModelProvider.ANTHROPIC)
    mock_provider.list_models = AsyncMock(return_value=[model_a, model_b])
    mock_provider.health_check = AsyncMock(return_value=HealthStatus.HEALTHY)

    registry = _make_mock_registry(
        providers={ModelProvider.ANTHROPIC: mock_provider},
    )
    svc = DynamicModelService(registry)

    result = await svc.provision_provider(
        provider_name="anthropic",
        api_key="sk-ant-test",
    )

    assert result.success is True
    assert result.models_discovered == 2
    assert result.health == "HEALTHY"
    assert "claude-3" in result.model_ids
    assert "claude-4" in result.model_ids
    # Snapshot should have been invalidated
    assert registry._snapshot_cache is None
    assert registry._snapshot_cache_ts == 0.0


@pytest.mark.asyncio
async def test_provision_existing_provider_error_returns_failure() -> None:
    """Re-provisioning that throws during list_models should return failure."""
    mock_provider = AsyncMock()
    mock_provider.list_models = AsyncMock(side_effect=RuntimeError("API down"))

    registry = _make_mock_registry(
        providers={ModelProvider.OPENAI: mock_provider},
    )
    svc = DynamicModelService(registry)

    result = await svc.provision_provider(
        provider_name="openai",
        api_key="sk-test",
    )

    assert result.success is False
    assert "API down" in (result.error or "")


# ── Test: DynamicModelService.list_provisionable ──────────────


def test_list_provisionable_returns_correct_structure() -> None:
    """list_provisionable should return a list of dicts with required keys."""
    model_a = _make_model_info("claude-3", ModelProvider.ANTHROPIC)
    registry = _make_mock_registry(
        providers={ModelProvider.ANTHROPIC: MagicMock()},
        model_cache={"claude-3": model_a},
    )
    svc = DynamicModelService(registry)

    result = svc.list_provisionable()

    assert isinstance(result, list)
    assert len(result) == len(CONNECTOR_PROVIDER_MAP)

    required_keys = {"provider_name", "provider", "display_name", "kind", "active", "model_count"}
    for entry in result:
        assert required_keys.issubset(entry.keys()), f"Missing keys in {entry}"

    # Anthropic should be active with 1 model
    anthropic_entry = next(e for e in result if e["provider_name"] == "anthropic")
    assert anthropic_entry["active"] is True
    assert anthropic_entry["model_count"] == 1

    # OpenAI should not be active
    openai_entry = next(e for e in result if e["provider_name"] == "openai")
    assert openai_entry["active"] is False
    assert openai_entry["model_count"] == 0


# ── Test: classify_model_tier ─────────────────────────────────


def test_classify_model_tier_local_returns_0() -> None:
    """Ollama (local) models should always be tier 0."""
    registry = _make_mock_registry()
    svc = DynamicModelService(registry)

    model = _make_model_info("llama3.1:8b", ModelProvider.OLLAMA, 0.0, 0.0)
    assert svc.classify_model_tier(model) == 0


def test_classify_model_tier_cheap_cloud_returns_0() -> None:
    """Cloud models with total cost <= $5/M tokens should be tier 0."""
    registry = _make_mock_registry()
    svc = DynamicModelService(registry)

    model = _make_model_info("groq-llama", ModelProvider.GROQ, 0.5, 1.0)
    assert svc.classify_model_tier(model) == 0


def test_classify_model_tier_standard_cloud_returns_1() -> None:
    """Cloud models with total cost $5-$30/M tokens should be tier 1."""
    registry = _make_mock_registry()
    svc = DynamicModelService(registry)

    model = _make_model_info("gpt-4o", ModelProvider.OPENAI, 5.0, 15.0)
    assert svc.classify_model_tier(model) == 1


def test_classify_model_tier_premium_returns_2() -> None:
    """Cloud models with total cost > $30/M tokens should be tier 2."""
    registry = _make_mock_registry()
    svc = DynamicModelService(registry)

    model = _make_model_info("claude-opus", ModelProvider.ANTHROPIC, 15.0, 75.0)
    assert svc.classify_model_tier(model) == 2


# ── Test: remove_provider ─────────────────────────────────────


@pytest.mark.asyncio
async def test_remove_nonexistent_provider_returns_false() -> None:
    """Removing a provider that is not active should return False."""
    registry = _make_mock_registry()
    svc = DynamicModelService(registry)

    result = await svc.remove_provider("anthropic")
    assert result is False


@pytest.mark.asyncio
async def test_remove_unknown_provider_name_returns_false() -> None:
    """Removing an unknown provider name should return False."""
    registry = _make_mock_registry()
    svc = DynamicModelService(registry)

    result = await svc.remove_provider("nonexistent_xyz")
    assert result is False


@pytest.mark.asyncio
async def test_remove_active_provider_cleans_up() -> None:
    """Removing an active provider should clean up providers, health, and model caches."""
    mock_provider = AsyncMock()
    model_a = _make_model_info("claude-3", ModelProvider.ANTHROPIC)
    model_b = _make_model_info("claude-4", ModelProvider.ANTHROPIC)
    model_c = _make_model_info("gpt-4o", ModelProvider.OPENAI)

    registry = _make_mock_registry(
        providers={ModelProvider.ANTHROPIC: mock_provider},
        model_cache={"claude-3": model_a, "claude-4": model_b, "gpt-4o": model_c},
        health_cache={ModelProvider.ANTHROPIC: HealthStatus.HEALTHY},
    )
    svc = DynamicModelService(registry)

    result = await svc.remove_provider("anthropic")

    assert result is True
    assert ModelProvider.ANTHROPIC not in registry._providers
    assert ModelProvider.ANTHROPIC not in registry._health_cache
    # Only Anthropic models removed, OpenAI model preserved
    assert "claude-3" not in registry._model_cache
    assert "claude-4" not in registry._model_cache
    assert "gpt-4o" in registry._model_cache
    mock_provider.close.assert_awaited_once()


# ── Test: refresh_provider ────────────────────────────────────


@pytest.mark.asyncio
async def test_refresh_inactive_provider_returns_error() -> None:
    """Refreshing a provider that is not active should return an error."""
    registry = _make_mock_registry()
    svc = DynamicModelService(registry)

    result = await svc.refresh_provider("anthropic")

    assert result.success is False
    assert "not active" in (result.error or "").lower()


@pytest.mark.asyncio
async def test_refresh_active_provider_updates_models() -> None:
    """Refreshing an active provider should replace its model cache entries."""
    mock_provider = AsyncMock()
    old_model = _make_model_info("claude-old", ModelProvider.ANTHROPIC)
    new_model = _make_model_info("claude-new", ModelProvider.ANTHROPIC)
    mock_provider.health_check = AsyncMock(return_value=HealthStatus.HEALTHY)
    mock_provider.list_models = AsyncMock(return_value=[new_model])

    registry = _make_mock_registry(
        providers={ModelProvider.ANTHROPIC: mock_provider},
        model_cache={"claude-old": old_model},
        health_cache={ModelProvider.ANTHROPIC: HealthStatus.DEGRADED},
    )
    svc = DynamicModelService(registry)

    result = await svc.refresh_provider("anthropic")

    assert result.success is True
    assert result.models_discovered == 1
    assert result.health == "HEALTHY"
    assert "claude-new" in result.model_ids
    # Old model should be gone, new one present
    assert "claude-old" not in registry._model_cache
    assert "claude-new" in registry._model_cache
    assert registry._health_cache[ModelProvider.ANTHROPIC] == HealthStatus.HEALTHY


# ── Test: snapshot invalidation ───────────────────────────────


def test_invalidate_snapshot_clears_cache() -> None:
    """_invalidate_snapshot should reset the registry snapshot cache."""
    registry = _make_mock_registry()
    registry._snapshot_cache = {"some": "data"}
    registry._snapshot_cache_ts = 12345.0

    svc = DynamicModelService(registry)
    svc._invalidate_snapshot()

    assert registry._snapshot_cache is None
    assert registry._snapshot_cache_ts == 0.0
