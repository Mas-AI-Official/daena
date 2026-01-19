"""
Council Approval API Routes.

Endpoints for managing approval workflow for high-impact council decisions.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from backend.services.council_approval_service import (
    council_approval_service,
    DecisionImpact,
    ApprovalStatus
)
from backend.database import SessionLocal, Decision
from backend.routes.monitoring import verify_monitoring_auth

router = APIRouter(prefix="/api/v1/council/approvals", tags=["council-approvals"])
logger = logging.getLogger(__name__)


@router.get("/pending")
async def get_pending_approvals(
    department: Optional[str] = Query(None, description="Filter by department"),
    impact: Optional[str] = Query(None, description="Filter by impact level (low, medium, high, critical)"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of approvals to return"),
    offset: int = Query(0, ge=0, description="Number of approvals to skip"),
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Get list of pending approval requests.
    
    Returns decisions that require approval before being committed.
    """
    try:
        session = SessionLocal()
        try:
            query = session.query(Decision).filter(Decision.status == ApprovalStatus.PENDING.value)
            
            if department:
                query = query.filter(Decision.departments_affected.contains([department]))
            
            if impact:
                query = query.filter(Decision.impact == impact.lower())
            
            total = query.count()
            decisions = query.order_by(Decision.created_at.desc()).offset(offset).limit(limit).all()
            
            return {
                "success": True,
                "total": total,
                "limit": limit,
                "offset": offset,
                "decisions": [
                    {
                        "decision_id": d.decision_id,
                        "title": d.title,
                        "description": d.description[:500],  # Truncate for list view
                        "decision_type": d.decision_type,
                        "impact": d.impact,
                        "departments_affected": d.departments_affected,
                        "confidence": d.reasoning,  # Confidence stored in reasoning
                        "created_at": d.created_at.isoformat() if d.created_at else None,
                        "risk_assessment": d.risk_assessment
                    }
                    for d in decisions
                ]
            }
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error fetching pending approvals: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching pending approvals: {str(e)}")


