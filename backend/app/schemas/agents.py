"""Agent & Department schemas: request/response models.

Covers CRUD for departments and agents, plus seed_defaults
for bootstrapping the 10-department Sunflower-Honeycomb structure.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas._base import DaenaSchema


class CreateDepartmentRequest(BaseModel):
    """Request to create a new department."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=2000)
    sunflower_index: int = Field(..., ge=0)
    cell_id: str | None = Field(None, max_length=20)
    config: dict | None = None


class CreateAgentRequest(BaseModel):
    """Request to create a new agent within a department."""

    department_id: UUID
    name: str = Field(..., min_length=1, max_length=100)
    sub_capability: str = Field(
        ..., pattern="^(MIND|EYES|HANDS|VOICE|SHIELD|MEMORY)$"
    )
    description: str | None = Field(None, max_length=2000)
    model_preference: str | None = Field(None, max_length=100)
    config: dict | None = None


class DepartmentResponse(DaenaSchema):
    """Single department response."""

    id: UUID
    tenant_id: UUID
    name: str
    description: str | None = None
    sunflower_index: int
    cell_id: str | None = None
    config: dict = Field(default_factory=dict)
    is_active: bool
    agent_count: int = 0
    created_at: str | None = None
    updated_at: str | None = None


class AgentResponse(DaenaSchema):
    """Single agent response."""

    id: UUID
    tenant_id: UUID
    department_id: UUID
    name: str
    sub_capability: str
    description: str | None = None
    model_preference: str | None = None
    config: dict = Field(default_factory=dict)
    is_active: bool
    created_at: str | None = None
    updated_at: str | None = None
