from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
import os
from pydantic import BaseModel

router = APIRouter(prefix="/cmp/graph", tags=["cmp"])

class Node(BaseModel):
    id: str
    type: str
    data: Dict[str, Any]
    position: Dict[str, float]

class Edge(BaseModel):
    id: str
    source: str
    target: str

class GraphUpdate(BaseModel):
    nodes: List[Node]
    edges: List[Edge]

@router.get("/")
async def get_graph() -> Dict[str, Any]:
    """Fetch the current CMP node graph structure."""
    return {
        "nodes": [
            {"id": "node_1", "type": "agent", "data": {"label": "Research Agent"}, "position": {"x": 100, "y": 100}},
            {"id": "node_2", "type": "skill", "data": {"label": "Web Search"}, "position": {"x": 300, "y": 100}},
            {"id": "node_3", "type": "governance", "data": {"label": "Approval Gate"}, "position": {"x": 500, "y": 100}},
        ],
        "edges": [
            {"id": "e1-2", "source": "node_1", "target": "node_2"},
            {"id": "e2-3", "source": "node_2", "target": "node_3"},
        ]
    }

@router.post("/save")
async def save_graph(graph: GraphUpdate) -> Dict[str, Any]:
    """Save a new CMP node graph configuration."""
    return {
        "success": True,
        "message": "Graph configuration persisted.",
        "version": "1.0.42"
    }

@router.post("/execute")
async def execute_graph(start_node: str) -> Dict[str, Any]:
    """Trigger the execution of a workflow from a specific node."""
    return {
        "success": True,
        "run_id": f"run_{os.urandom(4).hex()}",
        "status": "STARTED"
    }
