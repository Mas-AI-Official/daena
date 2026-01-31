from datetime import datetime
from typing import Any, Dict

import logging
import psutil
from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from pathlib import Path

from memory_service.audit import ledger_audit
from memory_service.insight_miner import InsightMiner
from memory_service.metrics import snapshot as memory_snapshot
from memory_service.stats import collect_memory_stats
from memory_service.policy_summary import load_policy_summary

router = APIRouter()
security = HTTPBearer(auto_error=False)

# Auth helper for monitoring endpoints (JWT + API Key support)
async def verify_monitoring_auth(
    authorization: HTTPAuthorizationCredentials = Depends(security),
    x_api_key: str = Header(None)
) -> bool:
    """
    Verify authentication for monitoring endpoints.
    
    SECURITY: Supports both JWT tokens and API keys.
    In production, requires valid JWT token or API key.
    In development, allows requests without auth for testing convenience.
    """
    import os
    
    # NO-AUTH MODE: bypass all auth checks (check at the very start)
    try:
        from backend.config.settings import get_settings
        settings = get_settings()
        if getattr(settings, "disable_auth", False) or os.getenv("DISABLE_AUTH", "0").lower() in {"1", "true", "yes", "on"}:
            return True
    except Exception:
        pass
    
    # Try JWT authentication first
    if authorization:
        try:
            from backend.services.jwt_service import get_jwt_service
            jwt_service = get_jwt_service()
            token = authorization.credentials
            
            # Verify JWT token
            payload = jwt_service.verify_token(token, token_type="access")
            if payload:
                # Check if user has monitoring permission
                user_role = payload.get("role", "user")
                if user_role in ["admin", "founder", "monitor"]:
                    return True
                else:
                    raise HTTPException(
                        status_code=403,
                        detail="Forbidden: Insufficient permissions for monitoring endpoints"
                    )
        except ImportError:
            # JWT service not available, fall back to API key
            pass
        except Exception as e:
            # JWT verification failed, try API key
            pass
    
    # Get valid API keys from settings or environment
    try:
        from backend.config.settings import get_settings
        settings = get_settings()
        valid_keys = [
            getattr(settings, "secret_key", None),
            getattr(settings, "monitoring_api_key", None),
            getattr(settings, "test_api_key", None),
        ]
        # Filter out None values
        valid_keys = [k for k in valid_keys if k]
    except ImportError:
        valid_keys = []
    
    # Also check environment variable for monitoring API key
    env_key = os.getenv("DAENA_MONITORING_API_KEY")
    if env_key:
        valid_keys.append(env_key)
    
    # Development behavior: allow requests without auth only when DISABLE_AUTH=1
    try:
        from backend.config.settings import get_settings
        settings = get_settings()
        # Check settings.disable_auth first (which handles env var parsing)
        if getattr(settings, "disable_auth", False):
            return True
            
        # Also check raw env var as fallback
        if os.getenv("DISABLE_AUTH", "0").lower() in {"1", "true", "yes", "on"}:
            return True
            
        # If we are in development mode, we might want to be more lenient
        # But for security tests to pass, we must respect the auth requirement unless explicitly disabled
        env = os.getenv("ENVIRONMENT", "development")
        if env == "development" and (getattr(settings, "disable_auth", False) or os.getenv("DISABLE_AUTH", "0").lower() in {"1", "true", "yes", "on"}):
            return True
    except Exception:
        pass
    else:
        # In production, require authentication
        if not x_api_key and not authorization:
            raise HTTPException(
                status_code=401,
                detail="Unauthorized: Authentication required for monitoring endpoints. Provide X-API-Key header or Bearer JWT token."
            )
    
    # Check API key header
    if x_api_key:
        if x_api_key in valid_keys:
            return True
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Invalid API key"
        )
    
    # Should not reach here, but fail secure
    raise HTTPException(
        status_code=401,
        detail="Unauthorized: Authentication required for monitoring endpoints"
    )

insight_miner = InsightMiner()

logger = logging.getLogger(__name__)


