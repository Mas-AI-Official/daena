"""Model Registry — central catalog of all LLM providers and models.

Responsibilities:
    1. Lazy provider instantiation (only when API key is configured)
    2. Periodic health-check cache (avoids hammering APIs)
    3. Unified model catalog across all providers
    4. Provider lookup by enum or model_id

The registry is a singleton (one per process).  FastAPI's lifespan
creates it at startup and tears it down on shutdown.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.config import get_settings
from app.core.constants import HealthStatus, ModelProvider
from app.core.logging import get_logger
from app.services.providers.base import BaseProvider, ModelInfo

logger = get_logger(__name__)

# Provider enum → (import path, class name, config key for API key)
_PROVIDER_MAP: dict[ModelProvider, tuple[str, str, str]] = {
    ModelProvider.OLLAMA: (
        "app.services.providers.ollama", "OllamaProvider", "ollama_base_url",
    ),
    ModelProvider.ANTHROPIC: (
        "app.services.providers.anthropic", "AnthropicProvider", "anthropic_api_key",
    ),
    ModelProvider.OPENAI: (
        "app.services.providers.openai", "OpenAIProvider", "openai_api_key",
    ),
    ModelProvider.GEMINI: (
        "app.services.providers.gemini", "GeminiProvider", "gemini_api_key",
    ),
    ModelProvider.GROQ: (
        "app.services.providers.groq", "GroqProvider", "groq_api_key",
    ),
    ModelProvider.OPENROUTER: (
        "app.services.providers.openrouter", "OpenRouterProvider", "openrouter_api_key",
    ),
    ModelProvider.PERPLEXITY: (
        "app.services.providers.perplexity", "PerplexityProvider", "perplexity_api_key",
    ),
    ModelProvider.TOGETHER: (
        "app.services.providers.together", "TogetherProvider", "together_api_key",
    ),
    ModelProvider.VLLM: (
        "app.services.providers.vllm", "VLLMProvider", "vllm_base_url",
    ),
}

_PROVIDER_DISPLAY_NAMES: dict[ModelProvider, str] = {
    ModelProvider.OLLAMA: "Ollama",
    ModelProvider.PERPLEXITY: "Perplexity",
    ModelProvider.ANTHROPIC: "Anthropic",
    ModelProvider.OPENAI: "OpenAI",
    ModelProvider.GEMINI: "Google Gemini",
    ModelProvider.OPENROUTER: "OpenRouter",
    ModelProvider.TOGETHER: "Together",
    ModelProvider.GROQ: "Groq",
    ModelProvider.VLLM: "vLLM",
}

_PROVIDER_KINDS: dict[ModelProvider, str] = {
    ModelProvider.OLLAMA: "local",
    ModelProvider.PERPLEXITY: "cloud",
    ModelProvider.ANTHROPIC: "cloud",
    ModelProvider.OPENAI: "cloud",
    ModelProvider.GEMINI: "cloud",
    ModelProvider.OPENROUTER: "cloud",
    ModelProvider.TOGETHER: "cloud",
    ModelProvider.GROQ: "cloud",
    ModelProvider.VLLM: "local",
}


class ModelRegistry:
    """Central catalog of providers and models.

    Usage::

        registry = ModelRegistry()
        await registry.initialize()          # instantiate available providers
        provider = registry.get_provider(ModelProvider.ANTHROPIC)
        models = await registry.list_all_models()
        await registry.close()               # cleanup on shutdown
    """

    def __init__(self) -> None:
        self._providers: dict[ModelProvider, BaseProvider] = {}
        self._model_cache: dict[str, ModelInfo] = {}
        self._model_cache_ts: float = 0.0  # monotonic timestamp of last refill
        self._health_cache: dict[ModelProvider, HealthStatus] = {}
        self._initialized = False
        self._snapshot_cache: dict[str, Any] | None = None
        self._snapshot_cache_ts: float = 0.0
        # TTL for the model catalog. Short enough that a user who
        # runs ``ollama pull <model>`` mid-session sees the new model
        # within ~60s (also applies to CLI runtimes coming/going),
        # long enough that dashboard polling doesn't hammer every
        # provider's /models endpoint. Override with force_refresh.
        self._MODEL_CACHE_TTL_SECONDS: float = 60.0

    async def initialize(self) -> None:
        """Instantiate providers that have valid credentials configured."""
        if self._initialized:
            return

        settings = get_settings()
        for provider_enum, (module_path, class_name, config_key) in _PROVIDER_MAP.items():
            # Ollama has a dedicated kill switch: the user migrated to
            # llama.cpp llama-server (vLLM adapter on :8080). Skip the
            # Ollama registration entirely when OLLAMA_ENABLED=false so
            # the "no models" / "list_models_failed" warnings disappear
            # and the router never picks an Ollama slot.
            if (
                provider_enum == ModelProvider.OLLAMA
                and not getattr(settings, "ollama_enabled", False)
            ):
                logger.debug(
                    "provider.skipped",
                    provider=provider_enum.value,
                    reason="ollama_enabled=false",
                )
                continue

            config_value = getattr(settings, config_key, "")
            if not config_value:
                logger.debug("provider.skipped", provider=provider_enum.value, reason="no_key")
                continue

            try:
                instance = self._instantiate(module_path, class_name)
                self._providers[provider_enum] = instance
                logger.info("provider.registered", provider=provider_enum.value)
            except Exception:
                logger.exception("provider.init_failed", provider=provider_enum.value)

        # CLI runtime providers: use subscription auth (no API key needed).
        # Auto-register for any provider slot that has no API key configured
        # but DOES have an installed CLI binary. This allows Claude Code,
        # Codex, and Gemini CLI to participate in Council/QE as proper providers.
        try:
            from app.services.providers.claude_cli import ALL_CLI_SPECS, CliProvider

            for spec in ALL_CLI_SPECS:
                try:
                    cli_provider = CliProvider(spec)
                    health = await cli_provider.health_check()
                    if health != HealthStatus.HEALTHY:
                        continue

                    if spec.provider in self._providers:
                        # API-key provider already has this slot.
                        # Store CLI provider as secondary source so
                        # Quintessence debates can use the CLI subscription
                        # model (Pro/Max tier) alongside the API-key model.
                        if not hasattr(self, "_cli_providers"):
                            self._cli_providers: dict = {}
                        self._cli_providers[spec.runtime_id] = cli_provider
                        # NOTE: CLI model is added to _model_cache AFTER
                        # list_all_models() runs (see below). Adding it here
                        # would cause list_all_models() to return early.
                        logger.info(
                            "provider.cli_coregistered",
                            provider=spec.provider.value,
                            via=f"{spec.runtime_id}_cli",
                            note="CLI subscription model registered as secondary",
                        )
                    else:
                        self._providers[spec.provider] = cli_provider
                        logger.info(
                            "provider.registered",
                            provider=spec.provider.value,
                            via=f"{spec.runtime_id}_cli",
                        )
                except Exception:
                    logger.debug(
                        "provider.cli_init_failed",
                        runtime=spec.runtime_id,
                        exc_info=True,
                    )
        except Exception:
            logger.debug("provider.cli_import_failed", exc_info=True)

        self._initialized = True
        logger.info(
            "registry.initialized",
            available=len(self._providers),
            total=len(_PROVIDER_MAP),
        )

        # Populate model catalog and health caches so ModelRouter
        # has data on first request (without this, _model_cache and
        # _health_cache stay empty and the router finds zero candidates).
        if self._providers:
            await self.list_all_models()
            await self.refresh_health()

        # Add CLI subscription models to cache AFTER list_all_models().
        # These are sovereign-tier models (Opus 4.6, Gemini 3.1 Pro, Codex 5.4)
        # that should participate in Quintessence debates alongside API models.
        if hasattr(self, "_cli_providers"):
            from app.services.providers.base import ModelInfo
            from app.services.providers.claude_cli import ALL_CLI_SPECS
            for spec in ALL_CLI_SPECS:
                if spec.runtime_id in self._cli_providers:
                    self._model_cache[spec.model_id] = ModelInfo(
                        model_id=spec.model_id,
                        provider=spec.provider,
                        display_name=spec.display_name,
                        context_window=spec.context_window,
                        tags=list(spec.tags),
                        cost_per_1m_input=0.0,
                        cost_per_1m_output=0.0,
                    )
                    logger.info(
                        "registry.cli_model_cached",
                        model_id=spec.model_id,
                        provider=spec.provider.value,
                    )

    def get_provider(self, provider: ModelProvider) -> BaseProvider | None:
        """Get an instantiated provider, or None if unavailable."""
        return self._providers.get(provider)

    def get_provider_for_model(self, model_id: str) -> BaseProvider | None:
        """Find which provider serves a given model_id.

        CLI models (claude-code-cli, codex-cli, gemini-cli) resolve to
        their CLI provider even when an API-key provider holds the same
        provider slot. This ensures subscription models use subscription auth.
        """
        # Check CLI providers first for CLI model IDs
        if hasattr(self, "_cli_providers") and model_id.endswith("-cli"):
            for _rt_id, _cli_prov in self._cli_providers.items():
                if hasattr(_cli_prov, "_spec") and _cli_prov._spec.model_id == model_id:
                    return _cli_prov

        info = self._model_cache.get(model_id)
        if info:
            return self._providers.get(info.provider)
        # Fallback: check each provider's catalog
        for provider in self._providers.values():
            for m_id in self._model_cache:
                cached = self._model_cache[m_id]
                if cached.provider == provider.provider and cached.model_id == model_id:
                    return provider
        return None

    @property
    def available_providers(self) -> list[ModelProvider]:
        """List of providers that are instantiated and configured."""
        return list(self._providers.keys())

    async def list_all_models(self, *, force_refresh: bool = False) -> list[ModelInfo]:
        """Aggregate model catalogs from all available providers.

        TTL-cached so that installing/removing a local Ollama model or
        connecting a new CLI runtime shows up within the configured
        window (``_MODEL_CACHE_TTL_SECONDS``). Pass ``force_refresh``
        from UI refresh buttons / periodic schedulers to skip the
        cache entirely.
        """
        import time as _time

        now = _time.monotonic()
        cache_age = now - self._model_cache_ts
        cache_expired = cache_age >= self._MODEL_CACHE_TTL_SECONDS

        if force_refresh or cache_expired:
            self._model_cache.clear()
        elif self._model_cache:
            return list(self._model_cache.values())

        all_models: list[ModelInfo] = []
        tasks: list[tuple[ModelProvider, asyncio.Task[list[ModelInfo]]]] = []
        for name, provider in self._providers.items():
            task = asyncio.create_task(provider.list_models())
            tasks.append((name, task))

        for name, task in tasks:
            try:
                models = await task
                for m in models:
                    self._model_cache[m.model_id] = m
                all_models.extend(models)
            except Exception:
                logger.exception("registry.list_models_failed", provider=name.value)

        self._model_cache_ts = now
        return all_models

    def get_model_info(self, model_id: str) -> ModelInfo | None:
        """Look up cached model info by ID."""
        return self._model_cache.get(model_id)

    async def refresh_health(self) -> dict[ModelProvider, HealthStatus]:
        """Run health checks on all providers concurrently."""
        tasks: dict[ModelProvider, asyncio.Task[HealthStatus]] = {}
        for name, provider in self._providers.items():
            tasks[name] = asyncio.create_task(provider.health_check())

        for name, task in tasks.items():
            try:
                self._health_cache[name] = await task
            except Exception:
                self._health_cache[name] = HealthStatus.UNAVAILABLE
                logger.exception("registry.health_failed", provider=name.value)

        return dict(self._health_cache)

    def get_health(self, provider: ModelProvider) -> HealthStatus:
        """Last known health status for a provider."""
        return self._health_cache.get(provider, HealthStatus.UNAVAILABLE)

    @property
    def health_summary(self) -> dict[str, Any]:
        """Structured health report for API responses."""
        return {
            p.value: {
                "status": self._health_cache.get(p, HealthStatus.UNAVAILABLE).value,
                "available": p in self._providers,
            }
            for p in ModelProvider
        }

    async def close(self) -> None:
        """Shutdown all provider HTTP clients."""
        for name, provider in self._providers.items():
            try:
                await provider.close()
            except Exception:
                logger.exception("registry.close_failed", provider=name.value)
        self._providers.clear()
        self._model_cache.clear()
        self._health_cache.clear()
        self._initialized = False

    async def snapshot(self, *, force_refresh: bool = False) -> dict[str, Any]:
        """Return a frontend-friendly registry snapshot.

        Caches the full snapshot dict for 60 seconds. Only
        force_refresh=True bypasses the cache (explicit user action).
        """
        import time as _time

        now = _time.monotonic()
        if (
            not force_refresh
            and hasattr(self, "_snapshot_cache")
            and self._snapshot_cache is not None
            and (now - self._snapshot_cache_ts) < 60.0
        ):
            return self._snapshot_cache

        settings = get_settings()
        models = await self.list_all_models(force_refresh=force_refresh)
        if force_refresh:
            await self.refresh_health()

        model_payloads: list[dict[str, Any]] = []
        model_counts: dict[ModelProvider, int] = {
            provider: 0 for provider in ModelProvider
        }

        for info in models:
            health = self.get_health(info.provider)
            selectable = health != HealthStatus.UNAVAILABLE
            model_counts[info.provider] += 1
            model_payloads.append(
                {
                    "model_id": info.model_id,
                    "display_name": info.display_name or info.model_id,
                    "provider": info.provider.value,
                    "provider_display_name": _PROVIDER_DISPLAY_NAMES[info.provider],
                    "kind": _PROVIDER_KINDS[info.provider],
                    "installed": info.provider == ModelProvider.OLLAMA,
                    "configured": self.is_configured(info.provider),
                    "reachable": selectable,
                    "selectable": selectable,
                    "availability_reason": self._model_reason(health),
                    "context_window": info.context_window,
                    "supports_streaming": info.supports_streaming,
                    "supports_vision": info.supports_vision,
                    "supports_tools": info.supports_tools,
                    "cost_per_1m_input": info.cost_per_1m_input,
                    "cost_per_1m_output": info.cost_per_1m_output,
                    "tags": info.tags,
                    "is_default": (
                        info.provider == ModelProvider.OLLAMA
                        and info.model_id == settings.ollama_default_model
                    ),
                    "source": (
                        "ollama_api"
                        if info.provider == ModelProvider.OLLAMA
                        else "provider_catalog"
                    ),
                }
            )

        model_payloads.sort(
            key=lambda item: (
                item["kind"] != "local",
                not item["selectable"],
                item["provider_display_name"].lower(),
                item["display_name"].lower(),
            )
        )

        provider_payloads: list[dict[str, Any]] = []
        for provider in ModelProvider:
            configured = self.is_configured(provider)
            registered = provider in self._providers
            health = self.get_health(provider)
            model_count = model_counts[provider]
            provider_payloads.append(
                {
                    "provider": provider.value,
                    "display_name": _PROVIDER_DISPLAY_NAMES[provider],
                    "kind": _PROVIDER_KINDS[provider],
                    "configured": configured,
                    "registered": registered,
                    "reachable": health != HealthStatus.UNAVAILABLE,
                    "selectable": (
                        registered
                        and health != HealthStatus.UNAVAILABLE
                        and model_count > 0
                    ),
                    "health": health.value,
                    "model_count": model_count,
                    "reason": self._provider_reason(
                        configured=configured,
                        registered=registered,
                        health=health,
                        model_count=model_count,
                    ),
                }
            )

        selectable_count = sum(1 for item in model_payloads if item["selectable"])

        result = {
            "providers": provider_payloads,
            "models": model_payloads,
            "default_model": settings.ollama_default_model,
            "ollama_base_url": settings.ollama_base_url,
            "summary": {
                "configured_provider_count": sum(
                    1 for provider in ModelProvider if self.is_configured(provider)
                ),
                "registered_provider_count": len(self._providers),
                "healthy_provider_count": sum(
                    1
                    for provider in ModelProvider
                    if self.get_health(provider) == HealthStatus.HEALTHY
                ),
                "selectable_model_count": selectable_count,
                "installed_model_count": sum(
                    1 for item in model_payloads if item["installed"]
                ),
            },
            "routing_modes": {
                "STANDARD": {
                    "truthful": True,
                    "reason": "Standard mode is backed by the live registry snapshot.",
                },
                "COUNCIL": {
                    "truthful": selectable_count >= 2,
                    "reason": (
                        "Active: multi-model synthesis with parallel execution."
                        if selectable_count >= 2
                        else (
                            f"Requires 2+ selectable models, currently {selectable_count}. "
                            "Falls back to Standard."
                        )
                    ),
                },
                "QUINTESSENCE": {
                    "truthful": selectable_count >= 2,
                    "reason": (
                        "Active: expert council with DCP-guided synthesis (3 domains, 15 experts)."
                        if selectable_count >= 2
                        else (
                            f"Requires 2+ selectable models, currently {selectable_count}. "
                            "Falls back to Standard."
                        )
                    ),
                },
            },
        }

        # Cache for 60s
        self._snapshot_cache = result
        self._snapshot_cache_ts = now
        return result

    @staticmethod
    def _instantiate(module_path: str, class_name: str) -> BaseProvider:
        """Import and instantiate a provider class by dotted path."""
        import importlib

        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        return cls()

    @staticmethod
    def _model_reason(health: HealthStatus) -> str:
        if health == HealthStatus.HEALTHY:
            return "Selectable"
        if health == HealthStatus.DEGRADED:
            return "Provider degraded"
        return "Provider unreachable"

    def is_configured(self, provider: ModelProvider) -> bool:
        """Whether the provider has enough config to be instantiated."""
        _, _, config_key = _PROVIDER_MAP[provider]
        return bool(getattr(get_settings(), config_key, ""))

    @staticmethod
    def _provider_reason(
        *,
        configured: bool,
        registered: bool,
        health: HealthStatus,
        model_count: int,
    ) -> str:
        if not configured:
            return "Not configured"
        if not registered:
            return "Configured but failed to initialize"
        if health == HealthStatus.UNAVAILABLE:
            return "Configured but unreachable"
        if model_count == 0:
            return "No models discovered"
        if health == HealthStatus.DEGRADED:
            return "Reachable with degraded health"
        return "Ready"
