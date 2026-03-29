"""Pipeline API -- project lifecycle management.

Manages AI company projects through 8 stages:
  DISCOVERY -> QUALIFICATION -> PROPOSAL -> CONTRACT ->
  EXECUTION -> DELIVERY -> BILLING -> CLOSED

Human gates at PROPOSAL, CONTRACT, DELIVERY require founder_approved=true.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_role
from app.core.database import get_db
from app.services.pipeline_service import PipelineService

router = APIRouter()


def get_pipeline_service(db: AsyncSession = Depends(get_db)) -> PipelineService:
    return PipelineService(db)


# ── Schemas ──

class CreateProjectRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    client_name: str | None = None
    client_email: str | None = None
    source: str | None = None
    budget_usd: float | None = None
    timeline_days: int | None = None
    tags: list[str] | None = None
    requirements: dict | None = None


class AdvanceStageRequest(BaseModel):
    founder_approved: bool = False
    notes: str | None = None


class UpdateScoringRequest(BaseModel):
    ai_doability_score: int | None = Field(None, ge=1, le=10)
    competition_level: int | None = Field(None, ge=1, le=10)
    budget_usd: float | None = None
    timeline_days: int | None = None


class UpdateFinancialsRequest(BaseModel):
    quoted_amount_usd: float | None = None
    actual_cost_usd: float | None = None
    invoiced_amount_usd: float | None = None
    paid_amount_usd: float | None = None
    payment_status: str | None = None


class SetDocumentRequest(BaseModel):
    doc_type: str = Field(..., pattern="^(proposal|contract|deliverables|invoice)$")
    path: str


# ── Endpoints ──

@router.get("/summary")
async def pipeline_summary(
    user: CurrentUser = Depends(get_current_user),
    service: PipelineService = Depends(get_pipeline_service),
):
    """Get project count per pipeline stage (for Kanban view)."""
    result = await service.get_pipeline_summary(user.tenant_id)
    return {"success": True, "data": result}


@router.get("/projects")
async def list_projects(
    stage: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    service: PipelineService = Depends(get_pipeline_service),
):
    """List pipeline projects with optional stage filter."""
    result = await service.list_projects(
        user.tenant_id, stage=stage, page=page, page_size=page_size,
    )
    return {"success": True, **result}


@router.post("/projects", status_code=201)
async def create_project(
    body: CreateProjectRequest,
    user: CurrentUser = Depends(get_current_user),
    service: PipelineService = Depends(get_pipeline_service),
):
    """Create a new project in DISCOVERY stage."""
    result = await service.create_project(
        tenant_id=user.tenant_id,
        title=body.title,
        description=body.description,
        client_name=body.client_name,
        client_email=body.client_email,
        source=body.source,
        budget_usd=body.budget_usd,
        timeline_days=body.timeline_days,
        tags=body.tags,
        requirements=body.requirements,
    )
    return {"success": True, "data": result}


@router.get("/projects/{project_id}")
async def get_project(
    project_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    service: PipelineService = Depends(get_pipeline_service),
):
    """Get a single project."""
    result = await service.get_project(project_id, user.tenant_id)
    if not result:
        return {"success": False, "error": {"code": "NOT_FOUND", "message": "Project not found"}}
    return {"success": True, "data": result}


@router.post("/projects/{project_id}/advance")
async def advance_project(
    project_id: UUID,
    body: AdvanceStageRequest,
    user: CurrentUser = Depends(require_role("MANAGER")),
    service: PipelineService = Depends(get_pipeline_service),
):
    """Advance a project to the next pipeline stage.

    Human gates (PROPOSAL, CONTRACT, DELIVERY) require founder_approved=true.
    """
    try:
        result = await service.advance_stage(
            project_id, user.tenant_id,
            founder_approved=body.founder_approved,
            notes=body.notes,
        )
        return {"success": True, "data": result}
    except ValueError as e:
        return {"success": False, "error": {"code": "INVALID_TRANSITION", "message": str(e)}}


@router.put("/projects/{project_id}/scoring")
async def update_scoring(
    project_id: UUID,
    body: UpdateScoringRequest,
    user: CurrentUser = Depends(get_current_user),
    service: PipelineService = Depends(get_pipeline_service),
):
    """Update project scoring (Research/Sales)."""
    try:
        result = await service.update_scoring(
            project_id, user.tenant_id,
            ai_doability_score=body.ai_doability_score,
            competition_level=body.competition_level,
            budget_usd=body.budget_usd,
            timeline_days=body.timeline_days,
        )
        return {"success": True, "data": result}
    except ValueError as e:
        return {"success": False, "error": {"code": "NOT_FOUND", "message": str(e)}}


@router.put("/projects/{project_id}/financials")
async def update_financials(
    project_id: UUID,
    body: UpdateFinancialsRequest,
    user: CurrentUser = Depends(require_role("MANAGER")),
    service: PipelineService = Depends(get_pipeline_service),
):
    """Update project financials (Finance department)."""
    try:
        result = await service.update_financials(
            project_id, user.tenant_id,
            quoted_amount_usd=body.quoted_amount_usd,
            actual_cost_usd=body.actual_cost_usd,
            invoiced_amount_usd=body.invoiced_amount_usd,
            paid_amount_usd=body.paid_amount_usd,
            payment_status=body.payment_status,
        )
        return {"success": True, "data": result}
    except ValueError as e:
        return {"success": False, "error": {"code": "NOT_FOUND", "message": str(e)}}


@router.put("/projects/{project_id}/document")
async def set_document(
    project_id: UUID,
    body: SetDocumentRequest,
    user: CurrentUser = Depends(get_current_user),
    service: PipelineService = Depends(get_pipeline_service),
):
    """Attach a document path to the project."""
    try:
        result = await service.set_document_path(
            project_id, user.tenant_id,
            doc_type=body.doc_type, path=body.path,
        )
        return {"success": True, "data": result}
    except ValueError as e:
        return {"success": False, "error": {"code": "INVALID", "message": str(e)}}


@router.get("/department/{department}")
async def department_queue(
    department: str,
    user: CurrentUser = Depends(get_current_user),
    service: PipelineService = Depends(get_pipeline_service),
):
    """Get all projects currently owned by a specific department."""
    projects = await service.get_department_queue(user.tenant_id, department)
    return {"success": True, "data": projects}


@router.get("/opportunities")
async def top_opportunities(
    limit: int = Query(3, ge=1, le=20),
    user: CurrentUser = Depends(get_current_user),
    service: PipelineService = Depends(get_pipeline_service),
):
    """Get top-scored DISCOVERY projects for founder review."""
    projects = await service.get_top_opportunities(user.tenant_id, limit=limit)
    return {"success": True, "data": projects}