@router.get("/metrics/summary")
async def get_metrics_summary(
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Standardized metrics summary endpoint - single source of truth for all dashboards.
    
    Returns authoritative counts for:
    - Agents (total/active)
    - Projects
    - Tasks
    - Council rounds
    - Errors
    
    All dashboards should read from this endpoint.
    """
    try:
        from backend.database import SessionLocal, Department, Agent
        from backend.config.council_config import COUNCIL_CONFIG
        
        db = SessionLocal()
        try:
            # Agent counts
            total_agents = db.query(Agent).count()
            active_agents = db.query(Agent).filter(Agent.is_active == True).count()
            
            # Department counts
            total_departments = db.query(Department).count()
            active_departments = db.query(Department).filter(Department.status == "active").count()
            
            # Validate against canonical config
            expected = COUNCIL_CONFIG.get_expected_counts()
            structure_valid = (
                total_departments == expected["departments"] and
                total_agents == expected["agents"]
            )
            
            # Council rounds (from scheduler if available)
            council_rounds = 0
            try:
                from backend.services.council_scheduler import council_scheduler
                council_rounds = len(council_scheduler.round_history) if hasattr(council_scheduler, 'round_history') else 0
            except:
                pass
            
            # Tasks (from analytics if available)
            tasks_completed = 0
            tasks_failed = 0
            try:
                from backend.services.analytics_service import analytics_service
                # Aggregate from all agents
                for agent_id in db.query(Agent).with_entities(Agent.id).all():
                    try:
                        efficiency = analytics_service.calculate_efficiency_metrics(agent_id[0])
                        tasks_completed += efficiency.total_interactions
                        tasks_failed += efficiency.total_interactions - (efficiency.total_interactions * efficiency.success_rate)
                    except:
                        pass
            except:
                pass
            
            # Errors (from ledger if available)
            errors = 0
            try:
                from memory_service.ledger import ledger_service
                # Count error events in ledger
                if hasattr(ledger_service, 'get_recent_events'):
                    recent_events = ledger_service.get_recent_events(limit=1000)
                    errors = sum(1 for e in recent_events if e.get('action', '').endswith('_error') or e.get('error'))
            except:
                pass
            
            return {
                "success": True,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "agents": {
                    "total": total_agents,
                    "active": active_agents,
                    "expected": expected["agents"],
                    "valid": total_agents == expected["agents"]
                },
                "departments": {
                    "total": total_departments,
                    "active": active_departments,
                    "expected": expected["departments"],
                    "valid": total_departments == expected["departments"]
                },
                "structure": {
                    "valid": structure_valid,
                    "expected": expected,
                    "actual": {
                        "departments": total_departments,
                        "agents": total_agents,
                        "roles_per_department": total_agents // total_departments if total_departments > 0 else 0
                    }
                },
                "council": {
                    "rounds": council_rounds,
                    "last_round": council_scheduler.round_history[-1] if hasattr(council_scheduler, 'round_history') and council_scheduler.round_history else None
                },
                "tasks": {
                    "completed": tasks_completed,
                    "failed": tasks_failed,
                    "total": tasks_completed + tasks_failed
                },
                "errors": errors,
                "heartbeat": {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "status": "live"  # Will be updated by heartbeat mechanism
                }
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error getting metrics summary: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting metrics summary: {str(e)}")


def get_system_metrics() -> Dict[str, Any]:
    """Get current system metrics in the format expected by frontend."""
    try:
        return {
            "cpu_usage": round(psutil.cpu_percent(interval=1), 1),
            "memory_usage": round(psutil.virtual_memory().percent, 1),
            "disk_usage": round(psutil.disk_usage('/').percent, 1),
            "gpu_usage": 0,  # Placeholder for GPU monitoring
            "network_io": {
                "bytes_sent": psutil.net_io_counters().bytes_sent,
                "bytes_recv": psutil.net_io_counters().bytes_recv
            },
            "active_connections": len(psutil.net_connections()),
            "uptime": round((datetime.now() - datetime.fromtimestamp(psutil.boot_time())).total_seconds(), 1)
        }
    except Exception as e:
        return {
            "cpu_usage": 0,
            "memory_usage": 0,
            "disk_usage": 0,
            "gpu_usage": 0,
            "network_io": {"bytes_sent": 0, "bytes_recv": 0},
            "active_connections": 0,
            "uptime": 0
        }

def get_hive_data() -> Dict[str, Any]:
    """Get hive data in the format expected by frontend."""
    try:
        # Mock hive data for now - replace with actual hive logic
        return {
            "core": {
                "status": "active",
                "health": 95,
                "connections": 12
            },
            "departments": [
                {
                    "department_id": "ai",
                    "name": "AI Department",
                    "agent_count": 5,
                    "active_agents": 3,
                    "total_tasks": 150,
                    "success_rate": 0.92,
                    "average_response_time": 2.3
                },
                {
                    "department_id": "data",
                    "name": "Data Department", 
                    "agent_count": 3,
                    "active_agents": 2,
                    "total_tasks": 89,
                    "success_rate": 0.88,
                    "average_response_time": 1.8
                }
            ],
            "connections": [
                {
                    "from": "ai",
                    "to": "data",
                    "strength": 0.8,
                    "type": "data_flow"
                }
            ],
            "metrics": {
                "total_agents": 8,
                "active_agents": 5,
                "total_tasks": 239,
                "success_rate": 0.90
            }
        }
    except Exception as e:
        return {
            "core": {"status": "error", "health": 0, "connections": 0},
            "departments": [],
            "connections": [],
            "metrics": {"total_agents": 0, "active_agents": 0, "total_tasks": 0, "success_rate": 0}
        }

def get_agent_metrics() -> Dict[str, Any]:
    """Get agent metrics in the format expected by frontend."""
    try:
        # Get real agent metrics from sunflower registry
        from backend.utils.sunflower_registry import sunflower_registry
        
        agent_metrics = {}
        for agent_id, agent_data in sunflower_registry.agents.items():
            agent_metrics[agent_id] = {
                "agent_id": agent_id,
                "name": agent_data.get("name", agent_id),
                "department": agent_data.get("department_id", "unknown"),
                "role": agent_data.get("role", "specialist"),
                "tasks_completed": 0,  # Will be updated from analytics service if available
                "tasks_failed": 0,  # Will be updated from analytics service if available
                "average_response_time": 0.0,  # Will be updated from analytics service if available
                "last_activity": datetime.now().isoformat(),
                "status": "active"
            }
        
        # Get real metrics from analytics service if available
        try:
            from backend.services.analytics_service import analytics_service
            for agent_id in sunflower_registry.agents.keys():
                try:
                    efficiency = analytics_service.calculate_efficiency_metrics(agent_id)
                    if agent_id in agent_metrics:
                        # Update with real metrics from analytics service
                        agent_metrics[agent_id]["tasks_completed"] = efficiency.total_interactions
                        # Calculate tasks_failed from success rate
                        tasks_failed = int(efficiency.total_interactions * (1.0 - efficiency.success_rate))
                        agent_metrics[agent_id]["tasks_failed"] = tasks_failed
                        # Convert response time from ms to seconds
                        agent_metrics[agent_id]["average_response_time"] = efficiency.avg_response_time_ms / 1000.0 if efficiency.avg_response_time_ms else 0.0
                        agent_metrics[agent_id]["status"] = "active" if efficiency.total_interactions > 0 else "idle"
                except Exception as e:
                    # If analytics service fails for an agent, keep default values
                    logger.debug(f"Could not get analytics for agent {agent_id}: {e}")
                    pass
        except ImportError:
            # Analytics service not available - use default values
            logger.debug("Analytics service not available - using default metrics")
            pass
        except Exception as e:
            logger.warning(f"Error getting analytics metrics: {e}")
            pass
        
        return agent_metrics
    except Exception as e:
        return {}

@router.get("/metrics")
async def get_system_metrics_endpoint(_: bool = Depends(verify_monitoring_auth)):
    """Get system metrics endpoint that frontend expects."""
    try:
        data = get_system_metrics()
        data["memory_system"] = memory_snapshot()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/hive/data")
async def get_hive_data_endpoint():
    """Get hive data endpoint that frontend expects."""
    try:
        return get_hive_data()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/agent-metrics")
async def get_agent_metrics_endpoint(_: bool = Depends(verify_monitoring_auth)):
    """Get agent metrics endpoint that frontend expects."""
    try:
        return get_agent_metrics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent-instrumentation")
async def get_agent_instrumentation(_: bool = Depends(verify_monitoring_auth)):
    """Get agent boot and heartbeat instrumentation metrics."""
    try:
        # Try to get from agent manager
        import sys
        import os
        project_root = os.path.join(os.path.dirname(__file__), '..', '..')
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        from Core.agents.agent_manager import agent_manager
        
        instrumentation_data = {}
        
        # Get all agents and their instrumentation metrics
        agents = agent_manager.get_agents()
        for agent_id, agent in agents.items():
            if hasattr(agent, 'get_boot_metrics') and hasattr(agent, 'get_heartbeat_metrics'):
                instrumentation_data[agent_id] = {
                    "boot_metrics": agent.get_boot_metrics(),
                    "heartbeat_metrics": agent.get_heartbeat_metrics(),
                    "uptime_sec": agent.get_uptime(),
                    "name": agent.name,
                    "department": agent.department
                }
        
        # Calculate aggregate metrics
        if instrumentation_data:
            boot_durations = [m["boot_metrics"]["boot_duration_sec"] for m in instrumentation_data.values()]
            uptimes = [m["uptime_sec"] for m in instrumentation_data.values()]
            heartbeat_counts = [m["heartbeat_metrics"]["heartbeat_count"] for m in instrumentation_data.values()]
            
            aggregate = {
                "total_agents": len(instrumentation_data),
                "avg_boot_duration_sec": sum(boot_durations) / len(boot_durations) if boot_durations else 0,
                "min_boot_duration_sec": min(boot_durations) if boot_durations else 0,
                "max_boot_duration_sec": max(boot_durations) if boot_durations else 0,
                "avg_uptime_sec": sum(uptimes) / len(uptimes) if uptimes else 0,
                "total_heartbeats": sum(heartbeat_counts) if heartbeat_counts else 0
            }
        else:
            aggregate = {
                "total_agents": 0,
                "avg_boot_duration_sec": 0,
                "min_boot_duration_sec": 0,
                "max_boot_duration_sec": 0,
                "avg_uptime_sec": 0,
                "total_heartbeats": 0
            }
        
        return {
            "success": True,
            "agents": instrumentation_data,
            "aggregate": aggregate,
            "timestamp": datetime.now().isoformat()
        }
    except ImportError as e:
        logger.warning(f"Agent manager not available: {e}")
        return {
            "success": False,
            "error": "Agent manager not available",
            "agents": {},
            "aggregate": {}
        }
    except Exception as e:
        logger.error(f"Error getting agent instrumentation: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting agent instrumentation: {str(e)}") 


@router.get("/memory")
async def get_memory_metrics_endpoint(_: bool = Depends(verify_monitoring_auth)):
    """Expose NBMF memory metrics snapshot for governance tools."""
    snapshot = memory_snapshot()
    snapshot["storage_stats"] = collect_memory_stats()
    try:
        snapshot["insight_sample"] = insight_miner.to_summary()
    except Exception as e:
        logger.error(f"Error getting insight sample: {e}")
        snapshot["insight_sample"] = {"count": 0, "items": []}
    snapshot["ledger"] = ledger_audit(recent=5)
    return snapshot


@router.get("/memory/stats")
async def get_memory_stats_endpoint(_: bool = Depends(verify_monitoring_auth)):
    """Detailed storage statistics across NBMF tiers."""
    return collect_memory_stats()


@router.get("/memory/insights")
async def get_memory_insights_endpoint(limit: int = 20, _: bool = Depends(verify_monitoring_auth)):
    """Return the top NBMF insight records for dashboards."""
    local_miner = InsightMiner(top_n=limit)
    return local_miner.to_summary()


@router.get("/memory/audit")
async def get_memory_audit_endpoint(recent: int = 10, _: bool = Depends(verify_monitoring_auth)):
    """Return ledger audit summary for governance dashboards."""
    return ledger_audit(recent=recent)


@router.get("/policy")
async def get_policy_summary_endpoint(cls: str | None = None, _: bool = Depends(verify_monitoring_auth)):
    """Return ABAC + fidelity summary for governance tools."""
    classes = [cls] if cls else None
    return load_policy_summary(classes)


@router.get("/memory/cas")
async def get_cas_diagnostics_endpoint(_: bool = Depends(verify_monitoring_auth)):
    """Return CAS efficiency diagnostics for LLM exchange caching."""
    from memory_service.caching_cas import CAS
    from memory_service.metrics import snapshot

    cas_root = Path(".llm_cas")
    metrics = snapshot()

    cas_hits = metrics.get("llm_cas_hit", 0)
    cas_misses = metrics.get("llm_cas_miss", 0)
    near_dup_reuse = metrics.get("llm_near_dup_reuse", 0)
    total_requests = cas_hits + cas_misses + near_dup_reuse

    cas_info: Dict[str, Any] = {
        "metrics": {
            "cas_hits": cas_hits,
            "cas_misses": cas_misses,
            "near_dup_reuse": near_dup_reuse,
            "total_requests": total_requests,
            "hit_rate": round((cas_hits + near_dup_reuse) / total_requests if total_requests else 0.0, 4),
            "exact_match_rate": round(cas_hits / total_requests if total_requests else 0.0, 4),
            "near_dup_rate": round(near_dup_reuse / total_requests if total_requests else 0.0, 4),
        },
    }

    if cas_root.exists():
        cas_files = list(cas_root.glob("*"))
        total_size = sum(f.stat().st_size for f in cas_files if f.is_file())
        cas_info["store"] = {
            "total_entries": len(cas_files),
            "total_size_bytes": total_size,
            "avg_size_bytes": round(total_size / len(cas_files) if cas_files else 0, 2),
            "path": str(cas_root),
        }
    else:
        cas_info["store"] = {"error": "CAS root does not exist", "path": str(cas_root)}

    return cas_info


def _prometheus_safe(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "_:" else "_" for ch in name)


def _render_prometheus(metrics: Dict[str, Any]) -> str:
    lines = ["# HELP daena_memory_metric NBMF memory subsystem metrics.", "# TYPE daena_memory_metric gauge"]
    for key, value in metrics.items():
        metric_key = _prometheus_safe(key.lower())
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        lines.append(f'daena_memory_metric{{name="{metric_key}"}} {numeric}')
    return "\n".join(lines) + "\n"


@router.get("/memory/prometheus", response_class=PlainTextResponse)
async def get_memory_metrics_prometheus(_: bool = Depends(verify_monitoring_auth)) -> str:
    """
    Expose NBMF + DNA metrics in Prometheus text format.
    
    Includes:
    - NBMF read/write latencies (p50, p95)
    - DNA lineage counters
    - Immune event counters
    - DNA health metrics
    """
    lines = []
    
    # NBMF metrics
    nbmf_metrics = memory_snapshot()
    lines.append("# HELP daena_nbmf_metric NBMF memory subsystem metrics.")
    lines.append("# TYPE daena_nbmf_metric gauge")
    for key, value in nbmf_metrics.items():
        metric_key = _prometheus_safe(key.lower())
        try:
            numeric = float(value)
            lines.append(f'daena_nbmf_metric{{name="{metric_key}"}} {numeric}')
        except (TypeError, ValueError):
            continue
    
    # DNA metrics (if Prometheus client available)
    try:
        from prometheus_client import generate_latest, REGISTRY
        from memory_service.dna_metrics import PROMETHEUS_AVAILABLE
        
        if PROMETHEUS_AVAILABLE:
            lines.append("\n# DNA Metrics")
            # Generate Prometheus format from registered metrics
            dna_metrics_text = generate_latest(REGISTRY).decode('utf-8')
            # Filter to only DNA metrics
            for line in dna_metrics_text.split('\n'):
                if 'dna_' in line or line.startswith('#') and 'dna' in line.lower():
                    lines.append(line)
    except ImportError:
        # Prometheus not available, skip DNA metrics
        pass
    
    return "\n".join(lines) + "\n"


@router.get("/memory/histograms")
async def get_memory_histograms(_: bool = Depends(verify_monitoring_auth)):
    """Get metrics with histogram buckets for SLO monitoring."""
    try:
        from memory_service.metrics_enhanced import snapshot_with_histograms
        return snapshot_with_histograms()
    except ImportError:
        # Fallback to regular snapshot
        return memory_snapshot()


@router.get("/memory/cost-tracking")
async def get_cost_tracking(_: bool = Depends(verify_monitoring_auth)):
    """Get cost tracking metrics including savings from CAS reuse."""
    metrics = memory_snapshot()
    cost_data = {
        "total_cost_usd": metrics.get("total_cost_usd", 0.0),
        "estimated_savings_usd": metrics.get("estimated_cost_savings_usd", 0.0),
        "cost_savings_percentage": metrics.get("cost_savings_percentage", 0.0),
        "costs_by_category": metrics.get("costs", {}),
        "cas_efficiency": {
            "hit_rate": metrics.get("llm_cas_hit_rate", 0.0),
            "exact_match_rate": metrics.get("llm_exact_match_rate", 0.0),
            "near_dup_rate": metrics.get("llm_near_dup_rate", 0.0),
        },
        "total_requests": metrics.get("llm_cas_hit", 0) + metrics.get("llm_cas_miss", 0) + metrics.get("llm_near_dup_reuse", 0),
        "cas_hits": metrics.get("llm_cas_hit", 0),
        "cas_misses": metrics.get("llm_cas_miss", 0),
        "near_dup_reuse": metrics.get("llm_near_dup_reuse", 0),
    }
    return cost_data


@router.get("/memory/slo-burn-rate")
async def get_slo_burn_rate(
    metric: str = "nbmf_read",
    threshold_ms: float = 25.0,
    window_minutes: int = 5,
    _: bool = Depends(verify_monitoring_auth)
):
    """Get SLO burn rate for a metric."""
    try:
        from memory_service.metrics_enhanced import get_slo_burn_rate
        return get_slo_burn_rate(metric, threshold_ms, window_minutes)
    except ImportError:
        raise HTTPException(status_code=501, detail="SLO burn rate calculation not available")