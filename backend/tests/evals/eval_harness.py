"""Lightweight eval harness primitives.

A real (not hollow) framework: EvalCase declares an acceptance check, run_eval
executes a deterministic assertion fn and records a structured pass/fail, and the
registry documents the full intended coverage so partially-implemented evals are
visible rather than silently absent.

Judge policy: deterministic-first. judge_available() gates any optional
LLM-as-judge scoring behind DAENA_EVAL_JUDGE so the harness never makes a paid
or networked call unless the operator explicitly opts in.
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EvalCase:
    """One behavioral acceptance check."""

    name: str
    category: str  # fallback | memory | governance | tool_safety | settings | error
    description: str
    implemented: bool = True  # False = declared coverage, deterministic check pending


@dataclass
class EvalResult:
    name: str
    passed: bool
    detail: str = ""
    skipped: bool = False


def judge_available() -> bool:
    """Whether an opt-in LLM judge is configured. Off by default (no paid surprise)."""
    return bool(os.getenv("DAENA_EVAL_JUDGE", "").strip())


async def run_eval(
    case: EvalCase,
    fn: Callable[[], Awaitable[tuple[bool, str]]],
) -> EvalResult:
    """Run a deterministic eval fn returning (passed, detail). Never raises."""
    if not case.implemented:
        return EvalResult(case.name, passed=False, skipped=True, detail="not yet implemented")
    try:
        passed, detail = await fn()
        return EvalResult(case.name, passed=passed, detail=detail)
    except Exception as exc:  # noqa: BLE001 - an eval error is a fail, not a crash
        return EvalResult(case.name, passed=False, detail=f"error: {exc}")


# The full intended coverage. Deterministic evals implemented now reuse code paths
# verified this session; LLM-judge-dependent ones are declared (implemented=False)
# so the gap is explicit, not hidden.
EVAL_REGISTRY: list[EvalCase] = [
    EvalCase("settings.heartbeat_roundtrip", "settings",
             "operator heartbeat config persists + rehydrates across a restart"),
    EvalCase("tool_safety.trace_no_secret_capture", "tool_safety",
             "run tracer never persists secret-looking metadata values"),
    EvalCase("error.trace_failopen", "error",
             "tracing failure never propagates into the chat path"),
    EvalCase("fallback.ragx_failopen", "fallback",
             "ragx grounding returns empty (no raise) when the service is down"),
    EvalCase("memory.recall_semantic", "memory",
             "follow-up turn recalls prior context", implemented=False),
    EvalCase("governance.refusal_high_risk", "governance",
             "tier-3+ action requires approval, not auto-execute", implemented=False),
]
