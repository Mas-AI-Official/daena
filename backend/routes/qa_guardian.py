"""
QA Guardian API Routes - Endpoints for the QA Guardian system

Integrates with Daena's existing FastAPI backend.
"""

import os
from datetime import datetime
from typing import List, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from backend.qa_guardian import (
    is_enabled, is_auto_fix_enabled, QA_GUARDIAN_ENABLED,
    Severity, RiskLevel, IncidentStatus
)
from backend.qa_guardian.guardian_loop import get_guardian_loop
from backend.qa_guardian.schemas.incident import Incident, IncidentCreate, IncidentUpdate

router = APIRouter(prefix="/qa", tags=["QA Guardian"])

# Path to dashboard template
DASHBOARD_TEMPLATE = Path(__file__).parent.parent.parent / "frontend" / "templates" / "qa_guardian_dashboard.html"


@router.get("/ui", response_class=HTMLResponse)
async def serve_dashboard():
    """Serve the QA Guardian dashboard UI"""
    try:
        return HTMLResponse(content=DASHBOARD_TEMPLATE.read_text(encoding="utf-8"), status_code=200)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Dashboard not found</h1>", status_code=404)


# ═══════════════════════════════════════════════════════════════════════
# Response Models
# ═══════════════════════════════════════════════════════════════════════

class GuardianStatus(BaseModel):
    enabled: bool
    running: bool
    auto_fix_enabled: bool
    kill_switch_active: bool
    rate_limit_remaining: int
    open_incidents: int
    total_incidents_24h: int


class IncidentSummary(BaseModel):
    incident_id: str
    severity: str
    status: str
    category: str
    subsystem: str
    summary: str
    created_at: datetime
    approval_required: bool


class ApprovalAction(BaseModel):
    action: str  # "approved" | "denied"
    reason: str


class ReportErrorRequest(BaseModel):
    error_type: str
    error_message: str
    stack_trace: Optional[str] = None
    subsystem: Optional[str] = None


class DashboardData(BaseModel):
    status: GuardianStatus
    open_incidents: List[IncidentSummary]
    recent_fixes: List[dict]
    regression_status: dict
    security_summary: dict


# ═══════════════════════════════════════════════════════════════════════
# Status & Control Endpoints
# ═══════════════════════════════════════════════════════════════════════

@router.get("/status", response_model=GuardianStatus)
async def get_status():
    """Get QA Guardian status"""
    loop = get_guardian_loop()
    status = loop.get_status()
    
    return GuardianStatus(
        enabled=status["enabled"],
        running=status["running"],
        auto_fix_enabled=status["auto_fix_enabled"],
        kill_switch_active=not status["enabled"] and QA_GUARDIAN_ENABLED,
        rate_limit_remaining=status["rate_limit_remaining"],
        open_incidents=status["open_incidents"],
        total_incidents_24h=status["total_incidents_24h"]
    )


@router.post("/kill-switch")
async def toggle_kill_switch(enable: bool = Body(..., embed=True)):
    """
    Enable or disable the kill switch.
    
    When enabled, all auto-fix attempts stop immediately.
    Requires founder authorization (TODO: add auth check).
    """
    import os
    # In production, this would persist to .env or config
    # For now, just update the environment variable
    os.environ["QA_GUARDIAN_KILL_SWITCH"] = "true" if enable else "false"
    
    loop = get_guardian_loop()
    
    return {
        "success": True,
        "kill_switch_active": enable,
        "message": "Kill switch " + ("activated" if enable else "deactivated")
    }


@router.post("/start")
async def start_guardian():
    """Start the guardian loop"""
    if not is_enabled():
        raise HTTPException(
            status_code=400, 
            detail="QA Guardian is disabled. Set QA_GUARDIAN_ENABLED=true"
        )
    
    loop = get_guardian_loop()
    await loop.start()
    
    return {"success": True, "message": "Guardian loop started"}


@router.post("/stop")
async def stop_guardian():
    """Stop the guardian loop"""
    loop = get_guardian_loop()
    await loop.stop()
    
    return {"success": True, "message": "Guardian loop stopped"}


# ═══════════════════════════════════════════════════════════════════════
# Incident Management Endpoints
# ═══════════════════════════════════════════════════════════════════════

