
"""
Core Dispatcher with Governance
Handles skill execution with policy checks and approval workflows.
"""
from typing import Dict, Any, Optional
from fastapi import HTTPException
from backend.services.auth_service import User
from backend.services.skill_registry import get_skill_registry
from backend.tools.registry import execute_tool
from backend.core.websocket_manager import websocket_manager
# Assuming approval mechanism exists or stub exists
# from backend.services.governance import create_approval_request (if exists)

async def dispatch_with_governance(skill_id: str, caller: User, params: dict):
    """Execute skill with governance checks"""
    registry = get_skill_registry()
    skill = registry.get_skill(skill_id)
    
    if not skill:
        # Fallback to check static skills if any, or error
        raise HTTPException(status_code=404, detail="Skill not found")

    # Check operators
    allowed_operators = skill.get("allowed_operators", ["founder", "daena"])
    # If caller.role is not in allowed operators (case insensitive)
    if caller.role.lower() not in [op.lower() for op in allowed_operators]:
        await websocket_manager.emit_event("policy.blocked", {
            "skill_id": skill_id,
            "caller": caller.user_id,
            "reason": "Not in operators list"
        })
        raise HTTPException(status_code=403, detail=f"{caller.role} cannot execute {skill['name']}")
    
    # Check approval needed
    risk_level = skill.get("risk_level", "medium")
    approval_policy = skill.get("approval_policy", "auto")
    
    needs_approval = False
    if risk_level in ["high", "critical"] and approval_policy != "auto":
        needs_approval = True
    
    if needs_approval:
        # Create approval request
        # Since we don't have the full governance service imported/confirmed, we'll mock the ID or try to use DB
        from backend.database import SessionLocal, PendingApproval
        import uuid
        
        approval_id = f"appr_{uuid.uuid4().hex[:8]}"
        
        db = SessionLocal()
        try:
             approval = PendingApproval(
                 approval_id=approval_id,
                 executor_id=caller.user_id,
                 executor_type="user",
                 tool_name=skill.get("name"),
                 action="execute",
                 args_json=params,
                 impact_level=risk_level,
                 status="pending"
             )
             db.add(approval)
             db.commit()
        finally:
             db.close()

        await websocket_manager.emit_event("approval.required", {
            "approval_id": approval_id,
            "skill_name": skill.get("name"),
            "risk_level": risk_level,
            "requester": caller.user_id
        })
        return {"status": "pending_approval", "approval_id": approval_id}
    
    # Execute
    # Map skill to tool. If skill has a 'code_body' it might be a dynamic skill or mapped to a tool.
    # The current registry implementation suggests skills map to tools or code.
    # We will try to execute it using `execute_tool` if it maps to a tool name, or assume custom execution logic.
    # For now, we assume skill name maps to tool name or category helps.
    
    # Simple mapping logic based on skill name match (registry usually ensures this)
    tool_name = skill.get("name")
    
    try:
        result = await execute_tool(
            tool_name=tool_name,
            args=params,
            department=None,
            agent_id=None,
            reason=f"skill_dispatch:{skill_id}",
            trace_id=None,
            dry_run=False
        )
    except Exception as e:
         # Some skills might not be direct tools.
         # For this specific dispatcher we assume tool execution.
         raise HTTPException(status_code=500, detail=f"Execution failed: {e}")
    
    # Audit log
    await websocket_manager.emit_event("skill.executed", {
        "skill_id": skill_id,
        "caller": caller.user_id,
        "result": str(result)[:200] # truncate
    })
    
    return result
