"""
DaenaBot Tools API: queue, approve, reject, history, connection status.
Governed OpenClaw integration (DaenaBot Hands).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config.branding import get_daena_bot_display_name
from backend.services.tool_request_store import (
    list_pending,
    list_history,
    get_request,
    update_status,
)
from backend.services import tool_broker

router = APIRouter(prefix="/api/v1/tools", tags=["daena-bot-tools"])


class ApproveBody(BaseModel):
    approver: str = "founder"
    notes: Optional[str] = None


class RejectBody(BaseModel):
    reason: str = "Founder rejected"
    rejector: str = "founder"


def _gateway_status() -> Dict[str, Any]:
    """Return connection status for the OpenClaw/DaenaBot Hands gateway."""
    try:
        from backend.integrations.openclaw_gateway_client import get_openclaw_client
        client = get_openclaw_client()
        return {
            "connected": client.is_connected,
            "authenticated": getattr(client, "is_authenticated", False),
            "display_name": get_daena_bot_display_name(),
        }
    except Exception:
        return {
            "connected": False,
            "authenticated": False,
            "display_name": get_daena_bot_display_name(),
        }


@router.get("/status")
async def get_status():
    """Connection status of DaenaBot Hands (OpenClaw Gateway)."""
    return _gateway_status()


@router.get("/queue")
async def get_queue():
    """Pending tool requests awaiting founder approval."""
    pending = list_pending()
    return {"pending": pending, "count": len(pending)}


@router.post("/{request_id}/approve")
async def approve_request(request_id: str, body: ApproveBody):
    """Approve a pending tool request and execute via gateway."""
    req = get_request(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.get("status") != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Request is not pending (status={req.get('status')})",
        )
    result = await tool_broker.execute_approved_request(request_id)
    return {"request_id": request_id, "status": "approved", "result": result}


@router.post("/{request_id}/reject")
async def reject_request(request_id: str, body: RejectBody):
    """Reject a pending tool request."""
    req = get_request(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.get("status") != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Request is not pending (status={req.get('status')})",
        )
    update_status(
        request_id,
        "rejected",
        {"rejected_by": body.rejector, "reason": body.reason},
    )
    return {"request_id": request_id, "status": "rejected"}


@router.get("/history")
async def get_tools_history(limit: int = 50):
    """Recent tool requests (all statuses)."""
    requests = list_history(limit=limit)
    return {"history": requests, "display_name": get_daena_bot_display_name()}
