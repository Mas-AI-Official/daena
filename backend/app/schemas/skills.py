"""Skill catalog request/response schemas.

Skills are reusable tool definitions (MCP-style) with governance
tier metadata. They define WHAT tools can do; execution records
track WHAT tools DID.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas._base import DaenaSchema

# ── Requests ──


class CreateSkillRequest(BaseModel):
    """Register a new skill in the catalog."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    category: str | None = Field(None, max_length=100)
    schema_def: dict = Field(
        default_factory=dict,
        description="JSON Schema defining the skill's input parameters",
    )
    implementation: str | None = Field(
        None,
        description="Python code or reference for the skill's logic",
    )
    governance_tier: int = Field(
        0, ge=0, le=4,
        description="Default governance tier (0=SILENT to 4=COUNCIL+APPROVE)",
    )
    version: str = Field("1.0.0", max_length=20)


class UpdateSkillRequest(BaseModel):
    """Update an existing skill."""

    description: str | None = None
    category: str | None = Field(None, max_length=100)
    schema_def: dict | None = None
    implementation: str | None = None
    governance_tier: int | None = Field(None, ge=0, le=4)
    is_active: bool | None = None
    version: str | None = Field(None, max_length=20)


# ── Responses ──


class SkillResponse(DaenaSchema):
    """Skill catalog entry."""

    id: UUID
    tenant_id: UUID
    name: str
    description: str | None = None
    category: str | None = None
    schema_def: dict
    implementation: str | None = None
    governance_tier: int
    is_active: bool
    version: str
    usage_count: int
    created_at: str | None = None
    updated_at: str | None = None


class SkillSummaryResponse(DaenaSchema):
    """Lightweight skill listing (no implementation code)."""

    id: UUID
    name: str
    description: str | None = None
    category: str | None = None
    governance_tier: int
    is_active: bool
    version: str
    usage_count: int
