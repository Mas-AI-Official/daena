"""
CMP (Connected Media Protocol) API Router.
Manages connectors, webhooks, and external integrations.
"""

from fastapi import APIRouter, HTTPException, Depends, Body
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime
import logging
import uuid

from backend.routes.auth import get_current_user
from backend.services.cmp import connector_registry
from backend.services.cmp.connector_base import ConnectorConfig

router = APIRouter(prefix="/api/v1/cmp", tags=["CMP"])
logger = logging.getLogger(__name__)


# ==================== Request Models ====================

class CreateConnectorRequest(BaseModel):
    connector_type: str
    name: str
    credentials: Dict[str, Any] = {}
    settings: Dict[str, Any] = {}
    webhook_url: Optional[str] = None
    enabled: bool = True


class ExecuteActionRequest(BaseModel):
    action: str
    params: Dict[str, Any] = {}


# ==================== Connector Types ====================

@router.get("/types")
async def list_connector_types(
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """List all available connector types."""
    types = connector_registry.list_types()
    return {
        "success": True,
        "types": types,
        "count": len(types)
    }


@router.get("/types/{connector_type}/schema")
async def get_connector_schema(
    connector_type: str,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get credentials and settings schema for a connector type."""
    connector_class = connector_registry.get_type(connector_type)
    if not connector_class:
        raise HTTPException(404, f"Connector type '{connector_type}' not found")
    
    return {
        "success": True,
        "connector_type": connector_type,
        "credentials_schema": connector_class.get_credentials_schema(),
        "settings_schema": connector_class.get_settings_schema()
    }


# ==================== Connector Instances ====================

@router.get("/connectors")
async def list_connectors(
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """List all configured connector instances."""
    instances = connector_registry.list_instances()
    return {
        "success": True,
        "connectors": instances,
        "count": len(instances)
    }


@router.post("/connectors")
async def create_connector(
    request: CreateConnectorRequest,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Create a new connector instance."""
    # Verify user role
    user_role = current_user.get("role", "user")
    if user_role not in ["founder", "daena_vp", "admin"]:
        raise HTTPException(403, "Only Founder/Admin can create connectors")
    
    # Check if connector type exists
    if not connector_registry.get_type(request.connector_type):
        raise HTTPException(400, f"Unknown connector type: {request.connector_type}")
    
    # Create config
    connector_id = str(uuid.uuid4())[:8]
    config = ConnectorConfig(
        connector_id=connector_id,
        connector_type=request.connector_type,
        name=request.name,
        credentials=request.credentials,
        settings=request.settings,
        webhook_url=request.webhook_url,
        enabled=request.enabled
    )
    
    # Create instance
    instance = connector_registry.create_instance(config)
    if not instance:
        raise HTTPException(500, "Failed to create connector")
    
    logger.info(f"Connector created: {connector_id} ({request.connector_type}) by {current_user.get('username')}")
    
    return {
        "success": True,
        "connector_id": connector_id,
        "connector_type": request.connector_type,
        "name": request.name
    }


@router.get("/connectors/{connector_id}")
async def get_connector(
    connector_id: str,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get a specific connector's status and info."""
    instance = connector_registry.get_instance(connector_id)
    if not instance:
        raise HTTPException(404, "Connector not found")
    
    return {
        "success": True,
        "connector": instance.get_status(),
        "metadata": instance.get_metadata()
    }


@router.delete("/connectors/{connector_id}")
async def delete_connector(
    connector_id: str,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Delete a connector instance."""
    user_role = current_user.get("role", "user")
    if user_role not in ["founder", "daena_vp", "admin"]:
        raise HTTPException(403, "Only Founder/Admin can delete connectors")
    
    if not connector_registry.remove_instance(connector_id):
        raise HTTPException(404, "Connector not found")
    
    logger.info(f"Connector deleted: {connector_id} by {current_user.get('username')}")
    
    return {
        "success": True,
        "message": f"Connector {connector_id} deleted"
    }


# ==================== Connection Management ====================

@router.post("/connectors/{connector_id}/connect")
async def connect_connector(
    connector_id: str,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Connect a connector to its external service."""
    instance = connector_registry.get_instance(connector_id)
    if not instance:
        raise HTTPException(404, "Connector not found")
    
    success = await instance.connect()
    
    return {
        "success": success,
        "status": instance.status.value,
        "error": instance.last_error if not success else None
    }


@router.post("/connectors/{connector_id}/disconnect")
async def disconnect_connector(
    connector_id: str,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Disconnect a connector from its external service."""
    instance = connector_registry.get_instance(connector_id)
    if not instance:
        raise HTTPException(404, "Connector not found")
    
    success = await instance.disconnect()
    
    return {
        "success": success,
        "status": instance.status.value
    }


@router.post("/connectors/{connector_id}/test")
async def test_connector(
    connector_id: str,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Test a connector's connection."""
    result = await connector_registry.test_connection(connector_id)
    return result


# ==================== Action Execution ====================

@router.post("/connectors/{connector_id}/actions")
async def execute_connector_action(
    connector_id: str,
    request: ExecuteActionRequest,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Execute an action on a connector."""
    result = await connector_registry.execute_action(
        connector_id=connector_id,
        action=request.action,
        params=request.params
    )
    return result


# ==================== Webhooks ====================

@router.post("/webhooks/{connector_id}")
async def receive_webhook(
    connector_id: str,
    payload: Dict[str, Any] = Body(...)
) -> Dict[str, Any]:
    """Receive webhook from external service."""
    result = await connector_registry.handle_webhook(
        connector_id=connector_id,
        payload=payload
    )
    return result


# ==================== Stats ====================

@router.get("/stats")
async def get_cmp_stats(
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get CMP registry statistics."""
    stats = connector_registry.get_stats()
    return {
        "success": True,
        **stats
    }
