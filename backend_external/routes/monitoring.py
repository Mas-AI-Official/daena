from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

import os
import psutil
from fastapi import APIRouter, HTTPException, Security
from fastapi.responses import PlainTextResponse
from fastapi.security import APIKeyHeader

from memory_service.metrics import snapshot as memory_snapshot

router = APIRouter()
_api_key_header = APIKeyHeader(name="X-DAENA-API-KEY", auto_error=False)


def _require_api_key(api_key: str | None) -> None:
    expected = os.getenv("DAENA_MONITORING_API_KEY")
    if expected and api_key != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


def get_system_metrics() -> Dict[str, Any]:
    """Get current system metrics in the format expected by frontend."""
    try:
        return {
            "cpu_usage": psutil.cpu_percent(interval=1),
            "memory_usage": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage("/").percent,
            "gpu_usage": 0,
            "network_io": {
                "bytes_sent": psutil.net_io_counters().bytes_sent,
                "bytes_recv": psutil.net_io_counters().bytes_recv,
            },
            "active_connections": len(psutil.net_connections()),
            "uptime": (datetime.now() - datetime.fromtimestamp(psutil.boot_time())).total_seconds(),
        }
    except Exception:
        return {
            "cpu_usage": 0,
            "memory_usage": 0,
            "disk_usage": 0,
            "gpu_usage": 0,
            "network_io": {"bytes_sent": 0, "bytes_recv": 0},
            "active_connections": 0,
            "uptime": 0,
        }


def get_hive_data() -> Dict[str, Any]:
    """Get hive data in the format expected by frontend."""
    try:
        return {
            "core": {"status": "active", "health": 95, "connections": 12},
            "departments": [
                {
                    "department_id": "ai",
                    "name": "AI Department",
                    "agent_count": 5,
                    "active_agents": 3,
                    "total_tasks": 150,
                    "success_rate": 0.92,
                    "average_response_time": 2.3,
                },
                {
                    "department_id": "data",
                    "name": "Data Department",
                    "agent_count": 3,
                    "active_agents": 2,
                    "total_tasks": 89,
                    "success_rate": 0.88,
                    "average_response_time": 1.8,
                },
            ],
            "connections": [
                {"from": "ai", "to": "data", "strength": 0.8, "type": "data_flow"}
            ],
            "metrics": {
                "total_agents": 8,
                "active_agents": 5,
                "total_tasks": 239,
                "success_rate": 0.90,
            },
        }
    except Exception:
        return {
            "core": {"status": "error", "health": 0, "connections": 0},
            "departments": [],
            "connections": [],
            "metrics": {"total_agents": 0, "active_agents": 0, "total_tasks": 0, "success_rate": 0},
        }


def get_agent_metrics() -> Dict[str, Any]:
    """Get agent metrics in the format expected by frontend."""
    try:
        return {
            "agent_1": {
                "agent_id": "agent_1",
                "tasks_completed": 45,
                "tasks_failed": 2,
                "average_response_time": 1.2,
                "last_activity": datetime.now().isoformat(),
                "status": "idle",
            },
            "agent_2": {
                "agent_id": "agent_2",
                "tasks_completed": 32,
                "tasks_failed": 1,
                "average_response_time": 0.8,
                "last_activity": datetime.now().isoformat(),
                "status": "busy",
            },
        }
    except Exception:
        return {}


@router.get("/metrics")
async def get_system_metrics_endpoint(api_key: str | None = Security(_api_key_header)):
    """Get system metrics endpoint that frontend expects."""
    _require_api_key(api_key)
    try:
        data = get_system_metrics()
        data["memory_system"] = memory_snapshot()
        return data
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/hive/data")
async def get_hive_data_endpoint(api_key: str | None = Security(_api_key_header)):
    """Get hive data endpoint that frontend expects."""
    _require_api_key(api_key)
    try:
        return get_hive_data()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/agent-metrics")
async def get_agent_metrics_endpoint(api_key: str | None = Security(_api_key_header)):
    """Get agent metrics endpoint that frontend expects."""
    _require_api_key(api_key)
    try:
        return get_agent_metrics()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/memory")
async def get_memory_metrics_endpoint(api_key: str | None = Security(_api_key_header)):
    """Expose NBMF memory metrics snapshot for governance tools."""
    _require_api_key(api_key)
    return memory_snapshot()


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
async def get_memory_metrics_prometheus(api_key: str | None = Security(_api_key_header)) -> str:
    """Expose NBMF metrics in Prometheus text format."""
    _require_api_key(api_key)
    return _render_prometheus(memory_snapshot())
