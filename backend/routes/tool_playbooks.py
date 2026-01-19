"""
Tool Playbooks API endpoints (Phase F).
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from backend.services.tool_playbooks import tool_playbook_library

router = APIRouter(prefix="/api/v1/playbooks", tags=["Tool Playbooks"])


class CreatePlaybookRequest(BaseModel):
    name: str
    description: str
    category: str
    steps: List[Dict[str, Any]]
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class ExecutePlaybookRequest(BaseModel):
    playbook_id: str
    variables: Dict[str, Any]


class ConvertDocRequest(BaseModel):
    doc_path: str
    name: str
    category: str
    tool_mapping: Optional[Dict[str, str]] = None


@router.get("/")
async def list_playbooks(category: Optional[str] = None) -> Dict[str, Any]:
    """List all playbooks, optionally filtered by category"""
    playbooks = tool_playbook_library.list_playbooks(category=category)
    return {
        "playbooks": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "category": p.category,
                "tags": p.tags,
                "steps_count": len(p.steps),
                "success_count": p.success_count,
                "failure_count": p.failure_count,
                "success_rate": p.success_count / max(1, p.success_count + p.failure_count),
            }
            for p in playbooks
        ],
        "categories": list(set(p.category for p in tool_playbook_library.playbooks.values()))
    }


@router.get("/categories")
async def list_categories() -> Dict[str, Any]:
    """List all categories"""
    categories = list(set(p.category for p in tool_playbook_library.playbooks.values()))
    return {"categories": categories}


@router.get("/{playbook_id}")
async def get_playbook(playbook_id: str) -> Dict[str, Any]:
    """Get a playbook by ID"""
    playbook = tool_playbook_library.get_playbook(playbook_id)
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    
    return {
        "id": playbook.id,
        "name": playbook.name,
        "description": playbook.description,
        "category": playbook.category,
        "tags": playbook.tags,
        "steps": [
            {
                "tool_name": s.tool_name,
                "args": s.args,
                "description": s.description,
                "expected_output": s.expected_output,
                "retry_on_failure": s.retry_on_failure,
                "max_retries": s.max_retries,
            }
            for s in playbook.steps
        ],
        "success_count": playbook.success_count,
        "failure_count": playbook.failure_count,
        "created_at": playbook.created_at,
        "updated_at": playbook.updated_at,
        "created_from_doc": playbook.created_from_doc,
        "metadata": playbook.metadata,
    }


@router.post("/create")
async def create_playbook(request: CreatePlaybookRequest) -> Dict[str, Any]:
    """Create a new playbook"""
    playbook = tool_playbook_library.create_playbook(
        name=request.name,
        description=request.description,
        category=request.category,
        steps=request.steps,
        tags=request.tags,
        metadata=request.metadata
    )
    
    return {
        "id": playbook.id,
        "name": playbook.name,
        "category": playbook.category,
        "status": "created"
    }


@router.post("/execute")
async def execute_playbook(request: ExecutePlaybookRequest) -> Dict[str, Any]:
    """Execute a playbook with variable substitution"""
    result = await tool_playbook_library.execute_playbook(
        playbook_id=request.playbook_id,
        variables=request.variables
    )
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result


@router.post("/convert-doc")
async def convert_doc_to_playbook(request: ConvertDocRequest) -> Dict[str, Any]:
    """Convert documentation to a playbook"""
    try:
        playbook = tool_playbook_library.convert_doc_to_playbook(
            doc_path=request.doc_path,
            name=request.name,
            category=request.category,
            tool_mapping=request.tool_mapping
        )
        
        return {
            "id": playbook.id,
            "name": playbook.name,
            "category": playbook.category,
            "steps_count": len(playbook.steps),
            "status": "converted"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/stats")
async def get_stats() -> Dict[str, Any]:
    """Get playbook library statistics"""
    playbooks = list(tool_playbook_library.playbooks.values())
    executions = tool_playbook_library.executions
    
    return {
        "total_playbooks": len(playbooks),
        "total_categories": len(set(p.category for p in playbooks)),
        "total_executions": len(executions),
        "successful_executions": sum(1 for e in executions if e.get("success")),
        "categories": {
            category: {
                "count": len([p for p in playbooks if p.category == category]),
                "avg_success_rate": sum(
                    p.success_count / max(1, p.success_count + p.failure_count)
                    for p in playbooks if p.category == category
                ) / max(1, len([p for p in playbooks if p.category == category]))
            }
            for category in set(p.category for p in playbooks)
        }
    }





