"""Dynamic model provisioning: add API keys at runtime, discover models without restart.

When a user connects an LLM provider (e.g. adds an Anthropic API key via the
Connections page), this service:
1. Validates the API key by probing the provider
2. Registers the provider in the live ModelRegistry
3. Discovers available models
4. Auto-classifies models for governance tiers
5. Invalidates the registry snapshot cache so frontend sees updates immediately
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from app.core.constants import HealthStatus, ModelProvider
from app.core.logging import get_logger
from app.services.model_registry import (
    _PROVIDER_DISPLAY_NAMES,
    _PROVIDER_KINDS,
    _PROVIDER_MAP,
    ModelRegistry,
)
from app.services.providers.base import ModelInfo

logger = get_logger(__name__)

# Map connector names to ModelProvider enums
CONNECTOR_PROVIDER_MAP: dict[str, ModelProvider] = {
    "anthropic": ModelProvider.ANTHROPIC,
    "openai": ModelProvider.OPENAI,
    "google_gemini": ModelProvider.GEMINI,
    "groq": ModelProvider.GROQ,
    "openrouter": ModelProvider.OPENROUTER,
    "together": ModelProvider.TOGETHER,
    "perplexity": ModelProvider.PERPLEXITY,
}

# Config key that each provider reads from settings
PROVIDER_CONFIG_KEYS: dict[ModelProvider, str] = {
    ModelProvider.ANTHROPIC: "anthropic_api_key",
    ModelProvider.OPENAI: "openai_api_key",
    ModelProvider.GEMINI: "gemini_api_key",
    ModelProvider.GROQ: "groq_api_key",
    ModelProvider.OPENROUTER: "openrouter_api_key",
    ModelProvider.TOGETHER: "together_api_key",
    ModelProvider.PERPLEXITY: "perplexity_api_key",
}


@dataclass
class ProvisionResult:
    """Result of a dynamic provider provisioning attempt."""

    provider: ModelProvider
    success: bool
    models_discovered: int = 0
    health: str = "UNAVAILABLE"
    error: str | None = None
    model_ids: list[str] = field(default_factory=list)


class DynamicModelService:
    """Hot-add LLM providers at runtime without server restart.

    Usage::

        svc = DynamicModelService(registry)
        result = await svc.provision_provider(
            provider_name="anthropic",
            api_key="sk-ant-...",
        )
        # result.success == True, result.models_discovered == 15
    """

    def __init__(self, registry: ModelRegistry) -> None:
        self._registry = registry

    async def provision_provider(
        self,
        *,
        provider_name: str,
        api_key: str,
    ) -> ProvisionResult:
        """Validate an API key, register the provider, and discover models.

        Steps:
        1. Map provider_name to ModelProvider enum
        2. Temporarily inject the API key into settings
        3. Instantiate the provider
        4. Run health check to validate the key
        5. If healthy, register in the live registry
        6. Discover models
        7. Invalidate snapshot cache
        """
        provider_enum = CONNECTOR_PROVIDER_MAP.get(provider_name.lower())
        if provider_enum is None:
            return ProvisionResult(
                provider=ModelProvider.OLLAMA,  # placeholder for unknown
                success=False,
                error=f"Unknown provider: {provider_name}",
            )

        # Check if already registered
        if provider_enum in self._registry._providers:
            # Re-discover models (key might have changed)
            try:
                provider = self._registry._providers[provider_enum]
                models = await provider.list_models()
                health = await provider.health_check()
                self._registry._health_cache[provider_enum] = health
                # Update model cache
                for m in models:
                    self._registry._model_cache[m.model_id] = m
                self._invalidate_snapshot()
                return ProvisionResult(
                    provider=provider_enum,
                    success=True,
                    models_discovered=len(models),
                    health=health.value,
                    model_ids=[m.model_id for m in models],
                )
            except Exception as exc:
                return ProvisionResult(
                    provider=provider_enum,
                    success=False,
                    error=str(exc),
                )

        # Inject API key into settings dynamically
        from app.core.config import get_settings

        settings = get_settings()
        config_key = PROVIDER_CONFIG_KEYS.get(provider_enum)
        if config_key:
            setattr(settings, config_key, api_key)

        # Instantiate provider
        provider_info = _PROVIDER_MAP.get(provider_enum)
        if not provider_info:
            return ProvisionResult(
                provider=provider_enum,
                success=False,
                error=f"No provider adapter for {provider_enum.value}",
            )

        module_path, class_name, _ = provider_info
        try:
            instance = self._registry._instantiate(module_path, class_name)
        except Exception as exc:
            logger.exception(
                "dynamic_model.instantiate_failed", provider=provider_enum.value
            )
            return ProvisionResult(
                provider=provider_enum,
                success=False,
                error=f"Failed to instantiate provider: {exc}",
            )

        # Validate via health check
        try:
            health = await asyncio.wait_for(instance.health_check(), timeout=10.0)
        except TimeoutError:
            health = HealthStatus.UNAVAILABLE
        except Exception:
            health = HealthStatus.UNAVAILABLE

        if health == HealthStatus.UNAVAILABLE:
            return ProvisionResult(
                provider=provider_enum,
                success=False,
                health=health.value,
                error="Provider health check failed. Verify API key is valid.",
            )

        # Register in live registry
        self._registry._providers[provider_enum] = instance
        self._registry._health_cache[provider_enum] = health

        # Discover models
        try:
            models = await instance.list_models()
            for m in models:
                self._registry._model_cache[m.model_id] = m
        except Exception:
            logger.exception(
                "dynamic_model.discover_failed", provider=provider_enum.value
            )
            models = []

        self._invalidate_snapshot()

        logger.info(
            "dynamic_model.provisioned",
            provider=provider_enum.value,
            models=len(models),
            health=health.value,
        )

        return ProvisionResult(
            provider=provider_enum,
            success=True,
            models_discovered=len(models),
            health=health.value,
            model_ids=[m.model_id for m in models],
        )

    async def remove_provider(self, provider_name: str) -> bool:
        """Remove a dynamically added provider from the live registry."""
        provider_enum = CONNECTOR_PROVIDER_MAP.get(provider_name.lower())
        if not provider_enum or provider_enum not in self._registry._providers:
            return False

        # Close the provider
        provider = self._registry._providers.pop(provider_enum)
        try:
            await provider.close()
        except Exception:
            pass

        # Remove from caches
        self._registry._health_cache.pop(provider_enum, None)
        # Remove associated models
        to_remove = [
            mid
            for mid, info in self._registry._model_cache.items()
            if info.provider == provider_enum
        ]
        for mid in to_remove:
            del self._registry._model_cache[mid]

        self._invalidate_snapshot()

        logger.info("dynamic_model.removed", provider=provider_enum.value)
        return True

    def list_provisionable(self) -> list[dict[str, Any]]:
        """List all providers that can be dynamically added."""
        result = []
        for name, provider_enum in CONNECTOR_PROVIDER_MAP.items():
            is_active = provider_enum in self._registry._providers
            result.append(
                {
                    "provider_name": name,
                    "provider": provider_enum.value,
                    "display_name": _PROVIDER_DISPLAY_NAMES.get(provider_enum, name),
                    "kind": _PROVIDER_KINDS.get(provider_enum, "cloud"),
                    "active": is_active,
                    "model_count": (
                        sum(
                            1
                            for m in self._registry._model_cache.values()
                            if m.provider == provider_enum
                        )
                        if is_active
                        else 0
                    ),
                }
            )
        return result

    async def refresh_provider(self, provider_name: str) -> ProvisionResult:
        """Re-check health and re-discover models for an existing provider."""
        provider_enum = CONNECTOR_PROVIDER_MAP.get(provider_name.lower())
        if not provider_enum or provider_enum not in self._registry._providers:
            return ProvisionResult(
                provider=provider_enum or ModelProvider.OLLAMA,
                success=False,
                error=f"Provider not active: {provider_name}",
            )

        provider = self._registry._providers[provider_enum]
        try:
            health = await provider.health_check()
            models = await provider.list_models()
            self._registry._health_cache[provider_enum] = health
            # Replace old models for this provider
            old_keys = [
                mid
                for mid, info in self._registry._model_cache.items()
                if info.provider == provider_enum
            ]
            for mid in old_keys:
                del self._registry._model_cache[mid]
            for m in models:
                self._registry._model_cache[m.model_id] = m
            self._invalidate_snapshot()
            return ProvisionResult(
                provider=provider_enum,
                success=True,
                models_discovered=len(models),
                health=health.value,
                model_ids=[m.model_id for m in models],
            )
        except Exception as exc:
            return ProvisionResult(
                provider=provider_enum,
                success=False,
                error=str(exc),
            )

    def _invalidate_snapshot(self) -> None:
        """Force the registry snapshot cache to expire."""
        self._registry._snapshot_cache = None
        self._registry._snapshot_cache_ts = 0.0

    def classify_model_tier(self, model_info: ModelInfo) -> int:
        """Auto-classify a model's governance tier based on cost and capabilities.

        Returns governance tier 0-2:
        - 0: Free/local models (no cost concern)
        - 1: Standard cloud models (moderate cost)
        - 2: Premium models (high cost, vision, tools)
        """
        if model_info.provider == ModelProvider.OLLAMA:
            return 0

        total_cost = model_info.cost_per_1m_input + model_info.cost_per_1m_output
        if total_cost > 30.0:  # Premium tier (e.g. GPT-4, Claude Opus)
            return 2
        if total_cost > 5.0:  # Standard cloud
            return 1
        return 0  # Cheap cloud models
