"""Governance endpoints: evaluation, approvals, audit trail.

Thin router layer -- all business logic lives in GovernanceEngine,
ApprovalService, and AuditService.
"""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_role
from app.core.database import get_db
from app.core.sse_channels import approval_channel
from app.schemas.governance import (
    ApprovalDecisionRequest,
    ApprovalResponse,
    CreateApprovalRequest,
    EvaluateRequest,
)
from app.services.approval import ApprovalService
from app.services.audit import AuditService
from app.services.governance import GovernanceEngine

router = APIRouter()


# Standard SSE response headers; matches the chat + scan stream
# convention so frontend EventSource clients see consistent framing.
_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


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
        governance_slider=body.governance_mode,
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


@router.post("/approvals", status_code=201, response_model=ApprovalResponse)
async def create_approval(
    body: CreateApprovalRequest,
    user: CurrentUser = Depends(get_current_user),
    service: ApprovalService = Depends(get_approval_service),
    audit: AuditService = Depends(get_audit_service),
) -> ApprovalResponse:
    """Create a governance approval request.

    Used when an action requires human approval before execution.
    Logs the request to the audit trail.
    """
    result = await service.request_approval(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action_type=body.action_type,
        action_params=body.action_params,
        risk_level=body.risk_level,
        governance_tier=body.governance_tier,
        session_id=body.session_id,
        context=body.context,
    )

    await audit.log_decision(
        tenant_id=user.tenant_id,
        actor_id=user.id,
        actor_type="USER",
        action_type="APPROVAL_REQUESTED",
        action_params={"action_type": body.action_type, "risk_level": body.risk_level},
        result="PENDING",
        risk_level=body.risk_level,
        governance_tier=body.governance_tier,
        session_id=body.session_id,
    )

    return ApprovalResponse(**result)


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


