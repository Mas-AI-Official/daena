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

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_role
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.research import ResearchDraft
from app.services.research_flow import (
    ALLOWED_KINDS,
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
    kind: Literal["career", "content"],
    body: ResearchRequest,
    user: CurrentUser,
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
