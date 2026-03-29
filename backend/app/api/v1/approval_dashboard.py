"""Approval Dashboard endpoints: pending items, approve, reject, summary.

Provides the backend API for the Approval Dashboard frontend panel.
Users see rejected actions, make decisions, and view audit trail.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import CurrentUser, get_current_user
from app.core.logging import get_logger
from app.services.approval_queue import ApprovalQueue

logger = get_logger(__name__)

router = APIRouter()

# Singleton approval queue
_approval_queue: ApprovalQueue | None = None


def get_approval_queue() -> ApprovalQueue:
    """Get or create the singleton ApprovalQueue."""
    global _approval_queue
    if _approval_queue is None:
        _approval_queue = ApprovalQueue()
    return _approval_queue


# ── Request models ──


class ApprovalDecisionBody(BaseModel):
    """Request body for approve/reject/escalate actions."""
    item_id: str


# ── Endpoints ──


@router.get("/pending")
async def get_pending(
    session_id: str | None = None,
    user: CurrentUser = Depends(get_current_user),
):
    """Get all pending approval items."""
    queue = get_approval_queue()
    items = queue.get_pending(session_id=session_id)
    return {
        "items": [item.to_dict() for item in items],
        "count": len(items),
    }


@router.get("/decided")
async def get_decided(
    session_id: str | None = None,
    limit: int = 50,
    user: CurrentUser = Depends(get_current_user),
):
    """Get decided items (approved, rejected, escalated)."""
    queue = get_approval_queue()
    items = queue.get_decided(session_id=session_id, limit=limit)
    return {
        "items": [item.to_dict() for item in items],
        "count": len(items),
    }


@router.get("/summary")
async def get_summary(
    user: CurrentUser = Depends(get_current_user),
):
    """Get approval queue summary counts."""
    queue = get_approval_queue()
    return queue.get_summary()


@router.get("/item/{item_id}")
async def get_item(
    item_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Get a specific approval item by ID."""
    queue = get_approval_queue()
    item = queue.get_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item.to_dict()


@router.post("/approve")
async def approve_item(
    body: ApprovalDecisionBody,
    user: CurrentUser = Depends(get_current_user),
):
    """Approve (override) a rejected action."""
    queue = get_approval_queue()
    item = await queue.approve(body.item_id, str(user.id))
    if not item:
        raise HTTPException(
            status_code=404,
            detail="Item not found or already decided",
        )
    return {"success": True, "item": item.to_dict()}


@router.post("/reject")
async def reject_item(
    body: ApprovalDecisionBody,
    user: CurrentUser = Depends(get_current_user),
):
    """Confirm rejection of an action."""
    queue = get_approval_queue()
    item = await queue.reject(body.item_id, str(user.id))
    if not item:
        raise HTTPException(
            status_code=404,
            detail="Item not found or already decided",
        )
    return {"success": True, "item": item.to_dict()}


@router.post("/escalate")
async def escalate_item(
    body: ApprovalDecisionBody,
    user: CurrentUser = Depends(get_current_user),
):
    """Escalate an item for higher authority review."""
    queue = get_approval_queue()
    item = await queue.escalate(body.item_id, str(user.id))
    if not item:
        raise HTTPException(
            status_code=404,
            detail="Item not found or already decided",
        )
    return {"success": True, "item": item.to_dict()}
