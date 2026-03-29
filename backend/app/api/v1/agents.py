"""Agent & Department endpoints: CRUD + seed.

Thin router layer — all business logic lives in AgentService.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_role
from app.core.database import get_db
from app.schemas.agents import CreateAgentRequest, CreateDepartmentRequest
from app.services.agents import AgentService

router = APIRouter()


# ── Dependency factory ──


async def get_agent_service(
    db: AsyncSession = Depends(get_db),
) -> AgentService:
    """Create AgentService per request."""
    return AgentService(db)


# ── Departments ──


@router.get("/departments")
async def list_departments(
    response: Response,
    include_inactive: bool = Query(False),
    user: CurrentUser = Depends(get_current_user),
    service: AgentService = Depends(get_agent_service),
):
    """List all departments for the tenant."""
    result = await service.list_departments(
        tenant_id=user.tenant_id,
        include_inactive=include_inactive,
    )
    response.headers["Cache-Control"] = "private, max-age=60, stale-while-revalidate=120"
    return {"success": True, "data": result}


@router.get("/departments/{department_id}")
async def get_department(
    department_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    service: AgentService = Depends(get_agent_service),
):
    """Get a single department by ID."""
    result = await service.get_department(
        department_id=department_id,
        tenant_id=user.tenant_id,
    )
    return {"success": True, "data": result}


@router.post("/departments", status_code=201)
async def create_department(
    body: CreateDepartmentRequest,
    user: CurrentUser = Depends(require_role("ADMIN")),
    service: AgentService = Depends(get_agent_service),
):
    """Create a new department. Requires ADMIN role."""
    result = await service.create_department(
        tenant_id=user.tenant_id,
        name=body.name,
        description=body.description,
        sunflower_index=body.sunflower_index,
        cell_id=body.cell_id,
        config=body.config,
    )
    return {"success": True, "data": result}


# ── Agents ──


@router.get("/agents")
async def list_agents(
    department_id: UUID | None = Query(None),
    include_inactive: bool = Query(False),
    user: CurrentUser = Depends(get_current_user),
    service: AgentService = Depends(get_agent_service),
):
    """List agents, optionally filtered by department."""
    result = await service.list_agents(
        tenant_id=user.tenant_id,
        department_id=department_id,
        include_inactive=include_inactive,
    )
    return {"success": True, "data": result}


@router.get("/agents/{agent_id}")
async def get_agent(
    agent_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    service: AgentService = Depends(get_agent_service),
):
    """Get a single agent by ID."""
    result = await service.get_agent(
        agent_id=agent_id,
        tenant_id=user.tenant_id,
    )
    return {"success": True, "data": result}


@router.post("/agents", status_code=201)
async def create_agent(
    body: CreateAgentRequest,
    user: CurrentUser = Depends(require_role("ADMIN")),
    service: AgentService = Depends(get_agent_service),
):
    """Create a new agent in a department. Requires ADMIN role."""
    result = await service.create_agent(
        tenant_id=user.tenant_id,
        department_id=body.department_id,
        name=body.name,
        sub_capability=body.sub_capability,
        description=body.description,
        model_preference=body.model_preference,
        config=body.config,
    )
    return {"success": True, "data": result}


# ── Seed ──


@router.post("/seed", status_code=201)
async def seed_defaults(
    user: CurrentUser = Depends(require_role("ADMIN")),
    service: AgentService = Depends(get_agent_service),
):
    """Bootstrap 10 default departments + 60 agents.

    Idempotent: skips already-existing departments/agents.
    Requires ADMIN role.
    """
    result = await service.seed_defaults(tenant_id=user.tenant_id)
    return {"success": True, "data": result}
