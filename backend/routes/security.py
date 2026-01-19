"""
Security Endpoints for Daena AI VP.
Provides access to threat detection, red/blue team simulation, and security monitoring.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from backend.services.threat_detection import threat_detector
from backend.services.red_blue_team import red_blue_simulator
from backend.routes.monitoring import verify_monitoring_auth
from starlette.requests import Request

# Import reverse-attack AI (Masoud-only department)
try:
    from backend.services.reverse_attack_ai import reverse_attack_ai
    REVERSE_ATTACK_AVAILABLE = True
except ImportError:
    REVERSE_ATTACK_AVAILABLE = False
    reverse_attack_ai = None

router = APIRouter(prefix="/api/v1/security", tags=["security"])
logger = logging.getLogger(__name__)


@router.get("/threats")
async def get_threats(
    request: Request,
    tenant_id: Optional[str] = Query(None),
    threat_level: Optional[str] = Query(None),
    hours: int = Query(24, ge=1, le=168),
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Get threat detection results.
    
    Args:
        tenant_id: Filter by tenant (optional)
        threat_level: Filter by threat level (low, medium, high, critical)
        hours: Look back N hours (1-168)
    
    Returns:
        List of threats matching criteria
    """
    # Use tenant_id from query or request state
    filter_tenant = tenant_id or getattr(request.state, 'tenant_id', 'default')
    
    # Parse threat level (simplified - threat_detector will handle)
    # Get threats with filters
    level_enum = None
    if threat_level:
        try:
            from backend.services.threat_detection import ThreatLevel
            level_enum = ThreatLevel[threat_level.upper()]
        except KeyError:
            pass
    
    threats = threat_detector.get_threats(
        tenant_id=filter_tenant if filter_tenant != "default" else None,
        threat_level=level_enum,
        hours=hours
    )
    
    return {
        "success": True,
        "count": len(threats),
        "filters": {
            "tenant_id": filter_tenant,
            "threat_level": threat_level,
            "hours": hours
        },
        "threats": [t.to_dict() for t in threats]
    }


