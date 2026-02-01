"""
Outcome Tracker API Routes

Provides endpoints for:
- Tracking decision outcomes
- Recording results
- Viewing expert calibration scores
- Getting insights and statistics
"""

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import logging

from backend.services.outcome_tracker import (
    get_outcome_tracker,
    OutcomeStatus,
    DecisionCategory
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/outcomes", tags=["outcomes"])


# ============================================
# Pydantic Models
# ============================================

class TrackDecisionRequest(BaseModel):
    outcome_id: str = Field(..., description="Unique ID for this decision")
    decision_type: str = Field(..., description="Type of decision")
    category: str = Field(default="general", description="Category of decision")
    recommendation: str = Field(..., description="What was recommended")
    agent_id: str = Field(default="daena", description="Which agent made it")
    council_result: Optional[Dict[str, Any]] = Field(default=None, description="Council vote if any")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")


class RecordOutcomeRequest(BaseModel):
    status: str = Field(..., description="Outcome status: successful, failed, partial, unknown")
    notes: str = Field(default="", description="Notes about the outcome")
    feedback_score: Optional[float] = Field(default=None, ge=1.0, le=5.0, description="User rating 1-5")


# ============================================
# Track Decision Endpoints
# ============================================

@router.post("/track")
async def track_decision(request: TrackDecisionRequest) -> Dict[str, Any]:
    """
    Start tracking a decision for its future outcome.
    
    Call this when Daena or a Council makes a recommendation.
    Later, record the actual outcome using /record.
    """
    tracker = get_outcome_tracker()
    
    outcome = tracker.track_decision(
        outcome_id=request.outcome_id,
        decision_type=request.decision_type,
        category=request.category,
        recommendation=request.recommendation,
        agent_id=request.agent_id,
        council_result=request.council_result,
        metadata=request.metadata
    )
    
    return {
        "success": True,
        "outcome_id": outcome.outcome_id,
        "message": f"Now tracking outcome for: {request.decision_type}"
    }


@router.post("/{outcome_id}/record")
async def record_outcome(outcome_id: str, request: RecordOutcomeRequest) -> Dict[str, Any]:
    """
    Record the actual outcome of a tracked decision.
    
    This closes the feedback loop and updates expert calibration.
    """
    tracker = get_outcome_tracker()
    
    # Validate status
    try:
        status = OutcomeStatus(request.status)
    except ValueError:
        valid = [s.value for s in OutcomeStatus]
        raise HTTPException(400, f"Invalid status. Must be one of: {valid}")
    
    success = tracker.record_outcome(
        outcome_id=outcome_id,
        status=status,
        notes=request.notes,
        feedback_score=request.feedback_score
    )
    
    if not success:
        raise HTTPException(404, f"Outcome not found: {outcome_id}")
    
    return {
        "success": True,
        "outcome_id": outcome_id,
        "recorded_status": request.status,
        "message": "Outcome recorded and expert scores updated"
    }


# ============================================
# List and Query Endpoints
# ============================================

@router.get("/pending")
async def get_pending_outcomes(
    limit: int = Query(default=50, ge=1, le=200)
) -> Dict[str, Any]:
    """Get decisions still pending outcome resolution."""
    tracker = get_outcome_tracker()
    pending = tracker.get_pending_outcomes(limit=limit)
    
    return {
        "count": len(pending),
        "outcomes": [
            {
                "outcome_id": o.outcome_id,
                "decision_type": o.decision_type,
                "category": o.category,
                "recommendation": o.recommendation[:200],
                "agent_id": o.agent_id,
                "created_at": o.created_at
            }
            for o in pending
        ]
    }


@router.get("/stats")
async def get_outcome_stats() -> Dict[str, Any]:
    """Get outcome tracking statistics."""
    tracker = get_outcome_tracker()
    return tracker.get_stats()


@router.get("/insights")
async def get_outcome_insights() -> Dict[str, Any]:
    """Get AI-generated insights from outcome data."""
    tracker = get_outcome_tracker()
    insights = tracker.get_insights()
    
    return {
        "insights": insights,
        "generated_at": tracker.get_stats().get("last_updated")
    }


# ============================================
# Expert Calibration Endpoints
# ============================================

@router.get("/experts")
async def get_expert_scores(
    domain: Optional[str] = Query(default=None, description="Filter by domain"),
    limit: int = Query(default=20, ge=1, le=100)
) -> Dict[str, Any]:
    """Get expert calibration scores sorted by accuracy."""
    tracker = get_outcome_tracker()
    experts = tracker.get_top_experts(domain=domain, limit=limit)
    
    return {
        "count": len(experts),
        "experts": [
            {
                "expert_id": e.expert_id,
                "domain": e.domain,
                "accuracy_score": round(e.accuracy_score, 1),
                "total_recommendations": e.total_recommendations,
                "successful_outcomes": e.successful_outcomes,
                "failed_outcomes": e.failed_outcomes,
                "last_updated": e.last_updated
            }
            for e in experts
        ]
    }


@router.get("/experts/{expert_id}")
async def get_expert_accuracy(expert_id: str) -> Dict[str, Any]:
    """Get accuracy score for a specific expert."""
    tracker = get_outcome_tracker()
    accuracy = tracker.get_expert_accuracy(expert_id)
    
    if accuracy is None:
        return {
            "expert_id": expert_id,
            "accuracy_score": None,
            "message": "No data for this expert yet"
        }
    
    return {
        "expert_id": expert_id,
        "accuracy_score": round(accuracy, 1)
    }


# ============================================
# Maintenance Endpoints
# ============================================

@router.post("/expire-old")
async def expire_old_outcomes(
    days: int = Query(default=30, ge=7, le=365)
) -> Dict[str, Any]:
    """Mark old pending outcomes as expired."""
    tracker = get_outcome_tracker()
    expired = tracker.expire_old_outcomes(days=days)
    
    return {
        "expired_count": expired,
        "message": f"Expired outcomes older than {days} days"
    }


@router.get("/health")
async def outcomes_health() -> Dict[str, Any]:
    """Health check for the outcome tracker."""
    try:
        tracker = get_outcome_tracker()
        stats = tracker.get_stats()
        
        return {
            "status": "healthy",
            "total_tracked": stats.get("total_tracked", 0),
            "pending": stats.get("pending", 0),
            "experts_calibrated": stats.get("experts_calibrated", 0)
        }
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e)
        }
