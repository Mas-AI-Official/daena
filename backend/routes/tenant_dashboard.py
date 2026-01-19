"""
Tenant-Scoped Dashboard Endpoints.
Provides tenant-specific views of system stats, agents, projects, and activity.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging

from backend.database import Department, Agent, Tenant, Project, get_db
from backend.middleware.tenant_context import get_tenant_id, require_tenant
from backend.utils.sunflower_registry import sunflower_registry
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/tenant", tags=["tenant-dashboard"])
logger = logging.getLogger(__name__)


def get_db_session():
    """Get database session."""
    db = next(get_db())
    try:
        yield db
    finally:
        db.close()


@router.get("/{tenant_id}/summary")
async def get_tenant_summary(
    tenant_id: str,
    request: Request,
    db: Session = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Get comprehensive tenant summary.
    
    Returns:
        Tenant-specific stats: agents, projects, departments, memory usage, activity
    """
    # Verify tenant exists
    tenant = db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant {tenant_id} not found")
    
    # Get tenant projects
    projects = db.query(Project).filter(Project.tenant_id == tenant.id).all()
    
    # Get tenant agents (filtered by projects)
    project_ids = [p.id for p in projects]
    # Note: In production, agents should be scoped to tenant/projects
    # For now, return all agents (this needs to be fixed with agent-tenant mapping)
    agents = db.query(Agent).filter(Agent.is_active == True).all()
    
    # Get departments involved
    departments = db.query(Department).filter(Department.status == "active").all()
    
    # Get memory stats (would need tenant-scoped memory queries)
    # For now, return placeholder
    memory_stats = {
        "total_items": 0,  # Would query NBMF with tenant filter
        "l1_items": 0,
        "l2_items": 0,
        "l3_items": 0,
        "total_size_bytes": 0
    }
    
    # Get activity (last 24 hours)
    # Would query ledger with tenant filter
    activity_count = 0
    
    return {
        "success": True,
        "tenant_id": tenant_id,
        "tenant_name": tenant.name,
        "company_name": tenant.company_name,
        "status": tenant.status,
        "subscription_tier": tenant.subscription_tier,
        "stats": {
            "total_projects": len(projects),
            "active_projects": len([p for p in projects if p.status == "active"]),
            "total_agents": len(agents),
            "active_agents": len([a for a in agents if a.status in ["active", "busy", "working"]]),
            "departments_involved": len(departments),
            "memory_items": memory_stats["total_items"],
            "activity_last_24h": activity_count
        },
        "projects": [
            {
                "id": p.project_id,
                "name": p.name,
                "status": p.status,
                "department_id": p.department_id
            }
            for p in projects
        ],
        "departments": [
            {
                "id": d.id,
                "slug": d.slug,
                "name": d.name,
                "agent_count": len([a for a in agents if a.department_id == d.id])
            }
            for d in departments
        ]
    }


@router.get("/{tenant_id}/activity")
async def get_tenant_activity(
    tenant_id: str,
    hours: int = 24,
    request: Request = None,
    db: Session = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Get tenant activity for the last N hours.
    
    Args:
        tenant_id: Tenant identifier
        hours: Number of hours to look back (default: 24)
    
    Returns:
        List of activities with timestamps
    """
    # Verify tenant exists
    tenant = db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant {tenant_id} not found")
    
    # Query ledger for tenant activities
    # Note: This would need to query the ledger file with tenant_id filter
    # For now, return placeholder
    activities = []
    
    # In production, would query:
    # from memory_service.ledger import AppendOnlyLedger
    # ledger = AppendOnlyLedger()
    # for record in ledger.iter_records():
    #     if record.get("meta", {}).get("tenant_id") == tenant_id:
    #         activities.append(record)
    
    return {
        "success": True,
        "tenant_id": tenant_id,
        "hours": hours,
        "activity_count": len(activities),
        "activities": activities
    }


@router.get("/{tenant_id}/memory")
async def get_tenant_memory_stats(
    tenant_id: str,
    request: Request = None,
    db: Session = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Get tenant-specific memory statistics.
    
    Returns:
        Memory stats scoped to tenant
    """
    # Verify tenant exists
    tenant = db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant {tenant_id} not found")
    
    # In production, would query NBMF with tenant filter
    # For now, return placeholder
    return {
        "success": True,
        "tenant_id": tenant_id,
        "memory": {
            "total_items": 0,
            "l1_items": 0,
            "l2_items": 0,
            "l3_items": 0,
            "total_size_bytes": 0,
            "compression_ratio": 0.0,
            "cas_hit_rate": 0.0
        }
    }


@router.get("/{tenant_id}/council-decisions")
async def get_tenant_council_decisions(
    tenant_id: str,
    limit: int = 10,
    request: Request = None,
    db: Session = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Get tenant-specific council decisions.
    
    Returns:
        List of council conclusions scoped to tenant
    """
    # Verify tenant exists
    tenant = db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant {tenant_id} not found")
    
    # Query council conclusions with tenant filter
    from backend.models.database import CouncilConclusion
    conclusions = db.query(CouncilConclusion).filter(
        CouncilConclusion.tenant_id == tenant_id
    ).order_by(CouncilConclusion.created_at.desc()).limit(limit).all()
    
    return {
        "success": True,
        "tenant_id": tenant_id,
        "count": len(conclusions),
        "decisions": [
            {
                "conclusion_id": c.conclusion_id,
                "title": c.title,
                "summary": c.summary,
                "department_id": c.department_id,
                "confidence_score": c.confidence_score,
                "status": c.status,
                "created_at": c.created_at.isoformat() if c.created_at else None
            }
            for c in conclusions
        ]
    }

