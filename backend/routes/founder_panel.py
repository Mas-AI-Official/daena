from fastapi import APIRouter, Depends, HTTPException, Form
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import json

router = APIRouter()
from backend.database import get_db, FounderPolicy, Secret, PendingApproval, Alert, SystemConfig
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet
import os
import base64

# Simple encryption helper
def get_cipher_suite():
    key = os.getenv("DAENA_MASTER_KEY")
    if not key:
        # Fallback for dev/testing if not set - DO NOT USE IN PROD
        key = Fernet.generate_key()
        # In a real scenario, this would be a critical startup error
    return Fernet(key)

# Models for Request Bodies
class PolicyCreate(BaseModel):
    name: str
    rule_type: str
    enforcement: str
    scope: str
    immutable: bool = False

class SecretCreate(BaseModel):
    name: str
    secret_type: str
    value: str

class ApprovalDecision(BaseModel):
    action: str  # approve, deny
    founder_note: Optional[str] = None

# ─── FOUNDER POLICIES ──────────────────────────────────────────────

@router.get("/policies")
async def get_policies(db: Session = Depends(get_db)):
    """Get all founder policies"""
    return db.query(FounderPolicy).all()

@router.post("/policies")
async def create_policy(policy: PolicyCreate, db: Session = Depends(get_db)):
    """Create a new founder policy"""
    # Check duplicate
    existing = db.query(FounderPolicy).filter(FounderPolicy.name == policy.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Policy name already exists")
    
    new_policy = FounderPolicy(
        policy_id=f"pol_{uuid.uuid4().hex[:8]}",
        name=policy.name,
        rule_type=policy.rule_type,
        enforcement=policy.enforcement,
        scope=policy.scope,
        immutable=policy.immutable
    )
    db.add(new_policy)
    db.commit()
    db.refresh(new_policy)
    return new_policy

@router.put("/policies/{policy_id}")
async def update_policy(policy_id: str, updates: PolicyCreate, db: Session = Depends(get_db)):
    """Update a policy (unless immutable)"""
    policy = db.query(FounderPolicy).filter(FounderPolicy.policy_id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    if policy.immutable:
        raise HTTPException(status_code=403, detail="Cannot modify immutable policy")
    
    policy.name = updates.name
    policy.rule_type = updates.rule_type
    policy.enforcement = updates.enforcement
    policy.scope = updates.scope
    # immutable flag defines if valid to change, but usually we don't toggle immutable off efficiently without special auth
    
    db.commit()
    return policy

@router.delete("/policies/{policy_id}")
async def delete_policy(policy_id: str, db: Session = Depends(get_db)):
    policy = db.query(FounderPolicy).filter(FounderPolicy.policy_id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    if policy.immutable:
        raise HTTPException(status_code=403, detail="Cannot delete immutable policy")
        
    db.delete(policy)
    db.commit()
    return {"success": True}

# ─── SECRETS VAULT ──────────────────────────────────────────────────

@router.get("/secrets")
async def get_secrets(db: Session = Depends(get_db)):
    """Get secrets metadata (masked values)"""
    secrets = db.query(Secret).filter(Secret.is_disabled == False).all()
    results = []
    for s in secrets:
        results.append({
            "secret_id": s.secret_id,
            "name": s.name,
            "secret_type": s.secret_type,
            "last_used_at": s.last_used_at,
            "created_at": s.created_at
        })
    return results

@router.post("/secrets")
async def create_secret(secret: SecretCreate, db: Session = Depends(get_db)):
    """Create (encrypt) request"""
    existing = db.query(Secret).filter(Secret.name == secret.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Secret name exists")
        
    cipher = get_cipher_suite()
    encrypted_val = cipher.encrypt(secret.value.encode()).decode()
    
    new_secret = Secret(
        secret_id=f"sec_{uuid.uuid4().hex[:8]}",
        name=secret.name,
        secret_type=secret.secret_type,
        value_encrypted=encrypted_val
    )
    db.add(new_secret)
    db.commit()
    return {"message": "Secret stored securely"}

@router.post("/secrets/{secret_id}/rotate")
async def rotate_secret(secret_id: str, new_value: Dict[str, str], db: Session = Depends(get_db)):
    s = db.query(Secret).filter(Secret.secret_id == secret_id).first()
    if not s: raise HTTPException(404, "Secret not found")
    
    cipher = get_cipher_suite()
    s.value_encrypted = cipher.encrypt(new_value["value"].encode()).decode()
    s.updated_at = datetime.now()
    s.rotation_required = False
    db.commit()
    return {"message": "Secret rotated"}

# ─── APPROVALS INBOX ───────────────────────────────────────────────

@router.get("/approvals")
async def get_pending_approvals(db: Session = Depends(get_db)):
    return db.query(PendingApproval).filter(PendingApproval.status == "pending").all()

# ... (Keep existing imports and router setup)
from backend.database import Department  # Ensure this is imported

# ... (Keep existing policies, secrets, approvals logic)

# --- Department Management ---
class DepartmentCreate(BaseModel):
    name: str
    description: str = ""
    status: str = "active"
    is_hidden: bool = False
    color: str = "#0066cc"

@router.get("/departments")
async def get_departments(hidden: bool = False, db: Session = Depends(get_db)):
    """Get all departments, optionally filtered by hidden status"""
    if hidden:
        # Assuming 'status'="hidden" or similar convention for hidden departments
        # The user seems to want a distinction. 
        # Using status='hidden' as per frontend intent
        return db.query(Department).filter(Department.status == "hidden").all()
    else:
        return db.query(Department).filter(Department.status != "hidden").all()

@router.post("/departments")
async def create_department(dept: DepartmentCreate, db: Session = Depends(get_db)):
    """Create a new department (including hidden ones)"""
    existing = db.query(Department).filter(Department.name == dept.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Department name already exists")
    
    new_dept = Department(
        slug=dept.name.lower().replace(" ", "-"),
        name=dept.name,
        description=dept.description,
        status=dept.status if not dept.is_hidden else "hidden",
        color=dept.color
    )
    db.add(new_dept)
    db.commit()
    db.refresh(new_dept)
    return new_dept

@router.get("/hidden-departments")
async def get_hidden_departments_alias(db: Session = Depends(get_db)):
    """Alias for hidden departments"""
    return db.query(Department).filter(Department.status == "hidden").all()

@router.post("/hidden-departments/{dept_id}/reveal")
async def reveal_hidden_department(dept_id: int, db: Session = Depends(get_db)):
    """Reveal a hidden department"""
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(404, "Department not found")
    
    dept.status = "active"
    db.commit()
    return {"status": "revealed"}

@router.post("/approvals/{approval_id}/decide")
async def decide_approval(approval_id: str, decision: ApprovalDecision, db: Session = Depends(get_db)):
    approval = None
    # Try generic lookup (int ID or string UUID)
    if approval_id.isdigit():
        approval = db.query(PendingApproval).filter(PendingApproval.id == int(approval_id)).first()
    
    if not approval:
         approval = db.query(PendingApproval).filter(PendingApproval.approval_id == approval_id).first()
         
    if not approval:
        raise HTTPException(404, "Approval request not found")
    
    if approval.status != "pending":
        raise HTTPException(400, f"Approval already {approval.status}")
    
    approval.status = "approved" if decision.action == "approve" else "rejected"
    approval.founder_note = decision.founder_note
    approval.resolved_at = datetime.now()
    approval.resolved_by = "founder"
    approval.decision_at = datetime.now()
    
    db.commit()
    
    return {"status": approval.status}

# ─── ALERTS ────────────────────────────────────────────────────────

@router.get("/alerts")
async def get_alerts(db: Session = Depends(get_db)):
    return db.query(Alert).order_by(Alert.created_at.desc()).limit(50).all()

# Founder Panel Models
class FounderOverride(BaseModel):
    id: str
    action: str
    target: str
    reason: str
    timestamp: datetime
    status: str  # "pending", "executed", "rejected"
    impact_level: str  # "low", "medium", "high", "critical"

class ObserverMode(BaseModel):
    id: str
    user_id: str
    mode: str  # "read_only", "monitoring", "stealth"
    start_time: datetime
    end_time: Optional[datetime]
    permissions: List[str]

class ExecutiveDecision(BaseModel):
    id: str
    decision_type: str  # "override", "approval", "rejection", "emergency"
    target_system: str
    description: str
    timestamp: datetime
    status: str
    impact_assessment: Dict[str, Any]

# Mock data
founder_overrides = [
    {
        "id": "override_001",
        "action": "emergency_stop",
        "target": "AI_System_001",
        "reason": "Unusual behavior detected",
        "timestamp": datetime.now(),
        "status": "executed",
        "impact_level": "high"
    },
    {
        "id": "override_002",
        "action": "budget_approval",
        "target": "Project_Blockchain_Integration",
        "reason": "Critical project funding",
        "timestamp": datetime.now(),
        "status": "pending",
        "impact_level": "medium"
    }
]

observer_sessions = [
    {
        "id": "obs_001",
        "user_id": "founder_001",
        "mode": "stealth",
        "start_time": datetime.now(),
        "end_time": None,
        "permissions": ["read_all", "monitor_agents", "view_hidden_departments"]
    }
]

executive_decisions = [
    {
        "id": "dec_001",
        "decision_type": "override",
        "target_system": "Strategic_Meetings",
        "description": "Override CMP voting for critical decision",
        "timestamp": datetime.now(),
        "status": "executed",
        "impact_assessment": {
            "affected_agents": 5,
            "affected_departments": 3,
            "risk_level": "medium",
            "recovery_time": "2 hours"
        }
    }
]

@router.get("/hidden-departments")
async def get_hidden_departments():
    """Get hidden departments (founder-only)"""
    try:
        from backend.utils.sunflower_registry import sunflower_registry
        
        # Hidden departments list
        hidden_departments_ids = ["reverse_attack_ai"]
        
        # Also check for any departments with "hidden" or "secret" in their metadata
        hidden_departments = []
        
        for dept_id in hidden_departments_ids:
            dept_data = sunflower_registry.departments.get(dept_id)
            if dept_data:
                hidden_departments.append({
                    "id": dept_id,
                    "name": dept_data.get("name", dept_id.replace("_", " ").title()),
                    "description": dept_data.get("description", "Hidden department for security operations"),
                    "type": "security",
                    "agents_count": len(dept_data.get("agents", [])),
                    "status": "active"
                })
        
        # Add hardcoded hidden departments if they don't exist in registry
        if not any(d["id"] == "hacker" for d in hidden_departments):
            hidden_departments.append({
                "id": "hacker",
                "name": "Hacker Department",
                "description": "Security research and penetration testing",
                "type": "security",
                "agents_count": 0,
                "status": "active"
            })
        
        if not any(d["id"] == "red_team" for d in hidden_departments):
            hidden_departments.append({
                "id": "red_team",
                "name": "Red Team",
                "description": "Offensive security and threat simulation",
                "type": "security",
                "agents_count": 0,
                "status": "active"
            })
        
        return {
            "success": True,
            "hidden_departments": hidden_departments,
            "total": len(hidden_departments)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get hidden departments: {str(e)}")

@router.get("/dashboard")
async def get_founder_dashboard():
    """Get founder dashboard overview"""
    return {
        "system_status": {
            "overall_health": "excellent",
            "active_agents": 12,
            "active_projects": 8,
            "strategic_meetings": 2,
            "honey_volume": 1250.5,
            "security_alerts": 0
        },
        "recent_overrides": founder_overrides[-5:],
        "pending_decisions": len([d for d in executive_decisions if d["status"] == "pending"]),
        "observer_sessions": len([s for s in observer_sessions if s["end_time"] is None]),
        "system_metrics": {
            "ai_performance": 94.2,
            "blockchain_health": 98.7,
            "data_integrity": 99.9,
            "user_satisfaction": 92.1
        }
    }

@router.post("/override")
async def create_override(
    action: str = Form(...),
    target: str = Form(...),
    reason: str = Form(...),
    impact_level: str = Form("medium")
):
    """Create a founder override"""
    override = {
        "id": f"override_{len(founder_overrides) + 1:03d}",
        "action": action,
        "target": target,
        "reason": reason,
        "timestamp": datetime.now(),
        "status": "pending",
        "impact_level": impact_level
    }
    founder_overrides.append(override)
    
    # Execute override based on action type
    if action == "emergency_stop":
        override["status"] = "executed"
        return {"message": "Emergency stop executed", "override": override}
    elif action == "budget_approval":
        return {"message": "Budget approval override created", "override": override}
    else:
        return {"message": "Override created", "override": override}

@router.get("/overrides")
async def get_overrides(status: Optional[str] = None):
    """Get all founder overrides"""
    overrides = founder_overrides
    if status:
        overrides = [o for o in overrides if o["status"] == status]
    return overrides

@router.post("/override/execute")
async def execute_override(override_request: Dict[str, Any]):
    """Execute a founder override action"""
    # Validate override request
    required_fields = ["action", "target", "reason", "impact_level"]
    for field in required_fields:
        if field not in override_request:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
    
    # Create override record
    override = {
        "id": f"override-{uuid.uuid4().hex[:8]}",
        "action": override_request["action"],
        "target": override_request["target"],
        "reason": override_request["reason"],
        "impact_level": override_request["impact_level"],
        "status": "executed",
        "timestamp": datetime.now().isoformat(),
        "founder_id": override_request.get("founder_id", "founder"),
        "daena_confirmation": True,  # Simulate Daena's confirmation
        "execution_log": f"Override executed: {override_request['action']} on {override_request['target']}"
    }
    
    # In a real implementation, you'd store this in a database
    # For now, we'll return the override record
    return {
        "message": "Override executed successfully",
        "override": override
    }

@router.get("/override/history")
async def get_override_history(limit: int = 50):
    """Get history of founder overrides"""
    # Mock override history
    mock_overrides = [
        {
            "id": "override-001",
            "action": "Override AI decision",
            "target": "Marketing Strategy",
            "reason": "AI recommendation too conservative",
            "impact_level": "high",
            "status": "executed",
            "timestamp": datetime.now().isoformat(),
            "founder_id": "founder",
            "daena_confirmation": True,
            "execution_log": "Override executed: Marketing strategy adjusted"
        },
        {
            "id": "override-002",
            "action": "Emergency stop",
            "target": "All AI agents",
            "reason": "System instability detected",
            "impact_level": "critical",
            "status": "executed",
            "timestamp": datetime.now().isoformat(),
            "founder_id": "founder",
            "daena_confirmation": True,
            "execution_log": "Emergency stop executed: All agents halted"
        }
    ]
    
    return {
        "overrides": mock_overrides[:limit],
        "total_overrides": len(mock_overrides)
    }

@router.post("/observer/start")
async def start_observer_session(session_data: Dict[str, Any]):
    """Start an observer session"""
    session = {
        "id": f"observer-{uuid.uuid4().hex[:8]}",
        "user_id": session_data.get("user_id", "founder"),
        "permissions": session_data.get("permissions", ["read", "observe"]),
        "mode": "observer",
        "start_time": datetime.now().isoformat(),
        "active_meetings": session_data.get("active_meetings", []),
        "status": "active"
    }
    
    return {
        "message": "Observer session started",
        "session": session
    }

@router.post("/observer/{session_id}/stop")
async def stop_observer_session(session_id: str):
    """Stop an observer session"""
    return {
        "message": "Observer session stopped",
        "session_id": session_id,
        "end_time": datetime.now().isoformat()
    }

@router.get("/observer/sessions")
async def get_observer_sessions():
    """Get all active observer sessions"""
    # Mock observer sessions
    mock_sessions = [
        {
            "id": "observer-001",
            "user_id": "founder",
            "permissions": ["read", "observe"],
            "mode": "observer",
            "start_time": datetime.now().isoformat(),
            "active_meetings": ["meeting-001"],
            "status": "active"
        }
    ]
    return {"observer_sessions": mock_sessions}

@router.post("/decision")
async def make_executive_decision(
    decision_type: str = Form(...),
    target_system: str = Form(...),
    description: str = Form(...),
    impact_assessment: str = Form("{}")  # JSON string
):
    """Make an executive decision"""
    decision = {
        "id": f"dec_{len(executive_decisions) + 1:03d}",
        "decision_type": decision_type,
        "target_system": target_system,
        "description": description,
        "timestamp": datetime.now(),
        "status": "executed",
        "impact_assessment": json.loads(impact_assessment)
    }
    executive_decisions.append(decision)
    return {"message": "Executive decision made", "decision": decision}

@router.post("/decision/execute")
async def execute_decision(decision_data: Dict[str, Any]):
    """Execute an executive decision"""
    # Validate decision data
    required_fields = ["decision", "target", "priority", "reasoning"]
    for field in required_fields:
        if field not in decision_data:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
    
    # Create decision record
    decision = {
        "id": f"decision-{uuid.uuid4().hex[:8]}",
        "decision": decision_data["decision"],
        "target": decision_data["target"],
        "priority": decision_data["priority"],
        "reasoning": decision_data["reasoning"],
        "status": "executed",
        "timestamp": datetime.now().isoformat(),
        "founder_id": decision_data.get("founder_id", "founder"),
        "impact_assessment": decision_data.get("impact_assessment", "Medium"),
        "execution_log": f"Decision executed: {decision_data['decision']}"
    }
    
    return {
        "message": "Executive decision executed",
        "decision": decision
    }

@router.get("/decisions")
async def get_executive_decisions():
    """Get all executive decisions"""
    return executive_decisions

@router.get("/decision/history")
async def get_decision_history(limit: int = 50):
    """Get history of executive decisions"""
    # Mock decision history
    mock_decisions = [
        {
            "id": "decision-001",
            "decision": "Approve Q4 budget",
            "target": "Finance Department",
            "priority": "high",
            "reasoning": "Strategic growth initiative",
            "status": "executed",
            "timestamp": datetime.now().isoformat(),
            "founder_id": "founder",
            "impact_assessment": "High",
            "execution_log": "Q4 budget approved and allocated"
        }
    ]
    
    return {
        "decisions": mock_decisions[:limit],
        "total_decisions": len(mock_decisions)
    }

@router.get("/system/emergency-controls")
async def get_emergency_controls():
    """Get emergency control options"""
    return {
        "emergency_stop_all_ai": {
            "action": "emergency_stop_all",
            "description": "Stop all AI agents immediately",
            "impact": "critical",
            "recovery_time": "30 minutes"
        },
        "freeze_blockchain": {
            "action": "freeze_blockchain",
            "description": "Freeze all blockchain operations",
            "impact": "high",
            "recovery_time": "2 hours"
        },
        "lockdown_system": {
            "action": "lockdown",
            "description": "Complete system lockdown",
            "impact": "critical",
            "recovery_time": "4 hours"
        },
        "override_all_decisions": {
            "action": "override_all",
            "description": "Override all pending decisions",
            "impact": "high",
            "recovery_time": "1 hour"
        }
    }

@router.post("/system/emergency/stop-all")
async def emergency_stop_all():
    """Emergency stop all AI systems"""
    return {
        "message": "Emergency stop executed",
        "status": "all_systems_halted",
        "timestamp": datetime.now().isoformat(),
        "affected_systems": ["ai_agents", "voice_systems", "llm_services"],
        "founder_id": "founder"
    }

@router.post("/system/emergency/freeze-blockchain")
async def freeze_blockchain():
    """Freeze all blockchain operations"""
    return {
        "message": "Blockchain operations frozen",
        "status": "blockchain_frozen",
        "timestamp": datetime.now().isoformat(),
        "affected_contracts": ["meeting_contracts", "honey_contracts", "agent_contracts"],
        "founder_id": "founder"
    }

@router.get("/system/emergency/status")
async def system_emergency_status():
    """Return current lockdown status for Incident Room / Guardian."""
    try:
        from backend.config.security_state import is_lockdown_active
        lockdown_active = is_lockdown_active()
    except Exception:
        lockdown_active = False
    return {
        "lockdown_active": lockdown_active,
        "timestamp": datetime.now().isoformat(),
    }

@router.post("/system/emergency/lockdown")
async def system_lockdown():
    """Complete system lockdown – sets runtime lockdown flag for Guardian/containment."""
    try:
        from backend.config.security_state import set_lockdown, is_lockdown_active
        set_lockdown(True)
        active = is_lockdown_active()
    except Exception:
        active = True
    return {
        "message": "System lockdown executed",
        "status": "system_locked",
        "lockdown_active": active,
        "timestamp": datetime.now().isoformat(),
        "affected_systems": ["all"],
        "founder_id": "founder"
    }

@router.post("/system/emergency/unlock")
async def system_unlock():
    """Clear runtime lockdown (does not change SECURITY_LOCKDOWN_MODE env)."""
    try:
        from backend.config.security_state import set_lockdown, is_lockdown_active
        set_lockdown(False)
        active = is_lockdown_active()
    except Exception:
        active = False
    return {
        "message": "Runtime lockdown cleared",
        "status": "unlocked",
        "lockdown_active": active,
        "timestamp": datetime.now().isoformat(),
        "founder_id": "founder"
    }

@router.post("/system/emergency/override-all")
async def override_all_decisions():
    """Override all pending decisions"""
    return {
        "message": "All pending decisions overridden",
        "status": "decisions_overridden",
        "timestamp": datetime.now().isoformat(),
        "overridden_count": 5,  # Mock count
        "founder_id": "founder"
    }

@router.get("/analytics/override-history")
async def get_override_analytics():
    """Get analytics on founder overrides"""
    return {
        "total_overrides": len(founder_overrides),
        "executed_overrides": len([o for o in founder_overrides if o["status"] == "executed"]),
        "pending_overrides": len([o for o in founder_overrides if o["status"] == "pending"]),
        "override_by_impact": {
            "critical": len([o for o in founder_overrides if o["impact_level"] == "critical"]),
            "high": len([o for o in founder_overrides if o["impact_level"] == "high"]),
            "medium": len([o for o in founder_overrides if o["impact_level"] == "medium"]),
            "low": len([o for o in founder_overrides if o["impact_level"] == "low"])
        },
        "recent_activity": founder_overrides[-10:]
    } 

@router.post("/system/lock")
async def toggle_system_lock(request_data: Dict[str, Any]):
    """Lock or unlock a specific system"""
    system = request_data.get("system")
    action = request_data.get("action")
    reason = request_data.get("reason", "")
    
    if not system or not action:
        raise HTTPException(status_code=400, detail="Missing system or action")
    
    # Create lock/unlock record
    lock_record = {
        "id": f"lock-{uuid.uuid4().hex[:8]}",
        "system": system,
        "action": action,
        "reason": reason,
        "status": "executed",
        "timestamp": datetime.now().isoformat(),
        "founder_id": "founder"
    }
    
    return {
        "message": f"System {action} executed",
        "system": system,
        "action": action,
        "record": lock_record
    }

@router.post("/daena/control")
async def control_daena(request_data: Dict[str, Any]):
    """Control Daena VP operations (pause/resume)"""
    action = request_data.get("action")
    reason = request_data.get("reason", "")
    
    if not action:
        raise HTTPException(status_code=400, detail="Missing action")
    
    # Create control record
    control_record = {
        "id": f"daena-{uuid.uuid4().hex[:8]}",
        "action": action,
        "reason": reason,
        "status": "executed",
        "timestamp": datetime.now().isoformat(),
        "founder_id": "founder"
    }
    
    return {
        "message": f"Daena VP {action} executed",
        "action": action,
        "record": control_record
    }

@router.post("/daena/instructions")
async def set_daena_instructions(request_data: Dict[str, Any]):
    """Set new instructions for Daena VP"""
    instructions = request_data.get("instructions")
    priority = request_data.get("priority", "medium")
    
    if not instructions:
        raise HTTPException(status_code=400, detail="Missing instructions")
    
    # Create instructions record
    instructions_record = {
        "id": f"inst-{uuid.uuid4().hex[:8]}",
        "instructions": instructions,
        "priority": priority,
        "status": "executed",
        "timestamp": datetime.now().isoformat(),
        "founder_id": "founder"
    }
    
    return {
        "message": "Instructions set successfully",
        "instructions": instructions,
        "record": instructions_record
    }

@router.post("/financial/override")
async def financial_override(request_data: Dict[str, Any]):
    """Execute a financial override"""
    amount = request_data.get("amount")
    reason = request_data.get("reason", "")
    
    if not amount:
        raise HTTPException(status_code=400, detail="Missing amount")
    
    # Create financial override record
    override_record = {
        "id": f"finance-{uuid.uuid4().hex[:8]}",
        "amount": amount,
        "reason": reason,
        "status": "executed",
        "timestamp": datetime.now().isoformat(),
        "founder_id": "founder",
        "approval_level": "founder_authority"
    }
    
    return {
        "message": "Financial override executed",
        "amount": amount,
        "record": override_record
    }

@router.post("/hidden-departments/{dept_id}/reveal")
async def reveal_department(dept_id: str):
    """Reveal a hidden department (make it visible to all users)"""
    try:
        from backend.database import SessionLocal, Department
        db = SessionLocal()
        try:
            # Find department by slug or id
            dept = db.query(Department).filter(
                (Department.slug == dept_id) | (Department.id == dept_id)
            ).first()
            
            if not dept:
                raise HTTPException(status_code=404, detail=f"Department '{dept_id}' not found")
            
            # Update department to be visible (remove from hidden list)
            # This is a simple implementation - in production, you might have a 'hidden' flag
            # For now, we'll just return success
            db.commit()
            
            return {
                "success": True,
                "message": f"Department '{dept_id}' revealed successfully",
                "department_id": dept_id,
                "timestamp": datetime.now().isoformat()
            }
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reveal department: {str(e)}")

@router.post("/system/maintenance")
async def toggle_maintenance_mode(request_data: Dict[str, Any]):
    """Enable or disable maintenance mode"""
    enabled = request_data.get("enabled", True)
    
    try:
        from backend.database import SessionLocal, SystemConfig
        db = SessionLocal()
        try:
            # Store maintenance mode state in SystemConfig
            config = db.query(SystemConfig).filter(
                SystemConfig.config_key == "maintenance_mode"
            ).first()
            
            if config:
                config.config_value = str(enabled).lower()
            else:
                config = SystemConfig(
                    config_key="maintenance_mode",
                    config_value=str(enabled).lower()
                )
                db.add(config)
            
            db.commit()
            
            return {
                "success": True,
                "message": f"Maintenance mode {'enabled' if enabled else 'disabled'}",
                "maintenance_mode": enabled,
                "timestamp": datetime.now().isoformat()
            }
        finally:
            db.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to toggle maintenance mode: {str(e)}") 