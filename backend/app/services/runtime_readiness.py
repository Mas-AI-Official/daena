"""Runtime readiness overlay -- Sprint-12A PR-1.

A thin overlay on top of ``runtime_truth_registry`` that adds the
*operational* layer the supervised-work brain needs:

    * ``cost_class``       -- free_local / subscription / metered_api / unknown
    * ``recommended_role`` -- main_brain / qe_reviewer / coder / researcher
                              / web_grounding / fallback / none
    * ``readiness_state``  -- ready / configured_untested / not_configured /
                              detected_offline / unknown
    * ``recommended_role_rationale`` -- one-liner the UI can render
    * Aggregated ``router_summary`` describing what Daena can actually
      do right now (which provider for main enrichment, which provider
      for web grounding, whether QE/Council is full or degraded).

This file owns NO discovery logic -- it reads the truth registry and
classifies. Truth = source of facts; readiness = source of decisions.
Single source of truth per CLAUDE.md Rule 2.

Hard rules baked in:

    * Returned items NEVER carry secret values. Booleans + metadata only.
    * No paid API calls. ``cost_class=metered_api`` items report
      ``readiness_state=configured_untested`` until an explicit
      operator action runs the per-provider zero-cost test.
    * If a critical role is unfilled (no main_brain ready), the
      ``router_summary`` says so honestly with a ``next_action``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.services.runtime_truth_registry import runtime_truth_registry


# ── Constants ────────────────────────────────────────────────────────


CostClass = Literal["free_local", "subscription", "metered_api", "unknown"]
RecommendedRole = Literal[
    "main_brain",
    "qe_reviewer",
    "coder",
    "researcher",
    "web_grounding",
    "fallback",
    "none",
]
ReadinessState = Literal[
    "ready",
    "configured_untested",
    "not_configured",
    "detected_offline",
    "unknown",
]


# Per-runtime classification map. Mirrors the IDs emitted by
# RuntimeTruthRegistry._discover_items so a missing entry here
# surfaces in tests as recommended_role="none".
#
# Tier ordering for each role: lower index = preferred when callable.
RUNTIME_CLASSIFICATION: dict[str, dict[str, Any]] = {
    # Local LLM endpoints -- free, fast, private. Default main brain.
    "vllm_configured": {
        "cost_class": "free_local",
        "primary_role": "main_brain",
        "secondary_roles": ["qe_reviewer", "coder"],
        "rationale": (
            "Local llama.cpp / vLLM endpoint -- zero cost, private, "
            "default main brain when callable."
        ),
    },
    "ollama_backend": {
        "cost_class": "free_local",
        "primary_role": "main_brain",
        "secondary_roles": ["qe_reviewer"],
        "rationale": "Local Ollama endpoint -- zero cost, private fallback.",
    },
    "ollama_windows": {
        "cost_class": "free_local",
        "primary_role": "fallback",
        "secondary_roles": ["main_brain"],
        "rationale": (
            "Ollama on Windows host (via host.docker.internal) -- "
            "fallback when backend-local Ollama isn't reachable."
        ),
    },

    # CLI runtimes -- subscription / fixed-cost. Coder + reviewer.
    "cli_claude": {
        "cost_class": "subscription",
        "primary_role": "coder",
        "secondary_roles": ["qe_reviewer", "main_brain"],
        "rationale": (
            "Claude Code CLI -- subscription brain. Strong on multi-file "
            "refactors + pair design. Probed via local CLI binary; "
            "no API key in chat."
        ),
    },
    "cli_codex": {
        "cost_class": "subscription",
        "primary_role": "coder",
        "secondary_roles": ["qe_reviewer"],
        "rationale": (
            "OpenAI Codex CLI -- subscription brain. Strong on tight "
            "single-file algorithmic work + async fire-and-forget."
        ),
    },
    "cli_gemini": {
        "cost_class": "subscription",
        "primary_role": "researcher",
        "secondary_roles": ["main_brain"],
        "rationale": (
            "Gemini CLI -- subscription brain. Good for long-context "
            "research synthesis + Google workspace tasks."
        ),
    },
    "cli_ollama": {
        "cost_class": "free_local",
        "primary_role": "fallback",
        "secondary_roles": [],
        "rationale": "Ollama CLI binary -- supports the local endpoints.",
    },

    # API providers -- metered. Used selectively.
    "provider_perplexity": {
        "cost_class": "metered_api",
        "primary_role": "web_grounding",
        "secondary_roles": ["researcher"],
        "rationale": (
            "Perplexity API -- web-grounded research. Use ONLY for "
            "queries that require live web data; never as the default "
            "main brain because it bills per call."
        ),
    },
    "provider_anthropic": {
        "cost_class": "metered_api",
        "primary_role": "qe_reviewer",
        "secondary_roles": ["main_brain", "coder"],
        "rationale": (
            "Anthropic API -- premium reviewer for hard QE/Council "
            "calls. Metered; gated behind explicit operator approval."
        ),
    },
    "provider_openai": {
        "cost_class": "metered_api",
        "primary_role": "qe_reviewer",
        "secondary_roles": ["main_brain"],
        "rationale": (
            "OpenAI API -- second QE reviewer. Metered; gated behind "
            "explicit operator approval."
        ),
    },
    "provider_gemini": {
        "cost_class": "metered_api",
        "primary_role": "researcher",
        "secondary_roles": ["main_brain"],
        "rationale": "Gemini API -- long-context research. Metered.",
    },
    "provider_groq": {
        "cost_class": "metered_api",
        "primary_role": "fallback",
        "secondary_roles": ["coder"],
        "rationale": "Groq API -- fast inference, fallback main brain.",
    },
    "provider_openrouter": {
        "cost_class": "metered_api",
        "primary_role": "fallback",
        "secondary_roles": [],
        "rationale": (
            "OpenRouter API -- multi-model gateway. Use deliberately, "
            "never as silent default."
        ),
    },
    "provider_together": {
        "cost_class": "metered_api",
        "primary_role": "fallback",
        "secondary_roles": [],
        "rationale": "Together API -- open-weights inference fallback.",
    },
}


# ── Result shapes ────────────────────────────────────────────────────


@dataclass(slots=True)
class ReadinessItem:
    """One row in the readiness inventory.

    Mirrors the truth-registry RuntimeTruthItem fields the UI needs
    (without secrets) plus the readiness overlay.
    """
    id: str
    display_name: str
    kind: Literal["local_llm", "cli_runtime", "api_provider", "runtime", "other"]
    detected: bool
    configured: bool
    authenticated_or_key_present: bool
    reachable: bool
    callable: bool
    model_count: int
    cost_class: CostClass
    recommended_role: RecommendedRole
    secondary_roles: list[str]
    readiness_state: ReadinessState
    recommended_role_rationale: str
    safe_failure_reason: str | None
    endpoint: str | None
    last_health_check: str | None


@dataclass(slots=True)
class RouterSummary:
    """Aggregated decision metadata the UI + smoke tests consume."""
    main_brain_id: str | None
    main_brain_cost_class: CostClass | None
    web_grounding_id: str | None
    coder_id: str | None
    researcher_id: str | None
    qe_reviewers_ready: list[str] = field(default_factory=list)
    qe_mode: Literal["full", "degraded", "unavailable"] = "unavailable"
    qe_mode_reason: str = ""
    next_action: str = ""


# ── Classification ───────────────────────────────────────────────────


def _kind_of(item: dict[str, Any]) -> str:
    """Map RuntimeTruthItem.type to a UI-friendly kind."""
    t = (item.get("type") or "").lower()
    item_id = item.get("id") or ""
    if t == "cli":
        return "cli_runtime"
    if t == "local_model":
        return "local_llm"
    if t == "api":
        return "api_provider"
    # CLI binaries that the truth registry tags as "runtime" (node, npm,
    # python, docker) are dependencies, not brains themselves.
    if t == "runtime":
        return "runtime"
    if item_id.startswith("provider_"):
        return "api_provider"
    return "other"


def _readiness_state(item: dict[str, Any], cost_class: str) -> ReadinessState:
    """Compute the readiness ladder bucket for an item."""
    detected = bool(item.get("detected"))
    configured = bool(item.get("configured"))
    callable_ = bool(item.get("callable"))
    reachable = bool(item.get("reachable_from_backend"))
    auth = item.get("authenticated")

    if not detected and not configured:
        return "not_configured"
    if cost_class == "free_local":
        # Local: callable means reachable + responding.
        if callable_ or reachable:
            return "ready"
        return "detected_offline" if (detected or configured) else "not_configured"
    if cost_class == "subscription":
        # CLI: detected + reachable from PATH = ready (auth probe is
        # explicitly NOT done -- would spend tokens).
        if callable_:
            return "ready"
        if detected:
            return "configured_untested"
        return "not_configured"
    if cost_class == "metered_api":
        # API key present is the only safe signal we have without
        # spending money. Tests must be initiated explicitly.
        if configured and auth is True:
            return "ready"
        if configured:
            return "configured_untested"
        return "not_configured"
    return "unknown"


def _classify_item(item: dict[str, Any]) -> ReadinessItem:
    item_id = item.get("id") or ""
    classification = RUNTIME_CLASSIFICATION.get(item_id, {
        "cost_class": "unknown",
        "primary_role": "none",
        "secondary_roles": [],
        "rationale": "No classification entry; runtime is uncategorized.",
    })
    cost_class = classification["cost_class"]
    state = _readiness_state(item, cost_class)
    primary = classification["primary_role"]
    # Demote primary role to "none" if the runtime is not ready -- the
    # router shouldn't list a not-ready provider as a candidate.
    if state != "ready" and primary != "none":
        recommended = "none"
    else:
        recommended = primary

    auth_field = item.get("authenticated")
    auth_present = bool(auth_field is True or auth_field == "unknown" and item.get("configured"))

    return ReadinessItem(
        id=item_id,
        display_name=str(item.get("display_name") or item_id),
        kind=_kind_of(item),  # type: ignore[arg-type]
        detected=bool(item.get("detected")),
        configured=bool(item.get("configured")),
        authenticated_or_key_present=auth_present,
        reachable=bool(item.get("reachable_from_backend")),
        callable=bool(item.get("callable")),
        model_count=len(item.get("models_tools_discovered") or []),
        cost_class=cost_class,
        recommended_role=recommended,
        secondary_roles=list(classification["secondary_roles"]),
        readiness_state=state,
        recommended_role_rationale=classification["rationale"],
        safe_failure_reason=item.get("last_failure_reason"),
        endpoint=item.get("endpoint"),
        last_health_check=item.get("last_health_check"),
    )


# ── Aggregation ──────────────────────────────────────────────────────


def _pick_for_role(
    items: list[ReadinessItem], role: RecommendedRole,
) -> ReadinessItem | None:
    """Return the first ready item whose primary or secondary role
    matches ``role``. Primary matches always beat secondary matches."""
    primary = [
        i for i in items
        if i.readiness_state == "ready" and i.recommended_role == role
    ]
    if primary:
        return primary[0]
    secondary = [
        i for i in items
        if i.readiness_state == "ready" and role in i.secondary_roles
    ]
    if secondary:
        return secondary[0]
    return None


def _build_router_summary(items: list[ReadinessItem]) -> RouterSummary:
    main = _pick_for_role(items, "main_brain")
    web = _pick_for_role(items, "web_grounding")
    coder = _pick_for_role(items, "coder")
    researcher = _pick_for_role(items, "researcher")

    # QE reviewers: any ready item whose primary or secondary roles
    # include qe_reviewer. The same item can fill main_brain AND
    # qe_reviewer slots in degraded mode but the smoke test enforces
    # full mode requires 2+ DISTINCT runtimes.
    qe_candidates = [
        i for i in items
        if i.readiness_state == "ready"
        and (i.recommended_role == "qe_reviewer"
             or "qe_reviewer" in i.secondary_roles)
    ]

    if len(qe_candidates) >= 2:
        qe_mode: Literal["full", "degraded", "unavailable"] = "full"
        qe_reason = (
            f"{len(qe_candidates)} reviewers ready: "
            f"{', '.join(c.id for c in qe_candidates[:5])}."
        )
    elif len(qe_candidates) == 1:
        qe_mode = "degraded"
        qe_reason = (
            f"Only one reviewer ready ({qe_candidates[0].id}); "
            f"QE will run in degraded mode without peer cross-check."
        )
    else:
        qe_mode = "unavailable"
        qe_reason = (
            "No QE reviewer is currently ready. Configure Anthropic / "
            "OpenAI / a second local model, or start the local "
            "endpoint."
        )

    next_action = ""
    if main is None:
        next_action = (
            "Start the local llama-server / vLLM endpoint at "
            "VLLM_BASE_URL or Ollama at OLLAMA_BASE_URL. No main "
            "brain is ready, so brain-enrichment work is blocked."
        )
    elif qe_mode == "unavailable":
        next_action = (
            "Configure at least one second runtime (Anthropic API "
            "key, OpenAI API key, or a second local model) so QE "
            "can run in full mode."
        )
    else:
        next_action = "Brain-enrichment is unblocked. Sprint-12 PR-1 may proceed."

    return RouterSummary(
        main_brain_id=main.id if main else None,
        main_brain_cost_class=main.cost_class if main else None,
        web_grounding_id=web.id if web else None,
        coder_id=coder.id if coder else None,
        researcher_id=researcher.id if researcher else None,
        qe_reviewers_ready=[c.id for c in qe_candidates],
        qe_mode=qe_mode,
        qe_mode_reason=qe_reason,
        next_action=next_action,
    )


# ── Public API ───────────────────────────────────────────────────────


async def get_runtime_readiness(refresh: bool = False) -> dict[str, Any]:
    """Return the readiness inventory + router summary.

    Args:
        refresh: When True, ask the truth registry to re-discover
            items first. Default False so the endpoint stays cheap.

    Returns:
        ``{"items": [ReadinessItem...], "router_summary": RouterSummary}``
        with NO secret values, NO API key bytes, NO tokens.
    """
    if refresh:
        truth = await runtime_truth_registry.refresh()
    else:
        truth = await runtime_truth_registry.get_truth()
    raw_items: list[dict[str, Any]] = list(truth.get("items") or [])
    classified: list[ReadinessItem] = [_classify_item(it) for it in raw_items]
    summary = _build_router_summary(classified)

    return {
        "items": [item_to_dict(c) for c in classified],
        "router_summary": summary_to_dict(summary),
        "updated_at": truth.get("updated_at"),
    }


def item_to_dict(item: ReadinessItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "display_name": item.display_name,
        "kind": item.kind,
        "detected": item.detected,
        "configured": item.configured,
        "authenticated_or_key_present": item.authenticated_or_key_present,
        "reachable": item.reachable,
        "callable": item.callable,
        "model_count": item.model_count,
        "cost_class": item.cost_class,
        "recommended_role": item.recommended_role,
        "secondary_roles": item.secondary_roles,
        "readiness_state": item.readiness_state,
        "recommended_role_rationale": item.recommended_role_rationale,
        "safe_failure_reason": item.safe_failure_reason,
        "endpoint": item.endpoint,
        "last_health_check": item.last_health_check,
    }


def summary_to_dict(s: RouterSummary) -> dict[str, Any]:
    return {
        "main_brain_id": s.main_brain_id,
        "main_brain_cost_class": s.main_brain_cost_class,
        "web_grounding_id": s.web_grounding_id,
        "coder_id": s.coder_id,
        "researcher_id": s.researcher_id,
        "qe_reviewers_ready": s.qe_reviewers_ready,
        "qe_mode": s.qe_mode,
        "qe_mode_reason": s.qe_mode_reason,
        "next_action": s.next_action,
    }


# ── Sprint-12A PR-3: QE/Council slot assignment ─────────────────────


# The five named QE/Council reviewer slots. Each slot has:
#   * intent     -- what kind of review it does
#   * preferred  -- ordered list of runtime ids that can fill the slot
#   * fallback_role -- if no preferred id is ready, fall back to any
#                       runtime in the readiness pool whose primary or
#                       secondary role matches this string
#
# The slots overlap on purpose. local_reasoner and code_reviewer can
# share a runtime when only one is ready -- the qe_mode tells the
# operator what mode QE is running in.
QE_SLOTS: dict[str, dict[str, Any]] = {
    "local_reasoner": {
        "intent": (
            "Cheap, private, deterministic first-pass review. Catches "
            "the obvious problems before paid lanes fire."
        ),
        "preferred": ["vllm_configured", "ollama_backend"],
        "fallback_role": "main_brain",
    },
    "code_reviewer": {
        "intent": (
            "Cross-file impact + refactor quality review. Wants the "
            "model best at reading whole modules."
        ),
        "preferred": ["cli_claude", "cli_codex", "vllm_configured"],
        "fallback_role": "coder",
    },
    "web_grounder": {
        "intent": (
            "Verifies claims that depend on live information (recent "
            "events, current pricing, regulation changes)."
        ),
        "preferred": ["provider_perplexity"],
        "fallback_role": "web_grounding",
    },
    "risk_reviewer": {
        "intent": (
            "Looks for hallucinations, missing evidence, security "
            "implications, scope creep, and 'too good to be true' "
            "fit_scores."
        ),
        "preferred": [
            "provider_anthropic", "provider_openai", "cli_claude",
        ],
        "fallback_role": "qe_reviewer",
    },
    "final_synthesizer": {
        "intent": (
            "Reads the other reviewers and writes the final summary "
            "the operator sees. Strong synthesis matters more than "
            "raw capability here."
        ),
        "preferred": [
            "vllm_configured", "ollama_backend", "cli_claude",
            "provider_anthropic",
        ],
        "fallback_role": "main_brain",
    },
}


@dataclass(slots=True)
class QESlotAssignment:
    slot: str
    intent: str
    runtime_id: str | None
    runtime_display_name: str | None
    fill_source: Literal["preferred", "fallback_role", "unfilled"]
    rationale: str


@dataclass(slots=True)
class QEReadiness:
    mode: Literal["full", "degraded", "unavailable"]
    distinct_runtime_ids: list[str]
    slot_assignments: list[QESlotAssignment]
    mode_reason: str


def _pick_for_slot(
    slot_name: str,
    spec: dict[str, Any],
    items: list[ReadinessItem],
    already_used: set[str],
) -> QESlotAssignment:
    """Resolve one QE slot to a ready runtime.

    Preferred ids beat fallback-role lookups. Within either tier, a
    runtime not yet assigned to another slot beats one that already
    is -- this is what gives QE actual diversity. Re-use is permitted
    when there is no other choice; the mode field tells the operator
    QE is running degraded.
    """
    ready_by_id = {i.id: i for i in items if i.readiness_state == "ready"}

    # 1. Try preferred ids in order, prioritising un-used.
    for preferred_id in spec["preferred"]:
        if preferred_id in ready_by_id and preferred_id not in already_used:
            it = ready_by_id[preferred_id]
            return QESlotAssignment(
                slot=slot_name,
                intent=spec["intent"],
                runtime_id=it.id,
                runtime_display_name=it.display_name,
                fill_source="preferred",
                rationale=f"Preferred runtime {it.id} is ready and unassigned.",
            )

    # 2. Fallback to any ready runtime whose primary/secondary role matches.
    fallback_role = spec.get("fallback_role")
    if fallback_role:
        candidates = [
            i for i in items
            if i.readiness_state == "ready"
            and (i.recommended_role == fallback_role
                 or fallback_role in i.secondary_roles)
        ]
        for it in candidates:
            if it.id not in already_used:
                return QESlotAssignment(
                    slot=slot_name,
                    intent=spec["intent"],
                    runtime_id=it.id,
                    runtime_display_name=it.display_name,
                    fill_source="fallback_role",
                    rationale=(
                        f"No preferred runtime ready; falling back to "
                        f"{it.id} via fallback_role={fallback_role!r}."
                    ),
                )

    # 3. Last resort: re-use a preferred runtime even though it's
    #    already assigned to another slot. QE flips to degraded when
    #    this happens for any slot.
    for preferred_id in spec["preferred"]:
        if preferred_id in ready_by_id:
            it = ready_by_id[preferred_id]
            return QESlotAssignment(
                slot=slot_name,
                intent=spec["intent"],
                runtime_id=it.id,
                runtime_display_name=it.display_name,
                fill_source="fallback_role",
                rationale=(
                    f"All preferred runtimes already assigned to other "
                    f"slots; re-using {it.id}. QE will run degraded."
                ),
            )

    return QESlotAssignment(
        slot=slot_name,
        intent=spec["intent"],
        runtime_id=None,
        runtime_display_name=None,
        fill_source="unfilled",
        rationale=(
            f"No ready runtime matches preferred IDs "
            f"({spec['preferred']!r}) or fallback role "
            f"({spec.get('fallback_role')!r})."
        ),
    )


def assign_qe_slots(items: list[ReadinessItem]) -> QEReadiness:
    """Assign each of the five QE slots to a ready runtime.

    Returns ``QEReadiness`` with:
      * ``mode``: full / degraded / unavailable
      * ``distinct_runtime_ids``: how many DIFFERENT runtimes
        contributed to the council
      * ``slot_assignments``: per-slot detail (or unfilled)
      * ``mode_reason``: plain-English string the UI renders
    """
    assignments: list[QESlotAssignment] = []
    used: set[str] = set()
    for slot_name, spec in QE_SLOTS.items():
        a = _pick_for_slot(slot_name, spec, items, used)
        assignments.append(a)
        if a.runtime_id is not None:
            used.add(a.runtime_id)

    distinct = sorted({a.runtime_id for a in assignments if a.runtime_id})
    filled_count = sum(1 for a in assignments if a.runtime_id is not None)

    if filled_count == 0:
        mode: Literal["full", "degraded", "unavailable"] = "unavailable"
        reason = (
            "No QE slot could be filled. Configure at least one local "
            "model or one CLI/API provider before running Council."
        )
    elif len(distinct) >= 2 and filled_count >= 3:
        mode = "full"
        reason = (
            f"{filled_count} slots filled with {len(distinct)} distinct "
            f"runtimes. QE can run with peer cross-check."
        )
    else:
        mode = "degraded"
        reason = (
            f"{filled_count} slots filled with {len(distinct)} distinct "
            f"runtime(s). QE runs in degraded mode -- there is no real "
            f"peer cross-check when reviewers are the same model. "
            f"Configure a second runtime to upgrade to full mode."
        )

    return QEReadiness(
        mode=mode,
        distinct_runtime_ids=distinct,
        slot_assignments=assignments,
        mode_reason=reason,
    )


def qe_readiness_to_dict(qe: QEReadiness) -> dict[str, Any]:
    return {
        "mode": qe.mode,
        "mode_reason": qe.mode_reason,
        "distinct_runtime_ids": qe.distinct_runtime_ids,
        "slot_assignments": [
            {
                "slot": a.slot,
                "intent": a.intent,
                "runtime_id": a.runtime_id,
                "runtime_display_name": a.runtime_display_name,
                "fill_source": a.fill_source,
                "rationale": a.rationale,
            }
            for a in qe.slot_assignments
        ],
    }


async def get_qe_readiness(refresh: bool = False) -> dict[str, Any]:
    """Public entry: fetch readiness + assign QE slots."""
    if refresh:
        truth = await runtime_truth_registry.refresh()
    else:
        truth = await runtime_truth_registry.get_truth()
    raw_items: list[dict[str, Any]] = list(truth.get("items") or [])
    classified = [_classify_item(it) for it in raw_items]
    qe = assign_qe_slots(classified)
    return qe_readiness_to_dict(qe)


def get_router_policy() -> dict[str, Any]:
    """Return the static router policy matrix (no I/O).

    Lets the UI render "where would Daena route X" without first
    refreshing the truth registry.
    """
    return {
        "version": "2026-05-05.v1",
        "roles": {
            "main_brain": {
                "intent": "default brain-enrichment + chat reasoning",
                "preference_order": [
                    "vllm_configured",
                    "ollama_backend",
                    "ollama_windows",
                    "cli_claude",
                    "cli_codex",
                    "cli_gemini",
                    "provider_anthropic",
                    "provider_openai",
                    "provider_groq",
                ],
                "guard": "Default to free_local; metered_api requires explicit operator opt-in.",
            },
            "qe_reviewer": {
                "intent": "Council / QE peer review of drafts and decisions",
                "preference_order": [
                    "vllm_configured",
                    "ollama_backend",
                    "cli_claude",
                    "provider_anthropic",
                    "provider_openai",
                ],
                "guard": "Need >=2 distinct ready runtimes for full mode; otherwise degraded.",
            },
            "coder": {
                "intent": "code review / refactor / scaffolding",
                "preference_order": [
                    "cli_claude",
                    "cli_codex",
                    "vllm_configured",
                    "ollama_backend",
                    "provider_anthropic",
                ],
                "guard": "Prefer subscription CLIs over metered APIs.",
            },
            "researcher": {
                "intent": "long-context summarisation, doc synthesis",
                "preference_order": [
                    "cli_gemini",
                    "vllm_configured",
                    "provider_gemini",
                    "ollama_backend",
                ],
                "guard": "Local first; Gemini API only for long-context that local cannot handle.",
            },
            "web_grounding": {
                "intent": "queries that require live web information",
                "preference_order": ["provider_perplexity"],
                "guard": (
                    "Perplexity ONLY when the query genuinely needs live web; "
                    "never as a silent default."
                ),
            },
            "fallback": {
                "intent": "last-resort brain when nothing else is ready",
                "preference_order": [
                    "ollama_windows",
                    "provider_groq",
                    "provider_openrouter",
                    "provider_together",
                ],
                "guard": "Reach for fallbacks ONLY when primary lanes are unavailable.",
            },
        },
        "hard_rules": [
            "No paid API call without ready=true on the chosen provider.",
            "No silent metered_api usage when a free_local option is ready.",
            "QE/Council requires >=2 distinct ready runtimes for full mode.",
            "Audit every router decision via integration.tool_invocation pattern.",
        ],
    }
