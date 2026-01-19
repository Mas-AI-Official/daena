"""Audit routes for governance and decision tracking."""
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
import asyncio
from backend.middleware.abac_middleware import abac_check
from backend.utils.sunflower_registry import sunflower_registry

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])

# Mock audit log storage (replace with database in production)
audit_logs = []

class AuditEntry:
    """Audit log entry."""
    def __init__(self, timestamp: datetime, actor: str, resource: str, 
                 action: str, allowed: bool, reason: str, context: Dict[str, Any] = None):
        self.timestamp = timestamp
        self.actor = actor
        self.resource = resource
        self.action = action
        self.allowed = allowed
        self.reason = reason
        self.context = context or {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "actor": self.actor,
            "resource": self.resource,
            "action": self.action,
            "allowed": self.allowed,
            "reason": self.reason,
            "context": self.context
        }

def log_audit_entry(actor: str, resource: str, action: str, 
                   allowed: bool, reason: str, context: Dict[str, Any] = None):
    """Log an audit entry."""
    entry = AuditEntry(datetime.now(), actor, resource, action, allowed, reason, context)
    audit_logs.append(entry)
    
    # Keep only last 1000 entries
    if len(audit_logs) > 1000:
        audit_logs.pop(0)
    
    # Emit audit event
    try:
        from backend.routes.events import emit
        emit("abac_decision", {
            "allow": allowed,
            "reason": reason,
            "actor": actor,
            "resource": resource,
            "action": action,
            "ts": datetime.now().isoformat()
        })
    except Exception:
        pass
    
    return entry

@router.get("/decisions")
async def get_audit_decisions(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    actor: Optional[str] = Query(None, description="Filter by actor"),
    resource: Optional[str] = Query(None, description="Filter by resource"),
    action: Optional[str] = Query(None, description="Filter by action"),
    allowed: Optional[bool] = Query(None, description="Filter by allowed status"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)")
):
    """Get paginated audit decisions."""
    # Apply ABAC check
    await abac_check("global", "read", "admin")
    
    # Filter logs
    filtered_logs = audit_logs.copy()
    
    if actor:
        filtered_logs = [log for log in filtered_logs if log.actor == actor]
    if resource:
        filtered_logs = [log for log in filtered_logs if log.resource == resource]
    if action:
        filtered_logs = [log for log in filtered_logs if log.action == action]
    if allowed is not None:
        filtered_logs = [log for log in filtered_logs if log.allowed == allowed]
    
    # Date filtering
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            filtered_logs = [log for log in filtered_logs if log.timestamp >= start_dt]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format")
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            filtered_logs = [log for log in filtered_logs if log.timestamp <= end_dt]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format")
    
    # Sort by timestamp (newest first)
    filtered_logs.sort(key=lambda x: x.timestamp, reverse=True)
    
    # Pagination
    total_count = len(filtered_logs)
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    page_logs = filtered_logs[start_idx:end_idx]
    
    return {
        "success": True,
        "data": [log.to_dict() for log in page_logs],
        "pagination": {
            "page": page,
            "limit": limit,
            "total_count": total_count,
            "total_pages": (total_count + limit - 1) // limit,
            "has_next": end_idx < total_count,
            "has_prev": page > 1
        },
        "filters": {
            "actor": actor,
            "resource": resource,
            "action": action,
            "allowed": allowed,
            "start_date": start_date,
            "end_date": end_date
        }
    }

@router.get("/decisions/stream")
async def stream_audit_decisions():
    """Stream audit decisions in real-time using Server-Sent Events."""
    # Apply ABAC check
    await abac_check("global", "read", "admin")
    
    async def event_generator():
        """Generate SSE events for audit logs."""
        last_count = len(audit_logs)
        
        while True:
            current_count = len(audit_logs)
            
            if current_count > last_count:
                # New logs available
                new_logs = audit_logs[last_count:]
                for log in new_logs:
                    yield f"data: {json.dumps(log.to_dict())}\n\n"
                last_count = current_count
            
            # Send heartbeat every 30 seconds
            await asyncio.sleep(30)
            yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': datetime.now().isoformat()})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*"
        }
    )

@router.get("/logs")
async def get_audit_logs(
    limit: int = Query(20, ge=1, le=100, description="Number of logs to return"),
    actor: Optional[str] = Query(None, description="Filter by actor"),
    action: Optional[str] = Query(None, description="Filter by action")
):
    """Get audit logs (simplified endpoint for frontend compatibility)."""
    try:
        # Filter logs
        filtered_logs = audit_logs.copy()
        
        if actor:
            filtered_logs = [log for log in filtered_logs if log.actor == actor]
        if action:
            filtered_logs = [log for log in filtered_logs if log.action == action]
        
        # Sort by timestamp (newest first)
        filtered_logs.sort(key=lambda x: x.timestamp, reverse=True)
        
        # Limit results
        limited_logs = filtered_logs[:limit]
        
        return {
            "logs": [log.to_dict() for log in limited_logs],
            "count": len(limited_logs),
            "total": len(audit_logs)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get audit logs: {str(e)}")

@router.get("/stats")
async def get_audit_stats():
    """Get audit statistics."""
    # Apply ABAC check
    await abac_check("global", "read", "admin")
    
    if not audit_logs:
        return {
            "success": True,
            "stats": {
                "total_entries": 0,
                "allowed_actions": 0,
                "denied_actions": 0,
                "top_actors": [],
                "top_resources": [],
                "top_actions": []
            }
        }
    
    # Calculate stats
    total_entries = len(audit_logs)
    allowed_actions = sum(1 for log in audit_logs if log.allowed)
    denied_actions = total_entries - allowed_actions
    
    # Top actors
    actor_counts = {}
    for log in audit_logs:
        actor_counts[log.actor] = actor_counts.get(log.actor, 0) + 1
    
    # Top resources
    resource_counts = {}
    for log in audit_logs:
        resource_counts[log.resource] = resource_counts.get(log.resource, 0) + 1
    
    # Top actions
    action_counts = {}
    for log in audit_logs:
        action_counts[log.action] = action_counts.get(log.action, 0) + 1
    
    return {
        "success": True,
        "stats": {
            "total_entries": total_entries,
            "allowed_actions": allowed_actions,
            "denied_actions": denied_actions,
            "denial_rate": round(denied_actions / total_entries * 100, 2),
            "top_actors": sorted(actor_counts.items(), key=lambda x: x[1], reverse=True)[:10],
            "top_resources": sorted(resource_counts.items(), key=lambda x: x[1], reverse=True)[:10],
            "top_actions": sorted(action_counts.items(), key=lambda x: x[1], reverse=True)[:10],
            "time_range": {
                "earliest": min(log.timestamp for log in audit_logs).isoformat(),
                "latest": max(log.timestamp for log in audit_logs).isoformat()
            }
        }
    }

# Initialize with some sample audit data
def init_sample_audit_data():
    """Initialize sample audit data for testing."""
    if not audit_logs:
        sample_entries = [
            ("admin", "departments", "read", True, "Admin access granted"),
            ("user1", "agents", "read", True, "User has department access"),
            ("user2", "projects", "write", False, "Insufficient permissions"),
            ("founder", "global", "delete", True, "Founder has full access"),
            ("dept_head", "department", "write", True, "Department head access"),
            ("agent", "memory", "read", False, "Agent cannot access global memory"),
        ]
        
        for actor, resource, action, allowed, reason in sample_entries:
            log_audit_entry(actor, resource, action, allowed, reason)

# Initialize sample data
init_sample_audit_data() 