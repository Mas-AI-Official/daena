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
    ModelTier,
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

# Cost-control (DECISION-023, 2026-06-05): score penalty applied to DEGRADED
# providers for non-SEARCH intents, so a HEALTHY local/free model wins ordinary
# prompts instead of a degraded paid provider (e.g. Perplexity 400ing every
# call). Large enough to overcome the +0.5 priority boost + the sovereign tier
# multiplier; degraded providers stay in the fallback chain, and SEARCH/research
# is exempt so a degraded web provider can still be used when actually needed.
# Tuned so a degraded provider drops below a healthy peer in the common case
# (degraded Perplexity ~1.08 -> ~0.08, below any healthy local), while a much
# stronger degraded model can still win a genuinely complex task ("unless
# governance requires stronger").
_DEGRADED_SCORE_PENALTY = 1.0

# Cost-control (DECISION-023): boost a HEALTHY local/free model for ordinary
# (non-SEARCH, SIMPLE/MODERATE) prompts so it wins over external providers --
# the FREE-tier "$0 local chat" + the documented "Auto mode: local handles cheap
# tasks" policy. COMPLEX/VERY_COMPLEX keep cloud-first (the tier bias already
# de-prioritizes local there), SEARCH stays external, and an explicit
# preferred_model override always wins (handled in the orchestrator).
_LOCAL_ORDINARY_BOOST = 0.6

# Maximum models for each routing mode
_MODE_MODEL_COUNTS: dict[RoutingMode, int] = {
    RoutingMode.STANDARD: 1,
    RoutingMode.COUNCIL: 3,
    RoutingMode.QUINTESSENCE: 5,
}

# ── Model Tier Classification ────────────────────────────────
# Maps model ID patterns to their capability tier.
# SOVEREIGN: flagship subscription models (used in Council/Quintessence debates)
# TACTICAL: mid-tier cloud models
# LOCAL: free local models (Ollama, vLLM)
#
# Provider-level defaults: entire providers default to a tier.
# Model-level overrides take precedence.

_PROVIDER_TIER: dict[ModelProvider, ModelTier] = {
    ModelProvider.ANTHROPIC: ModelTier.SOVEREIGN,
    ModelProvider.OPENAI: ModelTier.SOVEREIGN,
    ModelProvider.GEMINI: ModelTier.SOVEREIGN,
    ModelProvider.PERPLEXITY: ModelTier.SOVEREIGN,
    ModelProvider.GROQ: ModelTier.TACTICAL,
    ModelProvider.OPENROUTER: ModelTier.TACTICAL,
    ModelProvider.TOGETHER: ModelTier.TACTICAL,
    ModelProvider.OLLAMA: ModelTier.LOCAL,
    ModelProvider.VLLM: ModelTier.LOCAL,
}

# Specific model overrides (some Ollama models are cloud-proxied sovereign-class)
_MODEL_TIER_OVERRIDE: dict[str, ModelTier] = {
    # Small/fast models from sovereign providers are tactical, not sovereign
    "claude-3-haiku": ModelTier.TACTICAL,
    "claude-haiku": ModelTier.TACTICAL,
    "gemini-flash": ModelTier.TACTICAL,
    "gpt-4o-mini": ModelTier.TACTICAL,
    # Cloud-proxied Ollama models are tactical
    # (caught by _CLOUD_SUFFIXES check in classify_tier)
}

# ── Task-Aware Debate Roster ─────────────────────────────────
# For Council/Quintessence: which models are best for each intent.
# These are PROVIDER preferences, not exact model IDs, because
# the actual model available depends on what's registered.
#
# Order matters: first = strongest for this task type.
# The Primary Mind is EXCLUDED from this roster (it's the judge).

