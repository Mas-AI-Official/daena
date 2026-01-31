"""
Client Mode - AI Agent Marketplace

Add-On 2: Multi-tenant support for external clients using Daena as a service.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Header, Body
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/client-mode", tags=["Client Mode"])


# ═══════════════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════════════

class ClientTenant(BaseModel):
    id: str
    name: str
    api_key: str
    status: str  # active, suspended
    plan: str  # basic, pro, enterprise
    services_enabled: List[str]
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ServiceOffering(BaseModel):
    id: str
    name: str
    description: str
    department: str
    price_model: str  # per_request, subscription
    price_amount: float
    capabilities: List[str]


class ServiceRequest(BaseModel):
    request_id: str
    client_id: str
    service_id: str
    payload: Dict
    status: str  # pending, processing, completed, failed
    result: Optional[Dict] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════
# Mock Data Store
# ═══════════════════════════════════════════════════════════════════════

CLIENTS = {}
REQUESTS = {}

OFFERINGS = [
    ServiceOffering(
        id="finance_bookkeeping",
        name="Bookkeeping as a Service",
        description="Automated categorization and reconciliation",
        department="finance",
        price_model="subscription",
        price_amount=299.0,
        capabilities=["expense_tracking", "reconciliation"]
    ),
    ServiceOffering(
        id="legal_contracts",
        name="Contract Generation",
        description="Generate standard legal agreements",
        department="legal",
        price_model="per_request",
        price_amount=49.0,
        capabilities=["contract_generation", "compliance_check"]
    ),
    ServiceOffering(
        id="support_tier1",
        name="Tier 1 Support Agent",
        description="24/7 AI support handling common queries",
        department="support",
        price_model="subscription",
        price_amount=499.0,
        capabilities=["ticket_response", "kb_search"]
    )
]


# ═══════════════════════════════════════════════════════════════════════
# Client Management
# ═══════════════════════════════════════════════════════════════════════

@router.post("/onboard")
async def onboard_client(
    name: str = Body(...),
    plan: str = Body("basic")
):
    """Onboard a new external client"""
    client_id = f"client_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    api_key = f"dk_{client_id}_secret"
    
    client = ClientTenant(
        id=client_id,
        name=name,
        api_key=api_key,
        status="active",
        plan=plan,
        services_enabled=[]
    )
    
    CLIENTS[client_id] = client
    
    return {
        "success": True,
        "client": client,
        "message": "Client onboarded successfully. Save the API key!"
    }


@router.get("/catalog")
async def get_service_catalog():
    """Get available services for clients"""
    return {"offerings": OFFERINGS}


# ═══════════════════════════════════════════════════════════════════════
# Service Execution
# ═══════════════════════════════════════════════════════════════════════

def verify_client_key(x_api_key: str = Header(...)):
    """Verify client API key"""
    client = next((c for c in CLIENTS.values() if c.api_key == x_api_key), None)
    if not client:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return client


@router.post("/requests/{service_id}")
async def submit_request(
    service_id: str,
    payload: Dict = Body(...),
    client: ClientTenant = Depends(verify_client_key)
):
    """Submit a service request as a client"""
    # Verify service exists
    offering = next((o for o in OFFERINGS if o.id == service_id), None)
    if not offering:
        raise HTTPException(status_code=404, detail="Service not found")
    
    # Create request
    req_id = f"req_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    request = ServiceRequest(
        request_id=req_id,
        client_id=client.id,
        service_id=service_id,
        payload=payload,
        status="processing"
    )
    
    REQUESTS[req_id] = request
    
    # Mock processing (would normally queue to agent)
    # For now, just return success
    return {
        "success": True,
        "request_id": req_id,
        "status": "processing",
        "estimated_completion": "5 minutes"
    }


@router.get("/requests/{request_id}")
async def get_request_status(
    request_id: str,
    client: ClientTenant = Depends(verify_client_key)
):
    """Get status of a request"""
    req = REQUESTS.get(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    
    if req.client_id != client.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return req
