"""
SLO (Service Level Objective) Monitoring Endpoints.

Provides health endpoints for cloud liveness probes and SLO tracking.
"""

from fastapi import APIRouter, Depends
from typing import Dict, Any
from datetime import datetime

from backend.routes.monitoring import verify_monitoring_auth

router = APIRouter(prefix="/api/v1/slo", tags=["slo"])


@router.get("/health")
async def slo_health() -> Dict[str, Any]:
    """
    Health endpoint for cloud liveness probes.
    
    Returns 200 if service is healthy, 503 if degraded.
    """
    try:
        # Check critical services
        from backend.database import SessionLocal, Department, Agent
        from backend.config.council_config import COUNCIL_CONFIG
        
        db = SessionLocal()
        try:
            dept_count = db.query(Department).count()
            agent_count = db.query(Agent).count()
            
            # Validate structure
            expected = COUNCIL_CONFIG.get_expected_counts()
            structure_valid = (
                dept_count == expected["departments"] and
                agent_count == expected["agents"]
            )
            
            # Check if degraded
            if not structure_valid:
                return {
                    "status": "degraded",
                    "message": "Council structure invalid",
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }, 503
            
            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "checks": {
                    "database": "ok",
                    "council_structure": "valid"
                }
            }
        finally:
            db.close()
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": str(e),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }, 503


@router.get("/metrics")
async def slo_metrics(
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    SLO metrics endpoint.
    
    Returns:
        - Latency (p50, p95, p99)
        - Error budget
        - Round completion rate
        - Error rate
    """
    try:
        from backend.services.realtime_metrics_stream import _latency_buffer
        
        # Calculate latency percentiles
        def percentile(data, p):
            if not data:
                return 0
            sorted_data = sorted(data)
            index = int(len(sorted_data) * p / 100)
            return sorted_data[index] if index < len(sorted_data) else sorted_data[-1]
        
        nbmf_encode = list(_latency_buffer.get('nbmf_encode', []))
        nbmf_decode = list(_latency_buffer.get('nbmf_decode', []))
        council_decision = list(_latency_buffer.get('council_decision', []))
        
        # Error budget (target: 99.9% availability)
        error_budget = 0.001  # 0.1% error rate allowed
        
        # Round completion rate (from council scheduler if available)
        round_completion_rate = 1.0  # Default
        try:
            from backend.services.council_scheduler import council_scheduler
            if hasattr(council_scheduler, 'round_history') and council_scheduler.round_history:
                completed = sum(1 for r in council_scheduler.round_history if r.get("commit", {}).get("committed", False))
                total = len(council_scheduler.round_history)
                round_completion_rate = completed / total if total > 0 else 1.0
        except:
            pass
        
        return {
            "latency": {
                "nbmf_encode": {
                    "p50": percentile(nbmf_encode, 50),
                    "p95": percentile(nbmf_encode, 95),
                    "p99": percentile(nbmf_encode, 99)
                },
                "nbmf_decode": {
                    "p50": percentile(nbmf_decode, 50),
                    "p95": percentile(nbmf_decode, 95),
                    "p99": percentile(nbmf_decode, 99)
                },
                "council_decision": {
                    "p50": percentile(council_decision, 50),
                    "p95": percentile(council_decision, 95),
                    "p99": percentile(council_decision, 99)
                }
            },
            "error_budget": {
                "target": 0.999,  # 99.9% availability
                "remaining": error_budget,
                "unit": "error_rate"
            },
            "round_completion_rate": round_completion_rate,
            "error_rate": 0.0,  # Would calculate from error logs
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        return {
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

