"""VPWorkCommands -- Sprint-12 PR-5.

Lightweight natural-English command parser + runner that lets the
operator drive Daena's draft-and-workstream pipeline from chat
without touching the API surface manually:

    - "Daena, review this opportunity"        -> show latest drafts
    - "Enrich draft <id>"                     -> POST /enrich
    - "Run council on draft <id>"             -> POST /qe-review
    - "Create a work plan from draft <id>"    -> POST /workstreams/from-draft
    - "What should I do next?"                -> show open workstreams
                                                 + next_step_text
    - "Which department should handle this <id>?"
                                              -> deterministic routing answer

Hard rules baked in:

    * Deterministic backend state ONLY -- the parser uses regex,
      and the runner reads / writes through the existing service
      modules (no LLM call inside this service to interpret the
      command itself; the underlying services may call LLM where
      they already do, e.g. enrichment / council).
    * NEVER fabricates a draft id when the operator's text doesn't
      include one; instead returns ``needs_disambiguation`` with
      the recent drafts so the chat UI can render a follow-up.
    * When a command needs a runtime that isn't ready (e.g. enrich
      with no main brain), the underlying refusal flows through
      and the chat surface shows the readiness next_action verbatim.
    * No external action. None of the runners send / submit / post
      / apply / publish to anything outside Daena.
    * Audits one ``vp_command.<verb>`` row per call, with the
      parsed verb + draft_ref so operator history is filterable.

The parser ONLY answers known verbs; ambiguous input returns
``intent="unrecognized"`` so the chat orchestrator can fall through
to its normal LLM path. This module does NOT replace the chat
orchestrator -- it sits on top as a fast deterministic router.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.form_draft import FormDraft
from app.models.research import ResearchDraft
from app.models.workstream import (
    Workstream,
    WorkstreamSourceType,
    WorkstreamStatus,
)
from app.services.audit import AuditService


logger = get_logger(__name__)


VPIntent = Literal[
    "review_drafts",
    "enrich_draft",
    "qe_review_draft",
    "create_workstream_from_draft",
    "next_steps",
    "which_department",
    "unrecognized",
]


# UUID string -- accept full or short prefix (>=8 hex chars). The
# runner re-validates by querying. Drafts are tenant-scoped so a
# 8-char prefix is fine for the operator's own data set.
_UUID_PREFIX = re.compile(
    r"\b([0-9a-f]{8,}(?:-[0-9a-f]+)*)\b",
    re.IGNORECASE,
)


def _find_uuid_in_text(text: str) -> str | None:
    """Return the longest UUID-like token, or None.

    We accept full UUIDs and 8+-char prefixes so the operator can
    paste short forms from the UI. The runner re-checks with a
    real DB lookup that is tenant + user-scoped.
    """
    candidates = _UUID_PREFIX.findall(text or "")
    if not candidates:
        return None
    candidates.sort(key=len, reverse=True)
    return candidates[0]


# ── Parser ───────────────────────────────────────────────────────────


@dataclass(slots=True)
class ParsedCommand:
    intent: VPIntent
    raw: str
    draft_ref: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


_REVIEW_RE = re.compile(
    r"\b(review)\b.*\b(opportunity|opportunities|draft|drafts|content)\b",
    re.IGNORECASE,
)
_LIST_RE = re.compile(
    r"\b(list|show|see|view)\b.*\b(draft|drafts|opportunity|opportunities)\b",
    re.IGNORECASE,
)
_ENRICH_RE = re.compile(
    r"\b(enrich|fill|complete|fill\s+in)\b.*\b(draft|opportunity|form|content)\b",
    re.IGNORECASE,
)
_QE_RE = re.compile(
    r"\b(run\s+council|council|qe\s+review|review\s+council|"
    r"run\s+qe|peer\s+review)\b",
    re.IGNORECASE,
)
_WORKPLAN_RE = re.compile(
    r"\b(create|make|build|spin\s+up|promote)\b.*\b("
    r"work\s*plan|workstream|plan\s+of\s+work|next\s+steps?\s+plan)\b",
    re.IGNORECASE,
)
_WORKPLAN_FROM_RE = re.compile(
    r"\bfrom\b.*\b(this|that|draft|opportunity|content|form)\b",
    re.IGNORECASE,
)
_NEXT_RE = re.compile(
    r"\b(what\s+(?:should|do)\s+(?:i|we)\s+do\s+next|"
    r"what'?s\s+next|what\s+is\s+next|"
    r"next\s+step|next\s+steps?|"
    r"what\s+(?:should|do)\s+(?:i|we)\s+work\s+on|"
    r"what\s+now)\b",
    re.IGNORECASE,
)
_DEPT_RE = re.compile(
    r"\bwhich\s+department\b|\bwho\s+(?:should\s+)?handle(s)?\b|"
    r"\b(?:route|assign)\s+(?:this\s+)?to\s+which\s+department\b",
    re.IGNORECASE,
)


def parse_command(text: str) -> ParsedCommand:
    """Return the intent + draft ref extracted from a user message.

    The parser is permissive on noise -- "Daena, please run council
    on draft 12345678" parses the same as "council 12345678". The
    parser is strict on AMBIGUITY though: a verb that needs a draft
    id and gets none returns ``draft_ref=None`` so the runner can
    decide how to disambiguate.
    """
    raw = text or ""

    # Order matters: the most-specific verbs come first so a generic
    # "review" doesn't swallow "review council".
    ref = _find_uuid_in_text(raw)

    if _QE_RE.search(raw):
        return ParsedCommand(
            intent="qe_review_draft", raw=raw, draft_ref=ref,
        )
    if _ENRICH_RE.search(raw):
        return ParsedCommand(
            intent="enrich_draft", raw=raw, draft_ref=ref,
        )
    # "what should I do next" before "which department"
    if _NEXT_RE.search(raw):
        return ParsedCommand(intent="next_steps", raw=raw)
    if _DEPT_RE.search(raw):
        return ParsedCommand(
            intent="which_department", raw=raw, draft_ref=ref,
        )
    if _WORKPLAN_RE.search(raw):
        # A clear workplan verb is enough -- the runner will return
        # needs_disambiguation when no draft id is present.
        return ParsedCommand(
            intent="create_workstream_from_draft",
            raw=raw, draft_ref=ref,
        )
    if _REVIEW_RE.search(raw) or _LIST_RE.search(raw):
        return ParsedCommand(intent="review_drafts", raw=raw)

    return ParsedCommand(intent="unrecognized", raw=raw)


# ── Runner ───────────────────────────────────────────────────────────


@dataclass(slots=True)
class CommandResult:
    """What the chat layer renders. Stable across runners."""
    intent: VPIntent
    success: bool
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    needs_disambiguation: bool = False
    next_action: str | None = None


async def _resolve_draft(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    draft_ref: str | None,
) -> tuple[
    Literal["career", "content", "form"] | None,
    ResearchDraft | FormDraft | None,
]:
    """Look up a draft by id-prefix in the operator's scope.

    Tries ResearchDraft first, then FormDraft. Returns (kind, draft)
    or (None, None) if nothing matches.
    """
    if not draft_ref:
        return None, None
    # Try exact UUID first
    try:
        full = uuid.UUID(draft_ref)
        for cls, kinds in (
            (ResearchDraft, ("career", "content")),
            (FormDraft, ("form",)),
        ):
            row = (await db.execute(
                select(cls).where(
                    cls.id == full,
                    cls.tenant_id == tenant_id,
                    cls.user_id == user_id,
                )
            )).scalar_one_or_none()
            if row is not None:
                kind = (
                    row.kind if isinstance(row, ResearchDraft) else "form"
                )
                return kind, row  # type: ignore[return-value]
        return None, None
    except ValueError:
        pass
    # Prefix search via string conversion. ResearchDraft first.
    rdrafts = (await db.execute(
        select(ResearchDraft).where(
            ResearchDraft.tenant_id == tenant_id,
            ResearchDraft.user_id == user_id,
        )
    )).scalars().all()
    for r in rdrafts:
        if str(r.id).lower().startswith(draft_ref.lower()):
            return r.kind, r   # type: ignore[return-value]
    fdrafts = (await db.execute(
        select(FormDraft).where(
            FormDraft.tenant_id == tenant_id,
            FormDraft.user_id == user_id,
        )
    )).scalars().all()
    for f in fdrafts:
        if str(f.id).lower().startswith(draft_ref.lower()):
            return "form", f
    return None, None


async def _list_recent_drafts_summary(
    db: AsyncSession, *, user_id: uuid.UUID, tenant_id: uuid.UUID,
    limit: int = 10,
) -> dict[str, Any]:
    rdrafts = (await db.execute(
        select(ResearchDraft).where(
            ResearchDraft.tenant_id == tenant_id,
            ResearchDraft.user_id == user_id,
        ).order_by(desc(ResearchDraft.created_at)).limit(limit)
    )).scalars().all()
    fdrafts = (await db.execute(
        select(FormDraft).where(
            FormDraft.tenant_id == tenant_id,
            FormDraft.user_id == user_id,
        ).order_by(desc(FormDraft.created_at)).limit(limit)
    )).scalars().all()
    return {
        "research_drafts": [
            {
                "id": str(r.id),
                "kind": r.kind,
                "status": r.status,
                "goal": (r.goal or "")[:120],
                "_llm_pending": bool(
                    (r.structured_payload or {}).get("_llm_pending"),
                ),
            } for r in rdrafts
        ],
        "form_drafts": [
            {
                "id": str(f.id),
                "title": f.title,
                "status": f.status,
                "goal": (f.goal or "")[:120],
            } for f in fdrafts
        ],
    }


async def _next_steps_summary(
    db: AsyncSession, *, user_id: uuid.UUID, tenant_id: uuid.UUID,
    limit: int = 10,
) -> dict[str, Any]:
    rows = (await db.execute(
        select(Workstream).where(
            Workstream.tenant_id == tenant_id,
            Workstream.user_id == user_id,
            Workstream.archived_at.is_(None),
            Workstream.status.in_([
                WorkstreamStatus.RUNNING,
                WorkstreamStatus.BLOCKED,
                WorkstreamStatus.WAITING_APPROVAL,
            ]),
        ).order_by(desc(Workstream.last_activity_at)).limit(limit)
    )).scalars().all()
    return {
        "open_workstreams": [
            {
                "id": str(w.id),
                "goal": w.goal,
                "status": w.status.value,
                "next_step_text": w.next_step_text,
                "blocker_text": w.blocker_text,
                "source_type": w.source_type.value,
                "source_ref_id": (
                    str(w.source_ref_id) if w.source_ref_id else None
                ),
            } for w in rows
        ],
    }


def _which_department_for_draft(
    *,
    kind: str,
    draft: ResearchDraft | FormDraft | None,
) -> tuple[str, str]:
    """Return (department_name, reason)."""
    # Mirror PR-4's mapper. Re-imported to keep the parser side
    # independent of the FastAPI routing layer.
    from app.api.v1.workstreams import (
        _DRAFT_KIND_TO_DEPARTMENT_NAME,
        _looks_legal,
    )
    if isinstance(draft, ResearchDraft):
        payload = draft.structured_payload or {}
        if _looks_legal(payload, draft.goal):
            return "Legal & Compliance", "legal_flag"
    return _DRAFT_KIND_TO_DEPARTMENT_NAME.get(kind, "Operations"), "kind_default"


async def run_command(
    db: AsyncSession,
    parsed: ParsedCommand,
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    actor_role: str = "USER",
    registry: Any = None,
    allow_metered: bool = False,
    allow_web_grounding: bool = False,
) -> CommandResult:
    """Execute a parsed VP command.

    Returns a CommandResult the chat surface can render. Audits one
    ``vp_command.<intent>`` row per call.
    """
    audit = AuditService(db)
    intent = parsed.intent

    if intent == "unrecognized":
        return CommandResult(
            intent="unrecognized", success=False,
            summary=(
                "I didn't recognise that as a draft / workstream "
                "command. Try: 'review my drafts', 'enrich draft <id>', "
                "'run council on draft <id>', 'create a work plan from "
                "draft <id>', or 'what should I do next?'."
            ),
        )

    if intent == "review_drafts":
        data = await _list_recent_drafts_summary(
            db, user_id=user_id, tenant_id=tenant_id,
        )
        n = len(data["research_drafts"]) + len(data["form_drafts"])
        await audit.log_decision(
            tenant_id=tenant_id, actor_id=user_id, actor_type=actor_role,
            action_type="vp_command.review_drafts",
            action_params={"count": n},
            result="ALLOWED", risk_level="LOW", governance_tier=1,
        )
        await db.commit()
        return CommandResult(
            intent=intent, success=True,
            summary=f"You have {n} drafts in scope.",
            data=data,
        )

    if intent == "next_steps":
        data = await _next_steps_summary(
            db, user_id=user_id, tenant_id=tenant_id,
        )
        await audit.log_decision(
            tenant_id=tenant_id, actor_id=user_id, actor_type=actor_role,
            action_type="vp_command.next_steps",
            action_params={"count": len(data["open_workstreams"])},
            result="ALLOWED", risk_level="LOW", governance_tier=1,
        )
        await db.commit()
        n = len(data["open_workstreams"])
        if n == 0:
            return CommandResult(
                intent=intent, success=True,
                summary=(
                    "No open workstreams. Your next step is "
                    "operator's choice -- start one with 'create a "
                    "work plan from draft <id>'."
                ),
                data=data,
            )
        return CommandResult(
            intent=intent, success=True,
            summary=f"{n} open workstreams. Top: " + (
                data["open_workstreams"][0]["next_step_text"]
                or data["open_workstreams"][0]["goal"]
            ),
            data=data,
        )

    # Verbs from here on need a draft id to act on.
    if intent in (
        "enrich_draft",
        "qe_review_draft",
        "create_workstream_from_draft",
        "which_department",
    ):
        kind, draft = await _resolve_draft(
            db, user_id=user_id, tenant_id=tenant_id,
            draft_ref=parsed.draft_ref,
        )
        if draft is None:
            recent = await _list_recent_drafts_summary(
                db, user_id=user_id, tenant_id=tenant_id, limit=5,
            )
            await audit.log_decision(
                tenant_id=tenant_id, actor_id=user_id, actor_type=actor_role,
                action_type=f"vp_command.{intent}",
                action_params={
                    "draft_ref_provided": parsed.draft_ref,
                    "outcome": "needs_disambiguation",
                },
                result="ALLOWED", risk_level="LOW", governance_tier=1,
            )
            await db.commit()
            return CommandResult(
                intent=intent, success=False, needs_disambiguation=True,
                summary=(
                    "I need a specific draft id. Pick one and resend "
                    f"the command, e.g. '{intent.replace('_', ' ')} "
                    f"<id>'."
                ),
                data=recent,
            )

        if intent == "which_department":
            dept_name, reason = _which_department_for_draft(
                kind=kind or "", draft=draft,
            )
            await audit.log_decision(
                tenant_id=tenant_id, actor_id=user_id, actor_type=actor_role,
                action_type="vp_command.which_department",
                action_params={
                    "draft_id": str(draft.id),
                    "kind": kind, "department": dept_name,
                    "reason": reason,
                },
                result="ALLOWED", risk_level="LOW", governance_tier=1,
            )
            await db.commit()
            return CommandResult(
                intent=intent, success=True,
                summary=(
                    f"That draft would route to {dept_name} "
                    f"({reason})."
                ),
                data={
                    "draft_id": str(draft.id), "kind": kind,
                    "department": dept_name, "reason": reason,
                },
            )

        if intent == "enrich_draft":
            from app.services.draft_enrichment import (
                EnrichmentRefused,
                enrich_form_draft,
                enrich_research_draft,
            )
            try:
                if isinstance(draft, ResearchDraft):
                    result = await enrich_research_draft(
                        db, draft, allow_metered=allow_metered,
                        registry=registry, actor_id=user_id,
                    )
                else:
                    result = await enrich_form_draft(
                        db, draft, allow_metered=allow_metered,
                        registry=registry, actor_id=user_id,
                    )
            except EnrichmentRefused as exc:
                await db.commit()
                return CommandResult(
                    intent=intent, success=False,
                    summary=f"Enrichment refused: {exc.code}",
                    next_action=exc.next_action,
                    data={"refusal_code": exc.code},
                )
            await audit.log_decision(
                tenant_id=tenant_id, actor_id=user_id, actor_type=actor_role,
                action_type="vp_command.enrich_draft",
                action_params={
                    "draft_id": str(draft.id), "kind": kind,
                    "runtime_id": result.runtime_id,
                    "fields_filled": result.fields_filled,
                },
                result="ALLOWED", risk_level="LOW", governance_tier=1,
            )
            await db.commit()
            return CommandResult(
                intent=intent, success=True,
                summary=(
                    f"Enrichment complete via {result.runtime_id} "
                    f"({result.cost_class}). {result.fields_filled} "
                    f"fields filled, "
                    f"{len(result.needs_review)} flagged for review."
                ),
                data={
                    "draft_id": result.draft_id,
                    "runtime_id": result.runtime_id,
                    "cost_class": result.cost_class,
                    "fields_filled": result.fields_filled,
                    "needs_review": result.needs_review,
                    "llm_failed": result.llm_failed,
                },
            )

        if intent == "qe_review_draft":
            from app.services.draft_qe_review import (
                QECouncilUnavailable,
                run_draft_qe_review,
            )
            try:
                result = await run_draft_qe_review(
                    db, draft,
                    allow_metered=allow_metered,
                    allow_web_grounding=allow_web_grounding,
                    registry=registry, actor_id=user_id,
                )
            except QECouncilUnavailable as exc:
                await db.commit()
                return CommandResult(
                    intent=intent, success=False,
                    summary=f"QE/Council refused: {exc.code}",
                    next_action=exc.next_action,
                    data={"refusal_code": exc.code},
                )
            await audit.log_decision(
                tenant_id=tenant_id, actor_id=user_id, actor_type=actor_role,
                action_type="vp_command.qe_review_draft",
                action_params={
                    "draft_id": str(draft.id), "kind": kind,
                    "mode": result.mode,
                    "distinct_runtime_ids": result.distinct_runtime_ids,
                    "next_action": result.next_action,
                },
                result="ALLOWED", risk_level="LOW", governance_tier=1,
            )
            await db.commit()
            return CommandResult(
                intent=intent, success=True,
                summary=(
                    f"Council ran in mode={result.mode} with "
                    f"{len(result.distinct_runtime_ids)} distinct "
                    f"runtime(s). Next: {result.next_action}."
                ),
                data={
                    "draft_id": result.draft_id,
                    "mode": result.mode,
                    "mode_reason": result.mode_reason,
                    "distinct_runtime_ids": result.distinct_runtime_ids,
                    "findings": result.findings,
                    "objections": result.objections,
                    "missing_evidence": result.missing_evidence,
                    "risk_flags": result.risk_flags,
                    "confidence": result.confidence,
                    "next_action": result.next_action,
                    "warnings": result.warnings,
                },
            )

        if intent == "create_workstream_from_draft":
            # Inline the existing endpoint's logic by calling the
            # service-layer pieces directly. Department routing +
            # next-step seeding lives in the API module; we duplicate
            # the call here so chat can drive without HTTP.
            from app.api.v1.workstreams import (
                FromDraftRequest, post_from_draft,
            )

            class _ChatUser:
                def __init__(self, *, _id, _tid):
                    self.id = _id
                    self.tenant_id = _tid

            try:
                resp = await post_from_draft(
                    body=FromDraftRequest(
                        draft_kind=kind,
                        draft_ref=draft.id,
                    ),
                    user=_ChatUser(_id=user_id, _tid=tenant_id),  # type: ignore[arg-type]
                    db=db,
                )
            except Exception as exc:
                await db.commit()
                return CommandResult(
                    intent=intent, success=False,
                    summary=(
                        f"Could not create workstream: {type(exc).__name__}"
                    ),
                )
            ws = resp["data"]
            await audit.log_decision(
                tenant_id=tenant_id, actor_id=user_id, actor_type=actor_role,
                action_type="vp_command.create_workstream_from_draft",
                action_params={
                    "draft_id": str(draft.id), "kind": kind,
                    "workstream_id": ws["id"],
                },
                result="ALLOWED", risk_level="LOW", governance_tier=1,
            )
            # post_from_draft already commit()'d; nothing extra here.
            return CommandResult(
                intent=intent, success=True,
                summary=(
                    f"Workstream {ws['id'][:8]} created -- "
                    f"next: {ws.get('next_step_text') or ws['goal'][:80]}"
                ),
                data=ws,
            )

    return CommandResult(
        intent="unrecognized", success=False,
        summary="(internal) unhandled intent",
    )
