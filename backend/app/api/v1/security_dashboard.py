"""/3vilbob Security Dashboard API.

Provides real-time scan status, tool catalog, SHIELD activation state,
scan trace history, and self-improvement metrics.

This is the backend for the /security/dashboard frontend page.
"""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class DashboardStatus(BaseModel):
    evilbob_active: bool = False
    environment: str = ""
    activated_at: str = ""
    activated_by: str = ""
    capabilities: list[str] = []
    shield_status: dict[str, bool] = {}
    tool_stats: dict[str, Any] = {}
    scan_history: list[dict[str, Any]] = []
    self_improvement: dict[str, Any] = {}


class ToolInfo(BaseModel):
    name: str
    category: str
    description: str
    capabilities: list[str]
    installed: bool = False
    install_cmd: str = ""
    offensive_only: bool = False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/status", response_model=DashboardStatus)
async def get_dashboard_status() -> DashboardStatus:
    """Full dashboard status: mode, shields, tools, history, self-improvement."""
    # Mode status
    try:
        from app.services.security.evilbob_mode import get_state
        state = get_state()
        evilbob_active = state.active
        environment = state.environment
        activated_at = state.activated_at
        activated_by = state.activated_by
        capabilities = state.capabilities
    except Exception:
        evilbob_active = False
        environment = "unknown"
        activated_at = ""
        activated_by = ""
        capabilities = []

    # SHIELD activation status
    try:
        from app.services.department_prompts import get_offensive_shield_status
        shield_status = get_offensive_shield_status()
    except Exception:
        shield_status = {}

    # Tool catalog stats
    try:
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()
        installed = catalog.get_installed()
        tool_stats = {
            "total_known": catalog.total_tools,
            "total_installed": len(installed),
            "total_capabilities": catalog.total_capabilities,
            "categories": catalog.categories,
            "installed_names": [t.name for t in installed],
        }
    except Exception:
        tool_stats = {"total_known": 0, "total_installed": 0}

    # Scan history (last 20 traces)
    scan_history = _load_scan_history(20)

    # Self-improvement metrics
    self_improvement = _get_self_improvement_metrics()

    return DashboardStatus(
        evilbob_active=evilbob_active,
        environment=environment,
        activated_at=activated_at,
        activated_by=activated_by,
        capabilities=capabilities,
        shield_status=shield_status,
        tool_stats=tool_stats,
        scan_history=scan_history,
        self_improvement=self_improvement,
    )


@router.get("/tools", response_model=list[ToolInfo])
async def list_tools(
    category: str = "",
    capability: str = "",
    installed_only: bool = False,
) -> list[ToolInfo]:
    """List security tools from the catalog with optional filters."""
    try:
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()

        if capability:
            tools = catalog.find_by_capability(capability)
        elif category:
            tools = catalog.find_by_category(category)
        else:
            tools = catalog.get_all()

        result = []
        for tool in tools:
            is_installed = catalog.is_installed(tool.name)
            if installed_only and not is_installed:
                continue
            result.append(ToolInfo(
                name=tool.name,
                category=tool.category,
                description=tool.description,
                capabilities=tool.capabilities,
                installed=is_installed,
                install_cmd=tool.install_cmd,
                offensive_only=tool.offensive_only,
            ))
        return result
    except Exception as exc:
        logger.error("security_dashboard.tools_failed", error=str(exc))
        return []


@router.get("/tools/recommend")
async def recommend_tools(
    target_type: str = "web_application",
    waf: str = "",
) -> list[ToolInfo]:
    """Get tool recommendations for a target type."""
    try:
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()
        tools = catalog.recommend_for_target(target_type, waf)
        return [
            ToolInfo(
                name=t.name,
                category=t.category,
                description=t.description,
                capabilities=t.capabilities,
                installed=catalog.is_installed(t.name),
                install_cmd=t.install_cmd,
                offensive_only=t.offensive_only,
            )
            for t in tools
        ]
    except Exception as exc:
        logger.error("security_dashboard.recommend_failed", error=str(exc))
        return []


@router.get("/scans")
async def list_scans(limit: int = 50) -> list[dict[str, Any]]:
    """List recent scan traces."""
    return _load_scan_history(limit)


@router.get("/scans/{scan_id}")
async def get_scan_detail(scan_id: str) -> dict[str, Any]:
    """Get full detail of a specific scan trace."""
    trace_dir = os.path.join(os.environ.get("DAENA_VAR", "var"), "scan_traces")
    trace_path = os.path.join(trace_dir, f"{scan_id}.json")
    if not os.path.isfile(trace_path):
        raise HTTPException(status_code=404, detail=f"Scan trace {scan_id} not found")
    try:
        with open(trace_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/shields")
async def get_shield_details() -> dict[str, Any]:
    """Get detailed SHIELD activation status for each department."""
    try:
        from app.services.security.evilbob_mode import is_active
        from app.services.department_prompts import (
            get_offensive_shield_status,
            _OFFENSIVE_SHIELD_PROMPTS,
        )

        active = is_active()
        status = get_offensive_shield_status()

        details = {}
        for dept, is_offensive in status.items():
            details[dept] = {
                "mode": "offensive" if is_offensive else "defensive",
                "active": is_offensive,
                "role_summary": (
                    _OFFENSIVE_SHIELD_PROMPTS.get(dept, "")[:150] + "..."
                    if is_offensive
                    else "Standard defensive security review"
                ),
            }

        return {
            "evilbob_active": active,
            "departments": details,
            "total_offensive": sum(1 for v in status.values() if v),
            "total_departments": len(status),
        }
    except Exception as exc:
        logger.error("security_dashboard.shields_failed", error=str(exc))
        return {"evilbob_active": False, "departments": {}}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_scan_history(limit: int = 20) -> list[dict[str, Any]]:
    """Load scan trace summaries from var/scan_traces/."""
    trace_dir = os.path.join(os.environ.get("DAENA_VAR", "var"), "scan_traces")
    if not os.path.isdir(trace_dir):
        return []

    traces = sorted(os.listdir(trace_dir), reverse=True)[:limit]
    history = []
    for trace_file in traces:
        trace_path = os.path.join(trace_dir, trace_file)
        try:
            with open(trace_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            history.append({
                "scan_id": data.get("scan_id", trace_file.replace(".json", "")),
                "target": data.get("target", ""),
                "target_type": data.get("target_type", ""),
                "total_findings": data.get("total_findings", 0),
                "cycles_used": data.get("cycles_used", 0),
                "strategies_tried": data.get("strategies_tried", []),
                "offensive_mode": data.get("offensive_mode", False),
                "exploits_succeeded": data.get("exploits_succeeded", 0),
                "waf_detected": data.get("waf_detected", ""),
            })
        except (json.JSONDecodeError, OSError):
            continue

    return history


def _get_self_improvement_metrics() -> dict[str, Any]:
    """Get metrics about the self-improvement loop."""
    trace_dir = os.path.join(os.environ.get("DAENA_VAR", "var"), "scan_traces")
    if not os.path.isdir(trace_dir):
        return {"total_traces": 0, "upgrades_triggered": 0}

    total = len(os.listdir(trace_dir))
    upgrades = total // 10  # Every 10 scans triggers an upgrade check

    return {
        "total_traces": total,
        "upgrades_triggered": upgrades,
        "next_upgrade_at": ((total // 10) + 1) * 10,
        "traces_until_next": ((total // 10) + 1) * 10 - total,
    }
