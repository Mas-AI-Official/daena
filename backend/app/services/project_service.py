"""Project Service: CRUD for persistent project workspaces.

Projects survive backend restarts (stored in DB via SQLAlchemy).
Each project scopes chat sessions, tasks, files, and memory.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.project import Project

logger = get_logger(__name__)


class ProjectService:
    """Database-backed project management service.

    Provides CRUD operations for project workspaces. Projects
    are scoped to tenants and users, and persist across restarts.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        name: str,
        owner_id: UUID,
        tenant_id: UUID,
        description: str = "",
        working_directory: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> dict:
        """Create a new project."""
        project = Project(
            name=name,
            description=description,
            owner_id=owner_id,
            tenant_id=tenant_id,
            working_directory=working_directory,
            memory_scope=f"project:{name.lower().replace(' ', '-')}",
            settings=settings or {},
        )
        self._db.add(project)
        await self._db.flush()

        logger.info(
            "project.created",
            project_id=str(project.id),
            name=name,
            owner_id=str(owner_id),
        )
        return project.to_dict()

    async def get(self, project_id: UUID, tenant_id: UUID) -> dict | None:
        """Get a project by ID."""
        stmt = select(Project).where(
            Project.id == project_id,
            Project.tenant_id == tenant_id,
        )
        result = await self._db.execute(stmt)
        project = result.scalar_one_or_none()
        return project.to_dict() if project else None

    async def list_for_user(
        self,
        owner_id: UUID,
        tenant_id: UUID,
        limit: int = 50,
    ) -> list[dict]:
        """List all projects for a user, most recent first."""
        stmt = (
            select(Project)
            .where(
                Project.tenant_id == tenant_id,
                Project.owner_id == owner_id,
                Project.is_active == True,  # noqa: E712
            )
            .order_by(Project.updated_at.desc())
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        return [p.to_dict() for p in result.scalars().all()]

    async def update(
        self,
        project_id: UUID,
        tenant_id: UUID,
        **updates: Any,
    ) -> dict | None:
        """Update project fields."""
        stmt = select(Project).where(
            Project.id == project_id,
            Project.tenant_id == tenant_id,
        )
        result = await self._db.execute(stmt)
        project = result.scalar_one_or_none()
        if not project:
            return None

        for key, value in updates.items():
            if hasattr(project, key) and key not in ("id", "owner_id", "tenant_id", "created_at"):
                setattr(project, key, value)

        await self._db.flush()
        await self._db.refresh(project)

        logger.info(
            "project.updated",
            project_id=str(project_id),
            fields=list(updates.keys()),
        )
        return project.to_dict()

    async def delete(self, project_id: UUID, tenant_id: UUID) -> bool:
        """Soft-delete a project (set is_active=False)."""
        stmt = select(Project).where(
            Project.id == project_id,
            Project.tenant_id == tenant_id,
        )
        result = await self._db.execute(stmt)
        project = result.scalar_one_or_none()
        if not project:
            return False

        project.is_active = False
        await self._db.flush()
        logger.info("project.deleted", project_id=str(project_id))
        return True

    async def count(self, tenant_id: UUID) -> int:
        """Total number of active projects."""
        from sqlalchemy import func
        stmt = select(func.count(Project.id)).where(
            Project.tenant_id == tenant_id,
            Project.is_active == True,  # noqa: E712
        )
        result = await self._db.execute(stmt)
        return result.scalar() or 0
