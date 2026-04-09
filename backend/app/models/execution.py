"""Execution models: Task, ToolExecution, Skill.

Background tasks, tool invocations, and the skill catalog.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, JSONBCompat, SoftDeleteMixin, TenantMixin, TimestampMixin


class Task(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    """Background task (Autopilot mode). Tracks long-running operations."""

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,

    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="PENDING")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    result: Mapped[dict | None] = mapped_column(JSONBCompat, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    checkpoint_data: Mapped[dict | None] = mapped_column(JSONBCompat, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ToolExecution(Base, TenantMixin):
    """Record of a single tool invocation with governance metadata."""

    __tablename__ = "tool_executions"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,

    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True
    )
    tool_name: Mapped[str] = mapped_column(String(200), nullable=False)
    tool_params: Mapped[dict | None] = mapped_column(JSONBCompat, nullable=True)
    tool_result: Mapped[dict | None] = mapped_column(JSONBCompat, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="PENDING")
    governance_tier: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Skill(Base, TenantMixin, TimestampMixin):
    """Reusable skill in the skill catalog (MCP-style)."""

    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,

    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    schema_def: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, server_default="{}")
    implementation: Mapped[str | None] = mapped_column(Text, nullable=True)
    governance_tier: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    version: Mapped[str] = mapped_column(String(20), nullable=False, server_default="1.0.0")
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
