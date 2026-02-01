"""
Skill Registry API Routes

Daena can propose, test, approve, and use skills dynamically.
Skills go through governance before activation.

Lifecycle: DRAFT → PENDING_REVIEW → SANDBOX_TEST → APPROVED → ACTIVE
"""

from fastapi import APIRouter, HTTPException, Body
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/skills", tags=["skills"])


def get_registry():
    """Get the skill registry singleton."""
    from backend.services.skill_registry import get_skill_registry
    return get_skill_registry()


# ============================================
# Skill CRUD
# ============================================

@router.get("/")
async def list_skills(
    status: Optional[str] = None,
    category: Optional[str] = None
) -> Dict[str, Any]:
    """List all skills, optionally filtered by status or category."""
    registry = get_registry()
    skills = registry.list_skills(status_filter=status, category_filter=category)
    return {
        "count": len(skills),
        "skills": skills
    }


@router.get("/stats")
async def get_stats() -> Dict[str, Any]:
    """Get skill registry statistics."""
    registry = get_registry()
    return registry.get_stats()


@router.get("/{skill_id}")
async def get_skill(skill_id: str) -> Dict[str, Any]:
    """Get a single skill by ID."""
    registry = get_registry()
    skill = registry.get_skill(skill_id)
    if not skill:
        raise HTTPException(404, f"Skill not found: {skill_id}")
    return skill


@router.get("/by-name/{name}")
async def get_skill_by_name(name: str) -> Dict[str, Any]:
    """Get a skill by its unique name."""
    registry = get_registry()
    skill = registry.get_skill_by_name(name)
    if not skill:
        raise HTTPException(404, f"Skill not found: {name}")
    return skill


@router.post("/")
async def create_skill(
    payload: Dict[str, Any] = Body(...)
) -> Dict[str, Any]:
    """
    Create a new skill.
    
    Required fields:
    - name: unique slug (e.g., "read_csv")
    - display_name: human-readable name
    - description: what the skill does
    - category: filesystem, network, code_exec, data_transform, external_api, ai_tool, security, custom
    - creator: founder, daena, council, agent
    - creator_agent_id: which agent proposed it
    - input_schema: JSON Schema for inputs
    - output_schema: JSON Schema for outputs
    - code_body: the executable code
    """
    registry = get_registry()
    result = registry.create_skill(payload)
    
    if "error" in result:
        raise HTTPException(400, result["error"])
    
    return result


# ============================================
# Skill Governance
# ============================================

@router.post("/{skill_id}/approve")
async def approve_skill(
    skill_id: str,
    approver: str = Body(default="founder"),
    notes: str = Body(default="")
) -> Dict[str, Any]:
    """Approve a pending skill (Founder or Council action)."""
    registry = get_registry()
    result = registry.approve_skill(skill_id, approver, notes)
    
    if "error" in result:
        raise HTTPException(400, result["error"])
    
    return result


@router.post("/{skill_id}/reject")
async def reject_skill(
    skill_id: str,
    reason: str = Body(...),
    rejector: str = Body(default="founder")
) -> Dict[str, Any]:
    """Reject a pending skill."""
    registry = get_registry()
    result = registry.reject_skill(skill_id, reason, rejector)
    
    if "error" in result:
        raise HTTPException(400, result["error"])
    
    return result


@router.post("/{skill_id}/deprecate")
async def deprecate_skill(
    skill_id: str,
    reason: str = Body(default="No longer needed")
) -> Dict[str, Any]:
    """Deprecate an active skill."""
    registry = get_registry()
    result = registry.deprecate_skill(skill_id, reason)
    
    if "error" in result:
        raise HTTPException(400, result["error"])
    
    return result


# ============================================
# Skill Testing & Execution
# ============================================

@router.post("/{skill_id}/test")
async def test_skill(
    skill_id: str,
    test_inputs: Dict[str, Any] = Body(default={})
) -> Dict[str, Any]:
    """
    Test a skill in sandbox mode.
    
    This runs the skill in an isolated environment and captures:
    - stdout/stderr
    - security flags
    - execution time
    """
    registry = get_registry()
    result = registry.test_skill_sandbox(skill_id, test_inputs)
    
    if "error" in result:
        raise HTTPException(400, result["error"])
    
    return result


@router.post("/{skill_id}/use")
async def use_skill(
    skill_id: str,
    inputs: Dict[str, Any] = Body(default={})
) -> Dict[str, Any]:
    """
    Execute a skill (must be ACTIVE).
    
    This records usage for analytics and calibration.
    """
    registry = get_registry()
    skill = registry.get_skill(skill_id)
    
    if not skill:
        raise HTTPException(404, f"Skill not found: {skill_id}")
    
    if skill["status"] != "active":
        raise HTTPException(400, f"Skill is not active. Status: {skill['status']}")
    
    # Record usage
    registry.record_usage(skill_id)
    
    # In production, this would actually execute the skill
    # For now, return success with placeholder
    return {
        "skill_id": skill_id,
        "skill_name": skill["name"],
        "inputs": inputs,
        "result": f"Skill '{skill['name']}' executed successfully",
        "note": "Full execution engine integration pending"
    }


# ============================================
# Discovery
# ============================================

@router.get("/category/{category}")
async def list_by_category(category: str) -> Dict[str, Any]:
    """List all active skills in a category."""
    registry = get_registry()
    skills = registry.list_skills(status_filter="active", category_filter=category)
    return {
        "category": category,
        "count": len(skills),
        "skills": skills
    }


@router.get("/pending-review")
async def list_pending_review() -> Dict[str, Any]:
    """List skills pending review (for governance dashboard)."""
    registry = get_registry()
    skills = registry.list_skills(status_filter="pending_review")
    return {
        "count": len(skills),
        "skills": skills
    }


@router.get("/self-created")
async def list_self_created() -> Dict[str, Any]:
    """List skills that Daena created herself (for learning metrics)."""
    registry = get_registry()
    all_skills = registry.list_skills()
    self_created = [s for s in all_skills if s.get("creator") == "daena"]
    return {
        "count": len(self_created),
        "skills": self_created
    }


# ============================================
# Health
# ============================================

@router.get("/health")
async def skill_registry_health() -> Dict[str, Any]:
    """Health check for skill registry."""
    registry = get_registry()
    stats = registry.get_stats()
    
    return {
        "status": "healthy",
        "total_skills": stats.get("total", 0),
        "active_skills": stats.get("active", 0),
        "pending_review": stats.get("pending_review", 0),
        "self_created": stats.get("self_created", 0)
    }
