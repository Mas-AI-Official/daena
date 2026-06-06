"""Auto-routing cost-control: a HEALTHY local/free model must outrank a
DEGRADED paid provider for ordinary (non-SEARCH) prompts, while preserving
the governed-first behavior for SEARCH/research and complex tasks.

Root cause this guards (2026-06-05, DECISION-023):
  1. query_understanding._INTENT_PROVIDERS suggests OLLAMA (deprecated /
     UNAVAILABLE) as the local provider, never VLLM (the live llama-server),
     so the real local model was never an AUTO candidate -- routing fell to
     paid providers.
  2. provider health was only a sort tiebreaker, never in the score, so a
     DEGRADED paid provider (e.g. Perplexity, 400ing every call, +0.5 priority
     boost) outranked a HEALTHY local model.

Fixes (both in model_router.py):
  A. _collect_candidates always adds configured+HEALTHY LOCAL-tier providers
     (VLLM/OLLAMA) for non-SEARCH intents.
  B. _score_candidates applies a DEGRADED score penalty, skipped for SEARCH.
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


def _registry(model_health: dict[ModelProvider, HealthStatus], *models: ModelInfo):
    reg = MagicMock()
    provs = {m.provider for m in models}
    reg._providers = {p: MagicMock() for p in provs}
    reg._health_cache = {p: model_health.get(p, HealthStatus.HEALTHY) for p in provs}
    reg._model_cache = {m.model_id: m for m in models}
    reg.available_providers = list(provs)
    reg.get_provider.side_effect = lambda p: reg._providers.get(p)
    reg.get_health.side_effect = lambda p: reg._health_cache.get(p, HealthStatus.UNAVAILABLE)
    return reg


def _qu(intent: IntentType, complexity: ComplexityLabel, providers: list[ModelProvider]):
    return QueryUnderstanding(
        intent=intent, confidence=0.9, complexity_score=0.4,
        complexity_label=complexity, risk_level=RiskLevel.LOW, governance_tier=1,
        suggested_mode=RoutingMode.STANDARD, suggested_providers=providers,
        ambiguity_signals=[], clarifying_question=None, processing_time_ms=1,
    )


def _vllm():
    return ModelInfo(model_id="Qwen3-8B-Q4_K_M.gguf", provider=ModelProvider.VLLM,
                     display_name="Qwen3-8B (local)", context_window=8192, tags=["chat"])


def _perplexity():
    # priority-tagged like the real Sonar/Auto model that got the +0.5 boost.
    return ModelInfo(model_id="sonar-pro", provider=ModelProvider.PERPLEXITY,
                     display_name="Sonar Pro", context_window=128000,
                     cost_per_1m_input=1.0, cost_per_1m_output=1.0,
                     tags=["chat", "search", "grounded", "priority"])


def _anthropic():
    return ModelInfo(model_id="claude-sonnet-4", provider=ModelProvider.ANTHROPIC,
                     display_name="Claude Sonnet", context_window=200000,
                     cost_per_1m_input=3.0, cost_per_1m_output=15.0,
                     tags=["chat", "reasoning", "priority"])


def _score_of(decision, provider: ModelProvider) -> float:
    for c in [decision.primary, *decision.fallback_chain]:
        if c.provider == provider:
            return c.score
    return float("-inf")


class TestLocalHealthPreference:
    def test_auto_general_chat_prefers_healthy_local_over_degraded_paid(self):
        """The headline fix: ordinary prompt, only Perplexity suggested (DEGRADED),
        local VLLM is HEALTHY but NOT suggested -> router must still surface VLLM
        (Fix A) and pick it over the degraded paid provider (Fix B)."""
        reg = _registry(
            {ModelProvider.PERPLEXITY: HealthStatus.DEGRADED, ModelProvider.VLLM: HealthStatus.HEALTHY},
            _vllm(), _perplexity(),
        )
        router = ModelRouter(reg)
        # suggested_providers deliberately EXCLUDES VLLM (mirrors the stale map).
        decision = router.route(_qu(IntentType.SIMPLE, ComplexityLabel.MODERATE,
                                     [ModelProvider.PERPLEXITY]))
        assert decision.primary.provider == ModelProvider.VLLM, (
            f"expected healthy local VLLM, got {decision.primary.provider} "
            f"score={decision.primary.score}"
        )

    def test_degraded_paid_stays_in_fallback_chain(self):
        """Degraded provider is demoted, NOT removed -- still available as fallback."""
        reg = _registry(
            {ModelProvider.PERPLEXITY: HealthStatus.DEGRADED, ModelProvider.VLLM: HealthStatus.HEALTHY},
            _vllm(), _perplexity(),
        )
        router = ModelRouter(reg)
        decision = router.route(_qu(IntentType.SIMPLE, ComplexityLabel.MODERATE,
                                    [ModelProvider.PERPLEXITY, ModelProvider.VLLM]))
        providers = [decision.primary.provider, *(c.provider for c in decision.fallback_chain)]
        assert ModelProvider.PERPLEXITY in providers

    def test_search_intent_still_allows_degraded_external(self):
        """Research/web carve-out: SEARCH intent must NOT penalize the (degraded)
        web provider out of primary -- Perplexity can still win for search."""
        reg = _registry(
            {ModelProvider.PERPLEXITY: HealthStatus.DEGRADED, ModelProvider.VLLM: HealthStatus.HEALTHY},
            _vllm(), _perplexity(),
        )
        router = ModelRouter(reg)
        decision = router.route(_qu(IntentType.SEARCH, ComplexityLabel.MODERATE,
                                    [ModelProvider.PERPLEXITY]))
        assert decision.primary.provider == ModelProvider.PERPLEXITY

    def test_complex_task_healthy_sovereign_still_wins_over_local(self):
        """Governed-first preserved: for a COMPLEX task with all providers HEALTHY,
        the sovereign cloud model still beats local (no regression to the tier bias)."""
        reg = _registry(
            {ModelProvider.ANTHROPIC: HealthStatus.HEALTHY, ModelProvider.VLLM: HealthStatus.HEALTHY},
            _vllm(), _anthropic(),
        )
        router = ModelRouter(reg)
        decision = router.route(_qu(IntentType.ANALYSIS, ComplexityLabel.COMPLEX,
                                    [ModelProvider.ANTHROPIC, ModelProvider.VLLM]))
        assert decision.primary.provider == ModelProvider.ANTHROPIC

    def test_auto_ordinary_prefers_healthy_local_over_healthy_external(self):
        """Ordinary prompt, two HEALTHY providers: local VLLM (free) beats an
        external tactical provider (Groq) -- the FREE-tier $0-chat policy. Groq
        is only suggested; Fix A surfaces VLLM and the local-ordinary boost wins."""
        groq = ModelInfo(model_id="llama-3.1-8b-instant", provider=ModelProvider.GROQ,
                         display_name="Llama 3.1 8B", context_window=128000,
                         tags=["chat", "fast"])
        reg = _registry(
            {ModelProvider.GROQ: HealthStatus.HEALTHY, ModelProvider.VLLM: HealthStatus.HEALTHY},
            _vllm(), groq,
        )
        router = ModelRouter(reg)
        decision = router.route(_qu(IntentType.SIMPLE, ComplexityLabel.MODERATE,
                                    [ModelProvider.GROQ]))
        assert decision.primary.provider == ModelProvider.VLLM, (
            f"expected healthy local VLLM, got {decision.primary.provider} "
            f"score={decision.primary.score}"
        )
