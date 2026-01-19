"""Honeycomb adjacency endpoints for Daena."""
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Any
from backend.utils.sunflower_registry import sunflower_registry

router = APIRouter(prefix="/api/v1/honeycomb", tags=["honeycomb"])

@router.get("/adjacency")
async def get_adjacency(
    cell_id: str = Query(..., description="Cell ID to get neighbors for"),
    max_neighbors: int = Query(6, description="Maximum number of neighbors")
) -> Dict[str, Any]:
    """Get adjacency information for a specific cell."""
    try:
        neighbors = sunflower_registry.get_neighbors(cell_id, max_neighbors)
        cell_data = sunflower_registry.get_cell_by_id(cell_id)
        
        if not cell_data:
            raise HTTPException(status_code=404, detail=f"Cell {cell_id} not found")
            
        return {
            "success": True,
            "cell_id": cell_id,
            "cell_data": {
                "id": cell_data.get("id"),
                "name": cell_data.get("name"),
                "type": "department" if cell_id.startswith("D") else "agent",
                "sunflower_index": cell_data.get("sunflower_index")
            },
            "adjacency": {
                "neighbors": neighbors,
                "neighbor_count": len(neighbors),
                "max_neighbors": max_neighbors
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/rebuild_adjacency")
async def rebuild_adjacency() -> Dict[str, Any]:
    """Rebuild all adjacency relationships."""
    try:
        sunflower_registry.rebuild_adjacency()
        
        return {
            "success": True,
            "message": "Adjacency relationships rebuilt",
            "adjacency_count": len(sunflower_registry.adjacency_cache),
            "adjacency": sunflower_registry.adjacency_cache
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/org_snapshot")
async def get_org_snapshot() -> Dict[str, Any]:
    """Get complete organizational snapshot with adjacency."""
    try:
        # Build snapshot from registry data
        snapshot = {
            "departments": sunflower_registry.departments,
            "agents": sunflower_registry.agents,
            "projects": sunflower_registry.projects,
            "cells": sunflower_registry.cells,
            "adjacency": sunflower_registry.adjacency_cache,
            "stats": sunflower_registry.get_stats()
        }
        
        return {
            "success": True,
            "snapshot": snapshot
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/departments")
async def get_departments_with_adjacency() -> Dict[str, Any]:
    """Get all departments with their adjacency information."""
    try:
        departments = []
        for dept_id, dept_data in sunflower_registry.departments.items():
            neighbors = sunflower_registry.get_neighbors(dept_data["cell_id"])
            dept_with_adjacency = {
                **dept_data,
                "adjacency": {
                    "neighbors": neighbors,
                    "neighbor_count": len(neighbors)
                }
            }
            departments.append(dept_with_adjacency)
            
        return {
            "success": True,
            "departments": departments,
            "total_departments": len(departments)
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/agents")
async def get_agents_with_adjacency(
    department_id: str = Query(None, description="Filter by department ID")
) -> Dict[str, Any]:
    """Get all agents with their adjacency information."""
    try:
        agents = []
        if department_id:
            # Get agents for specific department
            dept_agents = sunflower_registry.get_department_agents(department_id)
            for agent_data in dept_agents:
                neighbors = sunflower_registry.get_neighbors(agent_data["cell_id"])
                agent_with_adjacency = {
                    **agent_data,
                    "adjacency": {
                        "neighbors": neighbors,
                        "neighbor_count": len(neighbors)
                    }
                }
                agents.append(agent_with_adjacency)
        else:
            # Get all agents
            for agent_id, agent_data in sunflower_registry.agents.items():
                neighbors = sunflower_registry.get_neighbors(agent_data["cell_id"])
                agent_with_adjacency = {
                    **agent_data,
                    "adjacency": {
                        "neighbors": neighbors,
                        "neighbor_count": len(neighbors)
                    }
                }
                agents.append(agent_with_adjacency)
                
        return {
            "success": True,
            "agents": agents,
            "total_agents": len(agents),
            "department_filter": department_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/routing_stats")
async def get_routing_stats() -> Dict[str, Any]:
    """Get honeycomb routing statistics."""
    try:
        # Calculate routing statistics
        total_cells = len(sunflower_registry.cells)
        total_adjacencies = sum(len(neighbors) for neighbors in sunflower_registry.adjacency_cache.values())
        
        # Calculate average neighbors per cell
        avg_neighbors = total_adjacencies / total_cells if total_cells > 0 else 0
        
        # Count different cell types
        dept_count = len(sunflower_registry.departments)
        agent_count = len(sunflower_registry.agents)
        project_count = len(sunflower_registry.projects)
        
        return {
            "success": True,
            "routing_stats": {
                "total_cells": total_cells,
                "departments": dept_count,
                "agents": agent_count,
                "projects": project_count,
                "total_adjacencies": total_adjacencies,
                "average_neighbors_per_cell": round(avg_neighbors, 2),
                "adjacency_cache_size": len(sunflower_registry.adjacency_cache)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) 