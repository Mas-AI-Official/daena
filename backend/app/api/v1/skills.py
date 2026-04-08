"""Skill catalog endpoints: CRUD for reusable tool definitions.

Skills are Daena's MCP-style tools with governance tier metadata.
All skills are tenant-scoped.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_role
from app.core.database import get_db
from app.schemas.skills import CreateSkillRequest, UpdateSkillRequest
from app.services.skill_service import SkillService

router = APIRouter()


async def get_skill_service(
    db: AsyncSession = Depends(get_db),
) -> SkillService:
    """Factory dependency for SkillService."""
    return SkillService(db)


@router.post("", status_code=201)
async def create_skill(
    body: CreateSkillRequest,
    user: CurrentUser = Depends(require_role("ADMIN")),
    service: SkillService = Depends(get_skill_service),
) -> dict:
    """Register a new skill in the tenant's catalog.

    Requires ADMIN role — skills define what tools are available
    to all users in the tenant.
    """
    skill = await service.create_skill(
        name=body.name,
        tenant_id=user.tenant_id,
        description=body.description,
        category=body.category,
        schema_def=body.schema_def,
        implementation=body.implementation,
        governance_tier=body.governance_tier,
        version=body.version,
    )
    return {"success": True, "data": skill}


@router.post("/seed")
async def seed_skills(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Force re-seed default skills for the current tenant. Idempotent."""
    from app.services.agents import AgentService

    svc = AgentService(db)
    result = await svc.seed_defaults(tenant_id=user.tenant_id)
    await db.commit()
    return {"success": True, "data": result}


@router.get("")
async def list_skills(
    user: CurrentUser = Depends(get_current_user),
    service: SkillService = Depends(get_skill_service),
    category: str | None = Query(None),
    active_only: bool = Query(True),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict:
    """List skills in the tenant's catalog."""
    result = await service.list_skills(
        tenant_id=user.tenant_id,
        category=category,
        active_only=active_only,
        page=page,
        page_size=page_size,
    )
    return {"success": True, "data": result.data, "pagination": result.pagination}


# ── Static paths MUST come before /{skill_id} to avoid UUID capture ──


@router.get("/installed")
async def list_installed_skills(
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Scan filesystem for SKILL.md files and return discovered skills."""
    from app.services.skill_scanner import scan_skills

    skills = scan_skills()
    return {
        "success": True,
        "data": [s.to_dict() for s in skills],
    }


# ── Dynamic paths (UUID-based) ──


@router.get("/{skill_id}")
async def get_skill(
    skill_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    service: SkillService = Depends(get_skill_service),
) -> dict:
    """Get full details of a skill including implementation."""
    skill = await service.get_skill(skill_id, user.tenant_id)
    return {"success": True, "data": skill}


@router.patch("/{skill_id}")
async def update_skill(
    skill_id: UUID,
    body: UpdateSkillRequest,
    user: CurrentUser = Depends(require_role("ADMIN")),
    service: SkillService = Depends(get_skill_service),
) -> dict:
    """Update a skill's metadata, implementation, or governance tier.

    Requires ADMIN role. Only provided fields are updated.
    """
    skill = await service.update_skill(
        skill_id,
        user.tenant_id,
        description=body.description,
        category=body.category,
        schema_def=body.schema_def,
        implementation=body.implementation,
        governance_tier=body.governance_tier,
        is_active=body.is_active,
        version=body.version,
    )
    return {"success": True, "data": skill}


@router.delete("/{skill_id}")
async def deactivate_skill(
    skill_id: UUID,
    user: CurrentUser = Depends(require_role("ADMIN")),
    service: SkillService = Depends(get_skill_service),
) -> dict:
    """Soft-deactivate a skill (keeps in catalog but hidden).

    Follows Daena Rule #2: never delete -- deactivate instead.
    """
    skill = await service.deactivate_skill(skill_id, user.tenant_id)
    return {"success": True, "data": skill}


class CreateFileSkillRequest:
    """Request to create a SKILL.md file."""


from pydantic import BaseModel, Field


class FileSkillCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    instructions: str = Field(..., min_length=10)
    trigger: str | None = None


@router.post("/create-file", status_code=201)
async def create_file_skill(
    body: FileSkillCreate,
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Create a new SKILL.md file in the project skills directory."""
    from app.services.skill_scanner import create_skill

    skill = create_skill(
        name=body.name,
        description=body.description,
        instructions=body.instructions,
        trigger=body.trigger,
    )
    return {"success": True, "data": skill.to_dict()}
