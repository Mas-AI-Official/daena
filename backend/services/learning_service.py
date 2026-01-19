"""
Learning Service for Daena AI VP

Tracks what Daena and agents learn from:
- Tool usage patterns
- User preferences
- Successful interactions
- Error corrections

Learnings appear in Founder Panel for review and approval.
Once approved, learnings become permanent and influence future behavior.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json

from backend.database import SessionLocal, LearningLog

logger = logging.getLogger(__name__)


class LearningCategory:
    TOOL_USAGE = "tool_usage"  # Learned how to use a tool
    PATTERN = "pattern"  # Learned a pattern/workflow
    PREFERENCE = "preference"  # Learned user preference
    KNOWLEDGE = "knowledge"  # Learned new knowledge
    CORRECTION = "correction"  # Learned from a correction
    OPTIMIZATION = "optimization"  # Learned an optimization


class LearningService:
    """
    Service for tracking and managing Daena's learnings.
    
    Learnings are logged when:
    - A tool is successfully used (can reuse pattern)
    - User provides feedback or correction
    - A new pattern is detected
    - Knowledge is extracted from interactions
    """
    
    def __init__(self):
        self.auto_approve_categories = []  # Categories that don't need approval
        self.max_pending_learnings = 100  # Max pending before cleanup
    
    def log_learning(
        self,
        learned_by: str,
        category: str,
        summary: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Optional[int]:
        """
        Log a new learning.
        
        Args:
            learned_by: Who learned (daena, agent_id, etc.)
            category: Learning category
            summary: Human-readable summary
            details: Full details dict
            
        Returns:
            Learning ID or None if failed
        """
        try:
            db = SessionLocal()
            try:
                learning = LearningLog(
                    learned_by=learned_by,
                    category=category,
                    summary=summary,
                    details_json=details or {},
                    approved=category in self.auto_approve_categories,
                    permanent=False
                )
                db.add(learning)
                db.commit()
                db.refresh(learning)
                
                logger.info(f"Learning logged: [{category}] {summary[:50]}... (ID: {learning.id})")
                return learning.id
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to log learning: {e}")
            return None
    
    def log_tool_learning(
        self,
        learned_by: str,
        tool_name: str,
        action: str,
        args: Dict[str, Any],
        result: Dict[str, Any]
    ) -> Optional[int]:
        """Log a tool usage learning."""
        if not result.get("success"):
            return None  # Don't learn from failures
        
        summary = f"Learned to use {tool_name}.{action}"
        details = {
            "tool_name": tool_name,
            "action": action,
            "args_template": args,
            "result_summary": str(result)[:200]
        }
        
        return self.log_learning(
            learned_by=learned_by,
            category=LearningCategory.TOOL_USAGE,
            summary=summary,
            details=details
        )
    
    def log_correction(
        self,
        learned_by: str,
        original_action: str,
        corrected_action: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[int]:
        """Log a correction learning."""
        summary = f"Learned correction: '{original_action[:30]}...' → '{corrected_action[:30]}...'"
        details = {
            "original": original_action,
            "corrected": corrected_action,
            "context": context or {}
        }
        
        return self.log_learning(
            learned_by=learned_by,
            category=LearningCategory.CORRECTION,
            summary=summary,
            details=details
        )
    
    def get_pending_learnings(
        self,
        limit: int = 20,
        learned_by: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get pending learnings for approval."""
        try:
            db = SessionLocal()
            try:
                query = db.query(LearningLog).filter(
                    LearningLog.approved == False
                )
                
                if learned_by:
                    query = query.filter(LearningLog.learned_by == learned_by)
                
                learnings = query.order_by(
                    LearningLog.learned_at.desc()
                ).limit(limit).all()
                
                return [
                    {
                        "id": l.id,
                        "learned_at": l.learned_at.isoformat() if l.learned_at else None,
                        "learned_by": l.learned_by,
                        "category": l.category,
                        "summary": l.summary,
                        "details": l.details_json,
                        "approved": l.approved,
                        "permanent": l.permanent
                    }
                    for l in learnings
                ]
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to get pending learnings: {e}")
            return []
    
    def get_recent_learnings(
        self,
        hours: int = 24,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get all learnings from the last N hours."""
        try:
            db = SessionLocal()
            try:
                since = datetime.utcnow() - timedelta(hours=hours)
                
                learnings = db.query(LearningLog).filter(
                    LearningLog.learned_at >= since
                ).order_by(
                    LearningLog.learned_at.desc()
                ).limit(limit).all()
                
                return [
                    {
                        "id": l.id,
                        "learned_at": l.learned_at.isoformat() if l.learned_at else None,
                        "learned_by": l.learned_by,
                        "category": l.category,
                        "summary": l.summary,
                        "approved": l.approved,
                        "permanent": l.permanent
                    }
                    for l in learnings
                ]
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to get recent learnings: {e}")
            return []
    
    def approve_learning(
        self,
        learning_id: int,
        approved_by: str = "founder",
        make_permanent: bool = True
    ) -> bool:
        """Approve a learning to make it permanent."""
        try:
            db = SessionLocal()
            try:
                learning = db.query(LearningLog).filter(
                    LearningLog.id == learning_id
                ).first()
                
                if not learning:
                    logger.warning(f"Learning not found: {learning_id}")
                    return False
                
                learning.approved = True
                learning.approved_at = datetime.utcnow()
                learning.approved_by = approved_by
                learning.permanent = make_permanent
                
                db.commit()
                logger.info(f"Learning approved: {learning_id} by {approved_by}")
                return True
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to approve learning: {e}")
            return False
    
    def reject_learning(
        self,
        learning_id: int,
        rejected_by: str = "founder"
    ) -> bool:
        """Reject and delete a learning."""
        try:
            db = SessionLocal()
            try:
                learning = db.query(LearningLog).filter(
                    LearningLog.id == learning_id
                ).first()
                
                if not learning:
                    logger.warning(f"Learning not found: {learning_id}")
                    return False
                
                db.delete(learning)
                db.commit()
                logger.info(f"Learning rejected: {learning_id} by {rejected_by}")
                return True
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to reject learning: {e}")
            return False
    
    def get_permanent_learnings(
        self,
        category: Optional[str] = None,
        learned_by: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all permanent learnings for use in behavior."""
        try:
            db = SessionLocal()
            try:
                query = db.query(LearningLog).filter(
                    LearningLog.permanent == True
                )
                
                if category:
                    query = query.filter(LearningLog.category == category)
                if learned_by:
                    query = query.filter(LearningLog.learned_by == learned_by)
                
                learnings = query.all()
                
                return [
                    {
                        "id": l.id,
                        "category": l.category,
                        "summary": l.summary,
                        "details": l.details_json
                    }
                    for l in learnings
                ]
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to get permanent learnings: {e}")
            return []
    
    def get_learning_stats(self) -> Dict[str, Any]:
        """Get learning statistics for dashboard."""
        try:
            db = SessionLocal()
            try:
                total = db.query(LearningLog).count()
                pending = db.query(LearningLog).filter(
                    LearningLog.approved == False
                ).count()
                approved = db.query(LearningLog).filter(
                    LearningLog.approved == True
                ).count()
                permanent = db.query(LearningLog).filter(
                    LearningLog.permanent == True
                ).count()
                
                # Count by category
                categories = {}
                for category in [LearningCategory.TOOL_USAGE, LearningCategory.PATTERN,
                                 LearningCategory.PREFERENCE, LearningCategory.KNOWLEDGE,
                                 LearningCategory.CORRECTION, LearningCategory.OPTIMIZATION]:
                    categories[category] = db.query(LearningLog).filter(
                        LearningLog.category == category
                    ).count()
                
                # Today's learnings
                today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                today_count = db.query(LearningLog).filter(
                    LearningLog.learned_at >= today
                ).count()
                
                return {
                    "total": total,
                    "pending": pending,
                    "approved": approved,
                    "permanent": permanent,
                    "today": today_count,
                    "by_category": categories
                }
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to get learning stats: {e}")
            return {"error": str(e)}


# Global instance
learning_service = LearningService()
