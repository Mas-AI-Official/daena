"""Execution request/response schemas.

Covers execution modes (CMD/EXE), task management (Autopilot),
and tool execution records with governance metadata.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas._base import DaenaSchema

# ── Requests ──


class ExecuteToolRequest(BaseModel):
    """Request to execute a tool within an EXE-mode session.

    Governance is evaluated automatically based on the tool's
    risk level and the session's governance slider.
    """

    tool_name: str = Field(..., min_length=1, max_length=200)
    params: dict = Field(default_factory=dict)
    session_id: UUID
    plan_approval_id: UUID | None = None


class CreateTaskRequest(BaseModel):
    """Create a background task (Autopilot mode)."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    session_id: UUID | None = None
    steps: list[dict] = Field(
        default_factory=list,
        description="Planned execution steps for governance pre-approval",
    )


class UpdateTaskRequest(BaseModel):
    """Update a running task's status or checkpoint."""

    status: str | None = Field(None, pattern="^(PAUSED|CANCELLED)$")
    checkpoint_data: dict | None = None


# ── Responses ──


class ToolExecutionResponse(DaenaSchema):
    """Result of a single tool execution."""

    id: UUID
    task_id: UUID | None = None
    session_id: UUID | None = None
    tool_name: str
    tool_params: dict | None = None
    tool_result: dict | None = None
    status: str
    governance_tier: int
    latency_ms: int | None = None
    error: str | None = None
    created_at: datetime | None = None


class TaskResponse(DaenaSchema):
    """Background task status and progress."""

    id: UUID
    user_id: UUID
    tenant_id: UUID
    session_id: UUID | None = None
    name: str
    description: str | None = None
    status: str
    progress: int
    result: dict | None = None
    error: str | None = None
    checkpoint_data: dict | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class GovernanceCheckResponse(BaseModel):
    """Pre-execution governance check result (returned before tool runs)."""

    allowed: bool
    governance_tier: int
    risk_level: str
    action_type: str
    requires_approval: bool
    message: str
    plan_covered: bool = False
