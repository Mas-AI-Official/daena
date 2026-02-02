"""
Projects API Routes
Manage project lifecycle
Now using SQLite persistence instead of in-memory storage
"""
from fastapi import APIRouter, HTTPException, Depends, Body
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel
from backend.database import get_db, Project as ProjectDB, Tenant
from backend.domain.project import Project, INITIAL_PROJECTS
from backend.core.websocket_manager import websocket_manager
from datetime import datetime
import logging
import json

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])
logger = logging.getLogger(__name__)

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    status: str = "active"
    department_id: Optional[int] = None

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    department_id: Optional[int] = None

def _project_db_to_domain(project_db: ProjectDB) -> Dict[str, Any]:
    """Convert DB Project to domain Project model"""
    # Get default tenant (or create one)
    tenant = project_db.tenant if project_db.tenant else None
    
    return {
        "id": project_db.project_id,
        "name": project_db.name,
        "description": project_db.description or "",
        "status": project_db.status,
        "progress": 0,  # TODO: Calculate from tasks
        "start_date": project_db.created_at.isoformat() if project_db.created_at else datetime.utcnow().isoformat(),
        "deadline": None,  # TODO: Add deadline field to Project table
        "finance": {
            "budget": 0.0,
            "spent": 0.0,
            "currency": "USD"
        },
        "team": [],  # TODO: Add project members table
        "tags": []  # TODO: Add tags field to Project table
    }

def _ensure_default_tenant(db: Session) -> Tenant:
    """Ensure default tenant exists"""
    tenant = db.query(Tenant).filter(Tenant.tenant_id == "default").first()
    if not tenant:
        tenant = Tenant(
            tenant_id="default",
            name="Default Organization",
            company_name="MAS-AI Company"
        )
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
    return tenant

def _ensure_initial_projects(db: Session):
    """Ensure initial projects exist in DB"""
    tenant = _ensure_default_tenant(db)
    
    for project in INITIAL_PROJECTS:
        # Check if project exists
        existing = db.query(ProjectDB).filter(
            ProjectDB.project_id == project.id
        ).first()
        
        if not existing:
            # Create project
            project_db = ProjectDB(
                project_id=project.id,
                tenant_id=tenant.id,
                name=project.name,
                description=project.description,
                status=project.status
            )
            db.add(project_db)
    
    db.commit()

@router.get("/")
async def list_projects(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """List all projects from database"""
    _ensure_initial_projects(db)
    
    projects = db.query(ProjectDB).all()
    projects_list = [_project_db_to_domain(p) for p in projects]
    
    return {"projects": projects_list}

@router.get("/{project_id}")
async def get_project(project_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get specific project details from database"""
    _ensure_initial_projects(db)
    
    project = db.query(ProjectDB).filter(ProjectDB.project_id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return _project_db_to_domain(project)

@router.post("/")
async def create_project(project: ProjectCreate, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Create a new project"""
    tenant = _ensure_default_tenant(db)
    
    # Generate project_id
    project_id = f"proj_{int(datetime.utcnow().timestamp())}"
    
    project_db = ProjectDB(
        project_id=project_id,
        tenant_id=tenant.id,
        name=project.name,
        description=project.description,
        status=project.status or "active",
        department_id=project.department_id
    )
    
    db.add(project_db)
    db.commit()
    db.refresh(project_db)
    
    # Emit WebSocket event
    await websocket_manager.publish_event(
        event_type="project.created",
        entity_type="project",
        entity_id=project_id,
        payload={"project": _project_db_to_domain(project_db)}
    )
    
    return {"success": True, "project": _project_db_to_domain(project_db)}

@router.put("/{project_id}")
async def update_project(
    project_id: str,
    project_update: ProjectUpdate,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Update project details"""
    project = db.query(ProjectDB).filter(ProjectDB.project_id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project_update.name:
        project.name = project_update.name
    if project_update.description is not None:
        project.description = project_update.description
    if project_update.status is not None:
        project.status = project_update.status
    if project_update.department_id is not None:
        project.department_id = project_update.department_id
    
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(project)
    
    # Emit WebSocket event
    await websocket_manager.publish_event(
        event_type="project.updated",
        entity_type="project",
        entity_id=project_id,
        payload={"project": _project_db_to_domain(project)}
    )
    
    return {"success": True, "project": _project_db_to_domain(project)}

@router.delete("/{project_id}")
async def delete_project(project_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Delete a project"""
    project = db.query(ProjectDB).filter(ProjectDB.project_id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    db.delete(project)
    db.commit()
    
    # Emit WebSocket event
    await websocket_manager.publish_event(
        event_type="project.deleted",
        entity_type="project",
        entity_id=project_id,
        payload={"project_id": project_id}
    )
    
    return {"success": True, "message": "Project deleted"}

@router.post("/{project_id}/pause")
async def pause_project(project_id: str, db: Session = Depends(get_db)):
    """Pause a project"""
    return await _update_project_status(project_id, "paused", db)

@router.post("/{project_id}/resume")
async def resume_project(project_id: str, db: Session = Depends(get_db)):
    """Resume a paused project"""
    return await _update_project_status(project_id, "active", db)

@router.post("/{project_id}/stop")
async def stop_project(project_id: str, db: Session = Depends(get_db)):
    """Stop/Cancel a project"""
    return await _update_project_status(project_id, "stopped", db)

async def _update_project_status(project_id: str, status: str, db: Session):
    project = db.query(ProjectDB).filter(ProjectDB.project_id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project.status = status
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(project)
    
    # Emit WebSocket event
    await websocket_manager.publish_event(
        event_type="project.updated",
        entity_type="project",
        entity_id=project_id,
        payload={"project": _project_db_to_domain(project)}
    )
    
    return {"success": True, "project": _project_db_to_domain(project)}