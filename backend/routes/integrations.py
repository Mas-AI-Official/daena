"""
CMP Integrations API Routes
Enhanced API for the Integration Hub with full governance support.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime
import uuid
import json
import os
import logging

from backend.database import (
    SessionLocal,
    IntegrationCatalog,
    IntegrationInstance,
    IntegrationPolicy,
    IntegrationAuditLog,
    User
)
from backend.routes.auth import get_current_user
from backend.services.integration_governance import get_integration_governance

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations", tags=["Integrations"])


# ============================================================
# Request/Response Models
# ============================================================

class ConnectRequest(BaseModel):
    auth_type: str  # 'oauth2' or 'api_key'
    credentials: Dict[str, Any]
    metadata: Optional[Dict] = {}


class PolicyUpdateRequest(BaseModel):
    allow_founder: Optional[bool] = None
    allow_daena: Optional[bool] = None
    allow_agents: Optional[bool] = None
    allowed_departments: Optional[List[str]] = None
    approval_mode: Optional[str] = None  # 'auto', 'needs_approval', 'always'
    max_daily_calls: Optional[int] = None
    max_daily_cost_usd: Optional[float] = None
    restricted_actions: Optional[List[str]] = None


class ExecuteRequest(BaseModel):
    instance_id: str
    action: str
    params: Dict[str, Any]
    actor_context: Optional[Dict] = {}  # {'department_id': '...', 'task_id': '...'}


# ============================================================
# Catalog Endpoints
# ============================================================

@router.get("/catalog")
async def list_catalog(
    category: Optional[str] = None,
    search: Optional[str] = None,
    featured_only: bool = False,
    current_user: User = Depends(get_current_user)
):
    """List available integration types in the catalog."""
    db = SessionLocal()
    try:
        query = db.query(IntegrationCatalog).filter(IntegrationCatalog.is_enabled == True)
        
        if category:
            query = query.filter(IntegrationCatalog.category == category)
        
        if featured_only:
            query = query.filter(IntegrationCatalog.is_featured == True)
        
        integrations = query.all()
        
        # Filter by search term
        if search:
            search_lower = search.lower()
            integrations = [
                i for i in integrations 
                if search_lower in i.name.lower() or 
                   (i.description and search_lower in i.description.lower())
            ]
        
        # Get unique categories
        all_categories = db.query(IntegrationCatalog.category).distinct().all()
        categories = [c[0] for c in all_categories if c[0]]
        
        return {
            "integrations": [
                {
                    "id": i.id,
                    "key": i.key,
                    "name": i.name,
                    "category": i.category,
                    "icon_url": i.icon_url,
                    "icon_svg": i.icon_svg,
                    "color": i.color,
                    "auth_type": i.auth_type,
                    "default_risk_level": i.default_risk_level,
                    "requires_approval": i.requires_approval,
                    "description": i.description,
                    "oauth_scopes": i.oauth_scopes if i.auth_type == 'oauth2' else None,
                    "api_key_fields": i.api_key_fields if i.auth_type == 'api_key' else None
                }
                for i in integrations
            ],
            "categories": categories
        }
    finally:
        db.close()


# ============================================================
# Instance Endpoints
# ============================================================

@router.get("/instances")
async def list_instances(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """List user's connected integration instances."""
    db = SessionLocal()
    try:
        query = db.query(IntegrationInstance).filter(
            IntegrationInstance.owner_id == str(current_user.id)
        )
        
        if status:
            query = query.filter(IntegrationInstance.status == status)
        
        instances = query.order_by(IntegrationInstance.updated_at.desc()).all()
        
        result = []
        for instance in instances:
            catalog = db.query(IntegrationCatalog).filter(
                IntegrationCatalog.key == instance.catalog_key
            ).first()
            
            policy = db.query(IntegrationPolicy).filter(
                IntegrationPolicy.instance_id == instance.id
            ).first()
            
            result.append({
                "id": instance.id,
                "catalog_key": instance.catalog_key,
                "name": catalog.name if catalog else instance.catalog_key,
                "icon_url": catalog.icon_url if catalog else None,
                "icon_svg": catalog.icon_svg if catalog else None,
                "color": catalog.color if catalog else None,
                "category": catalog.category if catalog else "unknown",
                "status": instance.status,
                "status_message": instance.status_message,
                "connected_at": instance.connected_at.isoformat() if instance.connected_at else None,
                "last_used_at": instance.last_used_at.isoformat() if instance.last_used_at else None,
                "metadata": instance.metadata_json,
                "policy": {
                    "allow_founder": policy.allow_founder if policy else True,
                    "allow_daena": policy.allow_daena if policy else True,
                    "allow_agents": policy.allow_agents if policy else False,
                    "approval_mode": policy.approval_mode if policy else "auto"
                } if policy else None
            })
        
        return {"instances": result}
    finally:
        db.close()


