"""
Approvals & Learning API Routes for Founder Panel

Provides endpoints for:
1. Viewing pending tool approvals
2. Approving/rejecting tool executions
3. Viewing learnings (today's, pending, permanent)
4. Approving/rejecting learnings
"""

from fastapi import APIRouter, HTTPException, Body, Query, Depends, Request
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import logging
from backend.database import SessionLocal, PendingApproval, FounderPolicy as DBPolicy, Secret as DBSecret
from backend.routes.founder import User, get_current_founder

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/founder", tags=["founder-panel"])


# ==================== APPROVALS ====================

class ApprovalAction(BaseModel):
    """Request model for approval actions."""
    approved: bool
    notes: Optional[str] = None


@router.get("/approvals")
async def get_pending_approvals(current_user: User = Depends(get_current_founder)) -> Dict[str, Any]:
    """Get all pending tool approvals."""
    try:
        from backend.database import SessionLocal, PendingApproval
        
        db = SessionLocal()
        try:
            approvals = db.query(PendingApproval).filter(
                PendingApproval.status == "pending"
            ).order_by(
                PendingApproval.created_at.desc()
            ).all()
            
            return {
                "success": True,
                "count": len(approvals),
                "approvals": [
                    {
                        "id": a.id,
                        "approval_id": a.approval_id,
                        "executor_id": a.executor_id,
                        "executor_type": a.executor_type,
                        "tool_name": a.tool_name,
                        "action": a.action,
                        "args": a.args_json,
                        "impact_level": a.impact_level,
                        "created_at": a.created_at.isoformat() if a.created_at else None
                    }
                    for a in approvals
                ]
            }
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error getting pending approvals: {e}")
        return {"success": False, "error": str(e), "approvals": []}


@router.post("/approvals/{approval_id}/decide")
async def decide_approval(
    approval_id: str,
    action: ApprovalAction
) -> Dict[str, Any]:
    """Approve or reject a pending tool execution."""
    from datetime import datetime
    
    try:
        from backend.database import SessionLocal, PendingApproval
        
        db = SessionLocal()
        try:
            approval = db.query(PendingApproval).filter(
                PendingApproval.approval_id == approval_id
            ).first()
            
            if not approval:
                raise HTTPException(status_code=404, detail="Approval not found")
            
            approval.status = "approved" if action.approved else "rejected"
            approval.resolved_at = datetime.utcnow()
            approval.resolved_by = "founder"
            
            db.commit()
            
            # If approved, execute the tool
            if action.approved:
                from backend.services.unified_tool_executor import unified_executor
                result = await unified_executor.execute(
                    tool_name=approval.tool_name,
                    action=approval.action,
                    args=approval.args_json or {},
                    executor_id=approval.executor_id,
                    skip_approval=True  # Already approved
                )
                return {
                    "success": True,
                    "status": "approved",
                    "execution_result": result
                }
            else:
                return {
                    "success": True,
                    "status": "rejected",
                    "message": f"Approval {approval_id} rejected"
                }
                
        finally:
            db.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing approval: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== LEARNINGS ====================

class LearningAction(BaseModel):
    """Request model for learning actions."""
    approved: bool
    make_permanent: bool = True


@router.get("/learnings")
async def get_learnings(
    request: Request, current_user: User = Depends(get_current_founder),
    filter: str = Query("pending", description="Filter: pending, today, all, permanent")
) -> Dict[str, Any]:
    """Get learnings with filter."""
    try:
        from backend.services.learning_service import learning_service
        
        if filter == "pending":
            learnings = learning_service.get_pending_learnings(limit=50)
        elif filter == "today":
            learnings = learning_service.get_recent_learnings(hours=24, limit=50)
        elif filter == "permanent":
            learnings = learning_service.get_permanent_learnings()
        else:  # all
            learnings = learning_service.get_recent_learnings(hours=168, limit=100)  # 1 week
        
        # Get stats
        stats = learning_service.get_learning_stats()
        
        return {
            "success": True,
            "filter": filter,
            "count": len(learnings),
            "stats": stats,
            "learnings": learnings
        }
        
    except Exception as e:
        logger.error(f"Error getting learnings: {e}")
        return {"success": False, "error": str(e), "learnings": []}


@router.get("/learnings/stats")
async def get_learning_stats() -> Dict[str, Any]:
    """Get learning statistics for dashboard."""
    try:
        from backend.services.learning_service import learning_service
        stats = learning_service.get_learning_stats()
        return {"success": True, **stats}
    except Exception as e:
        logger.error(f"Error getting learning stats: {e}")
        return {"success": False, "error": str(e)}


