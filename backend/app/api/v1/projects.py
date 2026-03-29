"""Project API endpoints: CRUD for persistent project workspaces.

Users create projects to organize tasks, files, chat sessions,
and department assignments into isolated workspaces.
"""

from __future__ import annotations

import html as _html
import re as _re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.api.deps import CurrentUser, get_current_user
from app.core.logging import get_logger
from app.services.project_service import ProjectService

logger = get_logger(__name__)

router = APIRouter()

# Singleton project service
_project_service: ProjectService | None = None


def get_project_service() -> ProjectService:
    """Get or create the singleton ProjectService."""
    global _project_service
    if _project_service is None:
        _project_service = ProjectService()
    return _project_service


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


class AddTaskBody(BaseModel):
    """Request body for associating a task with a project."""
    task_id: str


class AddFileBody(BaseModel):
    """Request body for tracking a file in a project."""
    file_path: str


# ── Endpoints ──


@router.get("")
async def list_projects(
    limit: int = 50,
    user: CurrentUser = Depends(get_current_user),
):
    """List all projects for the current user, most recent first."""
    service = get_project_service()
    projects = service.list_for_user(str(user.id), limit=limit)
    return {
        "projects": [p.to_dict() for p in projects],
        "count": len(projects),
    }


@router.post("")
async def create_project(
    body: CreateProjectBody,
    user: CurrentUser = Depends(get_current_user),
):
    """Create a new project workspace."""
    service = get_project_service()
    project = service.create(
        name=body.name,
        owner_id=str(user.id),
        description=body.description,
        working_directory=body.working_directory,
        settings=body.settings,
    )
    return {"success": True, "project": project.to_dict()}


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Get a specific project by ID."""
    service = get_project_service()
    project = service.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.owner_id != str(user.id):
        raise HTTPException(status_code=403, detail="Not your project")
    return project.to_dict()


@router.put("/{project_id}")
async def update_project(
    project_id: str,
    body: UpdateProjectBody,
    user: CurrentUser = Depends(get_current_user),
):
    """Update project fields."""
    service = get_project_service()
    project = service.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.owner_id != str(user.id):
        raise HTTPException(status_code=403, detail="Not your project")

    updates = body.model_dump(exclude_none=True)
    updated = service.update(project_id, **updates)
    return {"success": True, "project": updated.to_dict()}


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Delete a project."""
    service = get_project_service()
    project = service.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.owner_id != str(user.id):
        raise HTTPException(status_code=403, detail="Not your project")

    service.delete(project_id)
    return {"success": True}


@router.get("/{project_id}/tasks")
async def list_project_tasks(
    project_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """List task IDs associated with a project."""
    service = get_project_service()
    project = service.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"task_ids": project.task_ids, "count": len(project.task_ids)}


@router.post("/{project_id}/tasks")
async def add_project_task(
    project_id: str,
    body: AddTaskBody,
    user: CurrentUser = Depends(get_current_user),
):
    """Associate a task with a project."""
    service = get_project_service()
    added = service.add_task(project_id, body.task_id)
    if not added:
        raise HTTPException(
            status_code=404,
            detail="Project not found or task already added",
        )
    return {"success": True}


@router.get("/{project_id}/files")
async def list_project_files(
    project_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """List file paths tracked by a project."""
    service = get_project_service()
    project = service.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"file_paths": project.file_paths, "count": len(project.file_paths)}


@router.post("/{project_id}/files")
async def add_project_file(
    project_id: str,
    body: AddFileBody,
    user: CurrentUser = Depends(get_current_user),
):
    """Track a file in a project."""
    service = get_project_service()
    added = service.add_file(project_id, body.file_path)
    if not added:
        raise HTTPException(
            status_code=404,
            detail="Project not found or file already tracked",
        )
    return {"success": True}
