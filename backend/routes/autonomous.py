"""
Autonomous Execution API Routes

Provides endpoints for:
1. Starting autonomous project execution
2. Monitoring project progress
3. Frontend-to-backend reverse sync (pause, resume, update constraints)
4. Decision ledger access
5. NBMF memory management
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/autonomous", tags=["Autonomous Execution"])


# ============================================================================
# Request/Response Models
# ============================================================================

class ProjectRequest(BaseModel):
    """Request to start autonomous project execution"""
    title: str
    goal: str
    constraints: List[str] = []
    acceptance_criteria: List[str] = []
    deliverables: List[str] = []
    deadline: Optional[str] = None


class TaskControlRequest(BaseModel):
    """Request to control a task (pause/resume)"""
    task_id: str
    action: str  # pause, resume


class ConstraintUpdateRequest(BaseModel):
    """Request to update project constraints"""
    project_id: str
    constraints: List[str]


class MemoryWriteRequest(BaseModel):
    """Request to write to NBMF memory"""
    key: str
    value: Any
    tier: str = "T1"
    context: Optional[Dict[str, Any]] = None
    project_id: Optional[str] = None


class MemoryApprovalRequest(BaseModel):
    """Request to approve pending memory"""
    key: str
    tier: str
    approve: bool = True


# ============================================================================
# Project Execution Endpoints
# ============================================================================

@router.post("/execute")
async def execute_project(request: ProjectRequest):
    """
    Start autonomous project execution.
    
    This triggers the full 11-step execution loop:
    Intake → Decompose → Route → Acquire → Verify → Council → Execute → QA → Deliver → Audit → Improve
    """
    try:
        from backend.services.autonomous_executor import autonomous_executor
        
        project = await autonomous_executor.execute_project({
            "title": request.title,
            "goal": request.goal,
            "constraints": request.constraints,
            "acceptance": request.acceptance_criteria,
            "deliverables": request.deliverables
        })
        
        return {
            "success": True,
            "project_id": project.project_id,
            "status": project.status.value,
            "tasks_count": len(project.task_graph),
            "deliverables_count": len(project.produced_deliverables),
            "ledger_entry": project.ledger_entry
        }
    except Exception as e:
        logger.error(f"Project execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/project/{project_id}")
async def get_project_status(project_id: str):
    """Get current project status and task graph"""
    try:
        from backend.services.autonomous_executor import autonomous_executor
        
        status = autonomous_executor.get_project_status(project_id)
        if not status:
            raise HTTPException(status_code=404, detail="Project not found")
        
        return {"success": True, "project": status}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects")
async def list_active_projects():
    """List all active projects"""
    try:
        from backend.services.autonomous_executor import autonomous_executor
        
        projects = []
        for project_id, project in autonomous_executor.active_projects.items():
            projects.append({
                "project_id": project.project_id,
                "title": project.title,
                "status": project.status.value,
                "created_at": project.created_at.isoformat()
            })
        
        return {"success": True, "projects": projects}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Bidirectional Sync - Frontend → Backend
# ============================================================================

@router.post("/task/control")
async def control_task(request: TaskControlRequest):
    """
    Control task from frontend (pause/resume).
    
    This is the reverse sync: frontend action → backend state change.
    """
    try:
        from backend.services.autonomous_executor import autonomous_executor
        
        if request.action == "pause":
            result = await autonomous_executor.pause_task(request.task_id)
        elif request.action == "resume":
            result = await autonomous_executor.resume_task(request.task_id)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {request.action}")
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/project/constraints")
async def update_constraints(request: ConstraintUpdateRequest):
    """
    Update project constraints from frontend.
    
    This triggers re-routing if project is in early stages.
    """
    try:
        from backend.services.autonomous_executor import autonomous_executor
        
        result = await autonomous_executor.update_constraints(
            request.project_id,
            request.constraints
        )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Decision Ledger Endpoints
# ============================================================================

@router.get("/ledger")
async def get_ledger(limit: int = 100):
    """Get recent decision ledger entries"""
    try:
        from backend.services.decision_ledger import decision_ledger
        
        entries = decision_ledger.get_all_entries(limit)
        stats = decision_ledger.get_stats()
        
        return {
            "success": True,
            "entries": entries,
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ledger/project/{project_id}")
async def get_project_ledger(project_id: str):
    """Get decision ledger for a specific project"""
    try:
        from backend.services.decision_ledger import decision_ledger
        
        entries = decision_ledger.get_project_ledger(project_id)
        
        return {"success": True, "project_id": project_id, "entries": entries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# NBMF Memory Endpoints
# ============================================================================

@router.get("/memory/stats")
async def get_memory_stats():
    """Get NBMF memory statistics"""
    try:
        from backend.services.nbmf_memory import nbmf_memory
        
        return {
            "success": True,
            "stats": nbmf_memory.get_stats(),
            "pending_approvals": nbmf_memory.get_pending_approvals()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/write")
async def write_memory(request: MemoryWriteRequest):
    """Write to NBMF memory"""
    try:
        from backend.services.nbmf_memory import nbmf_memory, MemoryTier
        
        tier = MemoryTier(request.tier)
        entry = nbmf_memory.write(
            key=request.key,
            value=request.value,
            tier=tier,
            context=request.context,
            project_id=request.project_id
        )
        
        return {
            "success": True,
            "memory_id": entry.memory_id,
            "tier": entry.tier.value,
            "key": entry.key,
            "requires_approval": tier.value in ["T3", "T4"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory/read/{key}")
async def read_memory(key: str, tier: Optional[str] = None):
    """Read from NBMF memory"""
    try:
        from backend.services.nbmf_memory import nbmf_memory, MemoryTier
        
        tier_enum = MemoryTier(tier) if tier else None
        value = nbmf_memory.read(key, tier=tier_enum)
        
        return {
            "success": True,
            "key": key,
            "value": value,
            "found": value is not None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/approve")
async def approve_memory(request: MemoryApprovalRequest):
    """Approve or reject pending T3/T4 memory (Founder only)"""
    try:
        from backend.services.nbmf_memory import nbmf_memory, MemoryTier
        
        tier = MemoryTier(request.tier)
        
        if request.approve:
            success = nbmf_memory.approve(request.key, tier, approved_by="founder")
        else:
            success = nbmf_memory.reject(request.key, tier)
        
        return {
            "success": success,
            "action": "approved" if request.approve else "rejected",
            "key": request.key,
            "tier": tier.value
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Verification Gate Endpoints
# ============================================================================

@router.get("/verification/compliance-notes")
async def get_compliance_notes():
    """Get list of claims to avoid without proof"""
    try:
        from backend.services.verification_gate import verification_gate
        
        return {
            "success": True,
            "compliance_notes": verification_gate.get_compliance_notes()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verification/validate-claim")
async def validate_claim(claim: str):
    """Validate a single claim before use"""
    try:
        from backend.services.verification_gate import verification_gate
        
        result = verification_gate.validate_claim(claim)
        
        return {"success": True, "validation": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# WebSocket for Real-Time Project Updates
# ============================================================================

@router.websocket("/ws/project/{project_id}")
async def project_websocket(websocket: WebSocket, project_id: str):
    """WebSocket for real-time project updates"""
    await websocket.accept()
    
    try:
        from backend.services.event_bus import event_bus
        
        # Subscribe to project events
        await event_bus.connect(websocket)
        
        # Send current status
        from backend.services.autonomous_executor import autonomous_executor
        status = autonomous_executor.get_project_status(project_id)
        if status:
            await websocket.send_json({
                "type": "project.status",
                "data": status
            })
        
        # Keep connection alive and receive commands
        while True:
            try:
                data = await websocket.receive_json()
                
                # Handle frontend commands
                if data.get("action") == "pause_task":
                    result = await autonomous_executor.pause_task(data.get("task_id"))
                    await websocket.send_json({"type": "task.control", "data": result})
                
                elif data.get("action") == "resume_task":
                    result = await autonomous_executor.resume_task(data.get("task_id"))
                    await websocket.send_json({"type": "task.control", "data": result})
                
            except Exception as e:
                logger.debug(f"WebSocket receive error: {e}")
                break
                
    except WebSocketDisconnect:
        logger.info(f"Project WebSocket disconnected: {project_id}")
    finally:
        await event_bus.disconnect(websocket)
