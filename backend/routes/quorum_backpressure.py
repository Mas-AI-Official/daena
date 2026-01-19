"""
Quorum and Backpressure API Routes.

Provides endpoints for quorum voting and backpressure management.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional
from pydantic import BaseModel

from backend.utils.quorum import quorum_manager, QuorumType
from backend.utils.backpressure import backpressure_manager
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/quorum", tags=["quorum"])


class QuorumRequest(BaseModel):
    quorum_type: str  # "local", "global", "ring", "radial"
    required_votes: Optional[int] = None
    timeout_seconds: float = 30.0
    cell_id: Optional[str] = None  # Cell ID for LOCAL quorum (to track neighbors)


class VoteRequest(BaseModel):
    voter_id: str
    vote: bool
    confidence: float = 1.0


class CapacityRequest(BaseModel):
    requested_capacity: float = 0.1
    timeout_seconds: float = 5.0


@router.post("/start")
async def start_quorum(request: QuorumRequest) -> Dict[str, Any]:
    """Start a new quorum."""
    try:
        quorum_type = QuorumType[request.quorum_type.upper()]
        import uuid
        quorum_id = str(uuid.uuid4())
        
        # For LOCAL quorum, get neighbors if cell_id provided
        if quorum_type == QuorumType.LOCAL and request.cell_id:
            try:
                from backend.utils.sunflower_registry import sunflower_registry
                neighbors = sunflower_registry.get_neighbors(request.cell_id, max_neighbors=6)
                quorum_manager.set_cell_neighbors(request.cell_id, neighbors)
            except Exception as e:
                logger.warning(f"Could not get neighbors for {request.cell_id}: {e}")
        
        result = quorum_manager.start_quorum(
            quorum_id=quorum_id,
            quorum_type=quorum_type,
            required_votes=request.required_votes,
            timeout_seconds=request.timeout_seconds,
            cell_id=request.cell_id
        )
        
        return {
            "success": True,
            "quorum": result
        }
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid quorum type: {request.quorum_type}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start quorum: {str(e)}")


@router.post("/{quorum_id}/vote")
async def cast_vote(quorum_id: str, request: VoteRequest) -> Dict[str, Any]:
    """Cast a vote in a quorum."""
    try:
        result = quorum_manager.cast_vote(
            quorum_id=quorum_id,
            voter_id=request.voter_id,
            vote=request.vote,
            confidence=request.confidence
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return {
            "success": True,
            "vote": result
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cast vote: {str(e)}")


@router.get("/{quorum_id}/status")
async def get_quorum_status(quorum_id: str) -> Dict[str, Any]:
    """Get quorum status."""
    status = quorum_manager.get_quorum_status(quorum_id)
    
    if "error" in status:
        raise HTTPException(status_code=404, detail=status["error"])
    
    return {
        "success": True,
        "status": status
    }


@router.get("/history")
async def get_quorum_history(limit: int = 100) -> Dict[str, Any]:
    """Get quorum history."""
    history = quorum_manager.get_history(limit=limit)
    
    return {
        "success": True,
        "history": history,
        "total": len(history)
    }


@router.get("/stats")
async def get_quorum_stats() -> Dict[str, Any]:
    """Get quorum statistics."""
    stats = quorum_manager.get_stats()
    
    return {
        "success": True,
        "stats": stats
    }


# Backpressure endpoints

router_bp = APIRouter(prefix="/api/v1/backpressure", tags=["backpressure"])


@router_bp.post("/{cell_id}/request")
async def request_capacity(cell_id: str, request: CapacityRequest) -> Dict[str, Any]:
    """Request capacity (need)."""
    try:
        result = backpressure_manager.request_capacity(
            cell_id=cell_id,
            requested_capacity=request.requested_capacity,
            timeout_seconds=request.timeout_seconds
        )
        
        return {
            "success": True,
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to request capacity: {str(e)}")


@router_bp.post("/offer")
async def offer_capacity(
    source_cell_id: str,
    destination_cell_id: str,
    capacity: float = 0.1
) -> Dict[str, Any]:
    """Offer capacity to a neighbor (offer)."""
    try:
        result = backpressure_manager.offer_capacity(
            source_cell_id=source_cell_id,
            destination_cell_id=destination_cell_id,
            offered_capacity=capacity
        )
        
        return {
            "success": True,
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to offer capacity: {str(e)}")


@router_bp.post("/{token_id}/ack")
async def acknowledge_capacity(token_id: str, cell_id: str) -> Dict[str, Any]:
    """Acknowledge capacity transfer (ack)."""
    try:
        result = backpressure_manager.acknowledge_capacity(token_id=token_id, cell_id=cell_id)
        
        if result["status"] == "token_not_found":
            raise HTTPException(status_code=404, detail="Token not found")
        
        return {
            "success": True,
            "result": result
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to acknowledge capacity: {str(e)}")


@router_bp.post("/{cell_id}/release")
async def release_capacity(cell_id: str, capacity: float = 0.1) -> Dict[str, Any]:
    """Release capacity back to the pool."""
    try:
        result = backpressure_manager.release_capacity(cell_id=cell_id, capacity=capacity)
        
        return {
            "success": True,
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to release capacity: {str(e)}")


@router_bp.get("/{cell_id}/status")
async def get_cell_status(cell_id: str) -> Dict[str, Any]:
    """Get cell backpressure status."""
    status = backpressure_manager.get_cell_status(cell_id)
    
    return {
        "success": True,
        "status": status
    }


@router_bp.get("/stats")
async def get_backpressure_stats() -> Dict[str, Any]:
    """Get backpressure statistics."""
    stats = backpressure_manager.get_stats()
    
    return {
        "success": True,
        "stats": stats
    }

