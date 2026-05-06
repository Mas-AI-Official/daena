"""FormDrafts API -- Sprint-11 PR-3.

Endpoints:

    POST   /form-drafts/from-questions    Create from a list of pasted questions.
    POST   /form-drafts/from-html         Create from pasted form HTML.
    POST   /form-drafts/from-url          Create from a URL (scrape -> parse).
    GET    /form-drafts                   List the operator's drafts.
    GET    /form-drafts/{id}              Read one (with fields).
    PATCH  /form-drafts/{id}/fields/{fid} Edit one field's value.
    POST   /form-drafts/{id}/archive      Soft-delete a draft.
    DELETE /form-drafts/{id}              Hard-delete (only if ARCHIVED).

Hard rules:

    * No /submit, /send, /apply, /post, /publish, /dispatch endpoint.
      Tests assert these routes do not exist on the router.
    * Auth required on every endpoint (FOUNDER for create paths,
      any role for the operator's own drafts).
    * Per-field permissions ride on the field_type: blocked_payment
      and blocked_sensitive types come back without a suggested_value
      and with a notes string telling the operator they must fill
      manually.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_role
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.form_draft import FormDraft, FormDraftField
from app.models.research import ResearchDraft
from app.services.draft_enrichment import (
    EnrichmentRefused,
    enrich_form_draft,
)
from app.services.draft_qe_review import (
    QECouncilUnavailable,
    run_draft_qe_review,
)
from app.services.form_draft_service import (
    archive_draft,
    create_form_draft_from_html,
    create_form_draft_from_questions,
    parse_form_html,
    update_field_value,
)
from app.services.scrape import (
    ExtractResult,
    ScrapeError,
    extract_from_url,
)


logger = get_logger(__name__)
router = APIRouter()


# ── Pydantic shapes ──────────────────────────────────────────────────


class FormDraftFieldOut(BaseModel):
    id: str
    order: int
    label: str
    field_type: str
    value: str | None
    suggested_value: str | None
    confidence: float
    needs_review: bool
    options: list[str] | None
    notes: str | None

    @classmethod
    def from_model(cls, row: FormDraftField) -> "FormDraftFieldOut":
        return cls(
            id=str(row.id),
            order=row.order,
            label=row.label,
            field_type=row.field_type,
            value=row.value,
            suggested_value=row.suggested_value,
            confidence=row.confidence,
            needs_review=row.needs_review,
            options=row.options,
            notes=row.notes,
        )


class FormDraftOut(BaseModel):
    id: str
    title: str
    source_kind: str
    source_url: str | None
    source_host: str | None
    goal: str
    status: str
    audit_event_id: str | None
    research_draft_ref: str | None
    created_at: str
    fields: list[FormDraftFieldOut] = []

    @classmethod
    def from_model(
        cls, row: FormDraft, *, include_fields: bool = True,
    ) -> "FormDraftOut":
        return cls(
            id=str(row.id),
            title=row.title,
            source_kind=row.source_kind,
            source_url=row.source_url,
            source_host=row.source_host,
            goal=row.goal or "",
            status=row.status,
            audit_event_id=row.audit_event_id,
            research_draft_ref=row.research_draft_ref,
            created_at=row.created_at.isoformat() if row.created_at else "",
            fields=(
                [FormDraftFieldOut.from_model(f) for f in row.fields]
                if include_fields else []
            ),
        )


class FromQuestionsRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)
    questions: list[str] = Field(..., min_length=1, max_length=200)
    goal: str = Field(default="", max_length=4000)
    research_draft_ref: str | None = Field(default=None, max_length=64)


class FromHtmlRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)
    html: str = Field(..., min_length=1, max_length=200_000)
    source_url: str | None = Field(default=None, max_length=2048)
    goal: str = Field(default="", max_length=4000)
    research_draft_ref: str | None = Field(default=None, max_length=64)


class FromUrlRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)
    title: str = Field(default="Form from URL", max_length=256)
    goal: str = Field(default="Extract form questions", max_length=4000)
    max_chars: int = Field(default=8000, ge=200, le=32000)
    research_draft_ref: str | None = Field(default=None, max_length=64)


class FieldPatchRequest(BaseModel):
    value: str | None = Field(default=None, max_length=10_000)


class CreateResponse(BaseModel):
    success: bool
    draft: FormDraftOut


class ListResponse(BaseModel):
    success: bool
    drafts: list[FormDraftOut]


# ── Helpers ──────────────────────────────────────────────────────────


async def _load_draft(
    db: AsyncSession, draft_id: uuid.UUID, user: CurrentUser,
) -> FormDraft:
    from sqlalchemy.orm import selectinload
    row = (await db.execute(
        select(FormDraft)
        .where(FormDraft.id == draft_id)
        .where(FormDraft.tenant_id == user.tenant_id)
        .where(FormDraft.user_id == user.id)
        .options(selectinload(FormDraft.fields))
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="form_draft_not_found")
    return row


# ── Endpoints ────────────────────────────────────────────────────────


@router.post("/from-questions", response_model=CreateResponse)
async def post_from_questions(
    body: FromQuestionsRequest,
    user: CurrentUser = Depends(require_role("FOUNDER")),
    db: AsyncSession = Depends(get_db),
) -> CreateResponse:
    try:
        draft = await create_form_draft_from_questions(
            db,
            title=body.title,
            questions=body.questions,
            user_id=user.id,
            tenant_id=user.tenant_id,
            goal=body.goal,
            research_draft_ref=body.research_draft_ref,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    await db.refresh(draft, attribute_names=["fields"])
    return CreateResponse(success=True, draft=FormDraftOut.from_model(draft))


@router.post("/from-html", response_model=CreateResponse)
async def post_from_html(
    body: FromHtmlRequest,
    user: CurrentUser = Depends(require_role("FOUNDER")),
    db: AsyncSession = Depends(get_db),
) -> CreateResponse:
    try:
        draft = await create_form_draft_from_html(
            db,
            title=body.title,
            html=body.html,
            user_id=user.id,
            tenant_id=user.tenant_id,
            source_url=body.source_url,
            goal=body.goal,
            research_draft_ref=body.research_draft_ref,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    await db.refresh(draft, attribute_names=["fields"])
    return CreateResponse(success=True, draft=FormDraftOut.from_model(draft))


@router.post("/from-url", response_model=CreateResponse)
async def post_from_url(
    body: FromUrlRequest,
    user: CurrentUser = Depends(require_role("FOUNDER")),
    db: AsyncSession = Depends(get_db),
) -> CreateResponse:
    try:
        outcome: ExtractResult = await extract_from_url(
            body.url, body.goal, max_chars=body.max_chars,
        )
    except ScrapeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not outcome.success:
        raise HTTPException(
            status_code=400,
            detail=f"scrape_failed:{outcome.error or 'unknown'}",
        )

    # The scrape worker returns goal-tailored extracted text. If the
    # goal asked for raw HTML we will see HTML; otherwise we run the
    # text through a question-extraction pass (lines ending in '?')
    # before falling back to the html parser.
    text = outcome.result or ""
    questions = [
        line.strip().rstrip("?") + "?"
        for line in text.splitlines()
        if line.strip().endswith("?") and 5 <= len(line.strip()) <= 500
    ]
    if questions:
        try:
            draft = await create_form_draft_from_questions(
                db,
                title=body.title,
                questions=questions,
                user_id=user.id,
                tenant_id=user.tenant_id,
                goal=body.goal,
                research_draft_ref=body.research_draft_ref,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    else:
        # Treat as html / mixed text. parse_form_html will return [] if
        # there are no inputs; we surface that as a 422 so the operator
        # knows to retry with from-questions or from-html directly.
        parsed = parse_form_html(text)
        if not parsed:
            raise HTTPException(
                status_code=422,
                detail="no_questions_found",
            )
        try:
            draft = await create_form_draft_from_html(
                db,
                title=body.title,
                html=text,
                user_id=user.id,
                tenant_id=user.tenant_id,
                source_url=body.url,
                goal=body.goal,
                research_draft_ref=body.research_draft_ref,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    # Stamp the source_url on the draft so the operator can re-open it.
    draft.source_url = body.url
    await db.commit()
    await db.refresh(draft, attribute_names=["fields"])
    return CreateResponse(success=True, draft=FormDraftOut.from_model(draft))


@router.get("", response_model=ListResponse)
async def list_form_drafts(
    status: str | None = Query(default=None, description="DRAFT|ARCHIVED"),
    limit: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ListResponse:
    stmt = (
        select(FormDraft)
        .where(FormDraft.tenant_id == user.tenant_id)
        .where(FormDraft.user_id == user.id)
        .order_by(desc(FormDraft.created_at))
        .limit(limit)
    )
    if status is not None:
        stmt = stmt.where(FormDraft.status == status)
    rows = (await db.execute(stmt)).scalars().all()
    return ListResponse(
        success=True,
        drafts=[FormDraftOut.from_model(r, include_fields=False) for r in rows],
    )


@router.get("/{draft_id}", response_model=FormDraftOut)
async def get_form_draft(
    draft_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FormDraftOut:
    draft = await _load_draft(db, draft_id, user)
    return FormDraftOut.from_model(draft)


@router.patch("/{draft_id}/fields/{field_id}", response_model=FormDraftOut)
async def patch_field(
    draft_id: uuid.UUID,
    field_id: uuid.UUID,
    body: FieldPatchRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FormDraftOut:
    draft = await _load_draft(db, draft_id, user)
    field = next((f for f in draft.fields if f.id == field_id), None)
    if field is None:
        raise HTTPException(status_code=404, detail="field_not_found")
    await update_field_value(db, field=field, new_value=body.value)
    await db.commit()
    await db.refresh(draft, attribute_names=["fields"])
    return FormDraftOut.from_model(draft)


@router.post("/{draft_id}/archive", response_model=FormDraftOut)
async def post_archive(
    draft_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FormDraftOut:
    draft = await _load_draft(db, draft_id, user)
    await archive_draft(db, draft=draft)
    await db.commit()
    await db.refresh(draft, attribute_names=["fields"])
    return FormDraftOut.from_model(draft)


# ──────────────────────────────────────────────────────────────────
# Sprint-12 PR-2: routed-brain enrichment of form fields
# ──────────────────────────────────────────────────────────────────


class FormEnrichRequest(BaseModel):
    """Optional flags + research-context pointer for enrichment."""
    allow_metered: bool = Field(
        default=False,
        description="When True, allow a metered API provider to fill the brain slot.",
    )
    research_draft_id: uuid.UUID | None = Field(
        default=None,
        description=(
            "Optional ResearchDraft to use as grounding context. The "
            "draft must belong to the calling user. Only a whitelist "
            "of fields is passed to the LLM (company/role/fit_rationale/"
            "missing_skills/outreach_draft_local/next_tasks)."
        ),
    )


class FormEnrichResponse(BaseModel):
    success: bool
    draft_id: str
    runtime_id: str
    cost_class: str
    fields_filled: int
    needs_review: list[str]
    llm_failed: bool
    metadata: dict


@router.post("/{draft_id}/enrich", response_model=FormEnrichResponse)
async def post_enrich_form_draft(
    draft_id: uuid.UUID,
    request: Request,
    body: FormEnrichRequest | None = None,
    user: CurrentUser = Depends(require_role("FOUNDER")),
    db: AsyncSession = Depends(get_db),
) -> FormEnrichResponse:
    """Run LLM enrichment on a FormDraft's eligible fields.

    Reads ``/system/runtime-readiness`` first. Refuses honestly on
    no_ready_main_brain. Blocked field types (payment / sensitive)
    are NEVER given a suggested_value regardless of LLM output.
    NEVER submits the form.
    """
    draft = await _load_draft(db, draft_id, user)
    body = body or FormEnrichRequest()
    registry = getattr(request.app.state, "model_registry", None)

    research_ctx: dict | None = None
    if body.research_draft_id is not None:
        rd = (await db.execute(
            select(ResearchDraft).where(
                ResearchDraft.id == body.research_draft_id,
                ResearchDraft.tenant_id == user.tenant_id,
                ResearchDraft.user_id == user.id,
            )
        )).scalar_one_or_none()
        if rd is None:
            raise HTTPException(
                status_code=404,
                detail="research_draft_not_found_for_user",
            )
        research_ctx = rd.structured_payload or None

    try:
        result = await enrich_form_draft(
            db, draft,
            research_context=research_ctx,
            allow_metered=body.allow_metered,
            registry=registry,
            actor_id=user.id,
        )
    except EnrichmentRefused as exc:
        await db.commit()
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "next_action": exc.next_action},
        )

    await db.commit()
    return FormEnrichResponse(
        success=True,
        draft_id=result.draft_id,
        runtime_id=result.runtime_id,
        cost_class=result.cost_class,
        fields_filled=result.fields_filled,
        needs_review=result.needs_review,
        llm_failed=result.llm_failed,
        metadata=result.metadata,
    )


# ──────────────────────────────────────────────────────────────────
# Sprint-12 PR-3: QE/Council review for FormDraft
# ──────────────────────────────────────────────────────────────────


class FormQEReviewRequest(BaseModel):
    allow_metered: bool = Field(default=False)
    allow_web_grounding: bool = Field(default=False)


class FormReviewerOutputDTO(BaseModel):
    slot: str
    runtime_id: str
    cost_class: str
    findings: list[str]
    objections: list[str]
    missing_evidence: list[str]
    risk_flags: list[str]
    confidence: float
    notes: str | None
    failed: bool


class FormQEReviewResponse(BaseModel):
    success: bool
    draft_id: str
    draft_kind: str
    mode: str
    mode_reason: str
    distinct_runtime_ids: list[str]
    proposer_outputs: list[FormReviewerOutputDTO]
    synthesizer_runtime_id: str | None
    findings: list[str]
    objections: list[str]
    missing_evidence: list[str]
    risk_flags: list[str]
    confidence: float
    next_action: str
    warnings: list[str]


@router.post("/{draft_id}/qe-review", response_model=FormQEReviewResponse)
async def post_qe_review_form_draft(
    draft_id: uuid.UUID,
    request: Request,
    body: FormQEReviewRequest | None = None,
    user: CurrentUser = Depends(require_role("FOUNDER")),
    db: AsyncSession = Depends(get_db),
) -> FormQEReviewResponse:
    """Run QE/Council review on a FormDraft.

    Mode is reported HONESTLY (full / degraded / unavailable). NEVER
    claims a 'full council' when only one runtime contributed.
    """
    draft = await _load_draft(db, draft_id, user)
    body = body or FormQEReviewRequest()
    registry = getattr(request.app.state, "model_registry", None)

    try:
        result = await run_draft_qe_review(
            db, draft,
            allow_metered=body.allow_metered,
            allow_web_grounding=body.allow_web_grounding,
            registry=registry,
            actor_id=user.id,
        )
    except QECouncilUnavailable as exc:
        await db.commit()
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "next_action": exc.next_action},
        )
    await db.commit()
    return FormQEReviewResponse(
        success=True,
        draft_id=result.draft_id,
        draft_kind=result.draft_kind,
        mode=result.mode,
        mode_reason=result.mode_reason,
        distinct_runtime_ids=result.distinct_runtime_ids,
        proposer_outputs=[
            FormReviewerOutputDTO(
                slot=p.slot, runtime_id=p.runtime_id,
                cost_class=p.cost_class, findings=p.findings,
                objections=p.objections,
                missing_evidence=p.missing_evidence,
                risk_flags=p.risk_flags, confidence=p.confidence,
                notes=p.notes, failed=p.failed,
            )
            for p in result.proposer_outputs
        ],
        synthesizer_runtime_id=result.synthesizer_runtime_id,
        findings=result.findings,
        objections=result.objections,
        missing_evidence=result.missing_evidence,
        risk_flags=result.risk_flags,
        confidence=result.confidence,
        next_action=result.next_action,
        warnings=result.warnings,
    )


@router.delete("/{draft_id}")
async def delete_draft(
    draft_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    draft = await _load_draft(db, draft_id, user)
    if draft.status != "ARCHIVED":
        raise HTTPException(
            status_code=409,
            detail="archive_first: only ARCHIVED drafts can be hard-deleted",
        )
    await db.delete(draft)
    await db.commit()
    return {"success": True, "id": str(draft_id)}
