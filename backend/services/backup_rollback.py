"""
Backup and Rollback Service
Provides safe change management with automatic backups and rollback capability
"""
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from backend.database import get_db, SystemConfig, Base, engine
import sqlite3

logger = logging.getLogger(__name__)

class BackupRollbackService:
    """Service for creating backups and rolling back changes"""
    
    def __init__(self, db_path: str = "daena.db", backup_dir: str = "backups"):
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        self.config_backup_key = "backup_metadata"
    
    def create_backup(self, label: str = None, description: str = None) -> Dict[str, Any]:
        """
        Create a backup of the database and system configuration
        
        Args:
            label: Optional label for the backup
            description: Optional description
            
        Returns:
            Backup metadata with path and timestamp
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        label_suffix = f"_{label}" if label else ""
        backup_filename = f"backup_{timestamp}{label_suffix}.db"
        backup_path = self.backup_dir / backup_filename
        
        try:
            # Copy database file
            if self.db_path.exists():
                shutil.copy2(self.db_path, backup_path)
                logger.info(f"Database backup created: {backup_path}")
            else:
                logger.warning(f"Database file not found: {self.db_path}")
                return {"success": False, "error": "Database file not found"}
            
            # Save backup metadata
            metadata = {
                "timestamp": timestamp,
                "backup_path": str(backup_path),
                "label": label,
                "description": description,
                "db_size": backup_path.stat().st_size,
                "created_at": datetime.utcnow().isoformat()
            }
            
            # Save metadata to SystemConfig
            db = next(get_db())
            try:
                config = db.query(SystemConfig).filter(
                    SystemConfig.config_key == self.config_backup_key
                ).first()
                
                if not config:
                    config = SystemConfig(
                        config_key=self.config_backup_key,
                        config_type="json",
                        description="Backup metadata"
                    )
                    db.add(config)
                
                # Load existing backups
                existing_backups = []
                if config.config_value:
                    try:
                        existing_data = json.loads(config.config_value)
                        existing_backups = existing_data.get("backups", [])
                    except:
                        pass
                
                # Add new backup
                existing_backups.append(metadata)
                
                # Keep only last 10 backups
                if len(existing_backups) > 10:
                    # Remove oldest backup file
                    oldest = existing_backups.pop(0)
                    try:
                        Path(oldest["backup_path"]).unlink()
                    except:
                        pass
                
                config.config_value = json.dumps({
                    "backups": existing_backups,
                    "last_backup": metadata
                })
                db.commit()
                
                logger.info(f"Backup metadata saved: {backup_filename}")
                
                return {
                    "success": True,
                    "backup": metadata,
                    "message": f"Backup created: {backup_filename}"
                }
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error creating backup: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups"""
        db = next(get_db())
        try:
            config = db.query(SystemConfig).filter(
                SystemConfig.config_key == self.config_backup_key
            ).first()
            
            if not config or not config.config_value:
                return []
            
            data = json.loads(config.config_value)
            backups = data.get("backups", [])
            
            # Verify backup files still exist
            valid_backups = []
            for backup in backups:
                backup_path = Path(backup.get("backup_path", ""))
                if backup_path.exists():
                    valid_backups.append(backup)
                else:
                    logger.warning(f"Backup file not found: {backup_path}")
            
            return valid_backups
        finally:
            db.close()
    
    def rollback(self, backup_timestamp: str = None, backup_path: str = None) -> Dict[str, Any]:
        """
        Rollback to a previous backup
        
        Args:
            backup_timestamp: Timestamp of backup to restore
            backup_path: Direct path to backup file
            
        Returns:
            Rollback result
        """
        try:
            # Find backup file
            if backup_path:
                backup_file = Path(backup_path)
            elif backup_timestamp:
                backups = self.list_backups()
                backup = next((b for b in backups if b["timestamp"] == backup_timestamp), None)
                if not backup:
                    return {"success": False, "error": "Backup not found"}
                backup_file = Path(backup["backup_path"])
            else:
                # Use most recent backup
                backups = self.list_backups()
                if not backups:
                    return {"success": False, "error": "No backups available"}
                backup_file = Path(backups[-1]["backup_path"])
            
            if not backup_file.exists():
                return {"success": False, "error": f"Backup file not found: {backup_file}"}
            
            # Create safety backup before rollback
            safety_backup = self.create_backup(label="pre_rollback", description="Safety backup before rollback")
            
            # Close any open database connections
            # Note: This is a simplified approach - in production, you'd want to ensure all connections are closed
            
            # Copy backup over current database
            shutil.copy2(backup_file, self.db_path)
            
            logger.warning(f"Database rolled back to: {backup_file}")
            
            return {
                "success": True,
                "message": f"Rolled back to backup: {backup_file.name}",
                "safety_backup": safety_backup.get("backup", {}).get("timestamp") if safety_backup.get("success") else None
            }
            
        except Exception as e:
            logger.error(f"Error during rollback: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def auto_backup_before_change(self, change_type: str, change_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Automatically create backup before making a change
        
        Args:
            change_type: Type of change (e.g., "agent_update", "system_reset")
            change_data: Data about the change
            
        Returns:
            Backup result
        """
        label = f"auto_{change_type}"
        description = f"Auto-backup before {change_type}: {json.dumps(change_data)[:100]}"
        return self.create_backup(label=label, description=description)

# Global instance
backup_service = BackupRollbackService()



