"""Self-Healing Service -- Sprint-13 PR-6 (2026-05-06).

Daena detects subsystem failures and authors repair workstreams.
Cross-brain redundancy is encoded at the *suggested-brain* layer:
mechanical patches go to Codex (async-native, the right tool to
"hand-it-a-ticket-and-walk-away"); multi-file diagnosis goes to
Claude Code; runtime probing goes to the local-llm path (Ollama /
llama-server / vLLM) so the foreground never blocks on a paid call.

This module ships the detection + workstream-payload assembly. It
does NOT apply patches, run tests, or commit code. The operator (or
the trust-graduated autonomous loop in a future PR after the Phase 3
design lock) drives the actual patch.

Failure taxonomy
----------------

Eight failure subsystems, closed set:

::

    backend_health           backend uvicorn process is unreachable
    frontend_health          vite dev server is unreachable
    main_brain_not_ready     router_readiness has no callable main brain
    cli_runtime_offline      a configured Claude / Codex / Gemini CLI
                             is not callable
    mcp_probe_fail           an MCP server config exists but probe
                             failed
    schema_drift             alembic head != applied head
    fe_be_route_404          frontend calls a route that no backend
                             router mounts
    test_regression          pytest fast subset has new failures

Each failure is stamped with a deterministic ``id`` so a repair
workstream cannot be duplicated for the same root cause within a
single detection sweep. Repair workstreams land in Engineering by
default; Security Operations for ``mcp_probe_fail`` involving a
security-tagged MCP. The operator can override the routing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal


FailureSubsystem = Literal[
    "backend_health",
    "frontend_health",
    "main_brain_not_ready",
    "cli_runtime_offline",
    "mcp_probe_fail",
    "schema_drift",
    "fe_be_route_404",
    "test_regression",
]


FailureSeverity = Literal["info", "warn", "blocker"]


# Suggested brain per repair work class. Encodes the cross-AI
# delegation table from CLAUDE.md so the autonomous repair loop
# picks the right tool for the job. The operator can override.
SuggestedBrain = Literal[
    "codex_cli",       # async mechanical patches
    "claude_code",     # multi-file reasoning + design
    "ollama_backend",  # local probes / drafts (free)
    "vllm",            # local high-throughput when ollama busy
    "human",           # founder must look at this
]


@dataclass(frozen=True)
class Failure:
    """A single detected subsystem failure."""

    id: str
    subsystem: FailureSubsystem
    severity: FailureSeverity
    description: str
    suggested_brain: SuggestedBrain
    repair_action_class: str   # high-level "what kind of fix"
    department_hint: str       # "Engineering" / "Security Operations" / etc.
    evidence: dict = field(default_factory=dict)


# -------------------------------------------------------------------------
# Detection
# -------------------------------------------------------------------------


def enumerate_failures(probes: dict) -> list[Failure]:
    """Inspect the readiness ``probes`` dict and return the closed-set
    list of failures.

    The function is pure: callers inject the probe outputs (typically
    captured from /system/runtime-readiness, /system/router-readiness,
    /health, /system/morning-readiness) and get back a stable list.
    No HTTP, no DB, no LLM call here.

    Probes shape (all keys optional; absent keys are treated as
    "no signal", not as failures):

    ::

        {
          "backend_health":     {"reachable": bool, "detail": str},
          "frontend_health":    {"reachable": bool, "detail": str},
          "router_readiness":   {"main_brain_ready": bool, ...},
          "runtime_readiness":  {"items": [{"id":..,"readiness_state":..}, ...]},
          "schema_head":        {"alembic_head": str, "applied_head": str},
          "fe_be_routes":       {"frontend_calls": [...], "backend_paths": [...]},
          "test_regression":    {"newly_failing": [...]},
        }
    """

    out: list[Failure] = []

    bh = probes.get("backend_health") or {}
    if bh.get("reachable") is False:
        out.append(Failure(
            id="backend_health:unreachable",
            subsystem="backend_health",
            severity="blocker",
            description="Backend uvicorn is unreachable on the configured port.",
            suggested_brain="ollama_backend",
            repair_action_class="restart_or_diagnose_backend",
            department_hint="Engineering",
            evidence={"detail": str(bh.get("detail") or "")},
        ))

    fh = probes.get("frontend_health") or {}
    if fh.get("reachable") is False:
        out.append(Failure(
            id="frontend_health:unreachable",
            subsystem="frontend_health",
            severity="warn",
            description="Frontend Vite dev server is unreachable.",
            suggested_brain="ollama_backend",
            repair_action_class="restart_or_diagnose_frontend",
            department_hint="Engineering",
            evidence={"detail": str(fh.get("detail") or "")},
        ))

    rr = probes.get("router_readiness") or {}
    if rr and rr.get("main_brain_ready") is False:
        out.append(Failure(
            id="main_brain:not_ready",
            subsystem="main_brain_not_ready",
            severity="blocker",
            description=(
                "No callable main brain. Router fallback chain has no "
                "ready candidate. Operator action required to start a "
                "local model or refresh CLI auth."
            ),
            suggested_brain="human",
            repair_action_class="prompt_operator_to_choose_main_brain",
            department_hint="Engineering",
            evidence={"detail": str(rr.get("detail") or "")},
        ))

    runtime = probes.get("runtime_readiness") or {}
    items = runtime.get("items") or []
    for item in items:
        item_id = str(item.get("id") or "")
        kind = str(item.get("kind") or "")
        state = str(item.get("readiness_state") or "")
        if kind == "cli_runtime" and state == "detected_offline":
            out.append(Failure(
                id=f"cli_runtime:{item_id}:offline",
                subsystem="cli_runtime_offline",
                severity="warn",
                description=(
                    f"CLI runtime {item_id!r} detected but not callable. "
                    f"Likely auth expired or the binary moved."
                ),
                # Mechanical: re-run `<cli> login` or rebind path.
                suggested_brain="codex_cli",
                repair_action_class="refresh_cli_auth_or_rebind",
                department_hint="Engineering",
                evidence={"runtime_id": item_id},
            ))

    sh = probes.get("schema_head") or {}
    if sh and sh.get("alembic_head") and sh.get("applied_head"):
        if sh["alembic_head"] != sh["applied_head"]:
            out.append(Failure(
                id="schema_drift:head_mismatch",
                subsystem="schema_drift",
                severity="blocker",
                description=(
                    f"Alembic head {sh['alembic_head']} does not match "
                    f"applied head {sh['applied_head']}. Run "
                    f"`alembic upgrade head`."
                ),
                # Multi-file reasoning: schema + model + migration must
                # agree. Claude Code is the right tool.
                suggested_brain="claude_code",
                repair_action_class="reconcile_schema_drift",
                department_hint="Engineering",
                evidence={
                    "alembic_head": sh["alembic_head"],
                    "applied_head": sh["applied_head"],
                },
            ))

    routes = probes.get("fe_be_routes") or {}
    fe_calls = list(routes.get("frontend_calls") or [])
    be_paths = set(routes.get("backend_paths") or [])
    if fe_calls and be_paths:
        for path in fe_calls:
            if path not in be_paths:
                out.append(Failure(
                    id=f"fe_be_route_404:{path}",
                    subsystem="fe_be_route_404",
                    severity="warn",
                    description=(
                        f"Frontend calls {path!r} but the backend "
                        f"router does not mount it."
                    ),
                    # Mechanical: add the missing router or rename the
                    # frontend call.
                    suggested_brain="codex_cli",
                    repair_action_class="add_missing_route_or_rename_caller",
                    department_hint="Engineering",
                    evidence={"path": path},
                ))

    tr = probes.get("test_regression") or {}
    newly_failing = list(tr.get("newly_failing") or [])
    if newly_failing:
        out.append(Failure(
            id=f"test_regression:{len(newly_failing)}_failing",
            subsystem="test_regression",
            severity="warn",
            description=(
                f"Pytest fast subset has {len(newly_failing)} newly "
                "failing test(s)."
            ),
            # Multi-file reasoning -- root cause may span many files.
            suggested_brain="claude_code",
            repair_action_class="diagnose_and_fix_regression",
            department_hint="Engineering",
            evidence={"newly_failing": newly_failing[:8]},
        ))

    mcp = probes.get("mcp_probe_fail") or {}
    failed_mcps = list(mcp.get("failed") or [])
    for entry in failed_mcps:
        name = str(entry.get("name") or "?")
        is_security = bool(entry.get("security_tagged"))
        out.append(Failure(
            id=f"mcp_probe_fail:{name}",
            subsystem="mcp_probe_fail",
            severity="warn",
            description=(
                f"MCP server {name!r} failed its probe. Likely process "
                "missing or auth expired."
            ),
            suggested_brain="codex_cli",
            repair_action_class="restart_or_re_register_mcp",
            department_hint=(
                "Security Operations" if is_security else "Engineering"
            ),
            evidence={"mcp_name": name},
        ))

    return out


# -------------------------------------------------------------------------
# Workstream payload
# -------------------------------------------------------------------------


def repair_workstream_payload(failure: Failure) -> dict:
    """Return the payload the workstream router would consume to
    create a repair workstream for this failure.

    Pure function -- the caller is responsible for the actual write.
    The shape is locked: only fields the existing
    ``WorkstreamService.start`` understands appear here, plus a
    ``self_repair`` namespace inside ``initial_context`` that future
    consumers can read.
    """
    return {
        "goal": (
            f"Self-repair: {failure.description}"
        )[:500],
        "department_hint": failure.department_hint,
        "next_step_text": (
            f"Suggested brain: {failure.suggested_brain}. "
            f"Repair action class: {failure.repair_action_class}."
        )[:500],
        "initial_context": {
            "self_repair": {
                "failure_id": failure.id,
                "subsystem": failure.subsystem,
                "severity": failure.severity,
                "suggested_brain": failure.suggested_brain,
                "repair_action_class": failure.repair_action_class,
                "evidence": dict(failure.evidence or {}),
                # Encode the "Daena proposes; never auto-executes"
                # rule. This is the SAME guard the action factory
                # uses (PR-4): every self-repair starts in
                # propose-only mode.
                "delivery": "manual_only",
                "requires_approval": True,
            },
        },
    }