_DEBATE_ROSTER: dict[IntentType, list[ModelProvider]] = {
    # Code: Codex (execution) + Claude (reasoning) + Gemini (multimodal)
    IntentType.CODING: [
        ModelProvider.OPENAI, ModelProvider.ANTHROPIC,
        ModelProvider.GEMINI, ModelProvider.PERPLEXITY,
    ],
    # Analysis: Claude (deep reasoning) + Gemini (multimodal) + Perplexity (grounded)
    IntentType.ANALYSIS: [
        ModelProvider.ANTHROPIC, ModelProvider.GEMINI,
        ModelProvider.PERPLEXITY, ModelProvider.OPENAI,
    ],
    # Creative: Claude (creative writing) + Gemini (diverse) + Codex (structured)
    IntentType.CREATIVE: [
        ModelProvider.ANTHROPIC, ModelProvider.GEMINI,
        ModelProvider.OPENAI, ModelProvider.PERPLEXITY,
    ],
    # Multi-step: Claude (planning) + Codex (execution) + Gemini (verification)
    IntentType.MULTI_STEP: [
        ModelProvider.ANTHROPIC, ModelProvider.OPENAI,
        ModelProvider.GEMINI, ModelProvider.PERPLEXITY,
    ],
    # Search/knowledge: Perplexity (grounded search) + Claude (verify) + Gemini (ground)
    IntentType.SEARCH: [
        ModelProvider.PERPLEXITY, ModelProvider.ANTHROPIC,
        ModelProvider.GEMINI, ModelProvider.OPENAI,
    ],
    # Dangerous/sensitive: Claude (safety) + Gemini (ethics) + Codex (precision)
    IntentType.DANGEROUS: [
        ModelProvider.ANTHROPIC, ModelProvider.GEMINI,
        ModelProvider.OPENAI, ModelProvider.PERPLEXITY,
    ],
    # Simple: Claude (quality) + Perplexity (speed)
    IntentType.SIMPLE: [
        ModelProvider.ANTHROPIC, ModelProvider.PERPLEXITY,
        ModelProvider.GEMINI, ModelProvider.OPENAI,
    ],
    # Ambiguous: same as analysis
    IntentType.AMBIGUOUS: [
        ModelProvider.ANTHROPIC, ModelProvider.GEMINI,
        ModelProvider.PERPLEXITY, ModelProvider.OPENAI,
    ],
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
        effort_level: str = "medium",
        user_routing_prefs: dict[str, Any] | None = None,
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

        # "Power mode" cloud bias: when the user has combined Autopilot
        # + Quintessence + EXE, they've explicitly opted into the most
        # capable routing available. Local models (Ollama / vLLM / llama-
        # server) are weaker than Claude Opus / GPT-5 / Gemini 3 and
        # should NOT win routing for those sessions even on SIMPLE
        # complexity classifications. power_mode=True bumps SOVEREIGN
        # tier further and pushes LOCAL tier near zero for this call.
        # Signals: reasoning_mode in {COUNCIL, QUINTESSENCE} is the
        # strongest intent signal. metadata.power_mode=True is the
        # explicit hook for chat_orchestrator to force it when AGI+EXE
        # are also on.
        _power_mode = bool((metadata or {}).get("power_mode")) or (
            requested_mode in (RoutingMode.COUNCIL, RoutingMode.QUINTESSENCE)
        )
        scored = self._score_candidates(
            candidates,
            qu,
            preferred_tags=preferred_tags,
            power_mode=_power_mode,
            user_routing_prefs=user_routing_prefs,
        )

        # Boost Primary Mind: when the user explicitly sets a Primary Mind,
        # it MUST win the routing unless it's completely unavailable.
        # This is a hard preference (+2.0), not a soft nudge.
        #
        # The old +0.5 boost was too weak -- adaptive cost weights could
        # still push free local models above the user's chosen primary.
        # A user choosing Claude Code as Primary Mind expects Claude to
        # handle their requests, not deepseek-r1:14b.
        #
        # primary_mind can be a runtime_id (e.g. "claude_code"), a model_id
        # (e.g. "llama3.1:latest"), or a provider value (e.g. "OLLAMA").
        # Runtime IDs map to providers so we boost ALL models from that
        # provider, not just an exact model_id match.
        if primary_mind:
            _RUNTIME_TO_PROVIDER: dict[str, ModelProvider] = {
                "claude_code": ModelProvider.ANTHROPIC,
                "codex": ModelProvider.OPENAI,
                "gemini_cli": ModelProvider.GEMINI,
                "grok_cli": ModelProvider.GROQ,
                "ollama": ModelProvider.OLLAMA,
            }
            target_provider = _RUNTIME_TO_PROVIDER.get(primary_mind)
            boosted = False

            # Primary Mind = pick the top-tier model from that
            # provider (2026-04-18, per founder directive):
            # "it doesn't matter it is in cli or subscription or api
            # we always use the highest one". So when Primary Mind is
            # ``claude_code``, we don't just grab any Anthropic
            # candidate -- we grab the one tagged ``priority`` (Claude
            # Sonnet 4.7 Max). Same for codex / gemini_cli / etc.
            # Falls back to first-match only if no priority-tagged
            # candidate exists for that provider.
            def _is_priority(cand: ModelCandidate) -> bool:
                return "priority" in {t.lower() for t in cand.tags}

            target: ModelCandidate | None = None
            # Layer 1: exact model_id / provider-value match
            for c in scored:
                if c.model_id == primary_mind or c.provider.value == primary_mind:
                    target = c
                    break
            # Layer 2: provider match + priority tag (founder top-tier)
            if target is None and target_provider:
                for c in scored:
                    if c.provider == target_provider and _is_priority(c):
                        target = c
                        break
            # Layer 3: provider match without priority (older fallback)
            if target is None and target_provider:
                for c in scored:
                    if c.provider == target_provider:
                        target = c
                        break

            if target is not None:
                # Large bump so the Primary Mind choice dominates all
                # other scoring concerns unless the user explicitly
                # pinned a different model via preferred_model.
                object.__setattr__(target, "score", target.score + 3.0)
                boosted = True
                route_metadata["primary_mind"] = primary_mind
                route_metadata["primary_mind_boosted"] = True
                route_metadata["primary_mind_model"] = target.model_id
                route_metadata["primary_mind_priority_tier"] = _is_priority(target)

            if not boosted:
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

        # Resolve Primary Mind provider for debate exclusion
        _primary_mind_provider: ModelProvider | None = None
        if primary_mind:
            _RUNTIME_TO_PROVIDER_DEBATE: dict[str, ModelProvider] = {
                "claude_code": ModelProvider.ANTHROPIC,
                "codex": ModelProvider.OPENAI,
                "gemini_cli": ModelProvider.GEMINI,
                "grok_cli": ModelProvider.GROQ,
                "ollama": ModelProvider.OLLAMA,
            }
            _primary_mind_provider = _RUNTIME_TO_PROVIDER_DEBATE.get(primary_mind)
            # Also check if primary_mind is a provider value directly
            if not _primary_mind_provider:
                for prov in ModelProvider:
                    if prov.value == primary_mind:
                        _primary_mind_provider = prov
                        break

        council: list[ModelCandidate] = []
        mode_reason: str | None = None
        if requested_mode in (RoutingMode.COUNCIL, RoutingMode.QUINTESSENCE):
            council = self._select_diverse(
                scored, needed,
                intent=qu.intent,
                primary_mind_provider=_primary_mind_provider,
                effort_level=effort_level,
            )
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

        # Cost-control (DECISION-023): always let a HEALTHY local/free model
        # compete for ordinary prompts. The intent->provider suggestion map
        # (query_understanding._INTENT_PROVIDERS) names OLLAMA (deprecated /
        # UNAVAILABLE) for "local" and never VLLM (the live llama-server), so
        # the real local model was never an AUTO candidate and routing fell to
        # paid providers. For non-SEARCH intents, add any configured + HEALTHY
        # LOCAL-tier provider not already considered. SEARCH is exempt (web
        # research is the cloud providers' job).
        if qu.intent != IntentType.SEARCH:
            local_extra = [
                p for p in configured
                if _PROVIDER_TIER.get(p) == ModelTier.LOCAL
                and p not in providers_considered
                and self._registry.get_health(p) == HealthStatus.HEALTHY
            ]
            if local_extra:
                extra_candidates = self._collect_from_providers(local_extra)
                if extra_candidates:
                    candidates = candidates + extra_candidates
                    providers_considered = providers_considered + local_extra

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
            # Circuit breaker: skip providers the health tracker marks as dead
            try:
                from app.services.runtimes.health_tracker import get_health_tracker
                _ht = get_health_tracker()
                if not _ht.is_available(provider_enum.value):
                    logger.info(
                        "router.skipping_circuit_open",
                        provider=provider_enum.value,
                    )
                    continue
            except Exception:
                pass  # health tracker not initialized yet, proceed normally

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
        power_mode: bool = False,
        user_routing_prefs: dict[str, Any] | None = None,
    ) -> list[ModelCandidate]:
        """Score each candidate on tag match, cost, locality, and context.

        Weights adapt to complexity:
            SIMPLE:       cost 0.40, locality 0.30, tag 0.20, context 0.10
            MODERATE:     tag 0.35, locality 0.25, cost 0.25, context 0.15
            COMPLEX:      tag 0.45, context 0.20, cost 0.15, locality 0.20
            VERY_COMPLEX: tag 0.50, context 0.25, locality 0.15, cost 0.10

        Philosophy: simple tasks should use the cheapest available model.
        Complex tasks should use the most capable, regardless of cost.

        ``power_mode`` (Autopilot + Quintessence + EXE): pins the
        tier multipliers at VERY_COMPLEX level regardless of the query's
        own complexity classification. Local tier collapses to 0.25x,
        sovereign tier jumps to 1.75x -- cloud wins unless nothing else
        is reachable.

        ``user_routing_prefs`` (Phase 11 PR-S3 wire-up, 2026-06-01): the
        founder's per-user routing toggles from SettingsLLM. Currently
        honored:

            local_first_routing: bool (default True)
                When True (the default and the historical behavior), the
                computed locality weight is used as-is. When the user
                turns this OFF in SettingsLLM, the locality weight is
                multiplied by 0.5 so cloud models no longer get penalized
                for being remote.

            cost_aware_routing: bool (default True)
                Symmetric: when True (default), the cost weight is used
                as-is. When OFF, cost weight is multiplied by 0.5 so the
                user can pick higher-quality models without the router
                automatically downranking them on price.

        Both default True -> default behavior is unchanged. Turning
        either OFF de-emphasizes that factor in scoring rather than
        flipping a hard switch. This is the same shape the
        complexity-adaptive weights use.
        """
        preferred_tags = list(preferred_tags or _INTENT_TAGS.get(qu.intent, []))

        # Complexity-adaptive scoring weights
        from app.services.query_understanding import ComplexityLabel
        _weights = {
            ComplexityLabel.SIMPLE:       (0.20, 0.30, 0.40, 0.10),
            ComplexityLabel.MODERATE:     (0.35, 0.25, 0.25, 0.15),
            ComplexityLabel.COMPLEX:      (0.45, 0.20, 0.15, 0.20),
            ComplexityLabel.VERY_COMPLEX: (0.50, 0.15, 0.10, 0.25),
        }
        w_tag, w_loc, w_cost, w_ctx = _weights.get(
            qu.complexity_label, (0.35, 0.25, 0.25, 0.15)
        )

        # PR-S3 Phase 11 (2026-06-01): user-level routing preferences from
        # SettingsLLM. Both default True (matches the historical scoring
        # behavior). Turning either OFF in the UI de-emphasizes that factor
        # by 50% rather than flipping a hard switch.
        if user_routing_prefs is not None:
            if user_routing_prefs.get("local_first_routing") is False:
                w_loc *= 0.5
            if user_routing_prefs.get("cost_aware_routing") is False:
                w_cost *= 0.5

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
                w_tag * tag_score
                + w_loc * locality_score
                + w_cost * cost_score
                + w_ctx * context_score
            )

            # Complexity-aware tier bias (2026-04-16, refined).
            # - SIMPLE: no bias. Let cost + locality dominate. A greeting
            #   should not fan out to Claude Sonnet.
            # - MODERATE: mild sovereign preference.
            # - COMPLEX / VERY_COMPLEX: strong sovereign preference, strong
            #   local penalty. This is the "cloud-first for high-level
            #   tasks" policy the operator requested: local models
            #   (Ollama, vLLM) are weaker and serve as fallback, not
            #   cost-optimized default for hard questions.
            # Subscription CLIs (claude-code-cli, codex-cli, gemini-cli)
            # and their API twins share the same provider enum and
            # therefore the same tier -- they are treated as equal
            # sources of the same brain, ranked only by the per-candidate
            # cost/context/tag score that the router already computed.
            # Founder policy enforce_local_only still wins downstream.
            from app.core.constants import ModelTier
            from app.services.query_understanding import ComplexityLabel
            tier = self.classify_tier(c)
            _sov_mult = {
                ComplexityLabel.SIMPLE:       1.0,
                ComplexityLabel.MODERATE:     1.15,
                ComplexityLabel.COMPLEX:      1.5,
                ComplexityLabel.VERY_COMPLEX: 1.75,
            }
            _loc_mult = {
                ComplexityLabel.SIMPLE:       1.0,
                ComplexityLabel.MODERATE:     0.8,
                ComplexityLabel.COMPLEX:      0.4,
                ComplexityLabel.VERY_COMPLEX: 0.25,
            }
            # Power-mode override: pin tier multipliers at the strongest
            # cloud-preference setting (VERY_COMPLEX) regardless of what
            # the query's own complexity classification said. This is the
            # AGI+QE+EXE "use the best, not the nearest" routing policy.
            effective_complexity = (
                ComplexityLabel.VERY_COMPLEX if power_mode
                else qu.complexity_label
            )
            if tier == ModelTier.SOVEREIGN:
                tier_mult = _sov_mult.get(effective_complexity, 1.15)
            elif tier == ModelTier.TACTICAL:
                # F-COUNCIL-MODELS fix (2026-04-25, founder-driven):
                # In power_mode (Council/QE/AGI+EXE), TACTICAL providers
                # like Groq/Together/OpenRouter shouldn't compete with
                # SOVEREIGN frontier models. Previously tactical kept a
                # 1.0 multiplier and won via cheap cost+locality scores
                # (Kimi/Llama-4-scout beat Claude Sonnet because they're
                # free on Groq). Demote tactical to 0.55 in power_mode so
                # the council picks subscription-backed frontier models
                # (Claude Code CLI, Codex, Gemini CLI, Anthropic API,
                # OpenAI API, Gemini API, Perplexity Pro) when those are
                # available, falling back to tactical only if nothing
                # sovereign exists. Outside power_mode tactical stays
                # neutral (1.0) so cost-optimized routing still works.
                tier_mult = 0.55 if power_mode else 1.0
            else:  # LOCAL
                tier_mult = _loc_mult.get(effective_complexity, 0.8)
            composite = composite * tier_mult

            # F-COUNCIL-MODELS fix continued: extra boost for the
            # frontier+priority tagged candidates so within SOVEREIGN
            # the actual flagship (Sonnet 4.x, GPT-5.x, Gemini 2.5 Pro,
            # Sonar Pro) wins over any older sovereign sibling.
            if power_mode and ("frontier" in lower_tags or "priority" in lower_tags):
                composite = composite * 1.20

            # Priority boost (2026-04-18). Models tagged ``priority``
            # in their provider catalog are the founder-specified
            # top-tier per provider (e.g. Claude Sonnet 4.7 Max,
            # Codex 5.4, Gemini 3.1 Pro, Perplexity Auto). When two
            # candidates share a provider, the priority-tagged one
            # should always outrank its siblings unless the user has
            # explicitly pinned a cheaper model. Bump of +0.5 on the
            # already-tier-multiplied score is enough to dominate the
            # tag/locality/cost/context mix without nuking cost
            # discipline for non-priority models.
            if "priority" in lower_tags:
                composite += 0.5

            # Cost-control (DECISION-023): demote DEGRADED providers for
            # non-SEARCH intents so a HEALTHY local/free model wins ordinary
            # prompts instead of a degraded paid provider. The provider stays a
            # candidate (fallback chain), just not primary over a healthy
            # alternative. SEARCH is exempt so a degraded web provider (e.g.
            # Perplexity Sonar) can still be selected for research.
            if qu.intent != IntentType.SEARCH:
                if self._registry.get_health(c.provider) == HealthStatus.DEGRADED:
                    composite -= _DEGRADED_SCORE_PENALTY

            # Cost-control (DECISION-023): for ordinary (non-SEARCH, SIMPLE/
            # MODERATE) prompts, boost a HEALTHY local/free model so it wins over
            # external providers -- the FREE-tier "$0 local chat" / "Auto mode:
            # local handles cheap tasks" policy. COMPLEX+ keeps cloud-first via
            # the tier bias above; SEARCH is exempt; explicit override still wins.
            if (
                qu.intent != IntentType.SEARCH
                and qu.complexity_label in (ComplexityLabel.SIMPLE, ComplexityLabel.MODERATE)
                and tier == ModelTier.LOCAL
                and self._registry.get_health(c.provider) == HealthStatus.HEALTHY
            ):
                composite += _LOCAL_ORDINARY_BOOST

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
                        "weights": f"tag={w_tag} loc={w_loc} cost={w_cost} ctx={w_ctx}",
                        "complexity": qu.complexity_label.value,
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
        """Score models by deployment preference.

        CLI subscription models (claude-code-cli, codex-cli, gemini-cli)
        get 0.9 -- they use Pro/Max subscriptions and are the strongest
        available models per provider. They cost $0 per token (included
        in subscription) so they should be preferred over API-key models.

        Truly local Ollama models get 1.0 (free, on-device).
        Cloud-proxied Ollama gets 0.3.
        API-key cloud providers get 0.2.
        """
        # CLI subscription models: sovereign tier, $0/token
        if c.model_id.endswith("-cli"):
            return 0.9

        if c.provider != ModelProvider.OLLAMA:
            return 0.2  # external cloud provider (API key, costs money)

        model_lower = c.model_id.lower()
        for suffix in _CLOUD_SUFFIXES:
            if suffix in model_lower:
                return 0.3  # Ollama cloud-proxied model
        return 1.0  # truly local Ollama model

    # ── Model tier classification ────────────────────────────────

    @staticmethod
    def classify_tier(candidate: ModelCandidate) -> ModelTier:
        """Classify a model candidate into its capability tier.

        Priority: model-level override > cloud-suffix check > provider default.
        """
        model_lower = candidate.model_id.lower()

        # Check model-level overrides first
        for pattern, tier in _MODEL_TIER_OVERRIDE.items():
            if pattern in model_lower:
                return tier

        # Cloud-proxied Ollama models are tactical (they cost money)
        if candidate.provider == ModelProvider.OLLAMA:
            for suffix in _CLOUD_SUFFIXES:
                if suffix in model_lower:
                    return ModelTier.TACTICAL

        # Provider-level default
        return _PROVIDER_TIER.get(candidate.provider, ModelTier.LOCAL)

    # ── Internal: diverse selection for COUNCIL/QUINTESSENCE ───

    def _select_diverse(
        self,
        scored: list[ModelCandidate],
        count: int,
        intent: IntentType | None = None,
        primary_mind_provider: ModelProvider | None = None,
        effort_level: str = "medium",
    ) -> list[ModelCandidate]:
        """Pick up to ``count`` models for Council/Quintessence debate.

        Task-aware selection strategy:
        1. Only SOVEREIGN-tier models participate in debates
        2. Prefer providers from the debate roster for this intent
        3. Default: exclude the Primary Mind's provider so the Chairman
           gets diverse views, not a self-confirming echo
        4. Diverse providers: avoid picking 2 models from same provider
        5. Fallback: if not enough sovereign models, include tactical tier
        6. **Quorum fallback (Council R4 Phase 3, GPT-5.5 verdict)**: if
           the diverse roster would yield FEWER than 3 debaters AND
           ``effort_level`` ∈ {high, xhigh}, re-admit the Primary Mind's
           provider so the chamber has at least 3 voices. This is the
           sole legitimate path for same-provider debater admission —
           prior policy of "always admit on HIGH effort" was over-broad
           (R2 critique: "buying confidence theater with 25-50K tokens"
           when diversity is sufficient).
        """
        # Phase 0: try the diverse roster FIRST (provider-diversity-only).
        # If the result has >=3 debaters, ship it. Same-provider admission
        # is reserved for the QUORUM FALLBACK below.
        _effort_allows_quorum_fallback = effort_level in ("high", "xhigh")
        # Audit telemetry — populated through the function so we can log
        # the founder-visible reason at the end.
        _admission_reason: str = "diverse_roster"
        _allow_same_provider = False

        # Phase 1: filter to sovereign-tier candidates (DIVERSE PASS)
        sovereign = [
            c for c in scored
            if self.classify_tier(c) == ModelTier.SOVEREIGN
        ]

        # Exclude Primary Mind's provider for the diverse pass (default).
        sovereign_diverse_only = (
            [c for c in sovereign if c.provider != primary_mind_provider]
            if primary_mind_provider else list(sovereign)
        )

        # Phase 2: sort by debate roster priority for this intent,
        # then by model strength within each provider.
        # Within each provider, prefer CLI subscription models (-cli suffix)
        # over API-key models because CLI = Pro/Max subscription = strongest.
        roster = _DEBATE_ROSTER.get(intent, []) if intent else []

        def _roster_priority(c: ModelCandidate) -> int:
            if not roster:
                return 0  # No preference -- all equal
            try:
                return roster.index(c.provider)
            except ValueError:
                return len(roster)

        def _strength_score(c: ModelCandidate) -> float:
            """Higher = stronger model. CLI subscription > API Pro > API Flash."""
            s = c.score
            mid = c.model_id.lower()
            if mid.endswith("-cli"):
                s += 10.0  # CLI subscription = strongest per provider
            if "pro" in mid or "opus" in mid or "max" in mid:
                s += 5.0
            if "claude" in mid:
                s += 3.0  # Claude = strong general reasoner
            if "flash" in mid or "mini" in mid or "instant" in mid:
                s -= 10.0  # Never pick cheap models for debates
            return s

        sovereign.sort(key=lambda c: (_roster_priority(c), -_strength_score(c)))
        sovereign_diverse_only.sort(key=lambda c: (_roster_priority(c), -_strength_score(c)))

        # Phase 3: pick diverse providers FROM THE DIVERSE-ONLY POOL FIRST
        selected: list[ModelCandidate] = []
        seen_providers: set[ModelProvider] = set()

        for c in sovereign_diverse_only:
            if c.provider not in seen_providers:
                selected.append(c)
                seen_providers.add(c.provider)
            if len(selected) >= count:
                break

        # Count provider diversity AFTER the diverse pass — this is the
        # number GPT-5.5 R4 wanted in the audit telemetry so the founder
        # can see when quorum protection kicks in.
        _provider_diversity_count = len(seen_providers)

        # Phase 3b: QUORUM FALLBACK (Phase 3 Council verdict, 2026-04-25).
        # If we couldn't find 3 diverse debaters AND HIGH effort gives us
        # permission, admit the Primary Mind's provider as a debater.
        # This produces the slim-Claude-as-proposer + full-Claude-as-
        # Chairman pattern from R2, but ONLY when no real diversity is
        # available. Avoids R2's "confidence theater" failure mode where
        # we waste tokens admitting the same model when other providers
        # would have served just fine.
        if (
            _effort_allows_quorum_fallback
            and len(selected) < min(3, count)
            and primary_mind_provider is not None
        ):
            same_provider_pool = [
                c for c in sovereign
                if c.provider == primary_mind_provider
                and c not in selected
            ]
            same_provider_pool.sort(key=lambda c: -_strength_score(c))
            for c in same_provider_pool:
                # Allow even though provider is "seen" — the whole point
                # of the fallback is to admit the same provider.
                selected.append(c)
                seen_providers.add(c.provider)
                _allow_same_provider = True
                _admission_reason = "roster_quorum_fallback"
                if len(selected) >= count:
                    break

        # Phase 4: if not enough sovereign, include tactical tier
        if len(selected) < count:
            tactical = [
                c for c in scored
                if self.classify_tier(c) == ModelTier.TACTICAL
                and c.provider not in seen_providers
                and (_allow_same_provider or c.provider != primary_mind_provider)
            ]
            for c in tactical:
                if c.provider not in seen_providers:
                    selected.append(c)
                    seen_providers.add(c.provider)
                if len(selected) >= count:
                    break

        # Phase 5: last resort, allow any remaining model
        if len(selected) < count:
            for c in scored:
                if c not in selected and (
                    _allow_same_provider or c.provider != primary_mind_provider
                ):
                    selected.append(c)
                if len(selected) >= count:
                    break

        # Audit signal when Primary Mind's provider was admitted as a
        # debater alongside being the Chairman. Surfaces in the Governed
        # Execution Timeline as `same_provider_debater_admitted`.
        _same_provider_debater = (
            primary_mind_provider is not None
            and any(c.provider == primary_mind_provider for c in selected)
        )
        # Estimate added cost when same-provider was admitted (R4 Phase 3
        # second-signal request from GPT-5.5 — make the cost visible).
        _est_extra_tokens = 0
        _est_extra_cost = 0.0
        if _same_provider_debater and _admission_reason == "roster_quorum_fallback":
            same_prov_extras = [
                c for c in selected if c.provider == primary_mind_provider
            ]
            for c in same_prov_extras:
                # Round-trip estimate: ~30K input + 1K output for a slim
                # proposer call at ~$5/M input + $15/M output.
                _est_extra_tokens += 31_000
                _est_extra_cost += round(
                    (c.cost_per_1m_input * 30_000 + c.cost_per_1m_output * 1_000)
                    / 1_000_000,
                    4,
                )
        logger.info(
            "router.debate_roster_selected",
            intent=intent.value if intent else "none",
            count=len(selected),
            models=[c.model_id for c in selected],
            tiers=[self.classify_tier(c).value for c in selected],
            primary_mind_excluded=primary_mind_provider.value if primary_mind_provider else "none",
            effort_level=effort_level,
            same_provider_debater_admitted=_same_provider_debater,
            admission_reason=_admission_reason,
            provider_diversity_count=_provider_diversity_count,
            est_extra_tokens=_est_extra_tokens,
            est_extra_cost=_est_extra_cost,
        )

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

    # ── Public: model selection for CognitiveReasoner ──────────

    def select_best_single(
        self,
        *,
        offensive: bool = False,
    ) -> ModelCandidate | None:
        """Pick the single best model for cognitive reasoning.

        Used by CognitiveReasoner to select its working model.
        Tier hierarchy: SOVEREIGN > STRATEGIC > TACTICAL > LOCAL.
        Within tier: CLI subscription > Pro/Opus > standard > Flash/Mini.

        In offensive mode, local models are elevated (no guardrails).
        """
        all_providers = list(self._registry.available_providers)
        candidates = self._collect_from_providers(all_providers)

        if not candidates:
            return None

        # Filter out embedding models
        candidates = [
            c for c in candidates
            if "embed" not in c.model_id.lower()
            and "nomic" not in c.model_id.lower()
        ]

        if not candidates:
            return None

        def _strength(c: ModelCandidate) -> tuple[int, float]:
            """(tier_rank, strength_score). Lower tier_rank = better tier."""
            tier = self.classify_tier(c)
            mid = c.model_id.lower()

            # Tier ranking (lower = better)
            if offensive:
                # Offensive: local first (no guardrails), then sovereign
                tier_order = {
                    ModelTier.LOCAL: 0,
                    ModelTier.SOVEREIGN: 1,
                    ModelTier.TACTICAL: 2,
                }
            else:
                tier_order = {
                    ModelTier.SOVEREIGN: 0,
                    ModelTier.TACTICAL: 1,
                    ModelTier.LOCAL: 2,
                }

            tier_rank = tier_order.get(tier, 99)

            # Strength within tier
            strength = 0.0
            if mid.endswith("-cli"):
                strength += 200.0  # CLI subscription = strongest
            if "opus" in mid or "pro" in mid or "max" in mid:
                strength += 100.0
            if "claude" in mid:
                strength += 120.0  # Claude = best general reasoner (judge)
            if "sonnet" in mid:
                strength += 50.0
            if "4.6" in mid or "4-6" in mid:
                strength += 30.0
            if "sonar-pro" in mid:
                strength += 90.0
            if "codex" in mid:
                strength += 80.0
            # Penalties for cheap/fast models
            if "flash" in mid or "mini" in mid or "instant" in mid or "nano" in mid:
                strength -= 200.0
            if "8b" in mid or "3b" in mid or "7b" in mid:
                strength -= 50.0
            # Context window bonus
            strength += c.context_window / 100_000

            return (tier_rank, -strength)  # negate strength for sort

        candidates.sort(key=_strength)
        best = candidates[0]

        logger.info(
            "router.select_best_single",
            model=best.model_id,
            provider=best.provider.value,
            tier=self.classify_tier(best).value,
            offensive=offensive,
            candidates_evaluated=len(candidates),
        )
        return best

    def select_debate_roster(
        self,
        intent: IntentType | None = None,
        count: int = 3,
        *,
        primary_mind_provider: ModelProvider | None = None,
    ) -> list[ModelCandidate]:
        """Select models for Council/Quintessence debate.

        Public wrapper around _select_diverse. Used by CognitiveReasoner
        and benchmark runner to get task-aware debate participants.
        """
        all_providers = list(self._registry.available_providers)
        candidates = self._collect_from_providers(all_providers)
        # Filter embedding models
        candidates = [
            c for c in candidates
            if "embed" not in c.model_id.lower()
            and "nomic" not in c.model_id.lower()
        ]
        return self._select_diverse(
            candidates, count,
            intent=intent,
            primary_mind_provider=primary_mind_provider,
        )

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
