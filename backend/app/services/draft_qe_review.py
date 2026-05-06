"""DraftQEReview -- Sprint-12 PR-3.

Runs a QE/Council review pass on a ResearchDraft or FormDraft using
the runtime slot assignments from
:pyfunc:`app.services.runtime_readiness.get_qe_readiness`.

The pipeline mirrors the three-stage council pattern from CLAUDE.md
(MIXTURE-OF-AGENTS + KARPATHY THREE-STAGE COUNCIL) but slimmed for
draft review (no chat-orchestrator overhead, no DCP injection):

    Stage 1 -- Proposer fan-out (parallel)
        Each ready slot that applies to drafts produces an
        independent review. Slots used here:
          * local_reasoner    -- cheap private first-pass
          * risk_reviewer     -- hallucinations + missing evidence
          * web_grounder      -- only fires when slot is filled
                                 (Perplexity ready) and the operator
                                 explicitly opts in via
                                 ``allow_web_grounding=True``.
        ``code_reviewer`` is excluded -- drafts aren't code.

    Stage 2 -- Anonymized synthesis
        ``final_synthesizer`` reads the proposer outputs labelled
        only as Reviewer A / B / C and produces the final summary
        the operator sees. Aggregates findings, objections, missing
        evidence, risk flags. Returns a single ``confidence`` plus
        ``next_action``.

Hard rules:

    * Read ``/system/qe-readiness`` first. Mode is reported HONESTLY
      (full / degraded / unavailable). Never claim ``full`` when
      ``mode != "full"``.
    * For ``unavailable`` mode: refuse with a stable code; do NOT
      run reviewers; return the readiness mode_reason as
      ``next_action``.
    * For ``degraded`` mode: run anyway, but the response carries
      ``mode="degraded"`` and the response's ``warnings`` list
      includes the readiness mode_reason.
    * Web grounding NEVER fires unless ``allow_web_grounding=True``
      AND the ``web_grounder`` slot is filled by a ready runtime.
      Default is False.
    * No paid metered_api call without ``allow_metered=True`` AND
      the routed slot resolves to a metered runtime.
    * NEVER expose hidden chain-of-thought from any reviewer. The
      response only carries the structured summary fields.
    * Audit one ``draft.qe_review.<kind>`` row per call.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ModelProvider
from app.core.logging import get_logger
from app.models.form_draft import FormDraft
from app.models.research import ResearchDraft
from app.services.audit import AuditService
from app.services.draft_enrichment import (
    EnrichmentRefused,
    MeteredApiNotAllowed,
    NoReadyMainBrain,
    RUNTIME_TO_PROVIDER,
    _call_main_brain,
    _extract_json,
    select_provider,
    RoutedSelection,
)
from app.services.runtime_readiness import get_qe_readiness


logger = get_logger(__name__)


# Slots used for draft review. code_reviewer is intentionally
# excluded -- drafts aren't code, so the slot makes no sense here.
_DRAFT_REVIEW_PROPOSER_SLOTS = (
    "local_reasoner", "risk_reviewer", "web_grounder",
)
_DRAFT_REVIEW_SYNTH_SLOT = "final_synthesizer"


# ── Errors ────────────────────────────────────────────────────────────


class QECouncilUnavailable(EnrichmentRefused):
    def __init__(self, mode_reason: str) -> None:
        super().__init__(
            "qe_council_unavailable",
            next_action=mode_reason,
        )


class QECouncilWebGroundingNotAllowed(EnrichmentRefused):
    def __init__(self) -> None:
        super().__init__(
            "web_grounding_not_allowed",
            next_action=(
                "web_grounder slot is filled but allow_web_grounding=False. "
                "Pass allow_web_grounding=True OR the slot will stay "
                "unused for this review."
            ),
        )


# ── Result shapes ────────────────────────────────────────────────────


@dataclass(slots=True)
class ReviewerOutput:
    slot: str
    runtime_id: str
    cost_class: str
    findings: list[str] = field(default_factory=list)
    objections: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    confidence: float = 0.0
    notes: str | None = None
    failed: bool = False


@dataclass(slots=True)
class QEReviewResult:
    draft_id: str
    draft_kind: str
    mode: Literal["full", "degraded", "unavailable"]
    mode_reason: str
    distinct_runtime_ids: list[str]
    proposer_outputs: list[ReviewerOutput]
    synthesizer_runtime_id: str | None
    findings: list[str]
    objections: list[str]
    missing_evidence: list[str]
    risk_flags: list[str]
    confidence: float
    next_action: str
    warnings: list[str] = field(default_factory=list)


# ── Slot resolution ──────────────────────────────────────────────────


def _slot_to_routed(
    qe_readiness: dict[str, Any],
    slot_name: str,
    *,
    allow_metered: bool,
) -> RoutedSelection | None:
    """Map a ``qe_readiness`` slot assignment to a RoutedSelection.

    Returns None when:
      * slot is unfilled
      * routed runtime is metered_api and ``allow_metered=False``
      * routed runtime id has no provider mapping
    """
    slot = next(
        (
            a for a in qe_readiness["slot_assignments"]
            if a["slot"] == slot_name
        ),
        None,
    )
    if slot is None or not slot.get("runtime_id"):
        return None
    runtime_id = slot["runtime_id"]
    provider_enum = RUNTIME_TO_PROVIDER.get(runtime_id)
    if provider_enum is None:
        return None
    # We need the cost_class; the qe_readiness payload doesn't carry
    # it, so we infer from RUNTIME_TO_PROVIDER + the readiness layer's
    # contract. Free_local providers map to OLLAMA / VLLM enums;
    # subscription CLIs map to ANTHROPIC / OPENAI / GEMINI enums when
    # the API key is absent. We trust the readiness layer's invariant:
    # if the runtime is in slot_assignments, it is ``readiness_state=
    # "ready"`` -- which for metered_api requires explicit auth.
    # Subscription CLIs and free_local pass without metered.
    cost_class = "free_local"
    if runtime_id.startswith("provider_"):
        cost_class = "metered_api"
    elif runtime_id.startswith("cli_"):
        cost_class = "subscription"
    if cost_class == "metered_api" and not allow_metered:
        return None
    return RoutedSelection(
        runtime_id=runtime_id,
        cost_class=cost_class,
        provider_enum=provider_enum,
        rationale=f"qe_readiness assigned {runtime_id} to slot {slot_name}.",
    )


# ── Prompts ──────────────────────────────────────────────────────────


def _draft_summary_for_review(
    *, kind: str, draft: ResearchDraft | FormDraft,
) -> dict[str, Any]:
    """Reduce the draft to the minimum the LLM needs.

    We deliberately do NOT pass raw_extract or full HTML into the
    review prompt. Reviewers see the structured payload + key
    metadata only.
    """
    if isinstance(draft, ResearchDraft):
        return {
            "kind": kind,
            "id": str(draft.id),
            "goal": draft.goal,
            "source_host": draft.source_host,
            "structured_payload": draft.structured_payload,
        }
    # FormDraft
    questions = []
    for f in (draft.fields or []):
        questions.append({
            "label": f.label,
            "field_type": f.field_type,
            "suggested_value": f.suggested_value,
            "value": f.value,
            "needs_review": f.needs_review,
            "confidence": f.confidence,
        })
    return {
        "kind": "form",
        "id": str(draft.id),
        "goal": draft.goal,
        "title": draft.title,
        "fields": questions,
    }


_REVIEW_SCHEMA = (
    "Return STRICT JSON with these top-level keys: "
    "findings (string list), objections (string list), "
    "missing_evidence (string list), risk_flags (string list), "
    "confidence (float 0-1), notes (string). Output ONLY JSON."
)


def _proposer_prompt(slot: str, draft_dict: dict[str, Any]) -> tuple[str, str]:
    role_intent = {
        "local_reasoner": (
            "You are a CHEAP first-pass reviewer. Catch obvious "
            "problems: missing fields, contradictions inside the "
            "payload, fields the enrichment pass clearly hallucinated. "
            "Be terse."
        ),
        "risk_reviewer": (
            "You are a RISK reviewer. Look for hallucinations "
            "('too good to be true' fit_score, claims not grounded "
            "in the source), security implications, scope creep, "
            "over-confident outreach drafts. List every concern."
        ),
        "web_grounder": (
            "You are a WEB-GROUNDED reviewer. The operator has opted "
            "in to web verification. Identify claims that need live "
            "web verification and flag them in missing_evidence + "
            "claims_to_verify."
        ),
    }.get(slot, "You are a generic reviewer.")
    system = (
        f"You are Daena's QE-{slot} for draft review. {role_intent} "
        f"NEVER expose your reasoning or chain-of-thought. NEVER "
        f"include any 'send' / 'submit' / 'apply' / 'post' field. "
        f"{_REVIEW_SCHEMA}"
    )
    user = (
        f"Draft to review:\n"
        f"{json.dumps(draft_dict, ensure_ascii=False, default=str)}"
    )
    return system, user


def _synth_prompt(
    *, draft_dict: dict[str, Any], proposers: list[ReviewerOutput],
) -> tuple[str, str]:
    # Anonymize -- reviewers labelled A/B/C, no model names.
    labels = ["A", "B", "C", "D", "E"]
    block: list[dict[str, Any]] = []
    for i, p in enumerate(proposers):
        if p.failed:
            continue
        block.append({
            "label": f"Reviewer {labels[i]}",
            "findings": p.findings,
            "objections": p.objections,
            "missing_evidence": p.missing_evidence,
            "risk_flags": p.risk_flags,
            "confidence": p.confidence,
        })
    system = (
        "You are Daena's QE final synthesizer. You receive multiple "
        "anonymized reviews of the same draft. Aggregate them: "
        "deduplicate findings, escalate any objection raised by "
        "two or more reviewers, list every missing_evidence + "
        "risk_flag in the union, and produce a single overall "
        "confidence (use the LOWER end of the reviewers' range when "
        "they disagree). Decide the next action: 'approve_for_workstream', "
        "'operator_review_required', or 'reject_with_reason'. "
        "Return STRICT JSON with keys: findings, objections, "
        "missing_evidence, risk_flags, confidence (0-1), "
        "next_action (string), reasoning (one short sentence). "
        "NEVER expose chain-of-thought beyond the one-sentence "
        "reasoning field. NEVER include a 'submit' or 'send' field."
    )
    user = (
        f"Draft summary:\n"
        f"{json.dumps(draft_dict, ensure_ascii=False, default=str)}\n\n"
        f"Anonymized reviews:\n"
        f"{json.dumps(block, ensure_ascii=False)}"
    )
    return system, user


# ── Coercion ─────────────────────────────────────────────────────────


def _coerce_str_list(v: Any, *, limit: int = 24) -> list[str]:
    if not isinstance(v, list):
        return []
    out: list[str] = []
    for x in v:
        if isinstance(x, str) and x.strip():
            out.append(x.strip()[:600])
        if len(out) >= limit:
            break
    return out


def _coerce_confidence(v: Any) -> float:
    try:
        f = float(v)
        return max(0.0, min(1.0, f))
    except Exception:
        return 0.0


def _proposer_from_json(
    slot: str,
    selection: RoutedSelection,
    parsed: dict[str, Any] | None,
) -> ReviewerOutput:
    if not parsed:
        return ReviewerOutput(
            slot=slot,
            runtime_id=selection.runtime_id,
            cost_class=selection.cost_class,
            failed=True,
        )
    return ReviewerOutput(
        slot=slot,
        runtime_id=selection.runtime_id,
        cost_class=selection.cost_class,
        findings=_coerce_str_list(parsed.get("findings")),
        objections=_coerce_str_list(parsed.get("objections")),
        missing_evidence=_coerce_str_list(parsed.get("missing_evidence")),
        risk_flags=_coerce_str_list(parsed.get("risk_flags")),
        confidence=_coerce_confidence(parsed.get("confidence", 0.5)),
        notes=str(parsed.get("notes") or "")[:600] or None,
    )


# ── Public API ───────────────────────────────────────────────────────


async def run_draft_qe_review(
    db: AsyncSession,
    draft: ResearchDraft | FormDraft,
    *,
    allow_metered: bool = False,
    allow_web_grounding: bool = False,
    qe_readiness: dict[str, Any] | None = None,
    registry: Any = None,
    actor_id: uuid.UUID | None = None,
) -> QEReviewResult:
    """Run a QE/Council review pass on a draft.

    Args:
      draft: ResearchDraft or FormDraft instance (already loaded).
      allow_metered: Allow metered_api runtimes to fill review slots.
      allow_web_grounding: Allow Perplexity (web_grounder slot) to
        fire. Default False because Perplexity is metered.
      qe_readiness: Pre-fetched payload (testing hook).
      registry: ModelRegistry from app.state. Required.
      actor_id: User triggering the review (for audit).

    Raises:
      QECouncilUnavailable: zero ready reviewers; nothing fired.

    Returns:
      QEReviewResult with honest mode + per-reviewer outputs +
      synthesized summary.
    """
    qe = qe_readiness or await get_qe_readiness()
    mode = qe.get("mode", "unavailable")
    mode_reason = qe.get("mode_reason", "")
    audit = AuditService(db)
    kind = "form" if isinstance(draft, FormDraft) else (draft.kind or "unknown")

    if mode == "unavailable":
        await audit.log_decision(
            tenant_id=draft.tenant_id,
            actor_id=actor_id,
            actor_type="SYSTEM",
            action_type=f"draft.qe_review.{kind}",
            action_params={
                "draft_id": str(draft.id),
                "refusal_code": "qe_council_unavailable",
                "mode_reason": mode_reason[:500],
            },
            result="BLOCKED",
            risk_level="LOW",
            governance_tier=1,
        )
        raise QECouncilUnavailable(mode_reason)

    # Collect proposer routes
    proposer_routes: list[tuple[str, RoutedSelection]] = []
    for slot_name in _DRAFT_REVIEW_PROPOSER_SLOTS:
        if slot_name == "web_grounder" and not allow_web_grounding:
            continue
        sel = _slot_to_routed(qe, slot_name, allow_metered=allow_metered)
        if sel is None:
            continue
        proposer_routes.append((slot_name, sel))

    if not proposer_routes:
        await audit.log_decision(
            tenant_id=draft.tenant_id,
            actor_id=actor_id,
            actor_type="SYSTEM",
            action_type=f"draft.qe_review.{kind}",
            action_params={
                "draft_id": str(draft.id),
                "refusal_code": "no_eligible_reviewers",
                "allow_metered": allow_metered,
                "allow_web_grounding": allow_web_grounding,
            },
            result="BLOCKED",
            risk_level="LOW",
            governance_tier=1,
        )
        raise QECouncilUnavailable(
            "No proposer slots can fire under the current allow flags. "
            "Pass allow_metered=True OR start a local model.",
        )

    # Reduce draft for review
    draft_dict = _draft_summary_for_review(kind=kind, draft=draft)

    # Stage 1: proposer fan-out (parallel)
    async def _run_one(
        slot_name: str, sel: RoutedSelection,
    ) -> ReviewerOutput:
        sys_p, usr_p = _proposer_prompt(slot_name, draft_dict)
        try:
            text, _meta = await _call_main_brain(
                selection=sel, system=sys_p, user=usr_p,
                max_tokens=900, registry=registry,
            )
            parsed = _extract_json(text)
        except Exception:
            logger.exception(
                "draft_qe_review.proposer_call_failed",
                draft_id=str(draft.id),
                slot=slot_name,
                runtime_id=sel.runtime_id,
            )
            parsed = None
        return _proposer_from_json(slot_name, sel, parsed)

    proposer_outputs = await asyncio.gather(
        *[_run_one(name, sel) for name, sel in proposer_routes],
    )
    proposer_outputs = list(proposer_outputs)

    # Distinct runtimes touched. Used to decide if we can claim mode=full
    # NOT JUST trust the readiness label.
    distinct = sorted({p.runtime_id for p in proposer_outputs})
    successful = [p for p in proposer_outputs if not p.failed]

    # Stage 2: synthesize
    synth_route = _slot_to_routed(
        qe, _DRAFT_REVIEW_SYNTH_SLOT, allow_metered=allow_metered,
    )
    if synth_route is None and proposer_routes:
        # Fall back to the first proposer's runtime as synthesizer.
        synth_route = proposer_routes[0][1]

    synth_text = ""
    parsed: dict[str, Any] | None = None
    if synth_route is not None and successful:
        sys_p, usr_p = _synth_prompt(
            draft_dict=draft_dict, proposers=successful,
        )
        try:
            synth_text, _meta = await _call_main_brain(
                selection=synth_route, system=sys_p, user=usr_p,
                max_tokens=1200, registry=registry,
            )
            parsed = _extract_json(synth_text)
        except Exception:
            logger.exception(
                "draft_qe_review.synth_call_failed",
                draft_id=str(draft.id),
            )
            parsed = None

    # Final aggregation
    findings: list[str] = []
    objections: list[str] = []
    missing_evidence: list[str] = []
    risk_flags: list[str] = []
    if parsed:
        findings = _coerce_str_list(parsed.get("findings"), limit=30)
        objections = _coerce_str_list(parsed.get("objections"), limit=30)
        missing_evidence = _coerce_str_list(parsed.get("missing_evidence"), limit=30)
        risk_flags = _coerce_str_list(parsed.get("risk_flags"), limit=30)
        confidence = _coerce_confidence(parsed.get("confidence", 0.0))
        next_action = str(parsed.get("next_action") or "operator_review_required")
    else:
        # Synth failed -- fall back to the union of proposer outputs.
        for p in successful:
            findings.extend(p.findings)
            objections.extend(p.objections)
            missing_evidence.extend(p.missing_evidence)
            risk_flags.extend(p.risk_flags)
        confidence = (
            min(p.confidence for p in successful) if successful else 0.0
        )
        next_action = "operator_review_required"

    # Honest mode: if we don't actually have 2+ distinct runtimes
    # contributing successfully, we collapse to degraded regardless
    # of what the readiness payload said.
    final_mode: Literal["full", "degraded", "unavailable"]
    if len(distinct) >= 2 and len(successful) >= 2:
        final_mode = "full"
    elif successful:
        final_mode = "degraded"
    else:
        final_mode = "unavailable"

    warnings: list[str] = []
    if final_mode != "full":
        warnings.append(
            "QE ran in degraded mode -- there is no real peer "
            "cross-check when reviewers share a runtime or some "
            "reviewers failed.",
        )
    if mode != final_mode:
        warnings.append(
            f"qe_readiness reported mode={mode!r} but actual run "
            f"resolved to mode={final_mode!r}. Acting on the actual "
            f"run, not the snapshot.",
        )

    # Audit
    await audit.log_decision(
        tenant_id=draft.tenant_id,
        actor_id=actor_id,
        actor_type="SYSTEM",
        action_type=f"draft.qe_review.{kind}",
        action_params={
            "draft_id": str(draft.id),
            "mode_readiness": mode,
            "mode_actual": final_mode,
            "distinct_runtime_ids": distinct,
            "proposer_count": len(proposer_outputs),
            "successful_proposers": len(successful),
            "confidence": confidence,
            "next_action": next_action,
            "synthesizer_runtime_id": synth_route.runtime_id if synth_route else None,
        },
        result="ALLOWED",
        risk_level="LOW",
        governance_tier=1,
    )

    return QEReviewResult(
        draft_id=str(draft.id),
        draft_kind=kind,
        mode=final_mode,
        mode_reason=mode_reason,
        distinct_runtime_ids=distinct,
        proposer_outputs=proposer_outputs,
        synthesizer_runtime_id=(
            synth_route.runtime_id if synth_route else None
        ),
        findings=findings,
        objections=objections,
        missing_evidence=missing_evidence,
        risk_flags=risk_flags,
        confidence=confidence,
        next_action=next_action,
        warnings=warnings,
    )
