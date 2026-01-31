"""
Change Requests - Permissioned Self-Fix Module

Add-On 3: Strict permission workflow for Daena making changes.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/change-requests", tags=["Change Requests"])


# ═══════════════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════════════

class ChangeRequest(BaseModel):
    id: str
    title: str
    description: str
    scope: str  # auth, voice, cmp, agents, db, ui
    risk_score: int  # 1-10
    files_affected: List[str]
    diff_preview: str
    status: str  # pending, approved, rejected, implemented
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    approved_by: Optional[str] = None
    approval_type: Optional[str] = None  # once, category_24h


class ApprovalAction(BaseModel):
    action: str  # approve_once, approve_category, reject, simulate
    feedback: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════
# Storage
# ═══════════════════════════════════════════════════════════════════════

CHANGE_REQUESTS = {}
CATEGORY_APPROVALS = {}  # scope -> expiry_time


# ═══════════════════════════════════════════════════════════════════════
# Routes
# ═══════════════════════════════════════════════════════════════════════

@router.post("/create")
async def create_change_request(
    title: str = Body(...),
    description: str = Body(...),
    scope: str = Body(...),
    risk_score: int = Body(...),
    files_affected: List[str] = Body(...),
    diff_preview: str = Body(...)
):
    """Create a new change request (called by Daena)"""
    
    # Check if category is pre-approved
    expiry = CATEGORY_APPROVALS.get(scope)
    if expiry and expiry > datetime.utcnow():
        status = "approved"
        approval_type = "category_24h"
        logger.info(f"Auto-approving change {title} due to category approval")
    else:
        status = "pending"
        approval_type = None
    
    req_id = f"cr_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    
    request = ChangeRequest(
        id=req_id,
        title=title,
        description=description,
        scope=scope,
        risk_score=risk_score,
        files_affected=files_affected,
        diff_preview=diff_preview,
        status=status,
        expires_at=datetime.utcnow() + timedelta(hours=24),
        approval_type=approval_type
    )
    
    CHANGE_REQUESTS[req_id] = request
    
    return request


@router.get("")
async def list_change_requests(status: Optional[str] = None):
    """List change requests"""
    if status:
        return [r for r in CHANGE_REQUESTS.values() if r.status == status]
    return list(CHANGE_REQUESTS.values())


@router.post("/{req_id}/action")
async def handle_approval_action(req_id: str, action: ApprovalAction):
    """Handle founder action on a request"""
    req = CHANGE_REQUESTS.get(req_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    
    if action.action == "approve_once":
        req.status = "approved"
        req.approved_by = "founder"
        req.approval_type = "once"
        
        # Trigger implementation (mock)
        logger.info(f"Implementing change {req_id}")
        req.status = "implemented"
        
    elif action.action == "approve_category":
        req.status = "approved"
        req.approved_by = "founder"
        req.approval_type = "category_24h"
        
        # Set category approval
        CATEGORY_APPROVALS[req.scope] = datetime.utcnow() + timedelta(hours=24)
        
        req.status = "implemented"
        
    elif action.action == "reject":
        req.status = "rejected"
        # Log feedback
        logger.info(f"Change rejected: {action.feedback}")
        
    elif action.action == "simulate":
        # Trigger simulation
        return {
            "success": True,
            "simulation_id": f"sim_{req_id}",
            "status": "started"
        }
        
    return {"success": True, "request": req}


@router.get("/approvals/active")
async def get_active_approvals():
    """Get active category approvals"""
    now = datetime.utcnow()
    return {
        k: v for k, v in CATEGORY_APPROVALS.items() 
        if v > now
    }
