"""Intent Amplifier -- decodes what users ACTUALLY need from vague requests.

90% of users don't know the right question. They have something in mind
and say it poorly. This module bridges the gap between what they said and
what a power user would have asked for.

Runs as Stage 3.5 in the pipeline (after QueryUnderstanding, before GovernanceCheck).
Zero LLM calls -- deterministic heuristic (<10ms budget).

Architecture:
    1. Pattern matching: detect vague/incomplete requests
    2. Intent expansion: map to what a power user would mean
    3. Capability suggestion: recommend hidden features that help
    4. Amplified output: enriched QueryUnderstanding with suggestions
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.core.logging import get_logger
from app.services.query_understanding import (
    IntentType,
    ComplexityLabel,
    QueryUnderstanding,
)

logger = get_logger(__name__)


# ── Vague Pattern Detection ────────────────────────────────────


class VaguePattern(str, Enum):
    """Categories of vague user requests."""

    TOO_SHORT = "TOO_SHORT"                # "fix it", "make it work"
    NO_TARGET = "NO_TARGET"                # "improve performance" (of what?)
    IMPLICIT_SCOPE = "IMPLICIT_SCOPE"      # "update the code" (which code?)
    MISSING_CONTEXT = "MISSING_CONTEXT"    # "why doesn't it work?" (what is 'it'?)
    AMBIGUOUS_ACTION = "AMBIGUOUS_ACTION"  # "help me with this" (do what?)
    PREMATURE_HOW = "PREMATURE_HOW"        # asking HOW before clarifying WHAT
    COMPOUND_UNCLEAR = "COMPOUND_UNCLEAR"  # multiple things jumbled together


# Patterns that indicate vagueness (regex, pattern type, expansion hint)
_VAGUE_PATTERNS: list[tuple[str, VaguePattern, str]] = [
    # Too short / no context
    (r"^(fix|do|make|change|update|help)\s+(it|this|that)\.?$",
     VaguePattern.TOO_SHORT,
     "Specify what to fix and where -- file, function, or error message"),

    (r"^(it|this|that)\s+(doesn't|does not|isn't|is not|won't)\s+(work|run|compile|load)",
     VaguePattern.MISSING_CONTEXT,
     "Describe what you expected vs what happened, include error if any"),

    (r"^(help|assist|support)\s+(me|us)?\s*(with|on)?\s*(this|that|it)?\.?$",
     VaguePattern.AMBIGUOUS_ACTION,
     "Describe the specific task -- are you debugging, building, or learning?"),

    (r"^make\s+(it|this|that)\s+(better|faster|nicer|cleaner|simpler)\.?$",
     VaguePattern.NO_TARGET,
     "Specify what to improve -- performance, readability, UX, or architecture"),

    (r"^(improve|optimize|enhance|upgrade)\s+(performance|speed|quality)\.?$",
     VaguePattern.NO_TARGET,
     "Which component? Backend API, frontend render, database query, or build time?"),

    (r"^(update|change|modify)\s+(the\s+)?(code|file|function|class|module)\.?$",
     VaguePattern.IMPLICIT_SCOPE,
     "Which file or function? What change is needed?"),

    (r"^why\s+(doesn't|does not|isn't|won't|can't)",
     VaguePattern.MISSING_CONTEXT,
     "Include the error message, expected behavior, and what you've tried"),

    (r"^how\s+(do|can|should)\s+(I|we|you)",
     VaguePattern.PREMATURE_HOW,
     "Good question -- let me understand the goal first to give the best approach"),
]


# ── Intent Expansion Rules ─────────────────────────────────────
# Maps (intent, complexity) to what a power user would actually want


@dataclass(frozen=True, slots=True)
class Expansion:
    """An expanded interpretation of user intent."""

    power_user_intent: str
    recommended_mode: str | None = None       # CMD, EXE, or None (keep current)
    recommended_reasoning: str | None = None  # STANDARD, COUNCIL, QUINTESSENCE
    capability_hints: list[str] = field(default_factory=list)
    runtime_hints: dict[str, Any] = field(default_factory=dict)


_INTENT_EXPANSIONS: dict[tuple[IntentType, ComplexityLabel], Expansion] = {
    # Simple coding -> just do it efficiently
    (IntentType.CODING, ComplexityLabel.SIMPLE): Expansion(
        power_user_intent="Quick code change with verification",
        capability_hints=["token_efficient_tools"],
    ),

    # Complex coding -> research first, then implement, then verify
    (IntentType.CODING, ComplexityLabel.COMPLEX): Expansion(
        power_user_intent="Research the codebase, plan the change, implement with tests, verify",
        recommended_reasoning="COUNCIL",
        capability_hints=[
            "parallel_research",
            "coordinator_synthesis",
            "fresh_verification",
            "extended_thinking",
        ],
    ),

    # Very complex coding -> full orchestration
    (IntentType.CODING, ComplexityLabel.VERY_COMPLEX): Expansion(
        power_user_intent="Full architectural analysis, multi-file implementation with governance",
        recommended_reasoning="QUINTESSENCE",
        capability_hints=[
            "parallel_research",
            "coordinator_synthesis",
            "fork_cache_optimization",
            "extended_thinking",
            "session_memory_buffer",
            "worktree_isolation",
        ],
    ),

    # Multi-step tasks -> decompose and track
    (IntentType.MULTI_STEP, ComplexityLabel.MODERATE): Expansion(
        power_user_intent="Decompose into phases, execute with progress tracking",
        recommended_mode="EXE",
        capability_hints=[
            "task_decomposition",
            "parallel_execution",
            "progress_summarization",
        ],
    ),

    (IntentType.MULTI_STEP, ComplexityLabel.COMPLEX): Expansion(
        power_user_intent="Plan phases, research each, implement with dependency tracking",
        recommended_mode="EXE",
        recommended_reasoning="COUNCIL",
        capability_hints=[
            "coordinator_synthesis",
            "parallel_research",
            "dependency_tracking",
            "budget_tracking",
        ],
    ),

    # Analysis -> use reasoning and multiple perspectives
    (IntentType.ANALYSIS, ComplexityLabel.MODERATE): Expansion(
        power_user_intent="Structured analysis with data and comparison",
        recommended_reasoning="COUNCIL",
        capability_hints=["extended_thinking", "web_search_grounding"],
    ),

    (IntentType.ANALYSIS, ComplexityLabel.COMPLEX): Expansion(
        power_user_intent="Deep multi-perspective analysis with expert viewpoints",
        recommended_reasoning="QUINTESSENCE",
        capability_hints=[
            "extended_thinking",
            "parallel_research",
            "web_search_grounding",
        ],
    ),

    # Search -> ground in real data
    (IntentType.SEARCH, ComplexityLabel.SIMPLE): Expansion(
        power_user_intent="Quick factual lookup with current data",
        capability_hints=["web_search", "context7_docs"],
    ),

    # Tool use -> switch to EXE mode
    (IntentType.TOOL_USE, ComplexityLabel.SIMPLE): Expansion(
        power_user_intent="Execute tool action with governance",
        recommended_mode="EXE",
        capability_hints=["tool_governance_hooks"],
    ),

    (IntentType.TOOL_USE, ComplexityLabel.COMPLEX): Expansion(
        power_user_intent="Multi-step tool execution with planning and rollback",
        recommended_mode="EXE",
        capability_hints=[
            "action_planner",
            "workspace_chaining",
            "tool_governance_hooks",
            "env_scrubbing",
        ],
    ),

    # Creative -> let it breathe
    (IntentType.CREATIVE, ComplexityLabel.MODERATE): Expansion(
        power_user_intent="Creative generation with multiple approaches to choose from",
        recommended_reasoning="COUNCIL",
        capability_hints=["parallel_generation", "diverse_perspectives"],
    ),

    # Dangerous -> maximum governance
    (IntentType.DANGEROUS, ComplexityLabel.SIMPLE): Expansion(
        power_user_intent="Potentially dangerous action -- verify intent, apply maximum governance",
        recommended_reasoning="COUNCIL",
        capability_hints=[
            "hard_law_enforcement",
            "approval_queue",
            "env_scrubbing",
            "audit_trail",
        ],
    ),
}


# ── Capability-to-Runtime Hints ────────────────────────────────
# Maps capability hints to concrete runtime parameters


CAPABILITY_RUNTIME_MAP: dict[str, dict[str, Any]] = {
    "extended_thinking": {
        "anthropic": {"anthropic_beta": ["interleaved-thinking-2025-05-14"]},
        "openai": {"reasoning_effort": "high"},
        "gemini": {"thinking_level": "high"},
        "ollama": {"model_hint": "deepseek-r1:14b"},
    },
    "token_efficient_tools": {
        "anthropic": {"anthropic_beta": ["token-efficient-tools-2025-02-19"]},
    },
    "extended_cache": {
        "anthropic": {"anthropic_beta": ["extended-cache-ttl-2025-04-11"]},
    },
    "fast_mode": {
        "anthropic": {"speed": "fast"},
    },
    "web_search": {
        "anthropic": {"server_tools": ["web_search"]},
        "openai": {"tools": [{"type": "web_search_preview"}]},
        "gemini": {"tools": [{"google_search": {}}]},
    },
    "web_search_grounding": {
        "gemini": {"tools": [{"google_search": {}}]},
        "openai": {"tools": [{"type": "web_search_preview"}]},
    },
    "batch_discount": {
        "anthropic": {"use_batch_api": True},
        "openai": {"use_batch_api": True},
    },
    "flex_tier": {
        "openai": {"service_tier": "flex"},
    },
    "predicted_output": {
        "openai": {"use_predicted_output": True},
    },
    "context7_docs": {
        "_meta": {"use_context7": True},
    },
    "parallel_research": {
        "_meta": {"spawn_parallel_agents": True, "agent_count": 3},
    },
    "coordinator_synthesis": {
        "_meta": {"use_coordinator_pattern": True},
    },
    "fork_cache_optimization": {
        "_meta": {"use_fork_caching": True},
    },
    "fresh_verification": {
        "_meta": {"spawn_fresh_verifier": True},
    },
    "session_memory_buffer": {
        "_meta": {"enable_session_memory": True},
    },
    "budget_tracking": {
        "_meta": {"enable_budget_tracker": True, "max_continuations": 3},
    },
    "progress_summarization": {
        "_meta": {"enable_30s_summaries": True},
    },
    "tool_governance_hooks": {
        "_meta": {"enable_pre_post_hooks": True},
    },
    "env_scrubbing": {
        "_meta": {"scrub_env_vars": True},
    },
    "hard_law_enforcement": {
        "_meta": {"enforce_hard_laws": True, "governance_tier_override": 3},
    },
    "approval_queue": {
        "_meta": {"require_approval": True},
    },
    "audit_trail": {
        "_meta": {"force_audit": True},
    },
    "worktree_isolation": {
        "_meta": {"isolate_agents": True},
    },
    "action_planner": {
        "_meta": {"use_action_planner": True},
    },
    "workspace_chaining": {
        "_meta": {"enable_workspace": True},
    },
    "task_decomposition": {
        "_meta": {"decompose_tasks": True},
    },
    "parallel_execution": {
        "_meta": {"parallel_workers": True},
    },
    "dependency_tracking": {
        "_meta": {"track_dependencies": True},
    },
    "parallel_generation": {
        "_meta": {"generate_alternatives": True, "alternative_count": 3},
    },
    "diverse_perspectives": {
        "_meta": {"inject_dcp_experts": True},
    },
}


# ── Public API ─────────────────────────────────────────────────


@dataclass(slots=True)
class AmplifiedIntent:
    """Output of the IntentAmplifier."""

    # Original understanding (passed through)
    original: QueryUnderstanding

    # Amplification results
    is_vague: bool = False
    vague_patterns: list[VaguePattern] = field(default_factory=list)
    expansion_hints: list[str] = field(default_factory=list)

    # Power user interpretation
    power_user_intent: str | None = None
    recommended_mode_override: str | None = None
    recommended_reasoning_override: str | None = None

    # Capability suggestions for the runtime
    capability_hints: list[str] = field(default_factory=list)
    runtime_params: dict[str, dict[str, Any]] = field(default_factory=dict)

    # For the user (optional clarification)
    clarifying_note: str | None = None

    processing_time_ms: int = 0


def amplify_intent(
    query: str,
    understanding: QueryUnderstanding,
    provider: str = "anthropic",
) -> AmplifiedIntent:
    """Amplify a QueryUnderstanding with hidden capability awareness.

    This is the main entry point. Call after QueryUnderstanding, before
    GovernanceCheck. Zero LLM calls -- pure heuristic.

    Args:
        query: Raw user message text.
        understanding: Output from query_understanding pipeline.
        provider: Target LLM provider name (for runtime hint selection).

    Returns:
        AmplifiedIntent with enriched context and capability suggestions.
    """
    import time
    start = time.monotonic_ns()

    result = AmplifiedIntent(original=understanding)

    # Step 1: Detect vagueness
    query_lower = query.strip().lower()
    for pattern, vague_type, hint in _VAGUE_PATTERNS:
        if re.search(pattern, query_lower, re.IGNORECASE):
            result.is_vague = True
            result.vague_patterns.append(vague_type)
            result.expansion_hints.append(hint)

    # Also flag very short queries with complex intent
    word_count = len(query.split())
    if word_count < 5 and understanding.complexity_label in (
        ComplexityLabel.COMPLEX,
        ComplexityLabel.VERY_COMPLEX,
    ):
        result.is_vague = True
        if VaguePattern.TOO_SHORT not in result.vague_patterns:
            result.vague_patterns.append(VaguePattern.TOO_SHORT)
            result.expansion_hints.append(
                "Short query detected for complex task -- inferring expanded intent"
            )

    # Step 2: Expand intent
    key = (understanding.intent, understanding.complexity_label)
    expansion = _INTENT_EXPANSIONS.get(key)

    if expansion is None:
        # Fallback: try with MODERATE complexity
        fallback_key = (understanding.intent, ComplexityLabel.MODERATE)
        expansion = _INTENT_EXPANSIONS.get(fallback_key)

    if expansion:
        result.power_user_intent = expansion.power_user_intent
        result.recommended_mode_override = expansion.recommended_mode
        result.recommended_reasoning_override = expansion.recommended_reasoning
        result.capability_hints = list(expansion.capability_hints)

    # Step 3: Resolve capability hints to runtime parameters
    runtime_params: dict[str, dict[str, Any]] = {}
    meta_params: dict[str, Any] = {}

    for hint in result.capability_hints:
        mapping = CAPABILITY_RUNTIME_MAP.get(hint, {})

        # Collect provider-specific params
        if provider in mapping:
            provider_params = mapping[provider]
            for k, v in provider_params.items():
                if k == "anthropic_beta":
                    # Merge beta headers
                    existing = runtime_params.get("anthropic_beta", [])
                    if isinstance(existing, list):
                        existing.extend(v)
                    runtime_params["anthropic_beta"] = existing
                else:
                    runtime_params[k] = v

        # Collect meta params (orchestration hints)
        if "_meta" in mapping:
            meta_params.update(mapping["_meta"])

    result.runtime_params = {
        "provider_params": runtime_params,
        "orchestration": meta_params,
    }

    # Step 4: Generate clarifying note if vague
    if result.is_vague and result.power_user_intent:
        result.clarifying_note = (
            f"I interpreted your request as: {result.power_user_intent}. "
            f"Using: {', '.join(result.capability_hints[:3])}."
        )

    elapsed_ns = time.monotonic_ns() - start
    result.processing_time_ms = int(elapsed_ns / 1_000_000)

    logger.debug(
        "intent_amplified",
        intent=understanding.intent.value,
        complexity=understanding.complexity_label.value,
        is_vague=result.is_vague,
        capabilities=result.capability_hints,
        time_ms=result.processing_time_ms,
    )

    return result