@router.get("/approvals/events")
async def stream_approval_events(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    """Server-sent events for governance approval lifecycle.

    Subscribes to ``approval_channel`` and yields each envelope as a
    formatted SSE event. Decoupled from the chat SSE so approvals are
    live whether or not a chat session is open.

    Tenant filter: only events whose ``data.tenant_id`` matches the
    caller's tenant are forwarded. Cross-tenant isolation matches the
    rest of the governance API surface.

    Emits the following event types:

    - ``approval.pending`` ``{approval_id, tenant_id, tier, risk_level,
      action_type, session_id, expires_at, created_at}`` -- a new
      approval was created and is awaiting decision.
    - ``approval.resolved`` ``{approval_id, tenant_id, decision,
      resolver_user_id, decided_at, reason}`` -- approve or reject
      landed. ``decision`` is ``"APPROVED"`` or ``"REJECTED"``.
    - ``approval.expired`` ``{approval_id, tenant_id, expired_at}``
      Sweeper marked a stale pending request EXPIRED.
    - ``ping`` synthetic heartbeat every 25s of idle time.
    """
    tenant_id = str(user.tenant_id)

    async def _event_stream():
        async for envelope in approval_channel.subscribe():
            if await request.is_disconnected():
                break
            # Forward heartbeats unconditionally (no tenant on a ping)
            # and tenant-scope every domain event so cross-tenant
            # approvals never leak across the wire.
            payload = envelope.get("data") or {}
            if envelope.get("type") != "ping":
                if payload.get("tenant_id") and payload.get("tenant_id") != tenant_id:
                    continue
            data = json.dumps(envelope)
            yield f"event: {envelope['type']}\ndata: {data}\n\n"

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


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


@router.post("/audit/verify")
async def verify_audit_integrity_post(
    user: CurrentUser = Depends(require_role("ADMIN")),
    service: AuditService = Depends(get_audit_service),
):
    """Run a full chain verification (structural + content) and return
    a rich diagnostic if a break is detected.

    Distinct from ``GET /audit/verify`` which is the lightweight badge
    endpoint used by the audit page header. This POST is the operator /
    incident-response endpoint: it always runs in deep mode and emits
    diagnostic detail for the FIRST break encountered (chain index,
    row id, break kind, previous_hash, expected_hash, actual_hash). It
    does NOT mutate any audit row -- the audit ledger is append-only
    by design (Hard Law #9) and even verification must read-only.

    POST is the right verb because verification is an action with
    measurable cost (one SHA-256 recompute per row), is not safely
    cacheable (chain state mutates over time), and may evolve to
    accept future filter parameters (since_id, since_ts, max_rows)
    via a request body without breaking the URL shape.

    Requires ADMIN role. Tenant-scoped: caller's tenant_id is the
    only chain walked; cross-tenant tamper cannot be detected from
    one tenant's POST.

    Response shape:

    .. code-block:: json

        {
          "success": true,
          "data": {
            "verified": false,
            "total_entries": 12,
            "tenant_id": "...",
            "first_break_index": 3,
            "first_break": {
              "row_id": "...",
              "kind": "content",
              "previous_hash": "...",
              "expected_hash": "...",
              "actual_hash": "..."
            }
          }
        }

    When the chain verifies, ``first_break_index`` and ``first_break``
    are both ``null``.
    """
    result = await service.verify_chain_with_diagnostic(
        tenant_id=user.tenant_id,
    )
    return {"success": True, "data": result}


@router.get("/audit/verify")
async def verify_audit_integrity(
    deep: bool = Query(
        False,
        description=(
            "When true, also recompute SHA-256 from each row's payload "
            "and compare to the stored entry_hash. Catches content "
            "tampering (e.g. result flipped post-write) that the "
            "structural chain walk misses. Slower (one sha256 per row) "
            "but is the only way to detect tamper that did not break "
            "the prev_hash links."
        ),
    ),
    user: CurrentUser = Depends(require_role("ADMIN")),
    service: AuditService = Depends(get_audit_service),
):
    """Verify the hash chain integrity of the audit trail.

    Requires ADMIN role. Walks the entire chain for the tenant
    and reports any breaks. With ``?deep=true`` also recomputes each
    row's payload hash and reports any content corruption -- distinct
    from structural breaks so the operator can tell a chain split apart
    from a row whose payload was modified after the fact.

    Response shape:

    .. code-block:: json

        {
          "success": true,
          "data": {
            "valid": true,
            "total_entries": 12,
            "first_broken_id": null,
            "first_corrupt_id": null
          }
        }

    ``first_corrupt_id`` is always ``null`` when ``deep=false`` is in
    effect (it cannot be detected without the recompute pass).
    """
    result = await service.verify_chain_integrity(
        tenant_id=user.tenant_id, deep=deep,
    )
    return {"success": True, "data": result}


# ── Session 11: permission state endpoint ──
#
# Frontend asks this endpoint on the Connections page to decide:
#   - Whether to dim per-tool Allow/Ask pills (UNLEASHED dims them)
#   - Which banner copy to show above the MCP Servers list
#
# Takes governance_mode + autopilot as query params because they are
# per-session runtime state; the frontend already holds them in the
# uiStore. Returns the resolver's UI hints directly so the frontend
# doesn't reimplement the logic.


@router.get("/permission-state")
async def get_permission_state(
    governance_mode: str = Query("BALANCED"),
    autopilot: bool = Query(False),
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Return UI state describing how per-tool permissions interact
    with the current governance mode + autopilot combination.

    Session 11: unifies the two permission layers that evolved
    separately (per-tool Allow/Ask/Block vs UNLEASHED/BALANCED/GOVERNED).
    """
    from app.core.constants import GovernanceMode
    from app.services.permission_resolver import explain_permission_ui_state

    try:
        mode = GovernanceMode(governance_mode)
    except ValueError:
        mode = GovernanceMode.BALANCED

    state = explain_permission_ui_state(mode, autopilot_active=autopilot)
    return {"success": True, "data": {**state, "governance_mode": mode.value, "autopilot": autopilot}}