@router.post("/learnings/{learning_id}")
async def process_learning(
    learning_id: int,
    action: LearningAction
) -> Dict[str, Any]:
    """Approve or reject a learning."""
    try:
        from backend.services.learning_service import learning_service
        
        if action.approved:
            success = learning_service.approve_learning(
                learning_id=learning_id,
                approved_by="founder",
                make_permanent=action.make_permanent
            )
            return {
                "success": success,
                "status": "approved",
                "permanent": action.make_permanent
            }
        else:
            success = learning_service.reject_learning(
                learning_id=learning_id,
                rejected_by="founder"
            )
            return {
                "success": success,
                "status": "rejected"
            }
            
    except Exception as e:
        logger.error(f"Error processing learning: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/learnings/approve")
async def approve_learning(
    make_permanent: bool = Body(True)
) -> Dict[str, Any]:
    """Approve all pending learnings at once."""
    try:
        from backend.services.learning_service import learning_service
        
        pending = learning_service.get_pending_learnings(limit=100)
        approved_count = 0
        
        for learning in pending:
            if learning_service.approve_learning(
                learning_id=learning["id"],
                approved_by="founder",
                make_permanent=make_permanent
            ):
                approved_count += 1
        
        return {
            "success": True,
            "approved_count": approved_count,
            "total_pending": len(pending)
        }
        
    except Exception as e:
        logger.error(f"Error approving all learnings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== NEURAL BRAIN CONTROL ====================

class BrainModeRequest(BaseModel):
    mode: str

@router.post("/brain/mode")
async def set_brain_mode(request: BrainModeRequest):
    """Set the system brain mode (local/hybrid/cloud)."""
    db = SessionLocal()
    try:
        from backend.database import SystemConfig
        config = db.query(SystemConfig).filter(SystemConfig.config_key == "brain_mode").first()
        if not config:
            config = SystemConfig(config_key="brain_mode", config_value=request.mode)
            db.add(config)
        else:
            config.config_value = request.mode
        db.commit()
        return {"success": True, "mode": request.mode}
    finally:
        db.close()

# ==================== POLICIES ====================

class PolicyCreate(BaseModel):
    name: str
    rule_type: str
    enforcement: str
    scope: str = "global"

@router.get("/policies")
async def get_policies() -> Dict[str, Any]:
    """Get all founder policies."""
    db = SessionLocal()
    try:
        policies = db.query(DBPolicy).all()
        return {
            "success": True,
            "policies": [
                {
                    "id": p.policy_id,
                    "name": p.name,
                    "rule_type": p.rule_type,
                    "enforcement": p.enforcement,
                    "scope": p.scope
                } for p in policies
            ]
        }
    finally:
        db.close()

@router.post("/policies")
async def create_policy(policy: PolicyCreate) -> Dict[str, Any]:
    """Create a new founder policy."""
    db = SessionLocal()
    try:
        policy_id = f"pol_{policy.name.lower().replace(' ', '_')}"
        new_policy = DBPolicy(
            policy_id=policy_id,
            name=policy.name,
            rule_type=policy.rule_type,
            enforcement=policy.enforcement,
            scope=policy.scope
        )
        db.add(new_policy)
        db.commit()
        db.refresh(new_policy)
        return {"success": True, "policy": {"id": new_policy.policy_id}}
    finally:
        db.close()

@router.delete("/policies/{policy_id}")
async def delete_policy(policy_id: str) -> Dict[str, Any]:
    """Delete a policy."""
    db = SessionLocal()
    try:
        policy = db.query(DBPolicy).filter(DBPolicy.policy_id == policy_id).first()
        if not policy:
            raise HTTPException(status_code=404, detail="Policy not found")
        db.delete(policy)
        db.commit()
        return {"success": True}
    finally:
        db.close()

# ==================== SECRETS PROXY ====================

@router.get("/secrets")
async def list_founder_secrets() -> Dict[str, Any]:
    """List secrets from vault (metadata only)."""
    try:
        from backend.services.vault_service import get_vault_service
        vault = get_vault_service()
        secrets = vault.list_secrets("founder")
        return {"success": True, "secrets": secrets}
    except Exception as e:
        logger.error(f"Error listing secrets: {e}")
        return {"success": False, "error": str(e)}

@router.post("/secrets")
async def create_founder_secret(
    name: str = Body(...),
    value: str = Body(...),
    category: str = Body("general")
) -> Dict[str, Any]:
    """Create a secret in vault."""
    try:
        from backend.services.vault_service import get_vault_service
        vault = get_vault_service()
        result = vault.store_secret(name=name, value=value, category=category, owner="founder")
        return {"success": True, "secret": result}
    except Exception as e:
        logger.error(f"Error creating secret: {e}")
        return {"success": False, "error": str(e)}

# ==================== SETTINGS & INTEGRATIONS ====================

class SettingUpdate(BaseModel):
    key: str
    value: Any

@router.post("/settings")
async def update_setting(setting: SettingUpdate) -> Dict[str, Any]:
    """Update a system setting key-value pair."""
    db = SessionLocal()
    try:
        from backend.database import SystemConfig
        config = db.query(SystemConfig).filter(SystemConfig.config_key == setting.key).first()
        if not config:
            config = SystemConfig(config_key=setting.key, config_value=str(setting.value))
            db.add(config)
        else:
            config.config_value = str(setting.value)
        db.commit()
        return {"success": True, "key": setting.key, "value": setting.value}
    finally:
        db.close()

@router.get("/integrations/status")
async def get_integration_status() -> Dict[str, Any]:
    """Check status of external integrations based on vault secrets."""
    try:
        from backend.services.vault_service import get_vault_service
        vault = get_vault_service()
        
        # Check for existence of tokens in vault/env
        integrations = [
            {"id": "slack", "name": "Slack", "secret_key": "SLACK_BOT_TOKEN"},
            {"id": "discord", "name": "Discord", "secret_key": "DISCORD_BOT_TOKEN"},
            {"id": "github", "name": "GitHub", "secret_key": "GITHUB_TOKEN"},
            {"id": "openai", "name": "OpenAI", "secret_key": "OPENAI_API_KEY"},
            {"id": "email", "name": "Email", "secret_key": "SMTP_PASSWORD"},
        ]
        
        results = []
        for integ in integrations:
            # Check vault first, then maybe env? Vault service usually handles env fallback if configured
            secret = vault.get_secret(integ["secret_key"])
            status = "connected" if secret else "disconnected"
            results.append({
                "id": integ["id"],
                "name": integ["name"],
                "status": status,
                "last_sync": datetime.now().isoformat() if status == "connected" else None
            })
            
        return {"success": True, "integrations": results}
    except Exception as e:
        logger.error(f"Error checking integrations: {e}")
        return {"success": False, "error": str(e), "integrations": []}

# ==================== DASHBOARD ====================

@router.get("/dashboard")
@router.get("/control-panel")
async def get_founder_dashboard() -> Dict[str, Any]:
    """Get founder dashboard summary with live stats and settings."""
    try:
        from backend.services.learning_service import learning_service
        from backend.database import SessionLocal, PendingApproval, Agent, Department, SystemConfig
        
        db = SessionLocal()
        try:
            learning_stats = learning_service.get_learning_stats()
            pending_approvals = db.query(PendingApproval).filter(PendingApproval.status == "pending").count()
            active_agents = db.query(Agent).filter(Agent.is_active == True).count()
            online_depts = db.query(Department).all()
            
            # Fetch Settings
            settings_rows = db.query(SystemConfig).all()
            settings = {row.config_key: row.config_value for row in settings_rows}
            
            # Defaults
            if "injection_guard" not in settings: settings["injection_guard"] = "true"
            if "malicious_content_gate" not in settings: settings["malicious_content_gate"] = "true"

            # Autopilot status
            from backend.services.governance_loop import get_governance_loop
            loop = get_governance_loop()
            autopilot = loop.autopilot
            
            return {
                "success": True,
                "system_status": {
                    "agents_active": active_agents,
                    "departments_online": len(online_depts),
                    "pending_approvals": pending_approvals,
                    "system_health": "nominal"
                },
                "brain_status": {
                    "mode": settings.get("brain_mode", "hybrid"),
                },
                "settings": settings,
                "governance": {
                    "autopilot_enabled": autopilot,
                    "approval_queue": [] 
                },
                "economics": {
                    "daily_cost": 1.45 
                },
                "learning_stats": learning_stats,
                "last_updated": datetime.now().isoformat()
            }
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error getting dashboard: {e}")
        return {"success": False, "error": str(e)}