@router.get("/incidents", response_model=List[IncidentSummary])
async def list_incidents(
    status: Optional[str] = Query(None, description="Filter by status"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    limit: int = Query(50, le=200)
):
    """List incidents with optional filters"""
    loop = get_guardian_loop()
    store = loop.incident_store
    
    if status:
        incidents = store.get_by_status(status)
    else:
        incidents = list(store.incidents.values())
    
    # Apply severity filter
    if severity:
        incidents = [i for i in incidents if i.severity == severity]
    
    # Sort by created_at descending
    incidents.sort(key=lambda x: x.created_at, reverse=True)
    
    # Limit and convert to summary
    return [
        IncidentSummary(
            incident_id=i.incident_id,
            severity=i.severity,
            status=i.status,
            category=i.category,
            subsystem=i.subsystem,
            summary=i.summary,
            created_at=i.created_at,
            approval_required=i.approval_required
        )
        for i in incidents[:limit]
    ]


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: str):
    """Get full incident details"""
    loop = get_guardian_loop()
    incident = loop.incident_store.get(incident_id)
    
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    return incident.model_dump()


@router.patch("/incidents/{incident_id}")
async def update_incident(incident_id: str, update: IncidentUpdate):
    """Update an incident"""
    loop = get_guardian_loop()
    incident = loop.incident_store.get(incident_id)
    
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    # Apply updates
    if update.severity:
        incident.severity = update.severity
    if update.status:
        incident.status = update.status
        if update.status == IncidentStatus.CLOSED:
            incident.closed_at = datetime.utcnow()
    if update.risk_level:
        incident.risk_level = update.risk_level
    if update.owner:
        incident.owner = update.owner
    if update.resolution:
        incident.resolution = update.resolution
    
    loop.incident_store.update(incident)
    
    return {"success": True, "incident_id": incident_id}


@router.post("/incidents/{incident_id}/approve")
async def approve_incident_action(incident_id: str, approval: ApprovalAction):
    """
    Approve or deny a proposed action for an incident.
    
    This is the founder approval gate for high-risk fixes.
    """
    loop = get_guardian_loop()
    incident = loop.incident_store.get(incident_id)
    
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    if not incident.approval_required:
        raise HTTPException(status_code=400, detail="Incident does not require approval")
    
    if approval.action == "approved":
        incident.status = IncidentStatus.VERIFIED
        incident.resolution = f"Approved by founder: {approval.reason}"
        # TODO: Trigger actual fix application
    elif approval.action == "denied":
        incident.status = IncidentStatus.CLOSED
        incident.resolution = f"Denied by founder: {approval.reason}"
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Use 'approved' or 'denied'")
    
    loop.incident_store.update(incident)
    
    return {
        "success": True,
        "incident_id": incident_id,
        "new_status": incident.status
    }


# ═══════════════════════════════════════════════════════════════════════
# Manual Reporting Endpoints
# ═══════════════════════════════════════════════════════════════════════

@router.post("/report/error")
async def report_error(request: ReportErrorRequest):
    """Manually report an error to QA Guardian"""
    loop = get_guardian_loop()
    loop.report_error(
        error_type=request.error_type,
        error_message=request.error_message,
        stack_trace=request.stack_trace,
        subsystem=request.subsystem
    )
    
    return {"success": True, "message": "Error reported to QA Guardian"}


@router.post("/report/task-failure")
async def report_task_failure(
    task_id: str = Body(...),
    agent_id: Optional[str] = Body(None),
    error_message: Optional[str] = Body(None)
):
    """Report a task failure"""
    loop = get_guardian_loop()
    loop.report_task_failure(task_id, agent_id, error_message)
    
    return {"success": True, "message": "Task failure reported"}


@router.post("/report/timeout")
async def report_timeout(
    operation: str = Body(...),
    timeout_seconds: int = Body(...),
    subsystem: Optional[str] = Body(None)
):
    """Report a timeout"""
    loop = get_guardian_loop()
    loop.report_timeout(operation, timeout_seconds, subsystem)
    
    return {"success": True, "message": "Timeout reported"}


# ═══════════════════════════════════════════════════════════════════════
# Dashboard Endpoint
# ═══════════════════════════════════════════════════════════════════════

@router.get("/dashboard", response_model=DashboardData)
async def get_dashboard():
    """
    Get dashboard data for QA Guardian UI.
    
    Returns:
    - Current status
    - Open incidents
    - Recent fixes
    - Regression run status
    - Security scan summary
    """
    loop = get_guardian_loop()
    status = await get_status()
    
    # Get open incidents
    open_incidents = [
        IncidentSummary(
            incident_id=i.incident_id,
            severity=i.severity,
            status=i.status,
            category=i.category,
            subsystem=i.subsystem,
            summary=i.summary,
            created_at=i.created_at,
            approval_required=i.approval_required
        )
        for i in loop.incident_store.get_open()[:10]
    ]
    
    # TODO: Get actual fix history, regression status, security summary
    recent_fixes = []
    regression_status = {
        "last_run": None,
        "passed": 0,
        "failed": 0,
        "status": "not_run"
    }
    security_summary = {
        "last_scan": None,
        "critical": 0,
        "high": 0,
        "status": "not_run"
    }
    
    return DashboardData(
        status=status,
        open_incidents=open_incidents,
        recent_fixes=recent_fixes,
        regression_status=regression_status,
        security_summary=security_summary
    )


