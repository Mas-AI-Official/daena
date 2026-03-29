"""Governance endpoints: evaluation, approvals, audit trail.

Thin router layer — all business logic lives in GovernanceEngine,
ApprovalService, and AuditService.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_role
from app.core.database import get_db
from app.schemas.governance import (
    ApprovalDecisionRequest,
    EvaluateRequest,
)
from app.services.approval import ApprovalService
from app.services.audit import AuditService
from app.services.governance import GovernanceEngine

router = APIRouter()


# ── Dependency factories ──


async def get_governance_engine(
    db: AsyncSession = Depends(get_db),
) -> GovernanceEngine:
    """Create GovernanceEngine per request."""
    return GovernanceEngine(db)


async def get_approval_service(
    db: AsyncSession = Depends(get_db),
) -> ApprovalService:
    """Create ApprovalService per request."""
    return ApprovalService(db)


async def get_audit_service(
    db: AsyncSession = Depends(get_db),
) -> AuditService:
    """Create AuditService per request."""
    return AuditService(db)


# ── Evaluation ──


@router.post("/evaluate")
async def evaluate_action(
    body: EvaluateRequest,
    user: CurrentUser = Depends(get_current_user),
    engine: GovernanceEngine = Depends(get_governance_engine),
    audit: AuditService = Depends(get_audit_service),
):
    """Evaluate an action against governance policies.

    Returns the governance decision including tier, risk level,
    and whether approval is required.
    """
    decision = await engine.evaluate(
        action_type=body.action_type,
        action_params=body.action_params,
        governance_slider=body.governance_slider,
        actor_type=body.actor_type,
        actor_role=user.role,
        tenant_id=user.tenant_id,
        user_id=user.id,
        session_id=body.session_id,
    )

    # Log every evaluation (Hard Law #1)
    result = "ALLOWED" if decision["allowed"] else "BLOCKED"
    if decision["requires_approval"]:
        result = "APPROVAL_REQUIRED"

    await audit.log_decision(
        tenant_id=user.tenant_id,
        actor_id=user.id,
        actor_type=body.actor_type,
        action_type=body.action_type,
        action_params=body.action_params,
        result=result,
        risk_level=decision["risk_level"],
        governance_tier=decision["governance_tier"],
        session_id=body.session_id,
    )

    return {"success": True, "data": decision}


# ── Approvals ──


@router.get("/approvals")
async def list_pending_approvals(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status: str | None = Query(None, description="Filter by status: PENDING, APPROVED, REJECTED, EXPIRED"),
    user: CurrentUser = Depends(require_role("MANAGER")),
    service: ApprovalService = Depends(get_approval_service),
):
    """List approval requests for the tenant, optionally filtered by status.

    Defaults to PENDING when no status filter is provided.
    Requires MANAGER role or higher.
    """
    result = await service.list_pending(
        tenant_id=user.tenant_id,
        page=page,
        page_size=page_size,
        status=status,
    )
    return {"success": True, **result}


@router.get("/approvals/{request_id}")
async def get_approval(
    request_id: UUID,
    user: CurrentUser = Depends(require_role("MANAGER")),
    service: ApprovalService = Depends(get_approval_service),
):
    """Get a specific approval request."""
    result = await service.get_request(
        request_id=request_id,
        tenant_id=user.tenant_id,
    )
    return {"success": True, "data": result}


@router.post("/approvals/{request_id}/decide")
async def decide_approval(
    request_id: UUID,
    body: ApprovalDecisionRequest,
    user: CurrentUser = Depends(require_role("MANAGER")),
    service: ApprovalService = Depends(get_approval_service),
    audit: AuditService = Depends(get_audit_service),
):
    """Approve or reject a pending approval request.

    Requires MANAGER role or higher. Logs the decision to audit trail.
    """
    if body.decision == "APPROVED":
        result = await service.approve(
            request_id=request_id,
            tenant_id=user.tenant_id,
            decided_by=user.id,
            reason=body.reason,
        )
    else:
        result = await service.reject(
            request_id=request_id,
            tenant_id=user.tenant_id,
            decided_by=user.id,
            reason=body.reason,
        )

    # Audit the decision
    await audit.log_decision(
        tenant_id=user.tenant_id,
        actor_id=user.id,
        actor_type="USER",
        action_type=f"APPROVAL_{body.decision}",
        action_params={"request_id": str(request_id), "reason": body.reason},
        result=body.decision,
        risk_level=result["risk_level"],
        governance_tier=result["governance_tier"],
    )

    return {"success": True, "data": result}


# ── Audit Trail ──


@router.get("/audit")
async def get_audit_trail(
    response: Response,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    action_type: str | None = Query(None),
    user: CurrentUser = Depends(require_role("AUDITOR")),
    service: AuditService = Depends(get_audit_service),
):
    """Retrieve the governance audit trail.

    Requires AUDITOR role or higher. Supports filtering by action_type.
    """
    result = await service.get_audit_trail(
        tenant_id=user.tenant_id,
        page=page,
        page_size=page_size,
        action_type=action_type,
    )
    response.headers["Cache-Control"] = "private, max-age=10, stale-while-revalidate=30"
    return {"success": True, **result}


@router.get("/audit/verify")
async def verify_audit_integrity(
    user: CurrentUser = Depends(require_role("ADMIN")),
    service: AuditService = Depends(get_audit_service),
):
    """Verify the hash chain integrity of the audit trail.

    Requires ADMIN role. Walks the entire chain for the tenant
    and reports any breaks.
    """
    result = await service.verify_chain_integrity(tenant_id=user.tenant_id)
    return {"success": True, "data": result}