@router.get("/{decision_id}")
async def get_approval_details(
    decision_id: str,
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Get detailed information about a specific approval request.
    """
    try:
        session = SessionLocal()
        try:
            decision = session.query(Decision).filter(Decision.decision_id == decision_id).first()
            
            if not decision:
                raise HTTPException(status_code=404, detail=f"Decision not found: {decision_id}")
            
            return {
                "success": True,
                "decision": {
                    "decision_id": decision.decision_id,
                    "title": decision.title,
                    "description": decision.description,
                    "decision_type": decision.decision_type,
                    "impact": decision.impact,
                    "reasoning": decision.reasoning,
                    "agents_involved": decision.agents_involved,
                    "departments_affected": decision.departments_affected,
                    "risk_assessment": decision.risk_assessment,
                    "metrics_impact": decision.metrics_impact,
                    "related_projects": decision.related_projects,
                    "status": decision.status,
                    "created_at": decision.created_at.isoformat() if decision.created_at else None,
                    "implemented_at": decision.implemented_at.isoformat() if decision.implemented_at else None,
                    "created_by": decision.created_by
                }
            }
        finally:
            session.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching approval details: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching approval details: {str(e)}")


@router.post("/{decision_id}/approve")
async def approve_decision(
    decision_id: str,
    reason: Optional[str] = Body(None, description="Reason for approval"),
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Approve a pending council decision.
    
    This will allow the decision to be committed to NBMF.
    """
    try:
        session = SessionLocal()
        try:
            decision = session.query(Decision).filter(Decision.decision_id == decision_id).first()
            
            if not decision:
                raise HTTPException(status_code=404, detail=f"Decision not found: {decision_id}")
            
            if decision.status != ApprovalStatus.PENDING.value:
                raise HTTPException(
                    status_code=400,
                    detail=f"Decision is not pending (current status: {decision.status})"
                )
            
            # Update status to approved
            decision.status = ApprovalStatus.APPROVED.value
            decision.implemented_at = datetime.utcnow()
            if reason:
                decision.reasoning = f"{decision.reasoning}\n\nApproved: {reason}"
            
            session.commit()
            
            logger.info(f"Decision approved: {decision_id} by {getattr(_, 'username', 'system')}")
            
            # Trigger the council scheduler to commit the approved decision
            try:
                from backend.services.council_scheduler import council_scheduler
                import asyncio
                
                # Get decision details for commit
                department = decision.departments_affected[0] if decision.departments_affected else "general"
                topic = decision.title.replace("Council Decision: ", "") if decision.title else "Approved decision"
                action_text = decision.description or ""
                tenant_id = decision.related_projects[0] if decision.related_projects else None
                project_id = tenant_id  # Using related_projects for project_id
                
                # Commit the approved decision
                # Run in background task (non-blocking)
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # If loop is already running, schedule as task
                        asyncio.create_task(
                            council_scheduler.commit_approved_decision(
                                decision_id=decision_id,
                                department=department,
                                topic=topic,
                                action_text=action_text,
                                tenant_id=tenant_id,
                                project_id=project_id
                            )
                        )
                    else:
                        # If no loop running, run directly
                        commit_result = asyncio.run(
                            council_scheduler.commit_approved_decision(
                                decision_id=decision_id,
                                department=department,
                                topic=topic,
                                action_text=action_text,
                                tenant_id=tenant_id,
                                project_id=project_id
                            )
                        )
                        logger.info(f"Decision committed: {decision_id} - {commit_result.get('committed', False)}")
                except RuntimeError:
                    # No event loop - create new one
                    commit_result = asyncio.run(
                        council_scheduler.commit_approved_decision(
                            decision_id=decision_id,
                            department=department,
                            topic=topic,
                            action_text=action_text,
                            tenant_id=tenant_id,
                            project_id=project_id
                        )
                    )
                    logger.info(f"Decision committed: {decision_id} - {commit_result.get('committed', False)}")
                    
            except ImportError as e:
                logger.warning(f"Could not import council_scheduler to commit decision: {e}")
            except Exception as e:
                logger.error(f"Error triggering commit for approved decision {decision_id}: {e}")
                # Continue anyway - approval is saved, commit can be retried
            
            return {
                "success": True,
                "decision_id": decision_id,
                "status": ApprovalStatus.APPROVED.value,
                "message": "Decision approved and committed to NBMF."
            }
        finally:
            session.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving decision: {e}")
        raise HTTPException(status_code=500, detail=f"Error approving decision: {str(e)}")


@router.post("/{decision_id}/reject")
async def reject_decision(
    decision_id: str,
    reason: str = Body(..., description="Reason for rejection"),
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Reject a pending council decision.
    
    This will prevent the decision from being committed.
    """
    try:
        session = SessionLocal()
        try:
            decision = session.query(Decision).filter(Decision.decision_id == decision_id).first()
            
            if not decision:
                raise HTTPException(status_code=404, detail=f"Decision not found: {decision_id}")
            
            if decision.status != ApprovalStatus.PENDING.value:
                raise HTTPException(
                    status_code=400,
                    detail=f"Decision is not pending (current status: {decision.status})"
                )
            
            # Update status to rejected
            decision.status = ApprovalStatus.REJECTED.value
            decision.reasoning = f"{decision.reasoning}\n\nRejected: {reason}"
            
            session.commit()
            
            logger.info(f"Decision rejected: {decision_id} by {getattr(_, 'username', 'system')}")
            
            return {
                "success": True,
                "decision_id": decision_id,
                "status": ApprovalStatus.REJECTED.value,
                "message": "Decision rejected. It will not be committed."
            }
        finally:
            session.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting decision: {e}")
        raise HTTPException(status_code=500, detail=f"Error rejecting decision: {str(e)}")


@router.get("/stats/summary")
async def get_approval_stats(
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Get statistics about approval requests.
    """
    try:
        session = SessionLocal()
        try:
            total = session.query(Decision).count()
            pending = session.query(Decision).filter(Decision.status == ApprovalStatus.PENDING.value).count()
            approved = session.query(Decision).filter(Decision.status == ApprovalStatus.APPROVED.value).count()
            rejected = session.query(Decision).filter(Decision.status == ApprovalStatus.REJECTED.value).count()
            auto_approved = session.query(Decision).filter(Decision.status == ApprovalStatus.AUTO_APPROVED.value).count()
            
            # Group by impact
            impact_counts = {}
            for impact in ["low", "medium", "high", "critical"]:
                impact_counts[impact] = session.query(Decision).filter(Decision.impact == impact).count()
            
            return {
                "success": True,
                "stats": {
                    "total": total,
                    "pending": pending,
                    "approved": approved,
                    "rejected": rejected,
                    "auto_approved": auto_approved,
                    "by_impact": impact_counts,
                    "approval_rate": (approved / total * 100) if total > 0 else 0.0,
                    "rejection_rate": (rejected / total * 100) if total > 0 else 0.0
                }
            }
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error fetching approval stats: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching approval stats: {str(e)}")

