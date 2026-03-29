"""Capability Matrix: task type classification and runtime scoring.

Maps user intents and query understanding results to capability fields
that the RuntimeRegistry uses for selection. This bridges the existing
QueryUnderstanding system with the new runtime selection engine.
"""

from __future__ import annotations

from app.services.query_understanding import IntentType

# Map QueryUnderstanding intents to runtime capability fields.
# When a user's intent is classified, this tells us which capability
# dimension matters most for runtime selection.
INTENT_TO_TASK_TYPE: dict[IntentType, str] = {
    IntentType.SIMPLE: "simple_chat",
    IntentType.SEARCH: "web_research",
    IntentType.CODING: "code_generation",
    IntentType.ANALYSIS: "data_analysis",
    IntentType.CREATIVE: "simple_chat",
    IntentType.MULTI_STEP: "complex_reasoning",
    IntentType.DANGEROUS: "complex_reasoning",
    IntentType.AMBIGUOUS: "simple_chat",
}

# For EXE mode, we may need secondary capabilities. E.g., a CODING task
# in EXE mode needs code_generation + file_operations.
INTENT_TO_SECONDARY_TASKS: dict[IntentType, list[str]] = {
    IntentType.CODING: ["code_editing", "file_operations"],
    IntentType.MULTI_STEP: ["code_generation", "file_operations", "web_research"],
    IntentType.SEARCH: ["data_analysis"],
    IntentType.ANALYSIS: ["web_research"],
}

# Weights for composite scoring when multiple capabilities matter.
PRIMARY_WEIGHT = 0.65
SECONDARY_WEIGHT = 0.35


def task_type_for_intent(intent: IntentType) -> str:
    """Get the primary task type for a query understanding intent."""
    return INTENT_TO_TASK_TYPE.get(intent, "simple_chat")


def composite_score(
    capabilities: dict[str, float],
    intent: IntentType,
) -> float:
    """Calculate a composite capability score for a runtime given an intent.

    Blends primary task type score (65%) with average of secondary
    task type scores (35%). If no secondary tasks, primary gets 100%.

    Args:
        capabilities: Dict of capability field -> score (0-10).
        intent: The classified user intent.

    Returns:
        Composite score 0.0-10.0.
    """
    primary_task = task_type_for_intent(intent)
    primary_score = capabilities.get(primary_task, 0.0)

    secondary_tasks = INTENT_TO_SECONDARY_TASKS.get(intent, [])
    if not secondary_tasks:
        return primary_score

    secondary_scores = [
        capabilities.get(t, 0.0) for t in secondary_tasks
    ]
    avg_secondary = sum(secondary_scores) / len(secondary_scores) if secondary_scores else 0.0

    return (PRIMARY_WEIGHT * primary_score) + (SECONDARY_WEIGHT * avg_secondary)


def rank_runtimes(
    runtime_capabilities: dict[str, dict[str, float]],
    intent: IntentType,
    cost_ceiling: float | None = None,
) -> list[tuple[str, float]]:
    """Rank runtimes by composite score for an intent.

    Args:
        runtime_capabilities: {runtime_id: {capability: score}}.
        intent: Classified intent.
        cost_ceiling: Max $/1K tokens (None = no limit).

    Returns:
        List of (runtime_id, composite_score) sorted descending.
    """
    scored: list[tuple[str, float]] = []
    for rid, caps in runtime_capabilities.items():
        if cost_ceiling is not None:
            cost = caps.get("cost_per_1k_tokens", 0.0)
            if cost > cost_ceiling:
                continue
        score = composite_score(caps, intent)
        scored.append((rid, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
