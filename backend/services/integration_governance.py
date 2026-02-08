"""
Integration Governance Service
Enforces policies and approvals for integration usage.
Provides permission checking, risk evaluation, and audit logging.
"""

from typing import Dict, Optional, Tuple, List, Any
from datetime import datetime, timedelta
import json
import uuid
import logging

from backend.database import (
    SessionLocal,
    IntegrationInstance,
    IntegrationPolicy,
    IntegrationAuditLog,
    IntegrationCatalog,
    PendingApproval
)

logger = logging.getLogger(__name__)


class IntegrationGovernance:
    """Enforces policies and approvals for integration usage."""
    
    # High-risk actions that always require approval
    HIGH_RISK_ACTIONS = [
        'delete_repo', 'merge_pr', 'send_email', 'delete_page',
        'transfer_funds', 'modify_user', 'delete_user', 'deploy',
        'delete_database', 'execute_query', 'create_payment'
    ]
    
    # Medium-risk actions
    MEDIUM_RISK_ACTIONS = [
        'create_pr', 'update_page', 'create_issue', 'modify_file',
        'send_message', 'create_channel', 'add_member'
    ]
    
    def check_permission(
        self,
        instance_id: str,
        actor_type: str,  # 'founder', 'daena', 'agent'
        actor_id: str,
        department_id: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Check if actor has permission to use integration."""
        
        db = SessionLocal()
        try:
            # Get instance
            instance = db.query(IntegrationInstance).filter(
                IntegrationInstance.id == instance_id
            ).first()
            
            if not instance or instance.status != 'connected':
                return False, "Integration not connected"
            
            # Get policy
            policy = db.query(IntegrationPolicy).filter(
                IntegrationPolicy.instance_id == instance_id
            ).first()
            
            if not policy:
                # No policy = allow founder/daena by default
                if actor_type in ['founder', 'daena']:
                    return True, "Allowed by default policy"
                return False, "No policy found for integration"
            
            # Check role permissions
            if actor_type == 'founder' and policy.allow_founder:
                return True, "Allowed by founder policy"
            
            if actor_type == 'daena' and policy.allow_daena:
                return True, "Allowed by daena policy"
            
            if actor_type == 'agent' and policy.allow_agents:
                # Check department restriction
                if policy.allowed_departments and department_id:
                    if department_id not in policy.allowed_departments:
                        return False, "Agent not in allowed department"
                return True, "Allowed by agent policy"
            
            return False, "Actor not permitted by policy"
            
        finally:
            db.close()
    
    def evaluate_risk(
        self,
        instance_id: str,
        action: str,
        params: Dict
    ) -> Tuple[str, bool]:  # (risk_level, needs_approval)
        """Evaluate risk level of an action."""
        
        db = SessionLocal()
        try:
            # Get instance and catalog info
            instance = db.query(IntegrationInstance).filter(
                IntegrationInstance.id == instance_id
            ).first()
            
            if not instance:
                return 'medium', True  # Unknown = cautious
            
            catalog = db.query(IntegrationCatalog).filter(
                IntegrationCatalog.key == instance.catalog_key
            ).first()
            
            # Base risk from catalog
            base_risk = catalog.default_risk_level if catalog else 'medium'
            
            # Get policy
            policy = db.query(IntegrationPolicy).filter(
                IntegrationPolicy.instance_id == instance_id
            ).first()
            
            # Check if action is in restricted list
            if policy and action in (policy.restricted_actions or []):
                return 'high', True
            
            # Check high-risk actions
            if action in self.HIGH_RISK_ACTIONS:
                return 'high', True
            
            # Check medium-risk actions
            if action in self.MEDIUM_RISK_ACTIONS:
                needs_approval = policy.approval_mode == 'always' if policy else False
                return 'medium', needs_approval
            
            # Check approval mode from policy
            if policy and policy.approval_mode == 'always':
                return base_risk, True
            
            return base_risk, False
            
        finally:
            db.close()
    
    def check_limits(
        self,
        instance_id: str
    ) -> Tuple[bool, str]:
        """Check if integration has exceeded daily limits."""
        
        db = SessionLocal()
        try:
            policy = db.query(IntegrationPolicy).filter(
                IntegrationPolicy.instance_id == instance_id
            ).first()
            
            if not policy:
                return True, "No limits configured"
            
            # Count today's calls
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            call_count = db.query(IntegrationAuditLog).filter(
                IntegrationAuditLog.instance_id == instance_id,
                IntegrationAuditLog.created_at >= today_start,
                IntegrationAuditLog.action == 'execute'
            ).count()
            
            if call_count >= policy.max_daily_calls:
                return False, f"Daily call limit reached ({policy.max_daily_calls})"
            
            return True, f"Within limits ({call_count}/{policy.max_daily_calls})"
            
        finally:
            db.close()
    
    def create_approval_request(
        self,
        instance_id: str,
        action: str,
        params: Dict,
        actor_type: str,
        actor_id: str,
        risk_level: str
    ) -> str:
        """Create approval request for high-risk action. Returns approval_id."""
        
        db = SessionLocal()
        try:
            instance = db.query(IntegrationInstance).filter(
                IntegrationInstance.id == instance_id
            ).first()
            
            catalog_key = instance.catalog_key if instance else 'unknown'
            
            approval = PendingApproval(
                request_id=str(uuid.uuid4()),
                request_type='integration_execution',
                submitter_id=actor_id,
                title=f"Integration Action: {action} on {catalog_key}",
                description=f"Actor {actor_type} ({actor_id}) wants to execute '{action}' on integration '{catalog_key}'",
                request_data=json.dumps({
                    'instance_id': instance_id,
                    'catalog_key': catalog_key,
                    'action': action,
                    'params': params,
                    'actor_type': actor_type,
                    'actor_id': actor_id,
                    'risk_level': risk_level
                }),
                status='pending',
                risk_score=0.9 if risk_level == 'high' else 0.6,
                created_at=datetime.utcnow()
            )
            
            db.add(approval)
            db.commit()
            
            return approval.request_id
            
        finally:
            db.close()
    
    def log_execution(
        self,
        instance_id: str,
        action: str,
        params: Dict,
        actor_type: str,
        actor_id: str,
        actor_name: str = '',
        result: Optional[Dict] = None,
        error: Optional[str] = None,
        approval_required: bool = False,
        approval_status: Optional[str] = None,
        risk_level: str = 'low',
        execution_time_ms: int = 0
    ) -> str:
        """Log integration execution to audit trail. Returns log_id."""
        
        db = SessionLocal()
        try:
            # Get catalog key from instance
            instance = db.query(IntegrationInstance).filter(
                IntegrationInstance.id == instance_id
            ).first()
            catalog_key = instance.catalog_key if instance else None
            
            log = IntegrationAuditLog(
                id=str(uuid.uuid4()),
                actor_type=actor_type,
                actor_id=actor_id,
                actor_name=actor_name,
                instance_id=instance_id,
                catalog_key=catalog_key,
                action=action,
                action_details=params,
                request_summary=json.dumps(params)[:1000] if params else None,
                result_summary=json.dumps(result)[:1000] if result else None,
                error_message=error,
                risk_level=risk_level,
                approval_required=approval_required,
                approval_status=approval_status,
                execution_time_ms=execution_time_ms,
                created_at=datetime.utcnow()
            )
            
            db.add(log)
            
            # Update last_used_at on instance
            if instance:
                instance.last_used_at = datetime.utcnow()
            
            db.commit()
            
            return log.id
            
        finally:
            db.close()
    
    def get_audit_logs(
        self,
        instance_id: Optional[str] = None,
        action: Optional[str] = None,
        actor_type: Optional[str] = None,
        risk_level: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Dict], int]:
        """Get audit logs with filtering."""
        
        db = SessionLocal()
        try:
            query = db.query(IntegrationAuditLog)
            
            if instance_id:
                query = query.filter(IntegrationAuditLog.instance_id == instance_id)
            if action:
                query = query.filter(IntegrationAuditLog.action == action)
            if actor_type:
                query = query.filter(IntegrationAuditLog.actor_type == actor_type)
            if risk_level:
                query = query.filter(IntegrationAuditLog.risk_level == risk_level)
            
            total = query.count()
            logs = query.order_by(IntegrationAuditLog.created_at.desc()).offset(offset).limit(limit).all()
            
            result = [
                {
                    "id": log.id,
                    "timestamp": log.created_at.isoformat() if log.created_at else None,
                    "actor_type": log.actor_type,
                    "actor_name": log.actor_name,
                    "action": log.action,
                    "catalog_key": log.catalog_key,
                    "risk_level": log.risk_level,
                    "approval_required": log.approval_required,
                    "approval_status": log.approval_status,
                    "execution_time_ms": log.execution_time_ms,
                    "error_message": log.error_message
                }
                for log in logs
            ]
            
            return result, total
            
        finally:
            db.close()


# Singleton instance
_integration_governance: Optional[IntegrationGovernance] = None


def get_integration_governance() -> IntegrationGovernance:
    """Get singleton integration governance instance."""
    global _integration_governance
    if _integration_governance is None:
        _integration_governance = IntegrationGovernance()
    return _integration_governance
