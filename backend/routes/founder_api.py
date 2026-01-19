"""
Approvals & Learning API Routes for Founder Panel

Provides endpoints for:
1. Viewing pending tool approvals
2. Approving/rejecting tool executions
3. Viewing learnings (today's, pending, permanent)
4. Approving/rejecting learnings
"""

from fastapi import APIRouter, HTTPException, Body, Query
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/founder", tags=["founder-panel"])


# ==================== APPROVALS ====================

class ApprovalAction(BaseModel):
    """Request model for approval actions."""
    approved: bool
    notes: Optional[str] = None


@router.get("/approvals")
async def get_pending_approvals() -> Dict[str, Any]:
    """Get all pending tool approvals."""
    try:
        from backend.database import SessionLocal, PendingApproval
        
        db = SessionLocal()
        try:
            approvals = db.query(PendingApproval).filter(
                PendingApproval.status == "pending"
            ).order_by(
                PendingApproval.created_at.desc()
            ).all()
            
            return {
                "success": True,
                "count": len(approvals),
                "approvals": [
                    {
                        "id": a.id,
                        "approval_id": a.approval_id,
                        "executor_id": a.executor_id,
                        "executor_type": a.executor_type,
                        "tool_name": a.tool_name,
                        "action": a.action,
                        "args": a.args_json,
                        "impact_level": a.impact_level,
                        "created_at": a.created_at.isoformat() if a.created_at else None
                    }
                    for a in approvals
                ]
            }
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error getting pending approvals: {e}")
        return {"success": False, "error": str(e), "approvals": []}


@router.post("/approvals/{approval_id}")
async def process_approval(
    approval_id: str,
    action: ApprovalAction
) -> Dict[str, Any]:
    """Approve or reject a pending tool execution."""
    from datetime import datetime
    
    try:
        from backend.database import SessionLocal, PendingApproval
        
        db = SessionLocal()
        try:
            approval = db.query(PendingApproval).filter(
                PendingApproval.approval_id == approval_id
            ).first()
            
            if not approval:
                raise HTTPException(status_code=404, detail="Approval not found")
            
            approval.status = "approved" if action.approved else "rejected"
            approval.resolved_at = datetime.utcnow()
            approval.resolved_by = "founder"
            
            db.commit()
            
            # If approved, execute the tool
            if action.approved:
                from backend.services.unified_tool_executor import unified_executor
                result = await unified_executor.execute(
                    tool_name=approval.tool_name,
                    action=approval.action,
                    args=approval.args_json or {},
                    executor_id=approval.executor_id,
                    skip_approval=True  # Already approved
                )
                return {
                    "success": True,
                    "status": "approved",
                    "execution_result": result
                }
            else:
                return {
                    "success": True,
                    "status": "rejected",
                    "message": f"Approval {approval_id} rejected"
                }
                
        finally:
            db.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing approval: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== LEARNINGS ====================

class LearningAction(BaseModel):
    """Request model for learning actions."""
    approved: bool
    make_permanent: bool = True


@router.get("/learnings")
async def get_learnings(
    filter: str = Query("pending", description="Filter: pending, today, all, permanent")
) -> Dict[str, Any]:
    """Get learnings with filter."""
    try:
        from backend.services.learning_service import learning_service
        
        if filter == "pending":
            learnings = learning_service.get_pending_learnings(limit=50)
        elif filter == "today":
            learnings = learning_service.get_recent_learnings(hours=24, limit=50)
        elif filter == "permanent":
            learnings = learning_service.get_permanent_learnings()
        else:  # all
            learnings = learning_service.get_recent_learnings(hours=168, limit=100)  # 1 week
        
        # Get stats
        stats = learning_service.get_learning_stats()
        
        return {
            "success": True,
            "filter": filter,
            "count": len(learnings),
            "stats": stats,
            "learnings": learnings
        }
        
    except Exception as e:
        logger.error(f"Error getting learnings: {e}")
        return {"success": False, "error": str(e), "learnings": []}


@router.get("/learnings/stats")
async def get_learning_stats() -> Dict[str, Any]:
    """Get learning statistics for dashboard."""
    try:
        from backend.services.learning_service import learning_service
        stats = learning_service.get_learning_stats()
        return {"success": True, **stats}
    except Exception as e:
        logger.error(f"Error getting learning stats: {e}")
        return {"success": False, "error": str(e)}


@router.post("/learnings/{learning_id}")
async def process_learning(
    learning_id: int,
    action: LearningAction
) -> Dict[str, Any]:
    """Approve or reject a learning."""
    try:
        from backend.services.learning_service import learning_service
        
        if action.approved:
            success = learning_service.approve_learning(
                learning_id=learning_id,
                approved_by="founder",
                make_permanent=action.make_permanent
            )
            return {
                "success": success,
                "status": "approved",
                "permanent": action.make_permanent
            }
        else:
            success = learning_service.reject_learning(
                learning_id=learning_id,
                rejected_by="founder"
            )
            return {
                "success": success,
                "status": "rejected"
            }
            
    except Exception as e:
        logger.error(f"Error processing learning: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/learnings/approve-all")
async def approve_all_learnings(
    make_permanent: bool = Body(True)
) -> Dict[str, Any]:
    """Approve all pending learnings at once."""
    try:
        from backend.services.learning_service import learning_service
        
        pending = learning_service.get_pending_learnings(limit=100)
        approved_count = 0
        
        for learning in pending:
            if learning_service.approve_learning(
                learning_id=learning["id"],
                approved_by="founder",
                make_permanent=make_permanent
            ):
                approved_count += 1
        
        return {
            "success": True,
            "approved_count": approved_count,
            "total_pending": len(pending)
        }
        
    except Exception as e:
        logger.error(f"Error approving all learnings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== DASHBOARD ====================

@router.get("/dashboard")
async def get_founder_dashboard() -> Dict[str, Any]:
    """Get founder dashboard summary."""
    try:
        from backend.services.learning_service import learning_service
        from backend.database import SessionLocal, PendingApproval
        
        # Learning stats
        learning_stats = learning_service.get_learning_stats()
        
        # Pending approvals count
        db = SessionLocal()
        try:
            pending_approvals = db.query(PendingApproval).filter(
                PendingApproval.status == "pending"
            ).count()
        finally:
            db.close()
        
        return {
            "success": True,
            "pending_approvals": pending_approvals,
            "learning_stats": learning_stats,
            "alerts": [],
            "last_updated": "now"
        }
        
    except Exception as e:
        logger.error(f"Error getting dashboard: {e}")
        return {"success": False, "error": str(e)}
