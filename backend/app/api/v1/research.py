"""Research API -- supervised read-only career + content workflows.

PR-CAREEROPS-READONLY-RESEARCH-FLOW (Sprint-10 PR-3, 2026-05-05).
PR-CONTENTOPS-READONLY-RESEARCH-FLOW (Sprint-10 PR-4, 2026-05-05).

Endpoints:

  POST /api/v1/research/career    -> Career research draft.
  POST /api/v1/research/content   -> ContentOps research draft.
  GET  /api/v1/research/drafts    -> List the operator's drafts.
  GET  /api/v1/research/drafts/{id} -> Read one draft.

Hard rules enforced here:
  * Auth required (FOUNDER for create; any role for list/read of
    own drafts).
  * Drafts are LOCAL ONLY. No endpoint sends, posts, emails,
    or otherwise dispatches a draft externally. ``status`` field is
    DRAFT or ARCHIVED -- never SENT / POSTED / SUBMITTED.
  * Source URL must pass ``url_safety`` (re-checked inside the
    underlying scrape service). The brief explicitly forbids
    LinkedIn / Indeed automation; nothing here drives a browser at
    those sites.
"""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_role
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.research import ResearchDraft
from app.services.draft_enrichment import (
    EnrichmentRefused,
    enrich_research_draft,
)
from app.services.draft_qe_review import (
    QECouncilUnavailable,
    run_draft_qe_review,
)
from app.services.research_flow import (
    ALLOWED_KINDS,
    ALLOWED_OPPORTUNITY_TYPES,
    OpportunityType,
    ResearchFlowError,
    create_research_draft,
)


logger = get_logger(__name__)
router = APIRouter()


# ──────────────────────────────────────────────────────────────────
# Request / response shapes
# ──────────────────────────────────────────────────────────────────


class ResearchRequest(BaseModel):
    """Either ``url`` or ``url_or_topic`` may be supplied; we accept
    only http/https URLs (rejected by the underlying SSRF guard if
    they target loopback / private / internal-DNS)."""
    url: str = Field(..., min_length=1, max_length=2048)
    goal: str = Field(..., min_length=1, max_length=2000)
    max_chars: int = Field(default=8000, ge=200, le=32000)


class ResearchDraftOut(BaseModel):
    id: str
    kind: str
    source_url: str
    source_host: str
    goal: str
    summary: str
    raw_extract: str
    status: str
    audit_event_id: str | None
    created_at: str
    # Sprint-11 PR-2: kind-specific structured shape (opportunity for
    # kind=career, brief for kind=content). May be None on rows
    # created before the column existed.
    structured_payload: dict | None = None

    @classmethod
    def from_model(cls, row: ResearchDraft) -> "ResearchDraftOut":
        return cls(
            id=str(row.id),
            kind=row.kind,
            source_url=row.source_url,
            source_host=row.source_host,
            goal=row.goal,
            summary=row.summary,
            raw_extract=row.raw_extract,
            status=row.status,
            audit_event_id=row.audit_event_id,
            created_at=row.created_at.isoformat() if row.created_at else "",
            structured_payload=row.structured_payload,
        )


class CreateDraftResponse(BaseModel):
    success: bool
    draft: ResearchDraftOut


class ListDraftsResponse(BaseModel):
    success: bool
    drafts: list[ResearchDraftOut]


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────


async def _create(
    db: AsyncSession, *,
    kind: Literal["career", "content", "business_opportunity"],
    body: ResearchRequest,
    user: CurrentUser,
    opportunity_type: OpportunityType | None = None,
) -> ResearchDraft:
    try:
        draft = await create_research_draft(
            db,
            kind=kind,
            url=body.url,
            goal=body.goal,
            user_id=user.id,
            tenant_id=user.tenant_id,
            max_chars=body.max_chars,
            opportunity_type=opportunity_type,
        )
    except ResearchFlowError as exc:
        msg = str(exc)
        # Surface a stable error code (prefix before the colon).
        code = msg.split(":", 1)[0] if ":" in msg else msg
        raise HTTPException(
            status_code=400,
            detail={"code": code, "message": msg},
        )
    await db.commit()
    return draft


class OpportunityResearchRequest(ResearchRequest):
    """Sprint-13 PR-2 -- business opportunity research request.

    Inherits url + goal + max_chars from ResearchRequest. Adds the
    closed-set opportunity_type so the workstream generator (PR-3)
    can pick a default department deterministically.
    """
    opportunity_type: OpportunityType = Field(
        ...,
        description=(
            "One of: grant, accelerator, hackathon, freelance, customer, "
            "partnership, security_bounty, rfp, content, startup_program."
        ),
    )


