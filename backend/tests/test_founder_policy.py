"""Tests for founder routing policy CRUD + routing override behavior."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient

from app.core.constants import HealthStatus, ModelProvider, RoutingMode
from app.services.model_router import ModelRouter
from app.services.providers.base import ModelInfo
from app.services.query_understanding import (
    ComplexityLabel,
    IntentType,
    QueryUnderstanding,
    RiskLevel,
)

# ── Helpers ──


async def _register_founder(client: AsyncClient) -> dict:
    """Register a FOUNDER user and return auth headers."""
    unique = uuid.uuid4().hex[:8]
    email = f"founder-{unique}@example.com"

    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "display_name": "Policy Founder",
            "tenant_name": f"PolicyOrg-{unique}",
        },
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePass123!"},
    )
    data = login_resp.json()["data"]
    return {
        "token": data["access_token"],
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
        "user": data["user"],
    }


def _build_registry(*models: ModelInfo):
    """Build a mock model registry with the given models."""
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
    registry.get_provider.side_effect = (
        lambda provider: registry._providers.get(provider)
    )
    registry.get_health.side_effect = lambda provider: registry._health_cache.get(
        provider,
        HealthStatus.UNAVAILABLE,
    )
    return registry


def _make_qu(intent: IntentType = IntentType.CODING) -> QueryUnderstanding:
    return QueryUnderstanding(
        intent=intent,
        confidence=0.9,
        complexity_score=0.5,
        complexity_label=ComplexityLabel.MODERATE,
        risk_level=RiskLevel.LOW,
        governance_tier=1,
        suggested_mode=RoutingMode.STANDARD,
        suggested_providers=[ModelProvider.OLLAMA],
        ambiguity_signals=[],
        clarifying_question=None,
        processing_time_ms=1,
    )


# ── API Endpoint Tests ──


@pytest.mark.asyncio
async def test_get_policy_defaults(client: AsyncClient) -> None:
    """GET /founder/routing/policy returns defaults for new tenant."""
    auth = await _register_founder(client)
    resp = await client.get(
        "/api/v1/founder/routing/policy",
        headers=auth["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["preferred_models"] == {}
    assert data["blocked_models"] == []
    assert data["cost_ceiling"] is None
    assert data["enforce_local_only"] is False


@pytest.mark.asyncio
async def test_put_policy_creates_and_updates(client: AsyncClient) -> None:
    """PUT /founder/routing/policy creates then merges policy."""
    auth = await _register_founder(client)

    # Create
    resp1 = await client.put(
        "/api/v1/founder/routing/policy",
        json={
            "preferred_models": {"CODING": "deepseek-r1:14b"},
            "blocked_models": ["gpt-4o-mini"],
            "cost_ceiling": 0.50,
        },
        headers=auth["headers"],
    )
    assert resp1.status_code == 200
    data1 = resp1.json()["data"]
    assert data1["preferred_models"] == {"CODING": "deepseek-r1:14b"}
    assert data1["blocked_models"] == ["gpt-4o-mini"]
    assert data1["cost_ceiling"] == 0.50
    assert data1["id"] is not None

    # Update (merge -- add enforce_local_only, keep existing fields)
    resp2 = await client.put(
        "/api/v1/founder/routing/policy",
        json={"enforce_local_only": True},
        headers=auth["headers"],
    )
    data2 = resp2.json()["data"]
    assert data2["enforce_local_only"] is True
    # Previous fields preserved
    assert data2["preferred_models"] == {"CODING": "deepseek-r1:14b"}
    assert data2["blocked_models"] == ["gpt-4o-mini"]


@pytest.mark.asyncio
async def test_reset_policy(client: AsyncClient) -> None:
    """POST /founder/routing/policy/reset clears custom policy."""
    auth = await _register_founder(client)

    # Set a policy
    await client.put(
        "/api/v1/founder/routing/policy",
        json={"blocked_models": ["some-model"], "enforce_local_only": True},
        headers=auth["headers"],
    )

    # Reset
    resp = await client.post(
        "/api/v1/founder/routing/policy/reset",
        headers=auth["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["blocked_models"] == []
    assert data["enforce_local_only"] is False

    # Confirm GET also shows defaults
    get_resp = await client.get(
        "/api/v1/founder/routing/policy",
        headers=auth["headers"],
    )
    assert get_resp.json()["data"]["blocked_models"] == []


# ── Router Override Behavior Tests ──


class TestFounderPolicyRouting:
    """Tests for ModelRouter.route() with founder_policy."""

    def _models(self) -> list[ModelInfo]:
        return [
            ModelInfo(
                model_id="deepseek-r1:14b",
                provider=ModelProvider.OLLAMA,
                display_name="DeepSeek R1 14B",
                context_window=32768,
                tags=["reasoning", "analysis", "large"],
            ),
            ModelInfo(
                model_id="llama3.1:latest",
                provider=ModelProvider.OLLAMA,
                display_name="Llama 3.1",
                context_window=8192,
                tags=["chat", "fast"],
            ),
            ModelInfo(
                model_id="gpt-4o",
                provider=ModelProvider.OPENAI,
                display_name="GPT-4o",
                context_window=128000,
                cost_per_1m_input=5.0,
                cost_per_1m_output=15.0,
                tags=["analysis", "creative", "coding"],
            ),
        ]

    def test_preferred_model_override(self) -> None:
        """Founder preferred_models forces selection for matching intent."""
        registry = _build_registry(*self._models())
        router = ModelRouter(registry)
        qu = _make_qu(IntentType.CODING)

        decision = router.route(
            qu,
            founder_policy={
                "preferred_models": {"CODING": "llama3.1:latest"},
            },
        )
        assert decision.primary.model_id == "llama3.1:latest"
        assert decision.metadata["selection_reason"] == "founder_policy_override"

    def test_blocked_models_filtered(self) -> None:
        """Blocked models are excluded from candidates."""
        registry = _build_registry(*self._models())
        router = ModelRouter(registry)
        qu = _make_qu(IntentType.ANALYSIS)

        decision = router.route(
            qu,
            founder_policy={
                "blocked_models": ["deepseek-r1:14b"],
            },
        )
        # deepseek-r1:14b should not be selected
        assert decision.primary.model_id != "deepseek-r1:14b"

    def test_enforce_local_only(self) -> None:
        """enforce_local_only filters out cloud providers."""
        registry = _build_registry(*self._models())
        router = ModelRouter(registry)
        qu = _make_qu(IntentType.ANALYSIS)

        decision = router.route(
            qu,
            founder_policy={"enforce_local_only": True},
        )
        # Only Ollama models should survive
        assert decision.primary.provider == ModelProvider.OLLAMA

    def test_cost_ceiling_filters_expensive(self) -> None:
        """cost_ceiling removes models above the threshold."""
        registry = _build_registry(*self._models())
        router = ModelRouter(registry)
        qu = _make_qu(IntentType.CREATIVE)

        decision = router.route(
            qu,
            founder_policy={"cost_ceiling": 1.0},
        )
        # GPT-4o costs $20/1M total, should be filtered
        assert decision.primary.model_id != "gpt-4o"

    def test_no_policy_uses_default_routing(self) -> None:
        """Without policy, routing proceeds as normal."""
        registry = _build_registry(*self._models())
        router = ModelRouter(registry)
        qu = _make_qu(IntentType.CODING)

        decision = router.route(qu, founder_policy=None)
        assert decision.primary is not None
        assert "founder_policy_override" not in (
            decision.metadata.get("selection_reason") or ""
        )

    def test_preferred_model_unavailable_falls_through(self) -> None:
        """If preferred model is not in registry, scoring continues."""
        registry = _build_registry(*self._models())
        router = ModelRouter(registry)
        qu = _make_qu(IntentType.CODING)

        decision = router.route(
            qu,
            founder_policy={
                "preferred_models": {"CODING": "nonexistent-model:7b"},
            },
        )
        # Should still get a valid decision (not crash)
        assert decision.primary is not None
        assert decision.metadata.get("selection_reason") != "founder_policy_override"
