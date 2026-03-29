"""Project Service: CRUD and context management for project workspaces.

Projects are persistent workspaces where tasks, files, history, and
context are organized. Each project has its own chat scope, connected
runtimes, department assignments, and governance settings.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Project:
    """A persistent project workspace.

    Attributes:
        id: Unique project identifier.
        name: Human-readable project name.
        description: Project description/purpose.
        owner_id: User who created the project.
        created_at: Creation timestamp.
        updated_at: Last modification timestamp.
        working_directory: Local path for file operations.
        connected_runtimes: Which runtimes this project uses.
        memory_scope: Project-specific memory scope identifier.
        task_ids: Task IDs associated with this project.
        file_paths: File paths tracked by this project.
        department_ids: Active department IDs.
        settings: Project-specific settings overrides.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    owner_id: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )
    working_directory: str | None = None
    connected_runtimes: list[str] = field(default_factory=list)
    memory_scope: str = ""
    task_ids: list[str] = field(default_factory=list)
    file_paths: list[str] = field(default_factory=list)
    department_ids: list[str] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "owner_id": self.owner_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "working_directory": self.working_directory,
            "connected_runtimes": self.connected_runtimes,
            "memory_scope": self.memory_scope,
            "task_count": len(self.task_ids),
            "file_count": len(self.file_paths),
            "department_count": len(self.department_ids),
            "settings": self.settings,
        }


class ProjectService:
    """In-memory project management service.

    Provides CRUD operations for project workspaces. Projects
    are scoped to users and provide isolated context for chat,
    task execution, and file management.

    Usage::

        service = ProjectService()
        project = service.create(
            name="Daena V2",
            description="V2 automation",
            owner_id="user-1",
        )
        projects = service.list_for_user("user-1")
    """

    def __init__(self) -> None:
        self._projects: dict[str, Project] = {}

    def create(
        self,
        name: str,
        owner_id: str,
        description: str = "",
        working_directory: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> Project:
        """Create a new project.

        Args:
            name: Project name.
            owner_id: User ID of the creator.
            description: Optional project description.
            working_directory: Local path for file operations.
            settings: Project-specific overrides.

        Returns:
            The created Project.
        """
        project = Project(
            name=name,
            description=description,
            owner_id=owner_id,
            working_directory=working_directory,
            memory_scope=f"project:{name.lower().replace(' ', '-')}",
            settings=settings or {},
        )
        self._projects[project.id] = project

        logger.info(
            "project.created",
            project_id=project.id,
            name=name,
            owner_id=owner_id,
        )
        return project

    def get(self, project_id: str) -> Project | None:
        """Get a project by ID."""
        return self._projects.get(project_id)

    def list_for_user(
        self,
        owner_id: str,
        limit: int = 50,
    ) -> list[Project]:
        """List all projects for a user, most recent first.

        Args:
            owner_id: User ID to filter by.
            limit: Max projects to return.

        Returns:
            List of Projects sorted by updated_at descending.
        """
        projects = [
            p for p in self._projects.values()
            if p.owner_id == owner_id
        ]
        projects.sort(key=lambda p: p.updated_at, reverse=True)
        return projects[:limit]

    def update(
        self,
        project_id: str,
        **updates: Any,
    ) -> Project | None:
        """Update project fields.

        Args:
            project_id: Project to update.
            **updates: Fields to update (name, description, settings, etc.)

        Returns:
            Updated project, or None if not found.
        """
        project = self._projects.get(project_id)
        if not project:
            return None

        for key, value in updates.items():
            if hasattr(project, key) and key not in ("id", "owner_id", "created_at"):
                setattr(project, key, value)

        project.updated_at = datetime.now(UTC).isoformat()

        logger.info(
            "project.updated",
            project_id=project_id,
            fields=list(updates.keys()),
        )
        return project

    def delete(self, project_id: str) -> bool:
        """Delete a project.

        Args:
            project_id: Project to delete.

        Returns:
            True if deleted, False if not found.
        """
        if project_id in self._projects:
            del self._projects[project_id]
            logger.info("project.deleted", project_id=project_id)
            return True
        return False

    def add_task(self, project_id: str, task_id: str) -> bool:
        """Associate a task with a project."""
        project = self._projects.get(project_id)
        if project and task_id not in project.task_ids:
            project.task_ids.append(task_id)
            return True
        return False

    def add_file(self, project_id: str, file_path: str) -> bool:
        """Track a file in the project."""
        project = self._projects.get(project_id)
        if project and file_path not in project.file_paths:
            project.file_paths.append(file_path)
            return True
        return False

    @property
    def project_count(self) -> int:
        """Total number of projects."""
        return len(self._projects)
