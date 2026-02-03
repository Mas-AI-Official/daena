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


@router.get("/ping-hands")
async def ping_hands():
    """
    Test Hands connection: ping gateway (connect with short timeout).
    For UI "Test Hands Connection" button; returns connected, authenticated, error.
    """
    import asyncio
    try:
        from backend.integrations.openclaw_gateway_client import get_openclaw_client, _default_token
        token = _default_token()
        client = get_openclaw_client()
        client.timeout_sec = 3.0
        connected = await asyncio.wait_for(client.connect(), timeout=3.0)
        auth = getattr(client, "is_authenticated", False) or (connected and not (token and str(token).strip()))
        try:
            await client.disconnect()
        except Exception:
            pass
        return {
            "success": True,
            "connected": bool(connected),
            "authenticated": auth,
            "token_present": bool(token and str(token).strip()),
            "error": None,
            "display_name": get_daena_bot_display_name(),
        }
    except asyncio.TimeoutError:
        try:
            from backend.integrations.openclaw_gateway_client import _default_token
            tok = _default_token()
        except Exception:
            tok = None
        return {
            "success": False,
            "connected": False,
            "authenticated": False,
            "token_present": bool(tok and str(tok).strip()),
            "error": "timeout",
            "display_name": get_daena_bot_display_name(),
        }
    except Exception as e:
        return {
            "success": False,
            "connected": False,
            "authenticated": False,
            "token_present": False,
            "error": str(e),
            "display_name": get_daena_bot_display_name(),
        }


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
    try:
        from backend.routes.audit import log_audit_entry
        log_audit_entry(
            actor=body.approver,
            resource="tool_request",
            action="approve",
            allowed=True,
            reason=body.notes or "approved",
            context={"request_id": request_id, "risk_level": req.get("risk_level")},
        )
    except Exception:
        pass
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
    try:
        from backend.routes.audit import log_audit_entry
        log_audit_entry(
            actor=body.rejector,
            resource="tool_request",
            action="reject",
            allowed=False,
            reason=body.reason,
            context={"request_id": request_id, "risk_level": req.get("risk_level")},
        )
    except Exception:
        pass
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


class SubmitActionBody(BaseModel):
    action_type: str
    parameters: Dict[str, Any] = {}
    requested_by: str = "founder"


@router.post("/submit")
async def submit_tool_request(body: SubmitActionBody):
    """
    Submit a tool request (e.g. from Control Pannel 'Test Action').
    Goes through broker: might be executed immediately (low risk) or queued (approval).
    """
    action = {"action_type": body.action_type, "parameters": body.parameters}
    
    # Use async broker request
    try:
        status, result = await tool_broker.async_broker_request(
            action=action,
            requested_by=body.requested_by
        )
        return {
            "status": status,
            "result": result,
            "message": result.get("message") if result else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
