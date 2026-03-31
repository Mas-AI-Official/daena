"""Project model -- persistent workspaces for organizing work.

Projects survive backend restarts (stored in DB, not in-memory).
Each project scopes chat sessions, tasks, files, and memory.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, JSONBCompat, TenantMixin, TimestampMixin


class Project(Base, TenantMixin, TimestampMixin):
    """A persistent project workspace."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    owner_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    working_directory: Mapped[str | None] = mapped_column(String(500), nullable=True)
    memory_scope: Mapped[str] = mapped_column(String(255), default="", server_default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    settings: Mapped[dict] = mapped_column(JSONBCompat(), default=dict, server_default="{}")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "owner_id": str(self.owner_id),
            "working_directory": self.working_directory,
            "memory_scope": self.memory_scope,
            "is_active": self.is_active,
            "settings": self.settings or {},
            "task_count": 0,
            "file_count": 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