# ──────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────


@router.post("/career", response_model=CreateDraftResponse)
async def post_research_career(
    body: ResearchRequest,
    user: CurrentUser = Depends(require_role("FOUNDER")),
    db: AsyncSession = Depends(get_db),
) -> CreateDraftResponse:
    """Run the CareerOPS read-only research flow.

    Input: a job / company URL + an extraction goal (e.g. "extract
    the role title, the team, the required skills, the salary if
    listed, and a 3-sentence company summary").

    Output: a LOCAL ``ResearchDraft`` row with status=DRAFT. The
    operator decides what to do next -- this endpoint never submits
    an application, never sends an email, never drives a LinkedIn /
    Indeed browser session.
    """
    draft = await _create(db, kind="career", body=body, user=user)
    return CreateDraftResponse(success=True, draft=ResearchDraftOut.from_model(draft))


@router.post("/content", response_model=CreateDraftResponse)
async def post_research_content(
    body: ResearchRequest,
    user: CurrentUser = Depends(require_role("FOUNDER")),
    db: AsyncSession = Depends(get_db),
) -> CreateDraftResponse:
    """Run the ContentOps read-only research flow.

    Input: a source URL + a goal (e.g. "summarize the article's
    central thesis, list the three strongest claims, and extract
    a 12-tweet thread outline").

    Output: a LOCAL ``ResearchDraft`` row with status=DRAFT. NEVER
    posts the draft. NEVER logs into a social account. NEVER drives
    a browser at any social platform.
    """
    draft = await _create(db, kind="content", body=body, user=user)
    return CreateDraftResponse(success=True, draft=ResearchDraftOut.from_model(draft))


@router.post("/opportunity", response_model=CreateDraftResponse)
async def post_research_opportunity(
    body: OpportunityResearchRequest,
    user: CurrentUser = Depends(require_role("FOUNDER")),
    db: AsyncSession = Depends(get_db),
) -> CreateDraftResponse:
    """Sprint-13 PR-2 -- business opportunity research flow.

    Input: a source URL (grant page / hackathon page / customer site /
    bounty program scope / etc.) + a goal + a closed-set
    opportunity_type.

    Output: a LOCAL ``ResearchDraft`` row with kind=business_opportunity
    and status=DRAFT. NEVER applies, NEVER submits, NEVER scans.
    The workstream generator (PR-3) reads this row to draft an
    eligibility check + a local proposal -- still no external action.
    """
    draft = await _create(
        db,
        kind="business_opportunity",
        body=body,
        user=user,
        opportunity_type=body.opportunity_type,
    )
    return CreateDraftResponse(success=True, draft=ResearchDraftOut.from_model(draft))


