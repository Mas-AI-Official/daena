"""
Intelligence Routing API
Routes queries based on IQ/EQ/AQ/Execution dimensions
"""
from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.services.intelligence_routing import get_intelligence_router, IntelligenceScores
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/intelligence", tags=["intelligence"])


class QueryRequest(BaseModel):
    query: str
    context: Optional[Dict[str, Any]] = None
    available_agents: Optional[List[Dict[str, Any]]] = None


class ScoreRequest(BaseModel):
    query: str
    context: Optional[Dict[str, Any]] = None


@router.post("/score")
async def score_query(request: ScoreRequest) -> Dict[str, Any]:
    """Score a query on intelligence dimensions (IQ/EQ/AQ/Execution)"""
    intelligence_router = get_intelligence_router()
    scores = intelligence_router.score_query(request.query, request.context)
    
    return {
        "success": True,
        "query": request.query,
        "scores": scores.to_dict(),
        "primary_dimension": scores.get_primary_dimension().value
    }


@router.post("/route")
async def route_query(request: QueryRequest) -> Dict[str, Any]:
    """Route a query to appropriate agents based on intelligence scores"""
    intelligence_router = get_intelligence_router()
    
    result = await intelligence_router.route_and_merge(
        query=request.query,
        context=request.context,
        available_agents=request.available_agents
    )
    
    return {
        "success": True,
        **result
    }


@router.get("/scores/history")
async def get_intelligence_history(
    limit: int = 10,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get history of intelligence scores from audit log"""
    from backend.database import EventLog
    from sqlalchemy import desc
    
    events = db.query(EventLog).filter(
        EventLog.event_type == "intelligence.routing"
    ).order_by(desc(EventLog.created_at)).limit(limit).all()
    
    history = []
    for event in events:
        payload = event.payload_json or {}
        history.append({
            "timestamp": event.created_at.isoformat() if event.created_at else None,
            "query": payload.get("query", ""),
            "scores": payload.get("intelligence_scores", {}),
            "primary_dimension": payload.get("primary_dimension", ""),
            "agents_used": payload.get("agents_used", 0)
        })
    
    return {
        "success": True,
        "history": history,
        "total": len(history)
    }

