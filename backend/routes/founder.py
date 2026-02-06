
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

# --- Mocks for Dependencies ---
class User(BaseModel):
    id: str = "founder"
    role: str = "founder"

async def get_current_founder() -> User:
    # In reality, verify JWT token and role
    return User()

# Models
class BrainMode(BaseModel):
    mode: str  # local, hybrid, cloud

class ApprovalDecision(BaseModel):
    action: str  # approve, reject, approve_always

# Service Stubs
async def get_active_agent_count(): return 48
async def get_online_departments(): return 8
async def get_pending_approval_count(): return 3
async def get_system_health(): return "healthy"
async def get_local_models(): return ["llama3", "mistral"]
async def get_cloud_models(): return ["gpt-4", "claude-3-opus"]
async def get_active_model(): return "hybrid-auto"
async def get_brain_mode(): return "hybrid"
async def get_autopilot_status(): return False
async def get_approval_queue(): return []
async def get_recent_decisions(): return []
async def get_integrity_score(): return 98
async def get_threats_blocked(): return 12
async def get_last_audit(): return datetime.now().isoformat()
async def get_token_supply(): return 1000000
async def get_treasury_balance(): return 50000.00
async def get_daily_cost(): return 12.50

async def validate_mode_transition(mode): pass
async def set_brain_mode_setting(mode): pass
async def emit_event(name, data): pass
async def set_autopilot(enabled): pass

class MockAudit:
    async def log(self, data): print(f"Audit: {data}")
audit = MockAudit()

async def get_approval(id): 
    class Appr:
        skill_id = "test_skill"
    return Appr()

async def execute_approved_action(approval): pass
async def update_approval_status(id, status): pass
async def set_auto_approve(skill_id): pass


@router.get("/founder/control-panel")
async def get_control_panel(current_user: User = Depends(get_current_founder)):
    """Get founder control panel data"""
    
    return {
        "system_status": {
            "agents_active": await get_active_agent_count(),
            "departments_online": await get_online_departments(),
            "pending_approvals": await get_pending_approval_count(),
            "system_health": await get_system_health(),
        },
        "brain_status": {
            "local_models": await get_local_models(),
            "cloud_models": await get_cloud_models(),
            "active_model": await get_active_model(),
            "mode": await get_brain_mode(),  # "local" | "hybrid" | "cloud"
        },
        "governance": {
            "autopilot_enabled": await get_autopilot_status(),
            "approval_queue": await get_approval_queue(),
            "recent_decisions": await get_recent_decisions(),
        },
        "security": {
            "integrity_score": await get_integrity_score(),
            "threats_blocked": await get_threats_blocked(),
            "last_audit": await get_last_audit(),
        },
        "economics": {
            "token_supply": await get_token_supply(),
            "treasury_balance": await get_treasury_balance(),
            "daily_cost": await get_daily_cost(),
        }
    }

@router.post("/founder/brain/mode")
async def set_brain_mode(
    mode: BrainMode,
    current_user: User = Depends(get_current_founder)
):
    """Set brain mode: local_only, hybrid, cloud_first"""
    
    await validate_mode_transition(mode.mode)
    
    await set_brain_mode_setting(mode.mode)
    
    # Emit event
    await emit_event("brain.mode.changed", {
        "mode": mode.mode,
        "changed_by": current_user.id,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    return {"status": "success", "mode": mode.mode}

@router.post("/founder/governance/autopilot")
async def toggle_autopilot(
    enabled: bool,
    current_user: User = Depends(get_current_founder)
):
    """Toggle AGI Autopilot"""
    
    await set_autopilot(enabled)
    
    await audit.log({
        "type": "autopilot.toggled",
        "enabled": enabled,
        "by": current_user.id
    })
    
    return {"status": "success", "autopilot": enabled}

@router.post("/founder/approvals/{approval_id}/decide")
async def decide_approval(
    approval_id: str,
    decision: ApprovalDecision,
    current_user: User = Depends(get_current_founder)
):
    """Approve or reject a pending approval"""
    
    approval = await get_approval(approval_id)
    
    if decision.action == "approve":
        await execute_approved_action(approval)
        await update_approval_status(approval_id, "approved")
    elif decision.action == "reject":
        await update_approval_status(approval_id, "rejected")
    elif decision.action == "approve_always":
        await set_auto_approve(approval.skill_id)
        await execute_approved_action(approval)
    
    return {"status": "success", "action": decision.action}
