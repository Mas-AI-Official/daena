"""Mission Intelligence API -- autonomous red team operations.

Endpoints for starting, controlling, and monitoring autonomous
missions powered by MissionIntelligence.

Requires /3vilbob mode active for all operations.

BACKGROUND PATH ONLY -- never import in hot path
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class MissionStartRequest(BaseModel):
    goal: str
    target: str
    engagement_level: str = "pentest"  # audit, pentest, red_team, adversary


class MissionStatusResponse(BaseModel):
    mission_id: str = ""
    goal: str = ""
    target: str = ""
    engagement_level: str = ""
    status: str = ""
    current_phase: str = ""
    current_path: str = ""
    current_step: str = ""
    paths_total: int = 0
    paths_completed: int = 0
    paths_failed: int = 0
    nodes_discovered: int = 0
    dead_ends: int = 0
    pivots: int = 0
    elapsed_s: float = 0.0


# In-memory mission store (per-process, local only)
_active_missions: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/start")
async def start_mission(req: MissionStartRequest) -> dict[str, Any]:
    """Start a new autonomous mission.

    Requires /3vilbob mode active. Plans attack paths using
    goal-backward reasoning, maps proximity rings, generates
    attraction scenarios, and applies creative lenses.
    """
    from app.services.security.evilbob_mode import is_active
    if not is_active():
        raise HTTPException(
            status_code=403,
            detail="Mission operations require offensive mode active. Activate with /3vilbob key.",
        )

    from app.services.security.mission_intelligence import (
        EngagementLevel,
        MissionController,
    )

    # Validate engagement level
    try:
        level = EngagementLevel(req.engagement_level)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid engagement level: {req.engagement_level}. Use: audit, pentest, red_team, adversary",
        )

    controller = MissionController()
    status = await controller.start_mission(
        goal=req.goal,
        target=req.target,
        engagement_level=level,
    )

    # Store controller for subsequent operations
    _active_missions[status.mission_id] = controller

    return {
        "mission_id": status.mission_id,
        "status": status.status,
        "paths_total": status.paths_total,
        "nodes_discovered": status.nodes_discovered,
        "engagement_level": status.engagement_level.value,
    }


@router.get("/{mission_id}/status")
async def get_mission_status(mission_id: str) -> dict[str, Any]:
    """Get current mission status."""
    controller = _active_missions.get(mission_id)
    if not controller:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found")

    status = controller.get_status()
    return {
        "mission_id": status.mission_id,
        "goal": status.goal,
        "target": status.target,
        "engagement_level": status.engagement_level.value,
        "status": status.status,
        "current_phase": status.current_phase,
        "current_path": status.current_path,
        "current_step": status.current_step,
        "paths_total": status.paths_total,
        "paths_completed": status.paths_completed,
        "paths_failed": status.paths_failed,
        "nodes_discovered": status.nodes_discovered,
        "dead_ends": status.dead_ends,
        "pivots": status.pivots,
        "elapsed_s": status.elapsed_s,
    }


@router.post("/{mission_id}/execute")
async def execute_next_step(mission_id: str) -> dict[str, Any]:
    """Execute the next step in the mission."""
    controller = _active_missions.get(mission_id)
    if not controller:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found")

    result = await controller.execute_next_step()
    return result


@router.get("/{mission_id}/graph")
async def get_mission_graph(mission_id: str) -> dict[str, Any]:
    """Get the detective wall visualization data."""
    controller = _active_missions.get(mission_id)
    if not controller:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found")

    return controller.get_graph_visual()


@router.get("/{mission_id}/paths")
async def get_attack_paths(mission_id: str) -> list[dict[str, Any]]:
    """Get all attack paths with their steps."""
    controller = _active_missions.get(mission_id)
    if not controller:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found")

    return controller.get_paths_summary()


@router.get("/{mission_id}/proximity")
async def get_proximity_map(mission_id: str) -> list[dict[str, Any]]:
    """Get the proximity rings (what's AROUND the target)."""
    controller = _active_missions.get(mission_id)
    if not controller:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found")

    return controller.get_proximity_map()


@router.get("/{mission_id}/attraction")
async def get_attraction_scenarios(mission_id: str) -> list[dict[str, Any]]:
    """Get the 'target comes to you' scenarios."""
    controller = _active_missions.get(mission_id)
    if not controller:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found")

    return controller.get_attraction_scenarios()


@router.get("/{mission_id}/creative")
async def get_creative_paths(mission_id: str) -> list[dict[str, Any]]:
    """Get creative attack paths (outside-the-box thinking)."""
    controller = _active_missions.get(mission_id)
    if not controller:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found")

    return controller.get_creative_paths()


@router.get("/{mission_id}/weakest-link")
async def get_weakest_link(mission_id: str) -> dict[str, Any]:
    """Find the weakest link in the target's proximity chain."""
    controller = _active_missions.get(mission_id)
    if not controller:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found")

    weak = controller.get_weakest_link()
    if not weak:
        return {"message": "No proximity data available"}
    return weak


@router.get("/{mission_id}/traces")
async def get_trace_report(mission_id: str) -> dict[str, Any]:
    """Get the forensic trace report (what traces we left)."""
    controller = _active_missions.get(mission_id)
    if not controller:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found")

    return controller.get_trace_report()


@router.post("/{mission_id}/clean-traces")
async def clean_traces(mission_id: str) -> dict[str, Any]:
    """Clean all traces. ADVERSARY level only."""
    controller = _active_missions.get(mission_id)
    if not controller:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found")

    return await controller.clean_all_traces()


@router.get("/{mission_id}/engagement")
async def get_engagement_matrix(mission_id: str) -> dict[str, Any]:
    """Get the capability matrix for current engagement level."""
    controller = _active_missions.get(mission_id)
    if not controller:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found")

    return controller.get_engagement_matrix()


@router.get("/{mission_id}/opsec")
async def get_opsec_status(mission_id: str) -> dict[str, Any]:
    """Get the OpSec Shield status."""
    controller = _active_missions.get(mission_id)
    if not controller:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found")

    return controller.get_opsec_shield_report()


@router.post("/{mission_id}/save")
async def save_mission(mission_id: str) -> dict[str, Any]:
    """Save mission state for later resumption."""
    controller = _active_missions.get(mission_id)
    if not controller:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found")

    path = controller.save()
    return {"saved": True, "path": path, "mission_id": mission_id}


@router.post("/resume/{mission_id}")
async def resume_mission(mission_id: str) -> dict[str, Any]:
    """Resume a previously saved mission."""
    from app.services.security.mission_intelligence import MissionController

    try:
        controller = MissionController.resume(mission_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"No saved mission found: {mission_id}")

    _active_missions[mission_id] = controller
    status = controller.get_status()

    return {
        "mission_id": mission_id,
        "status": status.status,
        "goal": status.goal,
        "target": status.target,
        "nodes_discovered": status.nodes_discovered,
    }


@router.get("/active")
async def list_active_missions() -> list[dict[str, Any]]:
    """List all active missions."""
    missions = []
    for mid, controller in _active_missions.items():
        status = controller.get_status()
        missions.append({
            "mission_id": mid,
            "goal": status.goal,
            "target": status.target,
            "status": status.status,
            "engagement_level": status.engagement_level.value,
        })
    return missions
