"""
Comprehensive system summary endpoint - Single source of truth for all system stats.
This aggregates data from database, sunflower registry, NBMF memory, and analytics.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, Any, List
from datetime import datetime
import logging

from backend.database import Department, Agent, engine
from sqlalchemy.orm import sessionmaker

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
from backend.utils.sunflower_registry import sunflower_registry
from backend.routes.monitoring import verify_monitoring_auth

router = APIRouter()
logger = logging.getLogger(__name__)


def get_db_session():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/summary")
async def get_system_summary(request: Request, _: bool = Depends(verify_monitoring_auth)):
    """
    Comprehensive system summary - single source of truth.
    Returns all system stats aggregated from database, registry, and memory.
    """
    try:
        db = SessionLocal()
        
        # Ensure database schema is fixed before querying
        try:
            from backend.scripts.fix_tenant_id_column import fix_database_columns
            fix_database_columns()
        except Exception as schema_error:
            logger.warning(f"Could not verify database schema: {schema_error}")
        
        # 1. Get counts from database (source of truth) - handle missing columns gracefully
        try:
            total_departments = db.query(Department).filter(Department.status == "active").count()
            total_agents = db.query(Agent).filter(Agent.is_active == True).count()
            active_agents = db.query(Agent).filter(
                Agent.is_active == True,
                Agent.status.in_(["active", "busy", "working"])
            ).count()
        except Exception as query_error:
            # If query fails due to missing columns, use raw SQL
            if "no such column" in str(query_error).lower():
                logger.warning(f"Database columns missing, using raw SQL: {query_error}")
                from sqlalchemy import text
                try:
                    # Check if columns exist
                    result = db.execute(text("PRAGMA table_info(agents)"))
                    columns = [row[1] for row in result]
                    
                    # Build SELECT based on available columns
                    if "project_id" not in columns or "tenant_id" not in columns:
                        # Use minimal SELECT
                        total_agents_result = db.execute(text(
                            "SELECT COUNT(*) FROM agents WHERE is_active = 1"
                        ))
                        total_agents = total_agents_result.scalar() or 0
                        
                        active_agents_result = db.execute(text(
                            "SELECT COUNT(*) FROM agents WHERE is_active = 1 AND status IN ('active', 'busy', 'working')"
                        ))
                        active_agents = active_agents_result.scalar() or 0
                    else:
                        # Retry normal query
                        total_agents = db.query(Agent).filter(Agent.is_active == True).count()
                        active_agents = db.query(Agent).filter(
                            Agent.is_active == True,
                            Agent.status.in_(["active", "busy", "working"])
                        ).count()
                    
                    total_departments = db.query(Department).filter(Department.status == "active").count()
                except Exception as raw_error:
                    logger.error(f"Error with raw SQL fallback: {raw_error}")
                    total_departments = 0
                    total_agents = 0
                    active_agents = 0
            else:
                raise
        
        # 2. Get department details from database (EXCLUDE hidden departments from frontend)
        db_departments = db.query(Department).filter(Department.status == "active").all()
        departments_list = []
        hidden_departments = ["reverse_attack_ai"]  # Hidden departments (Masoud-only)
        
        for dept in db_departments:
            # Skip hidden departments in frontend
            if dept.slug in hidden_departments:
                continue
                
            try:
                dept_agents = db.query(Agent).filter(
                    Agent.department == dept.slug,
                    Agent.is_active == True
                ).all()
            except Exception as agent_error:
                if "no such column" in str(agent_error).lower():
                    logger.warning(f"Error querying agents for {dept.slug}: {agent_error}")
                    dept_agents = []
                else:
                    raise
            
            departments_list.append({
                "id": dept.slug,
                "name": dept.name,
                "description": dept.description,
                "color": dept.color,
                "sunflower_index": dept.sunflower_index,
                "cell_id": dept.cell_id,
                "agent_count": len(dept_agents),
                "active_agents": len([a for a in dept_agents if a.status in ["active", "busy", "working"]]),
                "agents": [{
                    "id": a.id,
                    "name": a.name,
                    "role": a.role,
                    "status": a.status,
                    "cell_id": a.cell_id
                } for a in dept_agents]
            })
        
        # 3. Get NBMF memory stats
        try:
            from memory_service.metrics import snapshot as memory_snapshot
            from memory_service.stats import collect_memory_stats
            memory_metrics = memory_snapshot()
            memory_stats = collect_memory_stats()
            
            nbmf_data = {
                "l1_count": memory_stats.get("l1_count", 0),
                "l2_count": memory_stats.get("l2_count", 0),
                "l3_count": memory_stats.get("l3_count", 0),
                "total_items": memory_stats.get("total_items", 0),
                "usage_percent": round(memory_stats.get("usage_percent", 0), 1),
                "trust_score": memory_metrics.get("trust_score", 0.0),
                "divergence": memory_metrics.get("divergence", 0.0)
            }
        except Exception as e:
            logger.warning(f"Could not load NBMF stats: {e}")
            nbmf_data = {
                "l1_count": 0,
                "l2_count": 0,
                "l3_count": 0,
                "total_items": 0,
                "usage_percent": 0,
                "trust_score": 0.0,
                "divergence": 0.0
            }
        
        # 4. Get CAS hit rate
        try:
            from memory_service.metrics import snapshot as memory_snapshot
            metrics = memory_snapshot()
            cas_hits = metrics.get("llm_cas_hit", 0)
            cas_misses = metrics.get("llm_cas_miss", 0)
            near_dup_reuse = metrics.get("llm_near_dup_reuse", 0)
            total_requests = cas_hits + cas_misses + near_dup_reuse
            cas_hit_rate = (cas_hits + near_dup_reuse) / total_requests if total_requests > 0 else 0.0
        except Exception as e:
            logger.warning(f"Could not load CAS stats: {e}")
            cas_hit_rate = 0.0
        
        # 5. Get projects count (if Project model exists)
        try:
            from backend.database import Project
            total_projects = db.query(Project).count()
        except:
            total_projects = 0
        
        # 6. Get registry stats (for verification)
        registry_stats = sunflower_registry.get_stats()
        
        db.close()
        
        return {
            "status": "ok",
            "endpoint_count": len(request.app.routes),
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "system": {
                "total_departments": total_departments,
                "total_agents": total_agents,
                "active_agents": active_agents,
                "inactive_agents": total_agents - active_agents,
                "total_projects": total_projects,
                "expected_structure": {
                    "departments": 8,
                    "agents_per_department": 6,
                    "total_expected_agents": 48
                },
                "registry_verification": {
                    "registry_departments": registry_stats.get("departments", 0),
                    "registry_agents": registry_stats.get("agents", 0),
                    "matches_database": (
                        registry_stats.get("departments", 0) == total_departments and
                        registry_stats.get("agents", 0) == total_agents
                    )
                }
            },
            "departments": departments_list,
            "memory": nbmf_data,
            "cas": {
                "hit_rate": cas_hit_rate,
                "hits": cas_hits,
                "misses": cas_misses,
                "near_dup_reuse": near_dup_reuse
            }
        }
        
    except Exception as e:
        error_msg = str(e).lower()
        logger.error(f"Error getting system summary: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        
        # If error is due to missing database columns, provide helpful message
        if "no such column" in error_msg:
            return {
                "success": False,
                "error": "Database schema needs migration",
                "message": "Please run: python backend/scripts/fix_tenant_id_column.py",
                "timestamp": datetime.now().isoformat(),
                "system": {
                    "total_departments": 0,
                    "total_agents": 0,
                    "active_agents": 0,
                    "inactive_agents": 0,
                    "total_projects": 0
                },
                "departments": [],
                "memory": {
                    "l1_count": 0,
                    "l2_count": 0,
                    "l3_count": 0,
                    "total_items": 0,
                    "usage_percent": 0
                },
                "cas": {"hit_rate": 0.0, "hits": 0, "misses": 0}
            }
        raise HTTPException(status_code=500, detail=f"Error generating system summary: {str(e)}")


@router.get("/health")
async def get_system_health():
    """
    Health check endpoint for load balancers and monitoring.
    Returns basic system status without authentication.
    This endpoint is used by cloud load balancers and monitoring systems.
    """
    try:
        db = SessionLocal()
        try:
            dept_count = db.query(Department).count()
            agent_count = db.query(Agent).filter(Agent.is_active == True).count()
            
            # Verify expected structure (8 departments, 48 agents)
            expected_depts = 8
            expected_agents = 48
            structure_ok = dept_count == expected_depts and agent_count == expected_agents
            
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "departments": dept_count,
                "agents": agent_count,
                "expected_structure": {
                    "departments": expected_depts,
                    "agents": expected_agents
                },
                "structure_verified": structure_ok
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