@router.get("/threats/summary")
async def get_threat_summary(
    request: Request,
    tenant_id: Optional[str] = Query(None),
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Get threat summary statistics.
    
    Returns:
        Threat summary with counts by level and type
    """
    filter_tenant = tenant_id or getattr(request.state, 'tenant_id', 'default')
    
    summary = threat_detector.get_threat_summary(
        tenant_id=filter_tenant if filter_tenant != "default" else None
    )
    
    return {
        "success": True,
        "tenant_id": filter_tenant,
        "summary": summary
    }


@router.post("/red-blue/drill")
async def run_defense_drill(
    request: Request,
    scenarios: Optional[List[str]] = None,
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Run red/blue team defense drill (synthetic attacks).
    
    IMPORTANT: All attacks are synthetic and internal only.
    No real exploits, no external systems, no actual harm.
    
    Args:
        scenarios: List of attack scenarios to test (optional, defaults to all)
    
    Returns:
        Drill results with detection/block rates
    """
    # Run drill (red_blue_simulator will handle scenarios)
    results = await red_blue_simulator.run_defense_drill(scenarios=scenarios)
    
    return {
        "success": True,
        "message": "Defense drill completed (synthetic attacks only)",
        "results": results
    }


@router.get("/red-blue/stats")
async def get_defense_stats(
    request: Request,
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Get red/blue team defense statistics.
    
    Returns:
        Defense statistics (detection rate, block rate, etc.)
    """
    stats = red_blue_simulator.get_defense_stats()
    
    return {
        "success": True,
        "defense_stats": stats
    }


@router.post("/threats/detect")
async def detect_threat(
    request: Request,
    threat_type: str,
    metadata: Dict[str, Any],
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Manually trigger threat detection (for testing).
    
    Args:
        threat_type: Type of threat to detect
        metadata: Threat metadata
    
    Returns:
        Detection result
    """
    tenant_id = getattr(request.state, 'tenant_id', metadata.get("tenant_id", "default"))
    
    # Route to appropriate detector
    threat = None
    
    if threat_type == "rate_limit":
        threat = threat_detector.detect_rate_limit_violation(
            tenant_id=tenant_id,
            endpoint=metadata.get("endpoint", ""),
            request_count=metadata.get("request_count", 0),
            time_window=metadata.get("time_window", 60.0)
        )
    elif threat_type == "prompt_injection":
        threat = threat_detector.detect_prompt_injection(
            prompt=metadata.get("prompt", ""),
            tenant_id=tenant_id,
            source=metadata.get("source", "manual")
        )
    elif threat_type == "tenant_isolation":
        threat = threat_detector.detect_tenant_isolation_violation(
            tenant_id=tenant_id,
            attempted_access=metadata.get("attempted_access", ""),
            source=metadata.get("source", "manual")
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown threat type: {threat_type}")
    
    return {
        "success": True,
        "detected": threat is not None,
        "threat": threat.to_dict() if threat else None
    }


@router.get("/reverse-attack/traces")
async def get_reverse_attack_traces(
    request: Request,
    attack_type: Optional[str] = None,
    source_ip: Optional[str] = None,
    limit: int = 100,
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Get reverse-attack AI traces (Masoud-only).
    
    IMPORTANT: This endpoint is only accessible to authorized users (Masoud).
    """
    if not REVERSE_ATTACK_AVAILABLE:
        raise HTTPException(status_code=404, detail="Reverse-attack AI not available")
    
    # Check authorization (in production, use proper auth)
    user_id = request.headers.get("X-User-ID", "unknown")
    if not reverse_attack_ai.is_authorized(user_id):
        raise HTTPException(status_code=403, detail="Unauthorized: Reverse-attack AI access restricted")
    
    from backend.services.reverse_attack_ai import AttackType
    
    attack_type_enum = None
    if attack_type:
        try:
            attack_type_enum = AttackType[attack_type.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid attack type: {attack_type}")
    
    traces = reverse_attack_ai.get_traces(
        attack_type=attack_type_enum,
        source_ip=source_ip,
        limit=limit
    )
    
    return {
        "success": True,
        "count": len(traces),
        "traces": [
            {
                "trace_id": t.trace_id,
                "attack_type": t.attack_type.value,
                "source_ip": t.source_ip,
                "source_tenant": t.source_tenant,
                "timestamp": t.timestamp,
                "confidence": t.confidence,
                "isolated": t.isolated,
                "reverse_traced": t.reverse_traced
            } for t in traces
        ]
    }


@router.post("/reverse-attack/trace/{trace_id}/reverse")
async def reverse_trace_attack(
    request: Request,
    trace_id: str,
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Reverse-trace an attack (Masoud-only).
    """
    if not REVERSE_ATTACK_AVAILABLE:
        raise HTTPException(status_code=404, detail="Reverse-attack AI not available")
    
    user_id = request.headers.get("X-User-ID", "unknown")
    if not reverse_attack_ai.is_authorized(user_id):
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    result = reverse_attack_ai.reverse_trace(trace_id)
    return {
        "success": True,
        "result": result
    }


@router.post("/reverse-attack/trace/{trace_id}/isolate")
async def isolate_attacker(
    request: Request,
    trace_id: str,
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Isolate an attacker (Masoud-only).
    """
    if not REVERSE_ATTACK_AVAILABLE:
        raise HTTPException(status_code=404, detail="Reverse-attack AI not available")
    
    user_id = request.headers.get("X-User-ID", "unknown")
    if not reverse_attack_ai.is_authorized(user_id):
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    result = reverse_attack_ai.isolate_attacker(trace_id)
    return {
        "success": True,
        "result": result
    }


@router.get("/reverse-attack/stats")
async def get_reverse_attack_stats(
    request: Request,
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Get reverse-attack AI statistics (Masoud-only).
    """
    if not REVERSE_ATTACK_AVAILABLE:
        raise HTTPException(status_code=404, detail="Reverse-attack AI not available")
    
    user_id = request.headers.get("X-User-ID", "unknown")
    if not reverse_attack_ai.is_authorized(user_id):
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    stats = reverse_attack_ai.get_stats()
    return {
        "success": True,
        "stats": stats
    }


@router.post("/honeytokens/create")
async def create_honeytoken(
    request: Request,
    token_type: str,
    fake_data: Dict[str, Any],
    tenant_id: Optional[str] = Query(None),
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Create a honeytoken trap (authorized users only).
    
    Args:
        token_type: Type of honeytoken (api_key, file_id, memory_id, etc.)
        fake_data: Fake sensitive data to use as bait
        tenant_id: Tenant ID (optional)
    
    Returns:
        Honeytoken ID and metadata
    """
    filter_tenant = tenant_id or getattr(request.state, 'tenant_id', None)
    
    token_id = threat_detector.create_honeytoken(
        token_type=token_type,
        fake_data=fake_data,
        tenant_id=filter_tenant
    )
    
    return {
        "success": True,
        "honeytoken_id": token_id,
        "token_type": token_type,
        "message": "Honeytoken created successfully"
    }


@router.post("/honeytokens/check/{token_id}")
async def check_honeytoken(
    request: Request,
    token_id: str,
    source: Optional[str] = Query(None),
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Check if a honeytoken was accessed (for testing/monitoring).
    
    Args:
        token_id: Honeytoken ID to check
        source: Source of the access (optional)
    
    Returns:
        Access status and threat if detected
    """
    tenant_id = getattr(request.state, 'tenant_id', None)
    source_ip = source or request.client.host if request.client else "unknown"
    
    threat = threat_detector.check_honeytoken_access(
        token_id=token_id,
        source=source_ip,
        tenant_id=tenant_id
    )
    
    return {
        "success": True,
        "honeytoken_id": token_id,
        "breach_detected": threat is not None,
        "threat": threat.to_dict() if threat else None
    }


@router.get("/honeytokens/stats")
async def get_honeytoken_stats(
    request: Request,
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Get honeytoken statistics.
    
    Returns:
        Honeytoken statistics (total tokens, breach rate, etc.)
    """
    stats = threat_detector.get_honeytoken_stats()
    
    return {
        "success": True,
        "stats": stats
    }


@router.post("/kill-switch/activate")
async def activate_kill_switch(
    request: Request,
    reason: str,
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Activate real-time kill-switch (authorized users only).
    
    IMPORTANT: This will immediately stop all operations.
    Use only in emergency situations.
    
    Args:
        reason: Reason for activation
    
    Returns:
        Activation status
    """
    user_id = request.headers.get("X-User-ID", "system")
    
    activated = threat_detector.activate_kill_switch(
        reason=reason,
        activated_by=user_id
    )
    
    if not activated:
        raise HTTPException(status_code=400, detail="Kill-switch already active")
    
    return {
        "success": True,
        "message": "Kill-switch activated",
        "reason": reason,
        "activated_by": user_id
    }


@router.post("/kill-switch/deactivate")
async def deactivate_kill_switch(
    request: Request,
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Deactivate kill-switch to resume operations (authorized users only).
    
    Returns:
        Deactivation status
    """
    user_id = request.headers.get("X-User-ID", "system")
    
    deactivated = threat_detector.deactivate_kill_switch(deactivated_by=user_id)
    
    if not deactivated:
        raise HTTPException(status_code=400, detail="Kill-switch not active")
    
    return {
        "success": True,
        "message": "Kill-switch deactivated",
        "deactivated_by": user_id
    }


@router.get("/kill-switch/status")
async def get_kill_switch_status(
    request: Request,
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Get kill-switch status.
    
    Returns:
        Current kill-switch status
    """
    status = threat_detector.get_kill_switch_status()
    
    return {
        "success": True,
        "status": status
    }
