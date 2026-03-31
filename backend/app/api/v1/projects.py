"""Project API endpoints: CRUD for persistent project workspaces.

Users create projects to organize tasks, files, chat sessions,
and department assignments into isolated workspaces.
Projects persist in the database (survive restarts).
"""

from __future__ import annotations

import html as _html
import re as _re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.services.project_service import ProjectService

logger = get_logger(__name__)

router = APIRouter()


# ── Helpers ──


def _sanitize_text(value: str, max_length: int = 500) -> str:
    """Sanitize user-provided text: strip HTML tags, limit length."""
    clean = _re.sub(r'<[^>]+>', '', value)
    clean = _html.unescape(clean)
    return clean[:max_length].strip()


# ── Request models ──


class CreateProjectBody(BaseModel):
    """Request body for creating a project."""
    name: str
    description: str = ""
    working_directory: str | None = None
    settings: dict | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = _sanitize_text(v, max_length=200)
        if not v:
            raise ValueError("Project name cannot be empty")
        if len(v) < 2:
            raise ValueError("Project name must be at least 2 characters")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        return _sanitize_text(v, max_length=2000)


class UpdateProjectBody(BaseModel):
    """Request body for updating a project."""
    name: str | None = None
    description: str | None = None
    working_directory: str | None = None
    settings: dict | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is not None:
            v = _sanitize_text(v, max_length=200)
            if len(v) < 2:
                raise ValueError("Project name must be at least 2 characters")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        if v is not None:
            v = _sanitize_text(v, max_length=2000)
        return v


# ── Endpoints ──


@router.get("")
async def list_projects(
    limit: int = 50,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all projects for the current user, most recent first."""
    service = ProjectService(db)
    projects = await service.list_for_user(
        owner_id=user.id,
        tenant_id=user.tenant_id,
        limit=limit,
    )
    return {
        "projects": projects,
        "count": len(projects),
    }


@router.post("")
async def create_project(
    body: CreateProjectBody,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new project workspace."""
    service = ProjectService(db)
    project = await service.create(
        name=body.name,
        owner_id=user.id,
        tenant_id=user.tenant_id,
        description=body.description,
        working_directory=body.working_directory,
        settings=body.settings,
    )
    await db.commit()
    return {"success": True, "project": project}


@router.get("/{project_id}")
async def get_project(
    project_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific project by ID."""
    service = ProjectService(db)
    project = await service.get(project_id, tenant_id=user.tenant_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.put("/{project_id}")
async def update_project(
    project_id: UUID,
    body: UpdateProjectBody,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update project fields."""
    service = ProjectService(db)
    updates = body.model_dump(exclude_none=True)
    updated = await service.update(project_id, tenant_id=user.tenant_id, **updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.commit()
    return {"success": True, "project": updated}


@router.delete("/{project_id}")
async def delete_project(
    project_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a project (soft-delete)."""
    service = ProjectService(db)
    deleted = await service.delete(project_id, tenant_id=user.tenant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.commit()
    return {"success": True}