@router.post("/instances/{catalog_key}/connect")
async def connect_integration(
    catalog_key: str,
    request: ConnectRequest,
    current_user: User = Depends(get_current_user)
):
    """Connect a new integration instance."""
    
    # Verify user is founder (only founders can connect integrations)
    if current_user.role != "FOUNDER":
        raise HTTPException(403, "Only Founder can connect integrations")
    
    db = SessionLocal()
    try:
        # Get catalog entry
        catalog = db.query(IntegrationCatalog).filter(
            IntegrationCatalog.key == catalog_key
        ).first()
        
        if not catalog:
            raise HTTPException(404, f"Integration type '{catalog_key}' not found")
        
        # Validate auth type
        if request.auth_type != catalog.auth_type:
            raise HTTPException(400, f"Invalid auth type. Expected {catalog.auth_type}")
        
        # Check for existing instance
        existing = db.query(IntegrationInstance).filter(
            IntegrationInstance.catalog_key == catalog_key,
            IntegrationInstance.owner_id == str(current_user.id),
            IntegrationInstance.status.in_(['connected', 'paused'])
        ).first()
        
        if existing:
            raise HTTPException(400, f"Integration '{catalog_key}' already connected")
        
        # Store credentials (in production, these should be encrypted)
        # For now, we'll store them as JSON
        encrypted_creds = json.dumps(request.credentials)
        
        # Create instance
        instance_id = str(uuid.uuid4())
        instance = IntegrationInstance(
            id=instance_id,
            catalog_key=catalog_key,
            owner_id=str(current_user.id),
            status='connected',
            encrypted_credentials=encrypted_creds,
            connected_at=datetime.utcnow(),
            metadata_json=request.metadata or {}
        )
        
        db.add(instance)
        
        # Create default policy
        policy = IntegrationPolicy(
            id=str(uuid.uuid4()),
            instance_id=instance_id,
            allow_founder=True,
            allow_daena=True,
            allow_agents=False,
            approval_mode='auto' if catalog.default_risk_level == 'low' else 'needs_approval',
            max_daily_calls=1000,
            max_daily_cost_usd=100.0
        )
        
        db.add(policy)
        db.commit()
        
        # Log connection
        governance = get_integration_governance()
        governance.log_execution(
            instance_id=instance_id,
            action='connect',
            params={'auth_type': request.auth_type},
            actor_type='founder',
            actor_id=str(current_user.id),
            actor_name=current_user.username,
            risk_level='low'
        )
        
        return {
            "id": instance_id,
            "status": "connected",
            "message": f"Successfully connected {catalog.name}"
        }
        
    finally:
        db.close()


@router.post("/instances/{instance_id}/disconnect")
async def disconnect_integration(
    instance_id: str,
    current_user: User = Depends(get_current_user)
):
    """Disconnect an integration."""
    
    db = SessionLocal()
    try:
        instance = db.query(IntegrationInstance).filter(
            IntegrationInstance.id == instance_id,
            IntegrationInstance.owner_id == str(current_user.id)
        ).first()
        
        if not instance:
            raise HTTPException(404, "Integration not found")
        
        instance.status = 'disconnected'
        instance.disconnected_at = datetime.utcnow()
        # Clear credentials
        instance.encrypted_credentials = None
        instance.access_token = None
        instance.refresh_token = None
        
        db.commit()
        
        # Log disconnection
        governance = get_integration_governance()
        governance.log_execution(
            instance_id=instance_id,
            action='disconnect',
            params={},
            actor_type='founder',
            actor_id=str(current_user.id),
            actor_name=current_user.username,
            risk_level='low'
        )
        
        return {"status": "disconnected"}
        
    finally:
        db.close()


@router.post("/instances/{instance_id}/pause")
async def pause_integration(
    instance_id: str,
    current_user: User = Depends(get_current_user)
):
    """Pause an integration (temporarily disable)."""
    
    db = SessionLocal()
    try:
        instance = db.query(IntegrationInstance).filter(
            IntegrationInstance.id == instance_id,
            IntegrationInstance.owner_id == str(current_user.id)
        ).first()
        
        if not instance:
            raise HTTPException(404, "Integration not found")
        
        instance.status = 'paused'
        db.commit()
        
        return {"status": "paused"}
        
    finally:
        db.close()


