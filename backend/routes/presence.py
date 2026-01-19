"""
Presence Service API Routes.

Provides endpoints for presence beacon management and neighbor state tracking.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

from backend.services.presence_service import presence_service, PresenceState

router = APIRouter(prefix="/api/v1/presence", tags=["presence"])


class RegisterCellRequest(BaseModel):
    cell_id: str
    department: str
    neighbors: Optional[List[str]] = None


@router.post("/register")
async def register_cell(request: RegisterCellRequest) -> Dict[str, Any]:
    """Register a cell for presence tracking."""
    try:
        result = await presence_service.register_cell(
            cell_id=request.cell_id,
            department=request.department,
            neighbors=request.neighbors
        )
        
        return {
            "success": True,
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to register cell: {str(e)}")


@router.post("/{cell_id}/unregister")
async def unregister_cell(cell_id: str) -> Dict[str, Any]:
    """Unregister a cell and stop beacons."""
    try:
        result = await presence_service.unregister_cell(cell_id=cell_id)
        
        return {
            "success": True,
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to unregister cell: {str(e)}")


@router.get("/{cell_id}")
async def get_cell_presence(cell_id: str) -> Dict[str, Any]:
    """Get presence information for a cell."""
    presence = presence_service.get_cell_presence(cell_id)
    
    return {
        "success": True,
        "presence": presence
    }


@router.get("/{cell_id}/neighbors")
async def get_neighbors(
    cell_id: str,
    state: Optional[str] = None
) -> Dict[str, Any]:
    """Get neighbors of a cell, optionally filtered by state."""
    state_filter = None
    if state:
        try:
            state_filter = PresenceState(state.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid state: {state}")
    
    neighbors = presence_service.get_neighbors(cell_id, state_filter=state_filter)
    
    return {
        "success": True,
        "cell_id": cell_id,
        "neighbors": neighbors,
        "count": len(neighbors)
    }


@router.get("/{cell_id}/fanout")
async def get_adaptive_fanout(
    cell_id: str,
    base_fanout: int = 6
) -> Dict[str, Any]:
    """Get adaptive fanout for a cell."""
    fanout = presence_service.get_adaptive_fanout(cell_id, base_fanout=base_fanout)
    
    return {
        "success": True,
        "cell_id": cell_id,
        "adaptive_fanout": fanout,
        "base_fanout": base_fanout
    }


@router.post("/heartbeat/check")
async def check_heartbeats() -> Dict[str, Any]:
    """Check heartbeats and mark offline neighbors."""
    try:
        offline_cells = await presence_service.check_heartbeats()
        
        return {
            "success": True,
            "offline_cells": offline_cells,
            "count": len(offline_cells)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check heartbeats: {str(e)}")


@router.get("/all")
async def get_all_presence() -> Dict[str, Any]:
    """Get presence information for all cells."""
    all_presence = presence_service.get_all_presence()
    
    return {
        "success": True,
        "presence": all_presence,
        "total_cells": len(all_presence)
    }


@router.get("/stats")
async def get_presence_stats() -> Dict[str, Any]:
    """Get presence service statistics."""
    stats = presence_service.get_stats()
    
    return {
        "success": True,
        "stats": stats
    }

