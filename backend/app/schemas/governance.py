"""Governance request/response schemas.

Covers: evaluation requests, governance decisions, approval workflows,
and audit trail entries.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas._base import DaenaSchema

# ── Evaluation ──


class EvaluateRequest(BaseModel):
    """Request to evaluate an action against governance policies."""

    action_type: str = Field(..., min_length=1, max_length=100)
    action_params: dict | None = None
    governance_mode: str = Field(
        "BALANCED",
        pattern="^(YOLO|LIGHT|STANDARD|STRICT|PARANOID|UNLEASHED|BALANCED|GOVERNED)$",
    )
    actor_type: str = Field("USER", pattern="^(USER|AGENT|COUNCIL|SYSTEM|FOUNDER)$")
    session_id: UUID | None = None


class GovernanceDecisionResponse(DaenaSchema):
    """Result of a governance evaluation."""

    allowed: bool
    governance_tier: int
    risk_level: str
    action_type: str
    requires_approval: bool = False
    request_id: UUID | None = None
    hard_law_violations: list[str] = Field(default_factory=list)
    message: str = ""


# ── Approvals ──


class CreateApprovalRequest(BaseModel):
    """Request to create a governance approval."""

    action_type: str = Field(..., min_length=1, max_length=100)
    action_params: dict | None = None
    risk_level: str = Field(..., pattern="^(NONE|LOW|MEDIUM|HIGH|CRITICAL)$")
    governance_tier: int = Field(..., ge=0, le=4)
    session_id: UUID | None = None
    context: dict | None = None


class ApprovalDecisionRequest(BaseModel):
    """Approve or reject a pending approval."""

    decision: str = Field(..., pattern="^(APPROVED|REJECTED)$")
    reason: str | None = Field(None, max_length=2000)


class ApprovalResponse(DaenaSchema):
    """Serialized governance approval request."""

    id: UUID
    tenant_id: UUID
    user_id: UUID
    action_type: str
    action_params: dict | None = None
    risk_level: str
    governance_tier: int
    status: str
    decided_by: UUID | None = None
    decided_at: str | None = None
    decision_reason: str | None = None
    expires_at: str | None = None
    session_id: UUID | None = None
    created_at: str | None = None
    updated_at: str | None = None


# ── Audit ──


class AuditEntryResponse(DaenaSchema):
    """Serialized tamper-evident audit log entry."""

    id: UUID
    tenant_id: UUID
    actor_id: UUID | None = None
    actor_type: str
    action_type: str
    action_params: dict | None = None
    result: str
    risk_level: str
    governance_tier: int
    prev_hash: str | None = None
    entry_hash: str
    session_id: UUID | None = None
    created_at: str | None = None
