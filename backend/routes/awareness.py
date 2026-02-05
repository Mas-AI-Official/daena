from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from ..services.agent_awareness import agent_awareness
from ..utils.sunflower_registry import sunflower_registry

router = APIRouter(prefix="/api/v1/awareness", tags=["Social Intelligence"])

@router.get("/graph")
async def get_collaboration_graph() -> Dict[str, Any]:
    """Get the full social intelligence graph of agents."""
    graph = agent_awareness.get_collaboration_graph()
    
    # Enhance nodes with sunflower positions and department info
    for node in graph["nodes"]:
        agent_id = node["id"]
        agent_data = sunflower_registry.get_agent_by_id(agent_id)
        if agent_data:
            node["name"] = agent_data["name"]
            node["role"] = agent_data["role"]
            node["department_id"] = agent_data["department_id"]
            node["coordinates"] = agent_data["coordinates"]
            
            dept = sunflower_registry.get_department_by_id(agent_data["department_id"])
            if dept:
                node["department_name"] = dept["name"]
                node["color"] = dept["color"]
    
    return graph

@router.get("/summary/{agent_id}")
async def get_agent_summary(agent_id: str) -> Dict[str, Any]:
    """Get awareness summary for a specific agent."""
    summary = agent_awareness.get_agent_awareness_summary(agent_id)
    agent_data = sunflower_registry.get_agent_by_id(agent_id)
    if agent_data:
        summary["name"] = agent_data["name"]
        summary["role"] = agent_data["role"]
    return summary

@router.get("/shared-context")
async def get_shared_context(agent_ids: List[str]) -> Dict[str, Any]:
    """Get context shared between a group of agents (Council)."""
    context = agent_awareness.get_shared_context(agent_ids)
    return {
        "agents": agent_ids,
        "shared_items": list(context),
        "count": len(context)
    }

@router.get("/system-structure")
async def get_system_structure() -> Dict[str, Any]:
    """Get Daena's own internal identity and structure info."""
    return sunflower_registry.get_daena_structure_info()
