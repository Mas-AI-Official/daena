"""
Skills API Routes — /api/v1/skills/*

Exposes the Skill Registry to the Control Plane frontend and to other agents via MCP.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

# Import registry singleton
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from services.skill_registry import get_skill_registry

router = APIRouter(prefix="/api/v1/skills", tags=["skills"])


# ─── REQUEST / RESPONSE MODELS ─────────────────────────────────────

class SkillCreateRequest(BaseModel):
    name: str = Field(..., description="Unique slug for the skill (e.g. 'parse_json')")
    display_name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="What this skill does")
    category: str = Field(..., description="Category: filesystem|network|code_exec|data_transform|external_api|ai_tool|security|custom")
    creator: str = Field(default="daena", description="Who is creating: founder|daena|council|agent")
    creator_agent_id: str = Field(default="daena", description="Agent ID of the creator")
    input_schema: Dict[str, Any] = Field(..., description="JSON Schema for inputs")
    output_schema: Dict[str, Any] = Field(..., description="JSON Schema for outputs")
    code_body: str = Field(..., description="The executable Python code for this skill")
    dependencies: Optional[List[str]] = Field(default=[], description="Skill IDs this skill depends on")
    allowed_agents: Optional[List[str]] = Field(default=[], description="Agent IDs allowed to use ([] = all)")


class SkillTestRequest(BaseModel):
    test_inputs: Dict[str, Any] = Field(..., description="Inputs to test the skill with")


class ApprovalRequest(BaseModel):
    approver: str = Field(default="founder")
    notes: str = Field(default="")


class RejectionRequest(BaseModel):
    reason: str = Field(..., description="Why the skill was rejected")
    rejector: str = Field(default="founder")


# ─── ROUTES ────────────────────────────────────────────────────────

@router.get("/")
async def list_skills(status: Optional[str] = None, category: Optional[str] = None):
    """List all skills, optionally filtered by status or category."""
    registry = get_skill_registry()
    return {
        "skills": registry.list_skills(status_filter=status, category_filter=category),
        "count": len(registry.list_skills(status_filter=status, category_filter=category))
    }


@router.get("/stats")
async def get_stats():
    """Registry-wide statistics for the dashboard."""
    registry = get_skill_registry()
    return registry.get_stats()


@router.get("/health")
async def health():
    """Health check for skill registry."""
    registry = get_skill_registry()
    stats = registry.get_stats()
    return {"status": "healthy", "total_skills": stats["total"], "active": stats["active"]}


@router.get("/{skill_id}")
async def get_skill(skill_id: str):
    """Get a single skill by ID."""
    registry = get_skill_registry()
    skill = registry.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill {skill_id} not found")
    return skill


@router.get("/by-name/{name}")
async def get_skill_by_name(name: str):
    """Get a skill by its unique name."""
    registry = get_skill_registry()
    skill = registry.get_skill_by_name(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    return skill


@router.post("/create")
async def create_skill(payload: SkillCreateRequest):
    """
    Create a new skill.
    - Founder: low/medium risk → ACTIVE immediately
    - Daena/Agent: → PENDING_REVIEW → needs approval
    """
    registry = get_skill_registry()
    result = registry.create_skill(payload.dict())
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/{skill_id}/test")
async def test_skill(skill_id: str, payload: SkillTestRequest):
    """Run a skill in sandbox mode with the given test inputs."""
    registry = get_skill_registry()
    result = registry.test_skill_sandbox(skill_id, payload.test_inputs)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/{skill_id}/approve")
async def approve_skill(skill_id: str, payload: ApprovalRequest):
    """Approve a pending skill (Founder action)."""
    registry = get_skill_registry()
    result = registry.approve_skill(skill_id, payload.approver, payload.notes)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/{skill_id}/reject")
async def reject_skill(skill_id: str, payload: RejectionRequest):
    """Reject a pending skill."""
    registry = get_skill_registry()
    result = registry.reject_skill(skill_id, payload.reason, payload.rejector)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/{skill_id}/deprecate")
async def deprecate_skill(skill_id: str, reason: str = ""):
    """Deprecate an active skill."""
    registry = get_skill_registry()
    result = registry.deprecate_skill(skill_id, reason)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/{skill_id}/use")
async def record_usage(skill_id: str):
    """Record that a skill was invoked (called by execution engine)."""
    registry = get_skill_registry()
    registry.record_usage(skill_id)
    return {"recorded": True}
