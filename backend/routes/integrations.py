"""
Integration API Routes
Enhanced endpoints for managing integrations with secure credential storage
"""
from fastapi import APIRouter, HTTPException, Body
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from backend.services.integration_registry import get_integration_registry
from backend.services.credentials_manager import get_credentials_manager

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])

# Request/Response Models
class ConnectRequest(BaseModel):
    credentials: Dict[str, Any]
    user_id: str = "default"

class ExecuteRequest(BaseModel):
    action: str
    params: Dict[str, Any] = {}
    user_id: str = "default"

@router.get("")
async def list_integrations(
    category: Optional[str] = None,
    status: Optional[str] = None
) -> Dict[str, Any]:
    """
    List all available integrations
    Query params:
        - category: Filter by category (ai, communication, productivity, etc.)
        - status: Filter by status (available, configured, active)
    """
    try:
        registry = get_integration_registry()
        integrations = registry.list_all(category=category, status=status)
        
        # Add configured status for each integration
        creds_manager = get_credentials_manager()
        configured_integrations = creds_manager.list_configured()
        
        for integration in integrations:
            if integration["id"] in configured_integrations:
                integration["has_credentials"] = True
            else:
                integration["has_credentials"] = False
        
        return {
            "success": True,
            "count": len(integrations),
            "integrations": integrations
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{integration_id}")
async def get_integration(integration_id: str) -> Dict[str, Any]:
    """Get specific integration details"""
    try:
        registry = get_integration_registry()
        integration = registry.get(integration_id)
        
        if not integration:
            raise HTTPException(status_code=404, detail=f"Integration '{integration_id}' not found")
        
        # Check if credentials are configured
        creds_manager = get_credentials_manager()
        credentials = creds_manager.retrieve(integration_id)
        
        integration["has_credentials"] = credentials is not None
        if credentials:
            integration["credentials_preview"] = creds_manager.mask_credentials(credentials)
        
        return {
            "success": True,
            "integration": integration
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{integration_id}/connect")
async def connect_integration(
    integration_id: str,
    request: ConnectRequest
) -> Dict[str, Any]:
    """
    Connect/configure an integration
    Body:
        - credentials: Dict with API keys, tokens, etc.
        - user_id: User ID (default: "default")
    """
    try:
        registry = get_integration_registry()
        integration_config = registry.get(integration_id)
        
        if not integration_config:
            raise HTTPException(status_code=404, detail=f"Integration '{integration_id}' not found")
        
        # Store credentials
        creds_manager = get_credentials_manager()
        creds_manager.store(integration_id, request.credentials, request.user_id)
        
        # Update status
        registry.update_status(integration_id, "configured")
        
        return {
            "success": True,
            "message": f"Successfully configured {integration_config['name']}",
            "integration_id": integration_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{integration_id}/test")
async def test_integration(
    integration_id: str,
    user_id: str = "default"
) -> Dict[str, Any]:
    """
    Test an integration connection
    """
    try:
        registry = get_integration_registry()
        integration_config = registry.get(integration_id)
        
        if not integration_config:
            raise HTTPException(status_code=404, detail=f"Integration '{integration_id}' not found")
        
        # Get credentials
        creds_manager = get_credentials_manager()
        credentials = creds_manager.retrieve(integration_id, user_id)
        
        if not credentials:
            raise HTTPException(status_code=400, detail=f"No credentials found for {integration_id}. Please connect first.")
        
        # Try to load and test integration
        try:
            # Dynamic import based on integration_id
            module_name = f"backend.services.integrations.{integration_id}_integration"
            module = __import__(module_name, fromlist=["Integration"])
            Integration = getattr(module, "Integration")
            
            instance = Integration(integration_id, credentials)
            await instance.connect()
            result = await instance.test_connection()
            
            if result.get("success"):
                registry.update_status(integration_id, "active")
                registry.register_active(integration_id, instance)
            
            return result
        except ModuleNotFoundError:
            return {
                "success": False,
                "message": f"Integration module not yet implemented for {integration_config['name']}",
                "integration_id": integration_id
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "integration_id": integration_id
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{integration_id}/execute")
async def execute_integration(
    integration_id: str,
    request: ExecuteRequest
) -> Dict[str, Any]:
    """
    Execute an action with an integration
    Body:
        - action: Action to perform (e.g., "send_email", "create_sheet")
        - params: Action parameters
        - user_id: User ID
    """
    try:
        registry = get_integration_registry()
        
        # Try to get active integration instance
        instance = registry.get_active(integration_id)
        
        if not instance:
            # Try to activate integration
            integration_config = registry.get(integration_id)
            if not integration_config:
                raise HTTPException(status_code=404, detail=f"Integration '{integration_id}' not found")
            
            creds_manager = get_credentials_manager()
            credentials = creds_manager.retrieve(integration_id, request.user_id)
            
            if not credentials:
                raise HTTPException(status_code=400, detail=f"No credentials found for {integration_id}")
            
            # Dynamic import
            try:
                module_name = f"backend.services.integrations.{integration_id}_integration"
                module = __import__(module_name, fromlist=["Integration"])
                Integration = getattr(module, "Integration")
                
                instance = Integration(integration_id, credentials)
                await instance.connect()
                registry.register_active(integration_id, instance)
            except ModuleNotFoundError:
                raise HTTPException(status_code=501, detail=f"Integration not yet implemented: {integration_id}")
        
        # Execute action
        result = await instance.execute(request.action, request.params)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{integration_id}/disconnect")
async def disconnect_integration(
    integration_id: str,
    user_id: str = "default"
) -> Dict[str, Any]:
    """
    Disconnect an integration (remove credentials)
    """
    try:
        registry = get_integration_registry()
        creds_manager = get_credentials_manager()
        
        # Remove credentials
        creds_manager.delete(integration_id, user_id)
        
        # Deactivate
        registry.deactivate(integration_id)
        registry.update_status(integration_id, "available")
        
        return {
            "success": True,
            "message": f"Successfully disconnected {integration_id}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{integration_id}/credentials")
async def get_credentials_preview(
    integration_id: str,
    user_id: str = "default"
) -> Dict[str, Any]:
    """Get masked credentials preview"""
    try:
        creds_manager = get_credentials_manager()
        credentials = creds_manager.retrieve(integration_id, user_id)
        
        if not credentials:
            return {
                "success": False,
                "message": "No credentials configured"
            }
        
        return {
            "success": True,
            "credentials": creds_manager.mask_credentials(credentials)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
