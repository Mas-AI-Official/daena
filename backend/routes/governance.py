"""
Governance API Routes — System-Wide Decision Control

Provides API endpoints for:
- Evaluating actions through governance
- Approving/rejecting pending actions
- Getting governance statistics
"""

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import logging

router = APIRouter(prefix="/api/v1/governance", tags=["governance"])
logger = logging.getLogger(__name__)


class ActionEvaluateRequest(BaseModel):
    action_type: str = Field(..., description="Type of action (file_write, package_install, etc.)")
    agent_id: str = Field(..., description="Agent requesting the action")
    description: str = Field(..., description="Description of the action")
    parameters: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None


class ApprovalRequest(BaseModel):
    decision_id: str = Field(..., description="Decision ID to approve/reject")
    approver_id: str = Field(default="founder", description="ID of approver")
    notes: str = Field(default="", description="Optional notes")


@router.post("/evaluate")
async def evaluate_action(request: ActionEvaluateRequest):
    """Evaluate an action through the governance loop."""
    try:
        from backend.services.governance_loop import get_governance_loop, ActionRequest, ActionType
        
        loop = get_governance_loop()
        
        # Map string to ActionType
        try:
            action_type = ActionType(request.action_type)
        except ValueError:
            action_type = ActionType.UNKNOWN
        
        action = ActionRequest(
            action_id=f"act_{hash(request.description) % 10000:04d}",
            action_type=action_type,
            agent_id=request.agent_id,
            description=request.description,
            parameters=request.parameters or {},
            context=request.context or {}
        )
        
        decision = loop.evaluate(action)
        
        return {
            "success": True,
            "decision": {
                "decision_id": decision.decision_id,
                "risk_level": decision.risk_level,
                "outcome": decision.outcome,
                "executed": decision.executed,
                "requires": decision.requires,
                "reason": decision.reason
            }
        }
    except Exception as e:
        logger.error(f"Governance evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/approve")
async def approve_action(request: ApprovalRequest):
    """Approve a pending action."""
    try:
        from backend.services.governance_loop import get_governance_loop
        
        loop = get_governance_loop()
        result = loop.approve(
            decision_id=request.decision_id,
            approver_id=request.approver_id,
            notes=request.notes
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="Decision not found or not pending")
        
        return {
            "success": True,
            "decision_id": request.decision_id,
            "status": "approved"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Governance approval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reject")
async def reject_action(request: ApprovalRequest):
    """Reject a pending action."""
    try:
        from backend.services.governance_loop import get_governance_loop
        
        loop = get_governance_loop()
        result = loop.reject(
            decision_id=request.decision_id,
            approver_id=request.approver_id,
            reason=request.notes
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="Decision not found or not pending")
        
        return {
            "success": True,
            "decision_id": request.decision_id,
            "status": "rejected"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Governance rejection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pending")
async def get_pending_approvals():
    """Get all pending approval requests."""
    try:
        from backend.services.governance_loop import get_governance_loop
        
        loop = get_governance_loop()
        pending = loop.get_pending()
        
        return {
            "success": True,
            "pending": pending,
            "count": len(pending)
        }
    except Exception as e:
        logger.error(f"Get pending failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_governance_stats():
    """Get governance loop statistics."""
    try:
        from backend.services.governance_loop import get_governance_loop
        
        loop = get_governance_loop()
        stats = loop.get_stats()
        
        return {
            "success": True,
            **stats
        }
    except Exception as e:
        logger.error(f"Get stats failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/toggle-autopilot")
async def toggle_autopilot(enabled: bool = Body(..., embed=True)):
    """Toggle autopilot mode on/off. Syncs to governance loop (chat) and brain DB (topbar/UI)."""
    try:
        from backend.services.governance_loop import get_governance_loop
        loop = get_governance_loop()
        loop.autopilot = enabled
        # Persist so GET /api/v1/brain/autopilot and topbar stay in sync
        try:
            from backend.routes.brain_status import _set_system_config, _AUTOPILOT_KEY
            _set_system_config(_AUTOPILOT_KEY, enabled, "boolean")
        except Exception:
            pass
        return {"success": True, "autopilot": enabled}
    except Exception as e:
        logger.error(f"Toggle autopilot failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
