"""Autopilot endpoints: start, stop, approve, state, summary.

Manages the continuation loop for Autopilot ON mode. All endpoints
require authentication. State changes push WebSocket notifications.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, get_current_user
from app.core.logging import get_logger
from app.core.sse_channels import queue_channel

logger = get_logger(__name__)

router = APIRouter()


# Standard SSE response headers; matches the chat + scan stream
# convention so frontend EventSource clients see consistent framing
# across every Daena SSE endpoint.
_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


# ── Request/Response models ──


class AutopilotStartRequest(BaseModel):
    """Request to start autopilot for a session."""
    session_id: str
    cost_ceiling: float = Field(default=1.0, ge=0.01, le=100.0)
    governance_preset: str = "BALANCED"


class AutopilotApproveRequest(BaseModel):
    """Request to approve a paused step."""
    session_id: str
    step_id: str


class AutopilotRejectRequest(BaseModel):
    """Request to reject a paused step (stops autopilot)."""
    session_id: str
    step_id: str


class AutopilotStopRequest(BaseModel):
    """Request to kill autopilot for a session."""
    session_id: str


class AutopilotResponse(BaseModel):
    """Standard autopilot response."""
    success: bool
    message: str
    state: dict | None = None


# ── Dependency: get the global AutopilotController ──
# The controller is initialized in events.py alongside the runtime registry.
# For now, we use a module-level reference.

_autopilot_controller = None


def get_autopilot_controller():
    """Get the singleton AutopilotController. Lazy-initialized."""
    global _autopilot_controller
    if _autopilot_controller is not None:
        return _autopilot_controller

    from app.core.events import get_runtime_registry
    from app.services.autopilot.continuation import AutopilotController
    from app.services.autopilot.criticality_classifier import CriticalityClassifier
    from app.services.runtimes.cost_estimator import CostEstimator
    from app.services.swarm.executor import SwarmExecutor

    registry = get_runtime_registry()
    classifier = CriticalityClassifier()
    cost_estimator = CostEstimator()
    executor = SwarmExecutor(registry, cost_estimator)
    controller = AutopilotController(executor, classifier)

    _autopilot_controller = controller
    return controller


# ── Endpoints ──


@router.post("/start", response_model=AutopilotResponse)
async def start_autopilot(
    body: AutopilotStartRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Start autopilot continuation for a session.

    Decomposes the current session context into subtasks and begins
    the continuation loop. Each step is classified by criticality
    before execution.
    """
    controller = get_autopilot_controller()

    # Check if already running
    existing = controller.get_state(body.session_id)
    if existing and existing.enabled:
        raise HTTPException(
            status_code=409,
            detail="Autopilot is already running for this session",
        )

    # For now, start with an empty plan. The chat_orchestrator will
    # populate the plan when it detects autopilot mode and calls
    # the SwarmPlanner. This endpoint is for explicit user activation.
    state = await controller.start(
        session_id=body.session_id,
        plan=[],
        context={
            "cost_ceiling": body.cost_ceiling,
            "governance_preset": body.governance_preset,
            "user_id": str(user.id),
        },
    )

    return AutopilotResponse(
        success=True,
        message="Autopilot started",
        state=state.to_dict(),
    )


@router.post("/stop", response_model=AutopilotResponse)
async def stop_autopilot(
    body: AutopilotStopRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Kill switch: immediately stop autopilot for a session."""
    controller = get_autopilot_controller()
    killed = await controller.kill(body.session_id)

    if not killed:
        raise HTTPException(
            status_code=404,
            detail="No active autopilot session found",
        )

    state = controller.get_state(body.session_id)
    return AutopilotResponse(
        success=True,
        message="Autopilot stopped",
        state=state.to_dict() if state else None,
    )


@router.post("/approve", response_model=AutopilotResponse)
async def approve_step(
    body: AutopilotApproveRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Approve a paused step to continue autopilot execution."""
    controller = get_autopilot_controller()
    approved = await controller.approve_step(body.session_id, body.step_id)

    if not approved:
        raise HTTPException(
            status_code=404,
            detail="No paused step found matching this session and step ID",
        )

    return AutopilotResponse(
        success=True,
        message=f"Step {body.step_id} approved",
    )


@router.post("/reject", response_model=AutopilotResponse)
async def reject_step(
    body: AutopilotRejectRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Reject a paused step, stopping autopilot."""
    controller = get_autopilot_controller()
    rejected = await controller.reject_step(body.session_id, body.step_id)

    if not rejected:
        raise HTTPException(
            status_code=404,
            detail="No paused step found matching this session and step ID",
        )

    return AutopilotResponse(
        success=True,
        message=f"Step {body.step_id} rejected, autopilot stopped",
    )


@router.get("/state/{session_id}", response_model=AutopilotResponse)
async def get_state(
    session_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Get current autopilot state for a session."""
    controller = get_autopilot_controller()
    state = controller.get_state(session_id)

    if not state:
        return AutopilotResponse(
            success=True,
            message="No autopilot session",
            state=None,
        )

    return AutopilotResponse(
        success=True,
        message="Autopilot state retrieved",
        state=state.to_dict(),
    )


@router.get("/summary/{session_id}")
async def get_summary(
    session_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Get summary of autopilot work for a session."""
    controller = get_autopilot_controller()
    state = controller.get_state(session_id)

    if not state:
        return {
            "session_id": session_id,
            "completed": 0,
            "total": 0,
            "total_cost": 0.0,
            "notifications": [],
        }

    return {
        "session_id": session_id,
        "completed": len(state.completed_steps),
        "total": len(state.completed_steps) + len(state.pending_steps),
        "total_cost": state.total_cost_usd,
        "notifications": state.notifications[-20:],  # Last 20 notifications
    }


@router.get("/queue/events")
async def stream_queue_events(
    request: Request,
    _user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    """Server-sent events for background-queue task lifecycle.

    Subscribes to ``queue_channel`` and yields each envelope as a
    formatted SSE event. Emits the following event types:

    - ``task.enqueued`` ``{task_id, session_id, tenant_id, description,
      priority, created_at}`` -- a producer enqueued a new task.
    - ``task.started`` ``{task_id, session_id, description, started_at}``
      Worker pulled the task and the run is in progress.
    - ``task.completed`` ``{task_id, session_id, result, finished_at}``
      Executor returned successfully.
    - ``task.failed`` ``{task_id, session_id, error, finished_at}``
      Executor raised; the row was finalized with the error string.
    - ``task.cancelled`` ``{task_id, session_id}`` -- operator cancel.
    - ``task.cancel_all`` ``{session_id, cancelled}`` -- session-wide
      kill switch fired.
    - ``ping`` synthetic heartbeat every 25s of idle time.

    Connection stays open until the client disconnects.
    """

    async def _event_stream():
        async for envelope in queue_channel.subscribe():
            if await request.is_disconnected():
                break
            data = json.dumps(envelope)
            yield f"event: {envelope['type']}\ndata: {data}\n\n"

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.get("/queue/status")
async def get_queue_status(
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Return truthful persistence/worker status for the background queue."""
    from app.services.autopilot.background_queue import get_background_queue

    queue = get_background_queue()
    return {
        "success": True,
        "data": {
            "worker_running": queue.is_running,
            "persistent": queue.is_persistent,
            "storage": "database" if queue.is_persistent else "memory_only",
            "queued_count": queue.queued_count,
            "active_count": queue.active_count,
            "restart_policy": (
                "queued rows restore from DB; running rows are marked failed_due_to_restart"
                if queue.is_persistent
                else "queue state is memory-only until app lifespan initializes persistence"
            ),
        },
    }
