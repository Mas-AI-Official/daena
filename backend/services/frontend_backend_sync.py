"""
Frontend-Backend Sync Service
Ensures frontend changes are persisted to backend and vice versa
Provides automatic backup before changes
"""
import json
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.database import get_db, SystemConfig, Agent, Department
from backend.services.backup_rollback import backup_service

logger = logging.getLogger(__name__)

class FrontendBackendSync:
    """Service for syncing frontend changes to backend"""
    
    def __init__(self):
        self.sync_config_key = "frontend_backend_sync"
    
    def save_frontend_setting(self, key: str, value: Any, auto_backup: bool = True) -> Dict[str, Any]:
        """
        Save a frontend setting to backend
        
        Args:
            key: Setting key (e.g., "sidebar_collapsed", "theme", "agent_display_mode")
            value: Setting value
            auto_backup: Whether to create backup before change
            
        Returns:
            Save result
        """
        try:
            # Auto-backup if enabled
            if auto_backup:
                backup_service.auto_backup_before_change(
                    change_type="frontend_setting",
                    change_data={"key": key, "value": str(value)[:100]}
                )
            
            db = next(get_db())
            try:
                # Load existing sync config
                config = db.query(SystemConfig).filter(
                    SystemConfig.config_key == self.sync_config_key
                ).first()
                
                if not config:
                    config = SystemConfig(
                        config_key=self.sync_config_key,
                        config_type="json",
                        description="Frontend-Backend sync settings"
                    )
                    db.add(config)
                    settings = {}
                else:
                    settings = json.loads(config.config_value) if config.config_value else {}
                
                # Update setting
                settings[key] = {
                    "value": value,
                    "updated_at": datetime.utcnow().isoformat()
                }
                
                config.config_value = json.dumps(settings)
                db.commit()
                
                logger.info(f"Frontend setting saved: {key} = {value}")
                
                return {
                    "success": True,
                    "key": key,
                    "value": value,
                    "message": f"Setting '{key}' saved"
                }
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error saving frontend setting: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def get_frontend_setting(self, key: str, default: Any = None) -> Any:
        """Get a frontend setting from backend"""
        db = next(get_db())
        try:
            config = db.query(SystemConfig).filter(
                SystemConfig.config_key == self.sync_config_key
            ).first()
            
            if not config or not config.config_value:
                return default
            
            settings = json.loads(config.config_value)
            setting = settings.get(key, {})
            return setting.get("value", default)
        except:
            return default
        finally:
            db.close()
    
    def sync_agent_change(self, agent_id: str, changes: Dict[str, Any], auto_backup: bool = True) -> Dict[str, Any]:
        """
        Sync agent changes from frontend to backend
        
        Args:
            agent_id: Agent ID
            changes: Dictionary of changes (e.g., {"name": "New Name", "role": "advisor_b"})
            auto_backup: Whether to create backup
            
        Returns:
            Sync result
        """
        try:
            if auto_backup:
                backup_service.auto_backup_before_change(
                    change_type="agent_update",
                    change_data={"agent_id": agent_id, "changes": changes}
                )
            
            db = next(get_db())
            try:
                agent = db.query(Agent).filter(Agent.cell_id == agent_id).first()
                if not agent:
                    try:
                        agent = db.query(Agent).filter(Agent.id == int(agent_id)).first()
                    except:
                        pass
                
                if not agent:
                    return {"success": False, "error": f"Agent not found: {agent_id}"}
                
                # Apply changes
                for key, value in changes.items():
                    if hasattr(agent, key):
                        setattr(agent, key, value)
                
                db.commit()
                db.refresh(agent)
                
                logger.info(f"Agent synced: {agent_id} - {changes}")
                
                return {
                    "success": True,
                    "agent_id": agent_id,
                    "changes": changes,
                    "message": "Agent changes synced to backend"
                }
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error syncing agent change: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def sync_department_change(self, department_id: str, changes: Dict[str, Any], auto_backup: bool = True) -> Dict[str, Any]:
        """Sync department changes from frontend to backend"""
        try:
            if auto_backup:
                backup_service.auto_backup_before_change(
                    change_type="department_update",
                    change_data={"department_id": department_id, "changes": changes}
                )
            
            db = next(get_db())
            try:
                dept = db.query(Department).filter(Department.slug == department_id).first()
                if not dept:
                    return {"success": False, "error": f"Department not found: {department_id}"}
                
                for key, value in changes.items():
                    if hasattr(dept, key):
                        setattr(dept, key, value)
                
                db.commit()
                db.refresh(dept)
                
                logger.info(f"Department synced: {department_id} - {changes}")
                
                return {
                    "success": True,
                    "department_id": department_id,
                    "changes": changes,
                    "message": "Department changes synced to backend"
                }
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error syncing department change: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

# Global instance
frontend_backend_sync = FrontendBackendSync()



