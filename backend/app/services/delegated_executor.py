"""Real executor for delegated VP tasks (P1 -- replaces the simulated ticker).

``ExecutionService._background_run`` calls ``execute_delegated_step`` for any
task whose checkpoint_data carries a delegation envelope with
``origin == "delegated"`` (materialized by ``delegated_goals.materialize_plan``).
One governed model call produces the step's work product; the returned dict
becomes ``task.result``.

Contract (v1 -- "delegated-llm-v1"):
  * SINGLE SHOT, NO TOOLS. The executor performs CMD-grade text work only: it
    drafts / analyzes / summarizes, it never sends, publishes, deploys, or
    spends. The spend/outward approval gate in ``run_task`` fires BEFORE this
    code runs; approval authorizes the step, not autonomous tool use. The EXE
    tool loop (DaenaBot dispatch through ``execute_tool``'s gate pipeline) is
    a later ticket.
  * HONEST FAILURE (ADR-001 / Rule 17). A provider outage, timeout, or empty
    completion RAISES; the caller marks the task FAILED with the error. There
    is no silent fallback to simulated success -- a fake COMPLETED is worse
    than a retryable FAILED (FAILED is in run_task's runnable set).
  * SESSION-FREE. Receives plain scalars captured before the request session
    closed (same race guard as ``experience_ingest``); never touches the DB.
  * Provider resilience comes from ``LLMService.generate_direct``: requested
    provider first, then cross-provider failover with circuit breaking.

``build_step_prompt`` is pure so the prompt contract is testable without a
model. The module-level registry cache avoids re-probing providers on every
delegated step; a benign init race (two concurrent firsts) just initializes
twice -- both instances are valid, last one wins.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from app.core.logging import get_logger

logger = get_logger(__name__)

EXECUTOR_NAME = "delegated-llm-v1"

# One model call per step. A work product needs more room than a chat turn
# (the orchestrator's inline idiom uses 45s) but must still bound a hung
# provider so the task cannot sit RUNNING forever.
_STEP_TIMEOUT_S = 120.0
_MAX_TOKENS = 2000
_TEMPERATURE = 0.35

# Lazily-initialized ModelRegistry shared by all delegated steps in this
# process. None until first use; stays None only while init keeps failing
# (each call retries, so a provider coming online is picked up).
_REGISTRY: Any = None


def build_step_prompt(
    *, name: str, description: str, delegation: dict[str, Any]
) -> tuple[str, str]:
    """Build (system_prompt, user_prompt) for one delegated step.

    Pure and deterministic: same inputs -> same strings. The system prompt
    pins the no-tools honesty contract so an approved outward step yields a
    ready-to-send artifact, never a false "sent it" claim.
    """
    department = str(delegation.get("department") or "General")
    goal = str(delegation.get("goal") or "").strip()
    classification = str(delegation.get("classification") or "free")
    step_index = delegation.get("step_index")

    system_prompt = (
        f"You are the {department} department of Daena, the AI company VP. "
        "Produce the complete work product for your assigned step as clean "
        "markdown. You have NO tools in this run: never claim to have sent, "
        "published, deployed, bought, or executed anything -- deliver the "
        "text artifact itself (the draft, the analysis, the plan). "
        "If part of the step cannot be finished by reasoning and writing "
        "alone, deliver what you can and end with a '## Blocked' section "
        "listing exactly what is missing. Do not invent facts you cannot "
        "know; mark assumptions explicitly."
    )

    user_lines = [f"# Assigned step: {name}"]
    if goal:
        user_lines += ["", f"Overall goal this step serves: {goal}"]
    if step_index is not None:
        user_lines += [f"Step index in the plan: {step_index}"]
    user_lines += [f"Governance classification: {classification}"]
    if description and description.strip() and description.strip() != name:
        user_lines += ["", "## Step description", "", description.strip()]
    user_lines += [
        "",
        "Produce the finished work product for this step now.",
    ]
    return system_prompt, "\n".join(user_lines)


async def _get_registry() -> Any:
    """Return the shared ModelRegistry, initializing it on first use.

    Fail-soft: returns None when initialization fails (no providers / bad
    config) so the caller can decide how to surface it. Mirrors the
    established off-request pattern (cognitive_reasoner.auto_select_model).
    """
    global _REGISTRY
    if _REGISTRY is not None:
        return _REGISTRY
    try:
        from app.services.model_registry import ModelRegistry

        registry = ModelRegistry()
        await registry.initialize()
        _REGISTRY = registry
        return registry
    except Exception:
        logger.warning(
            "delegated_executor.registry_init_failed", exc_info=True
        )
        return None


async def _pick_model(registry: Any) -> str | None:
    """Best-effort model choice via ModelRouter's tier system.

    Returns a model_id or None; None lets ``generate_direct`` walk every
    available provider with its own default, so selection failure is never
    fatal (the actual generate call decides success).
    """
    try:
        from app.services.model_router import ModelRouter

        best = ModelRouter(registry).select_best_single(offensive=False)
        if best is not None:
            return best.model_id
        for m in await registry.list_all_models():
            mid = m.model_id.lower()
            if "embed" not in mid and "nomic" not in mid:
                return m.model_id
    except Exception:
        logger.debug("delegated_executor.model_select_failed", exc_info=True)
    return None


async def execute_delegated_step(
    *,
    name: str,
    description: str,
    delegation: dict[str, Any],
    tenant_id: UUID,
    llm_service: Any = None,
    registry: Any = None,
) -> dict[str, Any]:
    """Execute one delegated step with a single governed model call.

    Args:
        name: Task name (subtask description head).
        description: Full task description ("[Dept] step text").
        delegation: The delegation envelope from checkpoint_data (plain dict
            copy -- goal / department / classification / step_index).
        tenant_id: Tenant scope, recorded in request metadata for audit.
        llm_service: Test seam; defaults to ``LLMService(registry)``.
        registry: Test seam; defaults to the shared lazy registry.

    Returns:
        JSON-serializable result dict for ``task.result`` -- artifact plus
        model / provider / token / cost audit fields.

    Raises:
        RuntimeError: no registry, timeout, or empty completion.
        ProviderUnavailableError: every provider failed (from LLMService).
    """
    system_prompt, user_prompt = build_step_prompt(
        name=name, description=description, delegation=delegation
    )

    if registry is None:
        registry = await _get_registry()
    if llm_service is None:
        if registry is None:
            raise RuntimeError(
                "delegated executor: model registry unavailable "
                "(no providers initialized); task can be retried"
            )
        from app.services.llm_service import LLMService

        llm_service = LLMService(registry)

    model_id = await _pick_model(registry) if registry is not None else None

    from app.services.providers.base import GenerateRequest, LLMMessage

    request = GenerateRequest(
        messages=[LLMMessage(role="user", content=user_prompt)],
        model_id=model_id,
        temperature=_TEMPERATURE,
        max_tokens=_MAX_TOKENS,
        system_prompt=system_prompt,
        metadata={
            "origin": "delegated",
            "executor": EXECUTOR_NAME,
            "tenant_id": str(tenant_id),
        },
    )

    try:
        response = await asyncio.wait_for(
            llm_service.generate_direct(request), timeout=_STEP_TIMEOUT_S
        )
    except (asyncio.TimeoutError, TimeoutError):
        raise RuntimeError(
            f"delegated step timed out after {_STEP_TIMEOUT_S:.0f}s "
            "waiting for the model"
        ) from None

    artifact = (response.content or "").strip()
    if not artifact:
        raise RuntimeError(
            "model returned an empty artifact; refusing to mark the "
            "step complete"
        )

    provider = getattr(response.provider, "value", None) or str(
        response.provider
    )
    department = delegation.get("department") or "General"
    return {
        "executor": EXECUTOR_NAME,
        "summary": f"[{department}] {name}"[:200],
        "artifact": artifact,
        "artifact_format": "markdown",
        "model_id": response.model_id,
        "provider": provider,
        "department": delegation.get("department"),
        "classification": delegation.get("classification"),
        "step_index": delegation.get("step_index"),
        "goal": str(delegation.get("goal") or "")[:500],
        "tokens_input": response.token_count_input,
        "tokens_output": response.token_count_output,
        "cost_usd": response.cost_usd,
        "latency_ms": response.latency_ms,
    }
