"""
Registry Summary Endpoint
Returns department/agent counts by role - single source of truth for 8×6 structure.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any
import logging

from backend.database import SessionLocal, Department, Agent
from backend.config.council_config import COUNCIL_CONFIG
from backend.routes.monitoring import verify_monitoring_auth

router = APIRouter(prefix="/api/v1/registry", tags=["registry"])
logger = logging.getLogger(__name__)


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/summary")
async def get_registry_summary(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Get registry summary with department and agent counts by role.
    
    Returns:
    {
        "departments": 8,
        "agents": 48,
        "roles_per_department": 6,
        "departments_by_role": {
            "engineering": 6,
            "product": 6,
            ...
        },
        "agents_by_role": {
            "advisor_a": 8,
            "advisor_b": 8,
            "scout_internal": 8,
            "scout_external": 8,
            "synth": 8,
            "executor": 8
        },
        "department_details": [
            {
                "slug": "engineering",
                "name": "Engineering",
                "agent_count": 6,
                "roles": {
                    "advisor_a": 1,
                    "advisor_b": 1,
                    ...
                }
            },
            ...
        ]
    }
    """
    try:
        # Get departments
        departments = db.query(Department).filter(Department.status == "active").all()
        dept_count = len(departments)
        
        # Get all agents
        agents = db.query(Agent).filter(Agent.is_active == True).all()
        agent_count = len(agents)
        
        # Count agents by role across all departments
        agents_by_role = {}
        for role in COUNCIL_CONFIG.AGENT_ROLES:
            agents_by_role[role] = db.query(Agent).filter(
                Agent.role == role,
                Agent.is_active == True
            ).count()
        
        # Build department details with role breakdown
        department_details = []
        departments_by_role = {}
        
        for dept in departments:
            dept_agents = db.query(Agent).filter(
                Agent.department_id == dept.id,
                Agent.is_active == True
            ).all()
            
            # Count roles within this department
            roles_in_dept = {}
            for role in COUNCIL_CONFIG.AGENT_ROLES:
                count = len([a for a in dept_agents if a.role == role])
                roles_in_dept[role] = count
            
            departments_by_role[dept.slug] = len(dept_agents)
            
            department_details.append({
                "slug": dept.slug,
                "name": dept.name,
                "agent_count": len(dept_agents),
                "roles": roles_in_dept
            })
        
        # Calculate average roles per department
        avg_roles = sum(departments_by_role.values()) / len(departments_by_role) if departments_by_role else 0
        
        return {
            "success": True,
            "departments": dept_count,
            "agents": agent_count,
            "roles_per_department": int(avg_roles),
            "departments_by_role": departments_by_role,
            "agents_by_role": agents_by_role,
            "department_details": department_details,
            "expected": COUNCIL_CONFIG.get_expected_counts(),
            "validation": COUNCIL_CONFIG.validate_structure(
                departments=dept_count,
                agents=agent_count,
                roles_per_dept=int(avg_roles)
            )
        }
        
    except Exception as e:
        logger.error(f"Error getting registry summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get registry summary: {str(e)}")