@router.get("/drafts", response_model=ListDraftsResponse)
async def list_research_drafts(
    kind: str | None = Query(default=None, description="Filter by kind (career|content)"),
    status: str | None = Query(default=None, description="Filter by status (DRAFT|ARCHIVED)"),
    limit: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ListDraftsResponse:
    """List the calling user's research drafts in this tenant.

    Drafts are LOCAL artifacts; this endpoint never reaches outside
    the local DB to enrich a row.
    """
    if kind is not None and kind not in ALLOWED_KINDS:
        raise HTTPException(status_code=400, detail=f"unknown_kind: {kind}")
    stmt = (
        select(ResearchDraft)
        .where(
            ResearchDraft.tenant_id == user.tenant_id,
            ResearchDraft.user_id == user.id,
        )
        .order_by(desc(ResearchDraft.created_at))
        .limit(limit)
    )
    if kind is not None:
        stmt = stmt.where(ResearchDraft.kind == kind)
    if status is not None:
        stmt = stmt.where(ResearchDraft.status == status)
    rows = (await db.execute(stmt)).scalars().all()
    return ListDraftsResponse(
        success=True,
        drafts=[ResearchDraftOut.from_model(r) for r in rows],
    )


@router.get("/drafts/{draft_id}", response_model=ResearchDraftOut)
async def get_research_draft(
    draft_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResearchDraftOut:
    """Read one draft. Tenant + user-scoped -- a draft is owned by
    its creator and never visible cross-tenant."""
    row = (await db.execute(
        select(ResearchDraft).where(
            ResearchDraft.id == draft_id,
            ResearchDraft.tenant_id == user.tenant_id,
            ResearchDraft.user_id == user.id,
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="draft_not_found")
    return ResearchDraftOut.from_model(row)


# ──────────────────────────────────────────────────────────────────
# Sprint-12 PR-1: routed-brain enrichment
# ──────────────────────────────────────────────────────────────────


class EnrichRequest(BaseModel):
    """Optional flags for an enrichment pass."""
    allow_metered: bool = Field(
        default=False,
        description=(
            "When True, allow the routed brain to be a metered API "
            "provider. Default False -- local-first policy."
        ),
    )


class EnrichResponse(BaseModel):
    success: bool
    draft_id: str
    runtime_id: str
    cost_class: str
    fields_filled: int
    needs_review: list[str]
    llm_failed: bool
    metadata: dict


@router.post("/drafts/{draft_id}/enrich", response_model=EnrichResponse)
async def post_enrich_research_draft(
    draft_id: uuid.UUID,
    request: Request,
    body: EnrichRequest | None = None,
    user: CurrentUser = Depends(require_role("FOUNDER")),
    db: AsyncSession = Depends(get_db),
) -> EnrichResponse:
    """Run LLM enrichment on one ResearchDraft.

    Reads ``/system/runtime-readiness`` first -- refuses with
    ``no_ready_main_brain`` if no main brain is currently ready,
    surfacing the readiness ``next_action`` so the operator knows
    what to start. NEVER hardcodes a provider. NEVER sends, posts,
    or otherwise externally acts on the draft.
    """
    row = (await db.execute(
        select(ResearchDraft).where(
            ResearchDraft.id == draft_id,
            ResearchDraft.tenant_id == user.tenant_id,
            ResearchDraft.user_id == user.id,
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="draft_not_found")

    body = body or EnrichRequest()
    registry = getattr(request.app.state, "model_registry", None)

    try:
        result = await enrich_research_draft(
            db, row,
            allow_metered=body.allow_metered,
            registry=registry,
            actor_id=user.id,
        )
    except EnrichmentRefused as exc:
        await db.commit()  # persist the refusal audit row
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "next_action": exc.next_action},
        )
    await db.commit()
    return EnrichResponse(
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
# Sprint-12 PR-3: QE/Council review for work artifacts
# ──────────────────────────────────────────────────────────────────


class QEReviewRequest(BaseModel):
    allow_metered: bool = Field(
        default=False,
        description="Allow metered_api runtimes to fill review slots.",
    )
    allow_web_grounding: bool = Field(
        default=False,
        description=(
            "Allow Perplexity (web_grounder slot) to verify claims. "
            "Metered; default False."
        ),
    )


class ReviewerOutputDTO(BaseModel):
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


class QEReviewResponse(BaseModel):
    success: bool
    draft_id: str
    draft_kind: str
    mode: str  # full | degraded | unavailable
    mode_reason: str
    distinct_runtime_ids: list[str]
    proposer_outputs: list[ReviewerOutputDTO]
    synthesizer_runtime_id: str | None
    findings: list[str]
    objections: list[str]
    missing_evidence: list[str]
    risk_flags: list[str]
    confidence: float
    next_action: str
    warnings: list[str]


@router.post("/drafts/{draft_id}/qe-review", response_model=QEReviewResponse)
async def post_qe_review_research_draft(
    draft_id: uuid.UUID,
    request: Request,
    body: QEReviewRequest | None = None,
    user: CurrentUser = Depends(require_role("FOUNDER")),
    db: AsyncSession = Depends(get_db),
) -> QEReviewResponse:
    """Run QE/Council review on a ResearchDraft.

    Reads ``/system/qe-readiness`` first. Refuses with
    ``qe_council_unavailable`` when no reviewers can fire under the
    operator's allow flags. Mode is reported HONESTLY -- a single-
    runtime review NEVER claims ``full`` regardless of what the
    snapshot said.
    """
    row = (await db.execute(
        select(ResearchDraft).where(
            ResearchDraft.id == draft_id,
            ResearchDraft.tenant_id == user.tenant_id,
            ResearchDraft.user_id == user.id,
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="draft_not_found")

    body = body or QEReviewRequest()
    registry = getattr(request.app.state, "model_registry", None)

    try:
        result = await run_draft_qe_review(
            db, row,
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
    return QEReviewResponse(
        success=True,
        draft_id=result.draft_id,
        draft_kind=result.draft_kind,
        mode=result.mode,
        mode_reason=result.mode_reason,
        distinct_runtime_ids=result.distinct_runtime_ids,
        proposer_outputs=[
            ReviewerOutputDTO(
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