@router.post("/instances/{instance_id}/resume")
async def resume_integration(
    instance_id: str,
    current_user: User = Depends(get_current_user)
):
    """Resume a paused integration."""
    
    db = SessionLocal()
    try:
        instance = db.query(IntegrationInstance).filter(
            IntegrationInstance.id == instance_id,
            IntegrationInstance.owner_id == str(current_user.id)
        ).first()
        
        if not instance:
            raise HTTPException(404, "Integration not found")
        
        instance.status = 'connected'
        db.commit()
        
        return {"status": "connected"}
        
    finally:
        db.close()


@router.post("/instances/{instance_id}/test")
async def test_integration(
    instance_id: str,
    current_user: User = Depends(get_current_user)
):
    """Test integration connection."""
    
    db = SessionLocal()
    try:
        instance = db.query(IntegrationInstance).filter(
            IntegrationInstance.id == instance_id,
            IntegrationInstance.owner_id == str(current_user.id)
        ).first()
        
        if not instance:
            raise HTTPException(404, "Integration not found")
        
        # For now, just update last_tested_at
        # In production, this would actually test the connection
        instance.last_tested_at = datetime.utcnow()
        db.commit()
        
        return {
            "connected": True,
            "tested_at": datetime.utcnow().isoformat()
        }
        
    finally:
        db.close()


# ============================================================
# Policy Endpoints
# ============================================================