@router.post("/request-review")
async def request_qa_review(
    target: str = Body(..., description="What to review: 'full', 'security', 'regression'"),
    notes: Optional[str] = Body(None)
):
    """
    Founder-initiated QA review request.
    
    Triggers the appropriate QA agents to perform a review.
    """
    # TODO: Implement actual agent triggering
    return {
        "success": True,
        "message": f"QA review requested: {target}",
        "request_id": f"review_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    }


# ═══════════════════════════════════════════════════════════════════════
# Regression & Golden Workflow Endpoints
# ═══════════════════════════════════════════════════════════════════════

@router.post("/run-regression")
async def run_regression(
    run_type: str = Body("smoke", description="'smoke', 'golden', or 'full'")
):
    """
    Trigger a regression test run.
    
    - smoke: Quick smoke tests only
    - golden: Golden workflows only
    - full: Complete test suite
    """
    # TODO: Implement actual test execution
    return {
        "success": True,
        "message": f"Regression run initiated: {run_type}",
        "run_id": f"reg_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    }


@router.post("/run-security-scan")
async def run_security_scan(
    scan_type: str = Body("full", description="'secrets', 'dependencies', or 'full'")
):
    """
    Trigger a security scan.
    """
    # TODO: Implement actual security scanning
    return {
        "success": True,
        "message": f"Security scan initiated: {scan_type}",
        "scan_id": f"sec_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    }


# ═══════════════════════════════════════════════════════════════════════
# Additional UI Endpoints
# ═══════════════════════════════════════════════════════════════════════

APPROVAL_TEMPLATE = Path(__file__).parent.parent.parent / "frontend" / "templates" / "approval_workflow.html"
CMP_CANVAS_TEMPLATE = Path(__file__).parent.parent.parent / "frontend" / "templates" / "cmp_canvas.html"
CONTROL_CENTER_TEMPLATE = Path(__file__).parent.parent.parent / "frontend" / "templates" / "control_center.html"


@router.get("/approvals", response_class=HTMLResponse)
async def serve_approvals():
    """Serve the approval workflow UI"""
    try:
        return HTMLResponse(content=APPROVAL_TEMPLATE.read_text(encoding="utf-8"), status_code=200)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Approval Workflow not found</h1>", status_code=404)


# CMP Canvas route (separate from /qa prefix)
from fastapi import APIRouter as _APIRouter
cmp_canvas_router = _APIRouter()

@cmp_canvas_router.get("/cmp-canvas", response_class=HTMLResponse)
async def serve_cmp_canvas():
    """Serve the CMP Canvas UI (n8n-like node graph)"""
    try:
        return HTMLResponse(content=CMP_CANVAS_TEMPLATE.read_text(encoding="utf-8"), status_code=200)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>CMP Canvas not found</h1>", status_code=404)


@cmp_canvas_router.get("/control-center", response_class=HTMLResponse)
async def serve_control_center():
    """Serve the Control Center UI"""
    try:
        return HTMLResponse(content=CONTROL_CENTER_TEMPLATE.read_text(encoding="utf-8"), status_code=200)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Control Center not found</h1>", status_code=404)


VOICE_DIAGNOSTICS_TEMPLATE = Path(__file__).parent.parent.parent / "frontend" / "templates" / "voice_diagnostics.html"
INCIDENT_ROOM_TEMPLATE = Path(__file__).parent.parent.parent / "frontend" / "templates" / "incident_room.html"


@cmp_canvas_router.get("/voice-diagnostics", response_class=HTMLResponse)
async def serve_voice_diagnostics():
    """Serve the Voice Diagnostics wizard UI"""
    try:
        return HTMLResponse(content=VOICE_DIAGNOSTICS_TEMPLATE.read_text(encoding="utf-8"), status_code=200)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Voice Diagnostics not found</h1>", status_code=404)


@cmp_canvas_router.get("/incident-room", response_class=HTMLResponse)
async def serve_incident_room():
    """Serve the Incident Room UI (deception hits, lockdown/unlock)."""
    try:
        return HTMLResponse(content=INCIDENT_ROOM_TEMPLATE.read_text(encoding="utf-8"), status_code=200)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Incident Room not found</h1>", status_code=404)

