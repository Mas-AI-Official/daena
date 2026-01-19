"""
SEC-Loop API Routes.

Endpoints for running and managing SEC-Loop cycles.
"""

from fastapi import APIRouter, HTTPException, Depends, Body, Query
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
import logging

from self_evolve.sec_loop import sec_loop, SECLoopResult
from self_evolve.rollback import RollbackManager
from backend.routes.monitoring import verify_monitoring_auth

router = APIRouter(prefix="/api/v1/self-evolve", tags=["sec-loop"])
logger = logging.getLogger(__name__)

rollback_manager = RollbackManager()


class SECLoopRequest(BaseModel):
    """Request model for SEC-Loop cycle."""
    department: str
    tenant_id: Optional[str] = None
    project_id: Optional[str] = None
    cell_id: Optional[str] = None


@router.post("/run")
async def run_sec_loop(
    request: SECLoopRequest = Body(...),
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Run a SEC-Loop cycle.
    
    Requires authentication and ABAC compliance.
    """
    from backend.config.settings import settings
    if not settings.training_enabled:
        raise HTTPException(status_code=403, detail="Self-evolution is disabled by configuration (DAENA_TRAINING_ENABLED=0)")

    try:
        result = sec_loop.run_cycle(
            department=request.department,
            tenant_id=request.tenant_id,
            project_id=request.project_id,
            cell_id=request.cell_id
        )
        
        return {
            "success": result.success,
            "cycle_id": result.cycle_id,
            "department": result.department,
            "candidates_selected": result.candidates_selected,
            "abstracts_created": result.abstracts_created,
            "abstracts_evaluated": result.abstracts_evaluated,
            "decisions_made": result.decisions_made,
            "abstracts_promoted": result.abstracts_promoted,
            "abstracts_rejected": result.abstracts_rejected,
            "duration_sec": result.duration_sec,
            "errors": result.errors
        }
    
    except Exception as e:
        logger.error(f"Error running SEC-Loop: {e}")
        raise HTTPException(status_code=500, detail=f"Error running SEC-Loop: {str(e)}")


@router.get("/status")
async def get_sec_loop_status(
    department: Optional[str] = Query(None, description="Filter by department"),
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Get current SEC-Loop status.
    
    Returns pending decisions and recent cycle results.
    """
    try:
        from self_evolve.policy import CouncilPolicy
        policy = CouncilPolicy()
        
        pending_decisions = policy.get_pending_decisions()
        if department:
            pending_decisions = [d for d in pending_decisions if d.department == department]
        
        return {
            "success": True,
            "pending_decisions": len(pending_decisions),
            "decisions": [
                {
                    "decision_id": d.decision_id,
                    "abstract_id": d.abstract_id,
                    "status": d.status.value,
                    "department": d.department,
                    "quorum_reached": d.quorum_reached,
                    "votes_count": len(d.votes)
                }
                for d in pending_decisions
            ]
        }
    
    except Exception as e:
        logger.error(f"Error getting SEC-Loop status: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting status: {str(e)}")


@router.post("/rollback")
async def rollback_promotions(
    n: int = Body(..., description="Number of promotions to rollback"),
    department: Optional[str] = Body(None, description="Optional department filter"),
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Rollback last N promotions.
    
    Requires authentication and ABAC compliance.
    """
    try:
        result = rollback_manager.rollback_last_n(n, department)
        
        return {
            "success": result.success,
            "rollback_id": result.rollback_id,
            "reverted_count": result.reverted_count,
            "reverted_abstracts": result.reverted_abstracts,
            "error": result.error
        }
    
    except Exception as e:
        logger.error(f"Error rolling back promotions: {e}")
        raise HTTPException(status_code=500, detail=f"Error rolling back: {str(e)}")

