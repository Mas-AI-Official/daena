"""ABAC (Attribute-Based Access Control) middleware for Daena."""
import logging
from typing import Dict, Any, Optional, Callable
from functools import wraps
from datetime import datetime

logger = logging.getLogger(__name__)

class ABACEnforcer:
    """ABAC enforcement engine."""
    
    def __init__(self):
        self.policies = {
            "global": {
                "read": ["founder", "admin"],
                "write": ["founder", "admin"],
                "delete": ["founder"]
            },
            "department": {
                "read": ["founder", "admin", "department_head"],
                "write": ["founder", "admin", "department_head"],
                "delete": ["founder", "admin"]
            },
            "project": {
                "read": ["founder", "admin", "department_head", "project_member"],
                "write": ["founder", "admin", "department_head", "project_lead"],
                "delete": ["founder", "admin", "department_head"]
            },
            "agent": {
                "read": ["founder", "admin", "department_head", "agent"],
                "write": ["founder", "admin", "department_head"],
                "delete": ["founder", "admin"]
            }
        }
        
        self.access_log = []
    
    def check_access(self, resource_tier: str, action: str, actor_role: str, 
                    context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Check if actor has access to perform action on resource tier.
        
        Args:
            resource_tier: global, department, project, agent
            action: read, write, delete
            actor_role: founder, admin, department_head, project_member, agent
            context: Additional context (department_id, project_id, etc.)
        
        Returns:
            True if access allowed, False otherwise
        """
        if resource_tier not in self.policies:
            logger.warning(f"Unknown resource tier: {resource_tier}")
            return False
        
        if action not in self.policies[resource_tier]:
            logger.warning(f"Unknown action: {action} for tier {resource_tier}")
            return False
        
        allowed_roles = self.policies[resource_tier][action]
        access_granted = actor_role in allowed_roles
        
        # Log access attempt
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "resource_tier": resource_tier,
            "action": action,
            "actor_role": actor_role,
            "context": context or {},
            "allowed": access_granted,
            "reason": f"Role {actor_role} {'allowed' if access_granted else 'denied'} for {action} on {resource_tier}"
        }
        
        self.access_log.append(log_entry)
        
        if access_granted:
            logger.info(f"ABAC: {actor_role} allowed {action} on {resource_tier}")
        else:
            logger.warning(f"ABAC: {actor_role} denied {action} on {resource_tier}")
        
        return access_granted
    
    def log_access(self, resource_tier: str, action: str, actor_role: str, 
                   context: Optional[Dict[str, Any]] = None, success: bool = True):
        """Log access attempt for audit purposes."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "resource_tier": resource_tier,
            "action": action,
            "actor_role": actor_role,
            "context": context or {},
            "success": success
        }
        self.access_log.append(log_entry)
    
    def get_access_log(self, limit: int = 100) -> list:
        """Get recent access log entries."""
        return self.access_log[-limit:] if self.access_log else []

# Global ABAC enforcer instance
abac_enforcer = ABACEnforcer()

def abac_check(resource_tier: str, action: str, actor_role: str, 
               context: Optional[Dict[str, Any]] = None):
    """
    ABAC decorator for checking access control.
    
    Usage:
        @abac_check("department", "read", "founder")
        async def get_department_data():
            pass
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not abac_enforcer.check_access(resource_tier, action, actor_role, context):
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=403, 
                    detail=f"Access denied: {actor_role} cannot {action} on {resource_tier}"
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def abac_guard(resource_tier: str, action: str, actor_role: str, 
               context: Optional[Dict[str, Any]] = None):
    """
    ABAC guard function for inline access control.
    
    Usage:
        if not abac_guard("project", "write", user_role, {"project_id": project_id}):
            raise AccessDeniedError()
    """
    return abac_enforcer.check_access(resource_tier, action, actor_role, context) 