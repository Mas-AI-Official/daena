"""Founder routing telemetry and preview tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from app.core.constants import HealthStatus, ModelProvider
from app.models.identity import Tenant
from app.services.audit import AuditService
from app.services.providers.base import ModelInfo


def _build_registry(*models: ModelInfo):
    registry = MagicMock()
    registry._providers = {
        provider: MagicMock()
        for provider in {model.provider for model in models}
    }
    registry._health_cache = {
        provider: HealthStatus.HEALTHY
        for provider in registry._providers
    }
    registry._model_cache = {model.model_id: model for model in models}
    registry.available_providers = list(registry._providers.keys())
    registry.get_provider.side_effect = lambda provider: registry._providers.get(provider)
    registry.get_health.side_effect = lambda provider: registry._health_cache.get(
        provider,
        HealthStatus.UNAVAILABLE,
    )
    registry.get_model_info.side_effect = lambda model_id: registry._model_cache.get(model_id)
    registry.snapshot = AsyncMock(return_value={
        "providers": [
            {
                "provider": provider.value,
                "display_name": provider.value.title(),
                "kind": "local" if provider == ModelProvider.OLLAMA else "cloud",
                "configured": True,
                "registered": True,
                "reachable": True,
                "selectable": True,
                "health": "HEALTHY",
                "model_count": sum(1 for model in models if model.provider == provider),
                "reason": "Ready",
            }
            for provider in registry.available_providers
        ],
        "models": [
            {
                "model_id": model.model_id,
                "display_name": model.display_name or model.model_id,
                "provider": model.provider.value,
                "provider_display_name": model.provider.value.title(),
                "kind": "local" if model.provider == ModelProvider.OLLAMA else "cloud",
                "installed": model.provider == ModelProvider.OLLAMA,
                "configured": True,
                "reachable": True,
                "selectable": True,
                "availability_reason": "Selectable",
                "context_window": model.context_window,
                "supports_streaming": True,
                "supports_vision": False,
                "supports_tools": False,
                "cost_per_1m_input": model.cost_per_1m_input,
                "cost_per_1m_output": model.cost_per_1m_output,
                "tags": list(model.tags),
                "is_default": model.model_id == "llama3.1:latest",
                "source": "ollama_api" if model.provider == ModelProvider.OLLAMA else "provider_catalog",
            }
            for model in models
        ],
        "default_model": "llama3.1:latest",
        "ollama_base_url": "http://localhost:11434",
        "summary": {
            "configured_provider_count": len(registry.available_providers),
            "registered_provider_count": len(registry.available_providers),
            "healthy_provider_count": len(registry.available_providers),
            "selectable_model_count": len(models),
            "installed_model_count": sum(1 for model in models if model.provider == ModelProvider.OLLAMA),
        },
        "routing_modes": {
            "STANDARD": {"truthful": True, "reason": "Registry-backed."},
            "COUNCIL": {"truthful": False, "reason": "Disabled."},
            "QUINTESSENCE": {"truthful": False, "reason": "Disabled."},
        },
    })
    return registry


@pytest.mark.asyncio
async def test_founder_routing_telemetry_returns_registry_and_recent_routes(
    client: AsyncClient,
    app,
    db_session,
    auth_headers: dict[str, str],
    test_tenant_id,
) -> None:
    registry = _build_registry(
        ModelInfo(
            model_id="qwen2.5:14b-instruct",
            provider=ModelProvider.OLLAMA,
            tags=["reasoning", "analysis", "coding"],
        ),
        ModelInfo(
            model_id="deepseek-r1:14b",
            provider=ModelProvider.OLLAMA,
            tags=["reasoning", "analysis", "large"],
        ),
    )
    app.state.model_registry = registry

    db_session.add(
        Tenant(
            id=test_tenant_id,
            name="Test Tenant",
            slug="test-tenant",
            plan="FREE",
            settings={},
        )
    )
    await db_session.flush()

    audit = AuditService(db_session)
    await audit.log_decision(
        tenant_id=test_tenant_id,
        actor_id=None,
        actor_type="USER",
        action_type="LLM_CALL",
        action_params={
            "model": "qwen2.5:14b-instruct",
            "provider": "OLLAMA",
            "intent": "CODING",
            "requested_routing_mode": "STANDARD",
            "applied_routing_mode": "STANDARD",
            "routing_source": "auto_routed",
            "selection_reason": "Selected for coding.",
            "top_candidates": [
                {"model_id": "qwen2.5:14b-instruct", "provider": "OLLAMA", "score": 0.91},
            ],
            "latency_ms": 412,
        },
        result="COMPLETED",
        risk_level="LOW",
        governance_tier=1,
    )

    response = await client.get(
        "/api/v1/founder/routing/telemetry",
        headers=auth_headers,
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["registry"]["summary"]["selectable_model_count"] == 2
    assert payload["trace_summary"]["total_routes"] == 1
    assert payload["trace_summary"]["by_provider"]["OLLAMA"] == 1
    assert payload["recent_routes"][0]["model"] == "qwen2.5:14b-instruct"


@pytest.mark.asyncio
async def test_founder_routing_preview_uses_live_reasoning_model_for_think_mode(
    client: AsyncClient,
    app,
    auth_headers: dict[str, str],
) -> None:
    registry = _build_registry(
        ModelInfo(
            model_id="qwen2.5:14b-instruct",
            provider=ModelProvider.OLLAMA,
            tags=["reasoning", "analysis", "coding"],
        ),
        ModelInfo(
            model_id="deepseek-r1:14b",
            provider=ModelProvider.OLLAMA,
            tags=["reasoning", "analysis", "large"],
        ),
        ModelInfo(
            model_id="llama3.1:latest",
            provider=ModelProvider.OLLAMA,
            tags=["chat", "fast"],
        ),
    )
    app.state.model_registry = registry

    response = await client.post(
        "/api/v1/founder/routing/preview",
        json={
            "message": "Analyze a backend latency regression and reason through likely causes.",
            "routing_mode": "COUNCIL",
            "chat_mode": "CMD",
            "governance_slider": "STANDARD",
            "think_mode": True,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["preview_source"] == "think_mode"
    assert payload["routing"]["applied_mode"] == "STANDARD"
    assert payload["routing"]["primary"]["model_id"] == "deepseek-r1:14b"
    assert "reasoning-capable model" in payload["routing"]["mode_reason"]
