"""
Council Rounds API - Expose round state and history to UI.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List, Optional
from datetime import datetime

from backend.routes.monitoring import verify_monitoring_auth
from backend.services.council_scheduler import council_scheduler

router = APIRouter(prefix="/api/v1/council", tags=["council"])


@router.get("/rounds/history")
async def get_round_history(
    limit: int = 10,
    department: Optional[str] = None,
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Get last N council rounds with outcomes and evidence pointers.
    
    Args:
        limit: Number of rounds to return (default: 10, max: 100)
        department: Filter by department (optional)
    
    Returns:
        List of round summaries with outcomes and evidence
    """
    try:
        if not hasattr(council_scheduler, 'round_history'):
            return {
                "success": True,
                "rounds": [],
                "total": 0,
                "message": "Council scheduler not initialized"
            }
        
        rounds = council_scheduler.round_history
        
        # Filter by department if provided
        if department:
            rounds = [r for r in rounds if r.get("department") == department]
        
        # Limit results
        limit = min(limit, 100)
        rounds = rounds[-limit:] if len(rounds) > limit else rounds
        
        # Add evidence pointers (NBMF txids from ledger)
        for round_data in rounds:
            round_id = round_data.get("round_id")
            if round_id:
                # Try to get evidence from ledger
                try:
                    from memory_service.ledger import ledger_service
                    if hasattr(ledger_service, 'get_events_by_ref'):
                        events = ledger_service.get_events_by_ref(round_id, limit=10)
                        round_data["evidence"] = [
                            {
                                "txid": e.get("txid"),
                                "action": e.get("action"),
                                "timestamp": e.get("timestamp")
                            }
                            for e in events
                        ]
                except:
                    round_data["evidence"] = []
        
        return {
            "success": True,
            "rounds": rounds,
            "total": len(rounds),
            "limit": limit,
            "department": department
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting round history: {str(e)}")


@router.get("/rounds/current")
async def get_current_round(
    department: Optional[str] = None,
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Get current council round state.
    
    Returns:
        Current round state with phase, active departments, and status
    """
    try:
        current_phase = council_scheduler.current_phase.value if hasattr(council_scheduler, 'current_phase') else "idle"
        round_id = getattr(council_scheduler, '_current_round_id', None)
        
        return {
            "success": True,
            "current_phase": current_phase,
            "round_id": round_id,
            "department": department,
            "active": current_phase != "idle",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting current round: {str(e)}")


@router.get("/rounds/{round_id}")
async def get_round_details(
    round_id: str,
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Get detailed information about a specific round.
    
    Returns:
        Round details including all phases, outcomes, and evidence
    """
    try:
        if not hasattr(council_scheduler, 'round_history'):
            raise HTTPException(status_code=404, detail="Round history not available")
        
        # Find round in history
        round_data = None
        for r in council_scheduler.round_history:
            if r.get("round_id") == round_id:
                round_data = r
                break
        
        if not round_data:
            raise HTTPException(status_code=404, detail=f"Round not found: {round_id}")
        
        # Get evidence from ledger
        evidence = []
        try:
            from memory_service.ledger import ledger_service
            if hasattr(ledger_service, 'get_events_by_ref'):
                events = ledger_service.get_events_by_ref(round_id, limit=50)
                evidence = [
                    {
                        "txid": e.get("txid"),
                        "action": e.get("action"),
                        "store": e.get("store"),
                        "route": e.get("route"),
                        "timestamp": e.get("timestamp"),
                        "extra": e.get("extra", {})
                    }
                    for e in events
                ]
        except:
            pass
        
        return {
            "success": True,
            "round": round_data,
            "evidence": evidence,
            "evidence_count": len(evidence)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting round details: {str(e)}")

