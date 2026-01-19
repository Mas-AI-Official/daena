"""
Events API Routes
Provides endpoints for accessing event log
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime, timedelta
import logging

from backend.database import get_db, EventLog
from backend.services.event_bus import event_bus

router = APIRouter(prefix="/api/v1/events", tags=["events"])
logger = logging.getLogger(__name__)

# Export emit function for backward compatibility
def emit(event_type: str, metadata: Dict[str, Any] = None):
    """Emit an event via the event bus (backward compatibility)"""
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(event_bus.publish(event_type, "system", "0", metadata or {}))
    except RuntimeError:
        # No running loop - skip event emission
        pass

@router.get("/recent")
async def get_recent_events(
    limit: int = Query(50, description="Maximum number of events to return"),
    since_event_id: Optional[int] = Query(None, description="Get events after this ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get recent events from the event log"""
    try:
        query = db.query(EventLog).order_by(desc(EventLog.id))
        
        if since_event_id:
            query = query.filter(EventLog.id > since_event_id)
        
        events = query.limit(limit).all()
        
        event_list = []
        for event in events:
            # Extract message from payload_json if available
            payload = event.payload_json if event.payload_json else {}
            message = payload.get("message", "") if isinstance(payload, dict) else ""
            
            event_list.append({
                "id": event.id,
                "event_type": event.event_type,
                "entity_type": event.entity_type,
                "entity_id": event.entity_id,
                "message": message,
                "payload": payload,
                "created_by": event.created_by,
                "created_at": event.created_at.isoformat() if event.created_at else None
            })
        
        return {
            "success": True,
            "events": event_list,
            "total": len(event_list),
            "latest_event_id": events[0].id if events else None
        }
    except Exception as e:
        logger.error(f"Failed to get recent events: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
async def list_events(
    limit: int = Query(100, description="Maximum number of events to return"),
    offset: int = Query(0, description="Number of events to skip"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """List events with optional filtering"""
    try:
        query = db.query(EventLog)
        
        if event_type:
            query = query.filter(EventLog.event_type == event_type)
        if entity_type:
            query = query.filter(EventLog.entity_type == entity_type)
        
        total = query.count()
        events = query.order_by(desc(EventLog.id)).offset(offset).limit(limit).all()
        
        event_list = []
        for event in events:
            # Extract message from payload_json if available
            payload = event.payload_json if event.payload_json else {}
            message = payload.get("message", "") if isinstance(payload, dict) else ""
            
            event_list.append({
                "id": event.id,
                "event_type": event.event_type,
                "entity_type": event.entity_type,
                "entity_id": event.entity_id,
                "message": message,
                "payload": payload,
                "created_by": event.created_by,
                "created_at": event.created_at.isoformat() if event.created_at else None
            })
        
        return {
            "success": True,
            "events": event_list,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Failed to list events: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_event_stats(
    hours: int = Query(24, description="Number of hours to look back"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get event statistics"""
    try:
        since = datetime.utcnow() - timedelta(hours=hours)
        
        total_events = db.query(EventLog).filter(EventLog.created_at >= since).count()
        
        # Count by event type
        from sqlalchemy import func
        type_counts = db.query(
            EventLog.event_type,
            func.count(EventLog.id).label('count')
        ).filter(
            EventLog.created_at >= since
        ).group_by(EventLog.event_type).all()
        
        stats = {
            "total_events": total_events,
            "period_hours": hours,
            "by_type": {event_type: count for event_type, count in type_counts}
        }
        
        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Failed to get event stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
