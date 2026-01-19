"""
Learning Routes
Handles approval/rejection of Daena's learning items by Founder
"""
from fastapi import APIRouter, HTTPException, Body
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
import logging

from backend.database import SessionLocal, LearningLog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/learning", tags=["learning"])


class ApprovalRequest(BaseModel):
    notes: Optional[str] = None


@router.get("/pending")
async def get_pending_learning() -> Dict[str, Any]:
    """Get all pending learning items that require founder approval."""
    db = SessionLocal()
    try:
        # Query unapproved learning items
        items = db.query(LearningLog).filter(
            LearningLog.approved == False,
            LearningLog.permanent == False
        ).order_by(LearningLog.learned_at.desc()).limit(50).all()
        
        return {
            "success": True,
            "learning_items": [
                {
                    "id": item.id,
                    "learned_at": item.learned_at.isoformat() if item.learned_at else None,
                    "learned_by": item.learned_by,
                    "category": item.category,
                    "summary": item.summary,
                    "details": item.details_json,
                    "approved": item.approved
                }
                for item in items
            ],
            "total": len(items)
        }
    except Exception as e:
        logger.error(f"Error getting pending learning: {e}")
        return {
            "success": True,
            "learning_items": [],
            "total": 0,
            "message": "No pending items"
        }
    finally:
        db.close()


@router.post("/{learning_id}/approve")
async def approve_learning(learning_id: int, request: ApprovalRequest = Body(default=ApprovalRequest())) -> Dict[str, Any]:
    """Approve a learning item - makes it permanent."""
    from datetime import datetime
    
    db = SessionLocal()
    try:
        item = db.query(LearningLog).filter(LearningLog.id == learning_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Learning item not found")
        
        item.approved = True
        item.permanent = True
        item.approved_at = datetime.now()
        item.approved_by = "founder"
        db.commit()
        
        logger.info(f"Learning item {learning_id} approved by founder")
        
        return {
            "success": True,
            "message": "Learning approved and made permanent",
            "learning_id": learning_id
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error approving learning: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post("/{learning_id}/reject")
async def reject_learning(learning_id: int) -> Dict[str, Any]:
    """Reject a learning item - deletes it."""
    db = SessionLocal()
    try:
        item = db.query(LearningLog).filter(LearningLog.id == learning_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Learning item not found")
        
        db.delete(item)
        db.commit()
        
        logger.info(f"Learning item {learning_id} rejected and deleted")
        
        return {
            "success": True,
            "message": "Learning rejected and removed",
            "learning_id": learning_id
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error rejecting learning: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post("/approve-all")
async def approve_all_learning() -> Dict[str, Any]:
    """Approve all pending learning items."""
    from datetime import datetime
    
    db = SessionLocal()
    try:
        count = db.query(LearningLog).filter(
            LearningLog.approved == False
        ).update({
            "approved": True,
            "permanent": True,
            "approved_at": datetime.now(),
            "approved_by": "founder"
        })
        db.commit()
        
        logger.info(f"Approved all {count} pending learning items")
        
        return {
            "success": True,
            "message": f"Approved {count} learning items",
            "count": count
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error approving all learning: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post("/reject-all")
async def reject_all_learning() -> Dict[str, Any]:
    """Reject all pending learning items."""
    db = SessionLocal()
    try:
        count = db.query(LearningLog).filter(
            LearningLog.approved == False
        ).delete()
        db.commit()
        
        logger.info(f"Rejected and deleted all {count} pending learning items")
        
        return {
            "success": True,
            "message": f"Rejected {count} learning items",
            "count": count
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error rejecting all learning: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/history")
async def get_learning_history(limit: int = 50) -> Dict[str, Any]:
    """Get approved learning history."""
    db = SessionLocal()
    try:
        items = db.query(LearningLog).filter(
            LearningLog.approved == True
        ).order_by(LearningLog.learned_at.desc()).limit(limit).all()
        
        return {
            "success": True,
            "learning_items": [
                {
                    "id": item.id,
                    "learned_at": item.learned_at.isoformat() if item.learned_at else None,
                    "learned_by": item.learned_by,
                    "category": item.category,
                    "summary": item.summary,
                    "approved_at": item.approved_at.isoformat() if item.approved_at else None,
                    "approved_by": item.approved_by
                }
                for item in items
            ],
            "total": len(items)
        }
    except Exception as e:
        logger.error(f"Error getting learning history: {e}")
        return {"success": True, "learning_items": [], "total": 0}
    finally:
        db.close()
