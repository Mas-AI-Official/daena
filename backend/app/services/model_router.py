"""Model Router — selects the best model(s) for a given query understanding.

Bridges QueryUnderstanding (intent → suggested providers) with
ModelRegistry (provider health + model catalog).  Returns a concrete
routing decision: which model to call, with what fallback chain, and
in what execution mode.

Routing algorithm:
    1. Filter suggested providers to those that are *healthy* and
       *available* in the registry.
    2. For each healthy provider, score candidate models by matching
       intent tags, cost efficiency, and context-window fit.
    3. Pick the top model.  For COUNCIL / QUINTESSENCE modes, pick
       multiple models from *different* providers.
    4. Build a fallback chain from remaining healthy providers.
    5. Return a RoutingDecision dataclass.

Performance budget: <10ms (no I/O — all data is in-memory from
ModelRegistry caches and QueryUnderstanding result).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from app.core.constants import (
    HealthStatus,
    ModelProvider,
    RoutingMode,
)
from app.core.logging import get_logger
from app.services.query_understanding import IntentType, QueryUnderstanding

logger = get_logger(__name__)

# ── Runtime routing (V2: EXE mode uses runtimes, not just LLM APIs) ───
# When action_mode == "EXE", the ModelRouter delegates runtime selection
# to the RuntimeRegistry. This keeps the existing LLM routing intact for
# CMD mode while adding runtime routing for EXE mode.

# Fallback model when no candidates survive scoring / health checks.
# Ollama's llama3.1:8b is free, local, and always-on in the Daena stack.
DEFAULT_MODEL = "llama3.1:latest"
DEFAULT_PROVIDER = ModelProvider.OLLAMA

# ── Intent → preferred model tags ──────────────────────────────
# When multiple models are available from the same provider, prefer
# models tagged with these labels.

_INTENT_TAGS: dict[IntentType, list[str]] = {
    IntentType.SIMPLE: ["fast", "small", "chat"],
    IntentType.SEARCH: ["search", "grounded", "chat"],
    IntentType.CODING: ["coding", "code", "developer"],
    IntentType.ANALYSIS: ["reasoning", "analysis", "large"],
    IntentType.CREATIVE: ["creative", "writing", "large"],
    IntentType.MULTI_STEP: ["reasoning", "large", "agentic"],
    IntentType.DANGEROUS: ["reasoning", "large"],
    IntentType.AMBIGUOUS: [],
}

# Suffixes that mark an Ollama model as a cloud-proxied model.
# These cost money and should be deprioritised vs truly local models.
_CLOUD_SUFFIXES = ("-cloud", ":cloud")

# Preferred local model priority — used as tiebreaker when scores are equal.
# Lower index = higher priority.
_PREFERRED_MODELS: list[str] = [
    "deepseek-r1:14b",
    "qwen2.5:14b-instruct",
    "qwen2.5:7b-instruct",
    "glm4:latest",
    "mistral:latest",
    "llama3.1:latest",
]

_MODEL_HINT_TAGS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("deepseek-r1", ("reasoning", "analysis", "large")),
    ("deepseek", ("reasoning", "analysis", "coding")),
    ("qwen3", ("reasoning", "analysis", "chat")),
    ("qwen2.5", ("reasoning", "analysis", "coding")),
    ("qwen", ("reasoning", "analysis", "coding")),
    ("coder", ("coding", "code", "developer")),
    ("code", ("coding", "code", "developer")),
    ("claude", ("analysis", "creative", "coding")),
    ("gpt-oss", ("analysis", "coding")),
    ("gpt", ("analysis", "coding", "creative")),
    ("o1", ("reasoning", "analysis")),
    ("o3", ("reasoning", "analysis")),
    ("gemini", ("analysis", "creative")),
    ("glm", ("analysis", "chat")),
    ("mistral", ("fast", "chat")),
    ("llama", ("chat", "fast")),
    ("gemma", ("small", "fast", "chat")),
    ("phi", ("small", "fast", "coding")),
)

_INTENT_MODEL_HINTS: dict[IntentType, list[str]] = {
    IntentType.SIMPLE: ["mistral", "llama", "gemma", "phi", "qwen"],
    IntentType.SEARCH: ["perplexity", "sonar", "qwen", "llama"],
    IntentType.CODING: ["coder", "qwen", "deepseek", "claude", "gpt", "glm", "llama"],
    IntentType.ANALYSIS: ["deepseek-r1", "qwen", "claude", "gpt", "gemini", "glm", "llama"],
    IntentType.CREATIVE: ["claude", "gpt", "gemini", "llama", "qwen", "mistral"],
    IntentType.MULTI_STEP: ["deepseek-r1", "qwen", "claude", "gpt", "gemini", "glm", "llama"],
    IntentType.DANGEROUS: ["deepseek-r1", "qwen", "claude", "gpt", "gemini", "llama"],
    IntentType.AMBIGUOUS: ["qwen", "deepseek-r1", "llama", "mistral"],
}

_HEALTH_SORT_ORDER: dict[HealthStatus, int] = {
    HealthStatus.HEALTHY: 0,
    HealthStatus.DEGRADED: 1,
    HealthStatus.UNAVAILABLE: 2,
}

# Maximum models for each routing mode
_MODE_MODEL_COUNTS: dict[RoutingMode, int] = {
    RoutingMode.STANDARD: 1,
    RoutingMode.COUNCIL: 3,
    RoutingMode.QUINTESSENCE: 5,
}


# ── Data structures ───────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ModelCandidate:
    """A scored model candidate for routing selection."""

    model_id: str
    provider: ModelProvider
    score: float  # 0.0 – 1.0 composite selection score
    cost_per_1m_input: float = 0.0
    cost_per_1m_output: float = 0.0
    context_window: int = 4096
    tags: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RoutingDecision:
    """Concrete routing decision returned by the router.

    For STANDARD mode: ``primary`` is the single model to call.
    For COUNCIL / QUINTESSENCE: ``council_models`` has 3-5 models
    from different providers.
    """

    mode: RoutingMode
    primary: ModelCandidate
    fallback_chain: list[ModelCandidate] = field(default_factory=list)
    council_models: list[ModelCandidate] = field(default_factory=list)
    routing_time_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Router ────────────────────────────────────────────────────

@dataclass(slots=True)
class RuntimeRoutingDecision:
    """Routing decision for EXE mode: which runtime executes the task.

    Returned by ModelRouter.route_runtime() when action_mode is EXE.
    Includes both the runtime selection and an optional LLM routing
    decision (for runtimes that need an LLM model, like Ollama).
    """
    runtime_id: str
    runtime_display_name: str
    capability_score: float
    fallback_runtime_id: str | None = None
    llm_decision: RoutingDecision | None = None  # for runtimes that need a model
    metadata: dict[str, Any] = field(default_factory=dict)


class ModelRouter:
    """Select the best model(s) for a query understanding result.

    Requires a reference to the ModelRegistry for provider health
    and model catalog lookups.  The registry must be initialised
    before the router is used.

    For EXE mode (V2), also supports runtime selection via an
    optional RuntimeRegistry reference.

    Usage::

        from app.services.model_registry import ModelRegistry

        registry = ModelRegistry()
        await registry.initialize()

        router = ModelRouter(registry)
        decision = router.route(query_understanding)

        # For EXE mode with runtime registry:
        runtime_decision = await router.route_runtime(query_understanding)
    """

    def __init__(self, registry: Any, runtime_registry: Any = None) -> None:
        # Type is Any to avoid circular import; expects ModelRegistry
        self._registry = registry
        # Optional RuntimeRegistry for V2 EXE mode runtime selection
        self._runtime_registry = runtime_registry

    def route(
        self,
        qu: QueryUnderstanding,
        *,
        requested_mode: RoutingMode | None = None,
        preferred_tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        founder_policy: dict[str, Any] | None = None,
        primary_mind: str | None = None,
    ) -> RoutingDecision:
        """Produce a routing decision from a query understanding.

        Steps:
            1. Collect healthy candidate models from suggested providers
            1b. Apply founder policy filters (blocked, cost ceiling, local-only)
            1c. Check for founder preferred-model override by intent
            2. Score each candidate (tag match + cost + context window)
            3. Select primary + fallbacks (STANDARD) or council set
            4. Return RoutingDecision
        """
        start = time.monotonic()
        requested_mode = requested_mode or qu.suggested_mode
        route_metadata = dict(metadata or {})
        preferred_tags = list(preferred_tags or _INTENT_TAGS.get(qu.intent, []))
        policy = founder_policy or {}

        candidates, candidate_metadata = self._collect_candidates(qu)

        # ── Apply founder policy pre-filters ──
        policy_override = self._apply_founder_policy(
            candidates, qu, policy,
        )
        if policy_override is not None:
            # Founder forced a specific model for this intent
            elapsed = self._elapsed(start)
            return RoutingDecision(
                mode=RoutingMode.STANDARD,
                primary=policy_override,
                fallback_chain=candidates[:3],
                routing_time_ms=elapsed,
                metadata={
                    **candidate_metadata,
                    **route_metadata,
                    "intent": qu.intent.value,
                    "requested_mode": requested_mode.value,
                    "applied_mode": RoutingMode.STANDARD.value,
                    "selection_reason": "founder_policy_override",
                    "founder_preferred_model": policy_override.model_id,
                },
            )

        if not candidates:
            # No candidates survived health/cache checks.  Fall back to
            # DEFAULT_MODEL so chat is never broken — the LLM service
            # will still surface an error if even the default is offline.
            fallback = ModelCandidate(
                model_id=DEFAULT_MODEL,
                provider=DEFAULT_PROVIDER,
                score=0.0,
            )
            logger.warning(
                "router.no_candidates_using_default",
                intent=qu.intent.value,
                default_model=DEFAULT_MODEL,
                requested_mode=requested_mode.value,
            )
            return RoutingDecision(
                mode=RoutingMode.STANDARD,
                primary=fallback,
                routing_time_ms=self._elapsed(start),
                metadata={
                    **candidate_metadata,
                    **route_metadata,
                    "intent": qu.intent.value,
                    "requested_mode": requested_mode.value,
                    "applied_mode": RoutingMode.STANDARD.value,
                    "fallback": "default_model",
                    "model": DEFAULT_MODEL,
                    "selection_reason": (
                        "No selectable registry candidates were available; "
                        f"falling back to {DEFAULT_MODEL}."
                    ),
                },
            )

        scored = self._score_candidates(
            candidates,
            qu,
            preferred_tags=preferred_tags,
        )

        # Boost Primary Mind: if user has set a primary runtime and it's in
        # the candidate list, give it a significant score boost so it's selected
        # first (unless founder policy already forced a different model).
        if primary_mind:
            for c in scored:
                if c.model_id == primary_mind or c.provider.value == primary_mind:
                    c.score += 0.5  # Large boost ensures primary mind wins ties
                    route_metadata["primary_mind"] = primary_mind
                    route_metadata["primary_mind_boosted"] = True
                    break
            else:
                route_metadata["primary_mind"] = primary_mind
                route_metadata["primary_mind_available"] = False
                logger.info(
                    "router.primary_mind_unavailable",
                    primary_mind=primary_mind,
                    available_models=[c.model_id for c in scored[:5]],
                )

        # Sort by score desc, then by preferred-model priority (tiebreaker).
        # Models not in _PREFERRED_MODELS get a high index so they sort last.
        _pref_len = len(_PREFERRED_MODELS)
        scored.sort(
            key=lambda c: (
                -c.score,
                self._health_priority(c.provider),
                self._family_priority(c.model_id, qu.intent),
                _PREFERRED_MODELS.index(c.model_id)
                if c.model_id in _PREFERRED_MODELS
                else _pref_len,
                c.cost_per_1m_input + c.cost_per_1m_output,
                c.model_id.lower(),
            ),
        )

        applied_mode = requested_mode
        needed = _MODE_MODEL_COUNTS.get(requested_mode, 1)

        primary = scored[0]
        fallbacks = scored[1:]

        council: list[ModelCandidate] = []
        mode_reason: str | None = None
        if requested_mode in (RoutingMode.COUNCIL, RoutingMode.QUINTESSENCE):
            council = self._select_diverse(scored, needed)
            if len(council) < 2:
                if requested_mode == RoutingMode.QUINTESSENCE:
                    # Quintessence works with 1 model via sequential DCP lenses.
                    # Put the primary model in council_models so the executor
                    # can iterate DCP prompts over it.
                    council = [primary]
                    mode_reason = (
                        "Quintessence: single model detected, will apply DCP expert "
                        "lenses sequentially instead of parallel multi-model."
                    )
                else:
                    applied_mode = RoutingMode.STANDARD
                    council = []
                    mode_reason = (
                        f"{requested_mode.value} requested, but fewer than two distinct "
                        "selectable models were available."
                    )

        elapsed = self._elapsed(start)

        decision = RoutingDecision(
            mode=applied_mode,
            primary=primary,
            fallback_chain=fallbacks[:3],
            council_models=council,
            routing_time_ms=elapsed,
            metadata={
                **candidate_metadata,
                **route_metadata,
                "intent": qu.intent.value,
                "requested_mode": requested_mode.value,
                "applied_mode": applied_mode.value,
                "suggested_providers": [
                    p.value for p in qu.suggested_providers
                ],
                "preferred_tags": preferred_tags,
                "candidates_evaluated": len(scored),
                "top_candidates": [
                    self._serialize_candidate(candidate)
                    for candidate in scored[:5]
                ],
                "selection_reason": self._selection_reason(primary),
            },
        )
        if mode_reason:
            decision.metadata["mode_reason"] = mode_reason

        logger.info(
            "router.decided",
            model=primary.model_id,
            provider=primary.provider.value,
            requested_mode=requested_mode.value,
            applied_mode=applied_mode.value,
            score=round(primary.score, 3),
            fallbacks=len(decision.fallback_chain),
            council=len(council),
            reason=decision.metadata.get("selection_reason"),
            ms=elapsed,
        )
        return decision

    # ── Founder policy application ──────────────────────────────

    def _apply_founder_policy(
        self,
        candidates: list[ModelCandidate],
        qu: QueryUnderstanding,
        policy: dict[str, Any],
    ) -> ModelCandidate | None:
        """Apply founder policy filters to candidates list (in-place).

        Returns a ModelCandidate if the founder forced a specific model
        for this intent (preferred_models override).  Otherwise returns
        None and filtering is applied to the candidates list directly.
        """
        if not policy:
            return None

        # 1. Check for preferred model override by intent
        preferred_models = policy.get("preferred_models") or {}
        intent_key = qu.intent.value
        forced_model_id = preferred_models.get(intent_key)
        if forced_model_id:
            for c in candidates:
                if c.model_id == forced_model_id:
                    logger.info(
                        "router.founder_policy_override",
                        intent=intent_key,
                        forced_model=forced_model_id,
                    )
                    return c
            # Model not available -- log warning, continue with filtering
            logger.warning(
                "router.founder_preferred_model_unavailable",
                intent=intent_key,
                forced_model=forced_model_id,
            )

        # 2. Filter blocked models
        blocked_models = set(policy.get("blocked_models") or [])
        if blocked_models:
            candidates[:] = [
                c for c in candidates
                if c.model_id not in blocked_models
            ]

        # 3. Filter blocked providers
        blocked_providers = {
            p.lower() for p in (policy.get("blocked_providers") or [])
        }
        if blocked_providers:
            candidates[:] = [
                c for c in candidates
                if c.provider.value.lower() not in blocked_providers
            ]

        # 4. Cost ceiling
        cost_ceiling = policy.get("cost_ceiling")
        if cost_ceiling is not None:
            candidates[:] = [
                c for c in candidates
                if (c.cost_per_1m_input + c.cost_per_1m_output) <= cost_ceiling
                or (c.cost_per_1m_input + c.cost_per_1m_output) == 0
            ]

        # 5. Enforce local-only (only Ollama non-cloud models)
        if policy.get("enforce_local_only"):
            candidates[:] = [
                c for c in candidates
                if c.provider == ModelProvider.OLLAMA
                and not any(
                    s in c.model_id.lower() for s in _CLOUD_SUFFIXES
                )
            ]

        return None

    # ── Internal: candidate collection ─────────────────────────

    def _collect_candidates(
        self, qu: QueryUnderstanding,
    ) -> tuple[list[ModelCandidate], dict[str, Any]]:
        """Gather models from healthy suggested providers.

        Only providers that are actually installed/configured (i.e. present in
        the registry) are ever placed into ``providers_considered``.  Providers
        that appear in ``_INTENT_PROVIDERS`` but have no API key configured are
        silently excluded so they never surface in audit logs.
        """
        configured = set(self._registry.available_providers)

        # Keep only suggestions whose provider is actually registered.
        suggested_raw = list(qu.suggested_providers)
        suggested = [p for p in suggested_raw if p in configured]
        provider_strategy = "suggested_providers"
        providers_considered = suggested

        # If no suggestion survives the configuration filter (e.g. AMBIGUOUS,
        # or all suggested providers are unconfigured), fall back to everything
        # that is available.
        if not suggested:
            providers_considered = list(configured)
            provider_strategy = "all_available_providers"

        candidates = self._collect_from_providers(providers_considered)
        # Use the filtered list as the exhaustion sentinel so the fallback
        # only fires when genuinely configured-but-empty, not when every
        # suggestion was unconfigured to begin with.
        if not candidates and suggested:
            providers_considered = list(configured)
            provider_strategy = "all_available_after_suggested_exhausted"
            candidates = self._collect_from_providers(providers_considered)

        return candidates, {
            "provider_strategy": provider_strategy,
            "providers_considered": [provider.value for provider in providers_considered],
        }

    def _collect_from_providers(
        self,
        providers: list[ModelProvider],
    ) -> list[ModelCandidate]:
        candidates: list[ModelCandidate] = []
        for provider_enum in providers:
            # Check health — treat UNKNOWN (never checked) same as HEALTHY
            # so newly registered providers aren't silently skipped.
            health = self._registry.get_health(provider_enum)
            if health == HealthStatus.UNAVAILABLE:
                # Still allow if provider is registered but simply never
                # had a health check (default is UNAVAILABLE).  Only skip
                # if we *actually ran* a check and it failed.
                if provider_enum not in self._registry._health_cache:
                    pass  # proceed — never checked, give it a chance
                else:
                    continue  # genuinely unhealthy, skip

            provider_inst = self._registry.get_provider(provider_enum)
            if provider_inst is None:
                continue

            # Pull models from the registry cache
            for _model_id, info in self._registry._model_cache.items():
                if info.provider == provider_enum:
                    candidates.append(
                        ModelCandidate(
                            model_id=info.model_id,
                            provider=info.provider,
                            score=0.0,
                            cost_per_1m_input=info.cost_per_1m_input,
                            cost_per_1m_output=info.cost_per_1m_output,
                            context_window=info.context_window,
                            tags=self._augment_tags(
                                info.model_id,
                                list(info.tags) if info.tags else [],
                            ),
                        )
                    )

        return candidates

    # ── Internal: scoring ──────────────────────────────────────

    def _score_candidates(
        self,
        candidates: list[ModelCandidate],
        qu: QueryUnderstanding,
        *,
        preferred_tags: list[str] | None = None,
    ) -> list[ModelCandidate]:
        """Score each candidate on tag match, cost, locality, and context.

        Scoring weights:
            - Tag match:      0.40  (does the model suit the intent?)
            - Locality:       0.25  (local > cloud — free and fast)
            - Cost efficiency: 0.20  (lower cost = higher score)
            - Context window:  0.15  (larger window = higher score for
              complex queries, less important for simple ones)
        """
        preferred_tags = list(preferred_tags or _INTENT_TAGS.get(qu.intent, []))

        scored: list[ModelCandidate] = []
        for c in candidates:
            tag_score = self._score_tags(c.tags, preferred_tags)
            cost_score = self._score_cost(c, qu)
            locality_score = self._score_locality(c)
            context_score = self._score_context(c, qu)
            lower_tags = {t.lower() for t in c.tags}
            matched_tags = [
                tag for tag in preferred_tags if tag.lower() in lower_tags
            ]

            composite = (
                0.40 * tag_score
                + 0.25 * locality_score
                + 0.20 * cost_score
                + 0.15 * context_score
            )

            scored.append(
                ModelCandidate(
                    model_id=c.model_id,
                    provider=c.provider,
                    score=round(composite, 4),
                    cost_per_1m_input=c.cost_per_1m_input,
                    cost_per_1m_output=c.cost_per_1m_output,
                    context_window=c.context_window,
                    tags=c.tags,
                    diagnostics={
                        "tag_score": round(tag_score, 4),
                        "cost_score": round(cost_score, 4),
                        "locality_score": round(locality_score, 4),
                        "context_score": round(context_score, 4),
                        "matched_tags": matched_tags,
                        "provider_health": self._registry.get_health(c.provider).value,
                        "family_priority": self._family_priority(c.model_id, qu.intent),
                    },
                )
            )

        return scored

    @staticmethod
    def _score_tags(
        model_tags: list[str], preferred: list[str],
    ) -> float:
        """0.0-1.0 based on tag overlap."""
        if not preferred:
            return 0.5  # no preference → neutral
        if not model_tags:
            return 0.2  # no tags → low default
        lower_tags = {t.lower() for t in model_tags}
        matches = sum(1 for p in preferred if p.lower() in lower_tags)
        return min(matches / len(preferred), 1.0)

    @staticmethod
    def _score_cost(c: ModelCandidate, qu: QueryUnderstanding) -> float:
        """Lower cost = higher score.  Free models (cost=0) get 1.0.

        For SIMPLE intents, cost matters more (prefer cheap).
        For ANALYSIS / MULTI_STEP / DANGEROUS, quality matters
        more (cost less important).
        """
        total_cost = c.cost_per_1m_input + c.cost_per_1m_output
        if total_cost == 0:
            return 1.0  # free (e.g. Ollama)

        # Normalize: $0-$5 per 1M tokens → 1.0-0.2
        # Beyond $30 → 0.1 (very expensive)
        normalized = max(0.1, 1.0 - (total_cost / 35.0))

        # For simple intents, penalise expensive models more
        if qu.intent in (IntentType.SIMPLE, IntentType.SEARCH):
            normalized = max(0.1, normalized * 1.3)

        return min(normalized, 1.0)

    @staticmethod
    def _score_context(
        c: ModelCandidate, qu: QueryUnderstanding,
    ) -> float:
        """Score context window relevance.

        Complex queries benefit from large context windows.
        Simple queries don't need them, so context matters less.
        """
        # Normalize: 4K = 0.2, 32K = 0.6, 128K+ = 1.0
        window_score = min(c.context_window / 128_000, 1.0)

        # Scale by complexity: simple queries don't need large windows
        complexity_weight = 0.3 + (qu.complexity_score * 0.7)
        return window_score * complexity_weight

    @staticmethod
    def _score_locality(c: ModelCandidate) -> float:
        """Score 1.0 for truly local models, 0.3 for cloud-proxied Ollama.

        Ollama models with cloud suffixes (e.g. qwen3.5:397b-cloud,
        kimi-k2.5:cloud) are routed through remote APIs and cost money.
        Local models (llama3.1:latest, mistral:latest, deepseek-r1:14b)
        run on-device for free and should be strongly preferred.

        Non-Ollama providers (OpenAI, Anthropic, etc.) get 0.2 — they
        are always cloud and always cost money.
        """
        if c.provider != ModelProvider.OLLAMA:
            return 0.2  # external cloud provider

        model_lower = c.model_id.lower()
        for suffix in _CLOUD_SUFFIXES:
            if suffix in model_lower:
                return 0.3  # Ollama cloud-proxied model
        return 1.0  # truly local Ollama model

    # ── Internal: diverse selection for COUNCIL/QUINTESSENCE ───

    @staticmethod
    def _select_diverse(
        scored: list[ModelCandidate], count: int,
    ) -> list[ModelCandidate]:
        """Pick up to ``count`` models from *different* providers.

        COUNCIL/QUINTESSENCE modes need diverse perspectives, so
        we avoid picking multiple models from the same provider.
        """
        selected: list[ModelCandidate] = []
        seen_providers: set[ModelProvider] = set()

        for c in scored:
            if c.provider not in seen_providers:
                selected.append(c)
                seen_providers.add(c.provider)
            if len(selected) >= count:
                break

        # If we still need more, allow duplicates from highest-scored
        if len(selected) < count:
            for c in scored:
                if c not in selected:
                    selected.append(c)
                if len(selected) >= count:
                    break

        return selected

    # ── Helpers ────────────────────────────────────────────────

    def _health_priority(self, provider: ModelProvider) -> int:
        return _HEALTH_SORT_ORDER.get(
            self._registry.get_health(provider),
            _HEALTH_SORT_ORDER[HealthStatus.UNAVAILABLE],
        )

    @staticmethod
    def _augment_tags(model_id: str, tags: list[str]) -> list[str]:
        augmented = list(dict.fromkeys(tag.lower() for tag in tags))
        model_lower = model_id.lower()
        for needle, hint_tags in _MODEL_HINT_TAGS:
            if needle in model_lower:
                for tag in hint_tags:
                    if tag not in augmented:
                        augmented.append(tag)
        return augmented

    @staticmethod
    def _family_priority(model_id: str, intent: IntentType) -> int:
        model_lower = model_id.lower()
        families = _INTENT_MODEL_HINTS.get(intent, [])
        for index, family in enumerate(families):
            if family in model_lower:
                return index
        return len(families)

    @staticmethod
    def _serialize_candidate(candidate: ModelCandidate) -> dict[str, Any]:
        return {
            "model_id": candidate.model_id,
            "provider": candidate.provider.value,
            "score": candidate.score,
            "tags": candidate.tags,
            "diagnostics": candidate.diagnostics,
        }

    @staticmethod
    def _selection_reason(candidate: ModelCandidate) -> str:
        diagnostics = candidate.diagnostics or {}
        matched_tags = diagnostics.get("matched_tags") or []
        provider_health = diagnostics.get("provider_health", "UNKNOWN")
        if matched_tags:
            matched = ", ".join(matched_tags)
            return (
                f"Selected for tag match ({matched}) with provider health "
                f"{provider_health.lower()}."
            )
        return (
            "Selected on composite score after availability, locality, cost, "
            f"and context checks (provider health {provider_health.lower()})."
        )

    @staticmethod
    def _elapsed(start: float) -> int:
        return int((time.monotonic() - start) * 1000)

    # ── V2: Runtime routing for EXE mode ──────────────────────────

    async def route_runtime(
        self,
        qu: QueryUnderstanding,
        *,
        user_preferred_runtime: str | None = None,
        auto_mode: bool = True,
        cost_ceiling: float | None = None,
    ) -> RuntimeRoutingDecision | None:
        """Select the best runtime for EXE mode execution.

        Returns None if no RuntimeRegistry is configured (pre-V2 mode).
        Falls back to LLM-only routing if no runtimes are available.

        This method is async because RuntimeRegistry.select_runtime()
        may need to refresh health status.
        """
        if self._runtime_registry is None:
            return None

        from app.services.runtimes.capability_matrix import task_type_for_intent

        task_type = task_type_for_intent(qu.intent)

        try:
            runtime_id = await self._runtime_registry.select_runtime(
                task_type,
                user_preference=user_preferred_runtime,
                auto_mode=auto_mode,
                cost_ceiling=cost_ceiling,
            )
        except Exception as e:
            logger.warning(
                "router.runtime_selection_failed",
                error=str(e),
                intent=qu.intent.value,
                task_type=task_type,
            )
            return None

        # Get capability score for logging
        caps = await self._runtime_registry.get_capabilities(runtime_id)
        score = caps.score_for(task_type)

        # Try to get a fallback runtime
        fallback_id = None
        try:
            fallback_id = await self._runtime_registry.select_runtime(
                task_type,
                exclude=[runtime_id],
            )
        except Exception:
            pass

        adapter = self._runtime_registry.get_adapter(runtime_id)
        display_name = adapter.display_name if adapter else runtime_id

        logger.info(
            "router.runtime_decided",
            runtime_id=runtime_id,
            display_name=display_name,
            task_type=task_type,
            score=round(score, 3),
            fallback=fallback_id,
            intent=qu.intent.value,
        )

        return RuntimeRoutingDecision(
            runtime_id=runtime_id,
            runtime_display_name=display_name,
            capability_score=score,
            fallback_runtime_id=fallback_id,
            metadata={
                "task_type": task_type,
                "intent": qu.intent.value,
                "user_preferred_runtime": user_preferred_runtime,
                "auto_mode": auto_mode,
                "cost_ceiling": cost_ceiling,
            },
        )
