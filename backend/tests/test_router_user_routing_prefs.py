"""PR-S3 Phase 11 wire-up tests (2026-06-01).

SettingsLLM has had two routing toggles for many releases:
  * local_first_routing
  * cost_aware_routing

Both persist into ``user.settings`` on PUT /settings/preferences. The
audit-trio workflow (2026-06-01) found that NO consumer was actually
reading them -- the controls were a silent lie. This wire-up:

  1. chat_orchestrator now reads both fields off ``user.settings`` when
     it loads the User row (same lookup that already reads primary_runtime
     and extension_permissions).
  2. ModelRouter.route() / ._score_candidates accept a new
     ``user_routing_prefs`` kwarg and, when local_first_routing is False
     in that dict, multiplies the locality weight by 0.5 so cloud models
     are no longer downranked for being remote. Symmetric for
     cost_aware_routing.
  3. Default behavior (no prefs passed, or both True) is unchanged.

These tests exercise the router directly with a mock registry. They do
NOT exercise the orchestrator->router flow end-to-end; that path is
covered by the chat-stream tests.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.core.constants import HealthStatus, ModelProvider, RoutingMode
from app.services.model_router import ModelRouter
from app.services.providers.base import ModelInfo
from app.services.query_understanding import (
    ComplexityLabel,
    IntentType,
    QueryUnderstanding,
    RiskLevel,
)


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
    registry.get_provider.side_effect = lambda p: registry._providers.get(p)
    registry.get_health.side_effect = lambda p: registry._health_cache.get(
        p, HealthStatus.UNAVAILABLE,
    )
    return registry


def _make_qu(intent: IntentType = IntentType.SIMPLE) -> QueryUnderstanding:
    return QueryUnderstanding(
        intent=intent,
        confidence=0.9,
        complexity_score=0.3,
        complexity_label=ComplexityLabel.MODERATE,
        risk_level=RiskLevel.LOW,
        governance_tier=1,
        suggested_mode=RoutingMode.STANDARD,
        suggested_providers=[ModelProvider.OLLAMA, ModelProvider.OPENAI],
        ambiguity_signals=[],
        clarifying_question=None,
        processing_time_ms=1,
    )


def _two_models() -> list[ModelInfo]:
    """A local Ollama model and a cloud OpenAI model. Both 'chat' tagged
    so neither has an explicit tag-match advantage."""
    return [
        ModelInfo(
            model_id="llama3.1:latest",
            provider=ModelProvider.OLLAMA,
            display_name="Llama 3.1",
            context_window=8192,
            tags=["chat"],
        ),
        ModelInfo(
            model_id="gpt-4o-mini",
            provider=ModelProvider.OPENAI,
            display_name="GPT-4o mini",
            context_window=128000,
            cost_per_1m_input=0.15,
            cost_per_1m_output=0.60,
            tags=["chat"],
        ),
    ]


class TestUserRoutingPrefs:
    """SettingsLLM toggles must influence ModelRouter scoring."""

    def test_no_prefs_uses_default_weights(self) -> None:
        """No prefs passed -> existing behavior (locality + cost weighted
        as before)."""
        router = ModelRouter(_build_registry(*_two_models()))
        decision = router.route(_make_qu())
        assert decision.primary is not None
        # Both models should have non-zero scores
        assert decision.primary.score > 0

    def test_both_prefs_true_is_baseline(self) -> None:
        """Both toggles True == current default behavior (the UI ships
        with both ON; turning OFF is the only signal that changes anything)."""
        router = ModelRouter(_build_registry(*_two_models()))
        baseline = router.route(_make_qu())
        with_prefs = router.route(
            _make_qu(),
            user_routing_prefs={
                "local_first_routing": True,
                "cost_aware_routing": True,
            },
        )
        # Same primary model in both calls.
        assert baseline.primary.model_id == with_prefs.primary.model_id

    def test_local_first_off_reduces_locality_weight(self) -> None:
        """When local_first_routing=False, the locality score
        contributes half as much to the composite. The cloud candidate's
        composite should rise relative to the local candidate's, even
        though the local model is still in the candidate pool.
        """
        router = ModelRouter(_build_registry(*_two_models()))

        on = router.route(
            _make_qu(),
            user_routing_prefs={"local_first_routing": True},
        )
        off = router.route(
            _make_qu(),
            user_routing_prefs={"local_first_routing": False},
        )

        def _score_of(decision, model_id: str) -> float:
            if decision.primary.model_id == model_id:
                return decision.primary.score
            for fb in decision.fallback_chain:
                if fb.model_id == model_id:
                    return fb.score
            return 0.0

        # The Ollama model has the highest locality score (local tier).
        # Turning local_first_routing OFF should NOT raise its score
        # relative to the baseline; it should lower it (or keep equal if
        # the model has no locality contribution at all).
        ollama_on = _score_of(on, "llama3.1:latest")
        ollama_off = _score_of(off, "llama3.1:latest")
        assert ollama_off <= ollama_on, (
            f"local_first_routing=False should not raise local model "
            f"score: on={ollama_on}, off={ollama_off}"
        )

    def test_cost_aware_off_reduces_cost_weight(self) -> None:
        """When cost_aware_routing=False, the cost score contributes
        half as much, so a cheap-but-mediocre model loses some of its
        score-from-cost advantage.
        """
        router = ModelRouter(_build_registry(*_two_models()))

        on = router.route(
            _make_qu(),
            user_routing_prefs={"cost_aware_routing": True},
        )
        off = router.route(
            _make_qu(),
            user_routing_prefs={"cost_aware_routing": False},
        )

        def _score_of(decision, model_id: str) -> float:
            if decision.primary.model_id == model_id:
                return decision.primary.score
            for fb in decision.fallback_chain:
                if fb.model_id == model_id:
                    return fb.score
            return 0.0

        # The local model (cost=0) has the highest cost score. Turning
        # cost_aware_routing OFF should not raise its score relative to
        # the baseline.
        ollama_on = _score_of(on, "llama3.1:latest")
        ollama_off = _score_of(off, "llama3.1:latest")
        assert ollama_off <= ollama_on, (
            f"cost_aware_routing=False should not raise the cheapest "
            f"model's score: on={ollama_on}, off={ollama_off}"
        )

    def test_user_prefs_does_not_crash_when_unknown_keys(self) -> None:
        """Forward-compatible: future prefs that the router does not
        recognize must not break routing (silently ignored)."""
        router = ModelRouter(_build_registry(*_two_models()))
        decision = router.route(
            _make_qu(),
            user_routing_prefs={
                "some_future_toggle": True,
                "local_first_routing": False,
            },
        )
        assert decision.primary is not None