@router.get("/instances/{instance_id}/policy")
async def get_policy(
    instance_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get integration policy."""
    
    db = SessionLocal()
    try:
        instance = db.query(IntegrationInstance).filter(
            IntegrationInstance.id == instance_id,
            IntegrationInstance.owner_id == str(current_user.id)
        ).first()
        
        if not instance:
            raise HTTPException(404, "Integration not found")
        
        policy = db.query(IntegrationPolicy).filter(
            IntegrationPolicy.instance_id == instance_id
        ).first()
        
        if not policy:
            raise HTTPException(404, "Policy not found")
        
        return {
            "instance_id": instance_id,
            "allow_founder": policy.allow_founder,
            "allow_daena": policy.allow_daena,
            "allow_agents": policy.allow_agents,
            "allowed_departments": policy.allowed_departments,
            "approval_mode": policy.approval_mode,
            "max_daily_calls": policy.max_daily_calls,
            "max_daily_cost_usd": policy.max_daily_cost_usd,
            "restricted_actions": policy.restricted_actions
        }
        
    finally:
        db.close()


@router.put("/instances/{instance_id}/policy")
async def update_policy(
    instance_id: str,
    request: PolicyUpdateRequest,
    current_user: User = Depends(get_current_user)
):
    """Update integration policy (Founder only)."""
    
    if current_user.role != "FOUNDER":
        raise HTTPException(403, "Only Founder can modify policies")
    
    db = SessionLocal()
    try:
        instance = db.query(IntegrationInstance).filter(
            IntegrationInstance.id == instance_id,
            IntegrationInstance.owner_id == str(current_user.id)
        ).first()
        
        if not instance:
            raise HTTPException(404, "Integration not found")
        
        policy = db.query(IntegrationPolicy).filter(
            IntegrationPolicy.instance_id == instance_id
        ).first()
        
        if not policy:
            raise HTTPException(404, "Policy not found")
        
        # Update fields
        if request.allow_founder is not None:
            policy.allow_founder = request.allow_founder
        if request.allow_daena is not None:
            policy.allow_daena = request.allow_daena
        if request.allow_agents is not None:
            policy.allow_agents = request.allow_agents
        if request.allowed_departments is not None:
            policy.allowed_departments = request.allowed_departments
        if request.approval_mode is not None:
            policy.approval_mode = request.approval_mode
        if request.max_daily_calls is not None:
            policy.max_daily_calls = request.max_daily_calls
        if request.max_daily_cost_usd is not None:
            policy.max_daily_cost_usd = request.max_daily_cost_usd
        if request.restricted_actions is not None:
            policy.restricted_actions = request.restricted_actions
        
        db.commit()
        
        return {"message": "Policy updated"}
        
    finally:
        db.close()


# ============================================================
# Execution Endpoints
# ============================================================

@router.post("/execute")
async def execute_integration_action(
    request: ExecuteRequest,
    current_user: User = Depends(get_current_user)
):
    """Execute an action on an integration with full governance."""
    import time
    
    governance = get_integration_governance()
    
    # Determine actor type
    actor_type = current_user.role.lower() if current_user.role else 'unknown'
    actor_id = str(current_user.id)
    actor_name = current_user.username
    
    # Check permission
    has_permission, permission_msg = governance.check_permission(
        instance_id=request.instance_id,
        actor_type=actor_type,
        actor_id=actor_id,
        department_id=request.actor_context.get('department_id')
    )
    
    if not has_permission:
        raise HTTPException(403, f"Permission denied: {permission_msg}")
    
    # Evaluate risk
    risk_level, needs_approval = governance.evaluate_risk(
        instance_id=request.instance_id,
        action=request.action,
        params=request.params
    )
    
    # Check limits
    within_limits, limit_msg = governance.check_limits(request.instance_id)
    if not within_limits:
        raise HTTPException(429, limit_msg)
    
    # If approval needed, create request
    if needs_approval:
        approval_id = governance.create_approval_request(
            instance_id=request.instance_id,
            action=request.action,
            params=request.params,
            actor_type=actor_type,
            actor_id=actor_id,
            risk_level=risk_level
        )
        
        # Log pending execution
        governance.log_execution(
            instance_id=request.instance_id,
            action=request.action,
            params=request.params,
            actor_type=actor_type,
            actor_id=actor_id,
            actor_name=actor_name,
            approval_required=True,
            approval_status='pending',
            risk_level=risk_level
        )
        
        return {
            "status": "pending_approval",
            "approval_id": approval_id,
            "message": "This action requires approval"
        }
    
    # Execute action (placeholder - would call actual connector)
    start_time = time.time()
    
    try:
        # In production, this would:
        # 1. Get the connector class
        # 2. Decrypt credentials
        # 3. Execute the action
        
        result = {"success": True, "message": f"Executed {request.action}"}
        execution_time = int((time.time() - start_time) * 1000)
        
        # Log success
        governance.log_execution(
            instance_id=request.instance_id,
            action=request.action,
            params=request.params,
            actor_type=actor_type,
            actor_id=actor_id,
            actor_name=actor_name,
            result=result,
            approval_required=False,
            risk_level=risk_level,
            execution_time_ms=execution_time
        )
        
        return {
            "status": "success",
            "result": result,
            "execution_time_ms": execution_time
        }
        
    except Exception as e:
        execution_time = int((time.time() - start_time) * 1000)
        
        # Log failure
        governance.log_execution(
            instance_id=request.instance_id,
            action=request.action,
            params=request.params,
            actor_type=actor_type,
            actor_id=actor_id,
            actor_name=actor_name,
            error=str(e),
            approval_required=False,
            risk_level=risk_level,
            execution_time_ms=execution_time
        )
        
        raise HTTPException(500, f"Execution failed: {str(e)}")


# ============================================================
# Audit Log Endpoints
# ============================================================

@router.get("/audit-log")
async def get_audit_log(
    instance_id: Optional[str] = None,
    action: Optional[str] = None,
    actor_type: Optional[str] = None,
    risk_level: Optional[str] = None,
    limit: int = Query(default=50, le=100),
    offset: int = 0,
    current_user: User = Depends(get_current_user)
):
    """Get integration audit log."""
    
    governance = get_integration_governance()
    
    logs, total = governance.get_audit_logs(
        instance_id=instance_id,
        action=action,
        actor_type=actor_type,
        risk_level=risk_level,
        limit=limit,
        offset=offset
    )
    
    return {
        "logs": logs,
        "total": total,
        "limit": limit,
        "offset": offset
    }


# ============================================================
# OAuth Endpoints (placeholder)
# ============================================================

@router.post("/oauth/{catalog_key}/auth-url")
async def get_oauth_url(
    catalog_key: str,
    redirect_uri: str,
    current_user: User = Depends(get_current_user)
):
    """Get OAuth authorization URL for integration."""
    
    db = SessionLocal()
    try:
        catalog = db.query(IntegrationCatalog).filter(
            IntegrationCatalog.key == catalog_key
        ).first()
        
        if not catalog or catalog.auth_type != 'oauth2':
            raise HTTPException(400, "Not an OAuth integration")
        
        # Get client credentials from environment
        client_id = os.getenv(catalog.oauth_client_id_env) if catalog.oauth_client_id_env else None
        if not client_id:
            raise HTTPException(500, "OAuth not configured for this integration")
        
        # Generate state token
        state = str(uuid.uuid4())
        
        # Build auth URL
        scopes = ' '.join(catalog.oauth_scopes) if catalog.oauth_scopes else ''
        auth_url = f"{catalog.oauth_auth_url}?client_id={client_id}&redirect_uri={redirect_uri}&scope={scopes}&state={state}&response_type=code"
        
        return {
            "auth_url": auth_url,
            "state": state
        }
        
    finally:
        db.close()


@router.post("/oauth/callback")
async def oauth_callback(
    code: str,
    state: str,
    catalog_key: str,
    current_user: User = Depends(get_current_user)
):
    """Handle OAuth callback and store tokens."""
    # Placeholder - would exchange code for tokens
    return {"status": "not_implemented"}
