"""Memory (NBMF) schemas: request/response models for memory operations.

Covers storing, recalling, promoting, and demoting memories
across the 5-tier Neural-Backed Memory Fabric.

Content types:
    User-facing: FACT, PREFERENCE, LEARNING, POLICY, DIRECTIVE
    Pipeline:    INTERACTION
    Agent:       AGENT_DECISION, SKILL_OUTCOME, PATTERN_LEARNED, APPROACH_FAILED
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas._base import DaenaSchema

# All valid content types for memory entries
_CONTENT_TYPE_RE = (
    "^(FACT|PREFERENCE|LEARNING|POLICY|DIRECTIVE"
    "|INTERACTION"
    "|AGENT_DECISION|SKILL_OUTCOME|PATTERN_LEARNED|APPROACH_FAILED)$"
)


class StoreMemoryRequest(BaseModel):
    """Request to store a new memory entry."""

    content: str = Field(..., min_length=1, max_length=50000)
    content_type: str = Field("FACT", pattern=_CONTENT_TYPE_RE)
    summary: str | None = Field(None, max_length=500)
    tags: list[str] = Field(default_factory=list)
    source: str | None = Field(None, max_length=200)
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    tier: int = Field(0, ge=0, le=2)
    scope: str = Field("USER", pattern="^(USER|SESSION|TENANT)$")
    session_id: UUID | None = None
    agent_id: UUID | None = None
    skill_id: str | None = None
    success_flag: bool | None = None
    metadata: dict | None = None


class StoreExperienceRequest(BaseModel):
    """Request to store an agent experience (auto-quarantined)."""

    agent_id: UUID
    content_type: str = Field(
        "AGENT_DECISION",
        pattern="^(AGENT_DECISION|SKILL_OUTCOME|PATTERN_LEARNED|APPROACH_FAILED)$",
    )
    content: str = Field(..., min_length=1, max_length=50000)
    summary: str | None = Field(None, max_length=500)
    skill_id: str | None = None
    success_flag: bool | None = None
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    metadata: dict | None = None


class PromoteRequest(BaseModel):
    """Request to promote a memory to a higher tier."""

    reason: str = Field(..., min_length=1, max_length=2000)


class DemoteRequest(BaseModel):
    """Request to demote a memory to a lower tier."""

    reason: str = Field(..., min_length=1, max_length=2000)


class MemoryResponse(DaenaSchema):
    """Single memory entry response."""

    id: UUID
    tenant_id: UUID
    user_id: UUID | None = None
    agent_id: UUID | None = None
    tier: int
    content_type: str
    content: str
    summary: str | None = None
    tags: list[str] = Field(default_factory=list)
    source: str | None = None
    confidence: float
    scope: str
    session_id: UUID | None = None
    access_count: int
    last_accessed: str | None = None
    expires_at: str | None = None
    is_quarantined: bool = False
    trust_score: float = 0.0
    content_hash: str | None = None
    skill_id: str | None = None
    success_flag: bool | None = None
    verification_status: str
    verified_by: UUID | None = None
    metadata: dict = Field(default_factory=dict)
    archived_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class LearningLogResponse(DaenaSchema):
    """Audit entry for a memory tier change."""

    id: UUID
    memory_id: UUID
    action: str
    from_tier: int | None = None
    to_tier: int | None = None
    reason: str | None = None
    actor_id: UUID | None = None
    created_at: str | None = None


class MemoryStatsResponse(DaenaSchema):
    """Memory statistics with quarantine info."""

    total_memories: int = 0
    quarantined_count: int = 0
    per_tier_counts: dict[str, int] = Field(default_factory=dict)
    experience_count: int = 0
    avg_trust_score: float = 0.0
