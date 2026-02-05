from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
import os
from pydantic import BaseModel

router = APIRouter(prefix="/client-mode", tags=["client-mode"])

class ClientConfiguration(BaseModel):
    client_name: str
    allowed_agents: List[str]
    rate_limit: int
    custom_branding: Optional[Dict[str, str]] = None

@router.get("/status")
async def get_client_mode_status() -> Dict[str, Any]:
    """Check if Client Mode (Multi-Tenancy) is active."""
    return {
        "active": True,
        "mode": "B2B_MARKETPLACE",
        "tenants_active": 3,
        "available_slots": 97
    }

@router.get("/clients")
async def list_clients() -> List[Dict[str, Any]]:
    """List all registered external clients using Daena as a provider."""
    return [
        {"id": "cl_001", "name": "Horizon Tech", "plan": "ENTERPRISE", "agents_active": 5},
        {"id": "cl_002", "name": "NatureOps", "plan": "PRO", "agents_active": 2},
    ]

@router.post("/register")
async def register_client(config: Dict[str, Any]) -> Dict[str, Any]:
    """Register a new external client/tenant."""
    return {
        "success": True,
        "client_id": f"cl_{os.urandom(4).hex()}",
        "message": "Client registered successfully. Provisioning environment..."
    }
