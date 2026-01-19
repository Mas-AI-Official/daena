"""
Real-Time Collaboration API Routes.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from typing import Optional, List
import logging

from backend.services.realtime_collaboration import (
    realtime_collaboration_service,
    ActivityType
)
from backend.services.websocket_service import websocket_manager
from backend.routes.monitoring import verify_monitoring_auth

router = APIRouter(prefix="/api/v1/collaboration", tags=["collaboration"])
logger = logging.getLogger(__name__)


@router.websocket("/ws")
async def collaboration_websocket(websocket: WebSocket, client_id: Optional[str] = None):
    """WebSocket endpoint for real-time collaboration updates."""
    await websocket_manager.connect(websocket, "general", client_id)
    
    try:
        # Send initial state
        await websocket_manager.send_personal_message({
            "type": "collaboration_state",
            "agent_status": realtime_collaboration_service.get_agent_status_summary(),
            "active_collaborations": realtime_collaboration_service.get_active_collaborations(),
            "timestamp": __import__("datetime").datetime.now().isoformat()
        }, websocket)
        
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            import json
            message = json.loads(data)
            
            # Handle ping
            if message.get("type") == "ping":
                await websocket_manager.send_personal_message({
                    "type": "pong",
                    "timestamp": __import__("datetime").datetime.now().isoformat()
                }, websocket)
            
            # Handle subscription requests
            elif message.get("type") == "subscribe":
                activity_types = message.get("activity_types", [])
                # Store subscription (simplified - in production, use client_id)
                logger.info(f"Subscription request: {activity_types}")
            
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Collaboration WebSocket error: {e}")
        websocket_manager.disconnect(websocket)


@router.get("/agent-status")
async def get_agent_status(_: bool = Depends(verify_monitoring_auth)):
    """Get current agent status summary."""
    return realtime_collaboration_service.get_agent_status_summary()


@router.get("/activity-feed")
async def get_activity_feed(
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of activities"),
    _: bool = Depends(verify_monitoring_auth)
):
    """Get activity feed."""
    activities = realtime_collaboration_service.get_agent_activity_feed(
        agent_id=agent_id,
        limit=limit
    )
    return {
        "activities": activities,
        "total": len(activities),
        "agent_id": agent_id
    }


@router.get("/active-collaborations")
async def get_active_collaborations(_: bool = Depends(verify_monitoring_auth)):
    """Get all active collaboration sessions."""
    return {
        "collaborations": realtime_collaboration_service.get_active_collaborations(),
        "total": len(realtime_collaboration_service.get_active_collaborations())
    }


@router.post("/record-activity")
async def record_activity(
    agent_id: str,
    department: str,
    activity_type: str,
    metadata: Optional[dict] = None,
    related_agents: Optional[List[str]] = None,
    _: bool = Depends(verify_monitoring_auth)
):
    """Record an agent activity."""
    try:
        activity_type_enum = ActivityType(activity_type)
    except ValueError:
        return {
            "error": f"Invalid activity type: {activity_type}",
            "valid_types": [e.value for e in ActivityType]
        }
    
    activity_id = realtime_collaboration_service.record_activity(
        agent_id=agent_id,
        department=department,
        activity_type=activity_type_enum,
        metadata=metadata,
        related_agents=related_agents
    )
    
    return {
        "success": True,
        "activity_id": activity_id
    }


@router.post("/complete-activity")
async def complete_activity(
    activity_id: str,
    success: bool = True,
    _: bool = Depends(verify_monitoring_auth)
):
    """Mark an activity as completed."""
    realtime_collaboration_service.complete_activity(activity_id, success)
    return {"success": True, "activity_id": activity_id}


@router.post("/start-collaboration")
async def start_collaboration(
    participants: List[str],
    session_type: str = "general",
    _: bool = Depends(verify_monitoring_auth)
):
    """Start a collaboration session."""
    session_id = realtime_collaboration_service.start_collaboration_session(
        participants=participants,
        session_type=session_type
    )
    return {
        "success": True,
        "session_id": session_id
    }


@router.post("/end-collaboration")
async def end_collaboration(
    session_id: str,
    _: bool = Depends(verify_monitoring_auth)
):
    """End a collaboration session."""
    realtime_collaboration_service.end_collaboration_session(session_id)
    return {"success": True, "session_id": session_id}


@router.post("/record-memory-update")
async def record_memory_update(
    operation: str,
    item_id: str,
    agent_id: Optional[str] = None,
    metadata: Optional[dict] = None,
    _: bool = Depends(verify_monitoring_auth)
):
    """Record a memory update for real-time broadcasting."""
    realtime_collaboration_service.record_memory_update(
        operation=operation,
        item_id=item_id,
        agent_id=agent_id,
        metadata=metadata
    )
    return {"success": True}

