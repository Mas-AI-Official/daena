"""
System Management API Routes
Handles system-wide operations like reset to default
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from sqlalchemy.orm import Session
from backend.database import get_db, SystemConfig
from backend.core.websocket_manager import websocket_manager
from datetime import datetime
import logging

router = APIRouter(prefix="/api/v1/system", tags=["system"])
logger = logging.getLogger(__name__)

@router.post("/reset-to-default")
async def reset_to_default(
    confirm: bool = False,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Reset system to default state
    WARNING: This will clear all user data and reset to initial state
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Reset requires confirm=true parameter"
        )
    
    try:
        # Clear all SystemConfig except critical ones
        critical_keys = ["active_brain_model", "default_brain_model"]
        db.query(SystemConfig).filter(
            ~SystemConfig.config_key.in_(critical_keys)
        ).delete()
        
        # Reset voice state to defaults
        from backend.routes.voice import _save_voice_state
        _save_voice_state(db, {
            "talk_active": False,
            "voice_name": "default",
            "rate": 1.0,
            "pitch": 1.0,
            "volume": 1.0
        })
        
        db.commit()
        
        # Emit WebSocket event
        websocket_manager.emit_event("system.reset", {
            "reset_at": datetime.utcnow().isoformat()
        })
        
        logger.warning("System reset to default state")
        
        return {
            "success": True,
            "message": "System reset to default state",
            "reset_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error resetting system: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Reset failed: {str(e)}")

@router.get("/status")
async def get_system_status(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get system status and configuration"""
    try:
        from backend.database import (
            Department, Agent, Task, ChatSession, ChatMessage,
            CouncilCategory, CouncilMember, Project as ProjectDB
        )
        from sqlalchemy import inspect, text
        
        stats = {}
        
        # Count departments (safe)
        try:
            stats["departments"] = db.query(Department).count()
        except Exception as e:
            logger.warning(f"Error counting departments: {e}")
            stats["departments"] = 0
        
        # Count agents (handle missing voice_id column gracefully)
        try:
            inspector = inspect(db.bind)
            columns = [col['name'] for col in inspector.get_columns('agents')]
            if 'voice_id' in columns:
                stats["agents"] = db.query(Agent).count()
            else:
                # Use raw SQL to count without voice_id
                result = db.execute(text("SELECT COUNT(*) FROM agents"))
                stats["agents"] = result.scalar() or 0
        except Exception as e:
            logger.warning(f"Error counting agents: {e}")
            stats["agents"] = 0
        
        # Count tasks (safe)
        try:
            stats["tasks"] = db.query(Task).count()
        except Exception as e:
            logger.warning(f"Error counting tasks: {e}")
            stats["tasks"] = 0
        
        # Count chat sessions (safe)
        try:
            stats["chat_sessions"] = db.query(ChatSession).filter(ChatSession.is_active == True).count()
        except Exception as e:
            logger.warning(f"Error counting chat sessions: {e}")
            stats["chat_sessions"] = 0
        
        # Count chat messages (safe)
        try:
            stats["chat_messages"] = db.query(ChatMessage).count()
        except Exception as e:
            logger.warning(f"Error counting chat messages: {e}")
            stats["chat_messages"] = 0
        
        # Count councils (safe)
        try:
            stats["councils"] = db.query(CouncilCategory).count()
        except Exception as e:
            logger.warning(f"Error counting councils: {e}")
            stats["councils"] = 0
        
        # Count council members (safe)
        try:
            stats["council_members"] = db.query(CouncilMember).count()
        except Exception as e:
            logger.warning(f"Error counting council members: {e}")
            stats["council_members"] = 0
        
        # Count projects (safe)
        try:
            stats["projects"] = db.query(ProjectDB).count()
        except Exception as e:
            logger.warning(f"Error counting projects: {e}")
            stats["projects"] = 0
        
        return {
            "success": True,
            "stats": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        # Return partial stats on error
        return {
            "success": False,
            "error": str(e),
            "stats": {},
            "timestamp": datetime.utcnow().isoformat()
        }

@router.post("/backup")
async def create_backup(
    label: str = None,
    description: str = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Create a system backup"""
    from backend.services.backup_rollback import backup_service
    
    result = backup_service.create_backup(label=label, description=description)
    return result

@router.get("/backups")
async def list_backups(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """List all available backups"""
    from backend.services.backup_rollback import backup_service
    
    backups = backup_service.list_backups()
    return {
        "success": True,
        "backups": backups,
        "count": len(backups)
    }

@router.post("/rollback")
async def rollback_to_backup(
    backup_timestamp: str = None,
    backup_path: str = None,
    confirm: bool = False,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Rollback to a previous backup"""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Rollback requires confirm=true parameter"
        )
    
    from backend.services.backup_rollback import backup_service
    
    result = backup_service.rollback(backup_timestamp=backup_timestamp, backup_path=backup_path)
    return result

@router.get("/frontend-setting")
async def get_all_frontend_settings(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get all frontend settings (for restore on load). Returns { key: { value, updated_at }, ... }."""
    from backend.services.frontend_backend_sync import frontend_backend_sync
    settings = frontend_backend_sync.get_all_frontend_settings()
    return settings

@router.post("/frontend-setting")
async def save_frontend_setting(
    key: str,
    value: Any,
    auto_backup: bool = True,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Save a frontend setting to backend"""
    from backend.services.frontend_backend_sync import frontend_backend_sync
    
    result = frontend_backend_sync.save_frontend_setting(key, value, auto_backup=auto_backup)
    return result

@router.get("/frontend-setting/{key}")
async def get_frontend_setting(
    key: str,
    default: Any = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get a frontend setting from backend"""
    from backend.services.frontend_backend_sync import frontend_backend_sync
    
    value = frontend_backend_sync.get_frontend_setting(key, default=default)
    return {
        "success": True,
        "key": key,
        "value": value
    }


@router.get("/capabilities")
async def get_system_capabilities() -> Dict[str, Any]:
    """Live capabilities: Hands, local LLM, tool catalog, governance, version. For DaenaBot Awareness UI."""
    try:
        from backend.core.capabilities import build_capabilities
        return await build_capabilities()
    except Exception as e:
        logger.exception("Capabilities build failed: %s", e)
        return {
            "success": False,
            "error": str(e),
            "available": {"hands_gateway": False, "local_llm": False, "tool_catalog": True},
            "health": {},
        }


@router.get("/policies")
async def get_system_policies() -> Dict[str, Any]:
    """Governance and tool policy summary: autopilot, auto-approve threshold, blocked commands, risk levels."""
    try:
        from backend.services.governance_loop import get_governance_loop
        from backend.services.tool_broker import ACTION_RISK, requires_approval, _emergency_stop, _automation_mode
        loop = get_governance_loop()
        stats = loop.get_stats()
        return {
            "success": True,
            "governance": {
                "autopilot_enabled": getattr(loop, "autopilot", True),
                "auto_approve_threshold": "low" if getattr(loop, "autopilot", True) else "none",
                "pending_count": len(loop.get_pending()),
                **stats,
            },
            "tool_policy": {
                "risk_levels": ACTION_RISK,
                "requires_approval_for": [k for k, v in ACTION_RISK.items() if requires_approval(v)],
                "emergency_stop_active": _emergency_stop(),
                "automation_mode": _automation_mode(),
            },
        }
    except Exception as e:
        logger.exception("Policies build failed: %s", e)
        return {"success": False, "error": str(e)}

