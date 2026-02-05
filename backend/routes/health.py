"""
Health Check Endpoints - Including Council Consistency Check
"""

from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.database import SessionLocal, Department, Agent
from backend.config.council_config import COUNCIL_CONFIG
from backend.routes.monitoring import verify_monitoring_auth

router = APIRouter(prefix="/api/v1/health", tags=["health"])


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/")
async def basic_health():
    """Basic health check for load balancers - checks Ollama status."""
    ollama_ok = False
    try:
        import httpx
        async with httpx.AsyncClient(timeout=1.0) as client:
            response = await client.get("http://localhost:11434/api/tags")
            ollama_ok = (response.status_code == 200)
    except Exception:
        ollama_ok = False

    status = "healthy" if ollama_ok else "degraded"
    
    return {
        "status": status,
        "ollama_available": ollama_ok,
        "timestamp": datetime.now().isoformat(),
        "service": "daena-ai-vp"
    }


@router.get("/council")
async def council_health(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Council health endpoint - validates 8×6 structure.
    
    Returns:
    {
        "status": "healthy" | "unhealthy",
        "departments": 8,
        "agents": 48,
        "roles_per_department": 6,
        "validation": {
            "departments_valid": true,
            "agents_valid": true,
            "roles_valid": true,
            "structure_valid": true
        },
        "expected": {
            "departments": 8,
            "agents": 48,
            "roles_per_department": 6
        },
        "timestamp": "2025-01-XX..."
    }
    """
    try:
        # Get actual counts from database
        dept_count = db.query(Department).filter(Department.status == "active").count()
        agent_count = db.query(Agent).filter(Agent.is_active == True).count()
        
        # Count agents per department to verify roles
        roles_per_dept = {}
        for dept in db.query(Department).filter(Department.status == "active").all():
            # Older DBs may have `department_id` NULL and store the department slug in `Agent.department`.
            agents = db.query(Agent).filter(
                Agent.is_active == True,
                or_(
                    Agent.department_id == dept.id,
                    Agent.department == dept.slug,
                ),
            ).count()
            roles_per_dept[dept.slug] = agents
        
        # Calculate average roles per department
        avg_roles = sum(roles_per_dept.values()) / len(roles_per_dept) if roles_per_dept else 0
        roles_per_department = int(avg_roles)
        
        # Validate against canonical config
        validation = COUNCIL_CONFIG.validate_structure(
            departments=dept_count,
            agents=agent_count,
            roles_per_dept=roles_per_department
        )
        
        # Determine status
        status = "healthy" if validation["structure_valid"] else "unhealthy"
        
        # Build response
        response = {
            "status": status,
            "departments": dept_count,
            "agents": agent_count,
            "roles_per_department": roles_per_department,
            "validation": validation,
            "expected": COUNCIL_CONFIG.get_expected_counts(),
            "department_breakdown": {
                slug: count for slug, count in roles_per_dept.items()
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # If unhealthy, return 503
        if status == "unhealthy":
            raise HTTPException(
                status_code=503,
                detail=response
            )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )


@router.get("/system")
async def system_health(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """Comprehensive system health check."""
    try:
        # Council structure
        council_status = await council_health(db, _)
        
        # Check LLM availability
        llm_status = {
            "ollama_available": False,
            "cloud_providers": [],
            "active_model": None
        }
        try:
            from backend.services.local_llm_ollama import check_ollama_available
            llm_status["ollama_available"] = await check_ollama_available()
            if llm_status["ollama_available"]:
                import httpx
                async with httpx.AsyncClient(timeout=5) as client:
                    response = await client.get("http://localhost:11434/api/tags")
                    if response.status_code == 200:
                        data = response.json()
                        models = [m.get("name") for m in data.get("models", []) if isinstance(m, dict)]
                        if models:
                            llm_status["active_model"] = models[0]
        except Exception as e:
            llm_status["error"] = str(e)
        
        # Check voice system
        voice_status = {
            "available": False,
            "tts_enabled": False
        }
        try:
            from backend.services.voice_service import voice_service
            voice_status["available"] = voice_service.available
            voice_status["tts_enabled"] = voice_service.talk_active
        except Exception:
            pass
        
        # Additional system checks
        return {
            "status": "healthy",
            "council": council_status,
            "database": {
                "connected": True,
                "departments_table": True,
                "agents_table": True
            },
            "llm": llm_status,
            "voice": voice_status,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
