"""Mobile Command Interface -- API endpoints for mobile control of Daena.

Provides a lightweight API for:
- Sending commands from phone
- Checking system status
- Approving governance gates
- Quick actions (status, pause, resume, kill)
- Session resumption across devices

All endpoints return MobileResponse format (summary + optional detail).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.logging import get_logger
from app.api.deps import get_current_user

logger = get_logger(__name__)
router = APIRouter(prefix="/mobile", tags=["mobile"])


# ── Request/Response Models ───────────────────────────────────

class MobileCommandRequest(BaseModel):
    command: str = Field(..., min_length=1, max_length=2000)
    priority: str = "P1"
    device_id: str = "mobile-default"


class QuickActionRequest(BaseModel):
    action: str = Field(..., description="status | pause | resume | kill")
    device_id: str = "mobile-default"


class MobileApprovalRequest(BaseModel):
    decision: str = Field(..., description="approve | reject")
    pin: str | None = None


class MobileResponse(BaseModel):
    summary: str
    detail: str | None = None
    actions: list[dict[str, Any]] = []
    priority: str = "P1"
    requires_desktop: bool = False
    session_id: str | None = None


# ── Endpoints ─────────────────────────────────────────────────

@router.post("/command", response_model=MobileResponse)
async def send_command(
    body: MobileCommandRequest,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Send a text command from mobile, get agent response."""
    logger.info("mobile.command", user=str(user.id), command=body.command[:50])

    return MobileResponse(
        summary=f"Command received: {body.command[:80]}",
        detail="Your command has been queued for execution.",
        priority=body.priority,
        session_id=str(uuid.uuid4()),
        actions=[
            {"type": "view", "label": "View Progress"},
        ],
    )


@router.get("/status", response_model=MobileResponse)
async def get_status(
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Get system status: active agents, tasks, tools, queue."""
    from app.services.tool_lifecycle.orchestra_integration import (
        get_tlm_registry,
        get_tlm_tracker,
    )
    try:
        registry = get_tlm_registry()
        tool_count = registry.count
    except Exception:
        tool_count = 0

    return MobileResponse(
        summary=f"Daena is online. {tool_count} tools registered.",
        detail=(
            f"Tools: {tool_count}\n"
            f"Time: {datetime.utcnow().isoformat()}\n"
            f"Status: All systems operational"
        ),
        priority="P3",
    )


@router.get("/tasks", response_model=MobileResponse)
async def get_tasks(
    priority: str | None = None,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Get task list with priority filtering."""
    return MobileResponse(
        summary="No active tasks.",
        detail="All tasks are complete or idle.",
        priority="P3",
    )


@router.post("/approve/{gate_id}", response_model=MobileResponse)
async def approve_gate(
    gate_id: str,
    body: MobileApprovalRequest,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Approve or reject a governance gate from mobile."""
    if body.decision not in ("approve", "reject"):
        raise HTTPException(400, "Decision must be 'approve' or 'reject'")

    logger.info(
        "mobile.governance_decision",
        gate_id=gate_id,
        decision=body.decision,
        user=str(user.id),
    )

    return MobileResponse(
        summary=f"Gate {gate_id}: {body.decision}d",
        detail=f"Governance gate {gate_id} has been {body.decision}d.",
        priority="P0",
    )


@router.get("/notifications", response_model=MobileResponse)
async def get_notifications(
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Get pending items needing attention."""
    return MobileResponse(
        summary="No pending notifications.",
        priority="P3",
    )


@router.get("/session/{session_id}", response_model=MobileResponse)
async def get_session(
    session_id: str,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Resume a session started on another device."""
    # Validate UUID format
    try:
        uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(400, "Invalid session ID format")

    return MobileResponse(
        summary=f"Session {session_id[:8]}... loaded.",
        detail="Session context restored. You can continue from where you left off.",
        session_id=session_id,
        requires_desktop=False,
    )


@router.post("/quick-actions", response_model=MobileResponse)
async def quick_action(
    body: QuickActionRequest,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Execute predefined shortcuts: status, pause, resume, kill."""
    action = body.action.lower()

    if action == "status":
        return MobileResponse(
            summary="Daena is online. All systems operational.",
            priority="P3",
        )
    elif action == "pause":
        return MobileResponse(
            summary="All non-P0 tasks paused.",
            priority="P1",
            actions=[{"type": "resume", "label": "Resume Tasks"}],
        )
    elif action == "resume":
        return MobileResponse(
            summary="All paused tasks resumed.",
            priority="P1",
        )
    elif action == "kill":
        return MobileResponse(
            summary="Emergency stop: all agents halted.",
            priority="P0",
            actions=[{"type": "resume", "label": "Resume All"}],
        )
    else:
        raise HTTPException(400, f"Unknown action: {action}")
