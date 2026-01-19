"""
Council Status & Presence Routes
Provides real-time council session status and presence information.
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query

from backend.services.council_scheduler import council_scheduler, CouncilPhase
from backend.routes.monitoring import verify_monitoring_auth

router = APIRouter(prefix="/api/v1/council", tags=["council-status"])


@router.get("/status")
async def get_council_status(
    department: Optional[str] = Query(None, description="Filter by department"),
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Get current council status - shows active sessions, current phase, and presence.
    
    Returns:
    {
        "current_phase": "idle|scout|debate|commit",
        "active_departments": ["engineering", "sales"],
        "round_history": [...],
        "presence": {
            "total_rounds": 10,
            "active_rounds": 2,
            "departments_in_session": ["engineering", "sales"]
        }
    }
    """
    try:
        stats = council_scheduler.get_stats()
        round_history = council_scheduler.get_round_history(department=department, limit=20)
        
        # Determine active departments (departments with recent rounds)
        active_departments = []
        current_phase = stats.get("current_phase", "idle")
        
        # Check for recent rounds (within last 5 minutes)
        from datetime import datetime, timedelta
        recent_threshold = datetime.utcnow() - timedelta(minutes=5)
        
        active_rounds = []
        for round_data in round_history:
            if round_data.get("status") in ["in_progress", "active"]:
                dept = round_data.get("department")
                if dept and dept not in active_departments:
                    active_departments.append(dept)
                active_rounds.append(round_data)
            # Also check by timestamp if available
            round_time = round_data.get("timestamp")
            if round_time:
                try:
                    if isinstance(round_time, str):
                        round_dt = datetime.fromisoformat(round_time.replace('Z', '+00:00'))
                    else:
                        round_dt = round_time
                    if round_dt >= recent_threshold:
                        dept = round_data.get("department")
                        if dept and dept not in active_departments:
                            active_departments.append(dept)
                except:
                    pass
        
        return {
            "current_phase": current_phase,
            "active_departments": active_departments,
            "active_rounds": len(active_rounds),
            "presence": {
                "total_rounds": stats.get("total_rounds", 0),
                "active_rounds": len(active_rounds),
                "departments_in_session": active_departments,
                "scheduler_running": stats.get("running", False)
            },
            "recent_history": round_history[:5],  # Last 5 rounds
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get council status: {str(e)}")


@router.get("/presence")
async def get_council_presence(
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Get council presence information - shows which departments have active council sessions.
    """
    try:
        stats = council_scheduler.get_stats()
        round_history = council_scheduler.get_round_history(limit=50)
        
        # Get departments with active/recent sessions
        from datetime import datetime, timedelta
        recent_threshold = datetime.utcnow() - timedelta(minutes=10)
        
        department_presence = {}
        for round_data in round_history:
            dept = round_data.get("department")
            if not dept:
                continue
            
            round_time = round_data.get("timestamp")
            is_recent = False
            if round_time:
                try:
                    if isinstance(round_time, str):
                        round_dt = datetime.fromisoformat(round_time.replace('Z', '+00:00'))
                    else:
                        round_dt = round_time
                    is_recent = round_dt >= recent_threshold
                except:
                    pass
            
            if dept not in department_presence:
                department_presence[dept] = {
                    "department": dept,
                    "has_active_session": round_data.get("status") in ["in_progress", "active"],
                    "last_round_time": round_time,
                    "is_recent": is_recent,
                    "round_count": 0
                }
            
            department_presence[dept]["round_count"] += 1
        
        return {
            "departments": list(department_presence.values()),
            "total_active": sum(1 for d in department_presence.values() if d["has_active_session"]),
            "current_phase": stats.get("current_phase", "idle"),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get council presence: {str(e)}")

