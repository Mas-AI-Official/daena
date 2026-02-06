from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
from datetime import datetime
from backend.services.governance_loop import GovernanceLoop
from backend.services.self_healing import get_self_healing_service

router = APIRouter(prefix="/api/v1/change-requests", tags=["governance"])

@router.get("/")
async def get_change_requests() -> Dict[str, Any]:
    """List all proposed system self-fixes and upgrades awaiting approval from Governance."""
    gov = GovernanceLoop.get_instance()
    pending = gov.get_pending()
    
    # Filter for file writes or self-fixes
    change_requests = []
    for p in pending:
        # Check if it looks like a self-fix or a file change
        if p.get("action_type") == "file_write" or p.get("source") == "governance":
            params = p.get("parameters", {})
            
            change_requests.append({
                "id": p["decision_id"],
                "proposer": p["agent_id"],
                "target": params.get("path") or p["description"].split(": ")[-1] if ":" in p["description"] else p["description"],
                "change_type": "SELF_HEAL" if "Self-Fix" in p["description"] or params.get("is_self_fix") else "SYSTEM_UPGRADE",
                "description": params.get("rationale") or p["description"],
                "status": "PENDING_FOUNDER",
                "timestamp": p["requested_at"],
                "score": params.get("risk_score", 85), # Mock score for UI
                "diff": params.get("content") or params.get("proposed_code") # The code being written
            })
            
    return {
        "success": True,
        "count": len(change_requests),
        "requests": change_requests
    }

@router.post("/{request_id}/approve")
async def approve_change(request_id: str) -> Dict[str, Any]:
    """Founder approval for a proposed self-fix. Actually applies the fix."""
    gov = GovernanceLoop.get_instance()
    success = gov.approve(request_id, "founder", "Approved via change-requests API")
    
    if not success:
        raise HTTPException(status_code=404, detail="Request not found or already processed")
    
    # Actually trigger the self-healing application
    healing = get_self_healing_service()
    result = await healing.apply_fix(request_id)
    
    return {
        "success": result.get("status") == "success",
        "request_id": request_id,
        "action": "APPROVED",
        "message": result.get("message", "Approved but application failed")
    }

@router.post("/{request_id}/reject")
async def reject_change(request_id: str, payload: Dict[str, str] = None) -> Dict[str, Any]:
    """Founder rejection of a proposed self-fix."""
    reason = payload.get("reason", "Incomplete analysis") if payload else "Incomplete analysis"
    gov = GovernanceLoop.get_instance()
    success = gov.reject(request_id, "founder", reason)
    
    if not success:
        raise HTTPException(status_code=404, detail="Request not found or already processed")
        
    return {
        "success": True,
        "request_id": request_id,
        "action": "REJECTED",
        "reason": reason
    }
