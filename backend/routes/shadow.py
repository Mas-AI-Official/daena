"""
Shadow Department API Routes — Defensive Deception Layer

Provides API endpoints for:
- Shadow agent statistics and alerts
- Honeypot management
- Threat intelligence
- FOUNDER ONLY ACCESS

NOTE: These endpoints should be protected with founder-level auth.
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import logging

router = APIRouter(prefix="/api/v1/shadow", tags=["shadow"])
logger = logging.getLogger(__name__)


# =============================================
# HONEYPOT DECOY ROUTES
# These look like real sensitive endpoints but trigger alerts
# =============================================

@router.get("/admin/keys", include_in_schema=False)
async def honeypot_admin_keys(request: Request):
    """HONEYPOT: Fake admin API keys endpoint."""
    from backend.services.shadow.honeypot import get_honeypot_manager
    
    manager = get_honeypot_manager()
    
    # Record the hit
    request_data = {
        "ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", "unknown"),
        "path": "/api/v1/shadow/admin/keys",
        "method": "GET",
        "headers": dict(request.headers)
    }
    manager.record_hit("hp_admin_keys", request_data)
    
    # Return fake data
    return manager.get_fake_response("hp_admin_keys")


@router.get("/internal/vault", include_in_schema=False)
async def honeypot_vault(request: Request):
    """HONEYPOT: Fake database vault dump."""
    from backend.services.shadow.honeypot import get_honeypot_manager
    
    manager = get_honeypot_manager()
    
    request_data = {
        "ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", "unknown"),
        "path": "/api/v1/shadow/internal/vault",
        "method": "GET",
        "headers": dict(request.headers)
    }
    manager.record_hit("hp_vault", request_data)
    
    return manager.get_fake_response("hp_vault")


@router.get("/config/secrets", include_in_schema=False)
async def honeypot_config(request: Request):
    """HONEYPOT: Fake config secrets."""
    from backend.services.shadow.honeypot import get_honeypot_manager
    
    manager = get_honeypot_manager()
    
    request_data = {
        "ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", "unknown"),
        "path": "/api/v1/shadow/config/secrets",
        "method": "GET",
        "headers": dict(request.headers)
    }
    manager.record_hit("hp_config", request_data)
    
    return manager.get_fake_response("hp_config")


# =============================================
# SHADOW AGENT DASHBOARD (FOUNDER ONLY)
# =============================================

@router.get("/dashboard")
async def get_shadow_dashboard():
    """Get Shadow department dashboard data. FOUNDER ONLY."""
    try:
        from backend.services.shadow.shadow_agent import get_shadow_agent
        
        shadow = get_shadow_agent()
        dashboard = shadow.get_dashboard_data()
        
        return {
            "success": True,
            **dashboard
        }
    except Exception as e:
        logger.error(f"Shadow dashboard failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
async def get_shadow_alerts(hours: int = 24):
    """Get recent alerts from Shadow agent."""
    try:
        from backend.services.shadow.shadow_agent import get_shadow_agent
        
        shadow = get_shadow_agent()
        alerts = shadow.get_recent_alerts(hours)
        
        return {
            "success": True,
            "hours": hours,
            "alerts": [a.__dict__ for a in alerts],
            "count": len(alerts)
        }
    except Exception as e:
        logger.error(f"Get alerts failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/honeypots")
async def get_honeypots():
    """Get all honeypot configurations."""
    try:
        from backend.services.shadow.honeypot import get_honeypot_manager
        
        manager = get_honeypot_manager()
        
        return {
            "success": True,
            "endpoints": manager.get_all_endpoints(),
            "canaries": manager.get_all_canaries(),
            "stats": manager.get_stats()
        }
    except Exception as e:
        logger.error(f"Get honeypots failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/threats")
async def get_threats():
    """Get threat intelligence report."""
    try:
        from backend.services.shadow.threat_intel import get_threat_intel
        
        intel = get_threat_intel()
        report = intel.generate_report()
        
        return {
            "success": True,
            **report
        }
    except Exception as e:
        logger.error(f"Get threats failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ips/blocked")
async def get_blocked_ips():
    """Get list of high-threat IPs."""
    try:
        from backend.services.shadow.threat_intel import get_threat_intel
        
        intel = get_threat_intel()
        ips = intel.get_high_threat_ips()
        
        return {
            "success": True,
            "blocked_ips": ips,
            "count": len(ips)
        }
    except Exception as e:
        logger.error(f"Get blocked IPs failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ScanInputRequest(BaseModel):
    content: str = Field(..., description="Content to scan")
    source: str = Field(default="api", description="Source of content")


@router.post("/scan")
async def scan_input(request: ScanInputRequest, http_request: Request):
    """Scan input for threats."""
    try:
        from backend.services.shadow.shadow_agent import get_shadow_agent
        
        shadow = get_shadow_agent()
        
        metadata = {
            "ip": http_request.client.host if http_request.client else "unknown",
            "user_agent": http_request.headers.get("user-agent", "unknown")
        }
        
        alerts = shadow.scan_input(
            content=request.content,
            source=request.source,
            metadata=metadata
        )
        
        return {
            "success": True,
            "clean": len(alerts) == 0,
            "alerts": [a.__dict__ for a in alerts]
        }
    except Exception as e:
        logger.error(f"Scan input failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
