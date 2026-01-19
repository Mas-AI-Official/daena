"""
Enhanced Council Routes V2 with Phase-Locked Rounds.

Integrates the new council scheduler with phase-locked rounds.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional
from datetime import datetime

from backend.services.council_scheduler import council_scheduler, CouncilScheduler
from backend.utils.message_bus_v2 import message_bus_v2

router = APIRouter(prefix="/api/v1/council-v2", tags=["council-v2"])


@router.post("/{department}/round")
async def start_council_round(
    department: str,
    topic: str = "Default council topic",
    timeout_override: Optional[float] = None
) -> Dict[str, Any]:
    """
    Start a phase-locked council round for a department.
    
    Executes: Scout Phase → Debate Phase → Commit Phase
    """
    try:
        if timeout_override:
            # Temporarily override timeouts
            original_timeouts = council_scheduler.phase_timeouts.copy()
            for phase in council_scheduler.phase_timeouts:
                council_scheduler.phase_timeouts[phase] = timeout_override
        
        round_summary = await council_scheduler.council_tick(department, topic)
        
        if timeout_override:
            council_scheduler.phase_timeouts = original_timeouts
        
        return {
            "success": True,
            "round": round_summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Council round failed: {str(e)}")


@router.get("/{department}/history")
async def get_council_history(
    department: str,
    limit: int = 10
) -> Dict[str, Any]:
    """Get council round history for a department."""
    history = council_scheduler.get_round_history(department=department, limit=limit)
    return {
        "success": True,
        "department": department,
        "history": history,
        "total_rounds": len(history)
    }


@router.get("/stats")
async def get_council_stats() -> Dict[str, Any]:
    """Get council scheduler statistics."""
    scheduler_stats = council_scheduler.get_stats()
    bus_stats = message_bus_v2.get_stats()
    
    return {
        "success": True,
        "scheduler": scheduler_stats,
        "message_bus": bus_stats
    }


@router.post("/{department}/scout")
async def publish_scout_summary(
    department: str,
    cell_id: str,
    summary: str,
    confidence: float = 0.5,
    emotion: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Publish a scout summary to cell topic.
    
    Used by scout agents during Scout Phase.
    """
    try:
        delivered = await message_bus_v2.publish_to_cell(
            department,
            cell_id,
            {
                "type": "scout_summary",
                "summary": summary,
                "confidence": confidence,
                "emotion": emotion or {}
            },
            sender=f"scout_{cell_id}"
        )
        
        return {
            "success": True,
            "delivered_to": delivered,
            "topic": f"cell/{department}/{cell_id}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to publish scout summary: {str(e)}")


@router.post("/{department}/debate")
async def publish_debate_draft(
    department: str,
    ring_number: int,
    draft: str,
    counter_to: Optional[str] = None,
    confidence: float = 0.5
) -> Dict[str, Any]:
    """
    Publish a debate draft to ring topic.
    
    Used by advisor agents during Debate Phase.
    """
    try:
        delivered = await message_bus_v2.publish_to_ring(
            ring_number,
            {
                "type": "debate_draft",
                "draft": draft,
                "counter_to": counter_to,
                "confidence": confidence
            },
            sender=f"advisor_{department}"
        )
        
        return {
            "success": True,
            "delivered_to": delivered,
            "topic": f"ring/{ring_number}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to publish debate draft: {str(e)}")


@router.post("/subscribe/{topic_pattern}")
async def subscribe_to_topic(
    topic_pattern: str,
    handler_name: str = "default_handler"
) -> Dict[str, Any]:
    """
    Subscribe to a topic pattern.
    
    Examples:
    - "cell/engineering/*" - all cells in engineering
    - "ring/1" - all cells in ring 1
    - "radial/north" - all cells in north arm
    """
    try:
        async def handler(message):
            # Store message for retrieval
            # In production, this would call actual agent handlers
            pass
        
        message_bus_v2.subscribe(topic_pattern, handler)
        
        return {
            "success": True,
            "topic_pattern": topic_pattern,
            "handler": handler_name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to subscribe: {str(e)}")

